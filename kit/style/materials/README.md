# Painted material library, texel-density rule, texture budget (A10)

Fifteen seamless, hand-painted-style colour maps that any style can use, a rule for how
sharp near surfaces must be, and a check of a world's texture memory. Engineering layer:
the rule and the budget apply to every world; the tints are style and come from the
world's profile (`../README.md`).

| Path | What it is |
|---|---|
| `library/*.jpg` | The 15 maps (the city's 13 plus `grass` and `sand`): 1024 px, 4 m per tile = **256 px per metre**, painted around a warm neutral grey (mean ~0.6) |
| `library.json` | Per map: kind, roles, file, sha256, mean colour; the rule, the budget, licence and origin |
| `materials.py` | `list`, `check`, `build`, `use`, `texel`, `budget`, `sample` (below) |
| `sample_world.jpg` | The sample world in the browser (eye height and from above) |
| `../../tests/style/materials/materials_test.py` | Tests: 30 checks, the browser-validated sample included |

Maps: `stone ashlar granite plaster timber` (walls), `slate slate_dark glazed shingle thatch`
(roofs: v runs down the slope, image top = ridge), `cobble` (street ground), `grass` (meadow turf) and `sand` (rippled sand and dust) for terrain bands beyond the streets, `iron` (straps, lamps),
`trim` (trim sheet: 8 strips cornice, frame, moulding, carved, dentil, rope, beam, strap, each
1/8 of the height, tiling along u). All are from `kit/tools/paint_materials.py`, the city's own
painted look (`the iamar browser source (not public)` `scripts/world/masterplan/mp_materials.gd`: 13 layers incl. the
trim sheet, one Texture2DArray at 256 px per metre).

## Use it in a world

```
python3 kit/style/materials/materials.py use worlds/my_world --profile worlds/my_world/style.json
```

writes `textures/materials/<material>.jpg` for every `materials.layers` entry of the profile,
each library map's mean colour scaled to the entry's `tint` (the painter's own `--tint`
rule), and the trim sheet's strips tinted to `materials.trim_sheet.looks`; plus
`textures/materials/materials.json` and a `credits` entry in `manifest.json`. `--size 512`
or `256` for a low tier, `--only a,b` for some. Works for any profile: the iamar one, an
`"extends": "iamar"` one, or a brand-new one such as
`../schema/examples/desert_trading_post.style.json`.

Then:

- **Primitives and terrain layers:** `"texture": "textures/materials/wall_plaster.jpg", "uv_scale": 4`.
- **Models:** in Blender use the map as Base Color and UV-map at **1 UV unit = 4 m** for
  1024 maps, **2 m** for 512 maps (`kit/blender/` trim and atlas tools), export .glb, then bake
  light with `kit/blender/bake_vertex_light.py` (below). Not `bake_unlit.py`: it replaces the
  painted map by one 10-40 px/m light texture, which fails the texel rule.

## Painted maps and baked light in one package (an internal task)

A glTF material has one colour texture, and the browser reads no second (lightmap) texture.
So the light goes into the vertex colours and the painted map stays the base colour:

```
python3 kit/style/materials/materials.py use worlds/my_world --profile <profile> --size 512
#   Blender: model, UV 1 unit = 2 m (512 px / 2 m = 256 px/m), export in.glb
iamar-world blender-run kit/blender/bake_vertex_light.py -- in.glb worlds/my_world/assets/house.glb
python3 kit/style/materials/materials.py texel worlds/my_world      # TEXEL_OK
python3 kit/style/materials/materials.py budget worlds/my_world --profile <profile>   # BUDGET_OK
```

`bake_vertex_light.py` cuts the static meshes on a 1 m grid (`--grid`), bakes sky, sun, bounce
and lamps with Cycles into COLOR_0, and exports the original materials unlit; the browser
draws map x COLOR_0 as-is (`docs/WORLD_FORMAT.md` section 5, checked headless with Godot's
GLTFDocument: unshaded, map and colours kept). Shadows are only as sharp as the grid, and
triangles grow with it (a 6 x 5 m house: about 1,000 at 1 m, 3,000 at 0.5 m). Make LODs from the
unbaked model and bake each level; decimating a baked model removes the light. Recipe
`bake_vertex_light`; test `kit/tests/blender/vertex_light_test.py` (five such houses on a cobble
square pass `texel`, `budget`, `lint` and `audit all`; about a minute on a 4-thread CPU).

## How to share maps between models (the one consistent rule)

Texture memory is counted `w x h x 4` bytes per image: a 1024 px RGBA map costs 4 MiB, a
512 px map 1 MiB. The world budget is 64 MiB (`budget.world_texture_bytes`), so a world can
hold at most sixteen 1024 px maps in total, or sixty-four 512 px maps. Five houses with four
1024 maps each are 80 MiB: over budget. Five houses with four 512 maps each are 20 MiB: fine.

How the counts share (the same way the browser, `iamar-world tiers` and `validate` count):

- A `.glb`'s embedded images are counted once however often the model is placed: placing the
  same `.glb` a hundred times costs the same as placing it once.
- Scene images (primitive and terrain textures, heightmap, the faces of a cubemap sky,
  rendered impostor cards) are counted once however many use them: terrain and primitives can
  share image files freely.
- The same image embedded in **several different** `.glb` files is counted once **per**
  `.glb`: every copy is paid again. This is the only place maps get duplicated, and it is
  where worlds overflow the budget.

So the rule is: **never embed the same map in two `.glb` files.** Share maps across models in
one of two ways, and do not mix them:

1. **One multi-model `.glb`** for models that belong together: a generated street row built
   by `iamar-world style-gen street` (`kit/style/gen/README.md` "Streets") packs every house
   into one file, each its own root node, so the painted maps are embedded once (81 to
   60 MiB in the harbour blind test). This is the only sanctioned exception to "one model
   per file" (`docs/WORLD_FORMAT.md` section 5); the exception exists because a street's
   houses share all their maps.
2. **One model per file with 512 px maps** for everything else: 512 maps tiled every 2 m
   hold 256 px/m like a 1024 map at 4 m (the cost is a 2 m repeat instead of 4 m), and one
   model per file keeps `lint`'s per-model triangle budget meaningful.

If you outgrow the exception (a second street with the same painted maps), split the shared
maps out into scene image files (counted once) instead of embedding a second copy.

### When the budget ERROR names your asset

`iamar-world validate` prints the per-asset check as

    ERROR assets/basket.glb: glTF images need 524288 bytes of texture memory, over the budget of 434176

(the exact wording lives in `the iamar browser source (not public)`; the kit cannot change it). It means: that one
`.glb` alone embeds more image bytes than its tier allows. The fix, in order:

1. If other models share those maps, pack them into one multi-model `.glb` (street.py or by
   hand) so the maps are embedded once.
2. Else drop the maps to 512 px tiled every 2 m (`materials.py build --size 512`): same
   256 px/m, quarter the memory.
3. Re-run `materials.py budget` and `iamar-world validate` to confirm the asset is under.

`materials.py budget` also warns when the same image is embedded in several models: treat
every such warning as a future budget overflow.

Rebuild a map with `materials.py build` (repaints all 13, about 75 s; the painter is
deterministic). `materials.py check` fails when a map is missing, its hash or mean colour
drifts from `library.json`, it does not tile, or it is no longer neutral.

## The texel-density rule

**Every near surface shows at least 256 texels per metre (20 % tolerance: 205).** Near means
LOD0 of anything a visitor walks up to: buildings, props, ground, walls, terrain layers,
textured primitives. Far LODs (node or mesh names with `LOD1` ... `LOD9`) need a quarter
(64, tolerance 51). More than 1024 px/m is a warning: nobody sees those texels.

```
python3 kit/style/materials/materials.py texel worlds/my_world     # or model.glb ...
OK    glb       my_world:assets/house.glb house/plaster: 251 px/m
ERROR glb       my_world:assets/well.glb well/stone: 63% of the surface is under 205 px/m (mean 140 px/m): ...
TEXEL_FAIL 14 surfaces, 1 under the rule
```

For a .glb it measures every textured triangle (UV area x texture pixels against its area in
metres, after node transforms, `KHR_texture_transform` scale and the object's `scale` in
`scene.json`) and fails a primitive when more than 10 % of its area is under the rule. For
primitives and terrain layers it is texture width / `uv_scale`. Exit 1 on any failure.
A palette-swatch primitive (over 90 % of its area maps each face to one texel of a colour strip,
as the catalogue's harbour set does) has no density to judge: it is listed as `OK palette`.
An unchanged catalogue model from the iamar city (catalogue `source.origin` `city`, matched byte
for byte) keeps the city's own painting, about 128 px/m on most props: under the rule it is a
`WARN ... exempt` line, not an error. Change the file and it is judged like any other.
Merging is a change: a city prop joined into another .glb (a "dress_clutter.glb" of many props,
AGENT_KIT step 7) is no longer the catalogue's bytes, so its surfaces fail the rule there
(harbour a5 G10: a merged market stall at 104 px/m, trestle table 129, planter 141). Keep city
catalogue props as separate unchanged files placed by `scene.json` (the browser instances
repeats of one file, so this costs little) and merge only your own props painted at the rule
or with palette swatches. A city prop you must merge has to be repainted to the rule first.
An asset listed in `manifest.json` `reused` (`iamar-world assets use <hash> --as <path>`) is
judged on the kit's copy, as lint and audit do.
Why 256: the city paints every near surface at it; a surface at 128 px/m looks blurry next to
it. How to meet it: 1024 px map per 4 m, or a trim sheet / atlas at the same density.

## The texture budget

```
python3 kit/style/materials/materials.py budget worlds/my_world
texture memory 52.0 MiB (69.3 MiB with mipmaps) of 64.0 MiB; largest 1024 px of 2048
BUDGET_OK
```

Counts as the browser does, and as `iamar-world tiers` and `validate` do (w x h x 4 per
image; each .glb once however often it is placed: objects, attachments, NPC models and theirs,
quest look models; each scene image once: primitive and terrain textures, heightmap, the faces
of a cubemap sky, rendered impostor cards). It counts texture memory only; triangles are in
`validate` and `tiers`. Fails when the
total exceeds the manifest's `budgets.texture_bytes` or the library's
`budget.world_texture_bytes` (64 MiB), or the largest image exceeds `budgets.texture_size` or
2048. A `reused` asset counts the kit's copy; a reused built-in object (no file in the kit) is
an INFO line, its maps ship with the browser. Warns for a non-power-of-two image, a model embedding more than 4 MiB (one 1024 map),
and the same image embedded in several models (each copy is paid again: use 512 maps at 2 m
for models, above). A profile may set
`materials.texture_budget` (same keys as `library.json` `budget`) and pass `--profile`.
Why 64 MiB: the city's 13 shared 1024 layers are 52 MiB; a building from
`iamar-world assets building` embeds about 17 MiB of its own
(`../lighting/README.md`), so four of them already pass it: share library maps instead.
Tiers: `iamar-world validate` checks each tier's `texture_size` / `texture_bytes`
(`docs/WORLD_TIERS.md`); `use --size 512` makes the low-tier maps.

## The sample world

```
IAMAR_KIT_PACK=<tools/build_pack.sh output> python3 kit/style/materials/materials.py sample out/materials_sample \
    --godot <godot 4.7 or iamar browser> --project <the iamar browser source (not public) checkout> [--profile iamar] [--shot out/shots]
```

The kit starter plus one 4 m wall per material (tinted by the profile) and a cobble square,
validated by the browser (`--kit validate`); `--shot` renders three views with `--kit preview`.
Verified 2026-10-20 on zoe (Godot 4.7.2, Intel Arc 140V, the iamar browser source (not public) 569b91a6): validated,
`texel` 13 surfaces OK at 256 px/m, `budget` 52.0 MiB of 64 MiB, worst frame 1.3 ms
(`sample_world.jpg`).

## Licence

Original: every pixel is painted by `kit/tools/paint_materials.py` from periodic noise and block
layouts; no photographs, third-party textures or generated-model input. The licence is the
iamar project's own, **not yet chosen by the maintainer** (`kit/inventory/licences.json` row
`original-procedural`); `use` writes that into the world's `credits`. Nothing here is a
third-party asset, so no attribution is owed.

## Traps

- A naive seam test (wrap-around step vs the *average* step) flags every roof and the iron
  plate: their tiles put a course joint on the wrap, by design. Compare with the strongest
  step inside the tile instead (`check`). FAILED first, fixed in this job.
- A package cannot ship shaders: these are plain Base Color maps, and light comes from the
  world's environment or a Blender bake (the city's `mp_painted.gdshader` patterns do not
  travel; see an internal task).
- FAILED (harbour blind test attempt 3, `kit/blindtest/harbour/attempt-3/gaps.md` G5, G6): `bake_unlit.py`
  on a painted house. The bake replaces the painted map by colour x light at `--texel` (10-40
  px/m), so `texel` fails; 256 px/m would need a 4096+ texture per house. The builder gave up
  baked light. Use `bake_vertex_light.py`.
- Primitives use world-space triplanar mapping with `uv_scale` metres per repeat
  (`the iamar browser source (not public)` `scripts/worlds/world_builder.gd`); terrain layers default to `uv_scale` 4,
  primitives to 1 (a 1024 map at the default 1 is 1024 px/m: say `"uv_scale": 4`).
