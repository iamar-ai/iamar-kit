# iamar world package format, version 0

This document is written for **AI agents that build iamar worlds**, and for
the people who review them. It says exactly what files a world is made of,
what every field means, what the browser does with it, and how to check your
work. Where this document and the JSON Schemas in `schemas/` disagree, the
schemas win; please report the mismatch.

* `schemas/manifest.schema.json` - `manifest.json`
* `schemas/scene.schema.json` - `scene.json`
* `schemas/signature.schema.json` - `signature.json`
* `schemas/pieces.schema.json` - the piece list of a packed `.iamar` (section 9a)

A world never contains engine code or engine files. It is glTF models,
PNG/JPEG images, Ogg audio, two JSON files and, optionally, world scripts written
in TypeScript (built into sandboxed WebAssembly, `scripts/*.wasm`).
The iamar browser happens to be built on Godot today; nothing in a package
may depend on that (no `.tscn`, `.tres`, `.import`, `.gd`, Godot class names,
node paths or `res://` paths).

The 2009 iamar client worked the same way: a world was a folder of media and a
`.sem` script that the browser downloaded from the host on entry. `scene.json`
replaces the `.sem` script's scene-building calls (`createLevel`,
`createSkyBox`, `setAmbientLight`, `createAnimatedObject`, ...); the behaviour
calls (`setPlayerEnterFunc`, signals) move to the sandboxed scripts.

---

## 1. Package layout

A package is a folder, or the same folder zipped into one file named
`<id>.iamar` (plain zip, files at the root of the archive, no enclosing
folder).

```
myworld/                        or  myworld.iamar (zip of the same)
  manifest.json                 required: who, what, budgets, features
  scene.json                    required: the world, as data
  signature.json                optional (required to be "trusted"): see section 9
  assets/*.glb                  binary glTF 2.0, textures embedded
  textures/*.png|jpg            sky faces, terrain layers, primitive textures, heightmaps
  audio/*.ogg                   Ogg Vorbis
  scripts/*.wasm                world scripts, written in TypeScript and built here (section 10)
  thumbnail.png                 optional, 512x288 suggested
  LICENSE, CREDITS.md           optional text files, ignored by the loader
```

Rules for every path inside the package:

* Relative, forward slashes, no `..`, no leading `/`, no `//`, at most 200
  characters, characters `A-Z a-z 0-9 _ . / -` only. Paths are
  **case-sensitive**.
* Models must be `.glb` (binary glTF with embedded buffers and images). A
  `.gltf` with side files is not accepted in format 0.
* Images must be PNG or JPEG. Audio must be Ogg Vorbis.
* Files and folders whose names start with `.` are not part of the package.
* Other files (`.md`, `LICENSE`) are allowed and ignored, but they count
  toward `package_bytes` and they are covered by the signature.
* Zips: plain stored or deflate entries, no ZIP64, encryption or multi-disk;
  at most 4096 entries, 12 folders deep, 256 MiB per file uncompressed and a
  compression ratio of at most 100:1 for files over 1 MiB. JSON files: valid
  UTF-8, nesting under 64, every number finite; positions within 100 km.
* glTF: everything embedded (no external `uri` for buffers or images), the node
  graph a tree, images within `texture_size`. Text in the manifest and scene is
  shown as plain text: `[` and `]` become `(` and `)`, control and bidi
  characters are removed (the iamar browser source (not public) `docs/SECURITY.md`).

## 2. Conventions

