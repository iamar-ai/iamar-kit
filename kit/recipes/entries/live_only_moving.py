"""Recipe live_only_moving (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 150
r("live_only_moving", "Live light only for what moves", "lighting",
  "Characters get live shadows only where the bake has sun; lamps stay live via the light pool.",
  "Always.", ["Use the bake for static things; live light and shadow only for characters and moving objects."], {},
  "perf: shadow cost.", "None.", "oakhaven bake.gd notes", "planned")
