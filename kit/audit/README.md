# Geometry audits (`iamar-world audit`)

The iamar city's own geometry audits, made generic so they run on any world package or model.
Python 3 with numpy (dark-bake also Pillow); no browser, no Godot, no GPU (Tier 0).

    iamar-world audit <NAME | all> <world folder | model.glb ...> [--json] [--quiet] [--lod 0|all] [--class C]
    python3 kit/audit/audit.py ...                     (the same; the launchers run this)

A world folder is read from its `scene.json`: objects placed by position, rotation (degrees,
applied Y, X, Z like the browser) and scale, plus box and plane primitives and the `terrain` section (`flat`, or `heightmap` built the way the browser
builds it from `resolution`, `size` and the image; `procedural` hills are the browser's noise and are not audited), which count as
the ground.
Collision-only objects (`visible_range` under 0.5) are skipped. A `.glb` given alone is audited
at the origin (`--class building` makes the building audits apply to it). Only LOD0 is audited
unless `--lod all` (then each level separately). Exit 0 = clean, 1 = an ERROR, 2 = bad arguments.

Run `iamar-world audit all <world>` after every geometry change and before the review gate,
and put its RESULT lines in the final report. `--lod all` audits every LOD level on its own
(a far LOD needs a closed roof as much as LOD0 does).

| Audit | Finds | City original (the iamar browser source (not public)) |
|---|---|---|
| `closure` | open edges a player can see into | `tools/masterplan_closure_audit.gd` (+ `.sh`) |
| `zfight` | coplanar overlapping faces that flicker; objects placed twice | `tests/masterplan_city/zfight_audit.gd`, `tools/zfight_audit.sh` |
| `roof` | holes, one-sided roofs and open wall tops seen from the sky | `tests/masterplan_city/mp_roof_audit_test.gd` |
| `edge` | building sides you can see through at eye height | `tools/masterplan_edge_audit.py` |
| `door` | doors you cannot walk through, holes over doors, sills too high | `tests/masterplan_city/door_audit.gd`, `tools/door_audit.sh` |
| `dark-bake` | near-black patches in the light bake on sky-facing faces | `tools/dark_bake_audit.py` (+ `tests/masterplan_city/dark_bake_dump.gd`) |
| `flat-wall` | walls longer than the profile's `lint.flat_wall_max_m` with no opening or relief | none (kit-only; `kit/audit/flat_wall.py`, Track A rule) |

The city versions build the whole masterplan city in Godot and read the city plan; these read only
the package files, so any world (iamar-family or a brand-new style) is judged the same way. They
are engineering checks (vision principle 4): no style profile is involved.

## What each audit checks, and what to do

Front faces are glTF counter-clockwise faces; a material with `doubleSided: true` counts as front
from both sides. Thresholds are constants at the top of `audit.py`.

**closure.** Boundary edges (used by one triangle, after welding vertices 2 mm apart, at least
0.12 m long) are sampled every 0.6 m. A sample is sealed when any other triangle of the world
passes within 3 cm (roof on a wall top, wall on the ground, a neighbour's wall). An unsealed
sample is reported only if a viewer sees it: viewers stand at 1.6 m and 2.8 m (first person,
third-person camera) on two rings around the object (3 m and 10 m outside it) and at every spawn
point; the sight line must reach the edge unobstructed and then land on the back of a one-sided
face or in the void. Fix: close the mesh (cap, extend the wall under the roof, weld), or make the
face double-sided when it really is a thin sheet. Any visible open length is an ERROR. Catalogue props that a world reuses
are sealed this way already (`kit/catalog/assets/seal_props.py`: fishing boat, fish stall, hanging net,
pine tree; `seal_trim_edges.py`: city houses), so they add no closure ERROR to your world.
A world keeps whatever copy it made earlier: when a closure ERROR sits in a file whose name or parts match
one of those sealed models (or whose hash is the unsealed original's), the audit adds a WARN naming it and
the refresh command (`iamar-world assets use <world folder> <id> --as <path>`; a merged file is rebuilt
from the sealed model).

**zfight.** Same-facing triangles of two different parts (or objects) within 2 cm of one plane and
2 degrees of one normal whose areas overlap by 0.002 m2 or more. A part pair with 0.05 m2 or more
is an ERROR, less is a WARN. The same asset placed twice at the same transform is an ERROR. Fix:
move one surface off the other by 3 cm or more (a sign stands proud of its wall), or cut the
hidden part away. Back-to-back faces (opposite normals, e.g. a door on a wall) are not reported,
nor two undersides that are each the bottom of their object (a crate standing where a paving slab
ends: only a camera under the ground could see them). Fully transparent primitives (`"color"`
ending in `00`, invisible collision proxies) are not drawn and take part in no audit. A pair a
quest's `on_complete` swaps (one object id in its `show`, the other in its `hide`) is never drawn
together and is skipped, logged as INFO naming the quest.

**Several models in one file:** a .glb whose root nodes carry extras `{"x-class": C}` (`iamar-world style-gen street`) becomes one audit object per root node (`<object id>/<node>`, class C), so the building audits judge every house of a street on its own and `zfight` does not call the houses copies of each other. Root nodes without x-class in such a file become one more object, `<object id>/untagged`, classed like an ordinary model (lint fails them `[parts]`).

**roof.** For each building, landmark and interior (the lint's model classes: `x-class` in
scene.json, else the kit catalogue's category for a catalogue copy, else the file name, else size;
`structure` (pier, quay, mast, frame, fence, ground, bridge ...), `vehicle` (boat, ship, cart ...),
`tree` (elm, oak, pine, hedge, bush ...), props and creatures get no roof, edge or door audit; an
object reused by hash (`manifest.json` `reused`) is audited from the kit's copy): vertical sky rays on a 0.75 m grid over its
footprint, and oblique rays from 52 and 28 degrees in four quarters aimed at its roof. `open` =
a point surrounded by the building has nothing of it above; `back` = the first face a flyer
meets is a back face (a back hit that rays 3 mm to either side meet as a front face is a
numerical leak and ignored); `sunk` = the first face is in the bottom 35 % of a building over
3 m tall and the building stands around it on all four sides at 0.8 m above it (a floor seen
through a missing roof, not the base step of a tower, and not a tread of an open-air stair: a
sky-visible point of the building 5 cm to 1.2 m higher or lower within one grid step, up or down). All are ERRORs. Fix: roof the gap, give the roof
its top side, close wall tops.

**edge.** From 2 m outside each side of a building, three rays at 1.6 m above its base (at 25,
50 and 75 % along the side) towards its middle. A side where two of the three miss, meet a back
face, or travel deeper than 40 % of the building into it (a hollow house with a wall missing) is
an ERROR. Sides whose start points are inside another object (a party wall, a terrace) are not
judged. Open-sided buildings (market halls, arcades, an open fish hall) will be reported: give
them closed sides at eye height, or mark them `"x-class": "structure"` in scene.json (a
`.glb` alone: `--class structure`).

**door.** Every node named `*door*` (not `frame`, `arch`, `knocker`, `handle`, `hinge`,
`lintel`, `surround`, `trim`) in a building, if it leads into a room: 1.2 m behind it at chest
height at least three of five rays (sides, inwards, up) meet front faces. A door drawn on a solid
block is decorative and only noted. Its walk-through axis is its thinnest side; outside is away
from the building's middle. `BLOCKED`: nine rays from 2 m outside to 1.2 m inside, at knee, chest
and head height, middle and either side, hit anything except the door leaf and its trims. `HOLE`:
a ray 0.3 m over the door top meets nothing of the building (also checked 8 m out to 3 m in, so
a deep porch is not a hole). `STEP`: the floor outside and inside differ by more than 0.45 m.
Fix: move whatever stands in the doorway (windows, signs, props), fill the wall over the door,
add a step or ramp.

**dark-bake.** Models with baked light: materials with `KHR_materials_unlit` and a colour
texture (what `kit/blender/bake_unlit.py` writes), or a lightmap PNG next to the model named
`<model>.lightmap.png`, read through `TEXCOORD_1` (red = sky light, green = sunlight, like the
city bakes; grey+alpha also read). Every texel on a sky-facing face (normal y 0.5 or more) is
sampled; dark = unlit colour at most 0.05 on every channel, or lightmap sky at most 0.16 and sun
at most 0.06. Not counted, because no viewer sees them as a black spot:
- covered texels: from the texel, the ray along its normal and 24 rays tilted 25, 50 and 75
  degrees around it all meet a surface within 10 m (a wall top under the eaves, a roof under a
  ridge cap or inside a turret, the top of a plinth core under its cap, ground under a house).
  The bake cannot light them either. Objects that can be entered (a `*door*` part, class
  `interior`) keep every texel; the INFO line per object gives the covered area;
- lines one or two texels wide (a dark seam at a UV island border, the fringe of a texel half
  under a cap) and triangles thinner than a texel (trim strips): that is filtering and lightmap
  padding, not a black spot. A spot three or more texels wide counts with its full area, edge
  texels included; the empty atlas between islands does not count as dark.
The other dark texels are grouped into patches (0.5 m cells, touching); a patch of 0.05 m2 or
more is an ERROR. Worlds without a bake are noted and pass. Models carrying the time-independent
sky/AO bake (`asset.extras.iamar_bake.kind == "sky_ao"`, written by `kit/blender/bake_vertex_ao.py`)
are listed (`sky_ao_objects` in the RESULT line). When the world's clock runs
(`environment.day_length_minutes` > 0) the audit WARNs if nothing is baked (the low tier draws no
shadows) or if a model carries an unlit time-of-day bake (right at one hour only);
`kit/style/lighting/README.md` "A running clock" gives the fix. Fix: look for what shades the patch
(a cap, a buried copy, two coplanar faces of one mesh), check the lightmap UVs (overlap,
padding) and rebake. `iamar-world lint` leaves the dark texels of baked (unlit) materials to this
audit.

**flat-wall.** Runs `kit/audit/flat_wall.py` (also usable alone, with `--style` and `--max-m`):
per building, landmark and structure, rays at 0.9, 1.6 and 2.3 m from each side find the longest
run of wall with no door, arch, pier, buttress or frame (5 cm of relief breaks a run). A run over
the style profile's `lint.flat_wall_max_m` (iamar: 6 m) is an ERROR. The profile is the world's own
`style.json`, else `iamar` (a loose `.glb` is judged by iamar); a profile without the limit (a
Track B world whose style bible decides) skips the audit with an INFO line. Fix: add a door, arch,
pier, buttress or lean-to, or break the wall into shorter volumes.

## Samples and tests

- `samples/audit_yard/`: two enterable houses and a crate; every audit passes (its `style.json` has no
  `lint.flat_wall_max_m`, so the plain 6 m fixture houses skip flat-wall). Rebuilt by
  `samples/make_samples.py` from `kit/tests/audit/audit_fixture.py`.
- `kit/tests/audit/audit_test.py` (suite `kit_audit` in `tools/run_tests.sh`): all audits pass
  `audit_yard` and `kit/lint/samples/desert_post`; each audit fails a copy broken on purpose
  (open-topped crate, a sign 5 mm proud of a face, a doubled placement, no roof, a one-sided roof,
  no back wall, a crate in the doorway, a 0.9 m sill, no lintel, a black bake, a black lightmap).

## Known result: city houses reused alone

`kit/lint/samples/iamar_city` (masterplan houses B002, B003, B005 as exported to
the iamar-models mesh archive (not public)) fails closure, roof and edge: about 250 m of visible open edge, 78 roof
rays, 7 open sides. The city builds every house with per-face visibility culling against its
real neighbours (faces no player can see in the city are never built), so a city house placed
on its own shows exactly those missing faces. This is correct for the city and wrong for reuse:
when a world reuses a city building away from its city neighbours, audit it, and close the
reported sides (or ask for an unculled export) before shipping.
