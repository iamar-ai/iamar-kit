#!/usr/bin/env python3
"""Composition check (kit/recipes/composition): the worked example passes, each seeded fault fails."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2] / "recipes" / "composition"
sys.path.insert(0, str(ROOT))
import check_composition as cc  # noqa: E402

GOOD = json.loads((ROOT / "examples" / "harbour_quarter.composition.json").read_text(encoding="utf-8"))


def seeded(fn):
    c = copy.deepcopy(GOOD)
    fn(c)
    return cc.check(c)


def expect(errs, word):
    assert any(word in e for e in errs), (word, errs)


def main() -> None:
    assert cc.check(GOOD) == [], cc.check(GOOD)
    expect(seeded(lambda c: c["signs"][0].update(letter_m=0.1)), "too small")
    expect(seeded(lambda c: c["signs"][0].update(mount_m=1.2)), "mounted at")
    expect(seeded(lambda c: c["signs"][1].update(mirrored=True)), "mirrored")
    expect(seeded(lambda c: c["signs"][1].update(lit=False)), "not lit")
    expect(seeded(lambda c: c["signs"][2].update(blocks_opening=True)), "covers a door")
    expect(seeded(lambda c: c["vistas"][0]["targets"][0].update(xz=[-120, 60])), "one picture")
    expect(seeded(lambda c: c["vistas"][0]["targets"][1].update(xz=[-18, 80])), "merge")
    expect(seeded(lambda c: c["obstacles"].append({"id": "wall", "rect": [-5, 30, 15, 35]})), "blocked by wall")
    expect(seeded(lambda c: [r.update(rise_m=3.0) for r in c["roofs"]]), "skyline flat")
    expect(seeded(lambda c: c["first_view"].update(heading_deg=180)), "first view")
    r = subprocess.run([sys.executable, str(ROOT / "check_composition.py"), str(ROOT / "examples" / "harbour_quarter.composition.json")], capture_output=True, text=True)
    assert r.returncode == 0 and "COMPOSITION_OK" in r.stdout, r
    print("composition_test OK")


if __name__ == "__main__":
    main()
