#!/usr/bin/env python3
"""check_tools.py covers every ship script and fails on a gap (an internal task, PUB8).

The real ship_scripts.json passes with --allow-pending; broken copies of it must fail:
a ship row left out, a kit file that does not exist, an entry without its reason, a pending
entry without --allow-pending, a bundled script kit_bundle.sh does not copy.
"""
import copy, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
CHECK = os.path.join(TOOLS, "check_tools.py")
real = json.load(open(os.path.join(TOOLS, "ship_scripts.json"), encoding="utf-8"))
if not os.path.exists(os.path.join(HERE, "..", "inventory", "scripts.json")):
    print("ship_scripts_test: SKIPPED (no kit/inventory/scripts.json: the public export leaves it out)")
    sys.exit(0)
bad = []


def run(doc, *flags):
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "ship.json")
        json.dump(doc, open(p, "w", encoding="utf-8"))
        r = subprocess.run([sys.executable, CHECK, "--ship", p, *flags], capture_output=True, text=True)
        return r.returncode, r.stdout


def first(status):
    return next(i for i, e in enumerate(real["scripts"]) if e["status"] == status)


def expect_fail(name, doc, needle, *flags):
    rc, out = run(doc, *flags)
    if rc == 0 or needle not in out:
        bad.append("%s: expected a failure naming %r, got rc %d: %s" % (name, needle, rc, out.strip()[-200:]))


rc, out = run(real, "--allow-pending")
if rc != 0:
    bad.append("real ship_scripts.json fails: " + out.strip()[-400:])

d = copy.deepcopy(real); d["scripts"].pop(first("browser"))
expect_fail("row left out", d, "ship row without a kit entry", "--allow-pending")
d = copy.deepcopy(real); d["scripts"].append(dict(d["scripts"][0]))
expect_fail("listed twice", d, "listed twice", "--allow-pending")
d = copy.deepcopy(real); d["scripts"][first("in-kit")]["kit"] = ["kit/gpu/no_such_stage.py"]
expect_fail("missing kit file", d, "no_such_stage.py does not exist", "--allow-pending")
d = copy.deepcopy(real); del d["scripts"][first("internal")]["reason"]
expect_fail("internal without reason", d, "missing reason", "--allow-pending")
d = copy.deepcopy(real); d["scripts"][first("covered")]["status"] = "maybe"
expect_fail("unknown status", d, "unknown status", "--allow-pending")
d = copy.deepcopy(real)
i = next(i for i, e in enumerate(d["scripts"]) if e["path"].endswith("/build_prebuilt.mjs"))
d["scripts"][i] = dict(d["scripts"][first("bundled")], path=d["scripts"][i]["path"])
expect_fail("bundled but not copied", d, "does not copy it", "--allow-pending")
d = copy.deepcopy(real); d["scripts"].append({"repo": "iamar", "path": "tools/kit_test.gd", "status": "internal", "reason": "x"})
expect_fail("not a ship row", d, "not a ship row", "--allow-pending")
d = copy.deepcopy(real)
d["scripts"][first("in-kit")] = {"repo": d["scripts"][first("in-kit")]["repo"], "path": d["scripts"][first("in-kit")]["path"],
                                 "status": "pending", "job": 4163, "reason": "test"}
expect_fail("pending without --allow-pending", d, "pending, an internal task")

print("FAIL: " + "; ".join(bad) if bad else "ship_scripts_test: PASS (%d entries)" % len(real["scripts"]))
sys.exit(1 if bad else 0)
