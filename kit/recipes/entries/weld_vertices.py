"""Recipe weld_vertices (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 70
r("weld_vertices", "Weld identical vertices", "geometry",
  "A mesh built as separate triangles (3 vertices per triangle, nothing shared) is indexed: corners that are equal in every attribute become one vertex. Same picture, far fewer vertices to build, upload and hold.",
  "Any mesh you assemble in code or export as a triangle soup; check with vertices per triangle (about 3.0 = soup, 0.6-2.2 = indexed).",
  ["Merge only vertices equal in EVERY attribute (position, normal, tangent, colour, UV, lightmap UV, bones); keep hard edges and UV/lightmap seams split.",
   "Keep the triangle order, so anything that hashes or bakes the mesh sees the same corners.",
   "Weld before generating LODs; never weld across a lightmap seam or the bake shifts."],
  {}, "vertex counts before/after per mesh; the same views shot before and after with the clock frozen are pixel-identical.",
  "A little build time.",
  "iamar-fps F11 1ebfb903 (city vertices 3.40M -> 3.12M, far prop copies -81 %, lamp glows -82 %; docs/perf/fps_f11_index_soup.md)", "manual")