* **Units:** metres. A standing adult is about 1.7-1.9 m.
* **Axes:** right-handed, **+Y up**, **-Z forward** (glTF's axes). North is -Z
  by convention, east is +X.
* **Angles:** degrees. `yaw` is a rotation about +Y: `0` faces -Z, `90` faces
  -X, `180` faces +Z, `-90` (or `270`) faces +X.
* **`rotation`** is `[x, y, z]` Euler degrees, applied yaw (Y) first, then
  pitch (X), then roll (Z), all about the object's own axes.
* **`scale`** is a number (uniform) or `[x, y, z]`.
* **Colours:** `"#rrggbb"` or `"#rrggbbaa"`, sRGB. (NPC `look` colours are
  bare `"rrggbb"`, as in Oakhaven.)
* **Positions** are `[x, y, z]`. Things that stand on the ground (spawn
  points, NPCs, creatures, portals) are dropped onto whatever collision is
  below them, so their `y` only has to be at or a little above the ground.
* **Ids** are lowercase `a-z 0-9 _ -`, start with a letter or digit, at most 64
  characters, unique within their section.
* Unknown keys are errors (they are almost always typos), except keys that
  start with `x-`, which every reader ignores, in any object. Use `x-` for
  your own notes.

## 3. manifest.json

```json
{
  "format": "iamar-world",
  "format_version": 0,
  "id": "mission_hall",
  "name": "The Mission Hall",
  "description": "A circular hall where mission-givers wait.",
  "author": {"name": "Ada Author", "owner": "ada"},
  "version": "1.0.0",
  "api_version": "0.4",
  "scene": "scene.json",
  "spawn": "default",
  "budgets": {"triangles": 150000, "objects": 64, "texture_size": 1024,
              "texture_bytes": 33554432, "lights": 4, "package_bytes": 16777216,
              "audio_bytes": 4194304, "script_bytes": 0},
  "features": ["sky", "objects", "lights", "npcs", "portals", "animation"],
  "optional_features": ["sounds"],
  "scripts": [],
  "license": "CC-BY-4.0",
  "credits": [{"files": ["textures/sky/*"], "author": "Johannes Schloerb", "license": "free use with credit", "source": "http://www.schloerb.com"}],
  "signer": {"name": "Ada Author", "key_id": "rsa:0123456789abcdef0123456789abcdef"}
}
```

| field | required | meaning |
|---|---|---|
| `format`, `format_version` | yes | always `"iamar-world"` and `0` |
| `id` | yes | the world's id: the local id and the `<world>` of `iamar://<owner>/<world>` |
| `name`, `description` | name | shown in the address bar and the world list |
| `author` | yes | `name`; optional `owner` (hub account) and `contact` |
| `version` | yes | semver of this world, e.g. `1.2.0`; bump it on every publish |
| `api_version` | yes | world API the package targets, `major.minor` (browsers refuse a newer minor: see section 8). The current API is `0.4`; declare the oldest version that has every function your scripts use |
| `scene` | no | scene file, default `scene.json` |
| `spawn` | no | a `spawn_points` id, or `{"position": [x,y,z], "yaw": deg}`; default: the spawn point `default`, else the first one, else the origin |
| `budgets` | yes | see section 8 (these are the low tier's) |
| `tiers` | no | hardware tiers `medium` / `high` / `ultra` with their own budgets and variant files under `tiers/<tier>/`: see [WORLD_TIERS.md](WORLD_TIERS.md) |
| `features` | no | built-in features the world needs (list below); a browser without one refuses to load the world. `world-experience-v1` is in the schema's feature enum for forward compatibility but current builds refuse it (see `experience` above) |
| `optional_features` | no | features the world uses but can do without |
| `scripts` | no | world scripts (TypeScript, built to `scripts/*.wasm`; section 10): `[{"path": "scripts/world.wasm"}]`. The schema also accepts `role` (`host`, `client` or `both`) and `entry` (a string, at most 64 characters), but the current browser does not read them: every script runs in every visitor's copy |
| `thumbnail`, `license`, `credits` | no | for the world list and for attribution |
| `signer` | no | who signed it; checked against `signature.json` |
| `reuse` | no | what other builders may reuse from this world: `{"allow": bool, "objects": {"assets/x.glb": bool}}`; default nothing (section 5a) |
| `reused` | no | objects this world uses by hash instead of carrying them (section 5a) |
| `techniques` | no | turn off kit recipes the browser applies to every world by default, e.g. `{"instancing": false}`; unlisted recipes stay on (`scripts/worlds/world_format.gd` does not read this; the kit does) |
| `experience` | no | world-experience block: `{"version": 1, "participation": "shared"`/`"solo"`, `"world_voice": "enabled"`/`"disabled"}`; accepted by `schemas/manifest.schema.json` but **refused by current builds** (`manifest.experience: world-experience-v1 activation is unavailable in this build`, `scripts/worlds/world_format.gd` `validate_manifest`) |

Feature names: `sky fog sun terrain water weather objects primitives lights
sounds portals triggers paths npcs creatures quests animation scripts`.

## 4. scene.json

Every section is optional. An empty scene (`{"format": "iamar-scene",
"format_version": 0}`) is a sky and nothing to stand on, so give it at least
terrain or a walkable object.

```json
{
  "format": "iamar-scene",
  "format_version": 0,
  "environment": {...},
  "terrain": {...},
  "water": [...],
  "objects": [...],
  "primitives": [...],
  "lights": [...],
  "spawn_points": [...],
  "sounds": [...],
  "portals": [...],
  "triggers": [...],
  "paths": [...],
  "npcs": [...],
  "creatures": [...],
  "quests": [...]
}
```

### 4.1 environment

```json
"environment": {
  "sky": {"type": "cubemap", "faces": {"px": "textures/sky/rt.jpg", "nx": "textures/sky/lf.jpg",
          "py": "textures/sky/up.jpg", "ny": "textures/sky/dn.jpg",
          "pz": "textures/sky/bk.jpg", "nz": "textures/sky/fr.jpg"}},
  "time_of_day": 10.5,
  "day_length_minutes": 0,
  "sun": {"enabled": true, "color": "#fff4e0", "energy": 1.0, "shadows": true},
  "ambient": {"color": "#666666", "energy": 1.0, "source": "color"},
  "fog": {"enabled": true, "color": "#c8d4e0", "density": 0.004},
  "weather": {"kind": "clear"},
  "exposure": 1.0
}
```

* `sky.type`: `procedural` (default: a blue gradient with a sun, tinted by
  `top_color`, `horizon_color`, `ground_color`), `color` (flat `color`), or
  `cubemap` (six images, `faces`). Cube faces use the OpenGL layout, each
  image being what you see from the centre of the cube:
  * side faces are upright (+Y at the top of the image): looking toward +X
    (`px`) the right edge of the image is -Z; toward -X (`nx`) it is +Z;
    toward +Z (`pz`) it is +X; toward -Z (`nz`) it is -X;
  * `py` (looking up): +X to the right, -Z at the top of the image;
  * `ny` (looking down): +X to the right, +Z at the top of the image.

  Faces should be square and equal in size. If the edges do not line up
  in the viewer, a face is turned or two faces are swapped (2009 Ogre
  skyboxes, for example, need `up`/`dn` turned 180 degrees and `lf`/`rt` as
  `px`/`nx`). `rotation` turns the cube about +Y, `energy` brightens it.
* `time_of_day` (hours, default 12) places the sun when `sun.direction` is
  absent: sunrise at 6 in the east (+X), noon high in the south (+Z side),
  sunset at 18 in the west. `day_length_minutes` > 0 lets time run
  (0 = time stands still, the default).
* `sun`: a directional light. `direction` is where the light travels
  (e.g. `[0.3, -1, 0.2]`). Default: enabled, white, energy 1, shadows on.
  Set `"enabled": false` for an indoor or night world lit by `lights`.
* `ambient`: light that reaches everything. `source: "sky"` takes it from the
  sky instead of `color`. Default `#808080`, energy 1, source color.
* `fog`: exponential fog; `height`/`height_density` add ground mist.
  `sky_affect` (0 to 1, default 0) is how much the fog also covers the sky:
  0 keeps a sunset or starry sky visible through light fog.
* `weather.kind`: `clear` (default), `cloudy`, `rain`, `storm`, `snow`.
  **Reserved in the v0 browser**: accepted and ignored until the runtime
  weather is promoted from Oakhaven.

### 4.2 terrain

```json
"terrain": {
  "type": "heightmap",
  "size": [256, 256],
  "position": [0, 0, 0],
  "heightmap": "textures/height.png",
  "min_height": -4, "max_height": 30,
  "resolution": 129,
  "materials": [
    {"texture": "textures/sand.jpg", "uv_scale": 4, "min_height": -100},
    {"texture": "textures/grass.jpg", "uv_scale": 6, "min_height": 0.5},
    {"texture": "textures/rock.jpg", "uv_scale": 8, "slope": true}
  ],
  "collision": true
}
```

* `type`: `none` (default when the section is absent), `flat` (a plane at
  `position.y`), `heightmap` or `procedural`.
* `size` `[x, z]` metres, centred on `position` (default `[256, 256]`).
* `heightmap`: greyscale PNG/JPEG. Black is `min_height`, white is
  `max_height` (relative to `position.y`). The top row of the image is the
  -Z edge, the left column is the -X edge.
* `procedural`: `{"seed": 7, "amplitude": 12, "frequency": 0.01,
  "octaves": 4, "flat_radius": 40}` - smooth rolling hills. The exact shape is
  the browser's noise and may differ slightly between browser versions; use a
  heightmap if a spot must be exact.
* `resolution`: vertices per side (default 129; at most 1025). Triangles =
  2 x (resolution - 1)^2 and count toward the budget.
  The heightmap is sampled only at the vertices, so the ground slopes between
  them: a vertex every `size / (resolution - 1)` m (320 m at 97 gives 3.3 m).
  A coastline or a cut drawn exactly at a modelled quay's inner edge becomes a
  slope that wide inside the walkable quay. Keep the heightmap below the quay
  deck by at least one vertex spacing past its edge (hide the slope under the
  deck), or raise `resolution`.
* `materials`: up to 4 layers, lowest first. A layer covers the ground from
  its `min_height` up to the next layer's. A layer with `"slope": true`
  covers steep ground (over about 35 degrees) instead. Each layer is a
  `texture` repeated every `uv_scale` metres, or a flat `color`.
* `collision` default true.

### 4.3 water

```json
"water": [{"id": "lake", "position": [40, 0.2, -10], "size": [60, 40], "depth": 3,
           "color": "#2d6a7acc", "swimmable": true}]
```

A flat surface; `position` is its centre. `swimmable` (default true) tells
the runtime that visitors swim there. **v0:** drawn as a translucent surface
with a volume (`depth` deep, default 2) in the "water" group. Visitors swim in
swimmable water with the same code as in Oakhaven (browser 5429f97 and later):
they float once it is about chest deep, dive (Underwater look), and climb out
over a bank, step or deck edge up to about 1 m above the surface. Give the
water a floor (terrain or a primitive) at `depth` below the surface and a
low edge to climb out on. `"swimmable": false` water is decoration: visitors
walk on whatever is under it. Waves and water-look fields are not in v0.

### 4.4 objects (placed glTF models)

```json
"objects": [
  {"id": "level", "asset": "assets/level.glb", "position": [0, 0, 0],
   "rotation": [0, 45, 0], "scale": 3, "collision": "mesh"},
  {"id": "flag", "asset": "assets/flag.glb", "position": [4, 0, 2],
   "animation": "wave", "collision": "none"},
  {"id": "statue", "asset": "assets/hero.glb", "position": [8, 0, 0],
   "animation": "idle1",
   "attach": [{"asset": "assets/helmet.glb", "bone": "head"}]}
]
```

* `asset`: a `.glb` in the package. Load it once, place it as often as you
  like; every placement counts toward the triangle budget.
* `collision`: `none` (default), `box` (the model's bounding box: cheap, for
  crates, houses you do not enter, rocks) or `mesh` (the exact triangles:
  for ground, floors, stairs, walkable levels). Use `mesh` only where people
  walk; it costs memory and physics time.
* `animation`: a glTF animation name to loop. Skinned models animate.
* `attach`: models fixed to a bone of this model (hair, hats, weapons),
  placed in the bone's space, like 2009 `attachObjectToBone`.
* `cast_shadow` (default true), `visible_range` in metres (0 = always).
* `min_tier` (`low` default, `medium`, `high`, `ultra`): draw this entry only on that hardware tier or better (detail only better GPUs show; see [WORLD_TIERS.md](WORLD_TIERS.md)). Primitives take it too.
* `sway` (default false, browser d44444b2 and later; refused by the pinned kit runtime 0bef8c6d — see `kit/runtime.lock`): the model moves in the world's wind as a tree, trunk
  rooted at its lowest point and canopy swaying, whatever its materials. Use it
  for trees and big bushes, such as the catalogue's city trees (vertex-coloured,
  no leaf texture).
* `tint` (`"#rrggbb"`, browser 03032d78 and later; refused by the pinned kit runtime 0bef8c6d — see `kit/runtime.lock`): re-colours this placement only.
  The colour multiplies the model's own colours (texture x vertex colour x base
  colour), so white and light-grey models take it fully and dark ones can only get
  darker; alpha is ignored. Use it to fit a reused built-in or catalogue object to
  your palette (`{"asset": "assets/rock.glb", "tint": "#e0c090"}` for a sand-coloured
  rock) without shipping a copy: the file stays shared, and objects with the same
  model and tint share one material (no extra draw calls). Works with `sway`.
  Impostor cards (`impostor`) show the untinted model. For a colour a multiply cannot
  reach (a dark model made light, a two-tone change), export the model and recolour
  the copy in Blender (it then counts as new download, not reuse).

