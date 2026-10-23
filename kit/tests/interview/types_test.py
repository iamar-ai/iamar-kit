#!/usr/bin/env python3
"""Dry run of every world-type question set (kit/interview/types): each type has its file, questions,
traps and a worked example brief that validates, and every example answer id exists in its question table."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

INT = Path(__file__).resolve().parents[2] / "interview"
sys.path.insert(0, str(INT / "schema"))
import brief  # noqa: E402

SECTIONS = ["## 1. Questions", "## 2. Traps and checks", "## 3. Reuse", "## 4. What goes into the brief",
            "## 5. Worked example and dry run"]


def main() -> None:
    for t in brief.TYPES:
        md = (INT / "types" / f"{t}.md").read_text(encoding="utf-8")
        for s in SECTIONS:
            assert s in md, (t, "missing section", s)
        ids = re.findall(r"^\| ([A-Z]\d+) \|", md, re.M)
        assert len(ids) >= 6 and len(ids) == len(set(ids)), (t, "question ids", ids)
        ex = INT / "types" / "examples" / t
        b = json.loads((ex / "brief.json").read_text(encoding="utf-8"))
        assert b["type"] == t, (t, b["type"])
        assert brief.check_brief(b, approved=True) == [], (t, brief.check_brief(b, approved=True))
        assert brief.check_md(b, (ex / "world.brief.md").read_text(encoding="utf-8")) == [], t
        for a in b["answers"]:
            assert a["id"] in ids, (t, "answer id not in the question table", a["id"])
    print("OK", len(brief.TYPES), "world types")


if __name__ == "__main__":
    main()
