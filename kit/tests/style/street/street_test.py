#!/usr/bin/env python3
"""Tests for `iamar-world style-gen street` (an internal task; harbour blind test attempt 4, gaps G9-G11):
a 12-house street (street.json, both sides of the harbour test's street) built as one .glb with
painted 1024 px maps passes every kit check per house:

  * texel: every near surface at 256 px per metre (`materials texel`);
  * texture budget: the street embeds each map once (6 maps, 24 MiB), under the 64 MiB world
    budget, where the same 12 houses as separate files embed 12 copies and fail it;
  * draw calls: the browser's merge_static key (merge_check.gd, headless Godot, skipped when no
    `godot` is on PATH) draws the street in at most one call per material, where 12 separate
    houses draw one per surface;
  * lint and audit judge each house (root node extras x-class building) on its own: 12 building
    budget lines and 12 audit objects, and all audits (closure, zfight, roof, edge, door) pass on
    the preview world (a merged row judged as one building failed them: G11);
  * per-house weathering survives (COLOR_0 differs between houses), the same input gives the same
    file, and a 512 px map set gets a 2 m tile (still 256 px per metre).

    python3 kit/tests/style/street/street_test.py [--keep DIR]

Needs numpy and Pillow (painter, audits); about a minute on a 4-thread CPU.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[2]
GEN = KIT / "style" / "gen" / "gen.py"
STREET = HERE / "street.json"
LAYERS = "dressed_stone,iron,roof_slate,timber,trim,wall_plaster"


def py(*args, cwd=None):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, cwd=cwd)


def glb_json(path: Path):
    data = path.read_bytes()
    n = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20:20 + n]), data[20 + n + 8:]


def main() -> int:
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    tmp = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="street_test_"))
    tmp.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (("  " + str(detail)[-900:]) if detail and not cond else ""), flush=True)

    try:
        import numpy  # noqa: F401
        import PIL  # noqa: F401
    except ImportError:
        print("SKIPPED street test (needs numpy and Pillow)")
        return 0
    maps = tmp / "maps"
    if not (maps / "roof_slate.png").is_file():
        r = py(KIT / "style" / "check_style.py", "--paint", maps, "--only", LAYERS)
        check("paint the iamar layers at 1024 px", r.returncode == 0, r.stdout + r.stderr)
    world = tmp / "world"
    shutil.rmtree(world, ignore_errors=True)
    out = tmp / "street.glb"
    r = py(GEN, "street", out, "--street", STREET, "--textures", maps, "--world", world, "--check", "--json")
    try:
        rep = json.loads(r.stdout)
    except ValueError:
        rep = {}
    check("style-gen street builds 12 houses and its audits pass", r.returncode == 0 and len(rep.get("houses", [])) == 12
          and rep.get("audit_ok"), r.stdout[-1500:] + r.stderr)
    check("every house within the building budget", rep and all(h["triangles"] <= h["budget"] for h in rep["houses"]),
          rep.get("houses"))
    check("1024 px maps tile every 4 m: 256 px/m", rep.get("tile_m") == 4.0 and rep.get("px_per_m") == 256.0, rep)

    g, bin_ = glb_json(out)
    roots = g["scenes"][0]["nodes"]
    marked = [g["nodes"][i] for i in roots if (g["nodes"][i].get("extras") or {}).get("x-class") == "building"]
    check("one root node per house, extras x-class building", len(roots) == 12 and len(marked) == 12,
          [g["nodes"][i].get("name") for i in roots])
    check("each painted map embedded once (6 images for 9 materials)", len(g.get("images", [])) == 6
          and len(g["materials"]) == 9, (len(g.get("images", [])), len(g["materials"])))
    check("houses keep their place and turn (translation + rotation)",
          marked[0].get("translation") == [3.0, 0.0, -10.0] and abs(abs(marked[0]["rotation"][1]) - 1.0) < 1e-6, marked[0])

    def colour(node_name, mat_name):
        mi = next(i for i, m in enumerate(g["materials"]) if m["name"] == mat_name)
        mesh = next(m for m in g["meshes"] if m["name"] == node_name)
        p = next(p for p in mesh["primitives"] if p["material"] == mi)
        a = g["accessors"][p["attributes"]["COLOR_0"]]
        return struct.unpack_from("<3f", bin_, g["bufferViews"][a["bufferView"]]["byteOffset"])
    check("per-house weathering in COLOR_0 (two houses differ)", colour("house_n1", "wall_plaster") != colour("house_s1", "wall_plaster"))
    out2 = tmp / "street2.glb"
    py(GEN, "street", out2, "--street", STREET, "--textures", maps)
    check("same input, same file", out2.read_bytes() == out.read_bytes())

    # the texel rule and the texture budget
    (world / "manifest.json").write_text(json.dumps({"format": "iamar-manifest", "budgets": {}}), encoding="utf-8")
    mats = KIT / "style" / "materials" / "materials.py"
    r = py(mats, "texel", world)
    check("materials texel passes", r.returncode == 0 and "TEXEL_OK" in r.stdout, r.stdout[-800:] + r.stderr)
    r = py(mats, "budget", world)
    check("materials budget passes (one copy of each map)", r.returncode == 0, r.stdout[-800:] + r.stderr)
    # the same houses as separate files: every file pays its maps again
    sep = tmp / "separate"
    shutil.rmtree(sep, ignore_errors=True)
    (sep / "assets").mkdir(parents=True)
    spec = json.loads(STREET.read_text(encoding="utf-8"))
    objs, files = [], []
    for h in spec["houses"]:
        f = sep / "assets" / (h["id"] + ".glb")
        args = ["house", f, "--region", spec["region"], "--seed", h["seed"], "--footprint", h["footprint"],
                "--storeys", h["storeys"], "--textures", maps, "--lods", "1"]
        for k in ("jetty", "oriel", "tower"):
            args.append("--" + k if h.get(k) else "--no-" + k)
        if "door_kind" in h:
            args += ["--door-kind", h["door_kind"]]
        py(GEN, *args)
        files.append(f)
        objs.append({"id": h["id"], "asset": "assets/" + f.name, "position": h["position"], "rotation": [0, h["yaw"], 0]})
    (sep / "scene.json").write_text(json.dumps({"format": "iamar-scene", "format_version": 0, "objects": objs}), encoding="utf-8")
    (sep / "manifest.json").write_text(json.dumps({"format": "iamar-manifest", "budgets": {}}), encoding="utf-8")
    r2 = py(mats, "budget", sep)
    check("the same 12 houses as separate files fail the budget", r2.returncode != 0 and "budget" in r2.stdout, r2.stdout[-600:])

    # lint and audit: every house on its own
    lint = KIT / "lint" / "style_lint.py"
    r = py(lint, world, "--json")
    try:
        lj = json.loads(r.stdout)
    except ValueError:
        lj = {"ok": False, "items": []}
    per_house = [i for i in lj["items"] if i["rule"] == "budget" and "#" in i["where"] and "class building" in i["message"]]
    check("lint passes, 12 houses linted as buildings", lj.get("ok") and len(per_house) == 12,
          [i for i in lj["items"] if i["level"] != "INFO"][:5] or len(per_house))
    audit = KIT / "audit" / "audit.py"
    r = py(audit, "all", world)
    check("audit all passes on the street world", r.returncode == 0, r.stdout[-1200:])
    sys.path.insert(0, str(KIT / "audit"))
    sys.path.insert(0, str(KIT / "lint"))
    import meshworld  # noqa: E402
    w = meshworld.load_world(world)
    classes = [o["cls"] for o in w.objects if o["id"].startswith("street/")]
    check("audit splits the street into 12 buildings", classes.count("building") == 12, classes)

    # draw calls with the browser's merge_static key (headless Godot)
    godot = shutil.which(os.environ.get("GODOT", "godot"))
    if godot:
        proj = tmp / "godot"
        proj.mkdir(exist_ok=True)
        (proj / "project.godot").write_text('config_version=5\n[application]\nconfig/name="street_merge_check"\n')
        shutil.copy(HERE / "merge_check.gd", proj / "merge_check.gd")

        def draws(*glbs):
            p = subprocess.run([godot, "--headless", "--path", str(proj), "--script", "merge_check.gd", "--", *map(str, glbs)],
                               capture_output=True, text=True, timeout=600)
            line = next((ln for ln in p.stdout.splitlines() if ln.startswith("MERGE_CHECK ")), "")
            kv = dict(x.split("=") for x in line.split()[1:])
            return int(kv.get("surfaces", -1)), int(kv.get("merged_draws", -1))
        s_one, d_one = draws(out)
        s_sep, d_sep = draws(*files)
        print("  draws: street %d surfaces -> %d merged; separate files %d surfaces -> %d merged" % (s_one, d_one, s_sep, d_sep))
        check("merge_static draws the street in at most one call per material", 0 < d_one <= len(g["materials"]), (s_one, d_one))
        check("separate files do not merge across files (G10)", d_sep >= 5 * d_one, (s_sep, d_sep))
    else:
        print("SKIPPED draw-call check (no godot on PATH)")

    # 512 px maps: 2 m tile at the same texel density
    maps512 = tmp / "maps512"
    if not (maps512 / "roof_slate.png").is_file():
        py(KIT / "style" / "check_style.py", "--paint", maps512, "--size", "512", "--only", LAYERS)
    r = py(GEN, "street", tmp / "street512.glb", "--street", STREET, "--textures", maps512, "--json")
    try:
        r512 = json.loads(r.stdout)
    except ValueError:
        r512 = {}
    check("512 px maps: tile 2 m, 256 px/m, 6 MiB", r512.get("tile_m") == 2.0 and r512.get("px_per_m") == 256.0
          and r512.get("texture_bytes") == 6 * 512 * 512 * 4, {k: r512.get(k) for k in ("tile_m", "px_per_m", "texture_bytes")})
    bad = tmp / "bad.json"
    bad.write_text(json.dumps({"houses": [{"id": "a", "position": [0, 0, 0]}, {"id": "a", "position": [9, 0, 0]}]}))
    r = py(GEN, "street", tmp / "bad.glb", "--street", bad)
    check("duplicate house ids are refused", r.returncode != 0 and "unique id" in r.stdout, r.stdout)

    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    print("street tests: %d/%d" % (sum(checks), len(checks)))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
