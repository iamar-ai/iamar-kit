# Split variant (an internal task): keeps the low cage's materials ("head", "body": one surface each in the game, so
# each gets its own LOD chain) and bakes both into the SAME maps.
# Stone statue bake (iamar gate statues, 2026-10-13; recipe sculpt_from_image): bakes a
# high sculpt's tangent normal map and its sky occlusion (a uniform white sky, direct +
# bounced DIFFUSE: how much sky each point sees, unlimited reach) onto the low cage, multiplies a pale stone
# colour by the occlusion into one albedo and exports both maps with tangents.
#   blender -b --factory-startup --python bake_stone.py -- hi.glb low.glb out.(glb|gltf) [size] [ao.png]
# Use absolute paths (Blender resolves relative ones against its own folder). An out path
# ending in .gltf writes glTF separate (out.gltf, out.bin, <name>_albedo.png,
# <name>_normal.png), so the game stores every texture once.
import bpy, sys
a = sys.argv[sys.argv.index("--") + 1:]
hi_p, lo_p, out_p = a[0], a[1], a[2]
size = int(a[3]) if len(a) > 3 else 2048
ao_png = a[4] if len(a) > 4 else ""
bpy.ops.wm.read_factory_settings(use_empty=True)
def imp(p):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=p)
    obs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1: bpy.ops.object.join()
    return bpy.context.view_layer.objects.active
hi = imp(hi_p); lo = imp(lo_p)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
pr = bpy.context.preferences.addons["cycles"].preferences
chosen = "NONE"
for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
    try: pr.compute_device_type = kind
    except TypeError: continue
    pr.refresh_devices()
    if any(d.type == kind for d in pr.devices): chosen = kind; break
pr.compute_device_type = chosen; pr.refresh_devices()
for d in pr.devices: d.use = d.type != "CPU"
sc.cycles.device = "GPU" if chosen != "NONE" else "CPU"
sc.cycles.samples = 128
dim = max(lo.dimensions)
# the occlusion has no reach limit: the sky bake below is a full DIFFUSE (GI) bake, and
# Cycles reads the world AO distance only for the AO pass and Fast GI, so a "reach" knob
# there would do nothing (an internal task). Broad hollows shade because they see less sky.
if len(a) > 5:
    sys.exit("bake_stone.py: takes at most 5 arguments (the old AO-reach 6th one had no effect)")
if sc.world is None:
    sc.world = bpy.data.worlds.new("w")
bpy.context.view_layer.objects.active = lo
# the cage keeps its imported custom split normals, which no longer match an edited mesh and split every
# vertex on export (23,970 instead of ~6,400 for 8000 tris; Godot then generates no LODs): drop them (an internal task)
bpy.ops.object.select_all(action="DESELECT"); lo.select_set(True)
bpy.ops.mesh.customdata_custom_splitnormals_clear()
bpy.ops.object.shade_smooth()
# material: stone colour x AO, normal map
nimg = bpy.data.images.new("statue_normal", size, size, alpha=False); nimg.colorspace_settings.name = "Non-Color"
aimg = bpy.data.images.new("statue_ao", size, size, alpha=False)
alb = bpy.data.images.new("statue_albedo", size, size, alpha=False)
mats = []
for i, old in enumerate(list(lo.data.materials)):
    nm_ = old.name.split(".")[0]
    mat = bpy.data.materials.new(nm_); mat.use_nodes = True
    nt = mat.node_tree
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = nimg
    ta = nt.nodes.new("ShaderNodeTexImage"); ta.image = aimg
    lo.data.materials[i] = mat; mats.append((mat, tn, ta))
print("BAKE_SPLIT materials", [m.name for m, _, _ in mats])
def activate(which):
    for mat, tn, ta in mats:
        for node in mat.node_tree.nodes: node.select = False
        node = tn if which == "n" else ta
        node.select = True; mat.node_tree.nodes.active = node
bpy.ops.object.select_all(action="DESELECT"); hi.select_set(True); lo.select_set(True)
bpy.context.view_layer.objects.active = lo
# Blender 5.0 bakes only into the image node that is selected AND active (an internal task: deselected -> "No active
# and selected image texture node", blank maps)
activate("n")
bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", use_selected_to_active=True,
    cage_extrusion=float(__import__("os").environ.get("EXT","0.02")) * dim, max_ray_distance=float(__import__("os").environ.get("RAY","0.05")) * dim, margin=8)
activate("a")
# sky light from every direction (a uniform white world), direct + bounced, no colour:
# how much of the sky each point of the sculpt sees, deep hollows dark, open forms bright
w = sc.world
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sc.cycles.samples = 256
sc.render.bake.use_pass_direct = True
sc.render.bake.use_pass_indirect = True
sc.render.bake.use_pass_color = False
bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, use_selected_to_active=True,
    cage_extrusion=float(__import__("os").environ.get("EXT","0.02")) * dim, max_ray_distance=float(__import__("os").environ.get("RAY","0.05")) * dim, margin=8)
if ao_png: aimg.filepath_raw = ao_png; aimg.file_format = "PNG"; aimg.save()
px_a = list(aimg.pixels); base = (0.86, 0.82, 0.74)
px = [0.0] * len(px_a)
for i in range(0, len(px_a), 4):
    o_ = px_a[i] ** 1.3   # a little more contrast in the occlusion
    px[i] = base[0] * o_; px[i+1] = base[1] * o_; px[i+2] = base[2] * o_; px[i+3] = 1.0
alb.pixels = px
for mat, tn, ta in mats:
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
    tb = nt.nodes.new("ShaderNodeTexImage"); tb.image = alb
    nt.links.new(tb.outputs["Color"], bsdf.inputs["Base Color"])
    nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.9
bpy.data.objects.remove(hi)
bpy.ops.object.select_all(action="DESELECT"); lo.select_set(True)
if out_p.lower().endswith(".gltf"):
    import os
    name = os.path.splitext(os.path.basename(out_p))[0]
    alb.name = name + "_albedo"; nimg.name = name + "_normal"
    bpy.ops.export_scene.gltf(filepath=out_p, use_selection=True, export_tangents=True,
        export_image_format="AUTO", export_format="GLTF_SEPARATE")
else:
    bpy.ops.export_scene.gltf(filepath=out_p, use_selection=True, export_tangents=True, export_image_format="AUTO")
print("BAKE_SPLIT_OK", out_p, len(lo.data.polygons), chosen)
