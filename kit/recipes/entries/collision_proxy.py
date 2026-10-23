"""Recipe collision_proxy (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 60
r("collision_proxy", "Simple collision shapes", "geometry",
  "Physics uses boxes and capsules, not the visual triangles.",
  "Everything except floors and stairs people walk on.",
  ["Use collision: box for houses you do not enter, rocks, crates.", "Use mesh only where people walk.", "Props are obstacles, not ground."],
  {}, "validate warns about mesh collision on big decorative models.", "None.",
  "docs/WORLD_FORMAT.md 4.4 collision; oakhaven 'props are obstacles, not ground'", "manual")
