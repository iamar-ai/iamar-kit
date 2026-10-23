#!/usr/bin/env python3
"""Night bake demo (an internal task): the same baked house seen at night, baked by day and baked by night.

A light bake (kit/blender/bake_unlit.py) writes one time of day into unlit textures, so a house
baked in daylight stays day-bright under a black night sky (the harbour blind-test review). This
builds a tiny world twice: a style-gen house with two style-gen lanterns and their point lights,

    before: the house baked with bake_unlit's daylight defaults
    after:  the house baked with `lighting.py bake-args night --world W --object house`
            (moonlight from the night preset, its dim blue sky, and the two lanterns as lamps)

then shoots both at dusk and night in the real preview (`iamar-world shots`) and writes a pair
sheet. The lanterns and the ground are live-lit in both.

    python3 kit/style/lighting/night_bake_demo.py <out dir> [--samples 64] [--no-shots | --shots-only]

--no-shots builds and bakes only; --shots-only shoots worlds an earlier --no-shots run made (on a
shared host: bake outside the render queue, then queue only the shots).

Needs Blender (`iamar-world blender-run`) and, for the shots, the browser with the kit pack
(IAMAR_BROWSER / IAMAR_KIT_PACK as for any `iamar-world` command) and Pillow.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

KIT = Path(__file__).resolve().parents[2]
GEN = KIT / "style" / "gen" / "gen.py"
LIGHTING = KIT / "style" / "lighting" / "lighting.py"
NIGHT = KIT / "style" / "lighting" / "presets" / "night.json"
DUSK = KIT / "style" / "lighting" / "presets" / "dusk.json"
IW = KIT / ("iamar-world.cmd" if os.name == "nt" else "iamar-world")
LANTERNS = [(-3.2, -5.8), (3.2, -5.8)]   # in front of the house (front wall at z = -4, facing -z)
CAMERAS = {"eye_height": 1.7, "times": ["dusk", "night"], "cameras": [
    {"name": "front", "at": [0, 0, -14], "look": [0, 4, 0]},
    {"name": "lantern", "at": [-5.5, 0, -9.5], "look": [-2, 2.2, -4]}]}


def run(cmd, **kw):
    print("+", " ".join(map(str, cmd)), flush=True)
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if p.returncode != 0:
        raise SystemExit("night_bake_demo: failed (%d)\n%s" % (p.returncode, (p.stdout + p.stderr)[-2000:]))
    return p.stdout


def world(folder: Path, house: Path, lantern: Path, light: dict):
    (folder / "assets").mkdir(parents=True, exist_ok=True)
    shutil.copy(house, folder / "assets" / "house.glb")
    shutil.copy(lantern, folder / "assets" / "lantern.glb")
    ly = light["position"][1]
    scene = {
        "format": "iamar-scene", "format_version": 0,
        "environment": json.loads(DUSK.read_text(encoding="utf-8"))["environment"],
        "primitives": [{"id": "ground", "shape": "box", "size": [60, 0.5, 60], "position": [0, -0.25, 0],
                        "color": "#8a8478", "collision": "box"}],
        "spawn_points": [{"id": "default", "position": [0, 0.1, -14], "yaw": 180}],
        "objects": [{"id": "house", "asset": "assets/house.glb", "position": [0, 0, 0], "collision": "mesh",
                     "x-class": "building"}]
        + [{"id": "lantern_%d" % i, "asset": "assets/lantern.glb", "position": [x, 0, z], "collision": "box",
            "x-class": "prop"} for i, (x, z) in enumerate(LANTERNS)],
        "lights": [dict(light, id="lamp_%d" % i, position=[x, ly, z]) for i, (x, z) in enumerate(LANTERNS)],
    }
    (folder / "scene.json").write_text(json.dumps(scene, indent=1) + "\n", encoding="utf-8")
    manifest = {"format": "iamar-world", "format_version": 0, "api_version": "0.4", "id": "night_bake_" + folder.name,
                "name": "Night bake " + folder.name, "version": "0.1.0", "scene": "scene.json", "spawn": "default",
                "author": {"name": "iamar kit"}, "license": "CC0-1.0",
                "description": "Night bake demo: a style-gen house and two style-gen lanterns.",
                "features": ["sky", "fog", "sun", "objects", "primitives", "lights"],
                "budgets": {"triangles": 20000, "objects": 50, "lights": 8, "texture_size": 1024,
                            "texture_bytes": 33554432, "package_bytes": 16777216, "audio_bytes": 1048576,
                            "script_bytes": 1048576}}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")


def pair_sheet(out: Path):
    from PIL import Image, ImageDraw
    tiles = [(t, c, w) for t in ("night", "dusk") for c in ("front", "lantern") for w in ("before", "after")]
    tw, th = 640, 360
    sheet = Image.new("RGB", (tw * 2, (th + 24) * 4), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    for i, (t, c, w) in enumerate(tiles):
        png = out / ("shots_" + w) / "shots" / ("%s_%s.png" % (c, t))
        x, y = (i % 2) * tw, (i // 2) * (th + 24)
        if png.exists():
            sheet.paste(Image.open(png).convert("RGB").resize((tw, th)), (x, y + 24))
        d.text((x + 8, y + 5), "%s: %s, %s" % ({"before": "BEFORE (daylight bake)", "after": "AFTER (night bake)"}[w], c, t),
               fill=(235, 235, 235))
    sheet.save(out / "night_bake_pair.jpg", quality=85)
    return out / "night_bake_pair.jpg"


def main(argv) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    out = Path(argv[0]).resolve()
    samples = argv[argv.index("--samples") + 1] if "--samples" in argv else "64"
    if "--shots-only" not in argv:
        build(out, samples)
    if "--no-shots" in argv:
        print("NIGHT_BAKE_DEMO worlds in %s (no shots)" % out)
        return 0
    for w in ("before", "after"):
        run([IW, "shots", out / w, out / ("shots_" + w), "--cameras", out / "cameras.json", "--size", "1280x720"])
    print("NIGHT_BAKE_DEMO %s" % pair_sheet(out))
    return 0


def build(out: Path, samples: str):
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    run([py, GEN, "house", raw / "house.glb", "--seed", 3, "--footprint", "10x8", "--storeys", 2, "--no-tower", "--lods", 1])
    rep = json.loads(run([py, GEN, "lantern", raw / "lantern.glb", "--json"]))
    world(out / "before", raw / "house.glb", raw / "lantern.glb", rep["light"])   # lamp positions for bake-args
    night = run([py, LIGHTING, "bake-args", "night", "--world", out / "before", "--object", "house"]).split()
    bake = [IW, "blender-run", KIT / "blender" / "bake_unlit.py", "--"]
    run(bake + [raw / "house.glb", raw / "house_day.glb", samples, "--texel", "0.03", "--max-size", "1024"])
    run(bake + [raw / "house.glb", raw / "house_night.glb", samples, "--texel", "0.03", "--max-size", "1024"] + night)
    world(out / "before", raw / "house_day.glb", raw / "lantern.glb", rep["light"])
    world(out / "after", raw / "house_night.glb", raw / "lantern.glb", rep["light"])
    (out / "cameras.json").write_text(json.dumps(CAMERAS, indent=1) + "\n", encoding="utf-8")
    print("NIGHT_BAKE_ARGS " + " ".join(night))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
