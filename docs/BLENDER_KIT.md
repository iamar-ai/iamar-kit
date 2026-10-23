# The Blender kit: scripts for modelling, baking and previews

`kit/blender/` is the kit's Blender toolset for world art. The site's world
page tells agents to "keep the Blender build script with the world" as
`tools/build.py` but never says where that script comes from or what the
other tools do. This page closes that gap.

## Running the tools

All tools run headless through the kit wrapper:

```sh
iamar-world blender-run <script.py> -- <args>
```

(`kit/iamar-world`:110-112 runs `blender -b --factory-startup --python` on
the script with everything after `--`.) Blender itself is external and
optional: the wrapper probes `BLENDER`, `blender` on `PATH`, and common
install locations, and needs Blender 4.x (`kit/iamar-world`:99-109); the
tools are written for Blender 4.2–4.5, tested on 4.5 LTS, using only the
Python API that ships with Blender (`kit/blender/_kitlib.py`).
`kit/blender/_kitlib.py` is shared helpers, not a tool itself; each tool
works from a copy of `kit/blender/` anywhere.

## The tools

| Script | What it does | Invocation |
|---|---|---|
| `starter_build.py` | **The `tools/build.py` starter.** Copy it into your world as `tools/build.py` and change it. Builds a small cottage and a tree in metres (+Z up in Blender; the glTF exporter writes +Y up, which is what iamar expects), gives every object a simple material, applies modifiers, checks a triangle budget, and exports one `.glb` per model into `<world>/assets/`. Keep the script with the world so it can be rebuilt and changed | `iamar-world blender-run tools/build.py -- <world folder>` |
| `look.py` | Quick preview renders of glTF models before they go into a world. Renders each model from several sides and from above with Blender's fast Workbench engine (no lights to set up, seconds per image) to check shape, scale, textures and bakes before `iamar-world preview` shows the whole world. Writes `<out prefix>_<i>_<view>.png` per model and view | `iamar-world blender-run kit/blender/look.py -- <out prefix> model.glb [more.glb ...] [options]` |
| `mirror.py` | Keeps one half of a model and mirrors it exactly symmetric — for generated or scanned models whose one side came out better. Cuts at a plane, keeps the good half, mirrors with a merged seam; UVs mirror with the geometry. All meshes are joined first | `iamar-world blender-run kit/blender/mirror.py -- in.glb out.glb [options]` (`--axis x|y|z`, glTF/iamar axes) |
| `bake_normals.py` | Bakes a high-poly model's detail (bevels, carving, fine relief) into a tangent-space normal map on the low-poly game mesh — the `bevel_normals` recipe in `kit/recipes/TECHNIQUES.md`. The low mesh keeps its own UVs and materials; the map is wired into every material and exported with tangents | `iamar-world blender-run kit/blender/bake_normals.py -- high.glb low.glb out.glb [options]` |
| `bake_unlit.py` | Bakes sky, sun and the model's own lights into one texture and exports the model unlit — the `bake_sky_sun` recipe in `kit/recipes/TECHNIQUES.md`. The exported materials carry `KHR_materials_unlit`, so the browser draws the bake as-is instead of lighting it twice | `iamar-world blender-run kit/blender/bake_unlit.py -- in.glb out.glb [samples] [options]` |
| `bake_vertex_ao.py` | Bakes ambient occlusion into vertex colours (`COLOR_0`) — the `bake_ao_vertex` recipe in `kit/recipes/TECHNIQUES.md`. Soft contact darkness in creases, under overhangs and where parts meet, stored per vertex, so characters, creatures and small props sit in the world without a lightmap. Works on skinned/animated models (bake uses the rest pose; skins and animations are kept). The browser multiplies vertex colours into the base colour (`docs/WORLD_FORMAT.md`:556) | `iamar-world blender-run kit/blender/bake_vertex_ao.py -- in.glb out.glb [options]` |

## Budgets

`starter_build.py` enforces per-model triangle budgets (`BUDGET_TRIS` in the
script): 6,000 for the cottage, 3,000 for the tree — raise them only with a
reason. These feed the world-level budgets the playbook sets: under 150,000
visible triangles and under 150 draw calls in the busiest view on the low
tier (see the site's [playbook](https://iamar.ai/docs/#playbook)).

Ask the user before installing Blender if it is missing
(`docs/TYPESCRIPT_WORLDS.md` §1, site tools section).
