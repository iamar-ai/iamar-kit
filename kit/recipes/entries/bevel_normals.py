"""Recipe bevel_normals (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 160
LAYER = "style"
r("bevel_normals", "Bevel and normal maps from high-poly", "lighting",
  "Bevels and fine detail are baked from a high-poly version into normal maps, so low-poly meshes read as carved.",
  "Buildings, furniture, weapons.",
  ["Model or bevel a high-poly version in the same place and scale as the game mesh; export both as .glb.",
   "Run `iamar-world blender-run kit/blender/bake_normals.py -- high.glb low.glb assets/out.glb --size 1024`. The low mesh needs non-overlapping UVs (or --unwrap). It wires the tangent-space map into every material of the low mesh, exports tangents (--save-map also keeps the PNG; keep it outside assets/).",
   "Do not combine with bake_sky_sun on the same model: unlit materials ignore normal maps (bake the light from the high-poly instead)."],
  {"size": 2048, "cage": 0.02, "distance": 0.04},
  "preview close-ups.", "A normal map per material.", "Graphics list item 3; iamar-models tools/mesh3d/bake_v2.py; kit/blender/starter_build.py uses real bevels", "manual",
  "kit/blender/bake_normals.py")
