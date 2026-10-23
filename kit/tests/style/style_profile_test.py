#!/usr/bin/env python3
"""Checks kit/style: the iamar profile and both example profiles pass check_style.py,
seeded mistakes fail it (unknown painter layer, invented scene field, loosened budget,
bad colour, black palette colour, missing source), and --paint writes tinted textures
for a profile that extends another. Painting needs numpy and Pillow; without them that
part reports SKIPPED.

    python3 kit/tests/style/style_profile_test.py
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[2]
TOOL = KIT / "style" / "check_style.py"
EXAMPLES = KIT / "style" / "schema" / "examples"


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append(cond)
        print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail and not cond else ""), flush=True)

    p = run()
    check("iamar profile passes", p.returncode == 0 and "OK" in p.stdout, p.stdout[-600:])
    for ex in ("desert_trading_post", "harbour_quarter"):
        p = run(EXAMPLES / ("%s.style.json" % ex))
        check("example %s passes" % ex, p.returncode == 0, p.stdout[-600:])

    iamar = json.loads((KIT / "style" / "iamar" / "style.json").read_text(encoding="utf-8"))
    check("iamar has 4 regions", set(iamar["regions"]) == {"civic", "mages", "warriors", "herbalists"})
    check("iamar paints 13 layers", len(iamar["materials"]["layers"]) == 13)
    check("iamar has 4 atmosphere presets", set(iamar["atmosphere"]["presets"]) == {"golden", "midday", "dusk", "night"})

    desert = json.loads((EXAMPLES / "desert_trading_post.style.json").read_text(encoding="utf-8"))
    seeded = {
        "unknown painter layer": (lambda d: d["materials"]["layers"].update({"marble": {"layer": "marble"}}), "painter has no layer"),
        "invented scene field": (lambda d: d["atmosphere"]["presets"]["noon_heat"]["environment"].update({"bloom": 0.5}), "no field 'bloom'"),
        "invented sub-field": (lambda d: d["atmosphere"]["presets"]["noon_heat"]["environment"]["fog"].update({"scatter": 0.3}), "no field 'scatter'"),
        "bad colour": (lambda d: d["palette"]["adobe"].update({"hex": "tan"}), "schema"),
        "black palette colour": (lambda d: d["palette"].update({"soot": {"hex": "#050505"}}), "no black surfaces"),
        "list grand_door_m": (lambda d: d.setdefault("dimensions", {}).update({"grand_door_m": [2.0, 3.2]}), "grand_door_m: must be an object"),
        "missing source": (lambda d: d.update({"sources": {"repo": "x"}}), "no source"),
    }
    with tempfile.TemporaryDirectory(prefix="iamar-style-") as raw:
        tmp = Path(raw)
        for name, (mutate, needle) in seeded.items():
            d = json.loads(json.dumps(desert))
            mutate(d)
            f = tmp / ("bad_%s.json" % name.replace(" ", "_"))
            f.write_text(json.dumps(d), encoding="utf-8")
            p = run(f)
            check("refuses %s" % name, p.returncode == 1 and needle in p.stdout, p.stdout[-400:])

        loose = json.loads((EXAMPLES / "harbour_quarter.style.json").read_text(encoding="utf-8"))
        loose["budgets"]["triangles"]["building"] = 9000
        f = tmp / "loose.json"
        f.write_text(json.dumps(loose), encoding="utf-8")
        p = run(f)
        check("refuses a loosened budget", p.returncode == 1 and "loosens iamar" in p.stdout, p.stdout[-400:])

        cyc = dict(loose, extends="harbour_quarter", id="harbour_quarter")
        f = tmp / "cycle.json"
        f.write_text(json.dumps(cyc), encoding="utf-8")
        check("refuses an extends cycle", run(f).returncode == 1)

        try:
            import numpy as np
            from PIL import Image
        except ImportError as e:
            print("SKIPPED paint (%s)" % e)
        else:
            out = tmp / "tex"
            p = run("--paint", out, "--profile", EXAMPLES / "harbour_quarter.style.json", "--size", "256",
                    "--only", "roof_slate,wall_plaster")
            check("paint runs on an extending profile", p.returncode == 0, (p.stdout + p.stderr)[-500:])
            idx = json.loads((out / "style_materials.json").read_text()) if (out / "style_materials.json").is_file() else {}
            check("paint index", idx.get("profile") == "harbour_quarter" and set(idx.get("materials", {})) == {"roof_slate", "wall_plaster"})
            f = out / "roof_slate.png"
            if f.is_file():
                m = np.asarray(Image.open(f).convert("RGB")).reshape(-1, 3).mean(axis=0)
                want = np.array([0x3e, 0x5d, 0x8c], dtype=float)
                check("paint tinted to the profile colour", np.abs(m - want).max() < 22, "mean %s want %s" % (np.round(m), want))
            else:
                check("roof_slate.png written", False)
            p = run("--paint", tmp / "x", "--profile", "iamar", "--only", "marble")
            check("paint refuses an unknown material", p.returncode == 1 and "no material" in p.stdout)

    print("kit style profile tests: %d/%d" % (sum(checks), len(checks)))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