### 4.5 primitives

Simple shapes for blockouts, floors, walls, markers:

```json
"primitives": [
  {"shape": "box", "size": [10, 0.5, 10], "position": [0, -0.25, 0], "color": "#8a9a5b", "collision": "box"},
  {"shape": "sphere", "radius": 0.5, "position": [0, 3, 0], "emission": "#ffcc66", "unlit": true},
  {"shape": "cylinder", "radius": 0.4, "height": 3, "position": [2, 1.5, 0], "texture": "textures/bark.jpg"},
  {"shape": "capsule", "radius": 0.3, "height": 1.8, "position": [4, 0.9, 0]},
  {"shape": "plane", "size": [20, 0, 20], "position": [0, 0, 0], "texture": "textures/tiles.jpg", "uv_scale": 2, "collision": "box"},
  {"shape": "wedge", "size": [6, 2, 8], "position": [0, 4, 0], "color": "#8b3a2e", "collision": "mesh"},
  {"shape": "frame", "size": [1.1, 2.2, 0.3], "thickness": 0.12, "position": [0, 1.1, 4], "color": "#5a4632", "collision": "mesh"},
  {"shape": "frame", "size": [1.0, 1.0, 0.3], "sill": true, "position": [2, 1.6, 4], "color": "#e8e0d0"}
]
```

Shapes are centred on `position` (a box of height 0.5 at y -0.25 has its top
at 0). `cylinder`/`capsule` `height` is the full height. `wedge` is a gable
roof: `size` is [width x, rise y, length z] with the ridge centred along z.
`frame` is a door or window frame for an opening in a wall: `size` is the
outer [width x, height y, depth z], `thickness` the width of the posts and
lintel (default 0.1 m, at most half the width or height), and `sill: true`
closes the bottom (a window; a door frame is open at the floor). Leave the
wall gap yourself (build the wall from boxes around the opening) and set
the frame's depth a little more than the wall's. `collision`
defaults to `none`; for primitives `box` and `mesh` both give the exact shape
(a wedge or frame collides on its own faces, so a doorway stays walkable).

### 4.6 lights

```json
"lights": [
  {"id": "lamp", "type": "point", "position": [0, 3, 0], "color": "#ffd9a0", "energy": 1.5, "range": 12},
  {"type": "spot", "position": [0, 6, 4], "rotation": [-60, 0, 0], "spot_angle": 30, "range": 15},
  {"type": "directional", "rotation": [-45, 30, 0], "energy": 0.4}
]
```

`attenuation`: 0 = no falloff inside `range` (how 2009 Ogre lights behaved),
1 = default, 2 = inverse square. `shadows` default false (shadows from point
and spot lights are expensive and may be ignored on low graphics tiers).

### 4.7 spawn_points

```json
"spawn_points": [{"id": "default", "position": [0, 0, 12], "yaw": 180},
                 {"id": "from_oakhaven", "position": [0, 0, -20], "yaw": 0}]
```

The manifest's `spawn` names the one visitors use when they arrive through
the address bar; portals from other worlds name one with `#id` (section 4.9).

### 4.8 sounds

```json
"sounds": [{"id": "birds", "file": "audio/birds.ogg", "loop": true, "volume_db": -8},
           {"id": "fountain", "file": "audio/water.ogg", "position": [0, 1, 0], "radius": 15, "loop": true}]
```

No `position` = ambient (heard the same everywhere). `autoplay` default true,
`loop` default true.

### 4.9 portals

```json
"portals": [{"id": "to_oakhaven", "to": "oakhaven#from_mission_hall", "label": "To Oakhaven",
             "position": [0, 0, 20], "yaw": 0, "size": [2.4, 3.2, 0.8], "visual": "ring", "color": "#7fd6ff"}]
```

* `to` is a world address:
  * `iamar://<owner>/<world>` - a world hosted by that hub account,
  * `iamar://<owner>` - that owner's main world,
  * `<world id>` - a world the browser already has locally (e.g.
    `oakhaven`, the built-in flagship world); `iamar://local/<id>` or
    `local/<id>` name an installed local world the same way,
  * a public alias such as `7judpcy8tgiu3` (13 characters; `iamar://` optional),
  * `<owner>/<world>` without the `iamar://` prefix,
  * any of these plus `#<spawn point id>` to arrive at that spawn point.
* `position` is the middle of the portal's bottom edge; `yaw` turns it (a
  portal with yaw 0 is entered walking toward -Z). `size` is the entry volume.
* `visual`: `ring` (default: a glowing ring with the label), `arch`, or
  `none` (you model the doorway yourself).
* The browser, not the world, decides whether to follow a portal (it may ask
  the visitor, check access, or download the target first).

#### How the browser shows and reads addresses

Packages, portals, quests, saves, bookmarks, rooms and the hub always use the
internal forms above. The address bar (and the corner label, the world list and
the old go-bar) shows a display form instead, the way a web browser hides
`https://` and `.com` is the usual suffix (the maintainer 2026-10-12):

| internal | shown |
|---|---|
| `iamar://local/oakhaven`, `iamar://oakhaven`, `oakhaven` | `iamar.3d` |
| `iamar://oakhaven/mission_hall` (any `oakhaven/<world>`) | `iamar.3d/mission_hall` |
| `iamar://alice/hall` | `alice.3d/hall` |
| `iamar://alice` | `alice.3d` |
| `iamar://7judpcy8tgiu3` (a public alias) | `7judpcy8tgiu3.3d` |
| `iamar://local/meadow` (an installed local world) | `local/meadow` |

`iamar://` is never shown and never needs typing; `.3d` is the default domain
suffix. Typed text is read as:

