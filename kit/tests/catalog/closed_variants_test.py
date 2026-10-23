#!/usr/bin/env python3
"""Closed variants of the open-sided city houses (kit/catalog/assets/close_open_sides.py, an internal task)
stand alone: each one placed free-standing in a world with a ground shows nothing open at eye
height on the sides that were open (audit edge; b053's original also fails edge on its -x and -z
sides, deep doorways and a jog the ray test reads as open, and b137's -z is its arcade loggia,
so only the closed sides count), and its cap adds no z-fighting (audit zfight: at most
CAP_ZFIGHT_M2 more coplanar area than the original; b028's original has 1 m2 of its own).
Every closed house (every variant, and b124 and b055, closed on every side) shows no open edge
at all (audit closure 0: seal_trim_edges.py gives the city's single-sheet trim a back, an internal task;
the forge b021 keeps a 0.6 m sliver where its 1.2 m +z stub meets the arcade), and b107's variant
shows at most a third of the open edge its original shows (what is left on an original is its
open side). Job 4161 (PUB6 batch 1) took it from the first six variants to all of them, and
gave each open side its own plane (two sides facing the same way at different depths).

    python3 kit/tests/catalog/closed_variants_test.py     (numpy; about a minute)
"""
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
ASSETS = KIT / "catalog" / "assets"
AUDIT = KIT / "audit" / "audit.py"
CAP_ZFIGHT_M2 = 0.5            # coplanar area a cap may add (a roof end's sliver along a trim)
CLOSURE_LEFT = {"buildings/b021_closed.glb": 0.6}   # metres of open edge a variant may keep


def world(root: Path, glb: str) -> Path:
    w = root / Path(glb).stem
    (w / "assets").mkdir(parents=True)
    shutil.copyfile(ASSETS / glb, w / "assets" / Path(glb).name)
    (w / "scene.json").write_text(json.dumps({
        "format": "iamar-scene", "format_version": 0,
        "primitives": [{"id": "ground", "shape": "box", "size": [80, 0.5, 80], "position": [0, -0.25, 0],
                        "collision": "box"}],
        "spawn_points": [{"id": "default", "position": [0, 0.1, 20], "yaw": 0}],
        "objects": [{"id": "house", "asset": "assets/" + Path(glb).name, "position": [0, 0, 0],
                     "collision": "mesh", "x-class": "building"}]}), encoding="utf-8")
    return w


def audit(name: str, w: Path) -> list:
    r = subprocess.run([sys.executable, str(AUDIT), name, str(w), "--json"], capture_output=True, text=True)
    out = json.loads(r.stdout)
    return out["items"] if isinstance(out, dict) else out


def open_m(items: list) -> float:
    for i in items:
        if i["audit"] == "closure" and "RESULT open_m=" in i["message"]:
            return float(i["message"].split("open_m=")[1])
    raise AssertionError("no closure RESULT line")


def coplanar_m2(items: list) -> float:
    for i in items:
        if i["audit"] == "zfight" and "RESULT coplanar_m2=" in i["message"]:
            return float(i["message"].split("coplanar_m2=")[1].split()[0])
    raise AssertionError("no zfight RESULT line")


def main() -> int:
    closed = json.loads((KIT / "catalog" / "sources" / "city_buildings_closed.json").read_text(encoding="utf-8"))["models"]
    assert len(closed) >= 30, [r["file"] for r in closed]
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        jobs = [(r["file"], n) for r in closed for n in ("edge", "zfight")]
        jobs += [(r["closed_from"]["file"], "zfight") for r in closed]
        whole = [r["file"] for r in closed] + ["buildings/b124.glb", "buildings/b055.glb"]
        jobs += [(f, "closure") for f in whole] + [("buildings/b107.glb", "closure")]
        worlds = {f: world(root, f) for f in {f for f, _ in jobs}}
        with ThreadPoolExecutor(max_workers=6) as ex:
            res = dict(zip(jobs, ex.map(lambda j: audit(j[1], worlds[j[0]]), jobs)))
        sides = {r["file"]: [s["faces"] for s in r["closed_from"]["sides"]] for r in closed}
        parent = {r["file"]: r["closed_from"]["file"] for r in closed}
        for (f, n), items in sorted(res.items()):
            if n == "closure" or f not in sides:
                continue
            if n == "zfight":
                added = coplanar_m2(items) - coplanar_m2(res[(parent[f], "zfight")])
                ok = added <= CAP_ZFIGHT_M2
                print("%s %s zfight: cap adds %.2f m2" % ("PASS" if ok else "FAIL", f, added))
                if not ok:
                    fails.append("%s zfight %.2f m2" % (f, added))
                continue
            errs = [i["message"] for i in items if i["level"] == "ERROR"
                    and any(i["message"].startswith("side %s:" % s) for s in sides[f])]
            print("%s %s %s" % ("FAIL" if errs else "PASS", f, n) + ("".join("\n  " + e for e in errs)))
            fails += errs
        for f in whole:
            m = open_m(res[(f, "closure")])
            ok = m <= CLOSURE_LEFT.get(f, 0.0)
            print("%s %s closure: %.2f m open" % ("PASS" if ok else "FAIL", f, m))
            if not ok:
                fails.append("%s closure" % f)
        before, after = open_m(res[("buildings/b107.glb", "closure")]), open_m(res[("buildings/b107_closed.glb", "closure")])
        ok = after <= before / 3
        print("%s b107 closure: %.2f m open, original %.2f m" % ("PASS" if ok else "FAIL", after, before))
        if not ok:
            fails.append("b107 closure")
    print("closed_variants_test: %s" % ("OK" if not fails else "%d failures" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
