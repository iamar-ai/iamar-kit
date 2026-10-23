#!/usr/bin/env python3
"""Untagged root nodes in a several-models file (review of 616b914 + d0a99ea, an internal task).

Lint and audit judge a .glb whose root nodes carry extras {"x-class": C} (`style-gen street`)
root by root. A root node without x-class in such a file is drawn all the same, but was judged
by neither: a 600-triangle extra root left lint's count at the tagged house's 12 and audit with
one object. Now lint ERRORs [parts] for it and still counts and lints it; audit keeps it as a
`<file>/untagged` object.

Checks: every root tagged passes with no [parts] error; one untagged root fails lint [parts],
its triangles count in the file total, and audit has an object for it; a file with no x-class
at all is one ordinary model, as before.

    python3 kit/tests/lint/parts_untagged_test.py
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
LINT = KIT / "lint" / "style_lint.py"
sys.path[:0] = [str(KIT / "style" / "gen"), str(KIT / "audit")]
from meshkit import Mesh, write_glb  # noqa: E402
import meshworld  # noqa: E402

MATS = {"wall": {"color": "#a08060"}}


def house() -> Mesh:
    m = Mesh()
    m.box("wall", (0, 2, 0), (4, 4, 4))   # 12 triangles
    return m


def junk() -> Mesh:
    m = Mesh()
    for i in range(50):
        m.box("wall", (20 + i * 2.0, 1, 0), (1, 2, 1))   # 600 triangles
    return m


def run(*args):
    return subprocess.run([sys.executable, str(LINT), *map(str, args)], capture_output=True, text=True)


def together(out: str) -> int:
    m = re.search(r"(\d+) triangles at LOD0 together", out)
    return int(m.group(1)) if m else -1


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (("  " + detail.strip()[-900:]) if detail and not cond else ""), flush=True)

    tag = {"x-class": "building"}
    with tempfile.TemporaryDirectory(prefix="iamar-kit-parts-") as d:
        tmp = Path(d)

        f = tmp / "street.glb"
        write_glb(f, {"a": house(), "b": house()}, MATS, node_extras={"a": tag, "b": tag})
        p = run(f)
        check("every root tagged: lint passes, no [parts] error", p.returncode == 0 and "ERROR" not in p.stdout
              and together(p.stdout) == 24, p.stdout)
        w = meshworld.load_models([f])
        check("every root tagged: audit has one object per house", sorted(o["id"] for o in w.objects) == ["street/a", "street/b"],
              str([o["id"] for o in w.objects]))

        f = tmp / "mixed.glb"
        write_glb(f, {"house": house(), "junk": junk()}, MATS, node_extras={"house": tag})
        p = run(f)
        check("an untagged root fails lint [parts] and is named", p.returncode == 1 and "[parts]" in p.stdout
              and "mixed.glb#junk" in p.stdout, p.stdout)
        check("the untagged root's triangles count in the file total (612)", together(p.stdout) == 612, p.stdout)
        w = meshworld.load_models([f])
        ids = sorted(o["id"] for o in w.objects)
        check("audit keeps the untagged root as its own object", ids == ["mixed/house", "mixed/untagged"], str(ids))
        rest = [o for o in w.objects if o["id"] == "mixed/untagged"]
        check("the untagged object has the 600 triangles and a class",
              bool(rest) and sum(len(pt["tris"]) for pt in rest[0]["model"].parts) == 600 and bool(rest[0]["cls"]),
              str(rest and rest[0].get("cls")))

        f = tmp / "plain.glb"
        write_glb(f, {"house": house(), "junk": junk()}, MATS)
        p = run(f)
        check("no x-class at all: one ordinary model, no [parts] lines", "[parts]" not in p.stdout, p.stdout)
        w = meshworld.load_models([f])
        check("no x-class at all: audit has one object", [o["id"] for o in w.objects] == ["plain"],
              str([o["id"] for o in w.objects]))

    bad = checks.count(False)
    print("kit lint untagged-parts test: %d of %d failed" % (bad, len(checks)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
