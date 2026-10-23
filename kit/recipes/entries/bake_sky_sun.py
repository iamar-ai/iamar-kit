"""Recipe bake_sky_sun (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- baked light
ORDER = 110
r("bake_sky_sun", "Blender Cycles light bake (sky and sun)", "lighting",
  "Sky light and sunlight with soft shadows are baked into a texture, so static glTF scenery is lit for free without double-lighting.",
  "Static architecture and big props that you author in Blender; primitives and reused assets stay live-lit.",
  ["Export the static model or area from Blender as a .glb with its ordinary materials (and any lamps as Blender lights).",
   "Run `iamar-world blender-run kit/blender/bake_unlit.py -- in.glb assets/out.glb [samples]` (options: --sun x,y,z towards the sun in glTF axes, --sky-strength, --no-sun for interiors, --texel, --max-size, --per-object). It adds a non-overlapping lightmap UV set, sizes the texture from the surface area, bakes colour x (sky + sun + bounce + lamps) + glow with Cycles (GPU when found) and exports one texture per mesh with KHR_materials_unlit, so the browser shows the bake once instead of lighting it twice.",
   "Skinned, animated and alpha (foliage, invisible collision) meshes stay live-lit with their own materials; keep moving characters, creatures, doors and flames out of baked files.",
   "Look at the result (`iamar-world blender-run kit/blender/look.py -- /tmp/look assets/out.glb --shading flat`), then in `iamar-world preview`.",
   "Bake interiors separately from shells, and rebake after any geometry change."],
  {"texel_m": 0.1, "max_size": 4096, "samples": 128},
  "preview the static model from lit and shadowed sides; confirm the bake is visible once and no surface is black.", "Bake time and one lightmap texture per object.",
  "kit/AGENT_KIT.md baked-lighting gotcha and Blender glTF KHR_materials_unlit; oakhaven tools/blender/mission_hall.py bake, tools/bake_light.py GPU selection", "manual",
  "kit/blender/bake_unlit.py")
