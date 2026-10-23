#!/usr/bin/env python3
"""Lighting and atmosphere presets for iamar worlds (kit/style/lighting).

    lighting.py list
    lighting.py check [<preset.json|id|world folder> ...]
                                                       every preset when none is named; a world
                                                       folder checks its scene.json environment
    lighting.py apply <preset.json|id> <world folder> [--keep-sky]
    lighting.py bake-args <preset.json|id> [--world <folder> --object <id>] [--reach 12]
                                                       kit/blender/bake_unlit.py options that bake
                                                       the preset (and the world's lamps near that
                                                       object) into a static model
    lighting.py ao-args --world <folder> --object <id> [--reach 3]
                                                       kit/blender/bake_vertex_ao.py --occluder
                                                       options: the world's other models within
                                                       reach m of the object, in its frame, so a
                                                       time-independent AO bake (a running clock)
                                                       gets the contact darkness of its neighbours
    lighting.py measure <shot.png> ...                 luminance numbers per screenshot
    lighting.py sample <new folder> --godot <godot> --project <browser project>
    lighting.py render <world folder> <out dir> --godot <godot> --project <browser project>
                       [--preset id ...] [--view "x,y,z>lx,ly,lz" ...] [--size 1280x720]

A preset is only the scene.json `environment` block (docs/WORLD_FORMAT.md 4.1),
using fields the browser really reads (scripts/worlds/world_builder.gd
_environment in the iamar browser source (not public)). There are no bloom, glow, colour-grade or
tonemap fields in a package: the package renders with a linear tonemap and
`exposure`, so the grade is carried by sky, sun, ambient and fog colours.

`check` fails on unknown fields, malformed colours, pure black, a sun that is
below the horizon (time_of_day outside about 6.2-17.8 with no `direction`
gives the sun zero energy in a package), a moving sun (`day_length_minutes`
> 0, no `direction`) whose colour x energy is strongly warm (it is overhead at
noon: orange cobbles and yellow grass, harbour a5 an internal task) and warm fog (a peach fog tinted the
city valley yellow: MASTERPLAN_TODO B15, FAILED). `render` copies the world to
a scratch folder, applies each preset and shoots it with the browser's
`world_view.gd` (the engine behind `iamar-world preview`), then writes
numbers.json and a contact sheet. Python 3; measure/render need Pillow and numpy.
"""
from __future__ import annotations

import colorsys
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRESETS = HERE / "presets"
SCHEMA = "iamar-lighting-preset/1"

