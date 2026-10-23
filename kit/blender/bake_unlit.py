"""Bake sky, sun and the model's own lights into one texture and export it unlit.

The kit's light bake (recipe `bake_sky_sun`, kit/recipes/TECHNIQUES.md). Takes any
static glTF model or scene (a house, a hall, a whole merged street) and returns a
.glb whose static meshes show their final lighting from a texture: colour x
(sky light + sunlight with soft shadows + bounce light + the model's own lamps)
+ glow of emissive surfaces. The exported materials carry KHR_materials_unlit,
so the iamar browser draws the bake as-is instead of lighting it twice.

    iamar-world blender-run kit/blender/bake_unlit.py -- in.glb out.glb [samples] [options]
    blender -b --factory-startup --python kit/blender/bake_unlit.py -- in.glb out.glb ...

What it does:
  1. imports in.glb; meshes that are skinned, have shape keys, are animated or use
     alpha (foliage cards, invisible collision proxies) stay as they are (live-lit);
  2. joins the static meshes into one (or keeps them apart with --per-object), adds a
     non-overlapping lightmap UV set and sizes the texture from the surface area
     (--texel metres per texel, capped at --max-size; or a fixed --size);
  3. bakes albedo, light (direct + indirect, denoised) and emission with Cycles on
     the GPU when one is found (OptiX, CUDA, HIP, oneAPI, Metal), else the CPU;
  4. writes colour = albedo * light * exposure + emission, tone-mapped to sRGB,
     as one JPEG (or PNG) per baked mesh, embedded in the .glb;
  5. exports out.glb: the baked meshes keep only the lightmap UVs and one unlit
     material each; live meshes keep their own materials. Lights in in.glb are
     baked and not exported (put live lamps in scene.json).

Lighting: a uniform sky (--sky colour, --sky-strength) and a sun (--sun direction
TOWARDS the sun in glTF axes, +Y up; --sun-strength; --no-sun for interiors lit
only by their lamps), plus point lamps from in.glb or --lamp. The bake is one time of
day: a world seen at night bakes the night (moon, dim sky, its lanterns), or its walls
glow with daylight under a black sky. `kit/style/lighting/lighting.py bake-args <preset>`
prints the matching options. Rebake after any geometry change. Bake interiors and shells
separately when they are seen from different places.

Blender 4.2-5.0 (tested 4.5 LTS and 5.0.1). Needs no add-ons. Typical time: a few minutes on a
GPU at 128 samples for a 2048 texture; use 16-32 samples for drafts.
"""
import math
import os
import shutil
import sys
import tempfile
import time

import bpy
import numpy as np
from mathutils import Vector

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402


def parse():
    p = K.make_parser("bake_unlit.py", __doc__.split("\n\n")[0])
    p.add_argument("input", help="model or scene to bake (.glb/.gltf)")
    p.add_argument("output", help="baked model to write (.glb)")
    p.add_argument("samples", nargs="?", type=int, default=128, help="Cycles samples for the light pass (default 128)")
    p.add_argument("--size", type=int, default=0, help="texture size in px (default: from --texel)")
    p.add_argument("--texel", type=float, default=0.1, help="metres per texel when sizing automatically (default 0.1)")
    p.add_argument("--max-size", type=int, default=4096, help="largest texture side (default 4096)")
    p.add_argument("--per-object", action="store_true", help="one texture per mesh instead of joining all static meshes")
    p.add_argument("--sky", default="0.85,0.9,1.0", help="sky colour r,g,b (linear, default 0.85,0.9,1.0)")
    p.add_argument("--sky-strength", type=float, default=0.5, help="sky brightness (default 0.5; 0 = no sky)")
    p.add_argument("--sun", default="0.4,0.8,0.35", help="direction towards the sun x,y,z in glTF axes (+Y up)")
    p.add_argument("--sun-strength", type=float, default=3.0, help="sun brightness (default 3.0)")
    p.add_argument("--sun-color", default="1.0,0.95,0.85", help="sun colour r,g,b (default warm white)")
    p.add_argument("--sun-angle", type=float, default=1.5, help="sun disc size in degrees: shadow softness (default 1.5)")
    p.add_argument("--no-sun", action="store_true", help="no sun (interiors lit by their own lamps and the sky)")
    p.add_argument("--exposure", type=float, default=1.0, help="light multiplier before tone mapping (default 1.0)")
    p.add_argument("--emission", type=float, default=1.0, help="weight of emissive colour in the result (default 1.0)")
    p.add_argument("--format", choices=("jpg", "png"), default="jpg", help="baked texture format (default jpg)")
    p.add_argument("--quality", type=int, default=90, help="JPEG quality (default 90)")
    p.add_argument("--margin", type=int, default=8, help="bake margin in px around UV islands (default 8)")
    p.add_argument("--no-denoise", action="store_true", help="skip denoising the light pass")
    p.add_argument("--cpu", action="store_true", help="bake on the CPU even when a GPU is available")
    p.add_argument("--save-images", metavar="DIR", help="also keep the baked textures in DIR")
    p.add_argument("--lamp", action="append", default=[], metavar="X,Y,Z[,R,G,B[,W]]",
                   help="add a point lamp to the bake (glTF axes, the model's own frame; colour linear, "
                        "default warm 1,0.62,0.25; W watts, default 60). Repeat per lamp. A night world's "
                        "lanterns: `lighting.py bake-args night --world W --object ID` prints these")
    p.add_argument("--lamp-radius", type=float, default=0.1, help="lamp size in m: shadow softness (default 0.1)")
    return K.parse_args(p)


