"""Recipe texture_sizes (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 200
r("texture_sizes", "Right-sized textures and atlases", "textures",
  "Small textures for small or far things, atlases to share one material across many props.",
  "Every material.", ["Pick the smallest size that looks right at the closest normal view.", "Share atlases between props in one area."], {},
  "validate: texture budget.", "Authoring time.", "WORLD_FORMAT budgets", "manual")
