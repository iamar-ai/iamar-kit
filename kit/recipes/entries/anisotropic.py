"""Recipe anisotropic (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 450
r("anisotropic", "Anisotropic filtering", "art", "Ground textures stay sharp at grazing angles instead of blurring toward the horizon.",
  "Ground, roads, floors.", ["Import ground textures with anisotropic filtering (4x-8x)."], {"level": 8}, "preview long roads.", "Nearly free.", "Graphics ideas #5", "automatic")