* `foo` or `foo.3d` -> `iamar://foo` (foo's main world on the hub),
* `foo/hall` or `foo.3d/hall` -> `iamar://foo/hall`,
* `iamar` or `iamar.3d` -> the built-in world,
* `local/<id>` -> the installed local world (unchanged),
* a full `iamar://...` link works as before; `#<spawn>` stays on the end.

Other suffixes (`.com` ...) are not special: the whole text is the name, and a
name with a dot is not a valid address. A bare public alias still resolves
through the hub. Note that a bare name now means the hub: an installed local
world is typed as `local/<id>`. Code: `WorldFormat.display_address` and
`WorldFormat.typed_address` (`scripts/worlds/world_format.gd`); tests:
`tools/address_display_test.gd`. The hub side is unchanged: it still sees
`iamar://` addresses.

### 4.10 triggers

```json
"triggers": [{"id": "stage", "shape": "box", "position": [0, 1, -8], "size": [6, 2, 4]},
             {"id": "well", "shape": "sphere", "position": [10, 0, 3], "radius": 2}]
```

Named volumes. A quest `goto` objective can target one by id. Scene triggers are not
delivered to world scripts: for a script-visible zone, spawn an entity and call
`entity_set_trigger` (callbacks `on_trigger_enter` / `on_trigger_exit`, docs/WORLD_API.md).
Invisible unless `debug_visible`.

### 4.11 paths

```json
"paths": [{"id": "market_loop", "points": [[0, 0], [10, 4], [12, 14], [2, 12]], "closed": true}]
```

Points are `[x, z]` (on the ground) or `[x, y, z]`. NPCs walk them (`npc.path`).

### 4.12 creatures

```json
"creatures": [{"kind": "chicken", "position": [6, 0, 4], "count": 5, "wander_radius": 6},
              {"kind": "bunny", "position": [-10, 0, 8], "count": 3, "wander_radius": 10, "seed": 4}]
```

Built-in animals by kind, from the browser's creature kits.

| kind | v0 browser |
|---|---|
| `chicken`, `bunny`, `cow`, `horse` | rendered and wandering (Oakhaven's animal models) |
| `deer`, `wolf` | rendered; wander and flee from the visitor, staying within 1.5x `wander_radius` |
| `duck`, `duckling`, `fish` | rendered; ducks float on the water and fish swim under it; the entry's `y` is the water surface (put the entry at the water's `y`) |
| `frog`, `turtle` | rendered and wandering (pond animals); a turtle with `depth` or `depth_range` swims under water instead, like a fish |
| `slime`, `blue_slime`, `big_slime`, `dragon` | reserved: skipped with a warning until those kits are promoted |

**Swimmers at depth** (fish, and turtles given a depth). Fields beside `count` and `wander_radius`:

| field | meaning |
|---|---|
| `depth` | metres below the surface the animals swim (fish default 0.35, so they show from above only in very clear water; 1-2 m reads well through clear water) |
| `depth_range` | `[min, max]` metres: each animal swims at its own depth in the range and changes depth now and then (overrides `depth`) |
| `school` | `true`: the herd travels as one group (a school of fish, turtles together), each animal at its own place in it; `false` (default): each wanders alone |

A swimmer never goes through the sea floor (it keeps about 0.15 m above the ground under it) or
out of the top of the water. Example, a school of 12 fish 0.8-1.8 m down in a 3 m deep bay:

```json
"water": [{"id": "bay", "position": [0, 0, 20], "size": [60, 40], "depth": 3}],
"creatures": [{"kind": "fish", "position": [0, 0, 20], "count": 12, "wander_radius": 10,
               "depth_range": [0.8, 1.8], "school": true},
              {"kind": "turtle", "position": [8, 0, 26], "count": 2, "wander_radius": 6, "depth": 1.2}]
```

`validate` warns when a duck, fish or swimming turtle is outside every `water` rectangle, when
its `y` is not that water's surface, when its depth is deeper than the water's `depth`, and when
its `wander_radius` reaches past the water's edge; each warning names the fix.

The drawn animals are the city's low-poly painted creatures (LOD0 triangles: wolf 6769, deer
4436, duck 2081, turtle 1446, fish 904, duckling 642, frog 504), with far parts beyond 30 m. For
a dragon, place a catalogue model as a scene object (`iamar-world assets search dragon`).

### 4.13 npcs

People. They come in two sorts:

**Built-in bodies** (`kind` `villager` or `guard`, or any `look`): the
browser's own characters (Oakhaven's CharacterVisual), dressed with Oakhaven
gear. This is what a quest giver usually is.

```json
{"id": "ilsa", "name": "Quartermaster Ilsa", "title": "Missions",
 "kind": "villager",
 "look": {"hero": "villager_woman", "height": 1.72, "skin": "f0dccb", "hair": "Hair_Long", "hair_color": "3a2418"},
 "outfit": {"chest": "dress", "dye": "royal", "head": "none", "back": "cape_green", "main_hand": "none", "off_hand": "spellbook"},
 "position": [0, 0, -12], "yaw": 180, "idle": "idle", "emotes": ["talk", "interact"],
 "wander_radius": 0,
 "greeting": ["Adventurer! There is work on the board for you.", "Back again? Good."]}
```

* `look.hero`: a preset from Oakhaven's `Heroes.DEFS`: `human_male`,
  `human_female`, `elf_female`, `villager_man`, `villager_woman`,
  `villager_lady`, `villager_dress`, `guard`, ... Or `look.body`
  (`male`/`female`) and set the rest yourself. `height`, `build`, `skin`,
  `hair`, `hair_color`, `beard` override the preset. With no hero/body the
  browser draws a random townsperson seeded by `look.seed` (or the id).
* `outfit`: Oakhaven `Gear` slots. Items: head `none hood feather_cap
  iron_helm winged_helm circlet wizard_hat`; chest `default linen leather
  chain plate robe dress`; back `none cape_*`; main_hand `none sword axe mace
  dagger staff bow`; off_hand `none round_shield kite_shield spellbook`;
  `dye`, `pants_dye`, `boots_dye`, `trim_dye`: dye ids (`crimson royal forest
  violet charcoal ivory gold ochre rust teal moss plum slate sky rose umber
  sand`). Unknown ids fall back to the default item.
* `idle`: `idle` (default), `sit`, `kneel`, `talk`, `guard`, ... (the
  built-in animation names); `emotes` are played now and then.
