#!/usr/bin/env python3
"""The brief validator (kit/interview/schema/brief.py): the sample passes, seeded conflicts fail."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

SCHEMA = Path(__file__).resolve().parents[2] / "interview" / "schema"
sys.path.insert(0, str(SCHEMA))
import brief  # noqa: E402

GOOD = json.loads((SCHEMA / "sample_brief.json").read_text(encoding="utf-8"))
MD = (SCHEMA / "sample_world.brief.md").read_text(encoding="utf-8")


def mutated(fn):
    b = copy.deepcopy(GOOD)
    fn(b)
    return brief.check_brief(b, approved=True)


def expect(errs, word):
    assert any(word in e for e in errs), (word, errs)


def main() -> None:
    assert brief.check_brief(GOOD, approved=True) == []
    assert brief.check_md(GOOD, MD) == []

    expect(mutated(lambda b: b.pop("budgets")), "missing field: budgets")
    expect(mutated(lambda b: b.update(track="B")), "own style.json")
    expect(mutated(lambda b: b.update(style_profile="x/style.json")), "track A uses")
    assert mutated(lambda b: b.update(style_file="worlds/harbour/style.json")) == []  # track A extending iamar
    expect(mutated(lambda b: b.update(style_file=3)), "style_file must be")
    expect(mutated(lambda b: b.update(track="B", style_profile="x/style.json", style_file="x/style.json")),
           "track A only")
    expect(mutated(lambda b: b["budgets"].update(triangles=500000)), "over the low tier cap")
    expect(mutated(lambda b: b["budgets"].update(download_mb=0)), "budgets.download_mb")
    expect(mutated(lambda b: b["setup"].update(build_tier=2)), "needs a local GPU")
    expect(mutated(lambda b: b.update(hero_quality="city")), "F3")
    expect(mutated(lambda b: (b["audience"].update(access="public", concurrent=50))), "F1")
    expect(mutated(lambda b: b["answers"][1].pop("shown")), "must be shown")
    expect(mutated(lambda b: b["answers"][0].update(source="guess")), "chosen or default")
    expect(mutated(lambda b: b["answers"].append(dict(b["answers"][0]))), "unique")
    expect(mutated(lambda b: b.update(open_questions=["which quarter?"])), "open_questions")
    expect(mutated(lambda b: b.pop("approval")), "approval needs")
    expect(mutated(lambda b: b.update(checkpoints=[])), "checkpoints")
    expect(mutated(lambda b: b["features"].extend({"id": f"n{i}", "kind": "npc"} for i in range(25))), "F2")
    assert brief.check_brief({k: v for k, v in GOOD.items() if k != "approval"}) == []  # approval is only needed to build

    bad_md = MD.replace("A2", "").replace("150000", "")
    errs = brief.check_md(GOOD, bad_md)
    expect(errs, "default answer A2")
    expect(errs, "budgets.triangles")

    ok = {"budgets": {k: {"measured": GOOD["budgets"][k] - 1} for k in brief.BUDGET_KEYS},
          "features": {f["id"]: {"met": True} for f in GOOD["features"]}}
    assert brief.check_report(GOOD, ok) == []
    over = copy.deepcopy(ok)
    over["budgets"]["triangles"]["measured"] = 200000
    expect(brief.check_report(GOOD, over), "exceeded")
    missing = copy.deepcopy(ok)
    del missing["features"]["quest_first_catch"]
    expect(brief.check_report(GOOD, missing), "quest_first_catch")
    unmet = copy.deepcopy(ok)
    unmet["features"]["npc_fisher"] = {"met": False, "note": "no model"}
    expect(brief.check_report(GOOD, unmet), "not met")
    del ok["budgets"]["texture_size"]
    expect(brief.check_report(GOOD, ok), "no measured value")

    cli = [sys.executable, str(SCHEMA / "brief.py")]
    r = subprocess.run(cli + ["check", str(SCHEMA / "sample_brief.json"), "--approved",
                              "--md", str(SCHEMA / "sample_world.brief.md")], capture_output=True, text=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr
    r = subprocess.run(cli + ["check", str(SCHEMA / "nope.json")], capture_output=True, text=True)
    assert r.returncode == 1 and "ERROR" in r.stdout
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tb = copy.deepcopy(GOOD)
        tb["style_file"] = "style.json"
        bp = Path(td) / "brief.json"
        bp.write_text(json.dumps(tb), encoding="utf-8")
        r = subprocess.run(cli + ["check", str(bp)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout  # style.json not written yet: fine
        (Path(td) / "style.json").write_text(json.dumps({"id": "w", "extends": "iamar"}), encoding="utf-8")
        r = subprocess.run(cli + ["check", str(bp)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout
        (Path(td) / "style.json").write_text(json.dumps({"id": "w"}), encoding="utf-8")
        r = subprocess.run(cli + ["check", str(bp)], capture_output=True, text=True)
        assert r.returncode == 1 and "must extend iamar" in r.stdout, r.stdout
    print("brief_test: OK")


if __name__ == "__main__":
    main()
