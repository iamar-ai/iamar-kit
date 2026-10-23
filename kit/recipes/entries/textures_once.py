"""Recipe textures_once (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 240
r("textures_once", "Store every texture once", "textures",
  "A model whose maps are embedded in a .glb gets them extracted again by Godot's import, so the repository and the build carry each texture twice. Ship the model as glTF with separate files instead.",
  "Every textured model you add (sculpted statues, baked props).",
  ["Export glTF separate: `name.gltf` + `name.bin` + `name_albedo.png` + `name_normal.png`, one folder per model (Blender: export_format GLTF_SEPARATE; `iamar-models tools/mesh3d/bake_stone.py ... out.gltf` does it).",
   "Name the images after the model so two models never share a texture file name.",
   "Point the game at the .gltf; shoot the same views before and after: only animated things may differ."],
  {}, "repository size of the asset folder; before/after shots.", "None.",
  "iamar gate statues 0e042740 (four statues 57 MB -> 29 MB, no visible change)", "manual")
