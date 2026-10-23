"""Recipe instance_tint (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 460
LAYER = "style"
r("instance_tint", "Per-instance colour variation", "art", "Every tree, bush, rock, roof and wall gets a slight random tint and brightness shift so copies stop looking copied.",
  "Every repeated model.", ["Give each placement a small random tint (hue +-4%, value +-8%) through instance colour."], {"hue": 0.04, "value": 0.08},
  "preview a forest and a street.", "Free.", "Graphics ideas #6", "planned")
