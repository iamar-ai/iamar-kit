"""A carved-stone hero statue on its plinth, painted with the library's stone maps (recipe
`hero_statue`, README.md here).

    iamar-world blender-run kit/recipes/statue/statue.py -- out.glb [options]

Options:
  --figure GLB     the figure (default: the catalogue's hero statue with sword,
                   kit/catalog/assets/landmarks/hero_w1.glb, 1,906 triangles, 3.3 m)
  --plinth GLB     the plinth it stands on (default: the catalogue's statue plinth,
                   kit/catalog/assets/landmarks/statue_bridge_1.glb, 528 triangles, 1.6 m); "none" for no plinth
  --scale S        scale the figure (default 1.0); the plinth keeps its size
  --figure-texture IMG  the figure's colour map (default kit/style/materials/library/plaster.jpg:
                   a mottled, even stone; a block map such as stone.jpg draws masonry courses
                   across the body). Better: the world's own tinted map from `materials.py use`
  --plinth-texture IMG  the plinth's colour map (default library/ashlar.jpg: cut courses)
  --size N         resize the map to N px (default 512; 1024 maps cost four times the texture memory)
  --name NAME      node and material name (default statue: lint classes it as hero_statue, 8k budget)

Joins figure and plinth into one mesh (open sheets such as a cloak become closed 4 cm slabs, and
inside-out or touching parts are fixed, so closure_audit passes), drops their flat vertex colours, UV-maps every face by
its main axis at 1 UV unit = N/256 m (2 m for a 512 map, so the map is 256 px per metre, the
texel rule), gives figure and plinth each one material with its map embedded (two draws), and
weathers them (COLOR_0 and streaks in the figure map; --no-weather for a plain one).
The statue is lit live (README.md: why not bake_vertex_light yet).

Prints STATUE_OK with the triangles and size. Blender 4.2-5.0, no add-ons.
"""
import os
import sys

import bmesh
import bpy
import mathutils
import mathutils.bvhtree
import mathutils.kdtree
from mathutils import noise, Vector

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(KIT, "blender"))
import _kitlib as K  # noqa: E402

SHEET_THICKNESS = 0.04   # metres: a cloak or coat tail carved as a 4 cm slab
WELD = 0.002             # weld distance of the closure audit
WEATHER_ATTR = "kit_weather"
NUDGE = 0.004            # a small part touching another is grown this far out of itself
LANDMARKS = os.path.join(KIT, "catalog", "assets", "landmarks")


def parse():
    p = K.make_parser("../recipes/statue/statue.py", __doc__.split("\n\n")[0])
    p.add_argument("output")
    p.add_argument("--figure", default=os.path.join(LANDMARKS, "hero_w1.glb"))
    p.add_argument("--plinth", default=os.path.join(LANDMARKS, "statue_bridge_1.glb"))
    p.add_argument("--scale", type=float, default=1.0)
    lib = os.path.join(KIT, "style", "materials", "library")
    p.add_argument("--figure-texture", default=os.path.join(lib, "plaster.jpg"))
    p.add_argument("--plinth-texture", default=os.path.join(lib, "ashlar.jpg"))
    p.add_argument("--size", type=int, default=512)
    p.add_argument("--name", default="statue")
    p.add_argument("--no-weather", action="store_true")
    return K.parse_args(p)


def join(objs, name):
    obs = K.meshes(objs)
    K.select_only(obs)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = name
    return ob


def bounds(ob):
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return [min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]


def box_uv(ob, tile):
    """Each face UV-mapped on the plane of its main normal axis, tile metres per UV unit."""
    me = ob.data
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    while me.color_attributes:
        me.color_attributes.remove(me.color_attributes[0])
    me.uv_layers.new(name="UVMap")
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.active
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            co = lp.vert.co
            lp[uv].uv = (co[a] / tile, co[b] / tile)
    bm.to_mesh(me)
    bm.free()


def parts_of(bm):
    """Face islands joined through shared edges: list of face lists."""
    seen, out = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        isl, stack = [], [f]
        seen.add(f)
        while stack:
            g = stack.pop()
            isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        out.append(isl)
    return out


def signed_volume(faces):
    v = 0.0
    for f in faces:
        cs = [lp.vert.co for lp in f.loops]
        for i in range(1, len(cs) - 1):
            v += cs[0].dot(cs[i].cross(cs[i + 1])) / 6.0
    return v


