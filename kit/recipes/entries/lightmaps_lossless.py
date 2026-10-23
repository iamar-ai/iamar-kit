"""Recipe lightmaps_lossless (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 140
r("lightmaps_lossless", "Keep lightmaps lossless", "lighting",
  "Lightmaps are not VRAM-compressed: compression pads them to a multiple of 4 and shifts the light.",
  "Every lightmap, unless the bake writes block-aligned sizes.",
  ["Import lightmap PNGs with lossless compression.",
   "Know the cost: Godot keeps them RGB8 (lossless and VRAM-uncompressed both; channel_pack does not apply), and GPUs store RGB8 padded to 4 bytes a texel, so a 2-channel sky/sun map costs as much as RGBA.",
   "To compress (BC5/RGTC, a quarter of the memory): make the bake write sizes that are a multiple of 4 (with the lightmap UVs scaled to match) and rebake; then check the hard-shadow views, where BC5 errs most (up to ~31/255 before filtering)."],
  {}, "screenshot diff after import changes.",
  "More VRAM than compressed: iamar city 198 maps, 90 Mpx, ~458 MB lossless vs ~115 MB BC5.",
  "oakhaven 00b844a perf pass; iamar-fps F3a 0f1c6e94 (docs/perf/fps_f3a_lightmap_vram.md: BC5 error, RG8 PortableCompressedTexture2D identical but 7-8x slower to load, RG8 DDS reads back as LA8)", "planned")
