"""Recipe bake_night (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 660
r("bake_night", "Bake the time of day the world is seen at", "lighting",
  "A light bake is one time of day: walls baked in daylight stay day-bright under a black night sky. Baking the night (moonlight, a dim blue sky and the lanterns as lamps) gives dark walls with warm pools by each lamp.",
  "A world that sits at dusk or night, or whose brief promises lamps at night, with light-baked (unlit) architecture.",
  ["Choose the world's lighting preset (kit/style/lighting presets; a world with running time keeps its walls live-lit instead: one bake cannot show both day and night).",
   "Place the lanterns and their point lights in scene.json first (lit_lantern).",
   "Per baked object: `python3 kit/style/lighting/lighting.py bake-args <preset> --world <world> --object <id>` prints bake_unlit options: the preset's sun or moon (direction, colour, energy x pi), its ambient as the sky, and every point light within its range + 12 m as `--lamp x,y,z,r,g,b,watts` in the object's own frame (45 W per unit of energy).",
   "`iamar-world blender-run kit/blender/bake_unlit.py -- in.glb assets/out.glb 64 --texel 0.03 <those options>`.",
   "Shoot the world at the time it is set to and at night (`iamar-world shots --times dusk,night`) and compare with the daylight bake (kit/style/lighting/night_bake_demo.py does both on a sample house)."],
  {"watts_per_energy": 45, "reach_m": 12, "samples": 64},
  "kit/tests/style/lighting_test.py (bake-args: preset sun, sky and lamps in the object's frame); kit/style/lighting/gallery/night_bake/night_bake_pair.jpg (before: daylight bake at night; after: night bake).",
  "One extra bake per object for each look you ship; the bake shows one time of day only.",
  "harbour blind-test review gap 3 (sheet_n: walls stay bright at night); iamar-kit kit/style/lighting/lighting.py bake-args, kit/blender/bake_unlit.py --lamp (an internal task)", "manual",
  "kit/style/lighting/lighting.py")
