"""Quick preview renders of glTF models, to look at a model before it goes into a world.

Renders each model from several sides (and from above) with Blender's fast Workbench
engine: no lights to set up, seconds per image. Use it after modelling or baking
to check shape, scale, textures and the bake, before `iamar-world preview` shows
the whole world.

    iamar-world blender-run kit/blender/look.py -- <out prefix> model.glb [more.glb ...] [options]
    blender -b --factory-startup --python kit/blender/look.py -- out/look model.glb ...

Writes <out prefix>_<i>_<view>.png per model i (0, 1, ...) and view.

Options:
  --views LIST   azimuths in degrees around the model, plus "top" (default 35,145,250,top)
  --size N       image size in px (default 768)
  --shading S    studio (lit, default), flat (colours as stored: shows an unlit bake
                 exactly as the browser draws it) or matcap
  --color C      texture (default), material (base colours only), vertex (COLOR_0) or
                 single (grey clay, for shape)
  --wire         overlay the wireframe (to judge triangle density)
  --elevation D  camera height in degrees above the horizon (default 20)

Prints the triangle count of each model (LOOK <file> <tris> tris <w>x<h>x<d> m).

Blender 4.2-4.5 (tested 4.5 LTS). No add-ons, no GPU needed.
"""
import math
import os
import sys

import bpy
import mathutils

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402


def parse():
    p = K.make_parser("look.py", __doc__.split("\n\n")[0])
    p.add_argument("prefix")
    p.add_argument("models", nargs="+")
    p.add_argument("--views", default="35,145,250,top")
    p.add_argument("--size", type=int, default=768)
    p.add_argument("--shading", choices=("studio", "flat", "matcap"), default="studio")
    p.add_argument("--color", choices=("texture", "material", "vertex", "single"), default="texture")
    p.add_argument("--wire", action="store_true")
    p.add_argument("--elevation", type=float, default=20.0)
    return K.parse_args(p)


def main():
    a = parse()
    os.makedirs(os.path.dirname(os.path.abspath(a.prefix)) or ".", exist_ok=True)
    written = 0
    for i, f in enumerate(a.models):
        K.reset()
        if f.lower().endswith(".obj"):
            bpy.ops.wm.obj_import(filepath=f, forward_axis="NEGATIVE_Z", up_axis="Y")
        else:
            K.import_glb(f)
        obs = K.meshes()
        if not obs:
            K.fail("no mesh in %s" % f)
        sc = bpy.context.scene
        sc.render.engine = "BLENDER_WORKBENCH"
        sh = sc.display.shading
        sh.light = a.shading.upper()
        sh.color_type = {"texture": "TEXTURE", "material": "MATERIAL", "vertex": "VERTEX", "single": "SINGLE"}[a.color]
        sh.show_backface_culling = False
        sh.show_object_outline = False
        sc.render.resolution_x = sc.render.resolution_y = a.size
        sc.render.film_transparent = False
        sc.view_settings.view_transform = "Standard"
        sc.world = bpy.data.worlds.new("w")
        sc.world.color = (0.55, 0.6, 0.66)
        if a.wire:
            for o in obs:
                o.show_wire = True
                o.show_all_edges = True
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.angle = math.radians(40)
        lo = mathutils.Vector((1e9,) * 3)
        hi = -lo
        for o in obs:
            for c in o.bound_box:
                w = o.matrix_world @ mathutils.Vector(c)
                lo = mathutils.Vector(map(min, lo, w))
                hi = mathutils.Vector(map(max, hi, w))
        ctr = (lo + hi) / 2
        r = max((hi - lo).length / 2, 1e-3)
        dist = r / math.sin(cam.data.angle / 2) * 1.05
        cam.data.clip_start = dist * 0.01
        cam.data.clip_end = dist * 4
        el = math.radians(a.elevation)
        for v in [s.strip() for s in a.views.split(",") if s.strip()]:
            if v == "top":
                d = mathutils.Vector((0.0, -0.001, 1.0)).normalized()
            else:
                az = math.radians(float(v))
                d = mathutils.Vector((math.cos(az) * math.cos(el), -math.sin(az) * math.cos(el), math.sin(el)))
            cam.location = ctr + d * dist
            cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = os.path.abspath("%s_%d_%s.png" % (a.prefix, i, v))
            bpy.ops.render.render(write_still=True)
            written += 1
        size = hi - lo
        # report in glTF axes: width x height (up) x depth
        K.log("LOOK %s %d tris %.2fx%.2fx%.2f m" % (f, K.tris(obs), size.x, size.z, size.y))
    K.log("LOOK_OK", written, "images")


K.run(main)
