#!/usr/bin/env python3
"""Fixed eye-height review shots of a world at day, dusk and night, with triangle counts.

    iamar-world shots <world> <out> [--cameras FILE] [--times day,dusk,night] [--tier T]
                      [--size WxH] [--frames N] [--npcs all|models|none] [--quest-done IDS|all]
                      [--strict] [--json]
    iamar-world shots --init <world>      write a starter <world>/shots.json from its spawn points
                                          (plus one edge_* camera per side of the playable area)
    iamar-world shots --edges <world> [--add] [--tier T]   exit 1 when a side of the playable area
                                          has no eye-height camera looking out (--add appends them),
                                          or when what they see is mostly bare ground at tier T (low)
    python3 kit/shots/shots.py ...        (same arguments; iamar-world shots runs this)

The camera set is <world>/shots.json (or --cameras FILE), see kit/shots/README.md:

    {"eye_height": 1.7,
     "cameras": [{"name": "gate", "at": [0, 0, 14], "yaw": 0},
                 {"name": "square", "at": [4, 0, -6], "look": [0, 2, -20]}],
     "times": ["day", "dusk", "night"],
     "time_presets": {"dusk": {"time_of_day": 17.8}},
     "budget": {"triangles": 150000, "draws": 150}}

`at` is where the viewer's feet are; the camera sits `eye_height` above it and looks at
`look` (a point) or along `yaw` / `pitch` (degrees; yaw as spawn points use it). Every
time of day renders a temporary copy of the world whose scene.json `environment` is patched
by the preset (the world folder itself is never changed), through `iamar-world preview
--view`, so the shots are what the browser draws. Output:

    <out>/shots/<camera>_<time>.png        the raw shots (pair two runs with compare-shots)
    <out>/sheets/<camera>_<time>.png       one review sheet per camera and time: the shot plus
                                           triangles, draw calls and objects against budget
    <out>/contact_sheet.png                every camera (rows) at every time (columns)
    <out>/shots.json, <out>/SHOTS.md       the numbers

A preview that crashes after writing every view (exit 134/139 at shutdown) keeps its shots
(a NOTE says so); views a crashed pass did not write are rendered again (--retries, default 1).
Exit 1 when a view is still missing (or, with --strict, when a shot is over budget); 2 on bad input.
Needs Pillow for the sheets (the shots and numbers are written without it).
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$")
VIEW_RE = re.compile(r"^VIEW (\d+) (\S+) draw=(\d+) prims=(\d+) objects=(\d+) fps=([0-9.]+) -> (.+)$")
DEFAULT_TIMES = ["day", "dusk", "night"]
# Environment patches merged into scene.json "environment" (docs/WORLD_FORMAT.md 4.1).
# A null value removes the key; "<key>_scale" multiplies the world's own <key> (default 1).
# sun.direction is removed so time_of_day places the sun: the browser then moves it and
# fades it out below the horizon (scripts/worlds/world_builder.gd); a world that keeps its
# own sun fixed would otherwise look the same at every hour. "procedural_sky" is merged
# into environment.sky only when the world uses the procedural sky (the default); a
# cubemap or flat-colour sky is the world's own choice and stays as it is. "fog_tint"
# blends the world's fog colour toward "color" by "amount" (0 to 1) when the world has fog:
# light day fog left as it is reads as a pale sheet over the ground under a dark night sky.
PRESETS = {
    "day": {"time_of_day": 13.0, "sun": {"direction": None}},
    "dusk": {"time_of_day": 17.6, "sun": {"direction": None, "color": "#ffb27a"},
             "ambient": {"energy_scale": 0.7},
             "procedural_sky": {"top_color": "#3b4f7d", "horizon_color": "#f0a464"}},
    "night": {"time_of_day": 22.5, "sun": {"direction": None},
              "ambient": {"energy_scale": 0.3}, "exposure_scale": 0.9,
              "procedural_sky": {"top_color": "#070b1c", "horizon_color": "#1a2140", "ground_color": "#0b0b12"},
              "fog_tint": {"color": "#1a2140", "amount": 0.85}},
}
FOG_DEFAULT = "#c8d4e0"   # world_builder.gd: the browser's fog colour when the world names none
HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")   # Godot's Color(String) html forms


def hex_rgb(s):
    """'#rgb', '#rgba', '#rrggbb' or '#rrggbbaa' (alpha last, as Godot reads it) -> ([r, g, b], alpha hex or ''); else None."""
    m = HEX_RE.match(str(s))
    if not m:
        return None
    h = m.group(1)
    if len(h) <= 4:
        h = "".join(c * 2 for c in h)
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)], h[6:]
# Washed-out check: the lower 45% of a frame is the ground (eye-height and aerial cameras alike);
# a pixel is near-white when its luminance is at least 225 of 255. A frame is WASHED OUT when
# more than 60% of that ground band is near-white: sand, salt or snow with no readable detail.
WASH_BAND = 0.45
WASH_LUMA = 225
WASH_SHARE = 0.60
DEFAULT_DRAWS = 150   # world_view.gd: "stay under ~150 draw calls"


class Bad(Exception):
    pass


def merge(base, patch):
    """Deep-merge patch into a copy of base (see PRESETS for null and _scale)."""
    out = copy.deepcopy(base) if isinstance(base, dict) else {}
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        elif k.endswith("_scale") and isinstance(v, (int, float)):
            key = k[: -len("_scale")]
            cur = out.get(key, 1.0)
            out[key] = (cur if isinstance(cur, (int, float)) else 1.0) * v
        elif isinstance(v, dict):
            out[k] = merge(out.get(k, {}), v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def tint_fog(env, tint):
    """Blend env.fog.color toward tint.color by tint.amount, only when the world has fog on."""
    fog = env.get("fog")
    if not isinstance(tint, dict) or not isinstance(fog, dict) or not fog.get("enabled", bool(fog)):
        return env
    a = hex_rgb(fog.get("color", FOG_DEFAULT))
    b = hex_rgb(tint.get("color", ""))
    amount = tint.get("amount", 1.0)
    if not (a and b and isinstance(amount, (int, float))):
        # a colour name ('lightgray') is valid for the browser but not blended here: say so
        print("NOTE shots: fog_tint not applied (fog colour %r, tint %r): give colours as #rrggbb"
              % (fog.get("color", FOG_DEFAULT), tint.get("color")), file=sys.stderr)
        return env
    t = min(1.0, max(0.0, float(amount)))
    (ca, alpha), (cb, _) = a, b
    env = dict(env)
    env["fog"] = dict(fog, color="#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb)) + alpha)
    return env


def vec3(v, what):
    if not (isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)):
        raise Bad("%s must be [x, y, z] numbers" % what)
    return [float(x) for x in v]


def load_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Bad("%s not found: %s" % (what, path))
    except json.JSONDecodeError as e:
        raise Bad("%s is not valid JSON: %s" % (what, e))


def world_files(world):
    manifest = load_json(world / "manifest.json", "manifest.json")
    scene_name = manifest.get("scene", "scene.json") if isinstance(manifest, dict) else "scene.json"
    if not isinstance(scene_name, str) or Path(scene_name).is_absolute() or ".." in Path(scene_name).parts:
        raise Bad("manifest scene must be a relative path inside the world")
    return manifest, scene_name, load_json(world / scene_name, scene_name)


def camera_view(cam, eye):
    """-> (name, eye position, look-at point) for world_view.gd --view."""
    if not isinstance(cam, dict):
        raise Bad("each camera must be an object")
    name = cam.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise Bad("camera name %r: letters, digits, _ and -, at most 48" % (name,))
    at = vec3(cam.get("at"), "camera %s at" % name)
    h = cam.get("eye_height", eye)
    if not isinstance(h, (int, float)) or not (0.0 < h <= 50.0):
        raise Bad("camera %s eye_height must be a number in (0, 50]" % name)
    pos = [at[0], at[1] + float(h), at[2]]
    if "look" in cam:
        look = vec3(cam["look"], "camera %s look" % name)
        if math.dist(look, pos) < 0.05:
            raise Bad("camera %s looks at its own position" % name)
    else:
        yaw, pitch = cam.get("yaw", 0.0), cam.get("pitch", -5.0)
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (yaw, pitch)) or abs(pitch) >= 89:
            raise Bad("camera %s needs look [x, y, z] or numeric yaw (and pitch within +-89)" % name)
        y, p = math.radians(yaw), math.radians(pitch)
        # yaw 0 faces -Z, as a Godot node / spawn point with rotation.y = yaw
        d = [-math.sin(y) * math.cos(p), math.sin(p), -math.cos(y) * math.cos(p)]
        look = [pos[i] + d[i] * 10.0 for i in range(3)]
    return name, pos, look


def load_cameras(path):
    cfg = load_json(path, "camera set")
    if not isinstance(cfg, dict) or not isinstance(cfg.get("cameras"), list) or not cfg["cameras"]:
        raise Bad("%s needs a non-empty \"cameras\" list" % path)
    eye = cfg.get("eye_height", 1.7)
    if not isinstance(eye, (int, float)) or not (0.0 < eye <= 50.0):
        raise Bad("eye_height must be a number in (0, 50]")
    views = [camera_view(c, float(eye)) for c in cfg["cameras"]]
    names = [v[0] for v in views]
    if len(set(names)) != len(names):
        raise Bad("camera names must be unique")
    presets = copy.deepcopy(PRESETS)
    extra = cfg.get("time_presets", {})
    if not isinstance(extra, dict) or not all(isinstance(v, dict) for v in extra.values()):
        raise Bad("time_presets must map a time name to an environment patch object")
    for k, v in extra.items():
        presets[k] = merge(presets.get(k, {}), v) if k in presets else v
    return cfg, views, presets


def fmt(v):
    return ",".join("%.3f" % x for x in v)


def runner_command(args):
    """-> argv list, or (Windows wrapper) one command line string with every argument quoted."""
    if args.runner:
        cmd = json.loads(args.runner)
        if not (isinstance(cmd, list) and cmd and all(isinstance(x, str) for x in cmd)):
            raise Bad("--runner must be a JSON list of strings")
        return cmd
    if os.name == "nt":
        return [str(KIT / "iamar-world.cmd")]
    cmd = ["bash", str(KIT / "iamar-world")]
    # preview needs a renderer: on a Linux host with no display, use a private Xvfb one
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        off = shutil.which("offscreen")
        if off:
            cmd = [off] + cmd
    return cmd


def run(cmd, timeout):
    # shots retries only the views a pass did not write; the launcher's own whole-preview
    # retry (kit/iamar-world, gaps G7) would render every view again after a crash on exit
    env = dict(os.environ, IAMAR_PREVIEW_RETRY="0", IAMAR_KIT_NO_NEXT="1")
    if os.name == "nt" and cmd[0].lower().endswith(".cmd"):
        # cmd.exe would read the '>' in a --view as a redirection unless every argument is
        # quoted; /s strips only the outer pair of quotes, the wrapper keeps the rest.
        if any('"' in c for c in cmd):
            raise Bad("paths must not contain double quotes")
        line = 'cmd /d /s /c "%s"' % " ".join('"%s"' % c for c in cmd)
        # Windows' own tools first: from Git Bash, PATH would give the wrapper Unix find
        env["PATH"] = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32") + os.pathsep + env.get("PATH", "")
        return subprocess.run(line, capture_output=True, text=True, timeout=timeout, env=env)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def render_time(args, world, scene_name, scene, views, time_name, patch, raw_dir, tmp):
    """Render every camera at one time of day; -> (results, error text)."""
    copy_dir = Path(tmp) / time_name / world.name
    try:
        shutil.copytree(world, copy_dir, ignore=shutil.ignore_patterns("shots", ".git"))
    except (OSError, shutil.Error) as e:   # full or unwritable temp dir (ENOSPC, EDQUOT, EACCES)
        return [], "cannot copy the world into the temp dir %s: %s (set --tmp or TMPDIR to a folder with room)" % (tmp, e)
    patched = dict(scene)
    patch = dict(patch)
    sky_patch = patch.pop("procedural_sky", None)
    fog_patch = patch.pop("fog_tint", None)
    env = tint_fog(merge(scene.get("environment", {}), patch), fog_patch)
    sky = env.get("sky") if isinstance(env.get("sky"), dict) else {}
    if isinstance(sky_patch, dict) and sky.get("type", "procedural") == "procedural":
        env["sky"] = merge(sky, sky_patch)
    patched["environment"] = env
    (copy_dir / scene_name).write_text(json.dumps(patched, indent=1), encoding="utf-8")
    try:
        base = runner_command(args)
    except Bad as e:
        return [], str(e)
    done, notes, err = {}, [], ""
    for attempt in range(1 + max(0, args.retries)):
        todo = [i for i in range(len(views)) if i not in done]
        if not todo:
            break
        if attempt:
            print("shots: %s, retrying %d view(s) the last pass did not write ..." % (time_name, len(todo)), flush=True)
        p, out, err = preview_pass(args, base, copy_dir, [views[i] for i in todo], Path(tmp) / time_name / ("out%d" % attempt) / "v")
        if p is None:   # a timeout or a renderer that will not start: another pass would too
            break
        for j, m in found_views(out).items():
            if j < len(todo):
                done[todo[j]] = m
        if p.returncode != 0 and len(done) == len(views):
            # every picture is on disk: a renderer that crashes while it shuts down
            # (exit 134/139) has still drawn them, so the shots stand
            notes.append("preview exit %d after every view was written (a crash on exit); the shots are kept" % p.returncode)
            err = ""
        elif p.returncode != 0 or len(done) < len(views):
            tail = "\n".join(l for l in out.splitlines() if l.strip())[-1500:]
            err = "preview exit %d, %d of %d views rendered:\n%s" % (p.returncode, len(done), len(views), tail)
        else:
            err = ""
    results = []
    for i, (name, pos, look) in enumerate(views):
        m = done.get(i)
        if m is None:
            continue
        dst = raw_dir / ("%s_%s.png" % (name, time_name))
        shutil.copyfile(Path(m.group(7).strip()), dst)
        results.append({"camera": name, "time": time_name, "time_of_day": patched["environment"].get("time_of_day"),
                        "triangles": int(m.group(4)), "draws": int(m.group(3)), "objects": int(m.group(5)),
                        "fps": float(m.group(6)), "eye": pos, "look": look, "shot": str(dst)})
        share = washed_share(dst) if time_name != "night" else None
        if share is not None:
            results[-1]["ground_near_white"] = round(share, 3)
            results[-1]["washed_out"] = share > WASH_SHARE
    for n in notes:
        print("NOTE shots %s: %s" % (time_name, n), file=sys.stderr)
    if len(results) < len(views) and not err:
        err = "%d of %d views rendered" % (len(results), len(views))
    return results, err


def preview_pass(args, base, copy_dir, views, prefix):
    """One preview run over views; -> (process or None, output text, error text)."""
    cmd = base + ["preview", str(copy_dir), str(prefix),
                  "--size", args.size, "--frames", str(args.frames), "--npcs", args.npcs]
    if args.tier:
        cmd += ["--tier", args.tier]
    if getattr(args, "quest_done", None):
        cmd += ["--quest-done", args.quest_done]
    for _name, pos, look in views:
        cmd += ["--view", "%s>%s" % (fmt(pos), fmt(look))]
    try:
        p = run(cmd, args.timeout)
    except subprocess.TimeoutExpired:
        return None, "", "preview timed out after %d s" % args.timeout
    except (OSError, Bad) as e:
        return None, "", "could not start the preview: %s" % e
    return p, (p.stdout or "") + "\n" + (p.stderr or ""), ""


def found_views(out):
    """-> {view index: VIEW line match} for the views whose picture is on disk."""
    found = {}
    for line in out.splitlines():
        m = VIEW_RE.match(line.strip())
        if m and Path(m.group(7).strip()).is_file():
            found[int(m.group(1))] = m
    return found


def washed_share(path):
    """-> share (0..1) of near-white pixels in the ground band of a shot, or None without Pillow."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(path).convert("L")
    except OSError:
        return None
    band = img.crop((0, int(img.height * (1 - WASH_BAND)), img.width, img.height))
    hist = band.histogram()
    total = sum(hist)
    return sum(hist[WASH_LUMA:]) / total if total else None


