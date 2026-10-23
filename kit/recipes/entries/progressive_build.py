"""Recipe progressive_build (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 260
r("progressive_build", "Build progressively, in time slices", "loading",
  "Heavy building work runs in small slices across frames (and on worker threads) so the game never freezes.",
  "Big worlds and any build step over a few milliseconds.",
  ["Split work into slices of about 10 ms per frame.", "Commit meshes on worker threads.", "Hide the first heavy frames behind the world-switch fade and progress bar."],
  {"slice_ms": 10}, "perf: no frame over 50 ms after load.", "Things appear over a few seconds.",
  "oakhaven town.gd slice_usec=10000, 'take the load stutters off the main thread', 00b844a progress bar", "planned")
