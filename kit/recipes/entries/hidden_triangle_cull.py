"""Recipe hidden_triangle_cull (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- measurement
ORDER = 360
r("hidden_triangle_cull", "Drop triangles nobody can see", "measurement",
  "Faces buried inside other geometry or never visible from any walkable place are removed before export: fewer triangles for free.",
  "Merged areas and big buildings assembled from overlapping parts.",
  ["A kit command will find faces never seen from the walkable area and strip them; until then delete hidden faces by hand in Blender."], {},
  "perf: triangles per view drop, preview unchanged.", "Build time.", "oakhaven tools/city_vis, landmark far-LOD bake", "planned")