* `greeting`: lines they say when a visitor talks to them; `shop`: wares as
  `[slot, item id, price]` (as Oakhaven's `QuestDefs.SHOPS`).

**glTF characters** (`kind: "character"`, `model` required): your own
skinned model with its own animations.

```json
{"id": "sakura", "name": "Sakura", "kind": "character", "model": "assets/sakura.glb",
 "model_forward": "-Z", "scale": 0.75, "idle": "idle1", "walk": "walk",
 "attach": [{"asset": "assets/stacyHair1.glb", "bone": "head"}],
 "position": [3, 0, 6], "yaw": 200, "wander_radius": 4}
```

* `model_forward`: which way the model faces in its file. glTF says +Z
  (default). Models from the 2009 iamar client face **-Z**.
* `idle`/`walk`: animation names in the glTF; `walk` is used while wandering.

Both sorts: `position` (feet, dropped to the ground), `yaw`,
`wander_radius` (stroll at random within it; 0 = stand still), or `path` (a
`paths` id to walk), `speed` (m/s, default 1.2).

### 4.14 quests

Quests are data, modelled directly on Oakhaven's `QuestDefs.QUESTS`, so a
bridge can hand them to Oakhaven's quest engine unchanged except for three
mechanical conversions: the array becomes a dictionary keyed by `id`,
`[x, z]` arrays become `Vector2`, and the objective kinds `goto`/`pickup`
become Oakhaven's `reach`/`collect`.

```json
"quests": [
  {"id": "hall_welcome", "title": "Welcome to the Hall",
   "giver": "ilsa",
   "offer": "Every hero starts somewhere. Go and see Old Bram in Oakhaven; he has been asking for help.",
   "accept": "Off you go, then. The portal is behind you.",
   "waiting": "Old Bram is in Oakhaven's market square.",
   "thanks": "Bram says you were a great help. Here is your pay.",
   "requires": [],
   "steps": [
     {"kind": "talk", "world": "iamar://local/oakhaven", "npc": "Old Bram", "at": [4.0, 12.0],
      "text": "Talk to Old Bram in Oakhaven", "choice": "The Mission Hall sent me.",
      "line": "About time! The fields need you."},
     [
       {"kind": "kill", "world": "iamar://local/oakhaven", "kinds": ["slime"], "count": 3,
        "areas": [[[10, 240], 20]], "text": "Slimes slain"},
       {"kind": "pickup", "item": "Hall Token", "look": "book", "spots": [[2, -8], [-6, 4]],
        "text": "Tokens found in the Hall"}
     ],
     {"kind": "goto", "trigger": "board", "text": "Report at the mission board"}
   ],
   "gold": 40, "xp": 100, "reward": ["head", "hood"]}
]
```

Quest fields (Oakhaven name in brackets where it differs):

| field | meaning |
|---|---|
| `id` | quest id (the key of `QuestDefs.QUESTS`) |
| `title`, `chain` | shown in the log; `chain` groups a storyline |
| `giver` | the npc id in this world who offers it |
| `turn_in` | npc id who takes it back (default the giver); with `turn_in_world` it is that world's NPC name |
| `requires` | quests to finish first: `"id"` (this world) or `"<address>#<id>"`, e.g. `"oakhaven#summons"` |
| `offer`, `accept`, `waiting`, `thanks` | lines: when offered, when accepted (optional), while in progress, when handed in ("done") |
| `steps` | done in order; each step is one objective or an array worked on together |
| `gold`, `xp`, `reward` | rewards; `reward` is `[slot, item id]` from Gear, or `[]` |
| `on_complete` | what handing it in changes in this world: `show`, `hide` (ids of objects, primitives or lights), `play` (sound ids); see below |

Objective fields. Every objective has `kind` and `text` (tracker line), and
optional `world`: the address where it happens (absent = this world). Use it
for missions that send visitors to another world; Oakhaven is
`iamar://local/oakhaven` (or just `oakhaven`).

| kind | Oakhaven | fields |
|---|---|---|
| `talk` | `talk` | `npc` (an npc id here; in another world that world's name for them, Oakhaven uses names), `choice`, `line`, `at` |
| `goto` | `reach` | `target` `[x, z]` and `radius`, or `trigger` (a trigger id) |
| `ride` | `ride` | as goto, on horseback |
| `kill` | `kill` | `kinds`, `count`, `areas` `[[[x, z], r], ...]`, `camps` (Oakhaven only) |
| `loot` | `loot` | as kill, plus `item` and `look`: each kill drops one to pick up |
| `pickup` | `collect` | `item`, `look`, `spots` `[[x, z], ...]` |

Item `look`: a built-in id (`horseshoe jelly lily book iron herb parcel`;
`parcel` is a plain wrapped parcel for any trade good; an unknown id draws the
herb), or a `.glb` path in the package (`"look": "assets/net_pile.glb"`, browser
863bbc1c and later). A model look must be in the package (the loader names the
missing `.look`); it is drawn as the item, shrunk so its largest side is at
most 0.6 m and centred, still glowing with sparkles, and its triangles count
once per spot (pickup) or per kill (loot), so keep it small (under ~500
triangles). Outside its own world (an objective with another `world`), or in
an older browser, it draws as the parcel. Kill
kinds in Oakhaven: `slime blue_slime big_slime chicken`.

**What a finished quest changes** (browser 08285aa and later). A quest can light
a lamp, open a gate or ring a bell when it is handed in, without a script:

```json
"on_complete": {"show": ["lamp_lit", "lamp_glow"], "hide": ["gate"], "play": ["bell"]}
```

* `show`: objects, primitives or lights (by `id`) that stay hidden until the
  quest is done (handed in), then appear.
* `hide`: objects, primitives or lights that are there until it is done, then
  vanish. Their colliders go with them, so a hidden gate can be walked through.
* `play`: sounds (4.8, by `id`) played once at the moment the quest is handed in
  in this world. Give them `"autoplay": false, "loop": false`.

The state follows the visitor's own quest progress: a visitor who finished the
quest on an earlier visit arrives to the done state (nothing plays), and one who
has not sees the start state. "Ready" (objectives done, not yet handed in)
still counts as not done. Up to 32 `show` / `hide` ids and 8 `play` ids. Scripts
that need more (an animation, a moving boat) read the quest state from `kv`
(WORLD_API.md, "Storage": `kv_get("quest:<id>")`).

The loader does **not** run quests; it hands them to the runtime as data
(`WorldPackage.quests`). It checks that `giver`, local `turn_in`, local
`talk.npc`, `trigger`, local `requires` and the `on_complete` ids refer to
things that exist.

## 5. Assets

* **glTF 2.0 binary** (`.glb`), textures embedded, Y-up, metres. Blender:
  File > Export > glTF 2.0, Format "glTF Binary", +Y Up on, Apply Modifiers
  on. Keep one model per file; place it many times with `objects`. The one exception is a
  generated street row: `iamar-world style-gen street` (`kit/style/gen/README.md`) packs a
  street's houses into a single multi-model `.glb` so their shared painted maps are embedded
  once (see `kit/style/materials/README.md` "How to share maps between models" for the rule
  and the texture-budget arithmetic).
* **Textures:** power-of-two sizes (256, 512, 1024, 2048) are safest; at most
  the declared `texture_size`. JPEG for photos and colour maps, PNG where you
  need alpha. Alpha-cut foliage and hair: set the glTF material's alpha mode
  to MASK.
* **Characters:** a skinned mesh with its animations in the same file.
  Animation names are what `animation`, `idle` and `walk` refer to. Say which
  way it faces (`model_forward`).
* **Vertex colours** multiply the base colour, as glTF specifies.
* **Audio:** Ogg Vorbis, mono for positional sounds, 44.1 or 48 kHz.
* Everything is downloaded by visitors: keep it small. A good first world is
  under 20 MB.

## 5a. Reusing premade objects

Builders are welcome to reuse objects that are already on their machine, and
reuse is the default: the less a world carries, the less its visitors download.
**Only built-in objects can be reused by reference** (`source.kind` `builtin`): browsers
refuse a `reused` record whose source is `kind: "world"` and never read the download
cache for it. An object from another world is **carried**: `iamar-world assets use`
copies its bytes into the package and adds a `credits` entry (author, licence, source).
A reused object is **referenced, not copied**. `manifest.reused` lists it:

```json
"reused": [
  {"path": "assets/oak.glb", "sha256": "<hex of the .glb>", "bytes": 48213,
   "source": {"world": "oakhaven", "kind": "builtin", "file": "assets/nature/tree_oak.glb"},
   "license": "CC0-1.0", "author": "Kenney (kenney.nl)"}
]
```

`scene.json` then uses `path` like any asset; the package must not also carry
that file. The browser finds the object by `sha256` in its asset library
(`scripts/worlds/asset_library.gd`): Oakhaven's built-in objects (indexed in
`scripts/worlds/builtin_assets.json`; all third-party art is CC0, so they are
always reusable and every browser has them). Objects inside other worlds' signed
packages are not looked up (they are carried, see above). The bytes must hash to `sha256`. A missing object
("not on this machine; visit <world> first"), a different hash, or a source
package whose signature fails refuses the world. The manifest is signed, so the
reused list and its hashes are covered by `signature.json`.

**Public catalogue objects** (`source.kind` `catalog`):
`iamar-world assets ref <world> <catalogue id>` references a kit catalogue object
that is not built in by its `sha256` in a release pack of `iamar-ai/iamar-kit`
(`source`: `repo`, `release`, `pack`, `id`, `file`) and adds the feature
`catalog-packs`. Browsers built from the iamar browser source (not public) 47267ddb or later download the
pack once on a visit and keep its objects in a shared cache; older browsers lack
the feature and refuse such a world. `assets use` (carrying the file) works everywhere.
`iamar-world package` checks every catalogue reference and catalogue copy first
(hash, size, licence, author, release). Format, release packs, the browser's
fetch-once cache and the hub mirror: [CATALOG_PACKS.md](CATALOG_PACKS.md).

**Permission.** Objects from **other players'** worlds are reusable only when
their creator allows it in that world's signed manifest: `"reuse": {"allow":
true}` for every object, or per object `"reuse": {"objects":
{"assets/rose.glb": true}}`. **The default is no.** The kit lists such objects
as `LOCKED` and refuses to `use` them, and the loader refuses a package that
reuses one anyway. A builder's own worlds (signed with a key in
`~/.config/iamar/signing/`) are always reusable to that builder.

**Credit.** `WorldPackage.attribution()` and `attribution_text()` give
`manifest.credits` plus every reused object's author, licence and source world,
for the world info. `iamar-world validate` prints them as `CREDIT` lines, and
the download split as `REUSE new <bytes>, reused <bytes> in <n> objects`.

**Behaviour comes along.** Oakhaven's generated animals are library entries of
kind `creature` (`cow`, `horse`, `chicken`, `bunny`): they need no file at all;
`assets use` prints the `scene.creatures` entry, and the browser builds them
with bounded wandering and idle poses; they do not inherit Oakhaven's
fleeing, petting, riding or combat. Built-in trees and plants
(`assets/naturekit`, 879 built-in models in all, `.glb` and `.gltf`) keep their
sway in the shared wind, and building pieces (`assets/village`: walls, doors,
roofs, stairs) keep their collision with `"collision": "mesh"`. Each built-in
model has a 128 px preview in `kit/thumbnails/` (`assets show` prints its path;
`assets thumbnails` remakes them, under a display). Oakhaven's procedural
buildings (`house` with `--width --depth --floors --style`, `inn`, `chapel`,
`blacksmith`, `alchemist`, `general_store`, `stable`) export with
`iamar-world assets building <kind> <out.glb>`: the town's own builder makes it,
with open doorways, furnished interiors and its colours (as vertex colours);
ship the file and place it with `"collision": "mesh"` so people walk in. Door
leaves that swing open are not offered yet (the format has no door behaviour).

Kit: `iamar-world assets list [--all]`, `search <words>`, `show <hash|name>`,
`use <world> <hash|name> [--as assets/<name>.glb]`; maintainers rebuild the
built-in index with `assets builtin-index`. Tests: `tests/asset_reuse/run.sh`
(reuse, missing source, tampered object, permission, licence display).

## 6. What the v0 browser builds

| section | v0 |
|---|---|
| sky (procedural, colour, cubemap), time of day, sun, ambient, fog, exposure | yes |
| weather | reserved, ignored |
| terrain flat / heightmap / procedural, up to 4 ground layers, collision | yes |
| water | surface + "water" volume; swimmable water swims (browser 5429f97+) |
| objects: glTF, collision none/box/mesh, looping animation, bone attachments | yes |
| primitives, lights, spawn points, sounds | yes |
| portals (Area3D, `portal_entered(address)`), triggers (`trigger_entered/exited(id, body)`) | yes |
| paths, npcs `kind: character` (glTF, idle, wander, path) | yes |
| npcs with built-in bodies (villager/guard/look) | exposed as data for the runtime's NPC bridge; `build(parent, {"npcs": "all"})` and the viewer draw them (no dialogs) |
| creatures chicken/bunny/cow/horse/deer/wolf/duck/duckling/fish/frog/turtle | yes (wander; deer and wolves flee, ducks float, fish swim); slimes and dragon reserved |
| quests | exposed as data (`WorldPackage.quests`) for the quest bridge |
| scripts | TypeScript world scripts in the sandbox (section 10) |

## 7. Validation

The browser validates, in order, and refuses the world at the first failing
step (warnings do not stop it):

1. package layout and paths (section 1),
2. `manifest.json` against `schemas/manifest.schema.json`,
3. `signature.json` if present (section 9); a bad signature always refuses,
4. `scene.json` against `schemas/scene.schema.json`,
5. references: every file named exists; ids are unique; npc paths, quest
   givers, quest npcs, triggers and local `requires` exist,
6. declared budgets against the browser's limits (section 8),
7. real counts against the declared budgets: triangles (after loading every
   glTF, times the number of placements), objects, texture edge and bytes,
   lights, file sizes,
8. `features` against what the browser supports.

Run the same checks yourself before you hand a world over:

```bash
iamar-world validate worlds/myworld
offscreen iamar-world preview worlds/myworld /tmp/shots/myworld   # screenshots + perf (also: iamar-world perf)
#   [--view "x,y,z>lx,ly,lz"]... [--npcs all|models|none] [--frames 60] [--size 1280x720]
#   prints VIEW <i> <name> draw=<draw calls> prims=<primitives> fps=... and STATS <budget> <real> / <declared>
```

## 8. Budgets

`manifest.budgets` is the world's promise. The browser checks it twice:
declared values must not exceed the browser's limits, and the real world
must not exceed the declared values.

| budget | browser limit (v0) | a sensible small world |
|---|---|---|
| `triangles` | 3,000,000 | 50,000 - 500,000 |
| `objects` | 5,000 | under 500 |
| `texture_size` | 4096 px | 1024 - 2048 |
| `texture_bytes` (w x h x 4, summed) | 1 GiB | under 128 MiB |
| `lights` | 64 | under 8 |
| `package_bytes` | 512 MiB | under 20 MiB |
| `audio_bytes` | 128 MiB | under 8 MiB |
| `script_bytes` | 16 MiB | - |

`objects` counts every scene entry that becomes something: water,
objects, primitives, lights, sounds, portals, triggers, npcs and each
individual creature (`count`). `lights` counts the entries of `lights`
plus one for the sun when `environment.sun` is enabled (the default). Oakhaven's own valley, for scale, draws 300-700k
triangles a frame on the i7-920 / HD 5750 test machine.

**World UI page budgets (world API 0.4).** A world whose scripts build UI
pages (docs/WORLD_API.md, api/ui_page.schema.json) may also lower these
per-script caps in `manifest.budgets`. Each is an integer from 1 to the
browser's ceiling; 0, fractions, strings and values over the ceiling make the
manifest invalid (the loader and `iamar-world validate` both refuse it), and
an omitted key keeps the ceiling. They can only lower: no manifest raises them,
and hardware tiers cannot set them.

| budget | ceiling (API 0.4) | what it counts |
|---|---|---|
| `max_pages` | 8 | pages a script has set (`ui_page_set`) |
| `max_page_nodes` | 512 | nodes in one page |
| `page_nodes_total` | 2000 | nodes over all of a script's pages |
| `max_surfaces` | 4 | pages shown on entities (`ui_page_surface`) |
| `max_page_images` | 32 | package images used by a script's pages |

A call over a cap returns `E_LIMIT` (-3). The other 0.4 limits (page and patch
bytes, depth, patch rate, surface sizes and distances, image pixels and bytes,
list items, select options) are fixed by the browser; api/world_api.json
`limits_added_in_0_4` lists them all.

**Version handshake.** `api_version` is `major.minor`. A browser loads a
package whose major equals its own and whose minor is not newer; anything else
is refused before a script runs, with `manifest.api_version: world API 0.4 is
newer than this browser (0.3); update iamar` (every browser since 0.1 applies
this rule). Declare the oldest API that has every import your scripts use: a
world without UI pages can stay at `0.3` and still open in 0.3 browsers.

## 9. Signing

A package is signed by its author's RSA key so any visitor, and any peer
that passes chunks along, can check who made it and that nothing changed.

**Algorithm.** RSA, 2048 bits or more, PKCS#1 v1.5 padding, SHA-256
(`RSA-PKCS1-v1_5-SHA256`). ed25519 would be smaller, but Godot's `Crypto`
signs and verifies RSA only, and RSA-2048 with SHA-256 is still a sound
choice, so format 0 uses it. A later format may add ed25519.

**What is signed.** `signature.json` lists the SHA-256 of every other file:

```json
{
  "format": "iamar-signature", "format_version": 0,
  "algorithm": "RSA-PKCS1-v1_5-SHA256",
  "signer": "Ada Author",
  "key_id": "rsa:0123456789abcdef0123456789abcdef",
  "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n",
  "signed_at": "2026-09-30T12:00:00Z",
  "files": {"assets/house.glb": "9f86d0...", "manifest.json": "2c26b4...", "scene.json": "fcde2b..."},
  "signature": "base64..."
}
```

The **signing text** is the UTF-8 string

```
iamar-signature/0\n
<sha256 hex> <path>\n        one line per entry of "files", sorted by path (byte order)
```

and `signature` is the base64 RSA signature over it. `key_id` is `rsa:` plus
the first 16 bytes, in hex, of the SHA-256 of the key's DER
SubjectPublicKeyInfo. Because `manifest.json` is one of the hashed files,
its `signer` claim is covered too.

**Verification** (the browser does all of it): recompute every hash; the
package must contain exactly the listed files plus `signature.json`; the
public key must hash to `key_id`; the manifest's `signer.key_id` (if
present) must equal it; the RSA signature must verify. Any failure is
`invalid` and the world is refused.

**Who made it.** A valid signature proves the holder of that key signed the
package; it says nothing about who that is. The browser keeps a list of
trusted signers (`scripts/worlds/trusted_signers.json`, plus the visitor's
own `user://trusted_signers.json`) that maps key ids to names. The loader
reports one of:

| status | shown as |
|---|---|
| `trusted` | "Signed by Ada Author" (name from the trusted list) |
| `untrusted` | "Signed by an unknown key rsa:1a2b... (claims to be X)" |
| `unsigned` | "Unsigned world" (allowed for local development unless the browser requires signatures) |
| `invalid` | refused |

**Tools.**

```bash
# make a key once (keep the private key private, never commit it)
iamar-world keygen me          # writes ~/.config/iamar/signing/me.key
# sign (writes signature.json, and sets manifest.signer)
# sign and pack in one step (writes signature.json, the .iamar and its .pieces.json)
iamar-world package worlds/myworld build/myworld.iamar ~/.config/iamar/signing/me.key "Your Name"
# verify
iamar-world verify build/myworld.iamar
```

Without Godot, OpenSSL produces the same signature:
`openssl dgst -sha256 -sign me.key signing.txt | base64 -w0`, and the key id is
`openssl pkey -in me.key -pubout -outform DER | sha256sum | cut -c1-32`.

Sign last: any edit after signing (even reformatting JSON) invalidates it.

## 9a. Distribution (pieces)

Visitors download a world from its host and then help share it, as the 2009
client's directTransfer did (`ANY_DT_ADD_TO_SHARE`, `ANY_DT_DOWNLOAD_FROM`):
every visitor who has a world becomes a source of its pieces. For that the
packed `.iamar` file is split into fixed-size **pieces** and described by a
signed **piece list**, with the same basename and `.pieces.json` extension, next to it
(`schemas/pieces.schema.json`):