def crossings(tree, p, up=Vector((0, 0, 1))):
    hits = 0
    while hits < 50:
        loc = tree.ray_cast(p, up)[0]
        if loc is None:
            break
        hits += 1
        p = loc + up * 1e-4
    return hits


def solid_sheets(ob, max_faces=400):
    """Make the figure a set of closed, outward-facing solids (audit closure 0).

    A cloak or coat tail is often one open sheet: edge-on it is paper-thin, and its back is
    either missing (single-sided) or lit like its front. Every small open part gets a real
    thickness (SHEET_THICKNESS, rims included). Every part is then turned outward (the catalogue
    figure has 20 inside-out parts), and a small part that meets another part along an edge is
    grown NUDGE outward (pulled in, it sank into the head and baked dark), so the weld does not join them into a non-manifold edge.
    Returns the number of sheet faces made solid."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)
    # the weld also joins parts that touch along an edge (4 faces on one edge): part them again
    bmesh.ops.split_edges(bm, edges=[e for e in bm.edges if len(e.link_faces) > 2], use_verts=True)
    parts = parts_of(bm)
    count = 0
    for part in parts:
        if len(part) <= max_faces and any(e.is_boundary for f in part for e in f.edges):
            count += len(part)
            bmesh.ops.solidify(bm, geom=part, thickness=SHEET_THICKNESS)
    parts = parts_of(bm)
    flipped = []
    for part in parts:   # a closed part with negative volume is inside out: turn it over whole
        closed = all(len(e.link_faces) == 2 for f in part for e in f.edges)
        if closed and signed_volume(part) < -1e-9:
            bmesh.ops.reverse_faces(bm, faces=part)
            flipped.append(part)
    # some were hair tufts sunk in the head: turned out they show as dark specks; drop any whose
    # faces mostly lie inside another part (an odd number of crossings straight up)
    sunk = []
    bm.verts.index_update()
    for part in flipped:
        own = set(part)
        rest = [f for f in bm.faces if f not in own]
        tree = mathutils.bvhtree.BVHTree.FromPolygons([v.co for v in bm.verts],
                                                      [[v.index for v in f.verts] for f in rest])
        inside = sum(1 for f in part if crossings(tree, f.calc_center_median()) % 2)
        if inside * 2 >= len(part):
            sunk.extend(part)
    if sunk:
        bmesh.ops.delete(bm, geom=sunk, context="FACES")
    parts = parts_of(bm)
    bm.normal_update()
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()
    tree = mathutils.kdtree.KDTree(len(bm.verts))
    for v in bm.verts:
        tree.insert(v.co, v.index)
    tree.balance()
    owner = {}
    for i, part in enumerate(parts):
        for f in part:
            for v in f.verts:
                owner[v.index] = i
    touching = set()
    for i, part in enumerate(parts):
        for f in part:
            for e in f.edges:
                others = [{owner[j] for _, j, _ in tree.find_range(v.co, WELD)} - {i} for v in e.verts]
                for k in others[0] & others[1]:
                    touching.add(min((i, k), key=lambda n: len(parts[n])))
    for i in touching:
        for v in {v for f in parts[i] for v in f.verts}:
            v.co += v.normal * NUDGE
    bm.to_mesh(ob.data)
    bm.free()
    return count


def weather_map(img, size):
    """Rain streaks and lichen-dark blotches painted into the figure's map, tiling: the map
    repeats every size/256 m, so the pattern is periodic in both directions."""
    import numpy as np
    px = np.array(img.pixels[:], dtype=np.float32).reshape(size, size, 4)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size * 2 * np.pi
    rng = np.random.default_rng(7)
    streak = np.zeros((size, size), np.float32)
    for k in rng.integers(3, 24, 14):   # vertical streaks: columns of varying darkness
        streak += np.sin(k * x + rng.uniform(0, 6.3)) * rng.uniform(0.3, 1.0)
    streak = np.clip(streak / 6.0, 0, 1) * (0.6 + 0.4 * np.sin(2 * y + 1.0))
    blot = sum(np.sin(a * x + b * y + rng.uniform(0, 6.3)) for a, b in rng.integers(1, 5, (6, 2)))
    blot = np.clip(blot / 3.0, 0, 1)
    shade = 1.0 - 0.14 * streak - 0.12 * blot
    px[..., 0] *= shade
    px[..., 1] *= shade * (1.0 + 0.02 * blot)
    px[..., 2] *= shade * (1.0 - 0.06 * blot)
    img.pixels[:] = px.ravel()


def stone_material(name, path, size, weathered=False):
    if not os.path.isfile(path):
        K.fail("no such texture: %s" % path)
    img = bpy.data.images.load(os.path.abspath(path))
    if img.size[0] != size:
        img.scale(size, size)
    if weathered:
        weather_map(img, size)
    img.pack()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True   # exported single-sided: each sheet side shows its own light
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.9
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def smooth(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def weather(ob, top, height):
    """Weathered stone in COLOR_0 (the browser multiplies it into the painted map and keeps the
    material lit): darker in folds and under the arms, grime rising from the plinth and the
    figure's feet, rain streaks down the vertical faces, a lichen green on the low upward faces
    and a two-scale mottle, so the figure is not one flat colour. Linear, at most 1."""
    me = ob.data
    ca = me.color_attributes.new(WEATHER_ATTR, "FLOAT_COLOR", "POINT")
    me.color_attributes.active_color = ca
    me.color_attributes.render_color_index = me.color_attributes.active_color_index
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        n, co = v.normal, v.co
        cav = 0.0
        for e in v.link_edges:
            d = e.other_vert(v).co - co
            if d.length > 1e-6:
                cav += n.dot(d.normalized())
        cav /= max(1, len(v.link_edges))
        rel = (co.z - top) / height if co.z >= top - 1e-4 else -1.0   # 0 at the feet, 1 at the head
        dark = 0.45 * smooth(0.0, 0.3, cav) + 0.18 * max(0.0, -n.z)
        if rel >= 0:
            grime = 0.3 * (1.0 - smooth(0.0, 0.45, rel))
        else:
            grime = 0.22 * (1.0 - smooth(0.0, 0.45, co.z))   # damp band at the plinth's foot
        streak = 0.16 * max(0.0, noise.noise(Vector((co.x * 5.0, co.y * 5.0, co.z * 0.35)))) * (1.0 - abs(n.z))
        mottle = 0.12 * noise.noise(co * 1.6) + 0.06 * noise.noise(co * 7.0 + Vector((3.1, 1.7, 0.4)))
        val = min(1.0, max(0.42, 0.93 - dark - grime - streak + mottle))
        lichen = max(0.0, n.z - 0.4) / 0.6 * (1.0 - smooth(-0.3, 0.6, rel)) * 0.6 \
            * smooth(-0.2, 0.4, noise.noise(co * 2.3 + Vector((7.0, 0.0, 0.0))))
        warm = grime / 0.3
        r = val * (1.0 - 0.10 * lichen) * (1.0 - 0.02 * warm)
        g = val * (1.0 - 0.02 * lichen) * (1.0 - 0.05 * warm)
        b = val * (1.0 - 0.22 * lichen) * (1.0 - 0.10 * warm)
        ca.data[v.index].color = (r, g, b, 1.0)
    bm.free()


def main():
    a = parse()
    K.reset()
    top = 0.0
    parts = []
    if a.plinth != "none":
        plinth = join(K.import_glb(a.plinth), "plinth")
        top = bounds(plinth)[1][2]
        plinth.data.materials.clear()
        plinth.data.materials.append(stone_material(a.name + "_plinth", a.plinth_texture, a.size))
        parts.append(plinth)
    fig = join(K.import_glb(a.figure), "figure")
    sheets = solid_sheets(fig)
    fig.data.materials.clear()
    fig.data.materials.append(stone_material(a.name + "_stone", a.figure_texture, a.size, not a.no_weather))
    fig.scale = (a.scale, a.scale, a.scale)
    bpy.context.view_layer.update()
    lo, hi = bounds(fig)
    fig.location = (-(lo[0] + hi[0]) * 0.5, -(lo[1] + hi[1]) * 0.5, top - lo[2])
    parts.append(fig)
    fig_lo, fig_hi = bounds(fig)
    ob = join(parts, a.name)
    for v in ob.data.polygons:
        v.use_smooth = True
    tile = a.size / 256.0
    box_uv(ob, tile)
    if not a.no_weather:
        weather(ob, fig_lo[2], max(0.1, fig_hi[2] - fig_lo[2]))
    K.export_glb(a.output, [ob], colors=not a.no_weather)
    lo, hi = bounds(ob)
    K.log("STATUE_OK", a.output, K.tris([ob]), "tris",
          "%.2fx%.2fx%.2f m" % (hi[0] - lo[0], hi[2] - lo[2], hi[1] - lo[1]),
          "map %d px, %.1f m per tile (256 px/m)" % (a.size, tile), "solid sheet faces %d" % sheets, "weathered" if not a.no_weather else "plain")


K.run(main)
