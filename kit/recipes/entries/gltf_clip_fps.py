"""Recipe gltf_clip_fps (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 620
r("gltf_clip_fps", "Animation clips that survive the 30 fps import", "packaging",
  "Godot's glTF import resamples every clip at 30 frames a second, so a stroke faster than 15 Hz aliases away (a 15 Hz sine sampled at 30 fps is all zeros: a dragonfly's wings stood still).",
  "Any looping clip in a .glb a world plays with scene.json objects \"animation\": wings, flags, wheels, flickers.",
  ["Keep motion at or under 15 Hz; for a buzz, flick between two poses on every 30 fps frame (cos at 15 Hz).",
   "Make clip lengths whole 30 fps frames (0.4 s = 12 frames) so the loop has no seam.",
   "Test the imported clip, not the one you wrote: advance the AnimationPlayer in small steps and measure the motion."],
  {"clip_fps": 30, "max_stroke_hz": 15}, "kit/tests/catalog/city_assets_test.gd (insect wings swing > 0.3 rad over a clip).", "None.",
  "iamar-kit kit/catalog/assets/export_insects.gd (CLIP_FPS, BUZZ_HZ); the iamar browser source (not public) scripts/worlds/world_builder.gd _play loops the clip", "manual")
