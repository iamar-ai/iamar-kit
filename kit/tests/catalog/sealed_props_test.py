#!/usr/bin/env python3
"""Checks kit/catalog/assets/seal_props.py (an internal task, harbour a5 G12): the reused catalogue
fishing boat, fish stall, hanging net and pine tree are sealed and match their rows, and a world
that places them the way the harbour blind test did (boats at a quay, stalls and nets on a hall
floor, pines on the ground) gets no closure ERROR from 'iamar-world audit closure'.

    python3 kit/tests/catalog/sealed_props_test.py

Needs numpy for the audit part; without numpy that part reports SKIPPED.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[2]
SEAL = KIT / "catalog" / "assets" / "seal_props.py"
AUDIT = KIT / "audit" / "audit.py"
ASSETS = KIT / "catalog" / "assets"

PLACES = [   # (id, catalogue file, position, yaw)
    ("boat_quay", "harbour/fishing_boat.glb", [-8, 0, 4], 90),
    ("boat_pier", "harbour/fishing_boat.glb", [-8, 0, -6], 0),
    ("fish_stall_0", "harbour/fish_stall.glb", [2, 0, 2], 0),
    ("fish_stall_1", "harbour/fish_stall.glb", [2, 0, -2], 180),
    ("hanging_net", "harbour/hanging_net.glb", [8, 0, 4], 0),
    ("tree_a", "trees/pine_tree.glb", [10, 0, -10], 0),
    ("tree_b", "trees/pine_tree.glb", [-12, 0, -14], 40),
]


def main() -> int:
    fails = []
    p = subprocess.run([sys.executable, str(SEAL), "--check"], capture_output=True, text=True)
    print(p.stdout.strip())
    if p.returncode:
        fails.append("seal_props.py --check failed")
    # the sealed pine's row lives in sources/city_models.json; its checker must still pass
    # (and must not call the harbour files, recorded in sources/harbour.json, orphans)
    imp = subprocess.run([sys.executable, str(SEAL.parent / "import_city_models.py"), "--check"],
                         capture_output=True, text=True)
    print(imp.stdout.strip().splitlines()[-1] if imp.stdout.strip() else imp.stderr.strip())
    if imp.returncode:
        fails.append("import_city_models.py --check failed")
    try:
        import numpy  # noqa: F401
    except ImportError:
        print("SKIPPED audit part (no numpy)")
        return 1 if fails else 0
    # each model on its own, viewed from all round (the boat's open hull shows from above the gunwale)
    for rel in sorted({r for _o, r, _p, _y in PLACES}):
        a = subprocess.run([sys.executable, str(AUDIT), "closure", str(ASSETS / rel), "--class", "prop", "--json"],
                           capture_output=True, text=True)
        try:
            n = sum(1 for i in json.loads(a.stdout)["items"] if i["audit"] == "closure" and i["level"] == "ERROR")
        except ValueError:
            n = -1
        print("%s alone: %s" % (rel, "no closure ERROR" if n == 0 else "%d closure ERRORs" % n))
        if n:
            fails.append("%s alone fails closure" % rel)
    tmp = Path(tempfile.mkdtemp(prefix="sealed_props_"))
    try:
        (tmp / "assets").mkdir()
        objects = []
        for oid, rel, pos, yaw in PLACES:
            name = rel.split("/")[-1]
            if not (tmp / "assets" / name).is_file():
                shutil.copy(ASSETS / rel, tmp / "assets" / name)
            objects.append({"id": oid, "asset": "assets/" + name, "position": pos, "rotation": [0, yaw, 0],
                            "collision": "box", "x-class": "prop"})
        scene = {"format": "iamar-scene", "format_version": 0,
                 "primitives": [{"id": "ground", "shape": "box", "size": [60.0, 0.5, 60.0], "position": [0, -0.25, 0],
                                 "color": "#8f8a70", "collision": "box"}],
                 "spawn_points": [{"id": "default", "position": [0, 0.1, 12], "yaw": 0}], "objects": objects}
        (tmp / "scene.json").write_text(json.dumps(scene), encoding="utf-8")
        (tmp / "manifest.json").write_text(json.dumps({
            "format": "iamar-world", "format_version": 0, "id": "sealed-props", "name": "Sealed props",
            "author": {"name": "iamar kit"}, "version": "1.0.0", "api_version": "0.1", "scene": "scene.json",
            "license": "CC0-1.0", "credits": []}), encoding="utf-8")
        a = subprocess.run([sys.executable, str(AUDIT), "closure", str(tmp), "--json"], capture_output=True, text=True)
        try:
            data = json.loads(a.stdout)
        except ValueError:
            print(a.stdout[-2000:], a.stderr[-2000:])
            return 1
        errs = [i for i in data["items"] if i["audit"] == "closure" and i["level"] == "ERROR"]
        for i in errs:
            print("ERROR", i.get("where"), i.get("message") or i.get("msg"))
        if errs:
            fails.append("%d closure ERRORs on the reused catalogue models" % len(errs))
        else:
            print("closure: no ERROR on %d placed models" % len(PLACES))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for f in fails:
        print("FAIL " + f)
    print("sealed_props_test: %s" % ("OK" if not fails else "FAILED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
