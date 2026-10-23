# iamar-world shots: fixed eye-height review shots at day, dusk and night

`preview` chooses its views from the world's bounds, so they move whenever the world grows.
Reviews, before/after comparisons and the final report need the **same cameras every time**,
at the height a visitor's eyes are, and at more than one time of day. `shots` does that.

| Command | What it does |
|---|---|
| `iamar-world shots --init <world>` | Writes a starter `<world>/shots.json`: one camera per spawn point, plus the view back, plus one `edge_*` camera per side of the playable area |
| `iamar-world shots --edges <world> [--add] [--tier T] [--cameras FILE]` | Exit 1 when a side of the playable area has no eye-height camera looking out over it (`--add` appends the missing `edge_*` cameras to shots.json), or when every camera covering a side sees more than 75% open ground at tier T (default low; "Bare view") |
| `iamar-world shots <world> <out> [--cameras FILE] [--times day,dusk,night] [--tier T] [--size WxH] [--frames N] [--npcs all\|models\|none] [--quest-done IDS\|all] [--retries N] [--strict] [--json]` | Renders every camera at every time and writes the sheets below |

It runs `kit/shots/shots.py` (Python 3; Pillow for the sheets) and renders through
`iamar-world preview --view`, so the images and numbers are what the browser draws. Like
`preview` it needs a renderer: a desktop session, or on a Linux host without a display it
wraps the preview in `offscreen` when that is installed (a private Xvfb display).

Quests: what a quest's `on_complete` shows or hides (`docs/WORLD_FORMAT.md` 4.14, a lamp that
lights when the errand is handed in) is drawn as a visitor first sees it, every quest not done
(`QUESTS start` in the preview output). `--quest-done <id>[,<id>...]` or `--quest-done all`
renders the end state instead; shoot both into two folders to compare the before and after.
(Browsers without QuestEffects draw every entry and print a NOTE.)

## The camera set: shots.json

```json
{
 "eye_height": 1.7,
 "cameras": [
  {"name": "arrival", "at": [0, 0.1, 14], "yaw": 0},
  {"name": "street", "at": [0, 0, 7], "look": [-6, 2, -18]},
  {"name": "tower_top", "at": [3, 22, -40], "yaw": 90, "pitch": -15, "eye_height": 1.6}
 ],
 "times": ["day", "dusk", "night"],
 "time_presets": {"dusk": {"time_of_day": 17.8}, "storm": {"time_of_day": 15, "fog": {"enabled": true, "density": 0.03}}},
 "budget": {"triangles": 150000, "draws": 150}
}
```

- `at` is where the viewer's **feet** are (on the ground or a floor: on a heightmap give the
  ground height as y). The camera sits `eye_height` above it (default 1.7 m; per camera too).
- Aim with `look` (a point) or `yaw` / `pitch` in degrees. Yaw is the spawn-point yaw: 0 faces
  -Z, 90 faces -X. Pitch defaults to -5 (a little down, as a person looks along a street).
- Names: letters, digits, `_` and `-`; they name the files, so keep them when the world changes.
- Choose the views a visitor sees: the arrival, the main street, each landmark from its
  approach, each interior, the view back to the entrance. Keep them; add, do not move.
