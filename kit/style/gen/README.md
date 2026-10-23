# Style generators (`iamar-world style-gen`)

The iamar city's own house, roof and door-arch builders, ported to plain Python 3 so any world
can build with them from a style profile (`../README.md`). No Blender, Godot or GPU (Tier 0);
the `--check` audits need numpy, `--textures` needs painted PNGs from `check_style.py --paint`.

    iamar-world style-gen house out.glb [--profile iamar] [--region civic] [--seed 7] [--footprint L]
                                        [--storeys 3] [--[no-]jetty] [--[no-]oriel] [--[no-]tower]
                                        [--door-kind 0|1|2] [--timber 0-4|plain|post|studs|braced|crossed]
                                        [--world preview --check] [--textures DIR]
    iamar-world style-gen roof  out.glb [--footprint U] [--eaves 6] [--pitch 0.9] ...
    iamar-world style-gen arch  out.glb [--width 1.3] [--door-h 2.2] [--ceiling 3.6] ...
    iamar-world style-gen lantern out.glb [--mount post|wall] [--height 2.6] [--glow 1.3] ...
    python3 kit/style/gen/gen.py ...            (the same; the launchers run this)

`--footprint` is a preset (`rect` 9x6, `narrow` 6x9, `L`, `T`, `U`), `WxD` (a rectangle) or a
JSON file with a list of `[x, z]` points (counter-clockwise or not; edge 0 is the front with the
door). `--world DIR` also writes a preview world (ground, spawn, the model) that the browser and
`iamar-world audit` can open; `--check` runs the closure, roof and zfight audits on every LOD of
it, and for `house` and `street` the flat-wall audit (Track A: no blank wall over the profile's `lint.flat_wall_max_m`; window
frames stand 15 cm proud so a side with windows is not flat, an internal task). `--lods 1` writes LOD0 alone (for `kit/blender/look.py`). `--json` prints the report.

