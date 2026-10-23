"""Bake sky, sun and lamps into vertex colours and keep the painted maps: painted detail + baked light.

The kit's route for painted architecture (recipe `bake_vertex_light`, an internal task). A glTF
material has one colour texture and no lightmap slot the browser reads, so
`bake_unlit.py` must replace the painted map by one baked colour x light texture per
mesh (10-40 px/m: blurry, and it fails `materials texel`). This bake keeps every
material's own Base Color map and UVs (the shared library maps at 256 px/m) and stores
the light in COLOR_0 instead. The materials are exported unlit (KHR_materials_unlit);
the browser draws base colour x map x COLOR_0 as-is (docs/WORLD_FORMAT.md section 5), so
`materials texel` passes and the texture memory is only the painted maps.

    iamar-world blender-run kit/blender/bake_vertex_light.py -- in.glb out.glb [samples] [options]
    blender -b --factory-startup --python kit/blender/bake_vertex_light.py -- in.glb out.glb ...

What it does:
  1. imports in.glb; meshes that are skinned, have shape keys, are animated, use alpha
     or glow (emission) stay as they are (live-lit); a mesh that mixes glowing / alpha
     materials with plain ones is first split by material, so only the glowing part stays
     live and the rest bakes;
  2. turns double-sided faces whose normal points into the model (a cloak facing the body,
     flipped triangles of a generated mesh) to their open side: Cycles bakes only the side
     the normal points to, and the browser draws a double-sided face from both sides with
     one COLOR_0 (--no-orient keeps every normal);
  3. cuts the static meshes on a --grid (metres) lattice, so the light has a vertex at
     least every --grid metres (a 4-vertex wall would show one smeared gradient), and
     splits hard edges (> --sharp degrees) so a sunlit wall does not bleed into the
     shaded one around the corner;
  4. bakes light (direct + indirect, no albedo) per vertex with Cycles (GPU when found);
  5. COLOR_0 = existing vertex colour x shoulder(light x exposure), linear, at most 1;
  6. exports out.glb with the original materials marked unlit; lights are baked and not
     exported (put live lamps in scene.json).

Lighting options are the same as bake_unlit.py (`lighting.py bake-args <preset>` prints
them). Cost: triangles grow with the grid. A 6 x 5 m house is about 3,000 triangles
at LOD0 with a 0.5 m grid and 1,000 at the default 1 m (8 x 6 m: 4,400 and 1,400). LODs: make them from the
unbaked model (kit/blender/lods.py) and bake each one, LOD1 with --grid 2 and LOD2 with
--grid 0; never decimate a baked model (planar decimation removes the grid, and with it
the light: a 1,400-triangle baked house fell to 44 triangles lit only at its corners,
an internal task). Shadows are as sharp as the grid: a
lamp's pool of light or a doorway shadow smaller than the grid is lost. Use
bake_unlit.py where the light must be sharper than the painted detail.

Blender 4.2-4.5 (tested 4.5 LTS). No add-ons.
"""
import math
import os
import sys
import time

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402

LIGHT_ATTR = "kit_light"


def parse():
    p = K.make_parser("bake_vertex_light.py", __doc__.split("\n\n")[0])
    p.add_argument("input", help="model or scene to bake (.glb/.gltf)")
    p.add_argument("output", help="baked model to write (.glb)")
    p.add_argument("samples", nargs="?", type=int, default=64, help="Cycles samples (default 64)")
    p.add_argument("--grid", type=float, default=1.0, help="light resolution: a vertex at least every M metres (default 1.0; 0 = no cuts)")
    p.add_argument("--sharp", type=float, default=30.0, help="split edges sharper than this many degrees (default 30)")
    p.add_argument("--sky", default="0.85,0.9,1.0", help="sky colour r,g,b (linear, default 0.85,0.9,1.0)")
    p.add_argument("--sky-strength", type=float, default=0.5, help="sky brightness (default 0.5; 0 = no sky)")
    p.add_argument("--sun", default="0.4,0.8,0.35", help="direction towards the sun x,y,z in glTF axes (+Y up)")
    p.add_argument("--sun-strength", type=float, default=3.0, help="sun brightness (default 3.0)")
    p.add_argument("--sun-color", default="1.0,0.95,0.85", help="sun colour r,g,b (default warm white)")
    p.add_argument("--sun-angle", type=float, default=1.5, help="sun disc size in degrees: shadow softness (default 1.5)")
    p.add_argument("--no-sun", action="store_true", help="no sun (interiors lit by their own lamps and the sky)")
    p.add_argument("--exposure", type=float, default=1.0, help="light multiplier before the shoulder (default 1.0)")
    p.add_argument("--cpu", action="store_true", help="bake on the CPU even when a GPU is available")
    p.add_argument("--lamp", action="append", default=[], metavar="X,Y,Z[,R,G,B[,W]]",
                   help="add a point lamp to the bake (glTF axes; colour linear, default warm 1,0.62,0.25; "
                        "W watts, default 60). Repeat per lamp")
    p.add_argument("--no-orient", action="store_true",
                   help="keep the normals: do not turn inward-facing double-sided faces to their open side")
    p.add_argument("--lamp-radius", type=float, default=0.1, help="lamp size in m: shadow softness (default 0.1)")
    return K.parse_args(p)


