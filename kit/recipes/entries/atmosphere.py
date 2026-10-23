"""Recipe atmosphere (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 180
LAYER = "style"
r("atmosphere", "Time-of-day palettes, haze and weather", "materials",
  "Sky, fog, haze and glow follow the time of day; rain and storms; wetness as one shader parameter.",
  "Outdoor worlds.", ["Use the browser's environment settings (scene.environment) rather than custom per-object effects."], {},
  "preview at several hours.", "Small.", "oakhaven 'Atmosphere and weather', Mats.set_wetness", "manual")
