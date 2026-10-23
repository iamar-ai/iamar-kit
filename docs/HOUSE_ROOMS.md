# A house from a room list

    iamar-world assets building house out/beach_house.glb --rooms bedroom:3,living,kitchen,bath:2 --style beach
    iamar-world assets building house out/flat.glb --rooms bedroom:2,living,kitchen,bath --floors 1 --style modern
    iamar-world assets building house out/beach_house.glb --rooms bedroom:3,living,kitchen,bath:2 --furnish

`scripts/kit/kit_house_rooms.gd` (an internal task) plans a house from the rooms you name and writes
it as one binary glTF with walk-through doorways, glazed windows, floors, a stair when there
are two floors, and a roof. Place it in `scene.json` with `"collision": "mesh"`: the doorways,
corridor and stair are walkable and the walls block.

| Option | Values | Default |
|---|---|---|
| `--rooms` | `living`, `kitchen`, `dining`, `bedroom`, `bath`, `study`, `laundry`, each optionally `:N` (also `bed`, `bathroom`, `lounge`, `office`) | required; at most 16 rooms |
| `--floors` | `1` or `2` | 2 for more than 6 rooms, else 1 |
| `--style` | `beach`, `modern`, `plaster`, `stone` | `beach` |
| `--roof` | `gable` or `flat` | `flat` for modern, else `gable` |
| `--furnish` | (a flag) furniture from the catalogue in every room, see [Furniture](#furniture) | off |

Without `--rooms`, `assets building house` still makes the town's house shell (KitBuildings).

## The plan

- A corridor 1.4 m wide runs the length of the house (x). Rooms sit in two rows, one each side
  of it, 4.2 m deep; widths: living 5.0, kitchen and dining 3.6, bedroom 3.6, study 3.0, bath
  and laundry 2.4 m. The last room of each row stretches so both rows end together.
- Every room has a 0.9 x 2.2 m doorway onto the corridor and one or two windows in its outside
  wall (baths: a small high window). Rooms at the ends get a window in the end wall too.
- The front door (1.1 x 2.2 m, with a porch step) is at the corridor's west end and faces -x.
- With two floors, bedrooms and studies go upstairs (with the second bath when there are two),
  the rest stay down. A stair bay at the east end holds a 16-step stair (0.19 m risers, 0.28 m
  treads) up the east wall, an opening in the floor above it, and a rail on its open side.
- Storeys are 3 m floor to floor; walls stand on a 0.15 m slab, so the house sits on flat ground
  at y = 0. Colours are plain glTF materials kept dark enough for the linear tonemap (no white
  clipping); glass is a translucent material.
- A three-bedroom, two-bath house on two floors is about 2,000 triangles.

## The rooms sidecar

Beside `out.glb` the command writes `out.rooms.json`:

    {"floors": 2, "size": [length, depth], "storey": 3.0, "style": "beach", "roof": "gable",
     "front_door": [x, y, z], "facing": [-1, 0, 0], "triangles": 1964,
     "rooms": [{"name": "bedroom_1", "type": "bedroom", "floor": 1,
                "rect": [x0, z0, x1, z1], "door": [x, y, z], "lit_by": ["light_3"],
                "windows": [{"wall": "north", "c": x, "w": 1.2, "high": false}, ...]}, ...],
     "lights": [{"id": "light_1", "type": "point", "position": [x, y, z], "color": "#ffdcb0",
                 "energy": 1.2, "range": 6.2}, ...],
     "stair": {"rect": [...], "bottom": [x, y, z], "top": [x, y, z]}}

Coordinates are in the model's own space (centred on x and z, ground at y = 0). Use the room
rectangles to place furniture (keep the doorway clear) and the front door to place the spawn
and the path. A window's `c` is its centre along its wall (x on the north and south walls, z on
the west and east ones); `high` marks a bath's small window with its sill at 1.5 m (others 0.9 m).

## Furniture

