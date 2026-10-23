#!/usr/bin/env python3
"""LOD nodes in a world package (harbour attempt 4, gaps G10 and G14; an internal task).

The browser has no `_LOD<n>` node handling for package models: it draws every node of a
.glb, so a model written with LOD0-2 in one file (`style-gen` default) costs the triangles
and draw calls of all three, on top of each other (13 style-gen lanterns: 58 draws with
their LOD nodes, 23 with `--lods 1`). The browser makes its own LOD chain (recipe
`lod_chain`), so a package ships LOD0 only.

Checks: `iamar-world lint` on a world ERRORs [lod] for an asset with LOD1+ nodes and counts
every drawn node in the frame total; the same model linted on its own keeps its LOD report
and no [lod] package error; a LOD0-only asset in the world passes.

    python3 kit/tests/lint/lod_nodes_test.py
"""
from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
LINT = KIT / "lint" / "style_lint.py"
SAMPLES = KIT / "lint" / "samples"
sys.path.insert(0, str(HERE))
from glb_fixture import house, write_glb  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(LINT), *map(str, args)], capture_output=True, text=True)


def placed(out: str) -> int:
    m = re.search(r"(\d+) placed triangles", out)
    return int(m.group(1)) if m else -1


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (("  " + detail.strip()[-900:]) if detail and not cond else ""), flush=True)

    lod0 = house(tris=1200)
    chain = lod0 + [dict(p, lod=1) for p in house(tris=600)] + [dict(p, lod=2) for p in house(tris=240)]
    with tempfile.TemporaryDirectory(prefix="iamar-kit-lodnodes-") as d:
        tmp = Path(d)

        # the model on its own: LODs are reported, no package error
        f = write_glb(tmp / "single" / "house.glb", chain)
        p = run(f)
        check("single model with LOD0-2 passes lint as before", p.returncode == 0 and "LOD1 600" in p.stdout
              and "[lod]" not in p.stdout, p.stdout)

        # baseline world: the city sample, B002 replaced by a LOD0-only house
        base = tmp / "lod0_only"
        shutil.copytree(SAMPLES / "iamar_city", base)
        write_glb(base / "assets" / "B002.glb", lod0)
        p = run(base)
        check("world with a LOD0-only asset passes", p.returncode == 0 and "[lod]" not in p.stdout, p.stdout)
        tris_lod0 = placed(p.stdout)

        # the same world with LOD1 and LOD2 nodes in that asset
        world = tmp / "lod_nodes"
        shutil.copytree(SAMPLES / "iamar_city", world)
        write_glb(world / "assets" / "B002.glb", chain)
        p = run(world)
        check("world asset with LOD1+ nodes fails lint [lod]", p.returncode == 1 and "[lod]" in p.stdout
              and "B002.glb" in p.stdout, p.stdout)
        check("the [lod] error names the fix (--lods 1, lod_chain)", "--lods 1" in p.stdout and "lod_chain" in p.stdout, p.stdout)
        n = sum(1 for line in p.stdout.splitlines() if "[lod]" in line and "B002.glb" in line)
        check("one [lod] error per asset, not per placement", n == 1, p.stdout)
        uses = (world / "scene.json").read_text(encoding="utf-8").count('"assets/B002.glb"')
        check("frame total counts every drawn LOD node (%d placements x 840 more)" % uses,
              tris_lod0 > 0 and placed(p.stdout) == tris_lod0 + uses * (600 + 240), p.stdout)

    bad = checks.count(False)
    print("kit lint LOD-node test: %d of %d failed" % (bad, len(checks)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
