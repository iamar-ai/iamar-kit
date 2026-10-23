"""Recipe lod_crossfade (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 470
r("lod_crossfade", "Smooth LOD transitions", "art", "A dithered crossfade between LOD levels, so trees and buildings stop visibly popping.",
  "Every LOD chain.", ["Enable dithered LOD fade on LOD meshes."], {"fade_m": 4.0}, "walk toward a forest.", "A little fill rate during the fade.", "Graphics ideas #7", "planned")
