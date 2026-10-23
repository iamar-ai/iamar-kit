#!/usr/bin/env python3
"""Checks kit/shots/lowtier (iamar-world lowtier) with the fake renderer of shots_test:

    python3 kit/tests/shots/lowtier_test.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
TOOL = KIT / "shots" / "lowtier" / "lowtier.py"
FAKE = HERE / "fake_preview.py"
DESERT = KIT / "lint" / "samples" / "desert_post"
CAMS = KIT / "shots" / "samples" / "desert_post.shots.json"
sys.path.insert(0, str(KIT / "shots" / "lowtier"))
import lowtier  # noqa: E402


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (("  " + str(detail).strip()[-900:]) if detail and not cond else ""), flush=True)

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("SKIPPED lowtier tests (Pillow missing)")
        return 0
    tmp = Path(tempfile.mkdtemp(prefix="lowtier_test_"))
    runner = json.dumps([sys.executable, str(FAKE)])
    try:
        world = tmp / "world"
        shutil.copytree(DESERT, world)

        def run(out, extra=None, *args):
            env = dict(os.environ, FAKE_PREVIEW_VARY="1", **(extra or {}))
            return subprocess.run([sys.executable, str(TOOL), str(world), str(tmp / out), "--cameras", str(CAMS),
                                   "--runner", runner, *args], capture_output=True, text=True, env=env)

        p = run("ok")
        rep = json.loads((tmp / "ok" / "lowtier.json").read_text(encoding="utf-8")) if (tmp / "ok" / "lowtier.json").is_file() else {}
        check("sample run passes (3 cameras x day,night)", p.returncode == 0 and len(rep.get("shots", [])) == 6, p.stdout + p.stderr)
        check("report and LOWTIER.md written", (tmp / "ok" / "LOWTIER.md").is_file() and rep.get("tier") == "low")
        check("low shots rendered at tier low, high comparison at tier high",
              (tmp / "ok" / "low" / "shots.json").is_file() and json.loads((tmp / "ok" / "high" / "shots.json").read_text(encoding="utf-8")).get("tier") == "high")
        p = subprocess.run([sys.executable, str(TOOL), str(world), str(tmp / "flat"), "--cameras", str(CAMS), "--runner", runner,
                            "--no-high"], capture_output=True, text=True, env=dict(os.environ, FAKE_PREVIEW_VARY="0"))
        check("flat pictures fail as blank", p.returncode == 1 and "FAIL blank" in p.stdout, p.stdout + p.stderr)
        p = run("fail", {"FAKE_PREVIEW_FAIL": "1"})
        check("a failed render fails the check", p.returncode == 1, p.stdout + p.stderr)
        p = run("nohigh", None, "--no-high")
        check("--no-high skips the comparison", p.returncode == 0 and not (tmp / "nohigh" / "high").exists(), p.stdout + p.stderr)
        p = run("npcsnone", None, "--npcs", "none")
        check("--npcs none passes through to both runs", p.returncode == 0 and (tmp / "npcsnone" / "high" / "shots.json").is_file(), p.stdout + p.stderr)
        # the fake renderer ignores --npcs, so check the argv shots receives (dropping the passthrough must fail here)
        seen = []
        real_main = lowtier.shots.main
        lowtier.shots.main = lambda argv: seen.append(list(argv)) or 0
        try:
            a = lowtier.argparse.Namespace(world=str(world), times="day", size="64x36", cameras=None, runner=None,
                                           tmp=None, frames=0, npcs="none")
            lowtier.run_shots(a, "low", tmp / "argv_low")
            lowtier.run_shots(a, "high", tmp / "argv_high")
            a.npcs = "all"
            lowtier.run_shots(a, "low", tmp / "argv_all")
        finally:
            lowtier.shots.main = real_main
        check("--npcs none reaches shots in both tier runs, the default adds nothing",
              len(seen) == 3 and all(s[s.index("--npcs") + 1] == "none" for s in seen[:2] if "--npcs" in s)
              and all("--npcs" in s for s in seen[:2]) and "--npcs" not in seen[2], seen)
        p = run("npcsbad", None, "--npcs", "bogus")
        check("--npcs rejects unknown values (exit 2)", p.returncode == 2, p.stdout + p.stderr)
        p = subprocess.run([sys.executable, str(TOOL), str(tmp / "missing"), str(tmp / "x")], capture_output=True, text=True)
        check("missing world exits 2", p.returncode == 2, p.stdout + p.stderr)

        # judge(): the pixel rules
        shot = {"time": "day", "triangles": 100, "budget": {"triangles": 1000}}
        good = {"mean": 120, "std": 40, "magenta": 0, "dark": 0.1, "bright": 0.1}
        check("judge: a normal shot passes", lowtier.judge(shot, good) == [])
        check("judge: flat picture is blank", "blank" in lowtier.judge(shot, dict(good, std=0.5)))
        check("judge: pink pixels are missing textures", "magenta" in lowtier.judge(shot, dict(good, magenta=0.3)))
        check("judge: black day shot is crushed, black night is not",
              "crushed" in lowtier.judge(shot, dict(good, dark=0.97)) and "crushed" not in lowtier.judge(dict(shot, time="night"), dict(good, dark=0.97)))
        check("judge: white shot is blown", "blown" in lowtier.judge(shot, dict(good, bright=0.95)))
        check("judge: over budget or empty triangles fail",
              "triangles" in lowtier.judge(dict(shot, triangles=5000), good) and "triangles" in lowtier.judge(dict(shot, triangles=0), good))
        check("judge: low tier drawing more than high lacks impostors",
              "impostors" in lowtier.judge(shot, good, {"triangles": 50}) and "impostors" not in lowtier.judge(shot, good, {"triangles": 500}))
        big = dict(shot, triangles=43061, budget={})
        check("judge: moving script entities (+0.4%) are within the impostor slack, +5% is not, slack 0 is strict",
              "impostors" not in lowtier.judge(big, good, {"triangles": 42893})
              and "impostors" in lowtier.judge(big, good, {"triangles": 41000})
              and "impostors" in lowtier.judge(big, good, {"triangles": 42893}, 0.0))
        p = run("badslack", None, "--impostor-slack", "2")
        check("--impostor-slack outside 0..1 exits 2", p.returncode == 2, p.stdout + p.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%d/%d checks passed" % (sum(checks), len(checks)))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