For example, `release.iamar` is paired with `release.pieces.json`. A canonical
`<id>-<version>.iamar` keeps its `<id>-<version>.pieces.json` name. The id and
version remain in the signed list; the output filename does not change them.
Packing requires a fresh archive and sidecar path and refuses existing files,
directories or symbolic links at either output. This preflight is single-writer,
not an atomic filesystem transaction. A later write failure can leave partial
output; preserve it for inspection and use a fresh output name for a retry.
The CLI signs the source folder before packing, so an output refusal does not
undo that signing step.

```json
{
  "format": "iamar-pieces", "format_version": 0,
  "id": "mission_hall", "version": "1.0.2",
  "size": 5412331,
  "sha256": "<hex of the whole .iamar>",
  "piece_size": 65536,
  "pieces": ["<hex of piece 0>", "<hex of piece 1>", "..."],
  "algorithm": "RSA-PKCS1-v1_5-SHA256", "signer": "Ada Author",
  "key_id": "rsa:...", "public_key": "-----BEGIN PUBLIC KEY-----...",
  "signature": "base64..."
}
```

* Piece `i` is bytes `[i * 65536, min(size, (i + 1) * 65536))` of the
  `.iamar` file; `len(pieces) = ceil(size / 65536)`.
* The piece list cannot live inside the zip it describes, so it is its own
  file with its own signature, made with the **same key** as the package's
  `signature.json`. Its signing text is

  ```
  iamar-pieces/0\n
  id <id>\n
  version <version>\n
  size <size>\n
  piece_size 65536\n
  sha256 <whole-file hex>\n
  <i> <piece hex>\n          one line per piece, i = 0, 1, 2, ...
  ```

* A downloader first gets the piece list (from the host, the hub or any
  peer), verifies its signature and decides whether it trusts the key (the
  same trust list as section 9). It can then take pieces from anyone: each
  piece is checked against its hash **before it is written**, and a peer
  that sends a bad piece can be dropped. When all pieces are in, the whole
  file must hash to `sha256`, and the assembled package is opened and its
  own `signature.json` verified as usual; its `key_id` must equal the piece
  list's.
* An unsigned piece list (no `key_id`/`public_key`/`signature`) is only
  trustworthy when it came from the world's host directly.
* The packed bytes the host publishes are canonical; peers pass on exactly
  those bytes and never repack.

Helpers (`scripts/worlds/world_pieces.gd`, class `WorldPieces`):

```gdscript
var out := WorldPieces.pack("res://worlds/mission_hall", "user://out/mission_hall.iamar", key)  # key: CryptoKey or null
# out = {ok, path, pieces_path, list: <piece list dict>, errors}
var list := WorldPieces.load_list(out.pieces_path)   # {ok, list, status, key_id, errors}
WorldPieces.piece_hashes(list)             # PackedStringArray
WorldPieces.verify_piece(list, 3, bytes)   # true if piece 3 is exactly these bytes
WorldPieces.assemble(list, pieces, "user://cache/mission_hall.iamar")  # pieces: Array[PackedByteArray] in order; checks every piece and the whole hash
var pkg := WorldPieces.open_assembled(list, "user://cache/mission_hall.iamar", {"require_trusted": true})
# opens it and checks it is what the list promised: same id and version, signed inside by the list's key
```

`load_list(...).status == "signed"` only proves the list is intact and was
made by the holder of the key it carries; trust it when `name` is set (a
trusted signer) or the key is the one you expected. Packages from strangers
should be opened with `require_trusted` (or at least `require_signature`).

The same from the command line: `iamar-world package <folder>
<out.iamar> <key> "<Name>"` writes the `.iamar` and its `.pieces.json`.

## 10. Scripts

