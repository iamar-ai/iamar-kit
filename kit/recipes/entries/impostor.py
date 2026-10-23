"""Recipe impostor (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 20
r("impostor", "Impostor cards far away", "geometry",
  "Distant trees, buildings and mountains become a flat textured card: a few triangles instead of thousands.",
  "Anything regularly seen beyond about 80-150 m.",
  ["Give the far object \"impostor\": <metres> in scene.json (about 80-150).", "Run `iamar-world impostors <folder>` (renders 8 views of the model into a small atlas; needs a display), then `iamar-world tiers` so lower tiers get smaller atlases. Objects reused by hash (assets use) are skipped: they are not in the folder, so model your own copy if it needs a card.", "The browser swaps model and card at that distance; many cards of one model are drawn together."],
  {"start_m": 120}, "preview the widest view; perf triangles drop.", "A texture per model.", "docs/WORLD_TIERS.md (impostor cards), oakhaven 802210a/906af53", "manual")
