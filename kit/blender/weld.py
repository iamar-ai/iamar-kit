"""Weld a model: merge duplicate vertices, drop loose and degenerate geometry, fix normals.

Generated, imported and joined meshes often have every face as its own island (split
vertices along each edge), zero-area slivers and stray vertices. They then shade with
seams, bake with cracks, decimate badly (LODs tear along the splits) and fail the
closure audit with edges that are really closed. Run this first, before LODs, bakes
and the closure audit (kit/blender/README.md, build order).

    iamar-world blender-run kit/blender/weld.py -- in.glb out.glb [options]

Options:
  --distance M     merge vertices closer than this, in metres (default 0.002; the city
                   closure audit welds at 2 mm too)
  --keep-normals   do not recalculate normals outside (default: recalculate, so the
                   faces of a closed shape point outwards)
  --sharp DEG      edges where faces meet at more than this stay hard (default 30)
  --join           join every mesh into one object (default: weld each object alone)
  --report FILE    write the numbers as JSON

Materials, UVs and colour attributes are kept; shading becomes smooth with hard edges
above --sharp degrees (boxes keep their corners, round shapes stay round); UV seams stay seams (merging
by distance only joins vertices whose positions match, and glTF splits them again
where UVs differ). Prints WELD_OK with vertices and triangles before and after.

Parts that touch exactly (a dome standing on its drum, a box stacked on a box, strips
meeting edge to edge) share vertex positions, so welding merges them into edges shared
by 3 or more faces, which closure_audit.py fails as non-manifold. weld.py does not cut
geometry to repair that; it prints a WELD_NONMANIFOLD line with the count and the
longest such edge (also "nonmanifold_edges" in --report). Fix it in the model: combine
the parts with an exact boolean union (starter_build.py's join), or sink each part a
few centimetres into the one it rests on and delete the faces nobody can see
(kit/blender/README.md, build order step 1).

Blender 4.2-4.5 (tested 4.5 LTS). No add-ons.
"""
import json
import os
import sys

import bmesh
import bpy

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402


def parse():
    p = K.make_parser("weld.py", __doc__.split("\n\n")[0])
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--distance", type=float, default=0.002)
    p.add_argument("--keep-normals", action="store_true")
    p.add_argument("--sharp", type=float, default=30.0)
    p.add_argument("--join", action="store_true")
    p.add_argument("--report", metavar="FILE")
    return K.parse_args(p)


def weld_object(ob, dist, recalc):
    """Welds one mesh in place; returns (merged vertices, removed faces, removed loose,
    non-manifold edges as (length, glTF midpoint))."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nv = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=dist)
    merged = nv - len(bm.verts)
    nf = len(bm.faces)
    # zero-area faces and zero-length edges: collapse them away
    bmesh.ops.dissolve_degenerate(bm, dist=dist * 0.5, edges=bm.edges[:])
    removed_faces = nf - len(bm.faces)
    loose = [v for v in bm.verts if not v.link_faces]
    nl = len(loose)
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    wire = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=wire, context="EDGES")
    if recalc and bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mw = ob.matrix_world
    nonman = []
    for e in bm.edges:
        if len(e.link_faces) > 2:
            mid = mw @ ((e.verts[0].co + e.verts[1].co) * 0.5)
            nonman.append((e.calc_length(), [round(mid.x, 3), round(mid.z, 3), round(-mid.y, 3)]))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return merged, removed_faces, nl, nonman


def main():
    a = parse()
    K.reset()
    obs = K.meshes(K.import_glb(a.input))
    if not obs:
        K.fail("no mesh in %s" % a.input)
    K.select_only(obs, obs[0])
    bpy.ops.object.make_single_user(object=True, obdata=True)
    if a.join and len(obs) > 1:
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        bpy.ops.object.join()
        obs = [bpy.context.view_layer.objects.active]
    verts0 = sum(len(o.data.vertices) for o in obs)
    tris0 = K.tris(obs)
    merged = removed = loose = 0
    nonman = []
    for ob in obs:
        m, r, lo, nm = weld_object(ob, a.distance, not a.keep_normals)
        K.reshade(ob, a.sharp)
        merged += m
        removed += r
        loose += lo
        nonman += nm
    verts1 = sum(len(o.data.vertices) for o in obs)
    tris1 = K.tris(obs)
    if tris1 == 0:
        K.fail("nothing left after welding (distance %.4f m too large?)" % a.distance)
    K.export_glb(a.output, None, colors=any(o.data.color_attributes for o in obs), animations=True)
    rep = {"input": a.input, "output": a.output, "distance_m": a.distance, "objects": len(obs),
           "vertices": [verts0, verts1], "triangles": [tris0, tris1], "merged_vertices": merged,
           "degenerate_faces_removed": removed, "loose_vertices_removed": loose,
           "normals_recalculated": not a.keep_normals, "nonmanifold_edges": len(nonman)}
    if a.report:
        with open(a.report, "w") as f:
            json.dump(rep, f, indent=1)
    K.log("WELD_OK", a.output, "vertices %d -> %d" % (verts0, verts1), "tris %d -> %d" % (tris0, tris1),
          "merged %d degenerate %d loose %d" % (merged, removed, loose))
    if nonman:
        ln, at = max(nonman)
        K.log("WELD_NONMANIFOLD", "%d edges shared by 3+ faces (longest %.2f m at %s):" % (len(nonman), ln, at),
              "parts touch exactly; union them (starter_build.py join) or sink them into each other",
              "and delete hidden faces, else closure_audit.py fails (kit/blender/README.md step 1)")


K.run(main)