World scripts are written in **TypeScript**: one global `world.ts`, with no
`import`/`export` or `async`/`await`. API calls are `iamar.<name>(...)`;
callbacks are plain global functions, including the required
`function on_init(): void`. See [WORLD_API.md section 1](WORLD_API.md#1-writing-a-script-for-agents)
and the [showcase source](the iamar browser source (not public)).

Build with `kit/iamar-world compile-typescript world.ts <package-template>
<fresh-out>`. The default is the pure-Node packer (Linux, macOS and Windows; Node 20 or
newer; the TypeScript 5.9.3 compiler installed separately, see the
[TypeScript section of AGENT_KIT.md](../kit/AGENT_KIT.md)). The `--from-source` option is the
older route: a **Linux x86_64 source-checkout command** that needs the five `IAMAR_TS_*` paths
from the [toolchain setup](the iamar browser source (not public)).
Neither route is the browser's `--kit` command.
The output directory must not already exist. The package is **`<fresh-out>/world/`**,
containing `scripts/world.wasm`, `manifest.json`, `scene.json` and
`THIRD_PARTY_NOTICES.txt`; keep the notices in the package.

Both routes copy the template's `scene.json` unchanged, with its saved assets and
metadata, so put every referenced local model, texture and audio file in the template
before building. The default packer fills in a missing script selection with
`scripts/world.wasm`, reconciles the manifest's API version and raises
`budgets.script_bytes` when the module needs more; it refuses a different script
selection. The `--from-source` route copies the manifest unchanged, so there you declare
the script and `budgets.script_bytes` yourself. Start from the
[showcase package template](the iamar browser source (not public)):
it declares `api_version: "0.3"` (the oldest API that has the calls it uses; the current API is 0.4), the `scripts` feature, exactly
`"scripts": [{"path": "scripts/world.wasm"}]`, and the sandbox budgets. Review the
features and budgets for your actual world. Validate, preview and sign `world/` after
any later edit. Keep the sibling `source/`, `guest/` and build receipts outside the package.

The scene loader never executes scripts; the sandbox does, for every visitor,
each running their own copy (messages between copies: `iamar.world_message`,
`iamar.is_authority`). Scene ids (`objects[].id`, `triggers[].id`, `npcs[].id`, ...) name things for
the scene itself (quests, triggers, portals, dialogue); `docs/WORLD_API.md` has no
call that turns a scene id into an entity handle. A script can only touch entities it
got from `entity_spawn`, so spawn from the script whatever it must move, light or
animate (a bell, a lamp light, birds) instead of placing it in `scene.json` and
looking it up.

## 11. Checklist for agents

1. Pick an `id`, write `manifest.json` (copy the example) and an almost empty
   `scene.json` with terrain and a spawn point. Validate.
2. Add models to `assets/` as `.glb`, place them in `objects`. Give walkable
   ground `collision: "mesh"`, obstacles `box`.
3. Light it: `environment.sun` for outdoors, `lights` for rooms.
4. Add people (`npcs`), animals (`creatures`), sound, portals, triggers and
   quests.
5. Run the viewer: look at every screenshot. Check scale (a door is about
   2.1 m tall, a person 1.8 m), facing (people look where `yaw` says) and
   textures (nothing black, pink or untextured).
6. Measure: set `budgets` a little above the viewer's reported numbers.
7. Sign it, then do not touch it.

## 12. Loader API (for the browser)

`scripts/worlds/` (Godot 4.7, GDScript). Engine-independent rules: 
`world_format.gd` (limits, features, addresses, references, budgets, the
QuestDefs conversion), `json_schema.gd` (validates against `schemas/`),
`world_signature.gd`, `world_pieces.gd`, `world_source.gd` (folder or zip,
read in memory, never extracted). Godot specifics: `world_builder.gd` and
the nodes `world_portal.gd`, `world_trigger.gd`, `world_character.gd`,
`world_creatures.gd`, `world_ground.gd`.

```gdscript
var pkg := WorldPackage.open("res://worlds/mission_hall")     # folder or .iamar zip
# options: {require_signature: false, require_trusted: false, check_budgets: true}
if not pkg.ok:
    push_error("\n".join(pkg.errors))      # every problem, "where: what"
pkg.warnings                                # non-fatal (reserved kinds, unsigned, ...)
pkg.id; pkg.title; pkg.version; pkg.manifest; pkg.scene      # plain data
pkg.stats                                   # real triangles, objects, texture_size, ... (budget keys)
pkg.signature.status                        # trusted | untrusted | unsigned (invalid never opens)
pkg.signer_text()                           # "Signed by Ada Author (key rsa:...)"
pkg.npcs; pkg.quests                        # arrays of dicts, straight from scene.json
WorldFormat.quests_for_oakhaven(pkg.quests) # {id: quest} in QuestDefs shape

var root: Node3D = pkg.build(parent, {"npcs": "models"})
# npcs: "models" (default; glTF characters only, built-in bodies are left to the
#       NPC bridge), "all" (also built-in bodies via Oakhaven's Npc), "none"
# creatures: true, sounds: true, environment: true (false if the shell owns the sky/sun)
# portal_body_filter: Callable(body) -> bool (e.g. only the local player)
pkg.spawn_point                             # Transform3D, dropped onto the ground after build
pkg.spawn_transform("from_oakhaven")        # a named spawn point
WorldPackage.yaw_of(pkg.spawn_point)        # radians, for Player.teleport(pos, yaw)
pkg.ground.height_at(x, z, from_y)          # ground queries without physics
pkg.portal_entered.connect(func(address): shell.go(address))       # "oakhaven#from_mission_hall"
pkg.trigger_entered.connect(func(id, body): ...)                    # also trigger_exited
var p := WorldPackage.make_portal(entry)    # a portal node from data, for built-in worlds
```

Built nodes: `root/Environment` (WorldEnvironment), `Sun`, `Terrain`,
`Objects/<id>`, `Primitives`, `Lights`, `Sounds`, `Portals/Portal_<id>`
(Area3D, mask 2), `Triggers/Trigger_<id>`, `Water` (+ volumes in group
"water"), `Npcs/Npc_<id>`, `Creatures`, `SpawnPoints/<id>` (Marker3D), and
`Colliders` (StaticBody3D on layer 1). The root must stay at the origin
(ground queries and wandering use root-local coordinates).

Worlds the browser has locally are listed in `worlds/index.json`; the
portals and spawn points the shell adds to built-in Oakhaven are data in
`worlds/oakhaven_portals.json` (portal shape as in 4.9; `x-on_ground`
means the shell sets `y` from Oakhaven's terrain).

Folders under `worlds/` are ignored by Godot's importer (`worlds/.gdignore`):
the glTF files are loaded at run time, as downloaded worlds are. An export
must include `worlds/*` and `schemas/*` as non-resource files (or ship the
worlds as `.iamar` files).

Tests: `OAK_SETTINGS=/tmp/x/settings.cfg godot --headless --path . -s res://tools/world_test.gd`.

## 13. Worked example

`worlds/mission_hall/` is the Mission Hall, shipped with the browser as a package: a circular hall
with its model and collision, a sun shaft, eight mission-givers (`npcs`) with their quests (`quests`),
sounds, and a return portal to Oakhaven (`oakhaven#from_mission_hall`). Read its `scene.json` next to this
document to see every part of the format in use.

## Addresses and names (not part of the package)

A world's address is not in the package and does not change the format. The hub gives every
registered world `iamar://<account>/<world id>` (the manifest `id`) and a free `iamar://<13 characters>`
alias. An account may also point a `.3d` name (for example `mycafe.3d`) at a world; the hub resolves it
like the alias. Packing, signing and verifying never depend on any of these.
