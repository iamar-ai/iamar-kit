#!/usr/bin/env python3
"""Checks kit/style/lighting: the four presets pass `lighting.py check`, seeded
mistakes fail it (invented bloom field, fog.sky_affect out of range, a sun
below the horizon, warm fog, pure black, wrong id), `apply` writes the environment
into a world, `bake-args` turns a preset and a world's lamps into bake_unlit options (in the
object's own frame), the gallery has every preset's shots and numbers and the night bake pair, and (when
IAMAR_PROJECT names an the iamar browser source (not public) checkout) every preset field is allowed by the
browser's schemas/scene.schema.json. `measure` needs numpy and Pillow; without them
that part reports SKIPPED.

    python3 kit/tests/style/lighting_test.py
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[2]
LIGHT = KIT / "style" / "lighting"
TOOL = LIGHT / "lighting.py"
PRESETS = ["dusk", "golden_hour", "night", "overcast"]
VIEWS = ["street", "houses", "above"]


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f": {detail}"))

    r = run("check")
    check("all presets pass check", r.returncode == 0, r.stdout + r.stderr)
    for p in PRESETS:
        check(f"preset {p} present", (LIGHT / "presets" / f"{p}.json").exists())

    base = json.loads((LIGHT / "presets" / "golden_hour.json").read_text(encoding="utf-8"))
    seeds = {
        "bloom": (lambda e: e.update(glow={"enabled": True}), "not a scene environment field"),
        "sky_affect_range": (lambda e: e["fog"].update(sky_affect=1.5), "sky_affect"),
        "below_horizon": (lambda e: e.update(time_of_day=18.5), "below"),
        "warm_fog": (lambda e: e["fog"].update(color="#eccfa8"), "B15"),
        "pure_black": (lambda e: e["ambient"].update(color="#000000"), "pure black"),
        "bad_colour": (lambda e: e["sun"].update(color="orange"), "#rrggbb"),
        "sun_up": (lambda e: e["sun"].update(direction=[0, 1, 0]), "negative"),
    }
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        for name, (mutate, needle) in seeds.items():
            d = json.loads(json.dumps(base))
            d["id"] = name
            mutate(d["environment"])
            f = t / f"{name}.json"
            f.write_text(json.dumps(d), encoding="utf-8")
            r = run("check", f)
            check(f"seeded {name} fails", r.returncode == 1 and needle in r.stdout, r.stdout)
        d = json.loads(json.dumps(base))
        d["id"] = "sky_affect_ok"
        d["environment"]["fog"]["sky_affect"] = 0.3
        f = t / "sky_affect_ok.json"
        f.write_text(json.dumps(d), encoding="utf-8")
        r = run("check", f)
        check("fog.sky_affect 0..1 passes with an old-browser warning",
              r.returncode == 0 and "sky_affect" in r.stdout, r.stdout)
        d = json.loads(json.dumps(base))
        f = t / "wrong_name.json"
        f.write_text(json.dumps(d), encoding="utf-8")
        r = run("check", f)
        check("id must match file name", r.returncode == 1 and "id must equal" in r.stdout, r.stdout)

        # a moon by direction is fine at 21.5 h
        d = json.loads((LIGHT / "presets" / "night.json").read_text(encoding="utf-8"))
        del d["environment"]["sun"]["direction"]
        d["id"] = "moonless"
        f = t / "moonless.json"
        f.write_text(json.dumps(d), encoding="utf-8")
        r = run("check", f)
        check("night without sun.direction fails (zero sun at 21.5 h)", r.returncode == 1, r.stdout)

        # a moving sun is overhead at noon: the golden-hour sun on a running clock turned the
        # harbour's cobbles orange and its grass yellow (harbour a4 3360, a5 3690)
        d = json.loads(json.dumps(base))
        d["id"] = "golden_moving"
        d["environment"]["day_length_minutes"] = 360
        f = t / "golden_moving.json"
        f.write_text(json.dumps(d), encoding="utf-8")
        r = run("check", f)
        check("golden-hour sun on a moving clock fails (warm at noon)",
              r.returncode == 1 and "the sun moves" in r.stdout and "3690" in r.stdout, r.stdout)
        d["environment"]["sun"]["direction"] = [0.9, -0.35, 0.2]
        d["id"] = "golden_fixed"
        f = t / "golden_fixed.json"
        f.write_text(json.dumps(d), encoding="utf-8")
        r = run("check", f)
        check("the same sun fixed by sun.direction passes", r.returncode == 0, r.stdout)
        day = json.loads((LIGHT / "presets" / "day.json").read_text(encoding="utf-8"))
        check("preset day moves the sun and keeps it near white",
              day["environment"]["day_length_minutes"] > 0 and "direction" not in day["environment"]["sun"], json.dumps(day))
        hw = t / "harbour_world"
        hw.mkdir()
        (hw / "scene.json").write_text(json.dumps({"environment": dict(base["environment"], day_length_minutes=360)}),
                                       encoding="utf-8")
        r = run("check", hw)
        check("check <world folder> judges its scene.json environment",
              r.returncode == 1 and "the sun moves" in r.stdout and "scene.json" in r.stdout, r.stdout)
        r = run("apply", "day", hw)
        r = run("check", hw)
        check("apply day fixes that world", r.returncode == 0, r.stdout)

        w = t / "world"
        w.mkdir()
        (w / "scene.json").write_text(json.dumps({
            "format": "iamar-scene", "format_version": 0,
            "environment": {"sky": {"type": "color", "color": "#336699"}},
            "primitives": [{"id": "a", "shape": "box"}]}), encoding="utf-8")
        r = run("apply", "dusk", w)
        s = json.loads((w / "scene.json").read_text(encoding="utf-8"))
        check("apply writes the preset environment", r.returncode == 0
              and s["environment"]["sun"]["color"] == "#ff9458" and s["primitives"][0]["id"] == "a",
              r.stdout + r.stderr)
        (w / "scene.json").write_text(json.dumps({
            "environment": {"sky": {"type": "color", "color": "#336699"}}}), encoding="utf-8")
        r = run("apply", "night", w, "--keep-sky")
        s = json.loads((w / "scene.json").read_text(encoding="utf-8"))
        check("apply --keep-sky keeps the world's sky", s["environment"]["sky"]["type"] == "color"
              and s["environment"]["exposure"] == 1.1, json.dumps(s))

        try:
            import numpy  # noqa: F401
            from PIL import Image
            img = t / "half.png"
            im = Image.new("RGB", (10, 10), (0, 0, 0))
            for x in range(5):
                for y in range(10):
                    im.putpixel((x, y), (255, 255, 255))
            im.save(img)
            r = run("measure", img)
            m = json.loads(r.stdout.split(" ", 1)[1])
            check("measure: half white is luma 0.5, 50% clipped, 50% crushed",
                  abs(m["mean_luma"] - 0.5) < 0.01 and m["clipped_pct"] == 50.0 and m["crushed_pct"] == 50.0,
                  r.stdout)
        except ImportError:
            print("SKIPPED measure (needs numpy and Pillow)")

        # bake-args (an internal task): the preset's moon, sky and the world's lamps for a night bake
        r = run("bake-args", "night")
        a = r.stdout.split()
        check("bake-args night: moon towards -direction, energy x pi, ambient as sky",
              r.returncode == 0 and "--sun=-0.400,0.800,0.450" in a and a[a.index("--sun-strength") + 1] == "1.100"
              and a[a.index("--sky-strength") + 1] == "0.420" and not any(x.startswith("--lamp") for x in a), r.stdout + r.stderr)
        w = t / "lamps"
        w.mkdir()
        (w / "scene.json").write_text(json.dumps({
            "objects": [{"id": "hall", "asset": "assets/hall.glb", "position": [10, 1, 5], "rotation": [0, 90, 0], "scale": 2}],
            "lights": [{"type": "point", "position": [10, 3, 3], "color": "#ffffff", "energy": 2, "range": 6},
                       {"type": "point", "position": [80, 3, 5], "energy": 1, "range": 6},
                       {"type": "spot", "position": [10, 3, 3]}]}), encoding="utf-8")
        r = run("bake-args", "night", "--world", w, "--object", "hall")
        lamps = [x for x in r.stdout.split() if x.startswith("--lamp=")]
        # (0, 2, -2) from the object, yaw 90 undone -> (2, 2, 0), scale 2 -> (1, 1, 0); 2 x 45 W / 2^2
        check("bake-args --world: near point lights only, in the object's frame (yaw, scale), 45 W per energy / scale^2",
              r.returncode == 0 and lamps in (["--lamp=1.000,1.000,-0.000,1.0000,1.0000,1.0000,22.5"],
                                              ["--lamp=1.000,1.000,0.000,1.0000,1.0000,1.0000,22.5"]), r.stdout + r.stderr)
        sun = [x for x in r.stdout.split() if x.startswith("--sun=")]
        # yaw 90 sends the sun (-0.4, 0.8, 0.45) to (-0.45, 0.8, -0.4) in the object's frame (an internal task)
        check("bake-args --world: the sun is rotated into the object's frame like the lamps",
              sun == ["--sun=-0.450,0.800,-0.400"], r.stdout)
        # a mirrored object (negative scale axis) mirrors the lamp but keeps its watts
        sj = json.loads((w / "scene.json").read_text(encoding="utf-8"))
        sj["objects"][0]["scale"] = [-2, 2, 2]
        (w / "scene.json").write_text(json.dumps(sj), encoding="utf-8")
        r = run("bake-args", "night", "--world", w, "--object", "hall")
        lamps = [x for x in r.stdout.split() if x.startswith("--lamp=")]
        check("bake-args --world: mirrored object (scale [-2,2,2]) mirrors x, 22.5 W (no complex power)",
              r.returncode == 0 and len(lamps) == 1 and lamps[0].startswith("--lamp=-1.000,1.000,")
              and lamps[0].endswith(",22.5"), r.stdout + r.stderr)
        sj["objects"][0]["scale"] = [2, 0, 2]
        (w / "scene.json").write_text(json.dumps(sj), encoding="utf-8")
        r = run("bake-args", "night", "--world", w, "--object", "hall")
        check("bake-args --world: zero scale fails cleanly", r.returncode != 0 and "zero scale" in r.stderr
              and "Traceback" not in r.stderr, r.stdout + r.stderr)
        r = run("bake-args", "night", "--world", w, "--object", "nope")
        check("bake-args: unknown object fails", r.returncode != 0 and "no object" in (r.stdout + r.stderr), r.stdout + r.stderr)

        # a long object: a lamp 30 m from its origin but beside its bounds is kept (an internal task)
        w2 = t / "long"
        (w2 / "assets").mkdir(parents=True)
        js = json.dumps({"asset": {"version": "2.0"}, "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
                         "accessors": [{"min": [-40, 0, -2], "max": [40, 3, 2]}]}).encode()
        js += b" " * (-len(js) % 4)
        (w2 / "assets" / "quay.glb").write_bytes(b"glTF" + (2).to_bytes(4, "little") + (20 + len(js)).to_bytes(4, "little")
                                                 + len(js).to_bytes(4, "little") + b"JSON" + js)
        (w2 / "scene.json").write_text(json.dumps({
            "objects": [{"id": "quay", "asset": "assets/quay.glb", "position": [0, 0, 0]}],
            "lights": [{"type": "point", "position": [30, 3, 0], "range": 6},
                       {"type": "point", "position": [90, 3, 0], "range": 6}]}), encoding="utf-8")
        # a stretched object: the sun is divided by the scale like the lamps, not only mirrored (an internal task)
        sj2 = json.loads((w2 / "scene.json").read_text(encoding="utf-8"))
        sj2["objects"][0]["scale"] = [1, 3, 1]
        (w2 / "scene.json").write_text(json.dumps(sj2), encoding="utf-8")
        r = run("bake-args", "night", "--world", w2, "--object", "quay")
        sun = [x for x in r.stdout.split() if x.startswith("--sun=")]
        exp = [-0.4, 0.8 / 3, 0.45]
        n = math.sqrt(sum(c * c for c in exp)) / math.sqrt(0.4 ** 2 + 0.8 ** 2 + 0.45 ** 2)
        check("bake-args --world: stretched object (scale [1,3,1]) lowers the sun in its frame",
              sun == ["--sun=" + ",".join("%.3f" % (c / n) for c in exp)], r.stdout + r.stderr)
        sj2["objects"][0]["scale"] = 1
        (w2 / "scene.json").write_text(json.dumps(sj2), encoding="utf-8")
        r = run("bake-args", "night", "--world", w2, "--object", "quay")
        lamps = [x for x in r.stdout.split() if x.startswith("--lamp=")]
        check("bake-args --world: lamps are selected by distance to the object's bounds, not its origin",
              r.returncode == 0 and len(lamps) == 1 and lamps[0].startswith("--lamp=30.000,"), r.stdout + r.stderr)

        # ao-args (an internal task): neighbours of the long quay within --reach, as occluder matrices in its frame
        sj2["objects"] = [
            {"id": "quay", "asset": "assets/quay.glb", "position": [10, 0, 5], "rotation": [0, 90, 0], "scale": 2},
            {"id": "house", "asset": "assets/quay.glb", "position": [12, 1, 5], "rotation": [0, 90, 0], "scale": 2},
            {"id": "far", "asset": "assets/quay.glb", "position": [10, 0, 200]},
            {"id": "flag", "asset": "assets/quay.glb", "position": [10, 0, 6], "animation": "wave"},
            {"id": "box", "asset": "assets/missing.glb", "position": [10, 0, 5]}]
        (w2 / "scene.json").write_text(json.dumps(sj2), encoding="utf-8")
        r = run("ao-args", "--world", w2, "--object", "quay")
        occ = r.stdout.split()
        # same yaw and scale, 2 m along x and 1 m up in the world: (2, 1, 0) / 2 rotated back by -90
        # degrees about y is (0, 0.5, 1) in the quay's frame, and the 3x3 part is the identity
        nums = [float(v) for v in occ[0].rsplit(",", 12)[1:]] if len(occ) == 1 else []
        want = [1, 0, 0, 0, 0, 1, 0, 0.5, 0, 0, 1, 1]
        check("ao-args: one near static neighbour, as a matrix in the object's frame",
              r.returncode == 0 and len(nums) == 12 and all(abs(a - b) < 1e-4 for a, b in zip(nums, want))
              and occ[0].startswith("--occluder=") and "flag" in r.stderr, r.stdout + r.stderr)
        r = run("ao-args", "--world", w2)
        check("ao-args without --object is a usage error", r.returncode == 2, r.stdout + r.stderr)

    for f in ("night_bake_pair.jpg", "before_front_night.jpg", "after_front_night.jpg", "cameras.json"):
        check(f"gallery night_bake/{f}", (LIGHT / "gallery" / "night_bake" / f).exists())
    nums_p = LIGHT / "gallery" / "numbers.json"
    check("gallery numbers.json exists", nums_p.exists())
    if nums_p.exists():
        nums = json.loads(nums_p.read_text(encoding="utf-8"))
        for p in PRESETS:
            entry = nums["presets"].get(p, {})
            shots = entry.get("shots", {})
            check(f"gallery {p}: three shots with numbers",
                  sorted(shots) == sorted(VIEWS) and all("mean_luma" in v and "primitives" in v
                                                        for v in shots.values()), json.dumps(shots)[:300])
            for v in VIEWS:
                check(f"gallery image {p}_{v}.png", (LIGHT / "gallery" / f"{p}_{v}.png").exists())
            cur = json.loads((LIGHT / "presets" / f"{p}.json").read_text(encoding="utf-8"))["environment"]
            check(f"gallery {p} rendered with the current preset", entry.get("environment") == cur,
                  "preset changed since the gallery was rendered: run lighting.py render again")

    proj = os.environ.get("IAMAR_PROJECT", "")
    schema_p = Path(proj) / "schemas" / "scene.schema.json" if proj else None
    if schema_p and schema_p.exists():
        sch = json.loads(schema_p.read_text(encoding="utf-8"))
        def deref(node):
            while isinstance(node, dict) and "$ref" in node:
                node = sch["$defs"][node["$ref"].rsplit("/", 1)[1]]
            return node
        env_s = deref(sch["properties"]["environment"])
        allowed = set(env_s["properties"])
        for p in PRESETS:
            env = json.loads((LIGHT / "presets" / f"{p}.json").read_text(encoding="utf-8"))["environment"]
            bad = [k for k in env if k not in allowed]
            for k, v in env.items():
                sub = deref(env_s["properties"].get(k, {}))
                if isinstance(v, dict) and "properties" in sub:
                    bad += [f"{k}.{kk}" for kk in v if kk not in sub["properties"]]
            check(f"{p}: every field allowed by the browser schema", not bad, ", ".join(bad))
    else:
        print("SKIPPED browser schema cross-check (set IAMAR_PROJECT to an the iamar browser source (not public) checkout)")

    print(f"{sum(checks)}/{len(checks)} passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
