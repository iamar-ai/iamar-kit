"""Atlas a model: bake all its materials into one colour texture on one material.

Recipes `texture_sizes` and `merge_static`: props that share one material (one colour
atlas) cost one draw call where a material per part costs one each, and the browser
merges static pieces with the same material per 96 m area. This tool gives the model a
fresh, non-overlapping UV map, bakes every material's base colour (textures, colours and
vertex-colour tints, no lighting) into one image through it and exports the model with
that single material. Parts whose material uses alpha (cards, glass, invisible proxies)
keep their own material untouched.

    iamar-world blender-run kit/blender/atlas.py -- in.glb out.glb [options]
    iamar-world blender-run kit/blender/atlas.py -- a.glb b.glb c.glb --out out.glb ...

Options:
  --out FILE        output when several inputs are given (they are atlased together)
  --size N          atlas size in px (default 1024)
  --margin N        bake margin in px around UV islands (default 8)
  --keep-objects    keep the objects apart (one material shared); default joins them
  --roughness F     roughness of the atlas material (default 0.9: painted, never plastic)
  --save-atlas PNG  also keep the atlas as a PNG file (it is always embedded in the .glb)
  --cpu             bake on the CPU even when a GPU is available

Reports the atlas's texel density (px per metre of surface) against the kit's
256 px/m near-surface rule (kit/tools/paint_materials.py) and prints ATLAS_OK.
Normal maps are not carried over: bake them onto the atlased model afterwards with
kit/blender/bake_normals.py (it keeps the low mesh's UVs). Light bakes come last
(kit/blender/bake_unlit.py), see kit/blender/README.md for the order.

Blender 4.2-5.0 (tested 4.5 LTS and 5.0.1). No add-ons.
"""
import math
import os
import shutil
import sys
import tempfile

import bpy
import numpy as np

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402

TEXEL_RULE = 256.0     # px per metre, kit/tools/paint_materials.py (TILE_M 4 m at 1024 px)


def parse():
    p = K.make_parser("atlas.py", __doc__.split("\n\n")[0])
    p.add_argument("inputs", nargs="+")
    p.add_argument("--out")
    p.add_argument("--size", type=int, default=1024)
    p.add_argument("--margin", type=int, default=8)
    p.add_argument("--keep-objects", action="store_true")
    p.add_argument("--roughness", type=float, default=0.9)
    p.add_argument("--save-atlas", metavar="PNG")
    p.add_argument("--cpu", action="store_true")
    a = K.parse_args(p)
    if a.out is None:
        if len(a.inputs) != 2:
            K.fail("give in.glb out.glb, or several inputs and --out out.glb")
        a.out = a.inputs.pop()
    return a


def uses_alpha(mat):
    if mat is None or not mat.use_nodes:
        return False
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            al = n.inputs["Alpha"]
            if al.is_linked or al.default_value < 0.999:
                return True
    return getattr(mat, "surface_render_method", "") == "BLENDED"


def uvs_in_unit_square(obs, tol=1e-3):
    for ob in obs:
        d = ob.data.uv_layers["atlas"].data
        co = np.empty(len(d) * 2, dtype=np.float32)
        d.foreach_get("uv", co)
        if len(co) and (co.min() < -tol or co.max() > 1 + tol):
            return False
    return True