# Every environment field the v0 browser reads (world_builder.gd _environment)
# or accepts as reserved (weather), per sub-object. Nothing else is allowed.
FIELDS = {
    "sky": {"type", "top_color", "horizon_color", "ground_color", "color", "energy",
            "faces", "rotation"},
    "sun": {"enabled", "color", "energy", "shadows", "direction"},
    "ambient": {"color", "energy", "source"},
    "fog": {"enabled", "color", "density", "height", "height_density"},
    "weather": {"kind", "intensity"},
}
SCALARS = {"time_of_day", "day_length_minutes", "exposure"}
SKY_TYPES = {"procedural", "color", "cubemap"}
WEATHER = {"clear", "cloudy", "rain", "storm", "snow"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
COLOR_KEYS = {"top_color", "horizon_color", "ground_color", "color"}

# The default eye-height cameras for the sample world (kit/style/lighting/README.md).
DEFAULT_VIEWS = [
    ("street", "0,1.7,9>0,2.5,-14"),
    ("houses", "13,1.7,4>-6,3,-12"),
    ("above", "0,22,30>0,0,-8"),
]


def sun_position(h: float) -> tuple[float, float, float]:
    """Unit vector toward the sun at hour h (world_builder.gd sun_position)."""
    t = (h - 6.0) / 12.0 * math.pi
    tilt = math.radians(62.0)
    v = (math.cos(t), math.sin(t) * math.sin(tilt), math.sin(t) * math.cos(tilt))
    n = math.sqrt(sum(a * a for a in v))
    return tuple(a / n for a in v)


def sun_factor(env: dict) -> float:
    """The browser's energy multiplier for the sun (1 when direction is given)."""
    sun = env.get("sun", {})
    if "direction" in sun:
        return 1.0
    y = sun_position(float(env.get("time_of_day", 12.0)))[1]
    return min(1.0, max(0.0, y * 4.0))


def resolve(name: str) -> Path:
    p = Path(name)
    if p.suffix == ".json" and p.exists():
        return p
    q = PRESETS / f"{name}.json"
    if q.exists():
        return q
    raise SystemExit(f"lighting: no preset {name!r} (have: {', '.join(ids())})")


def ids() -> list[str]:
    return sorted(p.stem for p in PRESETS.glob("*.json"))


def _rgb(hexs: str) -> tuple[float, float, float]:
    return tuple(int(hexs[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


def check_env(env: dict, where: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    if not isinstance(env, dict):
        return [f"{where}: environment must be an object"], warns
    for k, v in env.items():
        if k.startswith("x-"):
            continue
        if k in SCALARS:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                errors.append(f"{where}.{k}: must be a number")
            continue
        if k not in FIELDS:
            errors.append(f"{where}.{k}: not a scene environment field (allowed: "
                          f"{', '.join(sorted(set(FIELDS) | SCALARS))}); the browser has no "
                          "bloom, glow, grade or tonemap fields")
            continue
        if not isinstance(v, dict):
            errors.append(f"{where}.{k}: must be an object")
            continue
        for kk, vv in v.items():
            if kk.startswith("x-"):
                continue
            if k == "fog" and kk == "sky_affect":
                if not isinstance(vv, (int, float)) or isinstance(vv, bool) or not 0 <= vv <= 1:
                    errors.append(f"{where}.fog.sky_affect: must be a number from 0 to 1, got {vv!r}")
                else:
                    warns.append(f"{where}.fog.sky_affect: browsers older than iamar 24028ff (schema fix "
                                 "an internal task; pinned browser 0bef8c6d) refuse the whole world with it")
            elif kk not in FIELDS[k]:
                errors.append(f"{where}.{k}.{kk}: unknown (allowed: {', '.join(sorted(FIELDS[k]))})")
            elif kk in COLOR_KEYS:
                if not isinstance(vv, str) or not HEX.match(vv):
                    errors.append(f"{where}.{k}.{kk}: colour must be #rrggbb, got {vv!r}")
                elif vv.lower() == "#000000":
                    errors.append(f"{where}.{k}.{kk}: pure black (nothing is pure black)")
    sky = env.get("sky", {})
    if isinstance(sky, dict) and sky.get("type", "procedural") not in SKY_TYPES:
        errors.append(f"{where}.sky.type: one of {sorted(SKY_TYPES)}")
    w = env.get("weather", {})
    if isinstance(w, dict) and w.get("kind", "clear") not in WEATHER:
        errors.append(f"{where}.weather.kind: one of {sorted(WEATHER)}")
    elif isinstance(w, dict) and w.get("kind", "clear") != "clear":
        warns.append(f"{where}.weather.kind: reserved in the v0 browser (accepted, not drawn)")
    sun = env.get("sun", {})
    if isinstance(sun, dict) and sun.get("enabled", True):
        d = sun.get("direction")
        if d is not None:
            if not (isinstance(d, list) and len(d) == 3 and all(isinstance(a, (int, float)) for a in d)):
                errors.append(f"{where}.sun.direction: three numbers")
            elif d[1] >= 0:
                errors.append(f"{where}.sun.direction: y must be negative (light travels down)")
        else:
            f = sun_factor(env)
            if f <= 0.0:
                errors.append(f"{where}.time_of_day {env.get('time_of_day', 12.0)}: the sun is below "
                              "the horizon, so the browser gives it zero energy; use sun.direction "
                              "for a low sun or a moon, or sun.enabled false")
            elif f < 0.75:
                warns.append(f"{where}.time_of_day: the sun is very low, energy x{f:.2f}")
            moving_sun(env, where, errors, warns)
    fog = env.get("fog", {})
    if isinstance(fog, dict) and fog.get("enabled", bool(fog)):
        c = fog.get("color")
        if isinstance(c, str) and HEX.match(c):
            h, l, s = colorsys.rgb_to_hls(*_rgb(c))
            hue = h * 360.0
            if 15.0 <= hue <= 65.0 and s > 0.35 and l > 0.45:
                errors.append(f"{where}.fog.color {c}: warm, light fog tints the whole view yellow "
                              "(MASTERPLAN_TODO B15, FAILED); keep the warmth in the sun, the fog cool")
        dens = fog.get("density", 0.01)
        if isinstance(dens, (int, float)) and dens > 0.02:
            warns.append(f"{where}.fog.density {dens}: very thick (0.002-0.01 is haze)")
    ex = env.get("exposure", 1.0)
    if isinstance(ex, (int, float)) and not 0.5 <= ex <= 2.0:
        warns.append(f"{where}.exposure {ex}: outside 0.5-2.0")
    return errors, warns


# A sun that moves (no `direction`, `day_length_minutes` > 0) stands overhead at noon with the
# colour and energy chosen for its low hour. The golden-hour sun (#ffb064 x 1.8) on a moving clock
# turned the harbour's grey cobbles orange and its grass yellow every day shot (harbour a4 an internal task,
# a5 an internal task). Warmth here = energy x (red - blue) of the sun colour: the browser default #fff4e0
# x 1 is 0.12, golden hour 1.10.
MOVING_SUN_WARM_ERROR = 0.40
MOVING_SUN_WARM_WARN = 0.25
MOVING_SUN_ENERGY_WARN = 1.4


def moving_sun(env: dict, where: str, errors: list[str], warns: list[str]) -> None:
    sun = env.get("sun", {})
    dl = env.get("day_length_minutes", 0)
    if not isinstance(sun, dict) or "direction" in sun or not isinstance(dl, (int, float)) or dl <= 0:
        return
    c = sun.get("color", "#fff4e0")
    e = sun.get("energy", 1.0)
    if not (isinstance(c, str) and HEX.match(c)) or not isinstance(e, (int, float)):
        return
    r, _, b = _rgb(c)
    warm = e * (r - b)
    rule = (f"{where}.sun: the sun moves (day_length_minutes {dl}, no direction), so at noon it stands "
            f"overhead at {c} x {e}: warmth {warm:.2f} (energy x (red - blue))")
    fix = ("; keep a moving sun near white (#fff4e0, energy about 1: preset `day`) and carry the warmth "
           "in sky, ambient and surfaces, or fix the hour with sun.direction (harbour a4 3360, a5 3690)")
    if warm > MOVING_SUN_WARM_ERROR:
        errors.append(rule + f" > {MOVING_SUN_WARM_ERROR}: grey cobbles turn orange and grass yellow by day" + fix)
    elif warm > MOVING_SUN_WARM_WARN:
        warns.append(rule + f" > {MOVING_SUN_WARM_WARN}: the day reads warm" + fix)
    if e > MOVING_SUN_ENERGY_WARN:
        warns.append(f"{where}.sun.energy {e}: a moving sun this strong overexposes noon (keep it near 1)")


def check_world(world: Path) -> tuple[list[str], list[str]]:
    """The environment of a world folder's scene.json, under the preset rules."""
    try:
        scene = json.loads((world / "scene.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"{world}: {e}"], []
    return check_env(scene.get("environment", {}), f"{world.name}/scene.json environment")


def check_preset(path: Path) -> tuple[list[str], list[str]]:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"{path.name}: {e}"], []
    errors: list[str] = []
    if d.get("schema") != SCHEMA:
        errors.append(f"{path.name}: schema must be {SCHEMA!r}")
    if d.get("id") != path.stem:
        errors.append(f"{path.name}: id must equal the file name ({path.stem})")
    for k in ("title", "description"):
        if not isinstance(d.get(k), str) or not d.get(k):
            errors.append(f"{path.name}: {k} is required")
    e2, w = check_env(d.get("environment"), f"{path.stem}.environment")
    return errors + e2, w


def apply(preset: Path, world: Path, keep_sky: bool = False) -> dict:
    d = json.loads(preset.read_text(encoding="utf-8"))
    scene_p = world / "scene.json"
    scene = json.loads(scene_p.read_text(encoding="utf-8"))
    env = json.loads(json.dumps(d["environment"]))
    old = scene.get("environment", {})
    if keep_sky and "sky" in old:
        env["sky"] = old["sky"]
    scene["environment"] = env
    scene_p.write_text(json.dumps(scene, indent=1) + "\n", encoding="utf-8")
    return env


def _kit(godot: str, project: str, *args: str) -> str:
    flags = 0x00004000 if os.name == "nt" else 0
    p = subprocess.run([godot, "--headless", "--path", project, "--", "--kit", *args],
                       capture_output=True, text=True, timeout=600, creationflags=flags)
    if p.returncode != 0:
        raise SystemExit(f"lighting sample: kit {args[0]} failed\n{(p.stdout + p.stderr)[-1500:]}")
    return p.stdout


def sample(folder: Path, godot: str, project: str) -> Path:
    """Build the lighting sample world: the kit starter meadow, three generated
    houses (live-lit, so the presets show), primitive trees and two warm lamps."""
    if folder.exists():
        raise SystemExit(f"lighting sample: {folder} exists; give a new folder")
    _kit(godot, project, "new", str(folder), "--id", "lighting_sample", "--title",
         "Lighting sample", "--author", "iamar kit")
    for kind, style, w, d, fl, name in [("house", "plaster", 8, 6, 2, "house_a"),
                                        ("blacksmith", "stone", 9, 7, 1, "smithy"),
                                        ("house", "brick", 7, 6, 1, "house_b")]:
        _kit(godot, project, "assets", "building", kind, str(folder / "assets" / f"{name}.glb"),
             "--width", str(w), "--depth", str(d), "--floors", str(fl), "--style", style)
    sp = folder / "scene.json"
    s = json.loads(sp.read_text(encoding="utf-8"))
    s["objects"] = [
        {"id": "house_a", "asset": "assets/house_a.glb", "position": [-9, 0, -6], "rotation": [0, 20, 0], "collision": "box"},
        {"id": "smithy", "asset": "assets/smithy.glb", "position": [8, 0, -10], "rotation": [0, -15, 0], "collision": "box"},
        {"id": "house_b", "asset": "assets/house_b.glb", "position": [-2, 0, -20], "rotation": [0, 5, 0], "collision": "box"},
    ]
    prims = list(s.get("primitives", []))
    for i, (x, z, r) in enumerate([(-16, 4, 2.6), (14, 2, 2.2), (4, -28, 3.0),
                                   (-14, -22, 2.4), (18, -20, 2.8), (-6, 12, 2.0)]):
        prims.append({"id": f"trunk{i}", "shape": "cylinder", "radius": 0.3, "height": 3,
                      "position": [x, 1.5, z], "color": "#6b5038", "collision": "box"})
        prims.append({"id": f"crown{i}", "shape": "sphere", "radius": r, "position": [x, 3 + r * 0.8, z],
                      "color": "#4f7a3a" if i % 2 else "#5d8a3c"})
    lamps = [(-6.5, -2.2), (5.5, -5.6)]
    for i, (x, z) in enumerate(lamps):
        prims.append({"id": f"lamp{i}", "shape": "sphere", "radius": 0.18, "position": [x, 2.4, z],
                      "emission": "#ffcc77", "unlit": True})
    s["primitives"] = prims
    s["lights"] = [{"id": f"lamp{i}", "type": "point", "position": [x, 2.4, z], "color": "#ffc070",
                    "energy": 1.6, "range": 9} for i, (x, z) in enumerate(lamps)]
    s["terrain"]["size"] = [800, 800]
    s["terrain"]["materials"] = [{"color": "#6a8a4a"}]
    sp.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
    mp = folder / "manifest.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["features"] = sorted(set(m.get("features", [])) | {"objects", "lights"})
    # each generated building carries about 17 MB of texture memory; the starter's
    # 64 MB texture budget refuses the third one
    m["budgets"]["texture_bytes"] = 134217728
    mp.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    _kit(godot, project, "validate", str(folder))
    return folder


def measure(png: Path) -> dict:
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(png).convert("RGB"), dtype=np.float32) / 255.0
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    r, b = a[..., 0].mean(), a[..., 2].mean()
    return {
        "mean_luma": round(float(lum.mean()), 3),
        "p05_luma": round(float(np.percentile(lum, 5)), 3),
        "p95_luma": round(float(np.percentile(lum, 95)), 3),
        "clipped_pct": round(float((lum >= 0.98).mean() * 100.0), 2),
        "crushed_pct": round(float((lum <= 0.02).mean() * 100.0), 2),
        "warmth": round(float(r - b), 3),   # >0 warm, <0 cool
        "contrast": round(float(lum.std()), 3),
    }


def render(world: Path, out: Path, godot: str, project: str, presets: list[str],
           views: list[tuple[str, str]], size: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    results: dict = {"world": world.name, "size": size,
                     "views": {n: v for n, v in views}, "presets": {}}
    flags = 0x00004000 if os.name == "nt" else 0   # BELOW_NORMAL_PRIORITY_CLASS
    with tempfile.TemporaryDirectory(prefix="iamar_lighting_") as tmp:
        work = Path(tmp) / world.name
        shutil.copytree(world, work)
        for pid in presets:
            env = apply(resolve(pid), work)
            cmd = [godot, "--path", project, "-s", "res://scripts/kit/world_view.gd", "--",
                   str(work), str(out / pid), "--npcs", "none", "--frames", "30",
                   "--size", size]
            for _, v in views:
                cmd += ["--view", v]
            pre = [] if os.name == "nt" else ["nice", "-n", "19"]
            p = subprocess.run(pre + cmd, capture_output=True, text=True, timeout=600,
                               creationflags=flags)
            lines = [ln for ln in p.stdout.splitlines() if ln.startswith("VIEW ")]
            shots = {}
            for ln in lines:
                m = re.match(r"VIEW (\d+) (\S+) draw=(\d+) prims=(\d+) objects=(\d+) fps=([\d.]+) -> (.+)$", ln)
                if not m:
                    continue
                i = int(m.group(1))
                name = views[i][0] if i < len(views) else m.group(2)
                png = Path(m.group(7).strip())
                final = out / f"{pid}_{name}.png"
                if png.exists():
                    png.replace(final)
                shots[name] = {"draw_calls": int(m.group(3)), "primitives": int(m.group(4)),
                               "objects": int(m.group(5)), "fps": float(m.group(6)),
                               "image": final.name, **(measure(final) if final.exists() else {})}
            # world_view exits 1 when a performance TARGET fails (e.g. draw calls) even
            # though every shot was taken; record the targets, judge the shots.
            targets = [ln for ln in p.stdout.splitlines() if ln.startswith("TARGET ")]
            results["presets"][pid] = {"environment": env, "sun_energy_factor": sun_factor(env),
                                       "exit": p.returncode, "targets": targets, "shots": shots}
            if len(shots) != len(views):
                results["presets"][pid]["log_tail"] = (p.stdout + p.stderr)[-2000:]
    (out / "numbers.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    sheet(out, presets, [n for n, _ in views])
    return results


def sheet(out: Path, presets: list[str], views: list[str], tile: int = 480) -> Path | None:
    from PIL import Image, ImageDraw
    cells = [[out / f"{p}_{v}.png" for v in views] for p in presets]
    if not any(c.exists() for row in cells for c in row):
        return None
    th = tile * 9 // 16
    img = Image.new("RGB", (tile * len(views), (th + 22) * len(presets)), (24, 24, 28))
    dr = ImageDraw.Draw(img)
    for r, row in enumerate(cells):
        y = r * (th + 22)
        dr.text((6, y + 4), presets[r], fill=(235, 235, 235))
        for c, f in enumerate(row):
            if f.exists():
                img.paste(Image.open(f).convert("RGB").resize((tile, th)), (c * tile, y + 22))
    p = out / "sheet.png"
    img.save(p)
    return p


# Blender watts for one unit of a scene.json point light's energy, so a lamp baked into the walls
# lights them about as the live light does (calibrated on the night bake demo, gallery/night_bake)
WATTS_PER_ENERGY = 45.0


def _lin(hexs: str) -> list[float]:
    return [round(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4, 4) for c in _rgb(hexs)]


def bake_args(preset: Path, world: Path | None = None, obj: str | None = None, reach: float = 12.0) -> list[str]:
    """kit/blender/bake_unlit.py options that bake a preset's light into static models: the sun
    (or moon) from the preset's direction or time, its colour and energy (x pi: a Cycles sun of
    strength pi lights white as the browser's energy 1 does), the ambient as a uniform sky, and,
    given a world and an object id, that world's point lights within their range + `reach` m
    of the object's bounds (its origin when the .glb has none), moved into the object's own frame (sun too) (position, yaw and scale; watts / scale^2)."""
    env = json.loads(preset.read_text(encoding="utf-8"))["environment"]
    sun, amb = env.get("sun", {}), env.get("ambient", {})
    frame, scene = None, None
    if world is not None and obj:
        scene = json.loads((world / "scene.json").read_text(encoding="utf-8"))
        o = next((x for x in scene.get("objects", []) if x.get("id") == obj), None)
        if o is None:
            raise SystemExit(f"lighting: {world}/scene.json has no object {obj!r}")
        pos = [float(c) for c in o.get("position", [0, 0, 0])]
        rot = o.get("rotation", [0, o.get("yaw", 0), 0])
        if abs(float(rot[0])) > 1e-6 or abs(float(rot[2])) > 1e-6:
            print(f"WARN {obj}: only its yaw is applied to the sun and lamps (rotation {rot})", file=sys.stderr)
        sc = o.get("scale", 1)
        sc = [float(sc)] * 3 if isinstance(sc, (int, float)) else [float(c) for c in sc]
        if any(c == 0 for c in sc):
            raise SystemExit(f"lighting: {obj} has a zero scale {sc}: its frame has no lamp positions")
        frame = (pos, math.radians(float(rot[1])), sc, _asset_bounds(world, o))
    out = []
    energy = float(sun.get("energy", 1.0)) * sun_factor(env)
    if not sun.get("enabled", True) or energy <= 0:
        out.append("--no-sun")
    else:
        d = sun.get("direction")
        to_sun = [-float(c) for c in d] if d else list(sun_position(float(env.get("time_of_day", 12.0))))
        if frame:  # the sun direction goes into the object's frame like the lamps: yaw undone, then
            # divided by the scale (mirrored axes flip; a stretched axis changes the sun's angle, so
            # shading and shadows on the unscaled mesh match the scaled one; an internal task)
            _, yaw, sc, _ = frame
            x = to_sun[0] * math.cos(yaw) - to_sun[2] * math.sin(yaw)
            z = to_sun[0] * math.sin(yaw) + to_sun[2] * math.cos(yaw)
            v = [x / sc[0], to_sun[1] / sc[1], z / sc[2]]
            k = math.sqrt(sum(c * c for c in to_sun)) / (math.sqrt(sum(c * c for c in v)) or 1.0)
            to_sun = [c * k for c in v]  # same length as given; only the direction changes
        out += ["--sun=" + ",".join("%.3f" % c for c in to_sun),
                "--sun-color=" + ",".join("%.4f" % c for c in _lin(sun.get("color", "#ffffff"))),
                "--sun-strength", "%.3f" % (energy * math.pi)]
    out += ["--sky=" + ",".join("%.4f" % c for c in _lin(amb.get("color", "#ffffff"))),
            "--sky-strength", "%.3f" % float(amb.get("energy", 0.5))]
    if frame:
        pos, yaw, sc, bounds = frame
        for li in scene.get("lights", []):
            if li.get("type", "point") != "point":
                continue
            lp = [float(c) for c in li.get("position", [0, 0, 0])]
            dx, dy, dz = lp[0] - pos[0], lp[1] - pos[1], lp[2] - pos[2]
            # the lamp in the object's frame before the scale division
            rx = dx * math.cos(yaw) - dz * math.sin(yaw)
            rz = dx * math.sin(yaw) + dz * math.cos(yaw)
            if bounds:  # distance to the object's bounds (scaled), not to its origin
                lo, hi = bounds
                dist = math.sqrt(sum(
                    max(min(a * k, b * k) - v, 0.0, v - max(a * k, b * k)) ** 2
                    for v, a, b, k in zip((rx, dy, rz), lo, hi, sc)))
            else:
                dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist > float(li.get("range", 5)) + reach:
                continue
            lx, lz = rx / sc[0], rz / sc[2]
            col = _lin(li.get("color", "#ffffff"))
            # the object's frame shrinks distances by its scale, so the lamp's light falls off
            # over 1/scale^2 the distance: dim it by scale^2 to light the walls as the live light does
            s2 = abs(sc[0] * sc[1] * sc[2]) ** (2.0 / 3.0)  # a mirrored axis keeps its size
            out.append("--lamp=%.3f,%.3f,%.3f,%.4f,%.4f,%.4f,%.1f" % (
                lx, dy / sc[1], lz, *col, float(li.get("energy", 1.0)) * WATTS_PER_ENERGY / s2))
    return out


def _placement(o: dict, name: str) -> list[list[float]]:
    """4x4 glTF-space matrix T(position) Ry(yaw) S(scale) of a scene.json object (yaw only)."""
    pos = [float(c) for c in o.get("position", [0, 0, 0])]
    rot = o.get("rotation", [0, o.get("yaw", 0), 0])
    if abs(float(rot[0])) > 1e-6 or abs(float(rot[2])) > 1e-6:
        print(f"WARN {name}: only its yaw is applied (rotation {rot})", file=sys.stderr)
    sc = o.get("scale", 1)
    sc = [float(sc)] * 3 if isinstance(sc, (int, float)) else [float(c) for c in sc]
    y = math.radians(float(rot[1]))
    c, s = math.cos(y), math.sin(y)
    return [[c * sc[0], 0.0, s * sc[2], pos[0]],
            [0.0, sc[1], 0.0, pos[1]],
            [-s * sc[0], 0.0, c * sc[2], pos[2]],
            [0.0, 0.0, 0.0, 1.0]]


def _mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _inverse_affine(m: list[list[float]]) -> list[list[float]]:
    """Inverse of an affine 4x4 (3x3 part by cofactors)."""
    a = [r[:3] for r in m[:3]]
    det = (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
           + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    if abs(det) < 1e-12:
        raise SystemExit("lighting: an object with a zero scale has no frame")
    inv = [[(a[(j + 1) % 3][(i + 1) % 3] * a[(j + 2) % 3][(i + 2) % 3]
             - a[(j + 1) % 3][(i + 2) % 3] * a[(j + 2) % 3][(i + 1) % 3]) / det for j in range(3)] for i in range(3)]
    t = [-sum(inv[i][k] * m[k][3] for k in range(3)) for i in range(3)]
    return [inv[0] + [t[0]], inv[1] + [t[1]], inv[2] + [t[2]], [0.0, 0.0, 0.0, 1.0]]


def _world_box(m: list[list[float]], bounds) -> tuple[list[float], list[float]]:
    """World-space axis-aligned box of local bounds (the origin when there are none)."""
    lo, hi = bounds if bounds else ([0.0] * 3, [0.0] * 3)
    pts = [[sum(m[i][k] * p[k] for k in range(3)) + m[i][3] for i in range(3)]
           for p in ([x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2]))]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def ao_args(world: Path, obj: str, reach: float = 3.0) -> list[str]:
    """kit/blender/bake_vertex_ao.py --occluder options for one object of a world: every other
    placed .glb whose box comes within `reach` m of the object's box, as path + the row-major 3x4
    glTF matrix that puts it into the object's own frame (inverse(object) x neighbour). Models that
    move (animation, sway) and primitives are left out: say so on stderr."""
    scene = json.loads((world / "scene.json").read_text(encoding="utf-8"))
    objs = scene.get("objects", [])
    o = next((x for x in objs if x.get("id") == obj), None)
    if o is None:
        raise SystemExit(f"lighting: {world}/scene.json has no object {obj!r}")
    mt = _placement(o, obj)
    lo_t, hi_t = _world_box(mt, _asset_bounds(world, o))
    inv = _inverse_affine(mt)
    out, moving = [], []
    for i, n in enumerate(objs):
        if n is o:
            continue
        asset = str(n.get("asset", ""))
        if not asset.lower().endswith(".glb") or not (world / asset).is_file():
            continue
        name = n.get("id", "objects[%d]" % i)
        mn = _placement(n, name)
        lo, hi = _world_box(mn, _asset_bounds(world, n))
        gap = math.sqrt(sum(max(lo[k] - hi_t[k], 0.0, lo_t[k] - hi[k]) ** 2 for k in range(3)))
        if gap > reach:
            continue
        if n.get("animation") or n.get("sway"):
            moving.append(name)
            continue
        r = _mul(inv, mn)
        out.append("--occluder=" + str(world / asset) + "," + ",".join("%.5f" % r[a][b] for a in range(3) for b in range(4)))
    if moving:
        print(f"NOTE {obj}: left out moving neighbours {', '.join(moving)}", file=sys.stderr)
    if scene.get("primitives"):
        print(f"NOTE {obj}: primitives are not occluders (only placed .glb models are)", file=sys.stderr)
    return out


def _asset_bounds(world: Path, o: dict):
    """Local min/max of a .glb object's POSITION accessors (no node transforms), or None."""
    asset = o.get("asset")
    if not asset or not str(asset).lower().endswith(".glb"):
        return None
    try:
        data = (world / asset).read_bytes()
        if data[:4] != b"glTF":
            return None
        n = int.from_bytes(data[12:16], "little")
        doc = json.loads(data[20:20 + n])
        lo, hi = [], []
        for m in doc.get("meshes", []):
            for pr in m.get("primitives", []):
                acc = doc["accessors"][pr["attributes"]["POSITION"]]
                lo.append(acc["min"]); hi.append(acc["max"])
        if not lo:
            return None
        return ([min(c) for c in zip(*lo)], [max(c) for c in zip(*hi)])
    except (OSError, ValueError, KeyError, IndexError):
        return None


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "list":
        for i in ids():
            d = json.loads((PRESETS / f"{i}.json").read_text(encoding="utf-8"))
            print(f"{i:12s} {d.get('title', '')}: {d.get('description', '')}")
        return 0
    if cmd == "check":
        paths = [Path(n) if (Path(n) / "scene.json").is_file() else resolve(n) for n in rest]             or [PRESETS / f"{i}.json" for i in ids()]
        bad = 0
        for p in paths:
            errors, warns = check_world(p) if p.is_dir() else check_preset(p)
            for w in warns:
                print("WARN", w)
            for e in errors:
                print("ERROR", e)
            bad += bool(errors)
            print(("FAIL " if errors else "OK   ") + p.stem)
        return 1 if bad else 0
    if cmd == "apply":
        if len(rest) < 2:
            print("usage: lighting.py apply <preset> <world folder> [--keep-sky]", file=sys.stderr)
            return 2
        p = resolve(rest[0])
        errors, _ = check_preset(p)
        if errors:
            print("\n".join("ERROR " + e for e in errors), file=sys.stderr)
            return 1
        apply(p, Path(rest[1]), "--keep-sky" in rest[2:])
        print(f"APPLIED {p.stem} -> {Path(rest[1]) / 'scene.json'}")
        return 0
    if cmd == "bake-args":
        pos, opts, i = [], {"--world": None, "--object": None, "--reach": "12"}, 0
        while i < len(rest):
            if rest[i] in opts and i + 1 < len(rest):
                opts[rest[i]] = rest[i + 1]; i += 2; continue
            pos.append(rest[i]); i += 1
        if len(pos) != 1 or bool(opts["--world"]) != bool(opts["--object"]):
            print("usage: lighting.py bake-args <preset> [--world <folder> --object <id>] [--reach 12]", file=sys.stderr)
            return 2
        args = bake_args(resolve(pos[0]), Path(opts["--world"]) if opts["--world"] else None, opts["--object"],
                         float(opts["--reach"]))
        print(" ".join(args))
        return 0
    if cmd == "ao-args":
        opts, i = {"--world": None, "--object": None, "--reach": "3"}, 0
        while i < len(rest):
            if rest[i] in opts and i + 1 < len(rest):
                opts[rest[i]] = rest[i + 1]; i += 2; continue
            opts = None; break
        if not opts or not opts["--world"] or not opts["--object"]:
            print("usage: lighting.py ao-args --world <folder> --object <id> [--reach 3]", file=sys.stderr)
            return 2
        args = ao_args(Path(opts["--world"]), opts["--object"], float(opts["--reach"]))
        print(" ".join(shlex.quote(a) for a in args))
        return 0
    if cmd == "measure":
        for f in rest:
            print(f, json.dumps(measure(Path(f))))
        return 0
    if cmd == "sample":
        o = {"--godot": os.environ.get("IAMAR_GODOT", ""), "--project": os.environ.get("IAMAR_PROJECT", "")}
        pos = []
        i = 0
        while i < len(rest):
            if rest[i] in o and i + 1 < len(rest):
                o[rest[i]] = rest[i + 1]; i += 2; continue
            pos.append(rest[i]); i += 1
        if len(pos) != 1 or not o["--godot"] or not o["--project"]:
            print("usage: lighting.py sample <new folder> --godot <exe> --project <browser project>",
                  file=sys.stderr)
            return 2
        print(f"SAMPLE {sample(Path(pos[0]), o['--godot'], o['--project'])}")
        return 0
    if cmd == "render":
        opts = {"--godot": os.environ.get("IAMAR_GODOT", ""),
                "--project": os.environ.get("IAMAR_PROJECT", ""), "--size": "1280x720"}
        pre, vws, pos = [], [], []
        i = 0
        while i < len(rest):
            a = rest[i]
            if a in opts and i + 1 < len(rest):
                opts[a] = rest[i + 1]; i += 2; continue
            if a == "--preset" and i + 1 < len(rest):
                pre.append(rest[i + 1]); i += 2; continue
            if a == "--view" and i + 1 < len(rest):
                vws.append((f"view{len(vws)}", rest[i + 1])); i += 2; continue
            pos.append(a); i += 1
        if len(pos) != 2 or not opts["--godot"] or not opts["--project"]:
            print("usage: lighting.py render <world> <out> --godot <exe> --project <browser project>",
                  file=sys.stderr)
            return 2
        res = render(Path(pos[0]), Path(pos[1]), opts["--godot"], opts["--project"],
                     pre or ids(), vws or DEFAULT_VIEWS, opts["--size"])
        bad = 0
        for pid, r in res["presets"].items():
            for v, s in r["shots"].items():
                print(f"SHOT {pid:12s} {v:8s} luma={s.get('mean_luma')} clip={s.get('clipped_pct')}% "
                      f"crush={s.get('crushed_pct')}% warmth={s.get('warmth')} draw={s['draw_calls']} "
                      f"prims={s['primitives']}")
            if len(r["shots"]) != len(res["views"]):
                bad += 1
                print(f"FAIL {pid}: {len(r['shots'])} of {len(res['views'])} shots "
                      f"(exit {r['exit']})\n{r.get('log_tail', '')}")
        return 1 if bad else 0
    print(f"lighting: unknown command {cmd!r} (list, check, apply, bake-args, measure, sample, render)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
