#!/usr/bin/env python3
"""The statue spec checker passes the worked example and fails one seeded fault per rule."""
import copy
import json
import os
import sys

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "examples")
sys.path.insert(0, root)
import check_statue_spec as c  # noqa: E402

good = json.load(open(os.path.join(root, "harbour_extension", "founder_statue.spec.json")))
assert c.check(good) == [], c.check(good)
faults = {
    "lod0_tris": 12000, "lods": [8000, 4000], "map_px": 1024, "subject_fill": 0.4, "high_tris": 9000,
    "neck_kept": False, "base_stripped": False, "danglers_removed": False, "maps_dilated": False,
    "face_repainted": True, "shots": ["day_front"], "generator": {}, "concept": {"original": False},
}
for k, v in faults.items():
    s = copy.deepcopy(good)
    s[k] = v
    assert c.check(s), f"fault in {k} not caught"
prop = {"kind": "prop", "lod0_tris": 150, "lods": [150, 40], "map_px": 1024, "generator": {"licence": "own"}}
assert c.check(prop) == []
prop["lod0_tris"] = 900
assert c.check(prop)
print("STATUE_SPEC_TEST_OK")
