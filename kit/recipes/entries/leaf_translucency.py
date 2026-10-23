"""Recipe leaf_translucency (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 480
LAYER = "style"
r("leaf_translucency", "Backlit leaves", "art", "Leaves and grass glow softly when the sun is behind them (wrap and transmission light in the foliage shader).",
  "All foliage.", ["Use the foliage material with translucency on."], {"translucency": 0.35}, "preview against the low sun.", "A few shader instructions.", "Graphics ideas #8", "planned")
