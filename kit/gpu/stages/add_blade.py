"""Give a generated sculpt back a thin straight blade it lost (GPU tier, between shape and cage; Blender, CPU).

    blender -b --factory-startup --python kit/gpu/stages/add_blade.py -- \\
        in_high.glb out_high.glb --root=x,y,z --tip=x,y,z [--width 0.07] [--thick 0.02] [--segments 240]
    (or: python kit/gpu/sculpt.py blade in_high.glb out_high.glb --root=x,y,z --tip=x,y,z [...])

Image-to-3D generators drop parts too thin to read in the views: the city's warden statue
(an internal task) kept its crossguard but lost the greatsword's blade. This adds a diamond-section
blade, tapering to a point over the last 15 %, from --root (under the guard) to --tip,
joins it into the mesh and writes a new glb. Points are in Blender's frame
of the imported glb (Z up, front = -Y): read them off a look (kit/blender/look.py) or the
mesh's bounds; write them with "=" (--root=-0.1,0,1.2) so a minus sign is not read as an
option. Run it on the shape step's high mesh, then redo the cage (`sculpt.py cage`)
so the blade is in the cage, its UVs and the normal bake. The blade is cut into many
segments because the cage step drops loose parts under --min-part (2 %) of the largest
part's faces: a blade has segments x 8 + 2 triangles, and when that is under 2.5 % of the
source mesh's triangles (a raw Hunyuan mesh of 100k+ faces) --segments is raised to reach
it (BLADE_NOTE on stderr); past MAX_SEGMENTS it fails with BLADE_FAIL rather than lose the
blade at the cage step. A glb with several meshes is joined into one first, so none is lost.
The glb is written without normals so vertices stay shared and the cage sees one piece.
Prints BLADE_OK <out> <faces>.
Packaged from the iamar-models mesh archive (not public) tools/mesh3d/add_blade.py (iamar city, an internal task).
"""
import argparse
import math
import sys

BLADE_SHARE = 0.025     # blade triangles / source triangles; the cage keeps parts >= 0.02
MAX_SEGMENTS = 16384    # 131 074 triangles: enough for a 5.2M-triangle source


def blade_tris(segments):
    """Triangles of a blade of this many segments: 4 sides x 2 per segment and a 2-triangle cap."""
    return segments * 8 + 2


def blade_segments(requested, src_tris, share=BLADE_SHARE):
    """Segments to use: at least requested, and enough that the blade has >= share x src_tris
    triangles, so the cage step (--min-part 0.02) keeps it. None when over MAX_SEGMENTS."""
    need = max(0, math.ceil((share * src_tris - 2) / 8))
    n = max(requested, need)
    return n if n <= MAX_SEGMENTS else None


def point(s):
    try:
        v = [float(x) for x in s.split(",")]
    except ValueError:
        v = []
    if len(v) != 3 or not all(math.isfinite(x) for x in v):
        raise argparse.ArgumentTypeError("%r: a point is x,y,z (three numbers)" % s)
    return v


def parse(argv):
    ap = argparse.ArgumentParser(prog="add_blade.py", description=__doc__.split("\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--root", type=point, required=True, help="x,y,z under the guard (--root=x,y,z)")
    ap.add_argument("--tip", type=point, required=True, help="x,y,z of the point (--tip=x,y,z)")
    ap.add_argument("--width", type=float, default=0.07, help="metres, edge to edge")
    ap.add_argument("--thick", type=float, default=0.02, help="metres, flat to flat")
    ap.add_argument("--segments", type=int, default=240)
    a = ap.parse_args(argv)
    if not (0 < a.width <= 10 and 0 < a.thick <= 10):
        ap.error("--width and --thick must be in (0, 10] metres")
    if not 1 <= a.segments <= 4096:
        ap.error("--segments must be 1 to 4096")
    if math.dist(a.root, a.tip) < 1e-4:
        ap.error("the root and the tip are the same point")
    return a


def main(argv):
    a = parse(argv)
    import bpy
    import bmesh
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=a.src)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        print("BLADE_FAIL no mesh in %s" % a.src, file=sys.stderr)
        return 1
    if len(meshes) > 1:                           # one mesh, or the export keeps only the first
        bpy.ops.object.select_all(action="DESELECT")
        for m in meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.join()
    o = meshes[0]
    src_tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    segments = blade_segments(a.segments, src_tris)
    if segments is None:
        print("BLADE_FAIL %s has %d triangles: a blade of %d+ segments would be needed for the cage "
              "to keep it (max %d); reduce the mesh first (shape --max-faces)"
              % (a.src, src_tris, math.ceil((BLADE_SHARE * src_tris - 2) / 8), MAX_SEGMENTS), file=sys.stderr)
        return 1
    if segments != a.segments:
        print("BLADE_NOTE --segments %d -> %d: the blade must be >= %.1f %% of the mesh's %d triangles "
              "or the cage drops it" % (a.segments, segments, BLADE_SHARE * 100, src_tris), file=sys.stderr)
    p0, p1 = Vector(a.root), Vector(a.tip)
    ax = (p1 - p0).normalized()
    side = ax.cross(Vector((0, 1, 0)))           # width in the figure's own plane
    if side.length < 1e-6:                        # a blade pointing at the viewer
        side = ax.cross(Vector((1, 0, 0)))
    side.normalize()
    dep = side.cross(ax).normalized()             # thickness toward the viewer
    inv = o.matrix_world.inverted()
    bm = bmesh.new()
    rings = []
    for k in range(segments + 1):
        s = k / segments
        c = p0.lerp(p1, s)
        taper = 1.0 if s < 0.85 else max(0.0, (1.0 - s) / 0.15)
        w, t = a.width * 0.5 * taper, a.thick * 0.5 * taper
        rings.append([bm.verts.new(inv @ (c + side * w)), bm.verts.new(inv @ (c + dep * t)),
                      bm.verts.new(inv @ (c - side * w)), bm.verts.new(inv @ (c - dep * t))])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bm.faces.new(list(reversed(rings[0])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])        # outward
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("blade")
    bm.to_mesh(me)
    bm.free()
    bl = bpy.data.objects.new("blade", me)
    bpy.context.scene.collection.objects.link(bl)
    bl.matrix_world = o.matrix_world
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bl.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.join()
    bpy.ops.export_scene.gltf(filepath=a.dst, use_selection=True, export_format="GLB", export_normals=False)
    print("BLADE_OK %s %d" % (a.dst, len(o.data.polygons)))
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    sys.exit(main(argv))
