#!/usr/bin/env python3
"""Checks kit/style/materials: the library is sound (files, hashes, seamless, neutral,
licence recorded), `use` paints a profile's tinted copies into a world and records their
credit, the texel-density rule passes 256 px/m and fails a blurry surface (a .glb quad at a
known UV scale, primitives, terrain), far LODs get the quarter rule, and the texture budget
passes a library world and fails one over the manifest or library budget. City props merged
into one file lose their unchanged-catalogue exemption (harbour a5 G10). With
IAMAR_GODOT and IAMAR_PROJECT (an the iamar browser source (not public) checkout; IAMAR_KIT_PACK set to a
tools/build_pack.sh pack), it also builds the sample world and the browser validates it.
Needs numpy and Pillow; without them it reports SKIPPED.

    python3 kit/tests/style/materials/materials_test.py
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

KIT = Path(__file__).resolve().parents[3]
MAT = KIT / "style" / "materials"
TOOL = MAT / "materials.py"


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)


def quad_glb(path: Path, size_m: float, uv_units: float, tex_px: int, node_name="wall"):
    """A size_m x size_m quad whose UVs span uv_units, with an embedded tex_px PNG:
    texel density = tex_px * uv_units / size_m."""
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (tex_px, tex_px), (150, 140, 120)).save(b, "PNG")
    png = b.getvalue()
    pos = struct.pack("<12f", 0, 0, 0, size_m, 0, 0, size_m, size_m, 0, 0, size_m, 0)
    uv = struct.pack("<8f", 0, uv_units, uv_units, uv_units, uv_units, 0, 0, 0)
    idx = struct.pack("<6H", 0, 1, 2, 0, 2, 3)
    pad = lambda x: x + b"\0" * (-len(x) % 4)
    blob = pos + uv + idx + pad(png)
    g = {
        "asset": {"version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"name": node_name, "mesh": 0}],
        "meshes": [{"name": node_name, "primitives": [{"attributes": {"POSITION": 0, "TEXCOORD_0": 1}, "indices": 2, "material": 0}]}],
        "materials": [{"name": "m", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}],
        "textures": [{"source": 0}],
        "images": [{"bufferView": 3, "mimeType": "image/png"}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 4, "type": "VEC3", "min": [0, 0, 0], "max": [size_m, size_m, 0]},
            {"bufferView": 1, "componentType": 5126, "count": 4, "type": "VEC2"},
            {"bufferView": 2, "componentType": 5123, "count": 6, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 48},
            {"buffer": 0, "byteOffset": 48, "byteLength": 32},
            {"buffer": 0, "byteOffset": 80, "byteLength": 12},
            {"buffer": 0, "byteOffset": 92, "byteLength": len(png)},
        ],
        "buffers": [{"byteLength": len(blob)}],
    }
    js = pad(json.dumps(g).encode()).replace(b"\0", b" ")
    out = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(blob))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(blob), 0x004E4942) + blob
    path.write_bytes(out)


def world(t: Path, name: str, objects=(), primitives=(), terrain=None, budgets=None) -> Path:
    w = t / name
    (w / "assets").mkdir(parents=True)
    (w / "manifest.json").write_text(json.dumps({"id": name, "budgets": budgets or {"texture_size": 2048, "texture_bytes": 64 << 20}}))
    scene = {"objects": list(objects), "primitives": list(primitives)}
    if terrain:
        scene["terrain"] = terrain
    (w / "scene.json").write_text(json.dumps(scene))
    return w


def main() -> int:
    try:
        import numpy as np  # noqa: F401
        from PIL import Image
    except ImportError as e:
        print("SKIPPED materials (%s)" % e)
        return 0
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else ": " + str(detail)[-900:]), flush=True)

    r = run("check")
    check("library check passes", r.returncode == 0 and "LIBRARY_OK 15" in r.stdout, r.stdout + r.stderr)
    lib = json.loads((MAT / "library.json").read_text(encoding="utf-8"))
    check("licence and origin recorded", lib.get("licence") and lib.get("origin") and lib.get("licences_row") == "original-procedural")
    lic = json.loads((KIT / "inventory" / "licences.json").read_text(encoding="utf-8"))
    check("licence row exists in kit/inventory/licences.json",
          any(row["id"] == lib.get("licences_row") for row in lic["rows"]))
    check("rule is 256 px/m at 4 m per 1024 px tile",
          lib["rule"]["near_px_per_m"] == 256 and lib["size"] / lib["tile_m"] == 256)

    with tempfile.TemporaryDirectory(prefix="iamar-mat-") as tmp:
        t = Path(tmp)
        # a broken copy of the library must fail its check
        broken = t / "broken"
        shutil.copytree(MAT, broken, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(KIT / "tools", t / "tools")
        shutil.copytree(KIT / "lint", t / "lint")
        a = np.asarray(Image.open(broken / "library" / "stone.jpg").convert("RGB"), dtype=np.float64)
        # non-tiling art: a crop of the map blown up to full size (its edges no longer meet)
        crop = Image.fromarray(a[:600, :600].astype(np.uint8)).resize((a.shape[1], a.shape[0]), Image.LANCZOS)
        crop.save(broken / "library" / "stone.jpg", quality=92)
        # broken/ is kit/style/materials one level too shallow; recreate the kit layout
        kit2 = t / "kit"
        (kit2 / "style").mkdir(parents=True)
        shutil.move(str(broken), str(kit2 / "style" / "materials"))
        shutil.move(str(t / "tools"), str(kit2 / "tools"))
        shutil.move(str(t / "lint"), str(kit2 / "lint"))
        rb = subprocess.run([sys.executable, str(kit2 / "style" / "materials" / "materials.py"), "check"],
                            capture_output=True, text=True)
        check("seeded seam + hash drift fails check", rb.returncode == 1 and "stone: does not tile" in rb.stdout
              and "stone: sha256" in rb.stdout, rb.stdout + rb.stderr)

        # use: iamar profile and the brand-new desert profile
        for prof, expect in (("iamar", "roof_slate"), (str(KIT / "style" / "schema" / "examples" / "desert_trading_post.style.json"), None)):
            w = world(t, "use_" + Path(prof).stem.split(".")[0])
            r = run("use", w, "--profile", prof, "--size", "256")
            idx = json.loads((w / "textures" / "materials" / "materials.json").read_text()) if r.returncode == 0 else {}
            mats = idx.get("materials", {})
            check("use %s writes tinted maps" % Path(prof).name, r.returncode == 0 and mats and
                  all((w / m["file"]).is_file() for m in mats.values()) and (expect is None or expect in mats), r.stdout + r.stderr)
            man = json.loads((w / "manifest.json").read_text())
            check("use %s records the credit" % Path(prof).name,
                  any("textures/materials/*" in c.get("files", []) and c.get("license") == lib["licence"] for c in man.get("credits", [])))
            if expect:
                # the tint lands: roof_slate's mean colour is the profile's #3e5d8c
                m = np.asarray(Image.open(w / mats["roof_slate"]["file"]).convert("RGB")).reshape(-1, 3).mean(axis=0)
                check("tint lands on the profile colour", np.abs(m - np.array([0x3e, 0x5d, 0x8c])).max() < 6, m.round(1))
                tr = np.asarray(Image.open(w / mats["trim"]["file"]).convert("RGB"), dtype=float)
                beam = tr[6 * 32 + 4: 7 * 32 - 4].reshape(-1, 3).mean(axis=0)   # strip 6 = beam, #5c3b22
                check("trim strips take trim_sheet.looks", np.abs(beam - np.array([0x5c, 0x3b, 0x22])).max() < 14, beam.round(1))
                r = run("texel", w)
                check("library maps in a world have no texel targets yet (nothing placed)", r.returncode == 0, r.stdout)
        r = run("use", t / "use_iamar", "--profile", "iamar", "--only", "marble")
        check("use refuses a material the profile lacks", r.returncode != 0 and "marble" in (r.stdout + r.stderr))
        # --size follows the 256 px/m rule: 512 map -> uv_scale 2; --only merges into the index
        mj = t / "use_iamar" / "textures" / "materials" / "materials.json"
        before = set(json.loads(mj.read_text())["materials"])
        r = run("use", t / "use_iamar", "--profile", "iamar", "--size", "256", "--only", "roof_slate")
        check("--only keeps the other materials in materials.json",
              r.returncode == 0 and set(json.loads(mj.read_text())["materials"]) == before, r.stdout + r.stderr)
        # --only at a different size than the existing index must refuse (an internal task): merging
        # the new entry would silently drop the other entries from the index while their
        # jpgs stay on disk; the index is left untouched
        r = run("use", t / "use_iamar", "--profile", "iamar", "--size", "512", "--only", "roof_slate")
        idx_after = json.loads(mj.read_text())
        check("--only refuses a size change with a clear message and leaves the index untouched",
              r.returncode != 0 and "silently dropping" in (r.stdout + r.stderr)
              and "without --only" in (r.stdout + r.stderr)
              and idx_after["size"] == 256 and set(idx_after["materials"]) == before, r.stdout + r.stderr)
        w5 = world(t, "use_512")
        r = run("use", w5, "--profile", "iamar", "--size", "512", "--only", "roof_slate")
        i5 = json.loads((w5 / "textures" / "materials" / "materials.json").read_text()) if r.returncode == 0 else {}
        check("--size 512 prints and records uv_scale 2",
              "uv_scale 2)" in r.stdout and i5.get("materials", {}).get("roof_slate", {}).get("uv_scale") == 2
              and i5.get("texels_per_metre") == 256, r.stdout + r.stderr)

        # texel density: 4 m quad, UVs 1 unit, 1024 px -> 256 px/m (pass); 512 px -> 128 (fail)
        w = world(t, "texel", objects=[
            {"id": "good", "asset": "assets/good.glb", "position": [0, 0, 0]},
            {"id": "far", "asset": "assets/far.glb", "position": [9, 0, 0]},
        ], primitives=[
            {"id": "floor", "shape": "box", "size": [8, 0.1, 8], "texture": "textures/t1024.png", "uv_scale": 4},
        ], terrain={"materials": [{"texture": "textures/t1024.png", "uv_scale": 4}]})
        (w / "textures").mkdir()
        Image.new("RGB", (1024, 1024), (120, 130, 110)).save(w / "textures" / "t1024.png")
        quad_glb(w / "assets" / "good.glb", 4.0, 1.0, 1024)
        quad_glb(w / "assets" / "far.glb", 4.0, 1.0, 128, node_name="house_LOD2")   # 32 px/m: far rule 51 -> fail
        quad_glb(w / "assets" / "blurry.glb", 4.0, 1.0, 512)
        quad_glb(w / "assets" / "waste.glb", 1.0, 1.0, 2048)
        quad_glb(w / "assets" / "farok.glb", 4.0, 1.0, 256, node_name="house_lod1")    # 64 px/m: far ok
        r = run("texel", w, "--json")
        rows = json.loads(r.stdout[:r.stdout.rindex("]") + 1]) if "[" in r.stdout else []
        byw = {x["where"].split(":")[-1].split(" ")[0]: x for x in rows}
        check("256 px/m glb passes, value exact", abs(byw.get("assets/good.glb", {}).get("px_per_m", 0) - 256) < 0.5
              and byw["assets/good.glb"]["level"] == "OK", rows)
        check("primitive and terrain at uv_scale 4 pass", byw.get("primitives.floor", {}).get("level") == "OK"
              and byw.get("terrain.materials[0]", {}).get("level") == "OK", rows)
        check("far LOD under the quarter rule fails", byw.get("assets/far.glb", {}).get("level") == "ERROR", rows)
        check("world with a failing surface exits 1", r.returncode == 1)
        r = run("texel", w / "assets" / "blurry.glb")
        check("128 px/m near surface fails", r.returncode == 1 and "TEXEL_FAIL" in r.stdout and "128 px/m" in r.stdout, r.stdout)
        r = run("texel", w / "assets" / "waste.glb")
        check("2048 px/m warns, does not fail", r.returncode == 0 and "WARN" in r.stdout, r.stdout)
        r = run("texel", w / "assets" / "farok.glb")
        check("far LOD at 64 px/m passes", r.returncode == 0, r.stdout)
        sc = json.loads((w / "scene.json").read_text())
        sc["objects"][0]["scale"] = 2
        (w / "scene.json").write_text(json.dumps(sc))
        r = run("texel", w, "--json")
        rows = json.loads(r.stdout[:r.stdout.rindex("]") + 1])
        good = [x for x in rows if "good.glb" in x["where"]][0]
        check("object scale 2 halves the density (128 px/m -> fails)", abs(good["px_per_m"] - 128) < 0.5 and good["level"] == "ERROR", good)

        # palette swatches: every face samples one texel of a colour strip, no density to judge (G8)
        quad_glb(t / "palette.glb", 4.0, 0.0, 256)
        r = run("texel", t / "palette.glb")
        check("a palette-swatch model passes as palette, not 0 px/m", r.returncode == 0 and "palette swatches" in r.stdout, r.stdout)

        # an unchanged catalogue city model keeps the city's ~128 px/m painting: WARN with the reason (G8)
        r = run("texel", KIT / "catalog" / "assets" / "props" / "market_stall.glb")
        check("a catalogue city model under the rule is exempt (WARN, exit 0)", r.returncode == 0
              and "WARN" in r.stdout and "exempt: an unchanged catalogue model from the iamar city" in r.stdout, r.stdout)
        shutil.copy(KIT / "catalog" / "assets" / "props" / "market_stall.glb", t / "stall_edit.glb")
        with open(t / "stall_edit.glb", "ab") as f:
            f.write(b"\0" * 4)        # no longer byte for byte the catalogue's file
        r = run("texel", t / "stall_edit.glb")
        check("a changed copy of a city model is judged by the rule", r.returncode == 1 and "exempt" not in r.stdout, r.stdout)

        # merged: two city stalls joined into one file (harbour a5 G10) are no longer the catalogue's
        # bytes, so the exemption does not follow them; keep city props as separate unchanged files
        raw = (KIT / "catalog" / "assets" / "props" / "market_stall.glb").read_bytes()
        jlen = struct.unpack_from("<I", raw, 12)[0]
        gj = json.loads(raw[20:20 + jlen])
        sc = gj["scenes"][gj.get("scene", 0)]
        def copy_tree(ni):
            n = dict(gj["nodes"][ni], name="b_" + gj["nodes"][ni].get("name", str(ni)))
            if "children" in n:
                n["children"] = [copy_tree(c) for c in n["children"]]
            gj["nodes"].append(n)
            return len(gj["nodes"]) - 1
        for ni in list(sc["nodes"]):
            ci = copy_tree(ni)
            gj["nodes"][ci]["translation"] = [3.0, 0.0, 0.0]
            sc["nodes"].append(ci)
        js = json.dumps(gj).encode()
        js += b" " * (-len(js) % 4)
        rest = raw[20 + jlen:]
        (t / "stalls_merged.glb").write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + len(rest))
                                              + struct.pack("<II", len(js), 0x4E4F534A) + js + rest)
        r = run("texel", t / "stalls_merged.glb")
        check("a merged file holding city stalls is judged by the rule (no exemption)",
              r.returncode == 1 and "TEXEL_FAIL" in r.stdout and "exempt" not in r.stdout, r.stdout)

        # budget
        w = world(t, "budget_ok", objects=[{"id": "a", "asset": "assets/a.glb", "position": [0, 0, 0]}])
        quad_glb(w / "assets" / "a.glb", 4.0, 1.0, 1024)
        r = run("budget", w)
        check("one 1024 map: 4 MiB, passes", r.returncode == 0 and "texture memory 4.0 MiB" in r.stdout, r.stdout)
        w = world(t, "budget_bad", objects=[{"id": "a%d" % i, "asset": "assets/a%d.glb" % i, "position": [i, 0, 0]} for i in range(5)],
                  budgets={"texture_size": 1024, "texture_bytes": 16 << 20})
        for i in range(5):
            quad_glb(w / "assets" / ("a%d.glb" % i), 4.0, 1.0, 2048 if i == 0 else 1024)
        r = run("budget", w, "--json")
        out = json.loads(r.stdout[:r.stdout.rindex("}") + 1])
        msgs = " | ".join(m for _, m in out["notes"])
        check("over the manifest bytes and size fails", r.returncode == 1 and "> budget 16.0 MiB" in msgs and "2048 px > 1024" in msgs, msgs)
        check("an embedded 16 MiB map warns per model", "a0.glb embeds 16.0 MiB" in msgs, msgs)
        check("the same image in several models warns", "embedded in 4 models" in msgs, msgs)
        check("counts like the browser (w x h x 4)", out["numbers"]["texture_bytes"] == 2048 * 2048 * 4 + 4 * 1024 * 1024 * 4, out["numbers"])
        w = world(t, "budget_lib", objects=[{"id": "a%d" % i, "asset": "assets/a%d.glb" % i, "position": [i, 0, 0]} for i in range(5)],
                  budgets={"texture_size": 2048, "texture_bytes": 256 << 20})
        for i in range(5):
            quad_glb(w / "assets" / ("a%d.glb" % i), 4.0, 1.0, 2048)
        r = run("budget", w)
        check("over the library's 64 MiB world budget fails even when the manifest allows it",
              r.returncode == 1 and "library 67108864" in r.stdout, r.stdout)
        # an internal task: the same models and images as the browser's count (validate STATS): attachments,
        # NPC models and theirs, quest look models, rendered impostor cards; each file once
        w = world(t, "budget_all", objects=[{"id": "a", "asset": "assets/a.glb", "position": [0, 0, 0], "impostor": {},
                                             "attach": [{"asset": "assets/hat.glb"}]},
                                            {"id": "a2", "asset": "assets/a.glb", "position": [5, 0, 0]}])
        sc = json.loads((w / "scene.json").read_text())
        sc["npcs"] = [{"id": "n", "model": "assets/npc.glb", "attach": [{"asset": "assets/tool.glb"}]}]
        sc["quests"] = [{"id": "q", "steps": [{"look": "assets/coin.glb", "count": 3}]}]
        (w / "scene.json").write_text(json.dumps(sc))
        for n in ("a", "hat", "npc", "tool", "coin"):
            quad_glb(w / "assets" / ("%s.glb" % n), 4.0, 1.0, 256)
        (w / "impostors" / "assets").mkdir(parents=True)
        (w / "impostors" / "assets" / "a.glb.json").write_text("{}")
        for k in ("albedo", "normal"):
            Image.new("RGB", (512, 256)).save(w / "impostors" / "assets" / ("a.glb.%s.png" % k))
        r = run("budget", w, "--json")
        out = json.loads(r.stdout[:r.stdout.rindex("}") + 1])
        check("budget counts attachments, NPCs, quest looks and impostor cards like validate",
              r.returncode == 0 and out["numbers"]["texture_bytes"] == 5 * 256 * 256 * 4 + 2 * 512 * 256 * 4, out["numbers"])

        # reused by hash (manifest.reused, `assets use <hash> --as`): resolved like lint/audit, not missing (G13)
        entries = json.loads((KIT / "catalog" / "catalog.json").read_text(encoding="utf-8"))["entries"]
        kit_e = next(e for e in entries if e["source"].get("file") == "kit/catalog/assets/harbour/net_pile.glb")
        builtin_e = next(e for e in entries if e["source"].get("origin") == "builtin")
        w = world(t, "budget_reused", objects=[{"id": "k", "asset": "assets/kit.glb", "position": [0, 0, 0]},
                                               {"id": "b", "asset": "assets/builtin.glb", "position": [2, 0, 0]}])
        m = json.loads((w / "manifest.json").read_text())
        m["reused"] = [{"path": "assets/kit.glb", "sha256": kit_e["source"]["sha256"]},
                       {"path": "assets/builtin.glb", "sha256": builtin_e["source"]["sha256"]}]
        (w / "manifest.json").write_text(json.dumps(m))
        r = run("budget", w, "--json")
        out = json.loads(r.stdout[:r.stdout.rindex("}") + 1])
        msgs = " | ".join(m for _, m in out["notes"])
        check("budget resolves reused assets (kit copy counted, built-in noted), not missing",
              r.returncode == 0 and "missing" not in msgs and "assets/kit.glb" in out["numbers"]["models"]
              and "builtin.glb: reused built-in" in msgs, r.stdout)
        r = run("texel", w, "--json")
        check("texel judges the kit's copy of a reused asset", "kit.glb mesh0/net" in r.stdout, r.stdout)
        m["reused"].append({"path": "assets/ghost.glb", "sha256": "0" * 64})
        (w / "manifest.json").write_text(json.dumps(m))
        sc = json.loads((w / "scene.json").read_text())
        sc["objects"].append({"id": "g", "asset": "assets/ghost.glb", "position": [4, 0, 0]})
        (w / "scene.json").write_text(json.dumps(sc))
        r = run("budget", w)
        check("a reused record with an unknown hash is still missing", r.returncode == 1 and "ghost.glb: missing" in r.stdout, r.stdout)

    godot, project = os.environ.get("IAMAR_GODOT"), os.environ.get("IAMAR_PROJECT")
    if godot and project:
        with tempfile.TemporaryDirectory(prefix="iamar-mat-sample-") as tmp:
            s = Path(tmp) / "materials_sample"
            r = run("sample", s, "--godot", godot, "--project", project)
            check("sample world builds and the browser validates it", r.returncode == 0 and "SAMPLE" in r.stdout, r.stdout + r.stderr)
            if r.returncode == 0:
                r = run("texel", s)
                check("sample passes the texel rule", r.returncode == 0, r.stdout)
                r = run("budget", s)
                check("sample passes the texture budget", r.returncode == 0, r.stdout)
    else:
        print("SKIPPED sample world (set IAMAR_GODOT, IAMAR_PROJECT and IAMAR_KIT_PACK)")
    print("kit materials tests: %d/%d" % (sum(checks), len(checks)))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
