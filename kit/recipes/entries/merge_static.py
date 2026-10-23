"""Recipe merge_static (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 30
BROWSER_TECHNIQUE = "scripts/kit/techniques/merge_static.gd"   # the browser file that applies it to every world
r("merge_static", "Merge static meshes per area", "geometry",
  "Many small props become one mesh per area and material: far fewer draw calls.",
  "Props that never move: fences, crates, barrels, shelves, small furniture.",
  ["Nothing to do in a world package: the browser merges static pieces that look the same (same material colour, texture and settings) per 96 m area into one mesh with its own LOD chain (scripts/kit/world_techniques.gd, off with manifest techniques: {\"merge_static\": false}).", "Help it: give props that belong together the same material (one shared colour atlas) instead of a material per model.", "Impostor cards and custom shaders keep their own draw.", "Know where the areas are: they are 96 m squares in x and z. From browser 446b4862 they start at the smallest x and z of the pieces that can merge, so a town up to 96 m across is one area wherever it sits. Older browsers (including the pinned kit runtime, kit/runtime.lock, until it moves past 446b4862) start them at the world origin, with edges at x = 0 and z = 0: a town laid out around (0, 0) is cut into four areas and every shared look draws four times (harbour blind test a5: 187 draws for one view, 126 after moving the whole town by (+67, 0, +45) into one area). For those, keep the town inside one square from 0 to 96 (spawn near (48, 0, 48)) or move everything by one offset when you write scene.json."],
  {"cell_m": 96}, "perf: draw calls per view under budget.", "One bigger mesh per area; culling is coarser.",
  "oakhaven scripts/world/prop_batch.gd (PropBatch, keeps per-instance transforms for the bake export), 'Fewer prop draw calls'; world packages: oakhaven lakeside village 446 -> 126 draw calls", "automatic")
