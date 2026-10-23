#!/usr/bin/env python3
"""Checks kit/tools/paint_materials.py: sizes, materials.json, tint, and that every
texture tiles (the wrap-around seam is no stronger than an ordinary pixel step).
Needs numpy and Pillow; without them it reports SKIPPED and exits 0.

    python3 kit/tests/paint_materials_test.py
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

TOOL = Path(__file__).resolve().parents[1] / "tools" / "paint_materials.py"


def main() -> int:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        print("SKIPPED paint_materials (%s)" % e)
        return 0
    checks = []

    def check(name, cond, detail=""):
        checks.append(cond)
        print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""), flush=True)

    with tempfile.TemporaryDirectory(prefix="iamar-paint-") as raw:
        out = Path(raw) / "tex"
        p = subprocess.run([sys.executable, str(TOOL), str(out), "--materials", "stone,plaster,grass,sand",
                            "--size", "256", "--tint", "plaster=#c08060"], capture_output=True, text=True)
        check("runs", p.returncode == 0, p.stderr[-500:])
        meta = json.loads((out / "materials.json").read_text()) if (out / "materials.json").is_file() else {}
        check("materials.json", meta.get("size") == 256 and set(meta.get("materials", {})) == {"stone", "plaster", "grass", "sand"}
              and meta.get("tile_m") == 4.0)
        for name in ("stone", "plaster", "grass", "sand"):
            f = out / (name + ".png")
            if not f.is_file():
                check(name + " written", False)
                continue
            a = np.asarray(Image.open(f).convert("RGB")).astype(np.float64)
            check(name + " size", a.shape == (256, 256, 3), str(a.shape))
            inner_x = np.abs(np.diff(a, axis=1)).mean()
            inner_y = np.abs(np.diff(a, axis=0)).mean()
            seam_x = np.abs(a[:, 0] - a[:, -1]).mean()
            seam_y = np.abs(a[0] - a[-1]).mean()
            check(name + " tiles", seam_x < 2.5 * inner_x + 1 and seam_y < 2.5 * inner_y + 1,
                  "seam %.1f/%.1f vs step %.1f/%.1f" % (seam_x, seam_y, inner_x, inner_y))
        if (out / "plaster.png").is_file():
            m = np.asarray(Image.open(out / "plaster.png").convert("RGB")).reshape(-1, 3).mean(axis=0) / 255
            check("tint", abs(m[0] - 0.753) < 0.08 and abs(m[2] - 0.376) < 0.08, "mean %s" % np.round(m, 3))
        bad = subprocess.run([sys.executable, str(TOOL), str(out), "--materials", "marble"], capture_output=True, text=True)
        check("unknown material refused", bad.returncode != 0 and "unknown material" in bad.stderr)
        if (out / "grass.png").is_file():
            g = np.asarray(Image.open(out / "grass.png").convert("RGB")).reshape(-1, 3).mean(axis=0)
            check("grass is green", g[1] > g[0] and g[1] > g[2], "mean %s" % np.round(g, 1))
        if (out / "sand.png").is_file():
            m2 = np.asarray(Image.open(out / "sand.png").convert("RGB")).reshape(-1, 3).mean(axis=0)
            check("sand is warm", m2[0] > m2[2], "mean %s" % np.round(m2, 1))
        lst = subprocess.run([sys.executable, str(TOOL), "--list"], capture_output=True, text=True)
        check("list", lst.returncode == 0 and {"trim", "grass", "sand"} <= set(lst.stdout.split()))
    print("kit paint_materials tests: %d/%d" % (sum(checks), len(checks)))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
