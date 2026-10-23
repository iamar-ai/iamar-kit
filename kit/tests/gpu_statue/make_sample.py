# A tiny stand-in for an UltraShape-refined statue, for kit/tests/gpu_statue/statue_test.py:
#   blender -b --factory-startup --python make_sample.py -- out.glb
# One closed surface in the refined mesh's frame (about -0.95..0.80 high, Blender z up): a tapered robe, a neck, a head
# with a nose facing -y (the face oval FCX=0.03 FCZ=0.66), a staff beside it and a thin ground puddle under the feet that
# the sole cut must remove. Voxel-remeshed into one watertight skin, about 60k triangles.
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
parts = []
def add(op, **kw):
    op(**kw); parts.append(bpy.context.active_object)
add(bpy.ops.mesh.primitive_cone_add, vertices=48, radius1=0.24, radius2=0.13, depth=1.36, location=(0.03, 0, -0.27))
add(bpy.ops.mesh.primitive_cylinder_add, vertices=32, radius=0.055, depth=0.2, location=(0.03, 0, 0.5))
add(bpy.ops.mesh.primitive_uv_sphere_add, segments=48, ring_count=24, radius=0.12, location=(0.03, 0, 0.68))
add(bpy.ops.mesh.primitive_uv_sphere_add, segments=16, ring_count=8, radius=0.025, location=(0.03, -0.115, 0.66))
add(bpy.ops.mesh.primitive_cylinder_add, vertices=12, radius=0.02, depth=1.5, location=(-0.22, 0, -0.2))
add(bpy.ops.mesh.primitive_cylinder_add, vertices=48, radius=0.32, depth=0.012, location=(0.03, 0, -0.955))
for o in parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = parts[0]
bpy.ops.object.join()
o = bpy.context.active_object
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
m = o.modifiers.new("r", "REMESH"); m.mode = "VOXEL"; m.voxel_size = 0.0075
bpy.ops.object.modifier_apply(modifier="r")
bpy.ops.object.shade_smooth()   # shared vertices in the glb, as a generator writes them (flat shading splits every face)
print("SAMPLE faces", len(o.data.polygons))
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_materials="NONE")
