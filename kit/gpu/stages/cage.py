"""Generated high-poly surface -> game cage at real size (GPU tier, step 3; Blender, CPU).

    blender -b --factory-startup --python kit/gpu/stages/cage.py -- high.glb out_dir
        --height 2.0 --tris 3000 [--cut-below 0.0] [--min-part 0.02] [--name NAME]
        [--color "#b8b2a6"] [--angle 66] [--margin 0.01]

The surface is welded first (1e-5 of its size). An image-to-3D generator returns one dense surface (hundreds of thousands of faces) in a
unit box, often with crumbs floating beside it and a slab where the picture's ground was.
This step makes the two models the kit's normal bake needs, in the same place and scale:

  out_dir/<name>_high.glb   the cleaned surface: loose pieces under --min-part of the
                            largest part's faces dropped, everything below --cut-below
                            (fraction of the height, from the bottom) cut off and capped,
                            scaled to --height metres, standing on y=0, centred on its
                            FOOTPRINT (the middle of the lowest 3 %, not the bounding box:
                            a staff or a wing sticking out would push the feet off the plinth)
  out_dir/<name>_cage.glb   the same, decimated (collapse) to --tris triangles, smooth
                            shaded, one fresh UV unwrap (smart project), one material of
                            --color: the input of kit/blender/asset_pipeline.py --high

City lessons kept (the iamar-models mesh archive (not public) tools/mesh3d README, statue_v4): decimate the
untextured shape and bake detail back with a normal map (textured decimation shattered thin
sheets); never cut near the soles (cut only a base slab the picture had); judge the
triangle budget in the game, not here.

Prints CAGE_OK <cage> <tris> and writes out_dir/<name>_cage.json. Exits 1 on failure.
Blender 4.2-5.0 (tested 5.0.1). No add-ons.
"""
import json
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "blender"))
sys.dont_write_bytecode = True
import _kitlib as K  # noqa: E402


def parts_keep(bm, min_part):
    """Faces of every connected part with at least min_part x the largest part's faces."""
    seen = set()
    comps = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, comp = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    big = len(comps[0])
    drop = [f for c in comps if len(c) < min_part * big for f in c]
    return len(comps), drop


def main():
    p = K.make_parser("../gpu/stages/cage.py", __doc__.split("\n")[0])
    p.add_argument("high")
    p.add_argument("out_dir")
    p.add_argument("--height", type=float, required=True, help="real height in metres")
    p.add_argument("--tris", type=int, required=True, help="cage triangles (the LOD0 budget)")
    p.add_argument("--cut-below", type=float, default=0.0, help="drop this fraction of the height from the bottom")
    p.add_argument("--min-part", type=float, default=0.02, help="drop parts smaller than this x the largest")
    p.add_argument("--name", default=None)
    p.add_argument("--color", default="#b8b2a6", help="cage material base colour (pale stone)")
    p.add_argument("--angle", type=float, default=66.0, help="smart UV project angle limit")
    p.add_argument("--margin", type=float, default=0.01, help="UV island margin")
    a = K.parse_args(p)
    name = a.name or os.path.splitext(os.path.basename(a.high))[0].replace("_high", "")
    os.makedirs(a.out_dir, exist_ok=True)

    K.reset()
    obs = K.meshes(K.import_glb(a.high))
    if not obs:
        K.fail("no mesh in %s" % a.high)
    K.select_only(obs)
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    tris_in = K.tris([ob])

    bm = bmesh.new()
    bm.from_mesh(ob.data)
    # weld first: a glTF split at UV seams or hard edges is one face per part otherwise
    span = max((max(v.co[i] for v in bm.verts) - min(v.co[i] for v in bm.verts)) for i in range(3))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5 * max(span, 1e-9))
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    n_parts, drop = parts_keep(bm, a.min_part)
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    zs = [v.co.z for v in bm.verts]
    z0, z1 = min(zs), max(zs)
    if a.cut_below > 0:
        zc = z0 + a.cut_below * (z1 - z0)
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, zc), plane_no=(0, 0, 1), clear_inner=True)
        cut_edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        if cut_edges:
            bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        z0 = zc
    bm.to_mesh(ob.data)
    bm.free()

    # scale to the real height, stand on 0, centre the footprint
    vs = [v.co.copy() for v in ob.data.vertices]
    zs = [v.z for v in vs]
    z0, z1 = min(zs), max(zs)
    s = a.height / max(z1 - z0, 1e-9)
    foot = [v for v in vs if v.z <= z0 + 0.03 * (z1 - z0)]
    cx = (min(v.x for v in foot) + max(v.x for v in foot)) / 2
    cy = (min(v.y for v in foot) + max(v.y for v in foot)) / 2
    for v in ob.data.vertices:
        v.co = Vector(((v.co.x - cx) * s, (v.co.y - cy) * s, (v.co.z - z0) * s))
    ob.data.update()
    ob.name = name + "_high"
    tris_high = K.tris([ob])
    K.ensure_material(ob)
    high_out = os.path.join(a.out_dir, name + "_high.glb")
    K.export_glb(high_out, [ob])

    # cage: decimate a copy, unwrap, one material
    low = ob.copy()
    low.data = ob.data.copy()
    low.name = name
    bpy.context.collection.objects.link(low)
    K.select_only([low])
    mod = low.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = min(1.0, a.tris / max(1, tris_high))
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_smooth()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    import math
    bpy.ops.uv.smart_project(angle_limit=math.radians(a.angle), island_margin=a.margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    h = a.color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    m = bpy.data.materials.new(name + "_mat")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*[c ** 2.2 for c in rgb], 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
    low.data.materials.clear()
    low.data.materials.append(m)
    tris_cage = K.tris([low])
    cage_out = os.path.join(a.out_dir, name + "_cage.glb")
    K.export_glb(cage_out, [low])

    dims = low.dimensions
    rep = {"high_in": a.high, "tris_in": tris_in, "parts": n_parts, "faces_dropped": len(drop),
           "cut_below": a.cut_below, "height_m": a.height, "scale": round(s, 5),
           "high": high_out, "tris_high": tris_high, "cage": cage_out, "tris_cage": tris_cage,
           "size_m": [round(dims.x, 3), round(dims.z, 3), round(dims.y, 3)]}
    with open(os.path.join(a.out_dir, name + "_cage.json"), "w") as f:
        json.dump(rep, f, indent=1)
    K.log("CAGE_OK %s %d tris (high %d, %d parts, %d crumb faces dropped)" % (
        cage_out, tris_cage, tris_high, n_parts, len(drop)))


K.run(main)
