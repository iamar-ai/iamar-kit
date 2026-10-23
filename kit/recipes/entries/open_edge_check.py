"""Recipe open_edge_check (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 380
r("open_edge_check", "Find holes and open edges", "measurement",
  "validate will report models with open edges or gaps between parts, where light leaks through a bake or the sky shows through a wall.",
  "Every baked or enclosed model.",
  ["Until the check exists, look for gaps in Blender (Select > Select All by Trait > Non Manifold) before baking."], {},
  "validate.", "None.", "oakhaven masterplan_closure_audit", "planned")
