"""Recipe painted_materials (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 210
LAYER = "style"
r("painted_materials", "Seamless hand-painted material textures", "textures",
  "Stone, ashlar, granite, plaster, timber, slate, glazed tiles, shingles, thatch, cobbles, iron and a trim sheet, painted procedurally so every texture tiles exactly and shares one texel density.",
  "Buildings, roofs and streets that need a coherent painted look without photo textures or downloads.",
  ["Run `python3 kit/tools/paint_materials.py <world>/textures --materials stone,timber,slate --size 512` (numpy and Pillow only; --tint NAME=#RRGGBB colours one; --list names them).",
   "UV-map models at 4 m per texture repeat (one UV unit = 4 m) so every material keeps the same texel density; roof UVs run down the slope; trim mouldings map onto one of the trim sheet's 8 strips.",
   "Use the PNG as the material's Base Color in Blender, then bake light (bake_sky_sun) or leave it live-lit."],
  {"tile_m": 4.0, "size": 1024},
  "preview: no visible seams or stretching; texel density alike on neighbouring surfaces.", "One texture per material, shared between models.",
  "oakhaven tools/mp_textures/paint_library.py (the masterplan city's painted library)", "manual",
  "kit/tools/paint_materials.py")
