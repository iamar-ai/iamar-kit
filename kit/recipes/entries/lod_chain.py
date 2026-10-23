"""Recipe lod_chain (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- geometry
ORDER = 10
BROWSER_TECHNIQUE = "scripts/kit/techniques/lod_chain.gd"   # the browser file that applies it to every world
r("lod_chain", "Distance LOD chain", "geometry",
  "Far objects use much lower-poly versions, so the triangle budget goes to what is near.",
  "Every model larger than a crate, and every merged area mesh.",
  ["Model the full-detail version in Blender.", "Make LODs at about 50% and 20% of the triangles (Decimate, planar for buildings, collapse for organic shapes).",
   "Far away, swap to an impostor card (see impostor).", "Let the engine pick by screen size."],
  {"lod_ratios": [1.0, 0.5, 0.2], "lod_threshold_pixels": 4.0},
  "perf: triangles per view in the busiest and the widest views.", "More disk and memory per model; none at run time.",
  "oakhaven b22d441 (distance LODs for merged props), project.godot mesh_lod threshold_pixels=4 (higher visibly breaks baked buildings); the browser applies it to every world (scripts/kit/world_techniques.gd, off with manifest techniques: {\"lod_chain\": false})", "automatic")
