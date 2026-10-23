"""Recipe painted_look_bake (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 630
r("painted_look_bake", "Bake a shader-painted look into a texture before exporting an object as glTF", "packaging",
  "A look a shader makes (the city's mp_painted: wood grain, stone courses, iron, trims, contact shade, glow, all from per-vertex look codes) cannot travel in a glTF; exported with only its vertex colour the object is one flat colour per face. Run the shader's colour logic into a per-object atlas instead and keep the mesh.",
  "Every MeshKit object (props, furniture) a world package or the catalogue ships, and any object whose look comes from a custom shader (status: WORKS, an internal task: 45 props and 11 furniture pieces; a first bake from the raw vertex colours FAILED, see steps).",
  ["One chart per face (a MeshKit quad = two triangles sharing an edge and its UVs; other triangles alone) at 128 px/m with a 2 px gutter of the face's own edge colour, shelf-packed into the smallest power-of-two atlas; a bigger object is baked coarser to stay within 1024 px.",
   "Per texel interpolate position, normal, face UV and contact shade and evaluate the shader's colour code (kit/catalog/assets/painted_baker.gd ports mp_painted.gdshaderinc 1:1, noise included).",
   "Decode the vertex colour from sRGB first: Godot hands a spatial shader COLOR decoded, and raw values baked 1.4-4x too bright and washed out (measured against the live shader, unshaded).",
   "Keep triangles and winding, replace TEXCOORD_0, drop COLOR_0 and UV2 (the file then looks the same in every viewer and browser); iron, strap trim and glass go to their own surface for roughness and metallic; glow becomes an emission texture at a fixed dusk level.",
   "Leave out what needs the world (light bake and sky stains, street and ivy maps, rain): the world's own light and bake apply.",
   "Catalogue props: import_city_models.py, bake_painted.gd, import_city_models.py --baked; furniture: export_city_pieces.gd bakes itself."],
  {"px_per_m": 128, "max_atlas_px": 1024, "gutter_px": 2, "image": "JPEG q0.85", "glow_night_level": 0.35},
  "godot --headless --path <the iamar browser source (not public) checkout> -s kit/tests/catalog/painted_bake_test.gd (mesh kept, iron split, glow, grain varies, mean = the shader's colour, every shipped prop and furniture file textured); python3 kit/catalog/assets/import_city_models.py --check fails on a flat prop or furniture file.",
  "A 256-1024 px JPEG per object (3.4 MB for the 45 catalogue props); 15-60 s of one CPU core per object.",
  "iamar-kit 1374cbc kit/catalog/assets/painted_baker.gd, bake_painted.gd, assets/README.md 'The painted look, baked', docs/evidence/job3129_city_vs_bake.jpg; the iamar browser source (not public) shaders/mp_painted.gdshaderinc", "manual", "kit/catalog/assets/painted_baker.gd")
