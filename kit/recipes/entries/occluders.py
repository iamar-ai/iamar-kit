"""Recipe occluders (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- visibility
ORDER = 80
r("occluders", "Occluders on big walls and buildings", "visibility",
  "Things hidden behind a castle wall or a hall are not drawn at all.",
  "Large solid walls, buildings and hills between areas.",
  ["Add simple occluder boxes inside big solid shapes.", "Turn occlusion culling on."], {},
  "perf: draw calls behind walls drop.", "A little CPU per frame.", "oakhaven b22d441 (castle and garden occluders), project use_occlusion_culling=true", "planned")