def font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:   # Pillow < 10.1
        return ImageFont.load_default()


def sheet(r, world_name, tier, out_path, width=960):
    from PIL import Image, ImageDraw
    img = Image.open(r["shot"]).convert("RGB")
    img = img.resize((width, max(1, round(img.height * width / img.width))))
    band = 92
    page = Image.new("RGB", (width, img.height + band), (24, 22, 28))
    page.paste(img, (0, 0))
    d = ImageDraw.Draw(page)
    y = img.height + 8
    tod = r.get("time_of_day")
    d.text((12, y), "%s  |  camera %s  |  %s%s  |  tier %s" % (world_name, r["camera"], r["time"],
           " (%.1f h)" % tod if isinstance(tod, (int, float)) else "", tier or "default"), fill=(236, 230, 214), font=font(20))
    for j, (label, key) in enumerate((("triangles", "triangles"), ("draw calls", "draws"))):
        lim = r["budget"].get(key)
        over = lim is not None and r[key] > lim
        txt = "%s %s%s" % (label, "{:,}".format(r[key]), (" / %s %s" % ("{:,}".format(lim), "OVER" if over else "ok")) if lim else "")
        d.text((12 + j * 420, y + 30), txt, fill=(255, 110, 90) if over else (170, 220, 160), font=font(18))
    fps = ("   fps %.1f" % r["fps"]) if r["fps"] > 0 else ""   # a short settle reports 0
    d.text((12, y + 58), "objects %d%s   eye %s" % (r["objects"], fps, fmt(r["eye"])),
           fill=(190, 186, 176), font=font(16))
    if r.get("washed_out"):
        d.text((width - 330, y + 58), "WASHED OUT %d%% near-white ground" % round(r["ground_near_white"] * 100), fill=(255, 110, 90), font=font(16))
    page.save(out_path)
    return page


