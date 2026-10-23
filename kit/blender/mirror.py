"""Keep one half of a model and mirror it onto the other (make it exactly symmetric).

Useful for generated or scanned models whose one side came out better (sharper
paint, cleaner shape): cut at a plane, keep the good half, mirror it with a merged
seam. UVs mirror with the geometry, so the kept half's texture shows on both sides.
All meshes in the file are joined into one first.

    iamar-world blender-run kit/blender/mirror.py -- in.glb out.glb [options]
    blender -b --factory-startup --python kit/blender/mirror.py -- in.glb out.glb ...

Options (axes are glTF/iamar axes: +X right, +Y up, +Z towards the viewer):
  --axis A    x (default), y or z: the axis the mirror plane is perpendicular to
  --keep K    pos (default) or neg: the half to keep, by its side of the plane
  --at V      plane position along the axis in metres (default 0)
  --merge M   weld seam vertices closer than M metres (default 0.001)
  --smooth    shade the result smooth (default: keep the model's shading)

Not for skinned or animated models (the result is one static mesh).

Blender 4.2-4.5 (tested 4.5 LTS). No add-ons.
"""
import os
import sys

import bmesh
import bpy
from mathutils import Matrix

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402

# glTF axis -> (Blender axis index, sign of the glTF + direction in Blender)
AXES = {"x": (0, 1.0), "y": (2, 1.0), "z": (1, -1.0)}


def parse():
    p = K.make_parser("mirror.py", __doc__.split("\n\n")[0])
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--axis", choices=("x", "y", "z"), default="x")
    p.add_argument("--keep", choices=("pos", "neg"), default="pos")
    p.add_argument("--at", type=float, default=0.0)
    p.add_argument("--merge", type=float, default=0.001)
    p.add_argument("--smooth", action="store_true")
    return K.parse_args(p)


def main():
    a = parse()
    K.reset()
    obs = K.meshes(K.import_glb(a.input))
    if not obs:
        K.fail("no mesh in %s" % a.input)
    K.select_only(obs, obs[0])
    bpy.ops.object.make_single_user(object=True, obdata=True)
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    for o in [o for o in bpy.context.scene.objects if o.type != "MESH"]:
        bpy.data.objects.remove(o)
    K.select_only([ob], ob)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    before = K.tris([ob])

    idx, sign = AXES[a.axis]
    no = [0.0, 0.0, 0.0]
    no[idx] = sign                      # Blender direction of the glTF + side
    co = [0.0, 0.0, 0.0]
    co[idx] = sign * a.at
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    # clear_inner removes what lies behind the normal (the glTF - side)
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no,
                           clear_inner=(a.keep == "pos"), clear_outer=(a.keep == "neg"))
    if a.at != 0.0:
        bmesh.ops.translate(bm, vec=[-c for c in co], verts=bm.verts)
    bm.to_mesh(ob.data)
    bm.free()
    if not ob.data.polygons:
        K.fail("nothing left on the %s side of the plane" % a.keep)
    mm = ob.modifiers.new("mirror", "MIRROR")
    mm.use_axis = tuple(i == idx for i in range(3))
    mm.use_clip = True
    mm.use_mirror_merge = True
    mm.merge_threshold = a.merge
    bpy.ops.object.modifier_apply(modifier=mm.name)
    if a.at != 0.0:
        ob.data.transform(Matrix.Translation(co))
    if a.smooth:
        bpy.ops.object.shade_smooth()
    K.export_glb(a.output, [ob], colors=bool(ob.data.color_attributes))
    K.log("MIRROR_OK", a.output, "axis", a.axis, "kept", a.keep, "tris %d -> %d" % (before, K.tris([ob])))


K.run(main)