def main():
    a = parse()
    K.reset()
    obs = []
    for path in a.inputs:
        obs += K.meshes(K.import_glb(path))
    if not obs:
        K.fail("no mesh in %s" % ", ".join(a.inputs))
    K.select_only(obs, obs[0])
    bpy.ops.object.make_single_user(object=True, obdata=True)
    for ob in obs:
        K.ensure_material(ob)
    if not a.keep_objects and len(obs) > 1:
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        bpy.ops.object.join()
        obs = [bpy.context.view_layer.objects.active]
    mats_before = sorted({m.name for o in obs for m in o.data.materials if m})
    alpha_mats = {m.name for o in obs for m in o.data.materials if uses_alpha(m)}
    tris = K.tris(obs)

    # the atlas UV map: active for the bake, the old map stays the one textures read
    for ob in obs:
        me = ob.data
        render_uv = next((l for l in me.uv_layers if l.active_render), None)
        uv = me.uv_layers.new(name="atlas")
        me.uv_layers.active = uv
        if render_uv is not None:
            render_uv.active_render = True
    K.select_only(obs, obs[0])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    margin = (a.margin * 0.75) / a.size
    # Blender 5.0 packs a FRACTION margin of a few % far outside 0..1 (a black atlas);
    # ADD gives the same gap there
    method = "ADD" if bpy.app.version >= (5, 0, 0) else "FRACTION"
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin_method=method, margin=margin, shape_method="CONCAVE")
    except TypeError:
        bpy.ops.uv.pack_islands(margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    if not uvs_in_unit_square(obs):
        K.fail("atlas UVs do not fit in 0..1 after packing (Blender %s)" % bpy.app.version_string)

    sc = bpy.context.scene
    K.setup_cycles(4, "cpu" if a.cpu else "auto")
    sc.render.bake.margin_type = "EXTEND"
    img = bpy.data.images.new("atlas", a.size, a.size, alpha=False)   # 8-bit sRGB: albedo
    added = []
    for ob in obs:
        for slot in ob.material_slots:
            m = slot.material
            if m is None or m.name in alpha_mats or any(m is n.id_data for n, _ in added):
                continue
            n = m.node_tree.nodes.new("ShaderNodeTexImage")
            n.image = img
            m.node_tree.nodes.active = n
            added.append((n, m))
    if not added:
        K.fail("every material uses alpha: nothing to atlas")
    K.select_only(obs, obs[0])
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=a.margin, use_clear=True)
    for n, m in added:
        m.node_tree.nodes.remove(n)

    work = tempfile.mkdtemp(prefix="kit-atlas-")
    try:
        path = os.path.join(work, "atlas.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        if a.save_atlas:
            os.makedirs(os.path.dirname(os.path.abspath(a.save_atlas)) or ".", exist_ok=True)
            shutil.copy(path, a.save_atlas)
        final = bpy.data.images.load(path)
        final.pack()
        am = bpy.data.materials.new("atlas")
        am.use_nodes = True
        b = am.node_tree.nodes["Principled BSDF"]
        tx = am.node_tree.nodes.new("ShaderNodeTexImage")
        tx.image = final
        am.node_tree.links.new(tx.outputs[0], b.inputs["Base Color"])
        um = am.node_tree.nodes.new("ShaderNodeUVMap")   # explicit: alpha parts keep their own UVs
        um.uv_map = "atlas"
        am.node_tree.links.new(um.outputs[0], tx.inputs["Vector"])
        b.inputs["Roughness"].default_value = a.roughness
        b.inputs["Metallic"].default_value = 0.0

        area = uv_area = 0.0
        for ob in obs:
            me = ob.data
            keep = [m for m in me.materials if m and m.name in alpha_mats]
            # remap faces: alpha materials keep their slot, everything else uses the atlas
            old = [m.name if m else "" for m in me.materials]
            me.materials.clear()
            me.materials.append(am)
            for m in keep:
                me.materials.append(m)
            idx = {m.name: i + 1 for i, m in enumerate(keep)}
            uvd = me.uv_layers["atlas"].data
            for p in me.polygons:
                name = old[p.material_index] if p.material_index < len(old) else ""
                p.material_index = idx.get(name, 0)
                if p.material_index == 0:
                    area += p.area * (ob.matrix_world.to_scale().length / math.sqrt(3)) ** 2
                    cs = [uvd[li].uv.copy() for li in p.loop_indices]   # 5.0 reuses the Vector
                    uv_area += abs(sum(cs[i].x * cs[(i + 1) % len(cs)].y - cs[(i + 1) % len(cs)].x * cs[i].y
                                       for i in range(len(cs)))) / 2
            if not keep:
                for nm in [l.name for l in me.uv_layers if l.name != "atlas"]:
                    me.uv_layers.remove(me.uv_layers[nm])
                me.uv_layers["atlas"].active_render = True
            for nm in [c.name for c in me.color_attributes]:
                me.color_attributes.remove(me.color_attributes[nm])
        density = a.size * math.sqrt(uv_area / area) if area > 0 else 0.0
        K.export_glb(a.out, None, animations=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    verdict = "meets" if density >= TEXEL_RULE else "below"
    K.log("ATLAS_TEXEL_DENSITY %.0f px/m (%s the %d px/m near-surface rule; far props may be lower)"
          % (density, verdict, TEXEL_RULE))
    K.log("ATLAS_OK", a.out, "materials %d -> %d" % (len(mats_before), 1 + len(alpha_mats)),
          "tris %d" % tris, "size %d" % a.size)


K.run(main)