It prints `GEN_OK <kind> <file>: triangles LOD0 / LOD1 / LOD2 (LOD0 budget N, efficiency E)` and
exits 1 (`GEN_FAIL`) when LOD0 is over budget (the profile's `budgets.triangles.building`, a
prop's for the arch) or `--check` finds an ERROR.

| Command | Inputs | Outputs | Hardware | Licence | Fallback |
|---|---|---|---|---|---|
| `style-gen house` | profile, region, seed, footprint, storeys, feature switches, timber frame | `.glb` with `house_LOD0..2`, report (storeys, eaves, ridge, pitch, wings, features, triangles, Efficiency) | any CPU, Python 3 | kit licence (code ported from the iamar browser source (not public), same owner) | `iamar-world assets building` (the simpler Oakhaven town builder) |
| `style-gen roof` | footprint, eaves, pitch (or the profile's) | `.glb` with walls + `roof_LOD0..2`, report (wings, faces, plan area = footprint area) | any CPU | same | a Blender hip roof by hand |
| `style-gen arch` | door width and height, ceiling | `.glb` `arch_LOD0` on a sample wall, report (spring, rise) | any CPU | same | none needed |
| `style-gen lantern` | mount (post or wall), height, glow | `.glb` `lantern_LOD0..2` (~100 / 85 / 40 triangles), report with `light` (the scene.json point light to pair with it) | any CPU | same | a catalogue lamp (`category: lamp`) plus your own point light |

## Lanterns that read as lit

`style-gen lantern` builds a street lantern on a timber post with a stone foot (`--mount post`,
cap at `--height`, default 2.6 m) or an iron wall lantern on a bracket (`--mount wall`: the wall
is the z = 0 plane, the lantern stands out along +z; turn it with the object's yaw). The iron is
an open frame, a base plate, four corner bars and a pyramid cap, so the glass shows from every
side. The glass is the profile's `lamp_glow` colour, emissive with `KHR_materials_emissive_strength`
`--glow` (1.3 by default; above about 2 the browser's linear tonemap clips it to white).

The glass glows on its own; what lights the street is a point light. The report's `light` is the
entry to copy into scene.json `lights` for each lantern, with the lantern object's position added
(rotated by its yaw):

    "lights": [{"id": "lamp_0", "type": "point", "position": [x, y + 2.265, z], "color": "#ffc060",
                "energy": 1.4, "range": 9, "attenuation": 1, "shadows": false}]

Keep the lights within the manifest's `lights` budget (the browser lights the nearest few;
recipe `light_pool`). Keep lanterns live-lit (`asset_pipeline.py --light ao`), and if the world
is seen at dusk or night, bake their light into the walls around them:
`../lighting/README.md` "Night: bake the time you show" (recipes `lit_lantern`, `bake_night`).
`--world DIR --check` writes a preview world at the night preset with the light in place.

Why: the harbour blind test hid emissive glass inside a closed iron lathe, and its lanterns read
as dark grey boxes at dusk and night (review sheet_n). The test checks that nothing stands in
front of the glass.

## Half-timbered upper storeys (`--timber`)

Every house of two storeys or more gets a timber frame on its upper storeys, in one of the city's
five patterns (`frame.py`, from `mp_buildings.gd` `_base_style` and `_emit_facade_varied`):

| `--timber` | What the upper walls get | LOD0 triangles added (9x7 m, 3 storeys) |
|---|---|---|
| `0` / `plain` | nothing: plaster (or limewash) between the quoins | 0 |
| `1` / `post` | a rail on each storey's floor line and under the eaves, one post in the middle of each wall | 208 |
| `2` / `studs` | rails, and studs on every bay line of the window grid (so they fall between the windows) and at both ends | 288 |
| `3` / `braced` | studs, and a brace in each end panel: rail to rail in a panel without a window, a knee brace from the post beside a window | 384 |
| `4` / `crossed` | studs, and a cross in every panel: full height where there is no window, under the sills where there is | 528 |

Without `--timber` the house picks one by seed from the profile's weights,
`[plain, post, studs, braced, crossed]`: a region's `timber_frame_weights` (street.json: per house
`"timber"`), else `dimensions.timber_frame_weights`, else plain (a Track B look without weights,
such as the desert example, stays untimbered). The iamar profile frames its town houses by default
(`[0, 1, 3, 3, 2]`, the Warriors' street with no plain walls; also civic), and keeps the city's
quarter weights: warriors `[1, 1, 3, 3, 2]`, mages `[4, 2, 1, 1, 1]` (mostly plain), herbalists
`[2, 2, 2, 2, 2]`. The harbour example region has the Warriors' weights. The report says
`timber_frame` and `timber_pieces` (rails, posts, braces on LOD0).

Why: the harbour blind test a5 asked for "the warriors' street look" and got plaster faces with
quoins (review gap R3, sheets m_02 rv_tavern_close, m_07 rv_quay_houses_s): style-gen had corner
posts but no framing at all.

Rules it keeps:

* **Depths:** rails and posts 6 cm proud, braces 3 cm (2 cm or more from everything they cross,
  zfight PLANE_D); timber crossing timber is one material, so it does not flicker.
* **Clear of everything else on the wall:** each window with its sill and shutters, the door, the
  oriel, the tower, the quoins (rails stop 6 cm past the longest quoin) and the corner posts (rails
  end inside them). Posts are split around what they meet; a brace that would touch one is left out.
  `--check` (closure, roof, zfight on every LOD) passes for every pattern with every feature on.
* **LODs:** LOD1 keeps rails and posts, LOD2 has no frame.
* **Budget:** after shutters, sills and side quoins, `fit()` drops the braces (economy 4), then the
  posts (5), then the frame (6). A 3-storey 9x7 house at 3000 keeps its crosses (economy 3).

Shots: `docs/evidence/job3689/` (the five patterns side by side, painted iamar layers, eva software GL).
Test: `python3 kit/tests/style/gen/frame_test.py` (`--quick` skips the every-feature houses; ~2 min).

## What it builds, and where it comes from (the iamar browser source (not public), read-only)

| Part | City original | Kit file |
|---|---|---|
| Convex-wing envelope roof: cut at re-entrant corners, wings grown back across the cuts, upper envelope of hipped wings, ridge and hip caps (no caps on valleys) | `scripts/world/masterplan/mp_roof.gd` (A20) | `roof.py` |
| Deep flared eaves: overhang 0.42-0.66 m, falls flatter than the roof (x0.55), fascia, soffit | `mp_style.gd` `eave_overhang`, `eave_drop` | `roof.py` `eave_skirt` |
| Quoins (alternating long and short courses), timber corner posts above a stone ground storey | `mp_style.gd` `dress_corners`, `quoins`, `corner_post` | `house.py` |
| Timber frame on the upper storeys: rails, studs, corner braces, crosses; quarter weights | `mp_buildings.gd` `_base_style`, `_emit_facade_varied`, `_beam_along`, `_post` | `frame.py` |
| Jettied front (ground storey set back 0.32-0.55 m) on carved cove brackets | `mp_buildings.gd` jetty, `mp_style.gd` `jetty_brackets`, `bracket` | `house.py` |
| Oriel: timber bay on the first upper storey, lean-to roof, closed sides and underside, brackets | `mp_buildings.gd` `_emit_oriels`, `_emit_oriel` | `house.py` |
| Round corner tower: drum from the ground (facets inside the footprint start at the roof), storey bands, cone, finial, windows facing the corner | `mp_style.gd` `corner_tower` | `house.py` |
| Door frame and leaf (painted plank with iron straps, panelled, natural oak in a stone surround) | `Buildings.door`, `mp_style.gd` `DOOR_KINDS` | `arch.py` `door` |
| Round arch: voussoir ring and keystone springing from the lintel, timber tympanum; semicircle at most, refused under 0.28 m rise | `mp_style.gd` `door_arch` | `arch.py` `door_arch` |

What the city reads from its plan (lanes, neighbours' walls, the facade layout) the kit reads
from its arguments: every visible wall is dressed, the oriel takes the longest free wall, the tower
a convex corner with two walls of 4.6 m or more off the jettied front.

From the profile: colours per region (`wall`, `timber`, `roof`, `trim`, `ground_stone(s)`, `paints`;
the palette, then neutral defaults, when a region lacks one), weathered per role and seed by
`weathering.roles`; dimensions (`storey_m`, `storey_scale`, `door_m`, `window_*`, `jetty_m`,
`oriel_m`, `corner_tower_radius_m`, `eave_overhang_m`, `roof_pitch_rise_per_run`, or
`roof_height_fraction` for flat-roofed looks such as the desert example); one painted layer per
role (`materials.layers`: a layer whose `use` names the region first, then by painter layer; a new region needs its own entries or it gets the civic slate roof, see `kit/style/schema/examples/harbour_quarter.style.json`), so
glTF material names are the layer names and `--textures` fits.

**Roof share.** A profile that gives both pitches and `roof_height_fraction` (iamar: roofs a third
to a half of the whole height, Track A) gets a pitch that keeps the roof in that share for the
house's eaves: a picked pitch that is too low for a tall house is swapped for one of the list
that fits, else steepened up to the lint's ceiling (largest pitch + `lint.pitch_slack`). Every
3-storey house on a footprint 7 m or more deep (10x8, 7x7) now fits; before, three storeys under
a 0.72-0.88 pitch gave a quarter-height roof (harbour blind-test review). A narrow wing (an L or
U arm, a 6 m deep house of 3+ storeys) cannot reach the share under that ceiling: the report's
`roof_share` shows it and style-gen prints `WARN roof: ...` (and `warnings` in `--json`) when it
is more than 5 points outside, the lint's tolerance. Make such houses deeper or lower. The fallback
pitch never leaves the lint's pitch range, so a very deep 1-storey house keeps the lowest pitch
and warns that its roof is over half the height (split it into wings or add a storey).
`iamar-world lint` cannot check these roofs: it finds roofs by part name and a style-gen model is
one mesh (`house_LOD0`), so its pitch and height-fraction rules never run on them. The checks are
the generator's own: this pitch fit, `WARN roof`, and `--check` (the roof audit).

Modules: `gen.py` (the CLI), `house.py`, `frame.py`, `roof.py`, `arch.py` and `lantern.py` (the generators), `meshkit.py`
(mesh builder and binary glTF writer), `profile.py` (reads the style profile for them).

## Rules it keeps (each one cost the city a fix)

* **Closed and culled:** no face against a wall, a roof or the piece beside it; everything else
  closed. Each generator's output passes `iamar-world audit closure/roof/zfight --lod all` (the test).
  The kit audit judges what a player can see; the Blender `closure_audit.py` (and `asset_pipeline.py`)
  also counts every welded boundary edge and every edge shared by 3+ faces. On a generated house those
  are the floor edges at y=0 and the roof sheets meeting culled wall tops (the position of each is
  printed as `NONMANIFOLD_EDGE`). Tower storey bands leave 0.12-0.16 m slivers that the kit audit does not count as visible. Run the
  pipeline on a house with `--ground 0 --min-edge 0.2 --allow-nonmanifold`: then both audits agree
  (checked on seeds 1-6, LOD0; the kit audit needs the world's ground, as in `style-gen --world --check`).
* **Nothing in one plane:** window glass set 4 cm back inside a four-rail frame (11 cm off the wall,
  so the flat-wall audit counts it as relief even from a 5 cm corner post), glazing bars 3.5 cm in
  front of the glass (zfight flags faces within 3 cm), the frame sunk 1 cm into the wall, bands stop
  short of quoins.
* **Windows read dark by day, warm at night (an internal task):** a mullion and one transom (two over two lights)
  on house, oriel and tower windows, LOD0 and LOD1, and dark smooth glass (roughness 0.12)
  with the region's `window_glow` at emissive strength 0.2 (`profile.WINDOW_GLOW`). A package's
  emissive never changes with the hour, so it must stay under daylit glass: at 0.5 (an internal task) the
  panes read as flat amber panels by day, dusk and night alike (harbour a5 review gap R2).
* **Envelope planes:** wing edges on one wall line take that original edge's plane, so shared faces
  are emitted once (B095, B133 strips); the first identical plane of another wing owns the face.
* **Caps:** creases on one line merge before capping, caps stop short of junctions (C6 c307f752),
  hips stop where both cap feet are still on the roof (past the outline a foot hung over the eave),
  and a cap is split where the roof under it bends (a straight foot over a kink left a slit).
* **The ring's feet stand on the lintel:** the lintel is as deep as the ring (0.19 m); a 0.12 m
  lintel left the ring's feet open from below.
* **Budget first, then beauty:** LOD0 is fitted to the building budget by dropping shutters, then
  sills, then side quoins, then timber braces, posts and rails (`economy` in the report); LOD1 keeps caps, frames, the oriel and tower
  windows; LOD2 is walls, roof, eaves, glass and door.

Tests: `python3 kit/tests/style/gen/style_gen_test.py` (`--quick` for one house; ~30 s in full).
Recipe: `masterplan_house` in `kit/recipes/TECHNIQUES.md`.

## Streets: many houses in one model (`street.py`)

    iamar-world style-gen street worlds/my_world/assets/street.glb --street street.json \
        --profile worlds/my_world/style.json --textures worlds/my_world/.build/painted

Use it for any row or street of generated houses (5 or more painted houses seen together). Point
`--textures` at the world's `.build/` folder, not at the world folder itself: painted maps are
build inputs, and anything written into the world folder gets packed into the package download
(~12 MB of PNGs in the harbour blind test). Directories whose names start with `.` are not part
of a package (`docs/WORLD_FORMAT.md` section 1). One
`.glb` holds every house of the street, each its own root node, placed and turned as
`street.json` says (`position` [x, y, z] in the street's frame, `yaw` in degrees, plus every
`style-gen house` switch: `seed`, `footprint`, `storeys`, `jetty`, `oriel`, `tower`, `door_kind`,
`region`). A sample: `kit/tests/style/street/street.json` (12 houses on both sides of a 20 m street).
Place the file once in scene.json (`"position": [0, 0, 0]`, collision `mesh`), no `x-class`.

Why one file (harbour blind test attempt 4, gaps G9-G11; numbers from the 12-house test):

| Separate house files | `style-gen street` |
|---|---|
| every file embeds its own maps: 12 x 6 maps at 1024 px = 288 MiB, over the 64 MiB budget, so builders fell back to 512 px maps and blurry 128 px/m | each map once: 6 maps = 24 MiB at 1024 px, 256 px/m at the city's 4 m tile |
| the browser's merge_static merges surfaces only when they share a texture, never across files: 102 surfaces -> 90 draw calls | 102 surfaces -> 7 draw calls (one per look) |
| merging the houses by hand (one mesh) makes lint judge the row as one building (over budget) and `audit edge` see the gaps between houses | each house is a root node with extras `{"x-class": "building"}`: lint reports `street.glb#house_n1 ...`, audit objects `street/house_n1 ...`, each with the building budget, doors, roof, closure and edge rules |

How: every house uses the same materials (one per painted layer role, base colour factor 1); its
own weathering shift goes into `COLOR_0`, which glTF multiplies into the base colour (the browser
turns vertex colours on for package worlds; the file says `iamar_vertex_colour: linear`). The UV
tile follows the maps: 1 UV unit = map width / 256 m, so 1024 px maps tile every 4 m and 512 px
maps every 2 m, both at 256 px per metre (`--tile-m` overrides). 1024 px is the default to use: a
street pays for its maps once. Use 512 px only when the world's budget needs it: the design then
repeats at half size, and the dark slate joints can land on a whole ridge cap (lint `[colour]`
ERROR on `roof_slate_cap` for some seeds).

Checks, all per house: `iamar-world materials texel` and `materials budget` on the world,
`iamar-world lint`, `iamar-world audit all` on the world (a loose street.glb has no ground, so
closure reports the culled undersides, as for one house), and `--world DIR --check` for a preview
world. It prints `GEN_OK street ...: N houses, M materials, K maps (MiB, px/m, tile)` and a line per
house; exit 1 when a house is over the building budget.

Limits: LOD0 only (the browser builds LOD chains for merged meshes); for far LODs or impostors keep
far houses in their own street file. One street file is one object for `impostor` and
`visible_range`. Test: `python3 kit/tests/style/street/street_test.py` (19 checks, about 2 minutes;
the draw-call check runs when `godot` is on PATH).
