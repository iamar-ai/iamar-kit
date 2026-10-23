"""Bake a high-poly model's detail into a normal map on its low-poly game mesh.

The kit's normal-map bake (recipe `bevel_normals`, kit/recipes/TECHNIQUES.md):
bevels, carving and fine relief of the detailed version are baked as a tangent-
space normal map onto the low-poly mesh, which then reads as carved for a fraction
of the triangles. The low mesh keeps its own UVs and materials; the map is wired
into every one of its materials and exported with tangents.

    iamar-world blender-run kit/blender/bake_normals.py -- high.glb low.glb out.glb [options]
    blender -b --factory-startup --python kit/blender/bake_normals.py -- high.glb low.glb out.glb ...

Options:
  --size N        normal map size in px (default 2048)
  --cage F        ray start distance outside the low mesh, as a fraction of the low
                  model's largest dimension (default 0.02)
  --distance F    longest ray, same unit (default 0.04): raise it if detail is missing,
                  lower it if far-away parts project onto the wrong surface
  --unwrap        give the low mesh fresh, non-overlapping UVs first (its materials
                  then need re-texturing; use for untextured low meshes)
  --smooth        shade the low mesh smooth before baking (default: keep its shading)
  --save-map PNG  also keep the normal map as a PNG file (it is always embedded in out.glb)
  --cpu           bake on the CPU even when a GPU is available

Both files must be at the same place and scale (export them from one Blender
scene). The low mesh needs UVs without overlaps (mirrored halves are fine if they
are offset; a shared UV island bakes one side's detail onto both).

Blender 4.2-4.5 (tested 4.5 LTS). No add-ons.
"""
import math
import os
import shutil
import sys
import tempfile
import time

import bpy

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402


def parse():
    p = K.make_parser("bake_normals.py", __doc__.split("\n\n")[0])
    p.add_argument("high")
    p.add_argument("low")
    p.add_argument("output")
    p.add_argument("--size", type=int, default=2048)
    p.add_argument("--cage", type=float, default=0.02)
    p.add_argument("--distance", type=float, default=0.04)
    p.add_argument("--unwrap", action="store_true")
    p.add_argument("--smooth", action="store_true")
    p.add_argument("--save-map", metavar="PNG")
    p.add_argument("--cpu", action="store_true")
    return K.parse_args(p)


def import_joined(path, name):
    obs = K.meshes(K.import_glb(path))
    if not obs:
        K.fail("no mesh in %s" % path)
    K.select_only(obs, obs[0])
    bpy.ops.object.make_single_user(object=True, obdata=True)
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def main():
    a = parse()
    t0 = time.time()
    K.reset()
    hi = import_joined(a.high, "kit_high")
    low = import_joined(a.low, "kit_low")
    # drop the empties the importer made for node hierarchies
    for o in [o for o in bpy.context.scene.objects if o.type == "EMPTY"]:
        bpy.data.objects.remove(o)
    K.setup_cycles(1, "cpu" if a.cpu else "auto")
    K.ensure_material(low)
    me = low.data
    if a.unwrap or not me.uv_layers:
        if not me.uv_layers:
            K.log("NOTE low mesh has no UVs: unwrapping")
            me.uv_layers.new(name="UVMap")
        K.select_only([low], low)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.01)
        bpy.ops.object.mode_set(mode="OBJECT")
    if a.smooth:
        K.select_only([low], low)
        bpy.ops.object.shade_smooth()

    img = bpy.data.images.new(low.name + "_normal", a.size, a.size, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color"
    img.generated_color = (0.5, 0.5, 1.0, 1.0)
    texnodes = []
    for m in low.data.materials:
        nt = m.node_tree
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = img
        nt.nodes.active = tx
        texnodes.append((m, tx))
    dim = max(low.dimensions) or 1.0
    bpy.ops.object.select_all(action="DESELECT")
    hi.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", use_selected_to_active=True,
                        cage_extrusion=dim * a.cage, max_ray_distance=dim * a.distance, margin=8)
    work = tempfile.mkdtemp(prefix="iamar_normals_")
    png = os.path.join(work, "normal.png")
    img.filepath_raw = png
    img.file_format = "PNG"
    img.save()
    # wire it as the normal map of every material and drop the high mesh
    for m, tx in texnodes:
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tx.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bpy.data.objects.remove(hi)
    try:
        K.export_glb(a.output, [low], colors=bool(low.data.color_attributes), tangents=True)
        if a.save_map:
            os.makedirs(os.path.dirname(os.path.abspath(a.save_map)) or ".", exist_ok=True)
            shutil.copy(png, a.save_map)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    K.log("BAKE_NORMALS_OK", a.output, "low tris", K.tris([low]), "%.1fs" % (time.time() - t0))


K.run(main)
