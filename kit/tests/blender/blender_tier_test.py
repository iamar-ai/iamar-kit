#!/usr/bin/env python3
"""Runs the kit's Blender-tier commands (weld, closure_audit, lods, atlas, trim_map,
asset_pipeline in kit/blender/) headless on small generated models and checks what they
write. Needs Blender 4.2+ (BLENDER=/path/to/blender, on PATH, or in a usual install
folder); without it every check is reported SKIPPED and the test exits 0. About a
minute on a laptop CPU; every bake runs on the CPU.

    python3 kit/tests/blender/blender_tier_test.py [--keep DIR]
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
TOOLS = KIT / "blender"
sys.path.insert(0, str(KIT / "tests"))
from blender_tools_test import Glb, find_blender  # noqa: E402

# Test models (Blender +Z up, exported as glTF):
#   split.glb  : a 1 m cube whose 6 faces are separate (24 vertices), for weld
#   closed.glb : a 2 m house block with a pyramid roof resting on its top, both closed
#   open.glb   : the house block without its top face and without a roof (4 open 2 m edges)
#   inside.glb : a closed cube with its normals flipped (inside out)
#   corner.glb : one mesh of two closed 2 m cubes sharing one vertical outer edge (a non-manifold edge at x=1, z=-1)
#   dense.glb  : a 2-material sphere of about 3,800 triangles, for LODs and the atlas
#   cornice.glb: a 3 m x 0.3 m x 0.2 m moulding with material "trim"
GEN = r'''
import bpy, bmesh, sys
out = sys.argv[sys.argv.index("--") + 1]
def mat(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    return m
def export(name, obs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=out + "/" + name, export_format="GLB", use_selection=True, export_apply=True)
def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
clear()
bpy.ops.mesh.primitive_cube_add(size=1); c = bpy.context.object; c.data.materials.append(mat("stone", (.6, .6, .55)))
bm = bmesh.new(); bm.from_mesh(c.data); bmesh.ops.split_edges(bm, edges=bm.edges[:]); bm.to_mesh(c.data); bm.free()
export("split.glb", [c])
clear()
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1)); h = bpy.context.object; h.name = "walls"; h.data.materials.append(mat("plaster", (.8, .75, .6)))
bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=1.414, depth=1.2, location=(0, 0, 2.6), rotation=(0, 0, 0.7853982)); r = bpy.context.object; r.name = "roof"; r.data.materials.append(mat("slate", (.3, .35, .45)))
export("closed.glb", [h, r])
h["x-class"] = "wall_model"; r["x-class"] = "roof_model"
bpy.ops.object.select_all(action="DESELECT"); h.select_set(True); r.select_set(True)
bpy.ops.export_scene.gltf(filepath=out + "/multi.glb", export_format="GLB", use_selection=True, export_apply=True, export_extras=True)
bm = bmesh.new(); bm.from_mesh(h.data); bm.faces.ensure_lookup_table()
top = [f for f in bm.faces if f.normal.z > 0.9]; bmesh.ops.delete(bm, geom=top, context="FACES_ONLY"); bm.to_mesh(h.data); bm.free()
export("open.glb", [h])
clear()
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5)); i = bpy.context.object; i.name = "inside"
bm = bmesh.new(); bm.from_mesh(i.data); bmesh.ops.reverse_faces(bm, faces=bm.faces[:]); bm.to_mesh(i.data); bm.free()
export("inside.glb", [i])
clear()
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1)); a = bpy.context.object; a.name = "wing_a"
bpy.ops.mesh.primitive_cube_add(size=2, location=(2, 2, 1)); b = bpy.context.object; b.name = "wing_b"
bpy.ops.object.select_all(action="DESELECT"); a.select_set(True); b.select_set(True); bpy.context.view_layer.objects.active = a
bpy.ops.object.join()
export("corner.glb", [a])
clear()
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=40, radius=1); s = bpy.context.object; s.name = "dense"
s.data.materials.append(mat("red", (.8, .15, .1))); s.data.materials.append(mat("blue", (.1, .2, .8)))
for p in s.data.polygons:
    p.material_index = 1 if p.center.z > 0 else 0
export("dense.glb", [s])
clear()
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 3)); t = bpy.context.object; t.name = "cornice"
t.scale = (3, 0.2, 0.3); bpy.ops.object.transform_apply(scale=True); t.data.materials.append(mat("trim", (.8, .78, .7)))
export("cornice.glb", [t])
clear()
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5)); sp = bpy.context.object; sp.name = "vane"; sp.data.materials.append(mat("stone", (.6, .6, .55)))
sp.rotation_euler = (0, 0, 0); sp.keyframe_insert("rotation_euler", frame=1)
sp.rotation_euler = (0, 0, 3.14159); sp.keyframe_insert("rotation_euler", frame=30)
sp.animation_data.action.name = "spin"
bpy.ops.object.select_all(action="DESELECT"); sp.select_set(True)
bpy.ops.export_scene.gltf(filepath=out + "/animated.glb", export_format="GLB", use_selection=True, export_apply=True, export_animations=True)
print("GEN_OK")
'''

RESULTS: list[tuple[str, str, str]] = []
NAMES = ["generate", "weld", "weld_merged", "weld_hard_edges", "closure_closed_ok", "closure_open_fails", "closure_open_edges",
         "closure_skip", "closure_ground", "closure_inside_out", "closure_nonmanifold_at",
         "closure_allow_nonmanifold", "lods", "lods_smaller", "lods_report",
         "lods_targets", "atlas", "atlas_one_material", "atlas_texture", "trim_map", "trim_map_band",
         "pipeline", "pipeline_report", "pipeline_stops_on_open",
         "pipeline_light_options", "pipeline_keeps_animation", "pipeline_unnamed_clip", "pipeline_keeps_extras", "help"]


def check(name, cond, detail=""):
    RESULTS.append((name, "PASS" if cond else "FAIL", detail))
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""), flush=True)


def strip_clip_names(src, dst):
    """Copy of a .glb with the animations' names removed (JSON chunk rewritten)."""
    data = Path(src).read_bytes()
    jlen = int.from_bytes(data[12:16], "little")
    js = json.loads(data[20:20 + jlen])
    for x in js.get("animations", []):
        x.pop("name", None)
    raw = json.dumps(js).encode()
    raw += b" " * (-len(raw) % 4)
    body = len(raw).to_bytes(4, "little") + b"JSON" + raw + data[20 + jlen:]
    Path(dst).write_bytes(data[:8] + (12 + len(body)).to_bytes(4, "little") + body)


