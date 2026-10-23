"""Recipe terrain_blend (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 420
LAYER = "style"
r("terrain_blend", "Terrain texture blending by slope and height", "art", "Grass, dirt, rock and gravel chosen by slope and height with soft height-blended edges; triplanar rock on cliffs so nothing stretches.",
  "Any terrain.", ["Assign terrain layers with slope and height ranges.", "Use triplanar mapping on steep faces."], {}, "preview cliffs and hills.", "A few texture samples.", "Graphics ideas #2", "planned")
