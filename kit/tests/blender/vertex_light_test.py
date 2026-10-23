#!/usr/bin/env python3
"""Painted maps + baked light in one package (an internal task): five textured houses baked with
kit/blender/bake_vertex_light.py pass `materials texel`, `materials budget`, `lint` and
`audit` together.

Builds a world in a temporary folder: library maps at 512 px from `materials.py use
--size 512` (UV 1 unit = 2 m, so 256 px per metre), five gabled houses of different sizes in
Blender (plaster walls, slate roof, stone plinth, timber beam) UV-mapped to that density,
each baked with bake_vertex_light.py on the CPU, placed on a cobble square. Then checks
the baked .glb (COLOR_0, KHR_materials_unlit, the painted map still the base colour, sun
side brighter than shade side) and runs the four kit checks on the world.

Needs Blender 4.2+ (BLENDER=/path/to/blender, on PATH, or in ~/opt/blender-*); without it
every check is reported SKIPPED and the test exits 0. About 2-4 minutes on a 4-thread CPU.

    python3 kit/tests/blender/vertex_light_test.py [--keep DIR]
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
sys.path.insert(0, str(KIT / "tests"))
from blender_tools_test import Glb, find_blender  # noqa: E402

LAYERS = ["wall_plaster", "roof_slate", "dressed_stone", "timber"]
# (width x, depth z, wall height) in metres
HOUSES = [(6, 5, 4), (7, 5.5, 4.5), (5, 5, 3.6), (8, 6, 5), (6.5, 4.5, 4)]

GEN = r'''
import bpy, bmesh, json, math, sys
from mathutils import Vector
args = sys.argv[sys.argv.index("--") + 1:]
out, tex, houses = args[0], args[1], json.loads(args[2])
TILE = 2.0   # metres per UV unit: 512 px maps at 256 px/m
def mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(tex + "/" + name + ".jpg")
    m.node_tree.links.new(t.outputs[0], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.9
    return m
def planar_uv(ob):
    bm = bmesh.new(); bm.from_mesh(ob.data); uv = bm.loops.layers.uv.verify()
    up = Vector((0, 0, 1))
    for f in bm.faces:
        n = f.normal
        t = n.cross(up)
        t = Vector((1, 0, 0)) if t.length < 1e-4 else t.normalized()
        b = n.cross(t).normalized()
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co.dot(t) / TILE, lp.vert.co.dot(b) / TILE)
    bm.to_mesh(ob.data); bm.free()
def box(name, lo, hi, m, bottom=False):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector([lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3)])
    if not bottom:
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < -0.9], context="FACES_ONLY")
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(m); planar_uv(ob); return ob
def gable(name, w, d, h, rise, eave, m):
    # a closed triangular prism over the walls, ridge along x, overhanging by `eave`
    x0, x1 = -w / 2 - eave, w / 2 + eave
    y0, y1 = -d / 2 - eave, d / 2 + eave
    z0 = h - eave * rise / (d / 2)
    vs = [(x, y, z) for x in (x0, x1) for (y, z) in ((y0, z0), (0, h + rise), (y1, z0))]
    fs = [(0, 1, 4, 3), (1, 2, 5, 4), (0, 3, 5, 2), (0, 2, 1), (3, 4, 5)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(m); planar_uv(ob)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.to_mesh(me); bm.free()
    planar_uv(ob); return ob
for i, (w, d, h) in enumerate(houses):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    plaster, slate, stone, timber = mat("wall_plaster"), mat("roof_slate"), mat("dressed_stone"), mat("timber")
    obs = [box("walls", (-w / 2, -d / 2, 0.6), (w / 2, d / 2, h), plaster),
           box("plinth", (-w / 2 - 0.08, -d / 2 - 0.08, 0), (w / 2 + 0.08, d / 2 + 0.08, 0.6), stone),
           gable("roof", w, d, h, d * 0.45, 0.35, slate),
           box("beam", (-w / 2 - 0.04, -d / 2 - 0.14, h - 0.3), (w / 2 + 0.04, -d / 2 - 0.02, h - 0.05), timber, bottom=True)]
    for o in obs: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath="%s/house_%d_src.glb" % (out, i), export_format="GLB",
                              use_selection=True, export_apply=True, export_yup=True)
print("GEN_OK")
'''

RESULTS: list[tuple[str, str, str]] = []
NAMES = ["generate", "bake", "colour_0", "unlit", "painted_map_kept", "sun_side_brighter", "triangles",
         "texel", "budget", "lint", "audit"]


def check(name, cond, detail=""):
    RESULTS.append((name, "PASS" if cond else "FAIL", detail))
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""), flush=True)


def py(*args) -> tuple[int, str]:
    p = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def manifest(world: Path):
    m = {"format": "iamar-world", "format_version": 0, "id": "vertex_light_houses", "name": "Vertex-light houses",
         "description": "Five painted, light-baked houses (kit test, an internal task)", "author": {"name": "iamar kit"},
         "version": "1.0.0", "api_version": "0.1", "scene": "scene.json",
         "budgets": {"triangles": 150000, "objects": 64, "texture_size": 1024, "texture_bytes": 67108864,
                     "lights": 4, "package_bytes": 33554432, "audio_bytes": 0, "script_bytes": 0},
         "features": ["sky", "objects", "primitives"], "license": "CC0-1.0", "credits": []}
    (world / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")


def scene(world: Path):
    objs = []
    x = -22.0
    for i, (w, d, h) in enumerate(HOUSES):
        x += w / 2
        objs.append({"id": "house_%d" % i, "asset": "assets/house_%d.glb" % i, "position": [x, 0, 0],
                     "collision": "box"})
        x += w / 2 + 4
    s = {"format": "iamar-scene", "format_version": 0,
         "primitives": [{"id": "ground", "shape": "box", "size": [64, 0.5, 40], "position": [0, -0.25, 0],
                         "texture": "textures/materials/cobble.jpg", "uv_scale": 2, "collision": "box"}],
         "spawn_points": [{"id": "default", "position": [0, 0.1, 14], "yaw": 0}], "objects": objs}
    (world / "scene.json").write_text(json.dumps(s, indent=1) + "\n")


def mean_colour(g: Glb, prim) -> list[float]:
    cols = g.accessor(prim["attributes"]["COLOR_0"])
    return [sum(c[k] for c in cols) / max(1, len(cols)) for k in range(3)]


def facing_light(g: Glb, prim) -> dict:
    """Mean light of vertices whose normal faces +X (towards the default sun) vs -X."""
    ns = g.accessor(prim["attributes"]["NORMAL"])
    cs = g.accessor(prim["attributes"]["COLOR_0"])
    out = {}
    for key, sgn in (("sun", 1), ("shade", -1)):
        v = [sum(c[:3]) / 3 for n, c in zip(ns, cs) if n[0] * sgn > 0.9]
        out[key] = sum(v) / len(v) if v else None
    return out


def main() -> int:
    keep = Path(sys.argv[sys.argv.index("--keep") + 1]).resolve() if "--keep" in sys.argv else None
    blender = find_blender()
    if blender is None:
        for n in NAMES:
            print("SKIPPED " + n + "  (no Blender: set BLENDER=/path/to/blender)")
        print("kit vertex light tests: skipped (no Blender)")
        return 0
    print("BLENDER", blender, flush=True)
    w = Path(keep or tempfile.mkdtemp(prefix="iamar-kit-vlight-"))
    world = w / "world"
    try:
        (world / "assets").mkdir(parents=True, exist_ok=True)
        manifest(world)
        rc, log = py(KIT / "style/materials/materials.py", "use", world, "--profile", "iamar", "--size", "512",
                     "--only", ",".join(LAYERS + ["cobble"]))
        tex = world / "textures" / "materials"
        p = subprocess.run([blender, "-b", "--factory-startup", "--python-expr", GEN, "--", str(w), str(tex),
                            json.dumps(HOUSES)], capture_output=True, text=True, timeout=600)
        ok = rc == 0 and p.returncode == 0 and "GEN_OK" in p.stdout and (w / "house_4_src.glb").is_file()
        check("generate", ok, "" if ok else (log + p.stdout[-1500:] + p.stderr[-1500:]))
        if not ok:
            return 1
        scene(world)

        baked, logs = 0, []
        for i in range(len(HOUSES)):
            q = subprocess.run([blender, "-b", "--factory-startup", "--python", str(KIT / "blender/bake_vertex_light.py"),
                                "--", str(w / ("house_%d_src.glb" % i)), str(world / "assets" / ("house_%d.glb" % i)),
                                "8", "--cpu", "--sun", "1,0.8,0.2"], capture_output=True, text=True, timeout=900)
            good = q.returncode == 0 and "BAKE_VERTEX_LIGHT_OK" in q.stdout
            baked += good
            logs.append(q.stdout[-1200:] + q.stderr[-800:] if not good else
                        [ln for ln in q.stdout.splitlines() if ln.startswith(("GRID", "LIGHT"))])
        check("bake", baked == len(HOUSES), "%d/%d baked; %s" % (baked, len(HOUSES), logs[0]))
        if baked != len(HOUSES):
            print("\n".join(map(str, logs)))
            return 1

        g = Glb(world / "assets" / "house_0.glb")
        prims = list(g.prims())
        mats = g.js.get("materials", [])
        check("colour_0", all("COLOR_0" in pr["attributes"] for pr in prims), "%d primitives" % len(prims))
        check("unlit", bool(mats) and all("KHR_materials_unlit" in m.get("extensions", {}) for m in mats),
              ", ".join(m.get("name", "?") for m in mats))
        imgs = g.js.get("images", [])
        check("painted_map_kept", len(imgs) == len(LAYERS) and all(
            "baseColorTexture" in m.get("pbrMetallicRoughness", {}) for m in mats),
              "%d embedded images, every material keeps its base colour map" % len(imgs))
        walls = next((pr for pr in prims if mats[pr.get("material", 0)].get("name", "").startswith("wall_plaster")), prims[0])
        fl = facing_light(g, walls)
        check("sun_side_brighter", fl["sun"] is not None and fl["shade"] is not None and fl["sun"] > fl["shade"] * 1.3,
              "walls facing the sun %.3f, facing away %.3f" % (fl["sun"] or -1, fl["shade"] or -1))
        tris = [sum(len(Glb(world / "assets" / ("house_%d.glb" % i)).accessor(pr["indices"])) // 3
                    for pr in Glb(world / "assets" / ("house_%d.glb" % i)).prims()) for i in range(len(HOUSES))]
        check("triangles", max(tris) <= 3000, "per house %s (building budget 3000)" % tris)

        rc, log = py(KIT / "style/materials/materials.py", "texel", world)
        check("texel", rc == 0, log.strip().splitlines()[-1] if log.strip() else "")
        if rc:
            print(log)
        rc, log = py(KIT / "style/materials/materials.py", "budget", world, "--profile", "iamar")
        check("budget", rc == 0, " | ".join(log.strip().splitlines()[-2:]))
        if rc:
            print(log)
        rc, log = py(KIT / "lint/style_lint.py", world, "--style", "iamar")
        check("lint", rc == 0, log.strip().splitlines()[-1] if log.strip() else "")
        if rc:
            print(log)
        rc, log = py(KIT / "audit/audit.py", "all", world, "--quiet")
        check("audit", rc == 0, " | ".join(ln for ln in log.splitlines() if ln.startswith("RESULT"))[:400])
        if rc:
            print(log)
    finally:
        if keep is None:
            shutil.rmtree(w, ignore_errors=True)
    bad = [r for r in RESULTS if r[1] != "PASS"]
    print("kit vertex light tests: %d passed, %d failed" % (len(RESULTS) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
