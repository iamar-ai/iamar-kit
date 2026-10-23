"""Recipe multiview_sculpt (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 590
LAYER = "style"
TIER = 2
r("multiview_sculpt", "Sculpt from several generated views", "art",
  "One concept picture becomes a set of consistent views (front, sides, back) with a multi-view diffusion model, and the image-to-3D step builds the mesh from all of them: the far side is modelled and painted from its own view instead of guessed, so no mirror step and no blurred back.",
  "Any sculpted part seen from all round (a creature head on a skeleton, a statue in a square); worth it when a single-view sculpt shows a soft or wrong back.",
  ["Crop the part from the concept and cut away what is not it (a polygon mask times background removal; `iamar-models tools/mesh3d/mv_views.py --mask`).",
   "Views: `mv_views.py <img> <prefix> --mask poly.png --az 0 90 180 270 --text \"...\"` (MV-Adapter on SDXL, 768 px, ~90 s on an 11 GB GPU; four views fit, six do not). Make a contact sheet of the concept and the views and look at it: the back view is the weakest.",
   "Shape: `head_mv.py <prefix> <out> 4000 0.0 shape` (Hunyuan3D-2mv from front/left/back/right, about 80k faces), then `... low` (cut, decimate keeping topology, large-chart UVs) and `... paint --paint 000,090,270` (Hunyuan3D-2 paint from several views onto the cage's own UVs).",
   "Levels and bake: `blender -b --python <iamar-models>/tools/mesh3d/head_lods.py -- <out> <dir> <name> 2500,1500,700 --rot 0,0,180` (normal map from the high shape, coarser levels by collapse on the same UVs, glTF separate with one mesh per level), then `head_tex.py` (recolour the paint's grey fill, optional glow mask).",
   "Test 1500 / 2500 / 4000 triangles at the distance it is seen and keep the lowest that holds the silhouette landmarks (horns, jaw, brow); pay for it by coarsening what the player sees less."],
  {"views": 4, "view_size": 768, "triangles": 2500, "map_size": 1024}, "contact sheet of the views; triangles per level within the asset's old budget (dragon_lod_parts_test breeds); shots by day and night.",
  "GPU minutes per part; two 1024 maps per part.",
  "iamar stable dragon breeds 2026-10-14 (an internal task; docs/masterplan_audit/stable_dragons/). MV-Adapter (huanngzh, Apache-2.0); Hunyuan3D-2mv / -2 output may not be used in the EU, the UK or South Korea.", "manual")
