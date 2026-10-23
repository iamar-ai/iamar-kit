"""Recipe light_pool (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 100
BROWSER_TECHNIQUE = "scripts/kit/techniques/light_pool.gd"   # the browser file that applies it to every world
r("light_pool", "A pool of real lights", "visibility",
  "Only the few lamps nearest the camera get a real light; the rest glow through their material.",
  "Towns and halls with many lamps.",
  ["Register every lamp with its position.", "Each moment, give the nearest few a real light.", "Place each light from its fixture's transform (never a separately typed position)."],
  {"real_lights": 6}, "night screenshots: glows sit in the fixtures.", "Far lamps light nothing around them (until night lamps are baked).",
  "oakhaven scripts/world/light_pool.gd (POOL=6), d5a0e98 Buildings.light_at; the browser applies it to every world (scripts/kit/world_techniques.gd, off with manifest techniques: {\"light_pool\": false})", "automatic")
