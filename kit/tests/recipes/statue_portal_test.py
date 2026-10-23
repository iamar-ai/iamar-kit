#!/usr/bin/env python3
"""Tests for the hero statue and portal gate recipes (kit/recipes/statue, kit/recipes/portal; an internal task).

Builds the portal gate (painted at 512 px) and, when Blender is found, the statue (lit live),
places both in one world with a portal through the gate, and requires:
the gate's closure, zfight and roof audits; `audit all`, `lint` (the arch rule reads the gate as
a semicircle, nothing over budget), `materials texel` and `materials budget` on the world; the
statue at 2,000-2,600 triangles, closed (closure audit 0, solid coat), two painted stone materials,
single-sided, weathering in COLOR_0.
Without Blender the statue checks are reported SKIPPED. About 30 s on a 4-thread CPU.

    python3 kit/tests/recipes/statue_portal_test.py [--keep DIR]
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tests"))
sys.dont_write_bytecode = True
from blender_tools_test import Glb, find_blender  # noqa: E402

PY = sys.executable
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print("%s %s%s" % ("PASS" if ok else "FAIL", name, (": " + detail) if detail and not ok else ""), flush=True)


def run(args, timeout=600):
    q = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return q.returncode, q.stdout + q.stderr


def main() -> int:
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    tmp = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="statue_portal_"))
    tmp.mkdir(parents=True, exist_ok=True)
    world = tmp / "world"
    try:
        rc, out = run([PY, str(KIT / "style" / "check_style.py"), "--paint", str(tmp / "tex"), "--profile", "iamar",
                       "--size", "512", "--only", "dressed_stone,wall_plaster"])
        check("paint 512 px maps", rc == 0, out[-400:])
        rc, out = run([PY, str(KIT / "recipes" / "portal" / "portal_gate.py"), str(tmp / "gate.glb"), "--textures",
                       str(tmp / "tex"), "--world", str(world), "--check", "--json"])
        rep = json.loads(out[out.index("{"):]) if "{" in out else {}
        check("portal_gate GATE_OK with audits", rc == 0 and rep.get("audit_ok"), out[-600:])
        check("gate is low cost (< 600 triangles)", 0 < rep.get("triangles", 0) < 600, str(rep.get("triangles")))
        check("opening fits a [2.4, 3.2] portal", rep.get("width", 0) >= 2.6 and rep.get("spring", 0) >= 3.0, str(rep))
        g = Glb(tmp / "gate.glb")
        check("gate embeds its painted maps", len(g.js.get("images", [])) >= 1, str(g.js.get("images")))
        check("gate node is portal_arch_LOD0", [n.get("name") for n in g.js["nodes"]] == ["portal_arch_LOD0"],
              str([n.get("name") for n in g.js["nodes"]]))
        desert = KIT / "blindtest" / "desert" / "world" / "style.json"      # Track B: no dressed-stone layer
        rc, out = run([PY, str(KIT / "recipes" / "portal" / "portal_gate.py"), str(tmp / "pl.glb"), "--profile",
                       str(desert), "--world", str(tmp / "plw"), "--check", "--json"])
        prep = json.loads(out[out.index("{"):]) if "{" in out else {}
        check("Track B profile gets the plaster variant (auto) with GATE_OK", rc == 0 and prep.get("variant") == "plaster"
              and prep.get("audit_ok"), out[-500:])
        check("plaster gate has no voussoir ring (fewer triangles than stone)",
              0 < prep.get("triangles", 0) < rep.get("triangles", 0), str(prep.get("triangles")))
        rc, out = run([PY, str(KIT / "recipes" / "portal" / "portal_gate.py"), str(tmp / "st.glb"), "--profile",
                       str(desert), "--variant", "stone", "--json"])
        check("--variant stone forces the coursed arch", rc == 0 and '"variant": "stone"' in out, out[-300:])
        rc, out = run([PY, str(KIT / "recipes" / "portal" / "portal_gate.py"), str(tmp / "bad.glb"), "--width", "0.5"])
        check("too narrow an opening is refused", rc == 2 and "GATE_FAIL" in out, out)

        scene = json.loads((world / "scene.json").read_text())
        check("preview world has a visual:none portal through the gate",
              scene["portals"][0]["visual"] == "none" and scene["objects"][0]["asset"] == "assets/gate.glb")

        blender = find_blender()
        if blender:
            rc, out = run([blender, "-b", "--factory-startup", "--python", str(KIT / "recipes" / "statue" / "statue.py"),
                           "--", str(world / "assets" / "statue.glb")])
            check("statue.py STATUE_OK", rc == 0 and "STATUE_OK" in out, out[-800:])
            check("cloak sheets made solid", "solid sheet faces 0" not in out and "solid sheet faces" in out, out[-300:])
            rc, aud = run([blender, "-b", "--factory-startup", "--python", str(KIT / "blender" / "closure_audit.py"),
                           "--", str(world / "assets" / "statue.glb"), "--ground", "0.02"])
            check("statue closure audit 0 (open, non-manifold, inside-out)", rc == 0 and "CLOSURE_OK" in aud, aud[-600:])
            s = Glb(world / "assets" / "statue.glb")
            tris = sum(s.js["accessors"][p["indices"]]["count"] // 3 for p in s.prims())
            check("statue 2,000-2,600 triangles (the recipe 2.5k budget, 8k lint class)", 2000 <= tris <= 2600, str(tris))
            mats = sorted(m.get("name", "") for m in s.js.get("materials", []))
            check("statue has painted figure and plinth maps", mats == ["statue_plinth", "statue_stone"]
                  and all("baseColorTexture" in m.get("pbrMetallicRoughness", {}) for m in s.js["materials"]), str(mats))
            check("statue materials are single-sided (sheets have their own back faces)",
                  all(not m.get("doubleSided") for m in s.js["materials"]), str(s.js["materials"]))
            cols = [c for p in s.prims() for c in s.accessor(p["attributes"]["COLOR_0"])] \
                if all("COLOR_0" in p["attributes"] for p in s.prims()) else []
            lum = [sum(c[:3]) / 3 for c in cols]
            check("statue weathering in COLOR_0 (varies 0.42-1, not one flat colour)",
                  lum and min(lum) >= 0.41 and max(lum) <= 1.0 and max(lum) - min(lum) > 0.3,
                  "%d colours %s" % (len(lum), (min(lum), max(lum)) if lum else ""))
            scene["objects"][0]["position"] = [0, 0, 8]
            scene["portals"][0]["position"] = [0, 0, 8]
            scene["objects"].append({"id": "statue", "asset": "assets/statue.glb", "position": [0, 0, 0],
                                     "collision": "mesh"})
            (world / "scene.json").write_text(json.dumps(scene, indent=1))
        else:
            print("SKIPPED statue checks: no Blender 4.2+ (BLENDER=/path, PATH or ~/opt/blender-*)")
        (world / "manifest.json").write_text(json.dumps({
            "api_version": "0.3", "author": {"name": "kit test"}, "format": "iamar-world", "format_version": 0,
            "id": "statue_portal_test", "name": "statue and portal recipes", "scene": "scene.json", "spawn": "default",
            "version": "0.1.0", "features": ["objects", "primitives", "portals"],
            "budgets": {"triangles": 150000, "objects": 400, "texture_size": 1024, "texture_bytes": 67108864,
                        "lights": 16, "package_bytes": 64000000, "audio_bytes": 4194304, "script_bytes": 0}}, indent=1))
        rc, out = run([PY, str(KIT / "audit" / "audit.py"), "all", str(world), "--quiet"])
        check("audit all on the world", rc == 0, out[-800:])
        rc, out = run([PY, str(KIT / "lint" / "style_lint.py"), str(world)])
        check("lint passes with no warnings", rc == 0 and "0 error(s), 0 warning(s)" in out, out[-800:])
        check("lint reads the gate as a semicircular arch", "rise / half span 1.00" in out, out[-800:])
        rc, out = run([PY, str(KIT / "style" / "materials" / "materials.py"), "texel", str(world)])
        check("materials texel (256 px/m)", rc == 0 and "TEXEL_OK" in out, out[-800:])
        rc, out = run([PY, str(KIT / "style" / "materials" / "materials.py"), "budget", str(world), "--profile", "iamar"])
        check("materials budget", rc == 0 and "BUDGET_OK" in out, out[-800:])
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    failed = [n for n, ok, _ in results if not ok]
    print("statue/portal recipe tests: %d/%d" % (len(results) - len(failed), len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
