# Track A: an iamar-family world

For a world that should look and feel like the iamar city: an extension, a new district, a
village across the bridge. Use this after the interview has chosen Track A
(`README.md`) and the user has approved the brief (`../PROTOCOL.md`, section 8).

Each step ends with a **check** you must run; do not go on until it passes. Commands are
described in `kit/AGENT_KIT.md`; the style data is in `kit/style/`.

## Step 1: choose the style profile

Pick the nearest iamar quarter for the mood (palettes in `kit/style/iamar/style.json`, region
names `civic`, `mages`, `warriors`, `herbalists`) and decide what differs for this world (a new
region such as a harbour, a tighter budget). Create the world folder:

```bash
iamar-world new worlds/my_world --id my_world --title "My World" --author "<user's name>"
```

Write `worlds/my_world/style.json` as a profile that `extends` the iamar one and states only
what differs (see `kit/style/schema/examples/harbour_quarter.style.json`):

```json
{"schema": "iamar-style/1", "id": "my_world", "extends": "iamar",
 "name": "...", "description": "...",
 "regions": {"harbour": {"mood": "...", "roof": "#...", "wall": "#...", "timber": "#...", "trim": "#..."}}}
```

**Re-point the painted layers too.** Region colours alone do not change which painted texture
`style-gen` uses: a region with no layer of its own gets the civic ones (blue slate roof). Add
`materials.layers` entries whose `use` **starts with the region name** and whose `layer` is the
painter layer you want (`shingle` roof, `plaster` wall, `stone` ground, `timber`), as in
`kit/style/schema/examples/harbour_quarter.style.json`:

```json
"materials": {"layers": {
  "harbour_roof_shingle": {"layer": "shingle", "tint": "#5a5f66", "use": "harbour roofs"},
  "harbour_wall_plaster": {"layer": "plaster", "tint": "#e4dccb", "use": "harbour upper storeys"}}}
```

Choose region colours **inside the iamar weathering rules** (walls about 0.5 x saturation, no
pure black, no two neighbours with the same tint).

In the brief keep `"style_profile": "iamar"` and add `"style_file": "worlds/my_world/style.json"`
(the validator checks that the file, once written, `extends` iamar).

**Check:** `python3 kit/style/check_style.py worlds/my_world/style.json` passes. A budget looser
than the parent's, an unknown material layer or a malformed colour is refused.

## Step 2: greybox and scale

Block out the layout with plain shapes first: streets (the city uses lanes 5 m, alleys 3 m,
main streets 10 m), plots, landmarks, the portal arrival. Do not paint anything yet. Put the
camera at 1.7 m and walk it.

**Check:** `iamar-world validate worlds/my_world` has no ERROR; a person is about 1.8 m and a
door about 2.1 to 2.2 m; **show the user the greybox screenshots** (`iamar-world preview
worlds/my_world /tmp/greybox`) and get a yes. This is checkpoint 1 of the brief.

## Step 3: reuse before modelling

Search the catalogue for everything the brief needs before you build anything:

```bash
iamar-world assets search "<words>"        # then: assets show <hash|name>, assets use ... --as assets/x.glb
iamar-world assets building house out/house.glb --width 8 --depth 6 --floors 2 --style plaster
```

Objects tagged for the iamar style and neutral objects fit; objects from another look will not
(the catalogue's style tags tell you). Reusing is by reference: nothing is copied and visitors
who already have an object download nothing.

**Check:** the brief's `reuse` section lists what you borrowed and what is new; `iamar-world
validate` prints CREDIT and REUSE lines for what you borrowed.

## Step 4: build the new pieces

Build what the catalogue does not have, to the engineering practices (`../common.md`, section 5
flags; budgets from `kit/style/iamar/style.json`): ordinary house 1k to 3k triangles, landmark
5k to 15k, prop around 300; every visible face closed, nothing a visitor cannot see has
polygons; detail in painted textures and baked light, not triangles.

- Paint materials from the profile: `python3 kit/style/check_style.py --paint
  worlds/my_world/textures --profile worlds/my_world/style.json`.
- Use the Blender tools for LODs, normals and light bakes (`kit/blender/`, `docs/BLENDER_KIT.md`).
- Vary neighbours: no two houses next to each other share window rhythm, roof pitch or tint.
- Break every wall a walker sees: no stretch longer than the profile's `lint.flat_wall_max_m`
  (iamar: 6 m) at eye height without an opening, an arch or relief 5 cm or more proud or deep.
  The house generators do this; halls, sheds, warehouses and other buildings you model yourself
  need it by hand (harbour blind test a4: a 16 m fish hall wall and an 8 m net shed wall, both
  plain, were review FAILs). Ways the city does it, cheapest first: a door or doorway with a
  proud frame; piers or pilasters every 3 to 4 m (0.2 to 0.4 m deep); buttresses on stone
  halls; a blind or open arcade; a lean-to, a porch or a stair against the wall; a stone plinth
  with a timber or plaster wall above it set back; on timber sheds, posts and braces proud of the
  boards and an open bay. Keep surface detail in paint (painted half-timbering, staining: the city
moved carved detail into paint, an internal memory record, 315d5679); the check only asks for one cheap break
in the geometry every 6 m, and painted lines or flush window panes alone are not that break.

**Check:** `iamar-world lint worlds/my_world` has no ERROR (it checks palette, scale, budgets,
repeats); triangles per class are within the profile's `budgets`; `python3
kit/audit/flat_wall.py worlds/my_world` has no ERROR (a party wall against a neighbour, a quay
face over water and walls under 2.5 m high are not judged).

## Step 5: light and atmosphere

Copy the profile's `atmosphere.presets.<name>.environment` into `scene.json` `environment`
(golden hour for a warm look). Keep the sun warm and the fog cool and light; a warm fog tinted a
whole valley yellow in the city and FAILED.

**Check:** shots at the times of day the brief names (`iamar-world preview ... --view
"x,y,z>lx,ly,lz"` at about 1.7 m); no area is near-black at any of them.

## Step 6: connect it to the city

If the brief asks for a portal, add a `portals` entry in `scene.json` (`docs/WORLD_FORMAT.md`
section 4.9). Add the arrival back from the city only as the user's choice, because the city is
not edited by your world.

**Check:** `iamar-world validate` accepts the portal; the arrival point is on the ground and
framed, never a hole in a wall.

## Step 7: look, compare, review

Compare against the city's shots from the same camera
(`iamar-world compare-shots <city-shot-dir> <my-shot-dir>`), take the checkpoint screenshots
(greybox, scale, paint) and send them to the user, then pass the world to a **different agent**
for the review gate (`../../review/REVIEWER.md`). Fix the FAIL rows and ask again.

**Check:** the review report exists and is PASS or PASS (minor); the weighted score is at or
above the brief's threshold; every budget in the brief is met per tier.

## Track A mistakes seen in the city

- A long flat wall with no arch: FAIL in this track.
- A roof under a third of the building's height (the city uses one third to one half).
- Eave steps under about 0.6 m: invisible from the street; use jetties, oriels, gables, dormers
  and corner towers to give the street front an outline.
- More triangles for detail that paint should carry; a closed door that is not an opening.
- Warm fog; pure black iron; two neighbours with the same tint.
