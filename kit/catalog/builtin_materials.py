#!/usr/bin/env python3
"""Per-material colour and metallic table of the browser's built-in catalogue models.

A reused built-in object (`iamar-world assets use`) has no file in the kit, so lint could only
read its triangle count. This scans the browser's .glb files once and stores, per catalogue sha,
each material's triangle share, metallicFactor and mean colour in builtin_materials.json;
style_lint.lint_reused judges those like a model of the world's own.

  python3 kit/catalog/builtin_materials.py <browser workspace>      # rewrite builtin_materials.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lint"))
import style_lint as sl  # noqa: E402

OUT = HERE / "builtin_materials.json"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    root = Path(argv[0])
    prof, _ = sl.check_style.load("iamar")
    table = {}
    for e in json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))["entries"]:
        src = e.get("source") or {}
        f = root / str(src.get("file") or "")
        if src.get("origin") != "builtin" or e.get("kind") != "model" or f.suffix != ".glb" or not f.is_file():
            continue
        if sl.file_sha256(f) != str(src.get("sha256", "")).lower():
            continue
        mats: list = []
        sl.lint_model(f, prof, sl.Report(), None, str(f), collect=mats)
        if mats:
            table[src["sha256"]] = mats
    OUT.write_text(json.dumps(table, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    metal = sum(1 for m in table.values() if any(x["metallic"] >= 0.8 and not x["baked"] for x in m))
    print("%d models, %d with a metallic material -> %s" % (len(table), metal, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
