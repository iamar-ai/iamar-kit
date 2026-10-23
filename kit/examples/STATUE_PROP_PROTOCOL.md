# Statue and prop protocol (tool-agnostic)

How to make a hero statue or a prop for any iamar world with any tool: a hosted image-to-3D
service, a local GPU model, a hand sculpt in Blender, or a purchased model you have the licence
for. The steps say WHAT must hold and give the number; the tool only decides HOW. Every step ends
in a check that passes or fails: `python3 kit/examples/check_statue_spec.py <spec.json>` (rules
below) and the Blender tier tools (`kit/blender/README.md`). Evidence: the four gate statues of
the iamar city (an internal task; `docs/masterplan_audit/gate_statues/` in
the iamar browser source (not public); commits 2d2f7ad9, af5a8efa, 40a3b0c1, ac36f688, 0e042740, da531aae). Layer:
engineering rules apply to every world; the stone look (`style`) is the iamar profile's.

## Statue: ten steps with numbers

| # | Rule | Number | Check |
|---|---|---|---|
| 1 | Concept is ORIGINAL (your own prompt, the user's own image, a hand sketch). Never feed commercial art or someone else's sculpt. | `concept.original: true`, `concept.source` named | spec |
| 2 | Subject fills the canvas: one figure, plain background, full body in frame, subject height about 80 percent of the canvas height (70-90 accepted); smaller subjects lose detail in the image-to-3D step. | `subject_fill` 0.70-0.90 | spec |
| 3 | Make the high-poly sculpt (any tool). It is only the SOURCE for the bake, never shipped. | about 80,000 faces | spec `high_tris` >= 40,000 |
| 4 | Clean the sculpt: strip the generated ground base and floating danglers (loose islands, ground slabs, dust); KEEP THE NECK (cutting at the chin gives a floating head and a hole in front views); do not mirror a figure whose pose is asymmetric. | `base_stripped`, `danglers_removed`, `neck_kept` all true | spec |
| 5 | Decimate to the game budget with UVs (one texture chart set, no overlap). A hero statue of 3-4 m: 8,000 triangles. 12,000 looks no better; 5,000 and below facets faces and cloaks. Props: 300 (budget in AGENTS.md of the city); a kit prop at LOD0 is at most 600. | hero 8,000 (6,000-10,000); prop at most 600 | spec `lod0_tris` |
| 6 | Bake detail FROM the high-poly onto the low: tangent normal map plus ambient occlusion times the base colour; 2048 px for a hero, 1024 for a prop. | maps 2048 / 1024 px | spec `map_px` |
| 7 | Dilate the maps (every background texel takes the nearest chart texel) and generate mipmaps on import; otherwise black seams show at chart edges (city fix 2026-10-14, an internal task). | `maps_dilated: true` | spec |
| 8 | NEVER repaint or retouch the face by hand-painting over the baked map: a pasted or repainted face is the failure (the pasted statue faces were removed, da531aae). Fix a bad face by regenerating it first (own pass, own surface), not by painting. | `face_repainted: false` | spec |
| 9 | LOD chain: 1.0 / 0.25 / 0.125 / 0.0625 of LOD0 (city measured 8000/2000/1000/500/308). One glTF surface per part (head, body) so distance levels never thin the face to keep the cloak. | `lods` descending, LOD1 at most 0.30 of LOD0 | spec |
| 10 | Look from four sides (`look.py`) and in the world by day and night; commit the shots; the reviewer is not the author. | `shots` list has day and night | spec |

Licence step (all tiers): record the tool, version and licence of every generator in the spec
(`generator.licence`). Output of some models cannot be used in some regions (Hunyuan3D-2 output:
not in the EU, the UK or South Korea, Tencent community licence). Model weights are never shipped.

## Prop: seven steps

1. Silhouette first, in at most 600 triangles at LOD0 (barrel 120-200, crate 12-60, bollard 80-150).
2. `weld.py`, then `closure_audit.py` (props are seen from all sides, so open edges fail).
3. Detail in the 1024 texture: painted albedo and, only if it reads, a normal map baked from a
   throwaway high-poly (`bake_normals.py`). Props that move get `bake_vertex_ao.py`; static
   props get `bake_unlit.py`. Never both on one model.
4. Share one atlas across the props of a quarter (`atlas.py`, 1024): one material, one draw call.
5. `lods.py -- prop.glb prefix --budget 600` and keep the report.
6. Prefer textures to vertex colours: browsers before the iamar browser source (not public) d7d034da ignore `COLOR_0`
   in world packages (recipe `gltf_texture_colours`: WORKS from d7d034da on, FAILED before).
7. Place with `objects[]` (`collision: box`), shoot day and night.

## Spec file and check

`statue_spec.json` (one per statue or prop) is the evidence the checker reads; its example is
`kit/examples/harbour_extension/founder_statue.spec.json`.

```
python3 kit/examples/check_statue_spec.py kit/examples/harbour_extension/founder_statue.spec.json   # STATUE_SPEC_OK
python3 kit/tests/examples/check_statue_spec_test.py                                                # seeds one fault per rule
```

## What each tier can reach

| Tier | Statue | Prop |
|---|---|---|
| 0 (Blender, procedural) | stylised sculpt by hand or sculpt modifiers; 8k hero reachable, slower | all of it |
| 1 (hosted or API image-to-3D) | image to a 40-100k mesh in minutes; steps 3-10 still local in Blender | all of it |
| 2 (local GPU: SDXL, Hunyuan3D-2, UltraShape) | the city's pipeline: concept (SDXL) -> shape (about 80k faces, 2-3 min on an 11 GB GPU) -> decimate to 8k -> bake | not needed |

Fallback when no GPU: make the concept by hand, use a hosted image-to-3D service you have the
licence for, or model a stylised statue in Blender; do steps 4-10 unchanged.

## Face-first budget split (iamar STATUE PROTOCOL, the maintainer 2026-10-17/18; engineering)

Evidence: an internal memory record (protocol, 10 steps), `7ff3ba89` and `e02c811f` (strip what costs
triangles), `53c1c084` and `85eec7b0` (addenda), `f33ebbf9` (face likeness beats the 2.5k
face+head art-bar budget). Where this section differs from the 8,000 total above, this wins for
statues whose face shows: the 6,000-10,000 range still holds.

- The face is the key: it must look like the concept picture, gets the highest budget and is cut
  last and least in every LOD. Keep the neck.
- Cut the figure into face / hair-hat / body surfaces (one glTF primitive each, own LOD chain,
  locked seams) with one 2048 atlas, face charts at about 3x texel density. Budgets used:
  mage 4,000 / 1,700 / 4,000; healer and archer 3,000 / 1,500 / 3,500; bridge pair about
  2,500 / 1,000-1,300 / 2,700-3,000. A closed helmet or mask (face not shown): head about 1,000,
  spend the rest on the figure.
- Thin a dense face rim before the locked cut (face piece to about 9k faces, body to about 160k),
  or the rim eats the face budget and the face collapses into a triangle fan.
- Concept: cut the subject out and centre it at about 80 percent of a 1024 canvas; a subject
  touching the frame edge comes out as a flat relief sheet. Run the generator twice (full statue
  and a head close-up crop), pick the best face, and graft only the face and front of the neck
  onto the full run. Never paste a separate game hero face (rejected 2026-10-16) and never repaint.
- Say what was removed (base disc, rocks, danglers) and the triangles saved; say whether a shot
  shows the full-detail mesh or the cut-down game mesh.
- Generator used (Tier 2): Hunyuan3D-2.1 shape, octree 512 (768 gives the same face, 1024 needs
  more than 16 GB RAM), one run at a time under a memory cap and low priority.
