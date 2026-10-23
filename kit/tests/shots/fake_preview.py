#!/usr/bin/env python3
"""Stand-in for `iamar-world preview` in kit/tests/shots: writes one PNG per --view and prints
the VIEW lines world_view.gd prints. It records what it was given (the patched scene's
environment and the views) in $FAKE_PREVIEW_LOG, one JSON line per call.

FAKE_PREVIEW_PRIMS sets the triangles it reports (default 4000); FAKE_PREVIEW_FAIL=1 exits 1
after the first view; FAKE_PREVIEW_DROP=<i> renders every view except index i; FAKE_PREVIEW_VARY=1 draws two tones
per picture (lowtier_test: a flat picture counts as blank). FAKE_PREVIEW_WHITE=1 draws near-white pictures (the washed-out check). FAKE_PREVIEW_EXIT=<n> exits n after
writing every view (a crash on exit); FAKE_PREVIEW_CRASH_ONCE=<file> crashes (exit 139, no view)
on the first call, when <file> does not exist yet, and creates it.
"""
import json
import os
from pathlib import Path
import struct
import sys
import zlib


def png(path, w, h, rgb):
    row = bytes(rgb) * w
    if os.environ.get("FAKE_PREVIEW_VARY") == "1":   # right half darker: not a flat picture
        row = bytes(rgb) * (w // 2) + bytes(max(0, c - 60) for c in rgb) * (w - w // 2)
    raw = b"".join(b"\x00" + row for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def main():
    a = sys.argv[1:]
    assert a[0] == "preview", a
    world, prefix = Path(a[1]), a[2]
    views, opts, i = [], {}, 3
    while i < len(a):
        if a[i] == "--view":
            views.append(a[i + 1])
        else:
            opts[a[i]] = a[i + 1]
        i += 2
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    scene = json.loads((world / manifest.get("scene", "scene.json")).read_text(encoding="utf-8"))
    log = os.environ.get("FAKE_PREVIEW_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"environment": scene.get("environment", {}), "views": views, "opts": opts, "retry": os.environ.get("IAMAR_PREVIEW_RETRY")}) + "\n")
    once = os.environ.get("FAKE_PREVIEW_CRASH_ONCE")
    if once and not os.path.exists(once):
        Path(once).write_text("crashed\n", encoding="utf-8")
        print("Segmentation fault", file=sys.stderr)
        return 139
    w, h = (int(x) for x in opts.get("--size", "320x180").split("x"))
    w, h = min(w, 160), min(h, 90)
    tod = float(scene.get("environment", {}).get("time_of_day", 12.0))
    shade = max(20, min(235, int(255 - abs(tod - 13.0) * 20)))
    Path(prefix).parent.mkdir(parents=True, exist_ok=True)
    prims = int(os.environ.get("FAKE_PREVIEW_PRIMS", "4000"))
    drop = os.environ.get("FAKE_PREVIEW_DROP")
    for n, _v in enumerate(views):
        if drop is not None and n == int(drop):
            continue
        out = "%s_%d_custom%d.png" % (prefix, n, n)
        png(out, w, h, (250, 250, 245) if os.environ.get("FAKE_PREVIEW_WHITE") == "1" else (shade, max(0, shade - 40), max(0, shade - 90)))
        print("VIEW %d custom%d draw=%d prims=%d objects=%d fps=%.1f -> %s" % (n, n, 20 + n, prims + n, 12 + n, 0.0, out))
        if os.environ.get("FAKE_PREVIEW_FAIL") == "1":
            print("ERROR: fake renderer failed", file=sys.stderr)
            return 1
    return int(os.environ.get("FAKE_PREVIEW_EXIT", "0"))


if __name__ == "__main__":
    sys.exit(main())
