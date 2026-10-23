# Kit Blender tier (Tier 0): commands and the fixed build order

Every model that goes into an iamar world passes through these tools, in this order.
They are plain Blender Python scripts: headless, no add-ons, no network, any `.glb` in.
Each prints a `<TOOL>_OK` line on success and exits 1 on failure, so a build script can
chain them and stop at the first problem. `--help` after `--` lists every option.

```
iamar-world blender-run kit/blender/<tool>.py -- <arguments>
blender -b --factory-startup --python kit/blender/<tool>.py -- <arguments>   # the same, without the wrapper
```

## Install Blender (once)

- **Version:** Blender 4.2 to 5.0; tested on **4.5 LTS** (4.5.3, Linux and Windows) and
  **5.0.1** (Linux). On 5.0, `bake_unlit.py` uses 5.0's compositor node groups for its
  denoise; a `DENOISE_SKIPPED` line means the denoise did not run (the bake still
  finishes, but noisier: raise the samples).
- **Get it:** blender.org/download (Windows/macOS installer or the portable archive), or
  the system package manager (`sudo apt install blender` is often older than 4.2: check
  the version) or `snap install blender --classic`. Ask the user before installing.
- **Found by:** `BLENDER=/path/to/blender`, then `PATH`, then `~/opt/blender-*/`,
  `/opt/blender*`, `/usr/bin`, `/snap/bin`, `/Applications/Blender.app`, Windows
  `Program Files\Blender Foundation`. Check with `iamar-world blender` (prints the path
  and version).
- **Hardware:** any 64-bit CPU and 4 GB RAM. Bakes use the first GPU Cycles finds
  (OptiX, CUDA, HIP, oneAPI, Metal) and fall back to the CPU by themselves; `--cpu`
  forces the CPU. A CPU bake is slower (minutes, not seconds) but gives the same result.
- **Licence:** Blender is GPL-2.0-or-later; the scripts here ship with the kit. Models
  you make with Blender are yours (the GPL does not cover output).

## The build order (do not reorder)

| # | Step | Command | Why here |
|---|---|---|---|
| 1 | Model | your `tools/build.py` (start from `starter_build.py`), or an imported/generated model | silhouette triangles only; detail goes in textures; union touching parts (below) |
| 2 | Weld | `weld.py -- in.glb out.glb` | split vertices tear LODs, crack bakes and fake open edges |
| 3 | Closure audit | `closure_audit.py -- out.glb [--skip "ground*"] [--ground 0]` | anything a player can see must be closed; fix before spending bake time |
| 4 | Trim sheet (optional) | `trim_map.py -- in.glb out.glb --strip cornice --material trim` | mouldings, frames, beams carried by texture, not triangles |
| 5 | Atlas (optional) | `atlas.py -- in.glb out.glb --size 1024` | one material = one draw call; shared atlases merge per area |
| 6 | Normal bake (optional) | `bake_normals.py -- high.glb low.glb out.glb` | carved detail from a high-poly version |
| 7 | Light bake | `bake_unlit.py -- in.glb out.glb [samples]` (static architecture), `bake_vertex_light.py -- in.glb out.glb` (painted architecture that keeps its 256 px/m library maps) or `bake_vertex_ao.py -- in.glb out.glb` (props, creatures, anything moving, and every static model when the world's clock runs: lit materials, time-independent; `--occluder` from `lighting.py ao-args`) | baked light makes a place look finished; never both on one model |
| 8 | LODs + numbers | `lods.py -- in.glb prefix --budget N` | triangles per LOD and Efficiency for the review |
| 9 | Look | `look.py -- /tmp/look model.glb` | see it from several sides before it goes into the world |

**Parts that touch exactly (step 1).** A dome standing exactly on its drum, a box
stacked on a box, awning strips meeting edge to edge: a plain `join` keeps them as
separate shells whose vertices sit at the same places, and step 2 welds those into
edges shared by 3-4 faces. `weld.py` then prints `WELD_NONMANIFOLD` and step 3 fails
(`CLOSURE_FAIL ... non-manifold edges`; the desert blind test hit 38 on one house).
Fix it in the model, not with `--allow-nonmanifold`: combine the parts with an exact
boolean union (`starter_build.py`'s `join` does this and keeps every part's material),
or sink each part a few centimetres into the one it rests on so no vertices coincide,
and delete faces nobody can see (on the ground, or covered by another part).
Test: `kit/tests/blender/stacked_parts_test.py`.

Steps 2, 3, 5, 6, 7 and 8 in one command (stops at the first failed step, writes
`out_dir/pipeline.json` with every step and the triangles per LOD):

```
iamar-world blender-run kit/blender/asset_pipeline.py -- model.glb out_dir \
    --budget 3000 --atlas --light unlit --skip "ground*"
```

The light step takes `bake_unlit.py`'s main options: `--sun=X,Y,Z` (direction towards
the sun, glTF axes; write it with `=` when it starts with a minus), `--sun-strength S`,
`--no-sun`, `--texel M` (metres per light texel, default 0.1; 0.025 keeps more painted
detail on a house, but no unlit texture bake reaches the 256 px/m of `materials texel`: for
painted houses use `--light none` here and run `bake_vertex_light.py` on each LOD), `--max-size N` and `--light-size N` (a fixed texture size).
`pipeline.json` shows the sun the bake used (`LIGHTS` line) and `DENOISED`.

