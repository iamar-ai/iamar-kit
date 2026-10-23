"""Recipe streaming (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- loading and smoothness
ORDER = 250
r("streaming", "Stream terrain in chunks", "loading",
  "Only the terrain near the player is built and refined.", "Worlds larger than a few hundred metres.",
  ["Split terrain into chunks and build near ones first."], {"chunk_m": 90}, "frame-time metrics while walking.", "Code complexity.",
  "oakhaven scripts/world/terrain.gd CHUNK=90", "planned")