`--furnish` (`scripts/kit/kit_house_furnish.gd`, an internal task) puts catalogue furniture
(`kit/catalog/assets`, `assets search` finds each piece) in every room by its type:

| Room | Pieces (*optional*: left out quietly when the room is too small) |
|---|---|
| bedroom | cot bed, wardrobe, rug |
| living | sofa, rug, *armchair*, *bookshelf* |
| kitchen | kitchen counter, *kitchen dresser* |
| dining | trestle table with benches, *kitchen dresser* |
| bath | bathtub |
| study | bookshelf, *armchair*, *iron-bound chest* |
| laundry | iron-bound chest |

Each piece stands on its room's floor with its back to a wall (the outside wall first for
beds, sofas, counters and baths; a side wall first for wardrobes and shelves), facing into the
room. It keeps 0.25 m off the wall lines, clear of a 1.3 m apron inside the doorway (the
doorway's width plus 0.35 m each side), of the other pieces, and, when it is taller than
0.95 m, of the windows in the wall behind it. Rugs lie flat in the middle and may run under
other pieces. The pieces go into the same `.glb` as the house, as nodes under `Furniture`, so
the house stays one object and `"collision": "mesh"` covers them too; there is nothing more to
copy or place. Each room in the sidecar lists what it got in `"furniture"` (`item`, `asset`,
`position`, `yaw`, `footprint` `[x0, z0, x1, z1]`), `"skipped"` optional pieces and
`"unplaced"` main pieces (the command prints a WARN for each). The sidecar has
`"furnished": true` and `"furniture_triangles"`; `"triangles"` counts both. A furnished
three-bedroom, two-bath house on two floors is about 4,000 triangles and 0.6 MB.

The command reads the catalogue from `IAMAR_KIT_CATALOG` when it is set, else from `catalog/`
beside `iamar-kit.pck` (the kit download's layout) or the kit checkout's `kit/catalog`; without
one it stops with an ERROR.

## Lights

The sun and the sky light do not reach under a roof: a house without lights renders flat
grey and dark inside. The sidecar's `"lights"` are warm ceiling lights ready for
`scene.json` `"lights"` (`point`, colour `#ffdcb0`, energy 1.2, no shadows), and each room
lists the lights that reach it in `"lit_by"`. They run along each floor's corridor, one
every 5 m or so, at most 6 per house: the browser's renderer lights one mesh with at most
8 lights and the house is one mesh, so more would leave some rooms unlit at random. Without
shadows a corridor light shines through the inside walls into the rooms on both sides.

They are in the model's own space: add the object's position and turn them with its
rotation. For an object at `"position": [px, py, pz]`, `"rotation": [0, yaw, 0]`, a light
at model `[x, y, z]` goes to `[px + x cos(yaw) + z sin(yaw), py + y, pz - x sin(yaw) + z cos(yaw)]`
(`KitHouseRooms.scene_lights(info, position, yaw)` does this). `iamar-world validate` warns
when a room of a placed house has no point or spot light on its floor that reaches its
centre, and prints a light that fixes it; it reads `<model>.rooms.json` beside the `.glb`,
so keep the sidecar in the world folder (it checks folders, not packed `.iamar` files).

## Tests

    GODOT=/path/to/godot-4.7 tests/kit_house_rooms/run.sh

builds four houses (one and two floors, every style, gable and flat) in a throwaway project and
checks the triangle budget, that every triangle faces outward, that every doorway, the front
door and the ground corridor are open, that there is 2 m of headroom over every step, the
sidecar, and that the glTF keeps every triangle.

    GODOT=/path/to/godot-4.7 tests/kit_house_furnish/run.sh

furnishes the same four houses and checks every room has its pieces, inside its walls, on its
floor, clear of its doorway and of each other, that the glb holds every piece and stays under
the budget, and that a house without `--furnish` has none.

`tests/kit_house_furnish/shot.gd` renders evidence shots of a furnished house (a cut-away plan
per floor, a view into each room type from its doorway); see `docs/evidence/job3812/`.
