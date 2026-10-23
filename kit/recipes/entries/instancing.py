"""Recipe instancing (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 40
BROWSER_TECHNIQUE = "scripts/kit/techniques/instancing.gd"   # the browser file that applies it to every world
r("instancing", "Instance repeated props", "geometry",
  "One mesh drawn many times in a single call (MultiMesh): grass, flowers, rocks, trees.",
  "The same model placed more than about 10 times.",
  ["Place one model many times with an instance list instead of copies."], {},
  "perf: draw calls.", "Instances share one LOD choice per batch.", "oakhaven scripts/world/prop_batch.gd MultiMesh; the browser applies it to every world (scripts/kit/world_techniques.gd, off with manifest techniques: {\"instancing\": false})", "automatic")
