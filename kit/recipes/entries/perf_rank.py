"""Recipe perf_rank (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 370
r("perf_rank", "Rank models by cost", "measurement",
  "perf will list which models and shaders cost the most triangles and draw calls in each view, so you fix the worst first.",
  "Whenever a view is over budget.",
  ["A `perf --rank` option will list the top models per view; until then compare perf numbers with models hidden."], {},
  "perf.", "None.", "oakhaven tri_rank and shader_census tools", "planned")
