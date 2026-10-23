"""Recipe shared_wind (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- materials and atmosphere
ORDER = 170
r("shared_wind", "One shared wind", "materials",
  "Grass, flowers, trees and flags all sway from one wind value: one uniform, no per-object scripts.",
  "Any vegetation or cloth.", ["Drive vertex-shader sway from one global wind value."], {}, "perf: no per-frame scripts for sway.", "None.",
  "oakhaven 'One shared wind for grass, flowers, trees and flags'", "planned")
