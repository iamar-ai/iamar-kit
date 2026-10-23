"""Bake ambient occlusion into vertex colours (COLOR_0) of any glTF model.

The kit's vertex AO bake (recipe `bake_ao_vertex`, kit/recipes/TECHNIQUES.md).
Soft contact darkness in creases, under overhangs and where parts meet, stored per
vertex, so characters, creatures and small props sit in the world without a
lightmap. Works on skinned and animated models (the bake uses the rest pose and
the export keeps skins and animations). The browser multiplies COLOR_0 into the
base colour (docs/WORLD_FORMAT.md section 5), and the materials stay ordinary lit
materials.

    iamar-world blender-run kit/blender/bake_vertex_ao.py -- in.glb out.glb [options]
    blender -b --factory-startup --python kit/blender/bake_vertex_ao.py -- in.glb out.glb ...

Options:
  --distance M   how far occluders count, in metres (default 0.5; about a tenth of
                 the model's size is a good start: 0.1 for a chicken, 1-2 for a house)
  --strength S   0..1, how much of the darkness to apply (default 1.0)
  --floor F      lightest allowed darkness, 0..1 (default 0.25: nothing goes black)
  --local        each mesh occludes only itself (parts of one model do not shadow
                 each other; use for models whose parts move apart)
  --max-edge M   split every edge longer than M metres before baking (default 0: off).
                 Use it on low-poly buildings: a wall face with vertices only at its
                 corners gets the corner darkness (where roof, bands and ground meet)
                 spread over the whole face. 2 m suits a house (about twice the
                 triangles; the log prints how many), so check the tier budget after
  --occluder G,m00,m01,m02,m03,m10,...,m23
                 (repeatable) another model that shadows this one but is not baked or
                 exported: the houses beside a street, the quay walls around a harbour
                 floor. The 12 numbers are the row-major 3 x 4 glTF (+Y up) matrix that
                 puts G into this model's frame. Do not write them by hand:
                 `kit/style/lighting/lighting.py ao-args --world W --object ID` prints one
                 per neighbour from scene.json. Not with --local.
  --samples N    Cycles samples (default 64)
  --cpu          bake on the CPU even when a GPU is available

The bake is time-independent: no sun, no sky colour, only how much of the sky each
vertex sees within --distance. The materials stay lit, so the browser's live sun,
clock and shadows still light the model, and the AO keeps the contact darkness at
every hour and on the low tier, which draws no shadows. That is the bake for a world
whose clock runs (`day_length_minutes` > 0; recipe `bake_ao_vertex`, kit/style/
lighting/README.md "A running clock"). The output's asset.extras gets
`iamar_bake: {"kind": "sky_ao", ...}`, which `iamar-world audit dark-bake` reports.

Existing vertex colours are kept and multiplied by the AO. More vertices give finer
AO: the result is only as detailed as the mesh. Flattened models (flatten.py,
bake_unlit-style colour in COLOR_0) keep their colour in COLOR_0 too, so the AO
darkens the colour itself: on a low-poly building the default --floor 0.25 took
plaster from 0.85 to under 0.6 on most of the wall. For buildings use --max-edge,
and a soft --floor 0.6 --strength 0.7, or no AO at all (live sun and shadows).

Blender 4.2-4.5 (tested 4.5 LTS). No add-ons.
"""
import os
import sys
import time

import bmesh
import bpy

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402

AO_ATTR = "kit_ao"


def parse():
    p = K.make_parser("bake_vertex_ao.py", __doc__.split("\n\n")[0])
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--distance", type=float, default=0.5)
    p.add_argument("--strength", type=float, default=1.0)
    p.add_argument("--floor", type=float, default=0.25)
    p.add_argument("--local", action="store_true")
    p.add_argument("--max-edge", type=float, default=0.0)
    p.add_argument("--occluder", action="append", default=[])
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--cpu", action="store_true")
    a = K.parse_args(p)
    if a.occluder and a.local:
        K.fail("--occluder needs the whole scene to occlude: not with --local")
    return a


def parse_occluder(spec):
    """'path,m00,...,m23' -> (path, Blender 4x4 matrix). The matrix is in glTF space
    (+Y up); the importer turns glTF (x, y, z) into Blender (x, -z, y), so the same
    placement in Blender is C @ M @ C^-1."""
    from mathutils import Matrix
    parts = spec.rsplit(",", 12)
    if len(parts) != 13:
        K.fail("--occluder wants a path and 12 numbers, got %r" % spec)
    try:
        m = [float(v) for v in parts[1:]]
    except ValueError:
        K.fail("--occluder: not numbers in %r" % spec)
    mg = Matrix((m[0:4], m[4:8], m[8:12], (0.0, 0.0, 0.0, 1.0)))
    c = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    return parts[0], c @ mg @ c.inverted()


