"""Starter Blender build script for an iamar world (copy it into your world as
tools/build.py and change it). Run it headless through the kit:

    iamar-world blender-run tools/build.py -- <world folder>

It builds a small cottage and a tree in metres (+Z up in Blender; the glTF exporter
writes +Y up, which is what iamar expects), gives every object a simple material,
applies modifiers, checks a triangle budget, and exports one .glb per model into
<world>/assets/. Keep the script with the world so it can be rebuilt and changed.

Parts are combined with an exact boolean union (`join` below), never a plain join:
parts that touch exactly would otherwise weld into non-manifold edges and fail the
closure audit (kit/blender/README.md, build order step 1).
"""
import math
import os
import sys

import bpy
import bmesh

BUDGET_TRIS = {"cottage": 6000, "tree": 3000}   # per model; raise only with a reason


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, rgb, rough=0.8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    return m


def box(name, size, loc, mat, bevel=0.03, rot=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    # bake scale and rotation into the mesh, so joining and exporting keep them
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if bevel > 0:
        # small bevels catch the light: blocky edges read as carved
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    o.data.materials.append(mat)
    return o


def join(objs, name):
    """One closed model from overlapping or touching parts: an exact boolean union.

    A plain `bpy.ops.object.join()` keeps every part as its own shell. Where two parts
    touch exactly (a dome standing on its drum, a box stacked on a box, strips meeting
    edge to edge) their vertices sit at the same places, and weld.py (build order step 2)
    merges them into edges shared by 3-4 faces: closure_audit.py then fails with
    non-manifold edges. The union removes the faces between the parts instead, so
    touching, stacked and sunk-in parts all come out as one closed surface. Materials
    of every part are kept (material_mode TRANSFER).
    """
    for o in objs:
        bpy.context.view_layer.objects.active = o
        for mod in list(o.modifiers):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    base = objs[0]
    for o in objs[1:]:
        mod = base.modifiers.new("union", "BOOLEAN")
        mod.operation = "UNION"
        mod.solver = "EXACT"
        mod.object = o
        mod.material_mode = "TRANSFER"
        bpy.context.view_layer.objects.active = base
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(o, do_unlink=True)
    base.name = name
    bpy.ops.object.select_all(action="DESELECT")
    return base


def tris(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    n = sum(len(f.verts) - 2 for f in bm.faces)
    bm.free()
    return n


def export(o, path):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True)


def cottage():
    wall = material("wall", (0.86, 0.80, 0.68))
    roof = material("roof", (0.55, 0.22, 0.16))
    wood = material("wood", (0.40, 0.26, 0.15))
    parts = [box("walls", (5.0, 4.0, 2.6), (0, 0, 1.3), wall)]
    # gabled roof: two slanted slabs
    for s in (-1, 1):
        parts.append(box("roof", (5.6, 2.6, 0.18), (0, s * 1.05, 3.25), roof, 0.02, (math.radians(-s * 35), 0, 0)))
    parts.append(box("door", (0.9, 0.12, 1.9), (0, -2.02, 0.95), wood, 0.01))
    return join(parts, "cottage")


def tree():
    bark = material("bark", (0.36, 0.25, 0.16))
    leaf = material("leaf", (0.28, 0.52, 0.22), 0.9)
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.22, depth=3.0, location=(0, 0, 1.5))
    trunk = bpy.context.active_object
    trunk.data.materials.append(bark)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.6, location=(0, 0, 3.6))
    crown = bpy.context.active_object
    crown.data.materials.append(leaf)
    return join([trunk, crown], "tree")


def main(world):
    out = os.path.join(world, "assets")
    os.makedirs(out, exist_ok=True)
    for name, build in (("cottage", cottage), ("tree", tree)):
        clear()
        o = build()
        n = tris(o)
        if n > BUDGET_TRIS[name]:
            sys.exit("%s has %d triangles, more than its budget of %d" % (name, n, BUDGET_TRIS[name]))
        path = os.path.join(out, name + ".glb")
        export(o, path)
        print("BUILT %s %d triangles -> %s" % (name, n, path))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not args:
        sys.exit("usage: iamar-world blender-run tools/build.py -- <world folder>")
    main(args[0])
