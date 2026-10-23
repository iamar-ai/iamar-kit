#!/usr/bin/env python3
"""Rebuilds the audit sample world (every audit passes on it).

    python3 kit/audit/samples/make_samples.py

audit_yard/   two enterable houses (thick walls, a doorway with its door leaf, a lintel, a baked
              unlit roof) and a closed crate on a ground slab, made by
              kit/tests/audit/audit_fixture.py. kit/tests/audit/audit_test.py runs all six audits
              on it, then breaks copies of it on purpose (one fault per audit).
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(KIT / "tests" / "audit"))
from audit_fixture import box, hollow_house, part, scene, write_glb  # noqa: E402


def build(out: Path) -> Path:
    write_glb(out / "assets" / "house.glb", hollow_house())
    write_glb(out / "assets" / "crate.glb", [part("Crate", [box([-0.4, 0, -0.4], [0.4, 0.8, 0.4])], "#9a7a52")])
    objs = [{"id": "house_a", "asset": "assets/house.glb", "position": [-6, 0, 0], "collision": "mesh", "x-class": "building"},
            {"id": "house_b", "asset": "assets/house.glb", "position": [6, 0, -2], "rotation": [0, 90, 0],
             "collision": "mesh", "x-class": "building"},
            {"id": "crate", "asset": "assets/crate.glb", "position": [0, 0, 6], "collision": "box", "x-class": "prop"}]
    (out / "scene.json").write_text(json.dumps(scene(objs), indent=1) + "\n", encoding="utf-8")
    man = {"format": "iamar-world", "format_version": 0, "id": "audit-yard", "name": "Audit yard",
           "description": "Sample world for iamar-world audit: every geometry audit passes on it.",
           "author": {"name": "iamar kit"}, "version": "1.0.0", "api_version": "0.1", "scene": "scene.json",
           "budgets": {"triangles": 150000, "objects": 64, "texture_size": 1024, "texture_bytes": 33554432,
                       "lights": 4, "package_bytes": 16777216, "audio_bytes": 0, "script_bytes": 0},
           "features": ["sky", "objects", "primitives"], "license": "CC0-1.0", "credits": []}
    (out / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    # the 6 m fixture houses are plain on purpose: a profile without lint.flat_wall_max_m skips flat-wall
    (out / "style.json").write_text(json.dumps({"schema": "iamar-style/1", "id": "audit-yard", "lint": {}}, indent=1) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(build(HERE / "audit_yard"))
