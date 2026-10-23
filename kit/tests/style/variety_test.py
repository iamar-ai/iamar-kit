#!/usr/bin/env python3
"""Checks kit/style/variety: a sample district passes, seeded repeats fail one rule at a time,
jitter is repeatable and fixes a failing district, scatter keeps spacing and never repeats in a row.

    python3 kit/tests/style/variety_test.py
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
TOOL = KIT / "style" / "variety" / "variety.py"
sys.path.insert(0, str(TOOL.parent))
import variety  # noqa: E402

fails = []


def expect(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails.append(name)


def obj(i, asset, x, z, yaw=0, scale=1.0, tint=None):
    o = {"id": "o%d" % i, "asset": asset, "position": [x, 0, z], "rotation": [0, yaw, 0], "scale": scale}
    if tint:
        o["x-tint"] = tint
    return o


T = dict(variety.DEFAULTS)


def rules(scene):
    return [r for r, _, _ in variety.check(scene, T)]

district = {"objects": [obj(1, "a.glb", 0, 0), obj(2, "b.glb", 10, 0), obj(3, "a.glb", 20, 0, yaw=90),
                        obj(4, "c.glb", 30, 0), obj(5, "b.glb", 40, 0, scale=1.2), obj(6, "c.glb", 50, 0, yaw=45), obj(8, "d.glb", 60, 0)]}
expect("sample district passes", variety.check(district, T) == [])

bad = copy.deepcopy(district)
bad["objects"].append(obj(7, "a.glb", 5, 5))  # near o1, same yaw/scale/tint
expect("same asset, same look, 7 m away fails neighbours", rules(bad) == ["neighbours"])
bad["objects"][-1]["rotation"] = [0, 180, 0]
expect("a yaw change fixes it", rules(bad) == [])
bad["objects"][-1]["rotation"] = [0, 0, 0]
bad["objects"][-1]["x-tint"] = "#a08060"
bad["objects"][0]["x-tint"] = "#a08060"
expect("same tint on both still fails", any(r == "neighbours" for r, _, _ in variety.check(bad, T)))
bad["objects"][0]["x-tint"] = "#6080a0"
expect("different tint fixes it", rules(bad) == [])

run = {"objects": [obj(i, "a.glb", i * 8, 0, yaw=i * 40) for i in range(3)] + [obj(9, "b.glb", 90, 0), obj(10, "c.glb", 95, 0), obj(11, "d.glb", 99, 0)]}
expect("three houses in a row 8 m apart fail sequence", "sequence" in rules(run))
bent = {"objects": [obj(1, "a.glb", 0, 0), obj(2, "a.glb", 8, 0, yaw=40), obj(3, "a.glb", 8, 8, yaw=80)]}
expect("an L of three is not a row", "sequence" not in rules(bent))
row4 = {"objects": [obj(i, "a.glb", i * 15, 0, yaw=i * 40) for i in range(4)]}
seq4 = [m for r, _, m in variety.check(row4, T) if r == "sequence"]
expect("a street row of 4 houses 15 m apart is one sequence run of 4", len(seq4) == 1 and seq4[0].startswith("4 "))
far = {"objects": [obj(i, "a.glb", i * 30, 0, yaw=i * 40) for i in range(3)]}
expect("three placements 30 m apart are not a row", "sequence" not in rules(far))

# G16: list order is irrelevant; a spatial run fails however scene.json is ordered, an interleaved ground row passes
objs3 = [obj(i, "a.glb", i * 8, 0, yaw=i * 40) for i in range(3)] + [obj(9, "b.glb", 90, 0), obj(10, "c.glb", 95, 0)]
shuf = {"objects": [objs3[0], objs3[3], objs3[1], objs3[4], objs3[2]]}
expect("sequence ignores scene.json order (spatial run still fails)", "sequence" in rules(shuf))
inter = {"objects": [obj(1, "a.glb", 0, 0), obj(2, "b.glb", 6, 0), obj(3, "a.glb", 12, 0, yaw=40), obj(4, "b.glb", 18, 0, yaw=80), obj(5, "a.glb", 24, 0, yaw=120)]}
inter_rev = {"objects": list(reversed(inter["objects"]))}
expect("sequence is order-independent", rules(inter) == rules(inter_rev) == [])

# 3358: a run is spatial; placements far apart in z are not neighbours just because their x is close
ok = sum(not any(r == "sequence" for r, _, _ in variety.check({"objects": variety.scatter(["oak", "elm", "pine"], (0, 0, 100, 100), 60, seed=str(s))}, T))
         for s in range(20))
expect("scatter of 3 kinds x 60 over 100x100 m passes sequence on >= 19/20 seeds (%d/20)" % ok, ok >= 19)
ok2 = sum(not any(r == "sequence" for r, _, _ in variety.check({"objects": variety.scatter(["oak", "elm"], (0, 0, 100, 100), 30, seed=str(s))}, T))
          for s in range(20))
expect("scatter of 2 kinds x 30 passes sequence on >= 19/20 seeds (%d/20)" % ok2, ok2 >= 19)

share = {"objects": [obj(i, "a.glb" if i % 3 else "b.glb", i * 100, 0, yaw=i * 40) for i in range(1, 8)]}
expect("one asset over 40 % fails share", any(r == "share" for r, _, _ in variety.check(share, T)))

props = {"objects": [obj(1, "prop_barrel.glb", 0, 0), obj(2, "prop_barrel.glb", 0.5, 0, yaw=90)]}
expect("props closer than 1 m fail", any(r == "props" for r, _, _ in variety.check(props, T)))

a, b = copy.deepcopy(bad), copy.deepcopy(bad)
variety.jitter(a, "7")
variety.jitter(b, "7")
expect("jitter is repeatable", a == b)
expect("jitter uses the seed", variety.jitter(copy.deepcopy(bad), "8") != a)
lumpy = {"objects": [obj(i, "a.glb" if i % 2 else "b.glb", i * 3, 0) for i in range(1, 6)]}
expect("identical copies fail", any(r == "neighbours" for r, _, _ in variety.check(lumpy, T)))
expect("jitter fixes the neighbours rule", all(r != "neighbours" for r, _, _ in variety.check(variety.jitter(lumpy, "3"), T)))

pts = variety.scatter(["t1.glb", "t2.glb"], (0, 0, 40, 40), 30, min_dist=3, seed="5", avoid=[(20, 20, 6)])
expect("scatter places objects", len(pts) >= 20)
expect("scatter keeps min distance", all(variety.math.dist(p["position"], q["position"]) >= 2.99 for i, p in enumerate(pts) for q in pts[i + 1:]))
expect("scatter keeps out of avoid circle", all(variety.math.hypot(p["position"][0] - 20, p["position"][2] - 20) >= 6 for p in pts))
expect("scatter never repeats an asset in a row", all(p["asset"] != q["asset"] for p, q in zip(pts, pts[1:])))
expect("scatter is repeatable", pts == variety.scatter(["t1.glb", "t2.glb"], (0, 0, 40, 40), 30, min_dist=3, seed="5", avoid=[(20, 20, 6)]))

with tempfile.TemporaryDirectory() as d:
    w = Path(d)
    (w / "scene.json").write_text(json.dumps(district))
    r = subprocess.run([sys.executable, str(TOOL), "check", str(w)], capture_output=True, text=True)
    expect("CLI check passes a good district", r.returncode == 0 and "VARIETY_OK" in r.stdout)
    (w / "scene.json").write_text(json.dumps({"objects": district["objects"] + [obj(7, "a.glb", 5, 5)]}))
    r = subprocess.run([sys.executable, str(TOOL), "check", str(w)], capture_output=True, text=True)
    expect("CLI check fails a repeat (exit 1)", r.returncode == 1 and "VARIETY_FAIL" in r.stdout)
    subprocess.run([sys.executable, str(TOOL), "jitter", str(w / "scene.json"), "--seed", "2", "--write"], check=True, capture_output=True)
    r = subprocess.run([sys.executable, str(TOOL), "check", str(w)], capture_output=True, text=True)
    expect("CLI jitter --write fixes it", r.returncode == 0)
    r = subprocess.run([sys.executable, str(TOOL), "scatter", "x.glb", "y.glb", "--area", "0", "0", "30", "30", "--count", "10", "--out", str(w / "s2.json")], capture_output=True, text=True)
    expect("CLI scatter writes a scene", r.returncode == 0 and len(json.loads((w / "s2.json").read_text())["objects"]) > 0)

print("VARIETY_TESTS_OK" if not fails else "VARIETY_TESTS_FAILED %s" % fails)
sys.exit(1 if fails else 0)