def ao_material(distance, local):
    """An emission material showing the AO node, baked with EMIT: unlike the AO bake
    pass it can be limited to the object itself (--local)."""
    m = bpy.data.materials.new("kit_ao_bake")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = distance
    ao.only_local = local
    ao.samples = 16
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(ao.outputs["AO"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def split_long_edges(ob, max_edge):
    """Triangulate and halve every edge longer than max_edge (object space scaled to
    world), so big faces get vertices inside them. Colours, UVs and skin weights are
    interpolated by bmesh. Returns (triangles before, after)."""
    me = ob.data
    if me.shape_keys:
        K.log("MAX_EDGE_SKIP", ob.name, "has shape keys")
        return None
    sc = max(abs(v) for v in ob.matrix_world.to_scale()) or 1.0
    bm = bmesh.new()
    bm.from_mesh(me)
    before = sum(len(f.verts) - 2 for f in bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for _ in range(12):
        long = [e for e in bm.edges if e.calc_length() * sc > max_edge]
        if not long:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    after = len(bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return before, after


def main():
    a = parse()
    t0 = time.time()
    K.reset()
    K.import_glb(a.input)
    sc = bpy.context.scene
    K.setup_cycles(a.samples, "cpu" if a.cpu else "auto")
    sc.render.bake.target = "VERTEX_COLORS"
    sc.render.bake.use_clear = True
    # hidden meshes (bone shapes, helpers) are exported untouched
    obs = [o for o in K.meshes() if o.visible_get()]
    if not obs:
        K.fail("no mesh in %s" % a.input)
    # neighbours: in the scene while baking (the AO node traces all of it), never baked or exported
    occ = []
    for spec in a.occluder:
        path, mb = parse_occluder(spec)
        new = K.import_glb(path)
        for o in new:
            if o.parent is None:
                o.matrix_world = mb @ o.matrix_world
        occ += new
        K.log("OCCLUDER", path, "meshes", len(K.meshes(new)))
    bpy.context.view_layer.update()
    mat = ao_material(a.distance, a.local)
    if a.max_edge > 0:
        done = set()
        for ob in obs:
            if ob.data.name in done:
                continue
            done.add(ob.data.name)
            r = split_long_edges(ob, a.max_edge)
            if r:
                K.log("MAX_EDGE", ob.name, "triangles %d -> %d" % r)

    # the rest pose: armature deformation off while baking
    for ob in obs:
        for md in ob.modifiers:
            if md.type == "ARMATURE":
                md.show_render = False
    # bake every mesh with the AO material in place of its own (the whole model
    # occludes unless --local), then restore the materials
    saved = {}
    for ob in obs:
        if ob.data.users > 1:
            ob.data = ob.data.copy()   # linked copies sit in different places
        # swap slot by slot, so every face keeps its material index
        saved[ob.name] = list(ob.data.materials)
        if not ob.data.materials:
            ob.data.materials.append(mat)
        for i in range(len(ob.data.materials)):
            ob.data.materials[i] = mat
    stats = []
    for ob in obs:
        me = ob.data
        prev_active = me.color_attributes.active_color
        prev_name = prev_active.name if prev_active is not None else None
        ca = me.color_attributes.new(AO_ATTR, "FLOAT_COLOR", "POINT")
        me.color_attributes.active_color = ca
        K.select_only([ob], ob)
        bpy.ops.object.bake(type="EMIT")
        ca = me.color_attributes[AO_ATTR]
        vals = [0.0] * (4 * len(ca.data))
        ca.data.foreach_get("color", vals)
        ao = [min(1.0, max(a.floor, 1.0 - a.strength * (1.0 - vals[i * 4]))) for i in range(len(ca.data))]
        stats += ao
        target = me.color_attributes.get(prev_name) if prev_name else None
        if target is None:
            # no colours yet: the AO becomes COLOR_0 (grey, alpha 1)
            ca.data.foreach_set("color", [c for v in ao for c in (v, v, v, 1.0)])
            ca.name = "Color"
            target = ca
        else:
            # multiply into the existing colours (any domain)
            cols = [0.0] * (4 * len(target.data))
            target.data.foreach_get("color", cols)
            if target.domain == "POINT":
                per = ao
            else:   # face corners
                per = [ao[lp.vertex_index] for lp in me.loops]
            for i, v in enumerate(per):
                for k in range(3):
                    cols[i * 4 + k] *= v
            target.data.foreach_set("color", cols)
            me.color_attributes.remove(me.color_attributes[AO_ATTR])
            target = me.color_attributes[prev_name]
        me.color_attributes.active_color = target
        try:
            me.color_attributes.render_color_index = me.color_attributes.active_color_index
        except AttributeError:
            pass
        if saved[ob.name]:
            for i, m in enumerate(saved[ob.name]):
                me.materials[i] = m
        else:
            me.materials.clear()
        K.log("AO_BAKED", ob.name, "vertices", len(ao), "min %.3f mean %.3f" % (min(ao), sum(ao) / len(ao)))
    for ob in obs:
        for md in ob.modifiers:
            if md.type == "ARMATURE":
                md.show_render = True
    bpy.data.materials.remove(mat)
    for o in occ:
        bpy.data.objects.remove(o, do_unlink=True)
    K.export_glb(a.output, None, colors=True, animations=True)
    K.patch_asset_extras(a.output, {"iamar_bake": {
        "kind": "sky_ao", "tool": "kit/blender/bake_vertex_ao.py", "distance": a.distance,
        "strength": a.strength, "floor": a.floor, "local": bool(a.local), "occluders": len(a.occluder)}})
    K.log("BAKE_VERTEX_AO_OK", a.output, "meshes", len(obs), "vertices", len(stats),
          "min %.3f mean %.3f" % (min(stats), sum(stats) / len(stats)), "%.1fs" % (time.time() - t0))


K.run(main)
