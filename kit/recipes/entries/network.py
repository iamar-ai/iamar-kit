"""Recipe network (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- network
ORDER = 310
r("network", "Lean networking", "network",
  "Fast unreliable 15 Hz state, reliable events, Opus voice by distance, rarest-first parallel piece download, peers sharing pieces, per-peer rate limits.",
  "Built into the browser.", ["Keep packages small so first visits are fast; nothing to do in world data."], {},
  "", "None.", "oakhaven scripts/net/*, scripts/shell/world_fetcher.gd, world_swarm.gd", "automatic")
