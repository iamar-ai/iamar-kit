"""Recipe foliage_thinning (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 50
BROWSER_TECHNIQUE = "scripts/kit/techniques/foliage_thinning.gd"   # the browser file that applies it to every world
r("foliage_thinning", "Thin far foliage", "geometry",
  "Grass and flowers fade out with distance; trees are split into cells so culling works.",
  "Any ground cover or forest.",
  ["Split foliage into cells (e.g. 30-45 m).", "Reduce density with distance and stop at a visibility range."],
  {"visibility_end_m": 90, "margin_m": 8}, "perf in open views.", "Far ground looks a little barer.",
  "oakhaven b22d441 (thinned far foliage, split tree cells), prop_batch.gd visibility_range_end; the browser applies it to every world (scripts/kit/world_techniques.gd, off with manifest techniques: {\"foliage_thinning\": false})", "automatic")