def triple(s):
    v = [float(t) for t in s.split(",")]
    if len(v) != 3:
        K.fail("expected three comma-separated numbers, got %r" % s)
    return v


def uses_alpha(mat):
    if mat is None or not mat.use_nodes:
        return False
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            a = n.inputs["Alpha"]
            if a.is_linked or a.default_value < 0.999:
                return True
    return False


def is_animated(ob):
    o = ob
    while o is not None:
        if o.animation_data and o.animation_data.action:
            return True
        o = o.parent
    return False


def is_static(ob):
    if any(m.type == "ARMATURE" for m in ob.modifiers) or ob.parent_type == "BONE":
        return False, "skinned"
    if ob.data.shape_keys is not None:
        return False, "shape keys"
    if is_animated(ob):
        return False, "animated"
    if any(uses_alpha(m) for m in ob.data.materials):
        return False, "alpha material"
    return True, ""


def pow2_size(area, texel, max_size):
    # lightmap packing fills about half the square
    side = math.sqrt(max(area, 1e-6) / 0.5) / max(texel, 1e-4)
    size = 256
    while size < side and size < max_size:
        size *= 2
    return min(size, max_size)


def add_lightmap_uv(ob, size, margin):
    me = ob.data
    render_uv = next((l for l in me.uv_layers if l.active_render), None)
    lm = me.uv_layers.new(name="lightmap")
    me.uv_layers.active = lm
    if render_uv is not None:
        render_uv.active_render = True   # textures keep reading their own UVs while baking
    K.select_only([ob], ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=(margin * 0.75) / size,
                                shape_method="CONCAVE")
    except TypeError:
        bpy.ops.uv.pack_islands(margin=(margin * 0.75) / size)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake(ob, kind, size, samples, margin, pass_filter=None):
    img = bpy.data.images.new("%s_%s" % (ob.name, kind), size, size, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    added = []
    for slot in ob.material_slots:
        m = slot.material
        if m is None or not m.use_nodes:
            continue
        nt = m.node_tree
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img
        nt.nodes.active = n
        added.append((nt, n))
    K.select_only([ob], ob)
    bpy.context.scene.cycles.samples = samples
    t = time.time()
    if kind == "emit":
        bpy.ops.object.bake(type="EMIT", margin=margin, use_clear=True)
    else:
        bpy.ops.object.bake(type="DIFFUSE", pass_filter=pass_filter, margin=margin, use_clear=True)
    for nt, n in added:
        nt.nodes.remove(n)
    K.log("BAKED", ob.name, kind, size, "%.1fs" % (time.time() - t))
    return img


def pixels(img):
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def denoise(img, work):
    """Compositor denoise of a float image (OpenImageDenoise); None if unavailable."""
    try:
        sc = bpy.data.scenes.new("kit_denoise")
        sc.render.engine = "CYCLES"
        sc.cycles.samples = 1   # the render only runs the compositor (default 4096: 13x slower)
        sc.view_settings.view_transform = "Standard"
        cam = bpy.data.objects.new("kit_dn_cam", bpy.data.cameras.new("kit_dn_cam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        if hasattr(sc, "compositing_node_group"):
            # Blender 5.0+: the compositor is a node group with a Group Output
            # (scene.node_tree and the Composite node are gone)
            nt = bpy.data.node_groups.new("kit_denoise", "CompositorNodeTree")
            nt.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            sc.compositing_node_group = nt
            c = nt.nodes.new("NodeGroupOutput")
        else:
            # Blender 4.x
            sc.use_nodes = True
            nt = sc.node_tree
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            c = nt.nodes.new("CompositorNodeComposite")
        a = nt.nodes.new("CompositorNodeImage")
        a.image = img
        d = nt.nodes.new("CompositorNodeDenoise")
        nt.links.new(a.outputs[0], d.inputs[0])
        nt.links.new(d.outputs[0], c.inputs[0])
        w, h = img.size
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.render.resolution_percentage = 100
        sc.render.image_settings.file_format = "OPEN_EXR"
        sc.render.image_settings.color_depth = "32"
        path = os.path.join(work, img.name + "_dn.exr")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True, scene=sc.name)
        out = bpy.data.images.load(path)
        p = pixels(out)
        bpy.data.images.remove(out)
        K.log("DENOISED", img.name, "%dx%d" % (w, h))
        bpy.data.objects.remove(cam)
        bpy.data.scenes.remove(sc)
        if hasattr(bpy.types.Scene, "compositing_node_group"):
            bpy.data.node_groups.remove(nt)
        return p
    except Exception as e:  # compositor API differs between Blender versions
        K.log("DENOISE_SKIPPED", type(e).__name__, e)
        return None


def shoulder(x, knee=0.75):
    """Linear below the knee, then a soft roll-off toward 1 (sunlit floors, flames)."""
    y = np.where(x < knee, x, knee + (1 - knee) * (1 - np.exp(-(x - knee) / (1 - knee))))
    return np.clip(y, 0, 1)


def lin2srgb(x):
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(np.maximum(x, 0), 1 / 2.4) - 0.055)


def main():
    a = parse()
    t0 = time.time()
    K.reset()
    imported = K.import_glb(a.input)
    sc = bpy.context.scene
    for o in [o for o in imported if o.type == "CAMERA"]:
        bpy.data.objects.remove(o)
    lamps = [o for o in sc.objects if o.type == "LIGHT"]
    K.setup_cycles(a.samples, "cpu" if a.cpu else "auto")
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 4
    sc.cycles.glossy_bounces = 0
    sc.cycles.transmission_bounces = 2
    sc.cycles.use_denoising = False
    sc.render.bake.margin_type = "EXTEND"
    # save_render applies the scene's view transform (AgX by default in 4.x) on top
    # of the tone mapping below: keep it a plain sRGB write
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0

    # sky and sun
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
        # a sun light shines down its local -Z, so its +Z points at the sun
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
        lamps.append(lamp)
    K.log("LIGHTS sky %.2f sun %s lamps %d" % (a.sky_strength, "off" if a.no_sun else "%s towards %s" % (a.sun_strength, a.sun),
                                                len(lamps)))

    static, live = [], []
    for ob in K.meshes():
        ok, why = is_static(ob)
        (static if ok else live).append(ob)
        if not ok:
            K.log("LIVE", ob.name, "(%s): kept with its own materials" % why)
    if not static:
        K.fail("nothing to bake: no static, opaque mesh in %s" % a.input)

    # own every mesh and material, flatten transforms, give bare meshes a material
    K.select_only(static)
    bpy.ops.object.make_single_user(object=True, obdata=True, material=True)
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for ob in static:
        K.ensure_material(ob)
        for m in ob.data.materials:
            for n in m.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":   # bake diffuse light only
                    n.inputs["Metallic"].default_value = 0.0
                    for s in ("Transmission Weight", "Transmission"):
                        if s in n.inputs:
                            n.inputs[s].default_value = 0.0

    if a.per_object or len(static) == 1:
        targets = static
    else:
        # joining fills a colour attribute with black where a mesh lacks it, and
        # imported materials multiply by it: give every mesh every attribute, white
        cnames = {}
        for o in static:
            for ca in o.data.color_attributes:
                cnames[ca.name] = (ca.domain, ca.data_type)
        for o in static:
            for cn, (dom, dt) in cnames.items():
                if cn not in o.data.color_attributes:
                    ca = o.data.color_attributes.new(cn, dt, dom)
                    ca.data.foreach_set("color", [1.0] * (4 * len(ca.data)))
        K.select_only(static, static[0])
        bpy.ops.object.join()
        targets = [bpy.context.view_layer.objects.active]
        targets[0].name = "baked"

    work = tempfile.mkdtemp(prefix="iamar_bake_")
    baked_materials = set()
    try:
        for ob in targets:
            area = sum(p.area for p in ob.data.polygons)
            size = a.size or pow2_size(area, a.texel, a.max_size)
            add_lightmap_uv(ob, size, a.margin)
            K.log("TARGET", ob.name, "tris", K.tris([ob]), "area %.1f m2" % area, "texture", size)
            alb = pixels(bake(ob, "albedo", size, 16, a.margin, {"COLOR"}))[..., :3]
            irr_img = bake(ob, "light", size, a.samples, a.margin, {"DIRECT", "INDIRECT"})
            irr = None if a.no_denoise else denoise(irr_img, work)
            irr = (irr if irr is not None else pixels(irr_img))[..., :3]
            emit = pixels(bake(ob, "emit", size, 1, a.margin))[..., :3]
            lin = alb * irr * a.exposure + emit * a.emission
            lum = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
            K.log("LIGHT", ob.name, "lum p10 %.3f p50 %.3f p90 %.3f p99 %.3f" % tuple(np.percentile(lum, [10, 50, 90, 99])))
            out = lin2srgb(shoulder(lin))
            h, w = out.shape[:2]
            img = bpy.data.images.new("bake_" + ob.name, w, h, alpha=False)
            img.colorspace_settings.name = "sRGB"
            img.pixels.foreach_set(np.concatenate([out, np.ones((h, w, 1), np.float32)], axis=2).astype(np.float32).ravel())
            ext = "jpg" if a.format == "jpg" else "png"
            path = os.path.join(work, "bake_%s.%s" % (ob.name, ext))
            sc.render.image_settings.file_format = "JPEG" if ext == "jpg" else "PNG"
            sc.render.image_settings.quality = a.quality
            sc.render.image_settings.color_mode = "RGB"
            sc.render.image_settings.color_depth = "8"
            img.save_render(path, scene=sc)
            bpy.data.images.remove(img)
            final = bpy.data.images.load(path)
            final.colorspace_settings.name = "sRGB"
            # the written texture must hold exactly the colours computed above
            drift = np.abs(pixels(final)[..., :3].mean(axis=(0, 1)) - out.mean(axis=(0, 1))).max()
            if drift > 0.01:
                K.fail("baked texture %s drifted %.3f from the computed colours (colour management?)" % (path, drift))
            if a.save_images:
                os.makedirs(a.save_images, exist_ok=True)
                shutil.copy(path, a.save_images)

            # keep only the lightmap UVs and one unlit-to-be material
            me = ob.data
            for nm in [l.name for l in me.uv_layers if l.name != "lightmap"]:
                me.uv_layers.remove(me.uv_layers[nm])
            for nm in [c.name for c in me.color_attributes]:
                me.color_attributes.remove(me.color_attributes[nm])
            m = bpy.data.materials.new("bake_" + ob.name)
            m.use_nodes = True
            b = m.node_tree.nodes["Principled BSDF"]
            tx = m.node_tree.nodes.new("ShaderNodeTexImage")
            tx.image = final
            m.node_tree.links.new(tx.outputs[0], b.inputs["Base Color"])
            b.inputs["Roughness"].default_value = 1.0
            b.inputs["Metallic"].default_value = 0.0
            me.materials.clear()
            me.materials.append(m)
            for p in me.polygons:
                p.material_index = 0
            baked_materials.add(m.name)

        for o in [o for o in sc.objects if o.type == "LIGHT"]:
            bpy.data.objects.remove(o)
        K.export_glb(a.output, None, colors=bool(live), animations=bool(live))
        K.patch_unlit(a.output, baked_materials)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    K.log("BAKE_UNLIT_OK", a.output, "baked", len(targets), "live", len(live), "%.1fs" % (time.time() - t0))


K.run(main)
