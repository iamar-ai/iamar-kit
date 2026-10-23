"""Recipe quality_presets (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- quality settings
ORDER = 280
r("quality_presets", "Quality presets and auto-tune", "quality",
  "Fast / Balanced / higher presets with a first-run auto-tune; worlds must look pleasant on the lowest.",
  "Every world.", ["Design for the low tier first, then add detail that lights up on better GPUs."], {},
  "perf on Amber-class hardware (HD 5750, 1 GB) at 30 fps.", "Testing several tiers.", "oakhaven presets and _auto_tune; GPU tiers item (planned)", "manual")
