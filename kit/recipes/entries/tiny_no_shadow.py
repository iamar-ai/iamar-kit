"""Recipe tiny_no_shadow (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 90
BROWSER_TECHNIQUE = "scripts/kit/techniques/tiny_no_shadow.gd"   # the browser file that applies it to every world
r("tiny_no_shadow", "No live shadows on tiny props", "visibility",
  "Small props do not cast real-time shadows (the bake already darkens under them).",
  "Props smaller than about 1 m.", ["Set cast_shadow false on small props."], {"max_size_m": 1.0},
  "perf: shadow draw calls.", "None visible.", "oakhaven b22d441; the browser applies it to every world (scripts/kit/world_techniques.gd, off with manifest techniques: {\"tiny_no_shadow\": false})", "automatic")
