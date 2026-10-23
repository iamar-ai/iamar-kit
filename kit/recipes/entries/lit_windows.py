"""Recipe lit_windows (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 540
LAYER = "style"
r("lit_windows", "Lit windows at night", "art", "Windows glow warmly from inside, some flicker like candlelight, turning on and off through the evening (emissive only, no real lights).",
  "Every building with windows.", ["Give window panes the window-glow material (it follows the time of day)."], {}, "night preview.", "Free (emissive).", "Graphics ideas #14", "planned")