Do not bake normals and unlit light on the same model: unlit materials ignore normal
maps (bake the light from the high-poly model instead, recipe `bevel_normals`).

Vertex AO is only as fine as the mesh, and it multiplies whatever COLOR_0 already holds
(on a flattened model, the colours themselves). On a low-poly building each wall face has
vertices only at its corners, where roof, bands and ground meet, so the corner darkness
spreads over the whole face: with the defaults a generated house's plaster went from 0.85 to
0.59 (harbour blind test, gap G10). For buildings, split long edges first and keep the AO
soft: `--max-edge 2 --floor 0.6 --strength 0.7` kept it at 0.79 (about twice the triangles;
check the tier budget). Or give buildings no AO at all: live sun and shadows.

## Commands

| Command | Inputs | Outputs | Hardware | Fallback | Recipe |
|---|---|---|---|---|---|
| `weld.py -- in.glb out.glb [--distance 0.002] [--sharp 30] [--join] [--report f.json]` | any glTF | welded `.glb`; vertex/triangle counts before and after; `WELD_NONMANIFOLD` when touching parts welded into 3+-face edges | CPU | none needed | `weld_vertices` |
| `closure_audit.py -- in.glb [--weld] [--min-edge 0.12] [--ring 0.03] [--ground H] [--skip PAT] [--max-open N] [--report f.json]` | any glTF | `CLOSURE` lines, JSON report (open edges and non-manifold edges, each with length and glTF position; inside-out parts); exit 1 on a fail | CPU | `--allow-nonmanifold`, `--max-open N` for a known exception | `open_edge_check` |
| `lods.py -- in.glb prefix [--ratios 0.5,0.2 \| --targets N,N] [--mode auto\|collapse\|planar] [--budget N]` | any glTF | `prefix_lod0..N.glb`, `prefix_lods.json` (triangles per LOD, Efficiency) | CPU | `--mode collapse` when planar cannot cut | `lod_chain` |
| `atlas.py -- in.glb out.glb [--size 1024] [--keep-objects] [--save-atlas a.png]` or `a.glb b.glb --out out.glb` | glTF with several materials | one material with one baked colour atlas (alpha materials kept); texel density vs 256 px/m | GPU or CPU (Cycles) | `--cpu` | `texture_sizes`, `merge_static` |
| `trim_map.py -- in.glb out.glb --strip NAME\|N [--material M] [--sheet trim.png] [--tile-m 4]` | glTF with moulding faces | UVs on one trim-sheet strip; optional sheet material | CPU | `--across-m` for a fixed strip scale | `painted_materials` |
| `bake_normals.py -- high.glb low.glb out.glb [--size] [--unwrap]` | high and low model, same place and scale | low model with a tangent-space normal map | GPU or CPU | `--cpu` | `bevel_normals` |
| `bake_unlit.py -- in.glb out.glb [samples] [--sun=X,Y,Z] [--texel M] [--max-size N] [--size N] [--lamp=X,Y,Z,R,G,B,W ...] [--cpu]` | static model | one baked texture per mesh, KHR_materials_unlit; one time of day (a night world: `lighting.py bake-args night --world W --object ID` gives the moon, sky and lanterns as options) | GPU or CPU | `--cpu`, fewer samples | `bake_sky_sun`, `bake_night` |
| `bake_vertex_light.py -- in.glb out.glb [samples] [--grid M] [--sun=X,Y,Z] [--lamp=...] [--cpu]` | static model with painted maps | the same materials (painted Base Color maps and UVs kept) marked KHR_materials_unlit, light (sky, sun, bounce, lamps) in COLOR_0; passes `materials texel` | GPU or CPU | `--cpu`, `--grid 2` | `bake_vertex_light` |
| `bake_vertex_ao.py -- in.glb out.glb [--distance M] [--floor F] [--strength S] [--max-edge M] [--occluder G,m00..m23]` | any model (skins and animations kept); neighbours as occluders (not exported) | COLOR_0 ambient occlusion, multiplied into existing COLOR_0; asset.extras.iamar_bake.kind `sky_ao` | GPU or CPU | `--cpu` | `bake_ao_vertex` |
| `mirror.py -- in.glb out.glb --axis x --keep pos` | any model | exactly symmetric model | CPU | | |
| `look.py -- prefix model.glb ...` | any models | PNG views, triangles and size | CPU (Workbench/EEVEE) | | |
| `asset_pipeline.py -- model.glb out_dir [options]` | any model | every step's `.glb`, `out_dir/<name>.glb` + LODs, `pipeline.json` | as its steps | `--no-closure` for cards | all of the above. Animation clips (node animation, e.g. a spinning vane) are kept through weld, atlas, AO, LODs; the pipeline FAILS naming any clip that did not survive (skinned rigs through `bake_normals`, `--high`), so ship the raw file then |