def triple(s):
    v = [float(t) for t in s.split(",")]
    if len(v) != 3:
        K.fail("expected three comma-separated numbers, got %r" % s)
    return v


def principled(mat):
    if mat is None or not mat.use_nodes:
        return None
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def why_live(ob):
    """'' when the mesh can be baked, else why it stays live-lit."""
    if any(m.type == "ARMATURE" for m in ob.modifiers) or ob.parent_type == "BONE":
        return "skinned"
    if ob.data.shape_keys is not None:
        return "shape keys"
    o = ob
    while o is not None:
        if o.animation_data and o.animation_data.action:
            return "animated"
        o = o.parent
    for m in ob.data.materials:
        why = why_live_material(m)
        if why:
            return why
    return ""


def why_live_material(m):
    """'' when the material can be baked, else why its faces stay live-lit."""
    b = principled(m)
    if b is None:
        return ""
    a = b.inputs["Alpha"]
    if a.is_linked or a.default_value < 0.999:
        return "alpha material"
    es = b.inputs.get("Emission Strength")
    ec = b.inputs.get("Emission Color") or b.inputs.get("Emission")
    if es is not None and ec is not None and es.default_value > 0 and \
            (ec.is_linked or max(ec.default_value[:3]) > 0):
        return "emissive material (unlit drops the glow)"
    return ""


def split_mixed(obs):
    """A mesh with some glowing / alpha materials and some plain ones is split by material, so
    the plain parts bake and only the glowing parts stay live-lit (kit gap G15)."""
    n = 0
    for ob in obs:
        mats = [m for m in ob.data.materials if m is not None]
        if len(mats) < 2 or ob.data.shape_keys is not None or any(m.type == "ARMATURE" for m in ob.modifiers):
            continue
        flags = {bool(why_live_material(m)) for m in mats}
        if flags != {True, False}:
            continue
        if ob.data.users > 1:   # an instance: separating shared data would cut the others too
            ob.data = ob.data.copy()
        K.select_only([ob], ob)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="MATERIAL")
        bpy.ops.object.mode_set(mode="OBJECT")
        n += 1
        K.log("SPLIT", ob.name, "by material: glowing / alpha parts stay live, the rest bakes")
    return n


def lights(a, sc):
    world = bpy.data.worlds.new("kit_sky")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*triple(a.sky), 1.0)
    bg.inputs[1].default_value = a.sky_strength
    sc.world = world
    if not a.no_sun and a.sun_strength > 0:
        sun = bpy.data.objects.new("kit_sun", bpy.data.lights.new("kit_sun", "SUN"))
        sun.data.energy = a.sun_strength
        sun.data.color = triple(a.sun_color)
        sun.data.angle = math.radians(a.sun_angle)
        sc.collection.objects.link(sun)
        to_sun = Vector(K.gltf_to_blender(triple(a.sun))).normalized()
        sun.rotation_euler = Vector((0.0, 0.0, 1.0)).rotation_difference(to_sun).to_euler()
    for i, spec in enumerate(a.lamp):
        try:
            v = [float(t) for t in spec.split(",")]
        except ValueError:
            v = []
        if len(v) not in (3, 6, 7):
            K.fail("--lamp wants X,Y,Z or X,Y,Z,R,G,B or X,Y,Z,R,G,B,W, got %r" % spec)
        lamp = bpy.data.objects.new("kit_lamp_%d" % i, bpy.data.lights.new("kit_lamp_%d" % i, "POINT"))
        lamp.data.color = v[3:6] if len(v) >= 6 else (1.0, 0.62, 0.25)
        lamp.data.energy = v[6] if len(v) == 7 else 60.0
        lamp.data.shadow_soft_size = a.lamp_radius
        lamp.location = Vector(K.gltf_to_blender(v[:3]))
        sc.collection.objects.link(lamp)


