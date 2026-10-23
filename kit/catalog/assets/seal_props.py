#!/usr/bin/env python3
"""Seal the open sheets of catalogue props that fail 'iamar-world audit closure' when a world reuses them.

  python3 kit/catalog/assets/seal_props.py            # seal the files below in place, update their source rows
  python3 kit/catalog/assets/seal_props.py --check    # every file below is sealed and matches its row

Harbour blind test attempt 5 (kit/blindtest/harbour/gaps.md G12, an internal task) reused the
fishing boat, the fish stall, the hanging net and the pine tree and got 28 closure ERRORs from
them: the boat hull is one shell with no inner side (looking into the boat from the quay, the
player sees the culled back of the hull: water through the planks), the net and the price slate
are single sheets, and the pine's cones are open skirts (from under a branch tier the player
looks up into culled backs: sky through the tree). Each such sheet gets a back side with
seal_trim_edges.seal(), the step that already seals the city houses: the sheet's triangles are
copied with the winding reversed, so the edge is shared and the sheet reads as a thin plate from
both sides. Materials stay single-sided (no doubleSided cost on the rest of the model).

Run order: export_harbour.gd (or import_city_models.py for the pine), then this, then
harbour.py record (it re-measures the harbour rows) and catalog.py build. The city row of the
pine keeps the iamar-models copy it was sealed from as sealed.source_sha256. Sealing a sealed
file changes nothing, so the step is idempotent and --check fails when a file was re-exported
or re-imported without it. Python 3.8+, standard library only.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from import_city_models import measure  # noqa: E402
from seal_trim_edges import seal  # noqa: E402

SOURCES = HERE.parent / "sources"
# catalogue file -> the source json that records it
SEALED = {
    "harbour/fishing_boat.glb": "harbour.json",
    "harbour/fish_stall.glb": "harbour.json",
    "harbour/hanging_net.glb": "harbour.json",
    "trees/pine_tree.glb": "city_models.json",
}


def _row(src: dict, rel: str) -> dict:
    for r in src["models"]:
        if r["file"] == rel:
            return r
    raise SystemExit("%s: no row in its source" % rel)


def build() -> int:
    by_src = {}
    for rel, name in SEALED.items():
        by_src.setdefault(name, []).append(rel)
    for name, rels in by_src.items():
        path = SOURCES / name
        src = json.loads(path.read_text(encoding="utf-8"))
        for rel in rels:
            p = HERE / rel
            b = p.read_bytes()
            out, info = seal(b)
            row = _row(src, rel)
            if out != b:
                p.write_bytes(out)
                if name == "city_models.json":
                    prev = row.get("sealed", {}).get("source_sha256", row["sha256"])
                    row["sealed"] = {"source_sha256": prev, "back_triangles": info["back_triangles"],
                                     "by": "kit/catalog/assets/seal_props.py"}
            m = measure(out)
            row.update({"sha256": hashlib.sha256(out).hexdigest(), "bytes": len(out), "triangles": m["triangles"]})
            print("%s: %d open edges (%.2f m), %d back triangles, %d triangles"
                  % (rel, info["edges"], info.get("edge_m", 0.0), info["back_triangles"], m["triangles"]))
        path.write_text(json.dumps(src, indent=1) + "\n", encoding="utf-8")
    print("sealed %d files; now run harbour.py record and catalog.py build" % len(SEALED))
    return 0


def check() -> int:
    errs = []
    for rel, name in SEALED.items():
        b = (HERE / rel).read_bytes()
        out, info = seal(b)
        if out != b:
            errs.append("%s: %d sheets left without a back (rerun seal_props.py after the export or import)"
                        % (rel, info["back_triangles"]))
        row = _row(json.loads((SOURCES / name).read_text(encoding="utf-8")), rel)
        if hashlib.sha256(b).hexdigest() != row["sha256"]:
            errs.append("%s: sha256 differs from sources/%s" % (rel, name))
    for e in errs:
        print("CHECK " + e)
    print("sealed props: %d files, %s" % (len(SEALED), "OK" if not errs else "%d problems" % len(errs)))
    return 1 if errs else 0


def main(argv: list) -> int:
    if argv[:1] == ["--check"]:
        return check()
    if argv:
        print(__doc__)
        return 2
    return build()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
