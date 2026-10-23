#!/usr/bin/env python3
"""Mixed meshes in kit/blender/bake_vertex_light.py (gap G15, an internal task): one mesh with a
glowing lamp-glass material and a plain wall material must bake the wall part and keep only
the glass live-lit, instead of failing with "nothing to bake". A second object that shares the
same mesh (a glTF instance) must keep its wall too: splitting shared data cut it (review of f9f593b).

    python3 kit/tests/blender/bake_vertex_light_mixed_test.py

Needs Blender 4.2+ (BLENDER=/path/to/blender or on PATH); without it the test is SKIPPED, exit 0.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(KIT / "tests"))
from blender_tools_test import Glb, find_blender  # noqa: E402

GEN = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
ob = bpy.context.object
bpy.ops.mesh.primitive_cube_add(size=0.6, location=(0, 0, 2.3))
top = bpy.context.object
bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True); top.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.object.join()
wall = bpy.data.materials.new("wall"); wall.use_nodes = True
glass = bpy.data.materials.new("glass"); glass.use_nodes = True
b = glass.node_tree.nodes["Principled BSDF"]
b.inputs["Emission Color"].default_value = (1, 0.8, 0.3, 1); b.inputs["Emission Strength"].default_value = 3.0
ob.data.materials.append(wall); ob.data.materials.append(glass)
for p in ob.data.polygons:
    p.material_index = 1 if p.center.z > 1.0 else 0
ob2 = bpy.data.objects.new("lamp2", ob.data); bpy.context.collection.objects.link(ob2); ob2.location = (4, 0, 0)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
print("GEN_OK")
'''


def main() -> int:
    blender = find_blender()
    if blender is None:
        print("SKIPPED mixed_mesh_bake  (no Blender: set BLENDER=/path/to/blender)")
        return 0
    with tempfile.TemporaryDirectory(prefix="iamar-kit-mixed-") as d:
        src, dst = Path(d) / "lamp.glb", Path(d) / "lamp_baked.glb"
        p = subprocess.run([blender, "-b", "--factory-startup", "--python-expr", GEN, "--", str(src)],
                           capture_output=True, text=True, timeout=300)
        if "GEN_OK" not in p.stdout:
            print("FAIL generate\n" + p.stdout[-1500:] + p.stderr[-1500:])
            return 1
        q = subprocess.run([blender, "-b", "--factory-startup", "--python", str(KIT / "blender/bake_vertex_light.py"),
                            "--", str(src), str(dst), "8", "--cpu"], capture_output=True, text=True, timeout=600)
        good = q.returncode == 0 and "BAKE_VERTEX_LIGHT_OK" in q.stdout and "SPLIT" in q.stdout
        print(("PASS" if good else "FAIL") + " bake of a mixed glowing / plain mesh succeeds")
        if not good:
            print(q.stdout[-1500:] + q.stderr[-1000:])
            return 1
        g = Glb(dst)
        prims = list(g.prims())
        mats = g.js.get("materials", [])
        has = lambda pr: "COLOR_0" in pr["attributes"]  # noqa: E731
        name = lambda pr: mats[pr.get("material", 0)].get("name", "")  # noqa: E731
        wall = [pr for pr in prims if name(pr).startswith("wall")]
        glass = [pr for pr in prims if name(pr).startswith("glass")]
        checks = [("wall part baked (COLOR_0)", bool(wall) and all(map(has, wall))),
                  ("both instances keep their wall (shared mesh split per object)", len(wall) == 2),
                  ("glass part kept", bool(glass)),
                  ("glass keeps its glow (not unlit)", all("KHR_materials_unlit" not in m.get("extensions", {})
                                                          for m in mats if m.get("name", "").startswith("glass")))]
        bad = 0
        for n, ok in checks:
            print(("PASS " if ok else "FAIL ") + n)
            bad += not ok
        print("kit mixed-mesh bake test: %d failed" % bad)
        return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
