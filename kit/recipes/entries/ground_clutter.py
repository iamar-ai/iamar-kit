"""Recipe ground_clutter (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 430
LAYER = "style"
r("ground_clutter", "Ground clutter", "art", "Pebbles, fallen leaves, clover and mushrooms near paths and trees, instanced with LODs.",
  "Wherever people walk outdoors.", ["Scatter small instanced props by rules (near paths, under trees, by water).", "Thin them with distance."], {"visibility_end_m": 40},
  "perf: draw calls stay in budget.", "Instanced; small.", "Graphics ideas #3", "planned")
