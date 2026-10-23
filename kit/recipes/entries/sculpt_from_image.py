"""Recipe sculpt_from_image (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 580
LAYER = "style"
TIER = 1
r("sculpt_from_image", "Sculpt a hero statue from an image", "art",
  "A statue or hero prop is generated from a picture (image-to-3D), cut to a game budget and given the sculpt's detail as baked maps: it reads as carved stone at a fraction of the triangles.",
  "Statues, figureheads, gate guardians: one-off showpieces seen up close.",
  ["Make an ORIGINAL concept (`iamar-models tools/mesh3d/refimg.py`, SDXL text-only, about 8-10 options; or the client's own AI-generated image). Never feed commercial art or someone else's sculpt.",
   "Change one part without redrawing the figure: paint a mask (white = redraw, black = keep, feathered) and run `python kit/gpu/sculpt.py inpaint concept.png mask.png out/parts --prompt \"the part, in the figure's material\"` (SDXL inpainting, `kit/gpu/stages/inpaint_part.py`; the South Gate mage got a new staff this way).",
   "Shape: `gen3d_v2.py img prefix 20000 0.0 shape` (Hunyuan3D-2, about 80k faces, ~2-3 min on an 11 GB GPU), then `... 8000 0.0 low` (decimate + xatlas UVs). 8k triangles is the sweet spot for a 3-4 m statue: 12k looks no better, 5k and below facet faces and cloaks.",
   "A thin straight part the generator lost (a sword blade): `python kit/gpu/sculpt.py blade x_high.glb x_high_blade.glb --root=x,y,z --tip=x,y,z` (`kit/gpu/stages/add_blade.py`) on the high mesh, then redo the low mesh so the blade is in its UVs and the bake.",
   "Bake: `blender -b --python <iamar-models>/tools/mesh3d/bake_stone.py -- hi.glb low.glb out.gltf 2048` (tangent normal map + sky occlusion times a pale stone colour, glTF separate).",
   "Look from 4 sides (`kit/blender/look.py`), place it, and turn it so it faces the way the scene needs (find the front from a landmark of the pose: the drawn bow, not the elbow).",
   "Shoot it in the world by day and night from both sides and commit the shots."],
  {"triangles": 8000, "map_size": 2048}, "shots by day and night; LOD levels exist (8000/2000/1000/500).",
  "Two 2048 maps per statue (~6-8 MB); GPU minutes per statue.",
  "iamar gate statues 2026-10-13 (2d2f7ad9, af5a8efa, 40a3b0c1, ac36f688, 0e042740; docs/masterplan_audit/gate_statues/). Licence: Hunyuan3D-2 output may not be used in the EU, the UK or South Korea.", "manual")
