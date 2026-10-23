#!/usr/bin/env python3
"""Shrinks preview PNGs from render_previews.gd to a 256-colour palette with alpha
(libimagequant, dithered): the turntable strips drop to about 45% of their size with no
visible change at preview scale. Already-palette files are skipped, so a rerun is a no-op.

  python3 kit/catalog/compact_previews.py [kit/turntables kit/thumbnails ...]   (default: kit/turntables)
Needs Pillow built with libimagequant (pip install pillow; the PyPI wheels include it).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image, features

KIT = Path(__file__).resolve().parent.parent


def main(argv: list[str]) -> int:
    if not features.check("libimagequant"):
        print("ERROR Pillow lacks libimagequant (pip install --upgrade pillow)")
        return 2
    dirs = [Path(a) for a in argv] or [KIT / "turntables"]
    before = after = n = 0
    for d in dirs:
        for p in sorted(d.glob("*.png")):
            im = Image.open(p)
            if im.mode == "P":
                continue
            q = im.convert("RGBA").quantize(colors=256, method=Image.Quantize.LIBIMAGEQUANT,
                                            dither=Image.Dither.FLOYDSTEINBERG)
            buf = io.BytesIO()
            q.save(buf, "PNG", optimize=True)
            old = p.stat().st_size
            if len(buf.getvalue()) < old:
                p.write_bytes(buf.getvalue())
                before += old
                after += len(buf.getvalue())
                n += 1
    print("COMPACTED %d files, %d -> %d bytes" % (n, before, after))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