def run(blender, script_args, label):
    cmd = [blender, "-b", "--factory-startup"] + script_args
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    ok = p.returncode == 0
    if not ok and "--expect-fail" not in label:
        print("---- %s exited %d:\n%s\n%s" % (label, p.returncode, p.stdout[-2500:], p.stderr[-2500:]), flush=True)
    return ok, p.stdout + p.stderr


def tool(name):
    return ["--python", str(TOOLS / name), "--"]


def tris(path):
    g = Glb(path)
    return sum(len(g.accessor(p["indices"])) // 3 for p in g.prims())


def main() -> int:
    keep = Path(sys.argv[sys.argv.index("--keep") + 1]).resolve() if "--keep" in sys.argv else None
    blender = find_blender()
    if blender is None:
        for n in NAMES:
            print("SKIPPED " + n + "  (no Blender: set BLENDER=/path/to/blender)")
        print("kit blender tier tests: skipped (no Blender)")
        return 0
    print("BLENDER", blender, flush=True)
    w = Path(keep or tempfile.mkdtemp(prefix="iamar-kit-tier-"))
    w.mkdir(parents=True, exist_ok=True)
    try:
        ok, _ = run(blender, ["--python-expr", GEN, "--", str(w)], "generate")
        ok = ok and "GEN_OK" in _ and (w / "dense.glb").is_file()
        check("generate", ok)
        if not ok:
            return 1

        # weld: 24 split vertices of the cube become 8 (glTF splits them again only where UVs or normals differ)
        ok, log = run(blender, tool("weld.py") + [str(w / "split.glb"), str(w / "welded.glb"), "--report", str(w / "weld.json")], "weld")
        check("weld", ok and "WELD_OK" in log and (w / "welded.glb").is_file())
        rep = json.loads((w / "weld.json").read_text()) if (w / "weld.json").is_file() else {}
        check("weld_merged", rep.get("vertices") == [24, 8] and rep.get("triangles") == [12, 12], str(rep.get("vertices")))
        if (w / "welded.glb").is_file():
            g = Glb(w / "welded.glb")
            ns = [n for p in g.prims() for n in g.accessor(p["attributes"]["NORMAL"])]
            check("weld_hard_edges", bool(ns) and all(max(abs(c) for c in n) > 0.999 for n in ns),
                  "%d exported normals, all face-flat" % len(ns))
        else:
            check("weld_hard_edges", False)

        # closure audit
        ok, log = run(blender, tool("closure_audit.py") + [str(w / "closed.glb"), "--report", str(w / "c_closed.json")], "closure closed")
        check("closure_closed_ok", ok and "CLOSURE_OK" in log)
        ok, log = run(blender, tool("closure_audit.py") + [str(w / "open.glb"), "--report", str(w / "c_open.json")], "closure open --expect-fail")
        check("closure_open_fails", not ok and "CLOSURE_FAIL" in log)
        rep = json.loads((w / "c_open.json").read_text()) if (w / "c_open.json").is_file() else {}
        tot = rep.get("totals", {})
        tops = [e["at"][1] for e in rep.get("open_edges", [])]
        check("closure_open_edges", tot.get("open") == 4 and abs(tot.get("open_length_m", 0) - 8.0) < 0.01
              and all(abs(y - 2.0) < 0.01 for y in tops), "open=%s length=%s heights=%s" % (tot.get("open"), tot.get("open_length_m"), tops))
        ok, log = run(blender, tool("closure_audit.py") + [str(w / "open.glb"), "--skip", "walls*"], "closure skip")
        check("closure_skip", ok and "CLOSURE_OK" in log)
        ok, log = run(blender, tool("closure_audit.py") + [str(w / "open.glb"), "--ground", "2.0"], "closure ground")
        check("closure_ground", ok and "CLOSURE_OK" in log, "edges at the ground height count as sealed")
        ok, log = run(blender, tool("closure_audit.py") + [str(w / "inside.glb")], "closure inside --expect-fail")
        check("closure_inside_out", not ok and "inside-out" in log)

        ok, log = run(blender, tool("closure_audit.py") + [str(w / "corner.glb"), "--report", str(w / "c_corner.json")], "closure corner --expect-fail")
        rep = json.loads((w / "c_corner.json").read_text()) if (w / "c_corner.json").is_file() else {}
        nm = rep.get("nonmanifold_edges", [])
        check("closure_nonmanifold_at", not ok and len(nm) == 1 and "NONMANIFOLD_EDGE" in log
              and abs(nm[0]["at"][0] - 1) < 0.01 and abs(nm[0]["at"][1] - 1) < 0.01 and abs(nm[0]["at"][2] + 1) < 0.01
              and abs(nm[0]["length_m"] - 2) < 0.01, str(nm))
        ok, log = run(blender, tool("closure_audit.py") + [str(w / "corner.glb"), "--allow-nonmanifold"], "closure corner allow")
        check("closure_allow_nonmanifold", ok and "CLOSURE_OK" in log and "NONMANIFOLD_EDGE" in log)

        # LODs
        ok, log = run(blender, tool("lods.py") + [str(w / "dense.glb"), str(w / "lod" / "dense"), "--mode", "collapse", "--budget", "3000"], "lods")
        check("lods", ok and "LODS_OK" in log and all((w / "lod" / ("dense_lod%d.glb" % i)).is_file() for i in range(3)))
        if ok:
            t = [tris(w / "lod" / ("dense_lod%d.glb" % i)) for i in range(3)]
            check("lods_smaller", t[0] > t[1] > t[2] and 0.4 < t[1] / t[0] < 0.6 and 0.12 < t[2] / t[0] < 0.28, str(t))
            rep = json.loads((w / "lod" / "dense_lods.json").read_text())
            check("lods_report", [l["triangles"] for l in rep["levels"]] == t and rep["budget"] == 3000
                  and abs(rep["efficiency"] - round(100.0 * 3000 / t[0], 1)) < 0.05, "efficiency %s" % rep.get("efficiency"))
        ok, log = run(blender, tool("lods.py") + [str(w / "dense.glb"), str(w / "lod" / "tg"), "--targets", "1000,300"], "lods targets")
        if ok:
            t = [tris(w / "lod" / ("tg_lod%d.glb" % i)) for i in (1, 2)]
            check("lods_targets", 800 < t[0] < 1200 and 200 < t[1] < 400, str(t))
        else:
            check("lods_targets", False)

        # atlas: two materials become one with one texture; the texture shows both colours
        ok, log = run(blender, tool("atlas.py") + [str(w / "dense.glb"), str(w / "atlas.glb"), "--size", "256", "--cpu",
                                                   "--save-atlas", str(w / "atlas.png")], "atlas")
        check("atlas", ok and "ATLAS_OK" in log and "ATLAS_TEXEL_DENSITY" in log)
        if ok:
            g = Glb(w / "atlas.glb")
            mats = g.js.get("materials", [])
            check("atlas_one_material", len(mats) == 1 and len({p.get("material") for p in g.prims()}) == 1,
                  "%d materials" % len(mats))
            col = None
            try:
                from PIL import Image
                im = Image.open(w / "atlas.png").convert("RGB").resize((64, 64))
                px = list(im.get_flattened_data()) if hasattr(im, "get_flattened_data") else list(im.getdata())
                col = (sum(1 for r, gg, b in px if r > 150 and b < 90), sum(1 for r, gg, b in px if b > 150 and r < 90))
            except ImportError:
                pass
            has_tex = "baseColorTexture" in mats[0].get("pbrMetallicRoughness", {}) if mats else False
            if col is None:
                check("atlas_texture", has_tex and (w / "atlas.png").stat().st_size > 500, "PIL missing: size only")
            else:
                check("atlas_texture", has_tex and col[0] > 50 and col[1] > 50, "red px %d, blue px %d" % col)

        # trim map: every UV of the cornice lies in strip 0 (cornice: v from 7/8 to 1)
        ok, log = run(blender, tool("trim_map.py") + [str(w / "cornice.glb"), str(w / "cornice_trim.glb"), "--strip", "cornice",
                                                      "--material", "trim"], "trim_map")
        check("trim_map", ok and "TRIM_MAP_OK" in log and "faces 12" in log)
        if ok:
            g = Glb(w / "cornice_trim.glb")
            pts = []
            for p in g.prims():
                pts += list(zip(g.accessor(p["attributes"]["NORMAL"]), g.accessor(p["attributes"]["TEXCOORD_0"])))
            vs = [uv[1] for _, uv in pts]
            # the long front face (normal glTF +z): u runs 3 m at 4 m per repeat, v covers the whole strip
            front = [uv for nrm, uv in pts if nrm[2] > 0.99]
            fu = [uv[0] for uv in front]
            fv = [uv[1] for uv in front]
            # glTF flips v: Blender v 7/8..1 (top strip) is glTF v 0..1/8
            check("trim_map_band", bool(front) and all(-1e-4 <= v <= 0.125 + 1e-4 for v in vs)
                  and abs(max(fu) - min(fu) - 0.75) < 1e-3 and min(fv) < 1e-3 and max(fv) > 0.125 - 1e-3,
                  "v %.3f..%.3f, front u span %.3f (want 0.75)" % (min(vs), max(vs), (max(fu) - min(fu)) if fu else -1))

        # one command: weld, closure, atlas, AO, LODs
        ok, log = run(blender, tool("asset_pipeline.py") + [str(w / "closed.glb"), str(w / "pipe"), "--name", "house",
                                                            "--atlas", "--atlas-size", "128", "--light", "ao", "--samples", "8",
                                                            "--budget", "300", "--cpu"], "pipeline")
        check("pipeline", ok and "PIPELINE_OK" in log and (w / "pipe" / "house.glb").is_file())
        if (w / "pipe" / "pipeline.json").is_file():
            rep = json.loads((w / "pipe" / "pipeline.json").read_text())
            steps = [s["step"] for s in rep["steps"]]
            check("pipeline_report", rep["result"] == "ok" and steps == ["weld", "closure", "atlas", "light", "lods"]
                  and len(rep.get("triangles_per_lod", [])) == 3 and rep.get("efficiency") == 100.0,
                  "%s tris %s" % (steps, rep.get("triangles_per_lod")))
        else:
            check("pipeline_report", False, "no pipeline.json")
        ok, log = run(blender, tool("asset_pipeline.py") + [str(w / "open.glb"), str(w / "pipe_open"), "--cpu"], "pipeline open --expect-fail")
        rep = json.loads((w / "pipe_open" / "pipeline.json").read_text()) if (w / "pipe_open" / "pipeline.json").is_file() else {}
        check("pipeline_stops_on_open", not ok and rep.get("result") == "fail"
              and [s["step"] for s in rep.get("steps", [])] == ["weld", "closure"])

        # light-bake options reach bake_unlit.py (a negative sun direction too)
        ok, log = run(blender, tool("asset_pipeline.py") + [str(w / "closed.glb"), str(w / "pipe_lit"), "--light", "unlit",
                                                            "--samples", "4", "--sun=-0.8,0.45,-0.4", "--sun-strength", "2.5",
                                                            "--texel", "0.05", "--max-size", "128", "--no-closure", "--cpu"],
                      "pipeline unlit options")
        rep = json.loads((w / "pipe_lit" / "pipeline.json").read_text()) if (w / "pipe_lit" / "pipeline.json").is_file() else {}
        res = [l for s in rep.get("steps", []) if s["step"] == "light" for l in s["result"]]
        check("pipeline_light_options", ok and rep.get("result") == "ok"
              and any("2.5 towards -0.8,0.45,-0.4" in l for l in res) and any(l.startswith("DENOISED") for l in res),
              "; ".join(l for l in res if l.startswith(("LIGHTS", "DENOISE"))) or "no light step")

        # a model's animation clip survives the whole pipeline (or the pipeline refuses, naming the clip)
        ok, log = run(blender, tool("asset_pipeline.py") + [str(w / "animated.glb"), str(w / "pipe_anim"), "--name", "vane",
                                                            "--budget", "300", "--cpu"], "pipeline animated")
        names = [x.get("name") for x in Glb(w / "pipe_anim" / "vane.glb").js.get("animations", [])] if ok else []
        check("pipeline_keeps_animation", ok and "spin" in names, "clips %s" % names)
        # a clip with no name (allowed by glTF) comes back from Blender as Anim_0: not a lost clip
        unnamed = w / "animated_unnamed.glb"
        strip_clip_names(w / "animated.glb", unnamed)
        ok, log = run(blender, tool("asset_pipeline.py") + [str(unnamed), str(w / "pipe_unnamed"), "--name", "vane",
                                                            "--budget", "300", "--cpu"], "pipeline unnamed clip")
        n = len(Glb(w / "pipe_unnamed" / "vane.glb").js.get("animations", [])) if ok else 0
        check("pipeline_unnamed_clip", ok and n == 1, "ok %s, clips %d" % (ok, n))

        # node extras (x-class of each model in a multi-model file) survive the pipeline, in every LOD file
        ok, log = run(blender, tool("asset_pipeline.py") + [str(w / "multi.glb"), str(w / "pipe_multi"), "--name", "multi",
                                                            "--budget", "300", "--cpu"], "pipeline multi-model extras")
        want = {"walls": "wall_model", "roof": "roof_model"}
        got = {}
        for fn in ("multi.glb", "multi_lod1.glb", "multi_lod2.glb"):
            f = w / "pipe_multi" / fn
            got[fn] = {n.get("name"): (n.get("extras") or {}).get("x-class") for n in Glb(f).js.get("nodes", [])
                       if n.get("name") in want} if f.is_file() else {}
        check("pipeline_keeps_extras", ok and all(g == want for g in got.values()), "%s" % got)

        helps = []
        for t in ("weld.py", "closure_audit.py", "lods.py", "atlas.py", "trim_map.py", "asset_pipeline.py"):
            ok, log = run(blender, tool(t) + ["--help"], t + " --help")
            helps.append(ok and "usage:" in log)
        check("help", all(helps), "%d/%d tools" % (sum(helps), len(helps)))
    finally:
        if keep is None:
            shutil.rmtree(w, ignore_errors=True)
    failed = [r for r in RESULTS if r[1] == "FAIL"]
    print("kit blender tier tests: %d/%d" % (len(RESULTS) - len(failed), len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
