"""Recipe gltf_cache (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 230
r("gltf_cache", "Converted-model cache", "textures",
  "Converted glTF scenes are cached, so a second visit opens faster.", "Automatic in the browser.", ["Nothing to do as a builder."], {}, "", "Disk cache.",
  "oakhaven scripts/worlds/world_cache.gd", "automatic")
