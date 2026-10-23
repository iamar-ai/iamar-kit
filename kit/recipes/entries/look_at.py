"""Recipe look_at (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 510
r("look_at", "Characters look at each other", "art", "Heads turn toward nearby players and whoever they are talking to.",
  "NPCs and players (browser feature).", ["Give NPCs a look_at radius if they should notice visitors."], {"radius_m": 6}, "talk to an NPC.", "Tiny.", "Graphics ideas #11", "automatic")