- `budget` defaults to the manifest's `budgets.triangles` and 150 draw calls.
- `--cameras FILE` uses another set (a reviewer's own cameras, for example).

## World edge: --edges

Beyond the last house the terrain runs on to the edge of the heightmap. Nobody looks there while
building, so it stays a flat colour band and the first person to see it is the reviewer (harbour
blind test attempt 3, review FAIL row: `r_edge_east`, a bare green gradient hill from the east
quay). `--edges` makes that view part of every shot run:

- The **playable area** is the box around the spawn points, objects, NPCs, portals, triggers,
  lights and primitives up to 40 m (bigger primitives are ground or sea planes, not places).
- A side is **covered** when a camera at eye height (eye_height 5 m or less; aerials do not
  count) stands within 10 m of it, or a quarter of the area's depth if that is more, and looks
  out: its view within 50 degrees of the side's outward direction (north is -Z, east is +X).
- A missing side prints `EDGE <side> MISSING` with a ready camera, standing at the placed thing
  nearest that side and its middle, on the terrain (heightmap sampled; a pier keeps its own
  height), yaw pointing out, pitch 0. `--add` writes them into `<world>/shots.json` (move one if
  it stands inside a model). Exit 1 while any side is missing, 2 on bad input.
- Each terrain band with a colour but no texture prints a `NOTE edge:` line: from eye height a
  flat band reads as a bare gradient.

```
$ iamar-world shots --edges kit/blindtest/harbour/attempt-3/world        # attempt 3, before
EDGE playable area x -42.0..44.0, z -60.0..31.0
EDGE north ok      lighthouse
EDGE south MISSING no eye-height camera near this side looks out; add (or --add): {"name": "edge_south", "at": [1.0, 0.0, 31.0], "yaw": 180.0, "pitch": 0}
EDGE west  ok      portal, edge_west
EDGE east  MISSING no eye-height camera near this side looks out; add (or --add): {"name": "edge_east", "at": [42.0, 0.0, -1.2], "yaw": 270.0, "pitch": 0}
NOTE edge: terrain band {"color": "#a18f78", "min_height": -100} is a flat colour (no texture): ...
NOTE edge: terrain band {"color": "#6b8c40", "min_height": 0.4} is a flat colour (no texture): ...
NOTE edge: terrain band {"color": "#7f786e", "slope": true} is a flat colour (no texture): ...
edges: MISSING south,east
```

The builder's own `edge_west` camera covered the west; nothing covered the east, and the review's
camera there (`[44, 0, 1]` looking east, `kit/blindtest/harbour/attempt-3/review-a3/r_edge_east_day.jpg`)
found the bare hill. With `--add` the run gets `edge_east` 2 m from that spot, so the builder sees
the hill at step 6, not the reviewer at the end. How to close the view once the shot shows it:
`kit/AGENT_KIT.md` step 6, "Dress the world edge".

### Bare view: what the edge cameras see

A camera on every side is not enough: harbour attempt 4 had all four and passed, yet the review's
north and south edge shots were an empty yellow field to the horizon
(`kit/blindtest/harbour/review-a4/r_edge_north_day.jpg`, `r_edge_south_day.jpg`). So `--edges` also
judges each covered side by what its cameras see, without rendering:

- Rays over the camera's frame (48 x 27, the browser's 75 degree vertical field of view at 16:9,
  out to 400 m) meet the world as `kit/audit/meshworld.py` loads it (LOD0 models, visible
  primitives, the terrain mesh). A ray that ends on the terrain, or on a flat ground primitive
  more than 40 m across and under 2 m thick, is **open ground**; one that meets a `water` area
  first is open water (not bare); one that meets nothing is sky and does not count.
- It judges one tier, `--tier` (default `low`, the tier everyone can show): objects and
  primitives whose `min_tier` is above it are not there.
