"""Recipe cloud_shadows (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 410
LAYER = "style"
r("cloud_shadows", "Cloud shadows", "art", "Slow-scrolling cloud shadows drift over the land: one texture sample in the terrain and baked shaders, big sense of life.",
  "Outdoor worlds.", ["Enable the browser's cloud-shadow layer in scene.environment (density, speed, scale)."], {"density": 0.4, "speed_m_s": 3.0},
  "preview over 10 s.", "One texture sample.", "Graphics ideas 2026-10-01 #1", "planned")
