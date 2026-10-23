# Hardware tiers in world packages

A world is built once, with quality tiers inside it, and each visitor's browser
uses the tier its GPU can carry: a weak laptop runs it smoothly, a strong GPU
shows it at its best (the maintainer, 2026-10-01). This adds to the package format in
[WORLD_FORMAT.md](WORLD_FORMAT.md); a world without tiers works exactly as before.

| tier | for | budgets |
|---|---|---|
| `low` | an Amber-class GPU (Radeon HD 5750, 1 GB VRAM) at 30 fps; what everyone can show | `manifest.budgets` |
| `medium` | a mid-range laptop or older desktop GPU | `manifest.budgets` + `tiers.medium.budgets` |
| `high` | a mid-range desktop GPU at 60 fps | + `tiers.high.budgets` |
| `ultra` | a strong GPU, no cap beyond 60 fps | + `tiers.ultra.budgets` |

## Layout

The package's own files **are the low tier**. A richer tier only adds variants of
the media files (models and images) under `tiers/<tier>/`, at the same relative
path:

```
myworld/
  manifest.json
  scene.json
  assets/house.glb                 low: 2k triangles, 512 px textures
  textures/grass.png               low: 512 px
  tiers/medium/assets/house.glb    8k triangles, 1024 px
  tiers/high/assets/house.glb      the source: 30k triangles, 2048 px
  tiers/high/textures/grass.png    2048 px
```

`scene.json` always names the plain path (`assets/house.glb`). At tier T the
browser uses `tiers/T/<path>` if it is there, else the nearest lower tier's
variant, else the plain file (`WorldTiers.resolve`). So a tier may leave out any
file it does not improve, and a browser that knows nothing of tiers opens the low
tier. Audio, scripts, the heightmap and everything else are shared by all tiers.

## manifest.json

```json
"budgets": {"triangles": 150000, "texture_size": 1024, "texture_bytes": 67108864, ...},
"tiers": {
  "medium": {"budgets": {"triangles": 400000, "texture_size": 2048}},
  "high":   {"budgets": {"triangles": 900000, "texture_size": 2048, "texture_bytes": 268435456}}
}
```

* `tiers` is optional. Its keys are `medium`, `high`, `ultra`; `low` (the
  package itself) may also be listed, but only to set switches — never
  `budgets`, which are always `manifest.budgets` for the low tier; keys
  starting `x-` are ignored (`WorldTiers.validate`).
* A tier may set `budgets` for `triangles`, `objects`, `texture_size`,
  `texture_bytes` and `lights`; the rest always come from `manifest.budgets`. A
  tier's budgets are `manifest.budgets` with every declared tier up to it laid
  on top (`WorldTiers.budgets`), and the browser checks the tier it opens against
  them the same way it checks a one-tier world.
* A tier may also set switches (`low` included); a tier without one takes the
  nearest lower tier's (`WorldTiers.switch`):
  * `shadows` (default `true`): `false` turns off the sun's and the lights'
    shadows at that tier, a large saving on old GPUs;
  * `normal_maps` (default `true`): `false` makes the kit drop normal maps from
    that tier's models.

  ```json
  "tiers": {"low": {"shadows": false, "normal_maps": false}, "medium": {"shadows": true, "budgets": {...}}}
  ```
* A visitor gets the best tier the world declares that does not exceed the tier
  the browser chose (`WorldTiers.pick`): a world with only `low` and `high`
  gives a medium visitor the low tier.

## Detail that only better GPUs draw

Any entry in `scene.objects` or `scene.primitives` may carry `"min_tier"`
(`low`, `medium`, `high` or `ultra`): it is drawn only at that tier and better.
Use it for clutter, extra foliage, small props and decorations: the low tier stays
a complete, pleasant world, and denser scenery lights up on richer GPUs. Below
its tier the entry is left out before anything is loaded, so its model is not
downloaded into memory, does not count against that tier's budgets and is not
built (`WorldTiers.shows`).

```json
{"id": "fern_12", "asset": "assets/fern.glb", "position": [4, 0, 9], "min_tier": "medium"}
```

## Impostor cards for distant models

A scene object with `"impostor": <metres>` is drawn as its model up to that
distance and as a flat card beyond it (`WorldImpostors`): the card turns to face
the eye, shows the picture taken from the nearest of 8 sides, and is lit through
the captured normals, so it follows the sun. Use it on big, often-seen far
models (buildings, rocks, trees in the distance); a card is 2 triangles and one
draw call. The kit renders the pictures (this needs a display; on a server use
`offscreen`):

```bash
iamar-world impostors myworld [--px 128]   # writes impostors/<asset>.{albedo,normal}.png and .json
iamar-world tiers myworld                  # then each lower tier gets smaller pictures
```

