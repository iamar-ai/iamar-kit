#!/usr/bin/env python3
"""Check a statue or prop spec against the protocol in kit/examples/STATUE_PROP_PROTOCOL.md.
Prints FAIL lines and exits 1, or STATUE_SPEC_OK and exits 0."""
import json
import sys


def check(spec):
    fails = []
    kind = spec.get("kind")
    if kind not in ("statue", "prop"):
        return ["kind must be statue or prop"]
    statue = kind == "statue"
    lod0 = spec.get("lod0_tris", 0)
    lo, hi = (6000, 10000) if statue else (1, 600)
    if not lo <= lod0 <= hi:
        fails.append(f"lod0_tris {lod0} outside {lo}-{hi}")
    lods = spec.get("lods", [])
    if not lods or lods[0] != lod0 or any(b >= a for a, b in zip(lods, lods[1:])):
        fails.append("lods must start at lod0_tris and strictly descend")
    elif len(lods) > 1 and lods[1] > 0.30 * lod0:
        fails.append(f"LOD1 {lods[1]} above 0.30 of LOD0")
    want_px = 2048 if statue else 1024
    if spec.get("map_px") != want_px:
        fails.append(f"map_px must be {want_px}")
    if not spec.get("generator", {}).get("licence"):
        fails.append("generator.licence missing")
    if statue:
        c = spec.get("concept", {})
        if c.get("original") is not True or not c.get("source"):
            fails.append("concept must be original with a source")
        if not 0.70 <= spec.get("subject_fill", 0) <= 0.90:
            fails.append("subject_fill outside 0.70-0.90")
        if spec.get("high_tris", 0) < 40000:
            fails.append("high_tris below 40000 (nothing to bake from)")
        for k in ("base_stripped", "danglers_removed", "neck_kept", "maps_dilated"):
            if spec.get(k) is not True:
                fails.append(f"{k} must be true")
        if spec.get("face_repainted") is not False:
            fails.append("face_repainted must be false")
        shots = spec.get("shots", [])
        if not any("day" in s for s in shots) or not any("night" in s for s in shots):
            fails.append("shots need day and night")
    return fails


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: check_statue_spec.py spec.json")
    f = check(json.load(open(sys.argv[1])))
    for line in f:
        print("FAIL", line)
    if f:
        sys.exit(1)
    print("STATUE_SPEC_OK")
