# A blocked-out world from the interview brief

    iamar-world new my_beach_house --from-brief brief.json
    iamar-world new my_beach_house --from-brief brief.json --template beach --title "Sea Glass House"

`--from-brief` (an internal task, `scripts/kit/world_from_brief.gd`) reads the approved interview
brief (`brief.json`, [kit/interview/PROTOCOL.md](../kit/interview/PROTOCOL.md) section 6) and
starts the world from it instead of from an empty template: the starter template that fits,
the house built from its rooms ([HOUSE_ROOMS.md](HOUSE_ROOMS.md)) and placed on dry, level
ground, the spawn in front of the front door facing the house, the portal home beside it, a
path from the door, and the brief's time of day and budgets. It is a greybox to show the user
at the first checkpoint, not a finished world: it validates and previews on the first run, and
every part is ordinary `scene.json` you then edit.

## What it reads

| Brief field | Used for |
|---|---|
| `layout.zones` (optional) | The zones to lay out, in any order. Each is a name or an object with `kind`; a `house` zone takes `rooms`, `style`, `floors` and `roof` (the `assets building house` options). |
| `vision` | When there is no `layout`: the zones and the house are read from the sentence ("3-bedroom beach house", "two-bedroom cottage with a study and a garden", "harbour village"). |
| `type`, `extra_types` | `nature` adds a forest zone, `town`/`shop`/`social`/`event` the town, `interior` the one-room interior. |
| `mood.time` | morning 9:00, noon 12:30, afternoon 15:00, golden hour/sunset/evening 17:30 (`environment.time_of_day`). Night keeps the template's daylight and says so: a night world needs its own lights. |
| `budgets` | `triangles`, `texture_size`, `texture_bytes` lower the manifest budgets (never raise them). |
| `connections.name` | `iamar://sea-glass-house` gives the id `sea_glass_house` and the title "Sea Glass House" unless `--id`/`--title` are given. |
| `features` | NPCs, quests, scripts and UI pages are not blocked out; each gets a NOTE. |
| `approval` | Missing: a NOTE to show the user the greybox before building further. |

Zones: `house`, `beach`, `sea`, `garden`, `plaza`, `forest`, `town`, `interior`, `lake`, `river`,
`island`. An unknown zone, an empty list or a house style other than beach, modern, plaster or
stone is an error (exit 2) that names the choices.

## What it builds

- **Template:** beach when the brief has a beach or sea, else forest, else town (town or plaza),
  else interior (an interior world without a house), else the meadow. `--template` overrides it.
- **House:** `assets/house.glb` and `assets/house.rooms.json` from the room list (default from
  the vision: the bedroom and bath counts, plus dining, study or laundry when named; style beach
  on the beach, stone in the forest, modern when the vision says modern, else plaster). It is
  placed with `"collision": "mesh"` so the doorways, corridor and stair are walkable.
  - On the beach the front door faces the sea and the house slides inland until its whole
    footprint stands on the dunes (no sand or water under it), then 2 m more.
  - On the meadow, in the forest clearing and on the town square's north side the door faces +z,
    toward the spawn side.
  - Where the ground under it is not level, a foundation fills the gap under the floor and front
    steps lead down from the door.
  - Starter shapes on the house site are removed (the report lists them); a portal there is moved.
- **Spawn:** 8 m in front of the door and 3 m to the side, 0.2 m above the ground, facing the
  house (a three-quarter view of the front).
- **Garden:** a bed of flowers each side of the house. **Plaza:** a paved square with a fountain
  beside the house (meadow only; the town template already has its square).
- **Path:** `paths[front_path]` from the door past the spawn (NPCs can walk it).
- `objects` and `paths` are added to `manifest.features` when used.

Not built here, each with a NOTE: lakes, rivers and islands (`iamar-world terrain lake|river|island`,
then place the house by hand: the terrain helper moves the spawn); furniture and room lights
(from `house.rooms.json`: furnishing is an internal task, interior lighting an internal task); NPCs, quests and
scripts.

## Output

    TEMPLATE beach: a sandy shore sloping into clear, swimmable sea with fish, a dock, palms and a parasol
    BRIEF template beach zones house,beach,sea,garden house bedroom:3,living,kitchen,bath:2 style beach
    HOUSE .../assets/house.glb 159108 bytes 1734 triangles door [-4.9, 0.15, 0.0] facing [-1, 0, 0] floors 2 rooms 7 ...
    PLACED house assets/house.glb at [0.0, 1.75, 30.9] yaw -90.0, front door [0.0, 1.9, 26.0], 2 floor(s), 7 rooms, 1734 triangles
    PLACED spawn spawn at [3.0, 1.83, 18.0] yaw 166.91 facing the house
    NOTE the house is unfurnished and unlit inside: furnish it from assets/house.rooms.json (catalogue, an internal task) and add room lights
    NEW beach_house (Beach House) in .../my_beach_house - next: edit scene.json, then `iamar-world validate my_beach_house`

The laid-out folder is opened again before `NEW` is printed; if it does not validate the command
exits 1 with the errors (please report it with the brief).

## Worked example

`tests/kit_from_brief/beach_house.brief.json` is the creator-UX beach-house brief ("a large
3-bedroom beach house by the beach, water clear enough to swim in, fish visible in the water")
with a `layout`. Without the `layout` the vision alone gives the same template and house (no garden).

## Tests

    GODOT=/path/to/godot-4.7 tests/kit_from_brief/run.sh

plans the beach-house brief, a cottage brief, a listed layout, the interview's sample brief and
an interior brief, refuses seven bad briefs, and lays out a beach and a meadow: the floor above
every bit of ground under the house, the beach house on the dunes with its door to the sea, no
starter shape inside the house, the portal off the site, the spawn on the ground facing the house,
the front path, the plaza and garden, and budgets never raised. `tests/kit_new_argv` covers the
`--from-brief` option in the argument guard.