The pictures are ordinary package images: they count against `texture_size` and
`texture_bytes` (an atlas is 8 x px wide, so keep `--px` x 8 within the low
tier's `texture_size`). An object whose pictures are missing stays its model.
There is no cross-fade at the hand-over (on the compatibility renderer it would
make both transparent); a 5 % margin keeps them from flickering.

## The browser

Oakhaven's graphics presets are tiers (`Graphics.tier()`, `GpuTier.tier_for`):
Fast is `low`, Balanced `medium`, High `high`, and High on a strong discrete GPU
(RTX 2080 Ti class) `ultra`. The first run starts from the preset the GPU's class
suggests (`GpuTier.start_preset`; Amber's HD 5750 is Fast/low), the frame-rate
check steps it down, and the settings keep the preset with the tier it draws on
this GPU (`[graphics] preset`, `tier`, `gpu`); the menu shows the tier when it is
not the preset's own ("High (ultra)", `Graphics.label()`). The browser loads only the variant files its tier
resolves to (`WorldTiers.files_for` lists them, which is what a per-tier download
fetches: a low-tier visitor never needs anything under `tiers/`, a high one skips
the low copies of files it has high variants for). Choosing the preset from the
hardware and adapting it live to the frame time is Oakhaven item 20; this format
only says which files each tier uses.

## The kit builds the lower tiers

Build one high-quality version, put its tiers in the manifest, then:

```bash
godot --headless --path <oakhaven> -s res://scripts/kit/world_tiers_build.gd -- myworld   # or: iamar-world tiers myworld
```

The top tier's files are the source: on the first run the package's own files
are kept as `tiers/<top>/<path>`; after that `tiers/<top>/` is what you edit (or
re-export from Blender). For every model and image the scene uses, each lower
tier gets a copy made to fit its budgets:

* models: triangles cut to the tier's share of the top tier's real triangle
  count (Godot's meshoptimizer simplifier, as its import LODs use; vertices, UVs,
  skin weights and animations are kept, only triangles go). A world already under
  a tier's budget keeps every triangle there;
* small parts (surfaces under 600 triangles) and models placed with
  `collision: "mesh"` or `"convex"` keep every triangle: cutting them saves little
  and breaks the shape or the walk surface;
* textures (embedded in models, and the scene's images) halved until they fit
  the tier's `texture_size`; files that already fit are copied byte for byte;
* a variant that comes out identical to what the tier below uses is not stored
  (resolution falls back to it), and when every tier is the same the originals
  stay at their own paths. Until per-tier downloads exist every stored variant
  adds to the package, so declare tiers only where they differ;
* normal maps dropped where the tier says `normal_maps: false`.

`iamar-world pack` and `publish` run it for you first whenever the manifest declares
`tiers` (a tier over its budgets stops the pack; `IAMAR_NO_TIERS=1` skips the step).
It prints one line per tier and exits 1 when a tier is over its budgets:

```
TIER low    triangles=14112/20000 texture_size=512/512 texture_bytes=1572864/8388608 OK
TIER medium triangles=28224/40000 texture_size=1024/1024 texture_bytes=6291456/16777216 OK
TIER high   triangles=28224/80000 texture_size=2048/2048 texture_bytes=25165824/33554432 OK
```

The numbers are counted the way the browser counts them when it opens the tier, so
`tiers`, `validate` (its `STATS` and `TIER` lines) and `materials.py budget` give the same
totals for one folder: triangles of every model placement (objects and their attachments,
NPCs and theirs, quest look models), plus primitives, terrain, water and creatures (1200
per animal); texture memory as width x height x 4 for every image embedded in a model (a
map several materials share is one image, each .glb once however often it is placed) and
every scene image (sky faces, terrain and primitive textures, the heightmap, impostor
cards). A model reused by hash from outside the folder is not tiered and `tiers` does not
count it (an `INFO` line names it).

`validate` opens every tier against its own budgets (one `TIER` line each), and
`preview` / `perf` take `--tier low|medium|high|ultra` to look at and measure
one tier.

Design for the low tier first: it must stay pleasant, not just functional, since
it is what most visitors may see. Then let detail light up on better GPUs.

## Not yet

* Splitting the packed world into a base piece set plus one per tier, so a visitor
  downloads only its tier (needs a signature that covers files a visitor did not
  download; to be agreed with the networking/download owner).
* Effect switches beyond shadows (the format has no post effects yet).

Tests: `tests/world_tiers/run.sh`: the rules and the builder on a generated world
(`test.gd`), then, in an imported project, the real loader and builder on a tiered
world (`package_test.gd`: variant files and budgets per tier, `min_tier`, shadows,
impostor pictures rendered and the card swapped in past its distance; it renders,
so it runs under `offscreen` when there is no display).

