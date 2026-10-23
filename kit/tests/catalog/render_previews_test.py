#!/usr/bin/env python3
"""Thumbnails and turntables (job C3b): every catalogue entry names a thumbnail
(kit/thumbnails/<id>.png, 128x128) and a turntable (kit/turntables/<id>.png, an 8-view
768x96 strip) that exist, no preview file is left without an entry, and `catalog.py check`
fails on a seeded miss of either. Renders come from kit/catalog/render_previews.gd."""

from __future__ import annotations

import copy
import struct
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "catalog"))
import catalog  # noqa: E402


def png_size(p: Path) -> tuple[int, int]:
    head = p.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n", "%s is not a PNG" % p
    return struct.unpack(">II", head[16:24])


def main() -> None:
    cat = catalog.load(catalog.CATALOG)
    entries = cat["entries"]
    named = {"thumbnail": set(), "turntable": set()}
    for e in entries:
        fid = e["id"].replace(":", "_").replace("/", "_")
        for field, folder, size in (("thumbnail", "thumbnails", (128, 128)), ("turntable", "turntables", (768, 96))):
            rel = e.get(field)
            assert rel == "%s/%s.png" % (folder, fid), "%s: %s is %r" % (e["id"], field, rel)
            assert (KIT / rel).is_file(), "%s: %s missing" % (e["id"], rel)
            assert png_size(KIT / rel) == size, "%s: %s is %s, not %s" % (e["id"], rel, png_size(KIT / rel), size)
            named[field].add(rel)
    for field, folder in (("thumbnail", "thumbnails"), ("turntable", "turntables")):
        orphans = sorted("%s/%s" % (folder, p.name) for p in (KIT / folder).glob("*.png"))
        orphans = [o for o in orphans if o not in named[field]]
        assert not orphans, "%d %s without a catalogue entry, e.g. %s" % (len(orphans), folder, orphans[:3])
    print("PASS %d entries have a thumbnail and a turntable on disk, no orphans" % len(entries))

    # seeded misses: a missing file and a missing field both fail validation
    for field in ("thumbnail", "turntable"):
        for bad in ("%ss/no_such_entry.png" % field, None):
            seeded = copy.deepcopy(cat)
            seeded["entries"][0][field] = bad
            errs = catalog.validate(seeded)
            assert any(field in x and seeded["entries"][0]["id"] in x for x in errs), (field, bad, errs[:3])
            print("PASS seeded %s %r fails: %s" % (field, bad, [x for x in errs if field in x][0]))
    print("render_previews_test: all checks passed")


if __name__ == "__main__":
    main()