def contact(results, cams, times, out_path, cell=400):
    from PIL import Image, ImageDraw
    pages = {(r["camera"], r["time"]): r.get("_page") for r in results}
    h = None
    for p in pages.values():
        if p is not None:
            h = round(p.height * cell / p.width)
            break
    if h is None:
        return
    head = 28
    grid = Image.new("RGB", (cell * len(times), head + h * len(cams)), (16, 15, 19))
    d = ImageDraw.Draw(grid)
    for c, t in enumerate(times):
        d.text((c * cell + 8, 4), t, fill=(236, 230, 214), font=font(18))
    for rI, cam in enumerate(cams):
        for c, t in enumerate(times):
            p = pages.get((cam, t))
            if p is not None:
                grid.paste(p.resize((cell, h)), (c * cell, head + rI * h))
            else:
                d.text((c * cell + 8, head + rI * h + 8), "%s %s: not rendered" % (cam, t), fill=(255, 110, 90), font=font(16))
    grid.save(out_path)


def write_report(out, world_name, tier, results, errors, cams, times):
    rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    (out / "shots.json").write_text(json.dumps({"world": world_name, "tier": tier, "cameras": cams, "times": times,
                                                "shots": rows, "errors": errors}, indent=1), encoding="utf-8")
    lines = ["# Shots: %s" % world_name, "", "Tier %s. Triangles and draw calls are what the browser drew in that frame." % (tier or "default"), "",
             "| camera | time | triangles | draws | objects | fps | budget |", "|---|---|---:|---:|---:|---:|---|"]
    for r in rows:
        over = [k for k in ("triangles", "draws") if r["budget"].get(k) is not None and r[k] > r["budget"][k]]
        lines.append("| %s | %s | %s | %d | %d | %.1f | %s |" % (r["camera"], r["time"], "{:,}".format(r["triangles"]),
                     r["draws"], r["objects"], r["fps"], ("OVER " + ", ".join(over)) if over else "ok"))
    washed = [r for r in rows if r.get("washed_out")]
    if washed:
        lines += ["", "**WARN washed out:** over %d%% of the ground band is near-white (luminance >= %d), so the ground has no readable detail. "
                  "Lower exposure, darken the ground albedo, or add contrast (kit/recipes/composition/BRIGHT_WORLDS.md):" % (WASH_SHARE * 100, WASH_LUMA), ""]
        lines += ["- %s %s: %d%% near-white" % (r["camera"], r["time"], round(r["ground_near_white"] * 100)) for r in washed]
    for t, e in errors.items():
        lines += ["", "**%s failed:**" % t, "", "```", e, "```"]
    (out / "SHOTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# World edge check (kit/shots/README.md "World edge"). The playable area is the box around the
# things a visitor walks to: spawn points, objects, NPCs, portals, triggers, lights and small
# primitives (big ground or sea planes are scenery, not destinations). Each side needs one eye-height
# camera near it that looks out, or nobody sees the bare band beyond it until the review.
EDGE_SIDES = (("north", 2, -1.0, 0.0), ("south", 2, 1.0, 180.0), ("west", 0, -1.0, 90.0), ("east", 0, 1.0, 270.0))
EDGE_PLACES = ("spawn_points", "objects", "npcs", "portals", "triggers", "lights", "primitives")
EDGE_CONE = 50.0       # degrees: a camera looks out when its view is within this of the outward normal
EDGE_EYE_MAX = 5.0     # higher cameras are aerials: they never show the eye-height view
EDGE_BIG = 40.0        # primitives larger than this (m) are ground or sea, not places


def playable_bounds(scene):
    """-> (lo, hi, places): the box around the placed things, and the places a visitor can
    stand (each [x, y, z]; lights hang in the air, so they widen the box but are no place)."""
    pts, places = [], []
    for key in EDGE_PLACES:
        items = scene.get(key) if isinstance(scene, dict) else None
        for it in items if isinstance(items, list) else []:
            if not isinstance(it, dict):
                continue
            p = it.get("position")
            if not (isinstance(p, list) and len(p) == 3 and all(isinstance(x, (int, float)) for x in p)):
                continue
            size = it.get("size")
            if key == "primitives" and isinstance(size, list) and any(isinstance(x, (int, float)) and abs(x) > EDGE_BIG
                                                                      for x in size):
                continue
            pts.append([float(x) for x in p])
            if key != "lights":
                places.append(pts[-1])
    if len(places) < 2:
        raise Bad("the scene has fewer than two placed things: no playable area to find edges of")
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    if hi[0] - lo[0] < 1.0 or hi[2] - lo[2] < 1.0:
        raise Bad("the placed things lie on a line: no playable area to find edges of")
    return lo, hi, places


def edge_near(lo, hi, axis):
    """How far inside a side a camera may stand and still show it: 10 m or a quarter of the area."""
    return max(10.0, 0.25 * (hi[axis] - lo[axis]))


def ground_height(world, scene, x, z):
    """Terrain height at (x, z) (docs/WORLD_FORMAT.md 4.2), or None when it is not known."""
    t = scene.get("terrain") if isinstance(scene, dict) else None
    if not isinstance(t, dict):
        return None
    pos = t.get("position", [0, 0, 0])
    py = float(pos[1]) if isinstance(pos, list) and len(pos) == 3 else 0.0
    if t.get("type") == "flat":
        return py
    if t.get("type") != "heightmap" or not isinstance(t.get("heightmap"), str):
        return None
    try:
        from PIL import Image
        img = Image.open(world / t["heightmap"])
        size = t.get("size", [256, 256])
        sx, sz = float(size[0]), float(size[1])
        u = min(max((x - (float(pos[0]) - sx / 2)) / sx, 0.0), 1.0)
        v = min(max((z - (float(pos[2]) - sz / 2)) / sz, 0.0), 1.0)
        if img.mode.startswith("I"):
            top = 65535.0
        else:
            img, top = img.convert("L"), 255.0
        val = img.getpixel((round(u * (img.width - 1)), round(v * (img.height - 1))))
        lo, hi = float(t.get("min_height", 0)), float(t.get("max_height", 1))
        return py + lo + (hi - lo) * min(float(val) / top, 1.0)
    except Exception:   # no Pillow, a missing or odd image: the caller falls back to the place's height
        return None


def edge_cameras(world, scene):
    """One outward eye-height camera per side of the playable area, standing at the place near
    that side that is closest to the side and its middle (where a visitor can actually stand)."""
    lo, hi, places = playable_bounds(scene)
    cams = {}
    for side, axis, sign, yaw in EDGE_SIDES:
        other = 2 - axis
        line, mid = (hi[axis] if sign > 0 else lo[axis]), (lo[other] + hi[other]) / 2
        reach, span = edge_near(lo, hi, axis), max(hi[other] - lo[other], 1.0)
        near = [p for p in places if (line - p[axis]) * sign <= reach]
        p = min(near or places, key=lambda q: abs(q[other] - mid) / span + (line - q[axis]) * sign / reach)
        g = ground_height(world, scene, p[0], p[2])
        y = p[1] if g is None else max(g, p[1])
        cams[side] = {"name": "edge_" + side, "at": [round(p[0], 2), round(y, 2), round(p[2], 2)], "yaw": yaw, "pitch": 0}
    return cams


def edge_coverage(scene, cfg):
    """-> {side: [camera names that look out over it]} for the camera set cfg."""
    lo, hi, _places = playable_bounds(scene)
    eye = float(cfg.get("eye_height", 1.7))
    cover = {}
    for side, axis, sign, _yaw in EDGE_SIDES:
        near = edge_near(lo, hi, axis)
        line = hi[axis] if sign > 0 else lo[axis]
        cover[side] = []
        for c in cfg.get("cameras", []):
            name, pos, look = camera_view(c, eye)
            if float(c.get("eye_height", eye)) > EDGE_EYE_MAX:
                continue
            d = [look[0] - pos[0], look[2] - pos[2]]
            n = math.hypot(*d)
            if n < 1e-6:
                continue
            out = (d[0] if axis == 0 else d[1]) * sign / n
            inward = (line - pos[axis]) * sign    # metres inside the side (negative: beyond it)
            if out >= math.cos(math.radians(EDGE_CONE)) and inward <= near:
                cover[side].append(name)
    return cover


def flat_terrain_bands(scene):
    t = scene.get("terrain") if isinstance(scene, dict) else None
    mats = t.get("materials") if isinstance(t, dict) else None
    return [m for m in mats if isinstance(m, dict) and not m.get("texture")] if isinstance(mats, list) else []


# What an edge camera sees (README "World edge": bare view). Rays from the camera over its frame
# (the browser's 75 degree vertical field of view at 16:9) meet the world as kit/audit/meshworld
# loads it; a ray that ends on terrain, or on a big flat ground primitive (more than EDGE_BIG
# across, under 2 m thick), is bare; one that meets water first is open water, not bare; one that
# meets nothing is sky and does not count. Objects and primitives whose min_tier is above the judged tier are not there.
EDGE_FOV = 75.0
EDGE_RAYS = (48, 27)
EDGE_FAR = 400.0
EDGE_BARE_MAX = 0.75   # a side fails when every camera covering it sees more bare ground than this
TIER_ORDER = ("low", "medium", "high", "ultra")


def edge_bare(world, scene, cams, eye, tier):
    """-> {camera name: (bare share of what the camera sees below the sky, [names of the things it sees])}
    at tier; None when numpy is missing."""
    try:
        sys.path.insert(0, str(KIT / "audit"))
        import numpy as np
        import meshworld
    except ImportError:
        return None
    w = meshworld.load_world(world)
    rank = {t: i for i, t in enumerate(TIER_ORDER)}
    top = rank.get(tier, 0)
    gone = set()
    for key, pre in (("objects", ""), ("primitives", "primitive:")):
        for it in scene.get(key) or []:
            if isinstance(it, dict) and rank.get(it.get("min_tier"), 0) > top:
                gone.add(pre + str(it.get("id", it.get("asset", it.get("shape")))))
    ground = np.zeros(len(w.objects), bool)
    keep = np.ones(len(w.objects), bool)
    for i, o in enumerate(w.objects):
        keep[i] = o["id"] not in gone
        if o["id"] == "primitive:terrain":
            ground[i] = True
        elif o["cls"] == "primitive" and o["box"] is not None:
            size = o["box"][1] - o["box"][0]
            ground[i] = max(size[0], size[2]) > EDGE_BIG and size[1] < 2.0
    mask = keep[w.obj] if len(w.obj) else None
    waters = [wt for wt in scene.get("water") or [] if isinstance(wt, dict)]
    out = {}
    for c in cams:
        name, pos, look = camera_view(c, eye)
        pos = np.array(pos, float)
        f = np.array(look, float) - pos
        f /= np.linalg.norm(f)
        r = np.cross(f, [0.0, 1.0, 0.0])
        r = r / np.linalg.norm(r) if np.linalg.norm(r) > 1e-6 else np.array([1.0, 0.0, 0.0])
        u = np.cross(r, f)
        th = math.tan(math.radians(EDGE_FOV / 2))
        nx, ny = EDGE_RAYS
        xs = ((np.arange(nx) + 0.5) / nx * 2 - 1) * th * 16 / 9
        ys = (1 - (np.arange(ny) + 0.5) / ny * 2) * th
        d = (f[None, None] + xs[None, :, None] * r + ys[:, None, None] * u).reshape(-1, 3)
        t, tri, _f = w.raycast(np.repeat(pos[None], len(d), 0), d, EDGE_FAR, mask=mask)
        hit = tri >= 0
        wet = np.zeros(len(d), bool)
        for wt in waters:
            p, sz = wt.get("position", [0, 0, 0]), wt.get("size", [0, 0])
            if not (isinstance(p, list) and len(p) == 3 and isinstance(sz, list) and len(sz) == 2):
                continue
            with np.errstate(divide="ignore", invalid="ignore"):
                tw = (float(p[1]) - pos[1]) / d[:, 1]
            q = pos[None] + d * np.where(np.isfinite(tw), tw, 0)[:, None]
            inside = (np.abs(q[:, 0] - float(p[0])) <= float(sz[0]) / 2) & (np.abs(q[:, 2] - float(p[2])) <= float(sz[1]) / 2)
            wet |= (tw > 0) & (tw <= EDGE_FAR) & inside & (~hit | (tw < t))
        obj = np.where(hit, w.obj[np.maximum(tri, 0)], -1)
        bare = hit & ~wet & ground[np.maximum(obj, 0)]
        solid = (hit | wet).sum()
        seen = sorted({w.objects[i]["id"] for i in set(obj[hit & ~wet & ~bare].tolist())})
        out[name] = (float(bare.sum()) / solid if solid else 0.0, seen)
    return out


def edges(world, add=False, tier="low", cameras=None):
    """--edges: exit 1 when a side of the playable area has no outward eye-height camera, or when
    every camera covering it sees mostly bare ground at tier."""
    _m, _s, scene = world_files(world)
    target = Path(cameras).resolve() if cameras else world / "shots.json"
    if not target.is_file():
        raise Bad("no camera set: %s (run: iamar-world shots --init %s)" % (target, world))
    cfg, _views, _presets = load_cameras(target)
    lo, hi, _places = playable_bounds(scene)
    print("EDGE playable area x %.1f..%.1f, z %.1f..%.1f" % (lo[0], hi[0], lo[2], hi[2]))
    cover = edge_coverage(scene, cfg)
    fresh = edge_cameras(world, scene)
    names = {c.get("name") for c in cfg["cameras"] if isinstance(c, dict)}
    added, missing = [], []
    for side, *_ in EDGE_SIDES:
        if cover[side]:
            print("EDGE %-5s ok      %s" % (side, ", ".join(cover[side])))
        elif add and fresh[side]["name"] not in names:
            cfg["cameras"].append(fresh[side])
            added.append(side)
            print("EDGE %-5s ADDED   %s" % (side, json.dumps(fresh[side])))
        else:
            missing.append(side)
            print("EDGE %-5s MISSING no eye-height camera near this side looks out; add (or --add): %s"
                  % (side, json.dumps(fresh[side])))
    seen = edge_bare(world, scene, [c for c in cfg["cameras"] if isinstance(c, dict)
                                    and any(c.get("name") in cover[sd] for sd, *_ in EDGE_SIDES)],
                     float(cfg.get("eye_height", 1.7)), tier)
    bare = []
    if seen is None:
        print("NOTE edge: numpy is missing, so what the edge cameras see is not judged (pip install numpy)")
    else:
        for side, *_ in EDGE_SIDES:
            if not cover[side]:
                continue
            best = min(cover[side], key=lambda n: seen[n][0])
            share, things = seen[best]
            if share > EDGE_BARE_MAX:
                bare.append(side)
                print("EDGE %-5s BARE    %s sees %d%% open ground at tier %s (limit %d%%): close the view with a wall, "
                      "trees, rocks or a skyline that stand at this tier (no min_tier above %s)%s"
                      % (side, best, round(share * 100), tier, round(EDGE_BARE_MAX * 100), tier,
                         ("; it sees " + ", ".join(things[:6])) if things else ""))
            else:
                print("EDGE %-5s view    %s sees %d%% open ground at tier %s" % (side, best, round(share * 100), tier))
    for m in flat_terrain_bands(scene):
        print("NOTE edge: terrain band %s is a flat colour (no texture): from eye height it reads as a bare gradient"
              % json.dumps(m))
    if added:
        target.write_text(json.dumps(cfg, indent=1) + "\n", encoding="utf-8")
        print("wrote %s: %d edge camera(s) added; move one if it stands inside a model" % (target, len(added)))
    status = (["MISSING " + ",".join(missing)] if missing else []) + (["BARE " + ",".join(bare)] if bare else [])
    print("edges: %s" % ("; ".join(status) if status else "ok"))
    return 1 if missing or bare else 0


def init(world):
    _m, _s, scene = world_files(world)
    target = world / "shots.json"
    if target.exists():
        raise Bad("%s exists; edit it instead" % target)
    cams = []
    for sp in scene.get("spawn_points", []) if isinstance(scene, dict) else []:
        if isinstance(sp, dict) and isinstance(sp.get("position"), list):
            base = str(sp.get("id", "spawn%d" % len(cams)))
            base = re.sub(r"[^A-Za-z0-9_-]", "_", base)[:40] or "spawn"
            yaw = float(sp.get("yaw", 0.0))
            pos = vec3(sp["position"], "spawn point position")
            cams.append({"name": base, "at": pos, "yaw": yaw})
            cams.append({"name": base + "_back", "at": pos, "yaw": yaw + 180.0})
    if not cams:
        cams = [{"name": "origin", "at": [0, 0, 10], "yaw": 0}]
    try:
        cams += list(edge_cameras(world, scene).values())
    except Bad:
        pass   # too few placed things for a playable area yet: run --edges --add later
    target.write_text(json.dumps({"eye_height": 1.7, "cameras": cams, "times": DEFAULT_TIMES}, indent=1) + "\n", encoding="utf-8")
    print("wrote %s with %d camera(s) (edge_* look out over the world edge): add the views a visitor sees (the arrival, the main street, a landmark)" % (target, len(cams)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="iamar-world shots", description=__doc__.split("\n")[0])
    ap.add_argument("world")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--init", action="store_true", help="write a starter <world>/shots.json and stop")
    ap.add_argument("--edges", action="store_true", help="check that each side of the playable area has an outward eye-height camera; exit 1 if not")
    ap.add_argument("--add", action="store_true", help="with --edges: append the missing edge_* cameras to <world>/shots.json")
    ap.add_argument("--cameras", help="camera set file (default <world>/shots.json)")
    ap.add_argument("--times", help="comma-separated time names (default the file's times, else day,dusk,night)")
    ap.add_argument("--tier", help="hardware tier to render (default high; '' for the preview default); "
                    "with --edges the tier whose edge views are judged (default low)")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--frames", type=int, default=30, help="frames to settle each view (default 30)")
    ap.add_argument("--npcs", default="all", choices=["all", "models", "none"])
    ap.add_argument("--quest-done", metavar="IDS",
                    help="draw these quests (comma-separated ids, or 'all') as handed in: their "
                    "on_complete show/hide end state; default every quest not done, as a visitor first sees it")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per preview run (default 900)")
    ap.add_argument("--retries", type=int, default=1, help="re-run the views a crashed pass did not write (default 1)")
    ap.add_argument("--runner", help=argparse.SUPPRESS)   # tests: JSON argv of a stand-in for iamar-world
    ap.add_argument("--tmp", help="folder for the per-render world copies (default TMPDIR, else the system temp dir)")
    ap.add_argument("--strict", action="store_true", help="exit 1 when any shot is over budget")
    ap.add_argument("--json", action="store_true", help="print shots.json instead of the table")
    a = ap.parse_args(argv)
    world = Path(a.world).resolve()
    try:
        if not world.is_dir():
            raise Bad("world folder not found: %s" % a.world)
        if a.init:
            init(world)
            return 0
        if a.edges:
            return edges(world, add=a.add, tier=a.tier or "low", cameras=a.cameras)
        if a.tier is None:
            a.tier = "high"
        if not a.out:
            raise Bad("usage: iamar-world shots <world> <out> (or --init <world>)")
        if not re.match(r"^\d{2,5}x\d{2,5}$", a.size):
            raise Bad("--size must be WIDTHxHEIGHT")
        if a.frames < 1 or a.frames > 2000:
            raise Bad("--frames must be 1..2000")
        manifest, scene_name, scene = world_files(world)
        cam_path = Path(a.cameras).resolve() if a.cameras else world / "shots.json"
        if not cam_path.is_file():
            raise Bad("no camera set: %s (run: iamar-world shots --init %s)" % (cam_path, a.world))
        cfg, views, presets = load_cameras(cam_path)
        times = a.times.split(",") if a.times else cfg.get("times", DEFAULT_TIMES)
        if not isinstance(times, list) or not times or not all(isinstance(t, str) and NAME_RE.match(t) for t in times):
            raise Bad("times must be a non-empty list of names")
        missing = [t for t in times if t not in presets]
        if missing:
            raise Bad("no preset for time(s) %s: add them to time_presets" % ", ".join(missing))
        budget = {"triangles": (manifest.get("budgets", {}) or {}).get("triangles"), "draws": DEFAULT_DRAWS}
        budget.update({k: v for k, v in (cfg.get("budget") or {}).items() if k in ("triangles", "draws")})
    except Bad as e:
        print("ERROR shots: %s" % e, file=sys.stderr)
        return 2
    out = Path(a.out).resolve()
    if out == world or world in out.parents:
        print("ERROR shots: write the output outside the world folder (it would be copied into every render)", file=sys.stderr)
        return 2
    raw, sheets = out / "shots", out / "sheets"
    raw.mkdir(parents=True, exist_ok=True)
    sheets.mkdir(parents=True, exist_ok=True)
    world_name = str(manifest.get("name") or world.name)
    results, errors = [], {}
    try:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="iamar_shots_", dir=a.tmp or None)
    except OSError as e:
        print("ERROR shots: cannot make a temp dir in %s: %s" % (a.tmp or tempfile.gettempdir(), e), file=sys.stderr)
        return 1
    with tmp_ctx as tmp:
        for t in times:
            print("shots: %s, %d camera(s) ..." % (t, len(views)), flush=True)
            res, err = render_time(a, world, scene_name, scene, views, t, presets[t], raw, tmp)
            for r in res:
                r["budget"] = budget
            results += res
            if err:
                errors[t] = err
                print("ERROR shots %s: %s" % (t, err), file=sys.stderr)
    try:
        import PIL  # noqa: F401
        for r in results:
            r["_page"] = sheet(r, world_name, a.tier, sheets / ("%s_%s.png" % (r["camera"], r["time"])))
        contact(results, [v[0] for v in views], times, out / "contact_sheet.png")
    except ImportError:
        print("NOTE shots: Pillow is missing, so no review sheets (pip install Pillow); shots and numbers are written", file=sys.stderr)
    write_report(out, world_name, a.tier, results, errors, [v[0] for v in views], times)
    over = 0
    for r in results:
        bad = [k for k in ("triangles", "draws") if r["budget"].get(k) is not None and r[k] > r["budget"][k]]
        over += bool(bad)
        if not a.json:
            print("SHOT %-20s %-6s triangles=%d draws=%d objects=%d fps=%.1f %s" % (r["camera"], r["time"], r["triangles"],
                  r["draws"], r["objects"], r["fps"], ("OVER " + ",".join(bad)) if bad else "ok"))
    for r in results:
        if r.get("washed_out"):
            print("WARN shots %s %s: washed out, %d%% of the ground band is near-white" % (r["camera"], r["time"], round(r["ground_near_white"] * 100)), file=sys.stderr)
    if a.json:
        print((out / "shots.json").read_text(encoding="utf-8"))
    else:
        print("shots: %d of %d rendered, %d over budget -> %s (sheets/, contact_sheet.png, SHOTS.md)"
              % (len(results), len(views) * len(times), over, out))
    return 1 if errors or (a.strict and over) else 0


if __name__ == "__main__":
    sys.exit(main())
