#!/usr/bin/env python3
"""Rebuilds the style-lint sample worlds' scene files and the desert sample's models.

    python3 kit/lint/samples/make_samples.py

iamar_city/   three masterplan houses exported by the city (the iamar-models mesh archive (not public)
              buildings/B002, B003, B005 at 56aa77ee), placed on a street, judged by the
              iamar profile. The .glb files are committed as they came from the models repo.
desert_post/  a Track B world with its own style.json (the desert trading post example):
              flat-roofed adobe houses made by kit/tests/lint/glb_fixture.py.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(KIT / "tests" / "lint"))
from glb_fixture import house, write_glb  # noqa: E402


def manifest(wid: str, name: str, desc: str, credits: list) -> dict:
    return {"format": "iamar-world", "format_version": 0, "id": wid, "name": name, "description": desc,
            "author": {"name": "iamar kit"}, "version": "1.0.0", "api_version": "0.1", "scene": "scene.json",
            "budgets": {"triangles": 150000, "objects": 64, "texture_size": 1024, "texture_bytes": 33554432,
                        "lights": 4, "package_bytes": 16777216, "audio_bytes": 0, "script_bytes": 0},
            "features": ["sky", "objects", "primitives"], "license": "CC0-1.0", "credits": credits}


def scene(objects: list, ground: str) -> dict:
    return {"format": "iamar-scene", "format_version": 0,
            "primitives": [{"id": "ground", "shape": "box", "size": [80, 0.5, 80], "position": [0, -0.25, 0],
                            "color": ground, "collision": "box"}],
            "spawn_points": [{"id": "default", "position": [0, 0.1, 14], "yaw": 0}],
            "objects": objects}


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    city = HERE / "iamar_city"
    objs = [{"id": "b002", "asset": "assets/B002.glb", "position": [-14, 0, 0], "collision": "box"},
            {"id": "b003", "asset": "assets/B003.glb", "position": [0, 0, 0], "collision": "box"},
            {"id": "b005", "asset": "assets/B005.glb", "position": [14, 0, 0], "collision": "box"},
            {"id": "b003_far", "asset": "assets/B003.glb", "position": [0, 0, -30], "rotation": [0, 180, 0], "collision": "box"}]
    write(city / "manifest.json", manifest("lint_iamar_city", "Style lint sample: iamar city street",
          "Three of the city's own masterplan houses (vertex-coloured, baked by the city builder) on a cobbled street.",
          [{"files": ["assets/*.glb"], "author": "iamar city masterplan builder", "license": "CC0-1.0",
            "source": "the iamar-models mesh archive (not public) buildings/ at 56aa77ee"}]))
    write(city / "scene.json", scene(objs, "#938e83"))

    desert = HERE / "desert_post"
    shutil.copyfile(KIT / "style" / "schema" / "examples" / "desert_trading_post.style.json", desert / "style.json")
    common = dict(roof_rise=0.3, wall="#d6b48a", roof="#a9835c", door="#6b4a2e", wall_h=3.2)
    write_glb(desert / "assets" / "adobe_house.glb", house(width=7, depth=6, **common))
    write_glb(desert / "assets" / "adobe_house_wide.glb", house(width=10, depth=7, tris=2400, **common))
    write_glb(desert / "assets" / "brass_lamp.glb", [
        {"name": "Post", "min": [-0.08, 0, -0.08], "max": [0.08, 2.4, 0.08], "color": "#a8843e"},
        {"name": "Lamp", "min": [-0.2, 2.4, -0.2], "max": [0.2, 2.8, 0.2], "color": "#ffb25e", "emissive": True}])
    objs = [{"id": "house_a", "asset": "assets/adobe_house.glb", "position": [-6, 0, 0], "collision": "box"},
            {"id": "house_b", "asset": "assets/adobe_house_wide.glb", "position": [6, 0, 0], "collision": "box"},
            {"id": "house_c", "asset": "assets/adobe_house.glb", "position": [-6, 0, -20], "scale": 1.15, "collision": "box"},
            {"id": "lamp", "asset": "assets/brass_lamp.glb", "position": [0, 0, 4]}]
    write(desert / "manifest.json", manifest("lint_desert_post", "Style lint sample: desert trading post",
          "A Track B world with its own style.json: flat-roofed adobe houses and a brass lamp.",
          [{"files": ["assets/*.glb"], "author": "iamar kit test fixture", "license": "CC0-1.0"}]))
    write(desert / "scene.json", scene(objs, "#e0c79a"))
    print("wrote", city, desert)
    return 0


if __name__ == "__main__":
    sys.exit(main())
