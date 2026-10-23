"""Recipe sky_ambient_still_sun (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 675
r("sky_ambient_still_sun", "Sky ambient only with a still sun", "lighting",
  "Ambient light taken from the sky makes the renderer rebuild the sky's light every time the sun moves; with a still sun it is built once and costs nothing after.",
  "Any world that sets environment.ambient.source to \"sky\".",
  ["Keep `ambient.source: \"color\"` (the default) unless the sky's tint on shadowed sides really matters; pick the colour from the sky's horizon, darker.",
   "Use `ambient.source: \"sky\"` only with a fixed `time_of_day` or `sun.direction` (today's format has no moving sun).",
   "A sky that is only the background, with colour ambient, never builds sky light at all."],
  {"ambient_source": "color"}, "compare a shot with colour and sky ambient; keep sky only if the difference is visible.",
  "Sky ambient + a moving sun: +10 ms CPU / +9 ms GPU per frame on software GL (iamar tools/k5_5_sky_probe.gd); a still sun: one rebuild at load.",
  "iamar docs/perf/K5_5_ENVIRONMENT_RULES.md (an internal task): Godot GLES3 rebuilds sky radiance on any sky-visible light change when the sky feeds ambient/reflections; stepping the sun 0.05 deg/0.5 s only recovers ~2.5 ms", "manual")
