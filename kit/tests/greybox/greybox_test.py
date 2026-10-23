#!/usr/bin/env python3
"""Tests for kit/recipes/greybox/check_greybox.py: the worked example passes, and each rule fails
when its fault is seeded. Run: python3 kit/tests/greybox/greybox_test.py"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "recipes", "greybox"))
import check_greybox as cg  # noqa: E402

EXAMPLE = os.path.join(ROOT, "recipes", "greybox", "examples", "harbour_quarter.greybox.json")


def load():
    with open(EXAMPLE, encoding="utf-8") as f:
        return json.load(f)


def expect(name, mutate, needle, brief_checkpoints=None):
    g = copy.deepcopy(load())
    mutate(g)
    fails = cg.check(g, brief_checkpoints)
    if not any(needle in f for f in fails):
        print(f"NOT OK {name}: expected a FAIL containing {needle!r}, got {fails}")
        return False
    print(f"ok {name}")
    return True


def expect_pass(name, mutate, brief_checkpoints=None):
    g = copy.deepcopy(load())
    mutate(g)
    fails = cg.check(g, brief_checkpoints)
    if fails:
        print(f"NOT OK {name}: expected GREYBOX_OK, got {fails}")
        return False
    print(f"ok {name}")
    return True


def cli(args):
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(ROOT, "recipes", "greybox", "check_greybox.py")] + args,
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    ok = True
    base = cg.check(load())
    if base:
        print("NOT OK example should pass:", base)
        ok = False
    else:
        print("ok example passes")
    ok &= expect("bad stage", lambda g: g.update(stage="finished"), "FAIL stage")
    ok &= expect("painted at greybox", lambda g: (g.update(stage="greybox"), g["objects"][0].update(painted=True)), "G1")
    ok &= expect("door too low", lambda g: g["measurements"].update(door_m=1.2), "G2 scale: door_m")
    ok &= expect("person missing", lambda g: g["measurements"].pop("person_m"), "G2 scale: measurements.person_m missing")
    ok &= expect("no opening", lambda g: g["objects"][0].update(openings=[]), "G3")
    ok &= expect("over budget", lambda g: g["objects"][0].update(triangles=9000), "G6")
    ok &= expect("eye too high", lambda g: g["shots"][1].update(eye_m=40), "G4 eye height")
    ok &= expect("too few eye shots", lambda g: g.update(shots=g["shots"][:2] + [g["shots"][-1]]), "G4 shots")
    ok &= expect("no overview", lambda g: g.update(shots=[s for s in g["shots"] if s["kind"] != "aerial"]), "no aerial or map")
    ok &= expect("scale without approval", lambda g: g.update(approvals=[]), "G5 approval")
    ok &= expect("approval without words", lambda g: g["approvals"][0].update(words="yes"), "own words")
    ok &= expect("paint needs scale approval", lambda g: g.update(stage="paint"), "scale checkpoint")
    # an internal task: approvals follow the brief's checkpoints (interview default: all three; D4 may drop scale)
    def paint_no_scale(g):
        g.update(stage="paint", checkpoints=["greybox", "paint"])
        g["approvals"] = [a for a in g["approvals"] if a["checkpoint"] != "scale"]
    ok &= expect_pass("paint, brief has no scale checkpoint", paint_no_scale)
    ok &= expect_pass("paint, --brief without scale", lambda g: (g.update(stage="paint"),
                      g.update(approvals=[a for a in g["approvals"] if a["checkpoint"] != "scale"])),
                      ["greybox", "paint"])
    ok &= expect("brief names 'scale check'", lambda g: (paint_no_scale(g), g.update(checkpoints=["greybox", "scale check", "paint"])),
                 "scale checkpoint")
    ok &= expect("reworded 'scale walk' still needs scale", lambda g: (paint_no_scale(g),
                 g.update(checkpoints=["greybox", "Scale walk at 1.7 m", "paint"])), "scale checkpoint")
    ok &= expect_pass("'quest walkthrough' is not a greybox stage", lambda g: (paint_no_scale(g),
                      g.update(checkpoints=["greybox", "quest walkthrough", "paint"])))
    ok &= expect("greybox approval always needed", lambda g: (paint_no_scale(g), g.update(checkpoints=["paint"]),
                 g.update(approvals=[])), "greybox checkpoint")
    ok &= expect("no checkpoints: hint", lambda g: (g.update(stage="paint"), g.pop("checkpoints", None)), "copy the brief's")
    ok &= expect("checkpoints not a list", lambda g: g.update(checkpoints="greybox"), "FAIL checkpoints")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        g = load()
        g.update(stage="paint", approvals=[a for a in g["approvals"] if a["checkpoint"] != "scale"])
        gp, bp = os.path.join(d, "greybox.json"), os.path.join(d, "brief.json")
        json.dump(g, open(gp, "w", encoding="utf-8"))
        json.dump({"checkpoints": ["greybox", "paint"]}, open(bp, "w", encoding="utf-8"))
        rc_b, out_b = cli([gp, "--brief", bp])
        rc_n, out_n = cli([gp])
        good = rc_b == 0 and "GREYBOX_OK" in out_b and rc_n == 1 and "scale checkpoint" in out_n
        print(("ok" if good else "NOT OK") + f" cli --brief (rc {rc_b}, without brief rc {rc_n})")
        ok &= good
        # an internal task: --brief may come first; unreadable or non-object JSON is bad input (exit 2, no traceback)
        rc_f, out_f = cli(["--brief", bp, gp])
        good = rc_f == 0 and "GREYBOX_OK" in out_f
        print(("ok" if good else "NOT OK") + f" cli --brief before the file (rc {rc_f})")
        ok &= good
        bad_json, bad_list = os.path.join(d, "bad.json"), os.path.join(d, "list.json")
        open(bad_json, "w", encoding="utf-8").write("{not json")
        json.dump([1], open(bad_list, "w", encoding="utf-8"))
        for name, args in (("brief not JSON", [gp, "--brief", bad_json]), ("brief not an object", [gp, "--brief", bad_list]),
                           ("greybox not JSON", [bad_json]), ("greybox missing", [os.path.join(d, "none.json")]),
                           ("--brief without a file", [gp, "--brief"])):
            rc, out = cli(args)
            good = rc == 2 and "Traceback" not in out
            print(("ok" if good else "NOT OK") + f" cli {name} (rc {rc})")
            ok &= good
    print("ALL OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
