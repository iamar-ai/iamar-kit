#!/usr/bin/env python3
"""Runs every texture painter in kit/tools/painters/ into a temp dir and checks that it writes
non-empty, non-flat PNGs, and that a second run gives identical bytes (all painters are seeded).
Needs numpy, Pillow and scipy; without them it reports SKIPPED and exits 0.

    python3 kit/tests/painters_test.py
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

DIR = Path(__file__).resolve().parents[1] / "tools" / "painters"
# painter -> how it takes its output (file argument, directory argument)
PAINTERS = {"forest_road_paint": "file", "mp_fields_paint": "file", "mp_flora_paint": "file", "mp_herb_paint": "file",
            "forest_tree_paint": "dir", "masterplan_garden_paint": "dir", "mp_waterfall_paint": "dir",
            "road_lantern_paint": "dir", "strand_paint": "dir"}


def run(name: str, kind: str, out: Path) -> list[Path]:
    target = out / "atlas.png" if kind == "file" else out
    r = subprocess.run([sys.executable, str(DIR / (name + ".py")), str(target)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise SystemExit("FAIL %s exited %d: %s" % (name, r.returncode, r.stderr[-400:]))
    return sorted(out.rglob("*.png"))


def main() -> int:
    try:
        import numpy as np
        from PIL import Image
        import scipy  # noqa: F401
    except ImportError as e:
        print("SKIPPED painters (%s)" % e)
        return 0
    for name, kind in PAINTERS.items():
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = run(name, kind, Path(a)), run(name, kind, Path(b))
            if not first:
                raise SystemExit("FAIL %s wrote no PNG" % name)
            for p, q in zip(first, second):
                im = np.asarray(Image.open(p).convert("RGBA"))
                if im.std() < 1.0:
                    raise SystemExit("FAIL %s: %s is flat" % (name, p.name))
                if hashlib.md5(p.read_bytes()).digest() != hashlib.md5(q.read_bytes()).digest():
                    raise SystemExit("FAIL %s: %s differs between two runs" % (name, p.name))
            print("ok %s (%d PNG)" % (name, len(first)))
    print("PAINTERS_OK %d painters" % len(PAINTERS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
