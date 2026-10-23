#!/usr/bin/env python3
"""Catalogue creature use lines agree with WORLD_FORMAT 4.12 (an internal task).

`iamar-world assets search fish` offered `scene.json creatures: {"kind": "fish", ...}` while
WORLD_FORMAT.md 4.12 still called fish reserved (harbour blind test attempt 1, gap 5). This
reads the 4.12 kind table and fails when a catalogue entry tells the agent to place a creature
kind the table does not list as rendered, or when AGENT_KIT.md "Lights and creatures" leaves
out a rendered kind.
Run: python3 kit/tests/catalog/creature_kinds_doc_test.py
"""
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent.parent
REPO = KIT.parent


def table_kinds(doc: str) -> tuple[set, set]:
    sec = doc.split("### 4.12 creatures", 1)[1].split("\n### ", 1)[0]
    drawn, reserved = set(), set()
    in_kinds = False   # only the "| kind | ... |" table; the "| field | meaning |" table below it lists depth, school, ...
    for line in sec.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and not cells[0].startswith(("`", "-")):
            in_kinds = cells[0] == "kind"
        if not in_kinds or len(cells) != 2 or not cells[0].startswith("`"):
            continue
        kinds = set(re.findall(r"`(\w+)`", cells[0]))
        (reserved if cells[1].startswith("reserved") else drawn).update(kinds)
    return drawn, reserved


def main() -> int:
    drawn, reserved = table_kinds((REPO / "docs" / "WORLD_FORMAT.md").read_text())
    fails = []
    if not drawn:
        fails.append("WORLD_FORMAT.md 4.12: no rendered kinds found in the table")
    entries = json.loads((KIT / "catalog" / "catalog.json").read_text())["entries"]
    used = {}
    for e in entries:
        for k in re.findall(r'creatures: \{"kind": "(\w+)"', e.get("use", "")):
            used.setdefault(k, []).append(e["id"])
    for k, ids in sorted(used.items()):
        if k not in drawn:
            state = "reserved" if k in reserved else "not listed"
            fails.append(f"{', '.join(ids)}: use line places creature kind {k!r}, {state} in WORLD_FORMAT 4.12")
    kit = (KIT / "AGENT_KIT.md").read_text()
    para = kit.split("**Lights and creatures.**", 1)[1].split("\n\n", 1)[0]
    for k in sorted(drawn):
        if f"`{k}`" not in para:
            fails.append(f"AGENT_KIT.md 'Lights and creatures' does not list rendered kind {k!r}")
    print(f"rendered kinds: {' '.join(sorted(drawn))}")
    print(f"catalogue creature use lines: {sum(len(v) for v in used.values())} ({' '.join(sorted(used))})")
    for f in fails:
        print("FAIL", f)
    print("CREATURE_KINDS_OK" if not fails else f"{len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
