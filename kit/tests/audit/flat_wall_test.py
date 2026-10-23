#!/usr/bin/env python3
"""Tests for kit/audit/flat_wall.py (an internal task, harbour a4 review gap R1): a long eye-height wall
with no opening, arch or relief fails in a Track A profile; piers, a party wall, water and a Track B
profile do not. Last case: the harbour a4 world (fish hall and net shed fail, lighthouse passes).
Needs numpy. Exit 1 on any failure."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT / "audit"))
from audit_fixture import box, part, scene, write_glb  # noqa: E402
import flat_wall  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%s %s%s" % ("PASS" if ok else "FAIL", name, (": " + detail) if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def errors(rep, obj=None):
    return [i for i in rep["items"] if i["level"] == "ERROR" and (obj is None or (":%s " % obj) in i["where"])]


def hall(path, piers=False, length=10.0):
    """A closed stone block, length along x, 5 m deep, 4 m high; piers=True adds 0.3 m deep piers
    every 2.5 m on both long sides."""
    boxes = [box((0, 0, 0), (length, 4, 5))]
    if piers:
        for k in range(int(length // 2.5) + 1):
            x = min(k * 2.5, length - 0.4)
            boxes += [box((x, 0, -0.3), (x + 0.4, 3.0, 0)), box((x, 0, 5), (x + 0.4, 3.0, 5.3))]
    write_glb(path, [part("walls", boxes)])


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        hall(d / "plain.glb")
        hall(d / "piers.glb", piers=True)
        hall(d / "short.glb", length=5.0)

        rep = flat_wall.run([str(d / "plain.glb")], style="iamar")
        sides = sorted(i["where"].split()[-2] for i in errors(rep))
        check("plain 10 m block: both long sides fail at the iamar limit", sides == ["+z", "-z"], str(sides))
        check("the error gives the run length", all(abs(i["run_m"] - 10.0) < 0.3 for i in errors(rep)),
              str([i["run_m"] for i in errors(rep)]))
        check("piers every 2.5 m pass", not errors(flat_wall.run([str(d / "piers.glb")], style="iamar")))
        check("a 5 m block passes", not errors(flat_wall.run([str(d / "short.glb")], style="iamar")))
        check("--max-m 12 lets the plain block pass", not errors(flat_wall.run([str(d / "plain.glb")], max_m=12)))

        track_b = d / "track_b.json"
        track_b.write_text(json.dumps({"schema": "iamar-style/1", "id": "desert", "lint": {}}))
        rep = flat_wall.run([str(d / "plain.glb")], style=str(track_b))
        check("a profile without flat_wall_max_m skips the audit",
              rep["ok"] and any("skipped" in i["message"] for i in rep["items"]))

        # world: two plain blocks 1 m apart along z: the facing sides are party walls, not seen
        w = d / "world"
        (w / "assets").mkdir(parents=True)
        hall(w / "assets" / "plain.glb")
        objs = [{"id": "a", "asset": "assets/plain.glb", "position": [0, 0, 0], "x-class": "building"},
                {"id": "b", "asset": "assets/plain.glb", "position": [0, 0, 6], "x-class": "building"}]
        sc = scene(objs)
        (w / "scene.json").write_text(json.dumps(sc))
        rep = flat_wall.run([str(w)], style="iamar")
        got = sorted(i["where"].split(":")[1] for i in errors(rep))
        check("world: party walls 1 m apart are hidden, outer sides fail", got == ["a -z face", "b +z face"], str(got))

        # rotated 90 degrees: the long sides now face x and are still measured along the wall
        sc["objects"] = [dict(objs[0], rotation=[0, 90, 0])]
        (w / "scene.json").write_text(json.dumps(sc))
        rep = flat_wall.run([str(w)], style="iamar")
        check("world: a rotated block still fails on its two long sides", len(errors(rep)) == 2,
              str([(i["where"], i["run_m"]) for i in errors(rep)]))

        # water in front of one long side: a walker cannot stand there
        sc["objects"] = [objs[0]]
        sc["primitives"][0]["size"] = [60, 0.5, 60]
        sc["primitives"][0]["position"] = [0, -3.25, 0]
        sc["primitives"].append({"id": "pier", "shape": "box", "size": [30, 0.5, 4], "position": [5, -0.25, 7], "color": "#8f8a70"})
        sc["primitives"].append({"id": "bank", "shape": "box", "size": [30, 0.5, 6], "position": [5, -0.25, 2.5], "color": "#8f8a70"})
        sc["water"] = [{"id": "sea", "position": [5, -1.0, -8], "size": [40, 16], "depth": 2}]
        (w / "scene.json").write_text(json.dumps(sc))
        rep = flat_wall.run([str(w)], style="iamar")
        got = sorted(i["where"].split(":")[1] for i in errors(rep))
        check("world: the side over water is not seen", got == ["a +z face"], str(got))

    harbour = KIT / "blindtest" / "harbour" / "world"
    if (harbour / "scene.json").is_file():
        rep = flat_wall.run([str(harbour)])
        bad = {i["where"].split(":")[1].split()[0] for i in errors(rep)}
        check("harbour a4: fish hall and net shed fail", {"fish_hall", "net_shed"} <= bad, str(bad))
        check("harbour a4: lighthouse, quay and portal gate pass", not bad & {"lighthouse", "quay_structure", "portal_gate"}, str(bad))
        p = subprocess.run([sys.executable, str(KIT / "audit" / "flat_wall.py"), str(harbour / "assets" / "fish_hall.glb"),
                            "--quiet"], capture_output=True, text=True)
        check("CLI: fish_hall.glb alone exits 1", p.returncode == 1 and "flat wall" in p.stdout, p.stdout[-300:])

    print("%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
