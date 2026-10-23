# Recipe `hero_statue`: a carved-stone statue on a plinth in five minutes

A square or a gate with a statue needs one that reads as carved, weathered stone. The harbour
blind test built its own: a 552-triangle flat-orange figure on a box, no face, no material (review
FAIL row "sailor statue", an internal task). The full hero route (`kit/examples/STATUE_PROP_PROTOCOL.md`:
concept, 80k sculpt, 8k bake, 2048 maps) is the best result and needs a GPU or hours. This recipe
is the Tier 0 route that still passes: a catalogue figure on the catalogue plinth, painted with
the library's stone maps at the texel rule, weathered (darker folds, grime rising from the feet, rain
streaks, lichen on the low upward faces, in COLOR_0 and the figure map), with the cloak carved as a
closed 4 cm slab (closure audit 0), lit live by the world's sun and sky.

Layer: engineering (any world); the stone maps are style (pass your profile's tinted maps).
Tier 0: Blender 4.2-5.0 on any CPU. Status: WORKS (test below; shots in the real preview, iamar.26 day and dusk, in `docs/evidence/job3279/`; the solid coat and weathering, before and after, in `docs/evidence/job3362/`).

## Steps

```
# 1. figure + plinth, one mesh, UV-mapped at 256 px/m, two painted stone materials
iamar-world blender-run kit/recipes/statue/statue.py -- worlds/<world>/assets/statue.glb
#    STATUE_OK ... 2320 tris 2.90x4.90x2.90 m map 512 px, 2.0 m per tile (256 px/m) solid sheet faces 122 weathered
# 1b. closed: no open edge, no non-manifold edge, no inside-out part
iamar-world blender-run kit/blender/closure_audit.py -- worlds/<world>/assets/statue.glb --ground 0.02
# 2. look at it from four sides
iamar-world blender-run kit/blender/look.py -- /tmp/look worlds/<world>/assets/statue.glb
```

Place it with `objects[]` (`"collision": "mesh"`), on the axis of a street or in the middle of a
square, and add a `statue` camera to `shots.json` 4-6 m away at eye height (day and dusk shots
in `docs/evidence/job3279/`).

Check: `iamar-world lint` classes it `hero_statue` (8,000 budget: 2,320 passes);
`iamar-world materials texel` and `materials budget` pass (two 512 maps, about 2 MiB). List it
among the live-lit objects in the world's report (AGENT_KIT step 4).

Optional: bake the light into the vertex colours for the dark in the folds and under the arms
(the browser keeps the painted map and draws it unlit):
`iamar-world blender-run kit/blender/bake_vertex_light.py -- statue.glb baked.glb --grid 0.5`
(about 6,000 triangles, under the 8,000 budget). The city figures' cloaks are open sheets.
`statue.py` makes each one a closed 4 cm slab (an internal task: before, a flipped copy 1 cm out, which
read paper-thin edge-on in the harbour a4 review), so both sides of the cloak are drawn, and the bake has turned double-sided faces that point into the body
to their open side since an internal task. Before that, about 400 cloak faces baked black and
iamar.26 showed a black cloak from behind (an internal task). `kit/tests/blender/bake_vertex_light_sheet_test.py`
bakes this recipe and finds at most one visible face under 0.05 (a 12 cm2 face of a hair tuft at the head top). That check is in Blender: the baked
statue has not been looked at in the real preview yet.

## Options (`statue.py -- out.glb ...`)

| Option | Default | What |
|---|---|---|
| `--figure GLB` | `kit/catalog/assets/landmarks/hero_w1.glb` (knight with sword, 3.3 m, 1,906 tris) | any figure; `iamar-world assets search statue` lists more (`hero_e1.glb`: spear and shield, 5.4 m) |
| `--plinth GLB` | `.../statue_bridge_1.glb` (round two-step plinth, 1.6 m) | or `none` |
| `--scale S` | 1.0 | scales the figure only |
| `--figure-texture IMG` | `kit/style/materials/library/plaster.jpg` | an even, mottled stone. Not a block map (`stone.jpg`, `ashlar.jpg`): masonry courses across a body read as bricks |
| `--plinth-texture IMG` | `library/ashlar.jpg` | cut courses suit the plinth |
| `--size N` | 512 | map size; the UVs follow (1 unit = N/256 m) |
| `--no-weather` | off | no weathering: plain map, no COLOR_0 |
| `--name NAME` | statue | node and material names; keep *statue* in it so lint uses the statue budget |

For a world with its own palette, pass its tinted maps from
`python3 kit/style/materials/materials.py use worlds/<world> --profile <profile> --size 512`
(`textures/materials/<material>.jpg`).

## Limits

The figures are the city's posed base-body statues: a plain face, no carved detail beyond the
silhouette. For a named hero of the world (the founder, a saint), follow the full protocol.

## Test

```
python3 kit/tests/recipes/statue_portal_test.py     # builds and checks both recipes in one world
```