The kit's trim sheet comes from `python3 kit/tools/paint_materials.py <dir> --materials trim`
(8 strips, top to bottom: cornice, frame, moulding, carved, dentil, rope, beam, strap;
4 m per repeat). The browser also makes LODs of every mesh itself (Godot mesh LOD,
4 px threshold), so a world package ships LOD0 in `assets/`; the LOD files serve the
triangle report, impostor sources and worlds that place far versions themselves.

## Where these came from (evidence)

- Closure rule and numbers (2 mm weld, 0.12 m shortest edge, 3 cm seal ring):
  the iamar browser source (not public) `tools/masterplan_closure_audit.gd`, `docs/MASTERPLAN_CITY_BUILD.md` "Visibility rule".
- LOD ratios 1.0 / 0.5 / 0.2, planar for buildings, collapse for organic: recipe `lod_chain`
  (oakhaven b22d441; `project.godot` mesh_lod threshold_pixels=4).
- Weld before LODs, keep hard edges: recipe `weld_vertices`.
- Trim sheet with 8 strips at 256 px per metre: the iamar browser source (not public) `scripts/world/masterplan/mp_materials.gd`,
  `tools/mp_textures/paint_library.py`; kit `kit/tools/paint_materials.py`.
- Triangle budgets and Efficiency (100 x budget / triangles above budget): the art bar in
  `AGENT_KIT.md` / the iamar browser source (not public) `AGENTS.md` (the maintainer 2026-10-10).

## Tests

`python3 kit/tests/blender/blender_tier_test.py` (this tier: weld, closure audit, LODs,
atlas, trim map, pipeline; about 15 s on a laptop CPU), `python3 kit/tests/blender/stacked_parts_test.py`
(touching parts: plain join fails closure, union and `starter_build.py` pass) and `python3 kit/tests/blender_tools_test.py`
(the bake, mirror and look tools). Both report SKIPPED and exit 0 without Blender.
