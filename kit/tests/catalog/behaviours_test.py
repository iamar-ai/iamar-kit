#!/usr/bin/env python3
"""C4: every behaviour a catalogue entry declares has a named test.

Reads kit/catalog/catalog.json and behaviours.json, and checks that each declared behaviour
matches a rule whose marker is a check in city_assets_test.gd (which runs headless in a
package world; see its header). Prints the entry -> behaviour -> check table.
Run: python3 kit/tests/catalog/behaviours_test.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent.parent


def main() -> int:
    entries = json.loads((KIT / "catalog" / "catalog.json").read_text())["entries"]
    rules = json.loads((HERE / "behaviours.json").read_text())["rules"]
    gd = (HERE / "city_assets_test.gd").read_text()
    fails = []
    for r in rules:
        if r["marker"] not in gd:
            fails.append("marker not in city_assets_test.gd: %r" % r["marker"])
    n = 0
    for e in entries:
        for b in e.get("behaviours", []):
            n += 1
            hit = next((r for r in rules if re.search(r["pattern"], b)), None)
            if hit is None:
                fails.append("%s (%s): behaviour %r has no test" % (e["id"], e.get("name"), b))
            else:
                print("PASS %-26s %-45s -> %s" % (e["id"] + " " + str(e.get("name")), b[:45], hit["marker"]))
    if n == 0:
        fails.append("no catalogue entry declares a behaviour")
    for f in fails:
        print("FAIL", f)
    print("BEHAVIOURS %d declared, %d failures" % (n, len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