- A side is **BARE** when every camera covering it sees more than 75% open ground: exit 1,
  `edges: ... BARE <sides>`; otherwise one `EDGE <side> view` line gives the best camera's share.
  Use `--cameras FILE` to judge another camera set (a review's).

Measured on harbour attempt 4 with the review's cameras (`review-a4/cams.json`):

| camera | tier low | tier medium | review shot (tier low) |
|---|---:|---:|---|
| `r_edge_north` | 97% BARE | 84% BARE | empty field to the horizon |
| `r_edge_south` | 96% | 77% | empty field to the horizon (stands 37 m inside the area, so it covers no side) |
| `r_edge_east` | 16% | 15% | field wall and a row of trees: dressed |

```
$ iamar-world shots --edges kit/blindtest/harbour/world --cameras kit/blindtest/harbour/review-a4/cams.json
EDGE north BARE    r_edge_north sees 97% open ground at tier low (limit 75%): close the view with a wall, trees, rocks or a skyline that stand at this tier (no min_tier above low); it sees primitive:fieldwall_nw, primitive:seawall_n
EDGE east  view    r_edge_east sees 16% open ground at tier low
edges: MISSING south; BARE north
```

**Why attempt 4's edges were bare (trap):** the builder did dress the north and south, with 12
`edge_tree_*` trees, but gave every one `"min_tier": "medium"` (as step 6 then advised for far
trees), and the review ran at tier low. Edge dressing that closes the view must stand at tier
low; thin it at low with `impostor` distances, not with `min_tier`. The builder's own `edge_*`
cameras (`world/shots.json`) see 44% at low, 29% at medium: they look along the tree rows the
review's cameras missed, which is why the same world passes with its own set.

### Yellow day grass (trap)

In the same review the meadow is saturated yellow in every `day` shot and green at dusk. Cause:
the `day` preset removes `sun.direction` so the sun stands at 13:00, but keeps the world's own
sun, which harbour attempt 4 tuned for a fixed golden hour (`time_of_day` 17.4, `sun.direction`
set, colour `#ffc888`, energy 1.8, exposure 1.08). Overhead, that orange sun at 1.8 on the
yellow-green grass texture (mean sRGB 164, 190, 106) gives roughly linear red 0.78, green 0.69,
blue 0.10 (lit = albedo x (sun colour x energy x cos + ambient `#c0b0a0` x 0.8) x exposure),
which is sRGB about (229, 215, 90) before tone mapping: yellow. At the world's own fixed sun (21 degrees up, cos 0.36)
the sun term is less than half of that (0.36 against 0.85 at 13:00) and the grass stays green, as the dusk shots show. A world with a
fixed `sun.direction` never shows the 13:00 light in the browser (`world_builder.gd` uses the
direction and ignores `time_of_day`), so the yellow is in the review shots only; but a world that
lets the sun move (no `sun.direction`) is lit exactly this way at noon. Rules: keep `sun.energy`
near 1 and its colour near white (`#fff4e0`, the browser default) when the sun moves, and warm the
look with the sky, fog and ambient; judge a fixed-sun world by its own light, and treat its
`day` shots as a stress test.

Harbour attempt 5 hit it again for real: it set `day_length_minutes` 360 on the golden-hour
sun, so noon in the browser was orange (an internal task). Now `lighting.py check <world>` fails a warm
moving sun, the `day` lighting preset is the near-white one for a running clock, and
`iamar-world compare-shots <out>/shots --style <world>/style.json` fails the day shots whose
ground colour is off the profile's ground (`kit/style/lighting/README.md` "A running clock",
`kit/lint/README.md` "Ground colour by day").

## Times of day

Each time renders a temporary copy of the world whose scene.json `environment` is patched;
the world folder is never changed. Built-in presets:

| time | patch |
|---|---|
| `day` | `time_of_day` 13 |
| `dusk` | `time_of_day` 17.6, warm sun `#ffb27a`, ambient x 0.7, dusk colours on the procedural sky |
| `night` | `time_of_day` 22.5 (the browser fades the sun out below the horizon), ambient x 0.3, exposure x 0.9, a dark procedural sky, the world's fog colour blended 85% toward the night horizon `#1a2140` |

Every preset removes `sun.direction`, so `time_of_day` places the sun (a world with a fixed sun
would look the same at every hour). Sky colours change only for the **procedural** sky (the
default); a cubemap or flat-colour sky is the world's own choice and stays. A world whose sun
is disabled (an interior) keeps it disabled: its own lights carry every time.

`time_presets` in shots.json add times or refine the built-ins. A patch is merged into
`environment` (docs/WORLD_FORMAT.md 4.1): `null` removes a key, `<key>_scale` multiplies the
world's own value (default 1), `procedural_sky` is merged into `sky` only for a procedural sky.
`fog_tint` (`{"color": "#rrggbb", "amount": 0..1}`) blends the world's fog colour toward
`color` when the world has fog on (any sky type; hex colours `#rgb`, `#rrggbb` or `#rrggbbaa`, a
colour name is left as it is with a NOTE); a light day fog left as it is reads as a pale
grey sheet over the ground under a dark night sky. `"night": {"fog_tint": null}` keeps the
world's own fog colour. Desert before/after: `kit/blindtest/desert/review/sheets/m_night_5.jpg`
and `m_night_fogtint_after.jpg`. A world whose time runs (`day_length_minutes` > 0) should still
pick a fog colour that works at night: the browser does not retint fog by the hour.
Only fields the format has: inventing fields changes nothing.

