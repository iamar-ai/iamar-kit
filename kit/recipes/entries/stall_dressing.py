"""Recipe stall_dressing (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 560
LAYER = "style"
r("stall_dressing", "Market stall dressing", "art", "Shelves, hanging goods, cloth bolts and piles on every market stall, so a stall reads as a shop and not a blank counter.",
  "Every world with market stalls or shop counters the visitor can see.", [
   "Stock the back wall: two shelf rows with jars, folded cloth or bowls; never flat dark panels (they read as holes).",
   "Lay the counter in three depths: low goods at the front edge, taller in the middle, tallest at the back.",
   "Hang goods from the canopy edge or a side post: strings of pots or gourds, cloth strips, a lantern.",
   "Pile and bolt the goods: spice mounds in shallow bowls, cloth bolts stacked 3-2-1 with one drape over the edge, brass in clusters of mixed heights.",
   "At least 15 goods per stall (8+ on the counter, 4+ on shelves, 3+ hanging); count reused catalogue props at their real lod0 triangles (full recipe: kit/recipes/market/README.md)."],
  {"triangles_per_stall": 2600, "min_goods_per_stall": 15},
  "stall shots at eye height show stocked shelves, a three-deep counter and hanging goods; the dressed models pass lint.",
  "About 1,000-1,600 triangles of dressing per stall on top of the ~800-1,000-triangle shell.",
  "desert blind-test review gap 2 (docs/reviews/2026-10-21-an agent-blindtest-desert-a2.md; rv_saffa_goods, rv_cloth_stall, rv_brass_stall; an internal task); full recipe and before/after example: kit/recipes/market/README.md",
  "manual")