def cut(ob, grid, sharp_deg):
    """Slice the mesh on axis planes every `grid` metres and split hard edges.
    UVs and existing colours are interpolated by the cuts, so the painted maps do not move."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    if grid > 0:
        lo = [min(v.co[i] for v in bm.verts) for i in range(3)]
        hi = [max(v.co[i] for v in bm.verts) for i in range(3)]
        for axis in range(3):
            n = int(math.floor((hi[axis] - lo[axis]) / grid))
            no = Vector((0.0, 0.0, 0.0))
            no[axis] = 1.0
            for k in range(1, n + 1):
                co = Vector((0.0, 0.0, 0.0))
                co[axis] = lo[axis] + k * grid
                if co[axis] >= hi[axis] - 1e-4:
                    continue
                geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
                bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=co, plane_no=no)
    bm.edges.ensure_lookup_table()
    lim = math.radians(sharp_deg)
    hard = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim]
    if hard:
        bmesh.ops.split_edges(bm, edges=hard)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def hemisphere(n=16):
    """n fixed directions spread over the +Z hemisphere (Fibonacci), so runs repeat exactly."""
    out = []
    for i in range(n):
        z = 1.0 - (i + 0.5) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        t = i * math.pi * (3.0 - math.sqrt(5.0))
        out.append(Vector((r * math.cos(t), r * math.sin(t), z)))
    return out


def openness(tree, co, normal, dirs, reach):
    """Share of rays over the hemisphere around `normal` that hit nothing within `reach` m."""
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(normal)
    o = co + normal * 1e-3
    return sum(1 for d in dirs if tree.ray_cast(o, rot @ d, reach)[0] is None) / len(dirs)


def orient(static, margin=0.25, reach=10.0):
    """Flip double-sided faces whose normal side is enclosed and whose back side is open.

    A double-sided face is drawn from both sides but has one COLOR_0, and Cycles bakes the
    light on the side its normal points to. A sheet whose normal points into the model (a
    cloak facing the body, flipped triangles of a generated mesh) bakes the dark inside and
    shows black from outside: ~400 of hero_w1's cloak faces did (an internal task). Closed meshes
    keep their normals (their back sides are enclosed), so does a sheet open on both sides
    (it bakes the side its normal points to, as before) and a single-sided face (its back is
    never drawn). Returns the number of faces turned."""
    bms, verts, polys = [], [], []
    for ob in static:   # transforms are applied: mesh space is world space
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        off = len(verts)
        verts += [v.co.copy() for v in bm.verts]
        polys += [[v.index + off for v in f.verts] for f in bm.faces]
        bms.append(bm)
    tree = BVHTree.FromPolygons(verts, polys, epsilon=0.0)
    dirs = hemisphere()
    turned = 0
    for ob, bm in zip(static, bms):
        two = [m is None or not m.use_backface_culling for m in ob.data.materials] or [True]
        turn = []
        for f in bm.faces:
            if not two[min(f.material_index, len(two) - 1)] or f.calc_area() < 1e-10:
                continue
            c, n = f.calc_center_median(), f.normal.copy()
            front = openness(tree, c, n, dirs, reach)
            if front < 1.0 - margin and openness(tree, c, -n, dirs, reach) > front + margin:
                turn.append(f)
        if turn:
            me = ob.data
            # glTF import stores custom normals, which Cycles shades with and which
            # reverse_faces does not turn: keep them per (face, vertex), negate the turned
            custom = None
            if me.has_custom_normals:
                custom = {(p.index, me.loops[i].vertex_index): Vector(me.corner_normals[i].vector)
                          for p in me.polygons for i in p.loop_indices}
            bmesh.ops.reverse_faces(bm, faces=turn)
            bm.to_mesh(me)
            if custom is not None:
                flip = {f.index for f in turn}
                me.normals_split_custom_set(
                    [custom[(p.index, me.loops[i].vertex_index)] * (-1.0 if p.index in flip else 1.0)
                     for p in me.polygons for i in p.loop_indices])
            me.update()
        turned += len(turn)
        bm.free()
    return turned


def shoulder(x, knee=0.75):
    """Linear below the knee, then a soft roll-off toward 1 (the same curve as bake_unlit)."""
    if x < knee:
        return max(x, 0.0)
    return knee + (1 - knee) * (1 - math.exp(-(x - knee) / (1 - knee)))


def main():
    a = parse()
    t0 = time.time()
    K.reset()
    imported = K.import_glb(a.input)
    sc = bpy.context.scene
    for o in [o for o in imported if o.type == "CAMERA"]:
        bpy.data.objects.remove(o)
    K.setup_cycles(a.samples, "cpu" if a.cpu else "auto")
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 4
    sc.cycles.glossy_bounces = 0
    sc.cycles.use_denoising = False
    sc.render.bake.target = "VERTEX_COLORS"
    sc.render.bake.use_clear = True
    lights(a, sc)

    split_mixed(list(K.meshes()))
    static, live = [], []
    for ob in K.meshes():
        why = why_live(ob)
        (live if why else static).append(ob)
        if why:
            K.log("LIVE", ob.name, "(%s): kept with its own lit materials" % why)
    if not static:
        K.fail("nothing to bake: no static, opaque mesh in %s" % a.input)

    # own every mesh and material (a live mesh sharing a material must stay lit),
    # flatten transforms so the grid is in world metres
    K.select_only(static)
    bpy.ops.object.make_single_user(object=True, obdata=True, material=True)
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    unlit = set()
    for ob in static:
        K.ensure_material(ob)
        for m in ob.data.materials:
            b = principled(m)
            if b is not None:   # bake diffuse light only
                b.inputs["Metallic"].default_value = 0.0
                for s in ("Transmission Weight", "Transmission"):
                    if s in b.inputs:
                        b.inputs[s].default_value = 0.0
            unlit.add(m.name)
    if not a.no_orient:
        K.log("ORIENT %d inward-facing double-sided faces turned to their open side" % orient(static))
    before = K.tris(static)
    for ob in static:
        cut(ob, a.grid, a.sharp)
    K.log("GRID %.2f m: triangles %d -> %d" % (a.grid, before, K.tris(static)))

    lum_all = []
    for ob in static:
        me = ob.data
        prev = me.color_attributes.active_color
        prev_name = prev.name if prev is not None else None
        ca = me.color_attributes.new(LIGHT_ATTR, "FLOAT_COLOR", "POINT")
        me.color_attributes.active_color = ca
        K.select_only([ob], ob)
        t = time.time()
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"})
        ca = me.color_attributes[LIGHT_ATTR]
        raw = [0.0] * (4 * len(ca.data))
        ca.data.foreach_get("color", raw)
        light = [[shoulder(raw[i * 4 + k] * a.exposure) for k in range(3)] for i in range(len(ca.data))]
        lum_all += [0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] for c in light]
        base = me.color_attributes.get(prev_name) if prev_name else None
        if base is None:
            ca.data.foreach_set("color", [v for c in light for v in (*c, 1.0)])
            ca.name = "Color"
            target = ca
        else:
            cols = [0.0] * (4 * len(base.data))
            base.data.foreach_get("color", cols)
            per = light if base.domain == "POINT" else [light[lp.vertex_index] for lp in me.loops]
            for i, c in enumerate(per):
                for k in range(3):
                    cols[i * 4 + k] *= c[k]
            base.data.foreach_set("color", cols)
            me.color_attributes.remove(me.color_attributes[LIGHT_ATTR])
            target = me.color_attributes[prev_name]
        me.color_attributes.active_color = target
        try:
            me.color_attributes.render_color_index = me.color_attributes.active_color_index
        except AttributeError:
            pass
        K.log("BAKED", ob.name, "vertices", len(light), "%.1fs" % (time.time() - t))
    lum_all.sort()
    q = lambda f: lum_all[min(len(lum_all) - 1, int(f * len(lum_all)))]  # noqa: E731
    K.log("LIGHT lum p10 %.3f p50 %.3f p90 %.3f p99 %.3f" % (q(.1), q(.5), q(.9), q(.99)))

    for o in [o for o in sc.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o)
    K.export_glb(a.output, None, colors=True, animations=bool(live))
    K.patch_unlit(a.output, unlit)
    K.log("BAKE_VERTEX_LIGHT_OK", a.output, "baked", len(static), "live", len(live),
          "triangles", K.tris(static), "%.1fs" % (time.time() - t0))


K.run(main)