## Output

```
<out>/shots/<camera>_<time>.png      raw shots; compare two runs with
                                     iamar-world compare-shots <before>/shots <after>/shots
<out>/sheets/<camera>_<time>.png     review sheet: the shot plus world, camera, time, tier,
                                     triangles and draw calls against budget (OVER in red), objects
<out>/contact_sheet.png              every camera (rows) at every time (columns)
<out>/shots.json                     the numbers per shot, plus any render errors
<out>/SHOTS.md                       the same as a table, for the report to your user
```

Triangles and draw calls are what the renderer drew in that frame from that camera (the
`prims` and `draw` of `preview`'s VIEW lines), so they include the shadow pass.

Exit status: 0 when every shot rendered; 1 when a render failed or a view is missing (the
contact sheet shows the gap; never report a partial set as done), or with `--strict` when any
shot is over budget; 2 on bad input (unknown time, bad camera, output folder inside the world).

A renderer that crashes while it shuts down (exit 134 or 139) after writing every view has
still drawn them: the shots count, exit 0, and a `NOTE shots <time>: ... crash on exit` line
says what happened. When a pass crashes before writing some views, `shots` keeps the views it
did write and renders only the missing ones again (`--retries N`, default 1). Only a view still
missing after that is a failure; a timeout is not retried. Under that, the launcher
(`kit/iamar-world`, Linux/macOS) runs a `preview` that aborts (exit 134, glibc `double free or
corruption` / `realloc(): invalid old size`; or 139) once more by itself and prints
`iamar-world: preview crashed (exit N), running it once more`; `IAMAR_PREVIEW_RETRY=0` turns that off.
`shots` and `lowtier` set it to 0 for their own preview runs: they retry only the missing views, and
a launcher retry would render every view again after a crash on exit (and could run past `--timeout`).

Each render works on a copy of the world in a temp folder: `--tmp <dir>` (also on `lowtier`), else
`TMPDIR`, else the system temp dir. A full or unwritable temp dir prints one `ERROR shots ...` line
naming the folder and exits 1, with no traceback.

## Washed-out frames (WARN)

Day and dusk shots are measured: when more than 60% of the lower 45% of the frame (the ground band)
has luminance 225 or more (of 255), the shot is `washed_out` in `shots.json` (with
`ground_near_white`), the review sheet says WASHED OUT in red, `SHOTS.md` has a `WARN washed out`
list and stderr prints `WARN shots <camera> <time>: washed out ...`. It is a warning only: the exit
status does not change. Night is not measured; Pillow is needed. The fix is in
`kit/recipes/composition/BRIGHT_WORLDS.md`. Constants: `WASH_BAND`, `WASH_LUMA`, `WASH_SHARE` at the
top of `shots.py`.

## Example

`samples/desert_post.shots.json` is a camera set for the style-lint sample world
`kit/lint/samples/desert_post`:

```
iamar-world shots kit/lint/samples/desert_post /tmp/desert_shots --cameras kit/shots/samples/desert_post.shots.json
```

`samples/desert_post_contact_sheet.jpg` is that run (zoe, Godot 4.7.2, 2026-10-20): three cameras at day,
dusk and night, 192 to 5,004 triangles and 16 to 23 draw calls per view against a 150,000 /
150 budget.

## Test

`python3 kit/tests/shots/shots_test.py`: camera maths (eye height, yaw, look), the three
patches and `time_presets`, the world folder left unchanged, cubemap skies kept, budgets and
`--strict`, failed and missing renders, bad input, `--init`, with a stand-in renderer
(`kit/tests/shots/fake_preview.py`). With `IAMAR_BROWSER` (or `GODOT` and `IAMAR_PROJECT`)
and `IAMAR_KIT_PACK` set it also renders the desert sample for real.

On Windows the launcher is `iamar-world.cmd shots ...`. Run from Git Bash, the wrapper's
render check now calls Windows' own `find.exe` (Git's Unix `find` would walk the whole drive).
