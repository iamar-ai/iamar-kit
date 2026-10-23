"""Recipe texture_compression (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- textures and memory
ORDER = 190
r("texture_compression", "VRAM texture compression and mipmaps", "textures",
  "Textures are BC7 (desktop) and ETC2/ASTC (Apple Silicon) with mipmaps: about half the video memory.",
  "Every texture except lightmaps.", ["Import with VRAM compression (high quality) and mipmaps on; enable ETC2/ASTC import for macOS."], {},
  "perf: VRAM in the busiest view.", "More disk than lossless.", "oakhaven 00b844a (457 -> 250 MB on Amber), 887bd83 (ETC2/ASTC)", "planned")
