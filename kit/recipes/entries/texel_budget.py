"""Recipe texel_budget (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 220
LAYER = "style"
r("texel_budget", "Texel density and texture budget", "textures",
  "Near surfaces stay as sharp as the city's (256 px per metre) and the world's texture memory stays inside its budget, checked by a command instead of by eye.",
  "Every world that uses painted materials, before the independent review gate.",
  ["Write the profile's tints into the world: `iamar-world materials use <world> --profile <world>/style.json` (13 library maps tinted per layer; `--size 512` or `256` for a low tier).",
   "UV-map at 1 UV unit = 4 m, then run `iamar-world materials texel <glb|world> ...`: it fails any surface below the rule.",
   "Run `iamar-world materials budget <world> --profile <profile>`: it sums texture memory against the budget; drop sizes (texture_sizes) until it passes.",
   "`iamar-world materials list|check|sample` show the library, verify its hashes and build the sample world."],
  {"tile_m": 4.0, "px_per_m": 256},
  "`materials texel` and `materials budget` exit 0 before review.", "None at run time.",
  "iamar-kit b073489 kit/style/materials/materials.py (an internal task)", "manual",
  "kit/style/materials/materials.py")
