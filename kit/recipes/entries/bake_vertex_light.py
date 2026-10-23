"""Recipe bake_vertex_light (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 130
r("bake_vertex_light", "Painted maps + baked light (light in vertex colours)", "lighting",
  "Painted architecture keeps its shared 256 px/m library maps and still gets baked sky, sun and bounce light: the light is stored per vertex, not in a texture.",
  "Static houses, walls and big props that use painted maps (`materials use`) and must pass `materials texel`. A glTF material has one colour texture and the browser reads no lightmap slot, so bake_sky_sun would replace the painted map by a 10-40 px/m bake.",
  ["UV-map the model to the painted maps at 256 px/m (a 1024 map per 4 m, or a 512 map per 2 m: `materials use --size 512` keeps five textured houses inside the 64 MiB budget, because every .glb pays for its own embedded maps).",
   "Run `iamar-world blender-run kit/blender/bake_vertex_light.py -- in.glb assets/out.glb [samples] [--grid 1.0]` (the same --sun, --sky-strength, --no-sun and --lamp options as bake_unlit.py). It cuts the static meshes on a --grid lattice, splits hard edges, bakes light with Cycles into COLOR_0 and exports the original materials unlit.",
   "Skinned, animated, alpha and emissive meshes stay live-lit with their own materials.",
   "LODs: decimate the unbaked model (`lods.py`), then bake each level (LOD1 --grid 2, LOD2 --grid 0). FAILED: decimating the baked model removes the grid and the light with it (1,400 triangles fell to 44, lit only at the corners).",
   "Open sheets (cloaks, banners, generated meshes with flipped triangles): Cycles bakes the side a normal points to, and a double-sided face shows one COLOR_0 from both sides. The bake turns double-sided faces whose normal side is enclosed and whose back is open to the open side (--no-orient keeps the normals). FAILED before that: about 400 cloak faces of the catalogue hero_w1 baked black and the browser showed a black cloak from behind. A sheet whose two sides must differ needs thickness or a flipped single-sided copy (kit/recipes/statue/statue.py).",
   "Check with `iamar-world materials texel`, `materials budget`, `lint` and `audit all` on the world."],
  {"grid_m": 1.0, "samples": 64},
  "`python3 kit/tests/blender/vertex_light_test.py`: five baked houses pass texel, budget, lint and audit; sun side brighter than shade side. `python3 kit/tests/blender/bake_vertex_light_sheet_test.py`: a cloak facing the body, hero_w1 and the statue recipe bake with no visible face under 0.05.",
  "Triangles grow with the grid (a 6 x 5 m house: about 1,000 at 1 m, 3,000 at 0.5 m); shadows are only as sharp as the grid.",
  "kit/blindtest/harbour/attempt-3/gaps.md G5, G6 (harbour blind test attempt 3, 071465c); browser the iamar browser source (not public) scripts/worlds/world_package.gd _glb_vertex_colours (COLOR_0 multiplies albedo) and Godot GLTFDocument KHR_materials_unlit -> unshaded (checked headless, an internal task); open sheets: an internal task (iamar.26 black cloak), an internal task", "manual",
  "kit/blender/bake_vertex_light.py")
