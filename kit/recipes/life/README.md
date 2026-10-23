# Life and motion recipes: idle NPCs, wind, smoke, birds, doors, ambient audio

What makes a world feel alive without costing frame time. Each recipe names the city
implementation it comes from (a file in `the iamar browser source (not public)`, checked by
`check_life.py`), its status (WORKS / PARTIAL / FAILED, with evidence), its layer
(engineering = every world, style = the iamar look only) and the scene data a world
uses. Engineering rules hold for any world; the style notes only say what the iamar look
does, and a custom world writes its own.

The cheap-by-default rule behind all of them: **nothing is built at startup, and nothing is
simulated where nobody can see or hear it.** Each system places its work when the player is
close enough to notice and drops it when they leave.

Check the sample world (a scene that uses all six, data only):

```
python3 kit/recipes/life/check_life.py kit/recipes/life/examples/life_sample.scene.json <iamar-checkout>
```

It prints `LIFE_OK` when the scene has the expected life features, every cited city file
exists in the checkout, and the recipe headings match. It does not run the world; a
rendered run is the separate check (see "What is not verified").

## 1. Idle NPCs (engineering, WORKS)

Townsfolk stand at a post with an idle clip, face their work, and stroll between waypoints.
Far from the player they stop costing anything.

- City: `scripts/actors/npc.gd` (post, idle clip, nameplate, strolls), `scripts/actors/npc_facing.gd`
  (townsfolk working at something face it; idle clips for sit, talk, kneel), `scripts/actors/npc_tiers.gd`
  (look and animation per tier), `scripts/actors/hero_life.gd` (breathing, weight shift and glances for
  the hero, the same small-signs idea for the player's own body).
- Cost rule (from `npc.gd`): off-screen NPCs more than 20 m away walk on every third physics tick; anyone
  in view, near, or in a conversation runs at full rate. Beyond the draw range they sleep altogether.
  A town of 125 walkers without this sent the physics step into a spiral far out in the forest.
- Scene data: an `npcs[]` entry with `idle` set (e.g. `"idle": "idle"`), `position`, `yaw`, a `name`.
  The sample world has one.
- Rule for a new world: give every idle NPC an idle clip that suits its job; do not put NPCs on a
  walk with no waypoints (they stand still and read as statues).

## 2. Wind and sway (engineering, WORKS)

Trees, grass and flags move in one shared wind so the whole scene sways together.

- City: `shaders/wind.gdshaderinc` (the shared wind), `shaders/wind_plant.gdshaderinc` and
  `shaders/wind_plant.gdshader` (plants), `shaders/foliage.gdshader` (canopy: trunk rooted, leaves moving),
  `shaders/wind_flag.gdshader` (cloth). Tree generation: `scripts/world/tree_gen.gd`.
- Scene data: an `objects[]` entry with `"sway": true` (schema: "Sway in the shared wind as a tree: trunk
  rooted, canopy moving"). The sample world sets it on two trees.
- Cost: one shader uniform drives every object; no per-tree script runs.
- Trap: a tree with `sway` on but a non-tree mesh (a rock, a building) moves like a tree and looks wrong.
  Use `sway` only for trees, bushes and tall plants.
- Style: canopy colour and leaf density are style; the wind itself is engineering.

## 3. Smoke and fire (style, WORKS in the great halls)

Fireplaces, braziers and chimneys: flames, sparks and a little smoke drawn up a flue.

- City: `scripts/world/masterplan/mp_fireplace.gd` (surround, hearth, layered additive flame billboards,
  rising embers, grey smoke up the flue, one warm light that flickers). Chimneys: the masterplan house
  pieces in `scripts/world/masterplan/mp_buildings.gd`.
- Cost rules: every emitter is capped (CPUParticles3D with a fixed amount), one `OmniLight`, and the
  particles follow the camera only in the Graphics presets that allow them (Fast drops mist and leaves in
  `scripts/world/forest_fx.gd`).
- Layer: style. A different world can use the same engineering caps with its own colours.
- Trap: a fire with a dynamic light per flame in a town of 50 fires. Keep one light per room and let the
  flames be billboards.

## 4. Birds and butterflies (engineering, WORKS)

Birds on the ground and in the sky, and butterflies by the flowers.

- City: `scripts/world/ambient_birds.gd` (ground flocks that burst up as you come near and wheel off;
  far flocks high over the land; placed only when about to be seen and by day; no shadows),
  `shaders/forest_bird.gdshader` (the wing beat), `scripts/world/butterflies.gd` (real 3D butterflies in
  one MultiMesh, placed where flowers are, 24 m areas, by day and within about 30 m of the camera),
  `scripts/world/butterfly_motion.gd` (wing motion).
- Cost: one MultiMesh draw call for all birds (18 triangles each), a few dozen transforms moved per frame.
  Nothing is simulated where nobody looks. The deep wood has its own birds from `forest_fx`, so the open-country
  flocks keep out of it.
- Scene data: birds are an engine ambient system, not a scene object; a world turns them on by default
  and does not list them. Butterflies follow flowers the world places.
- Trap: birds that never leave a flock or fly through the ground. Flocks take off when you come close and land
  again further away; check the flight near terrain in the preview.

## 5. Doors (engineering for the hero, style for the frame, WORKS)

Doors that open for the player, and a companion that waits outside a door when the player goes in.

- City: `scripts/world/buildings.gd` (`door(...)` takes an `open` flag, so a door can be drawn open or closed),
  `scripts/actors/player.gd` (`_door_assist`: the hero is nudged through a doorway), `scripts/gameplay/whelp_doors.gd`
  (which building the hero is inside, and the waiting spot outside its door, from the plan's footprints).
- Cost: the building test is a bounding box first; the polygon is tested only near it.
- Scene data: a building or object's `collision` (`box`, etc.) and, for a companion, the building's door
  line. Doors that are open in the picture must still be walkable.
- Trap: a door drawn open that is still a solid wall for collision. Check the hero can walk through it in
  the real preview world.

## 6. Ambient audio (engineering, WORKS)

Loops that set the mood, and sounds that come from a place.

- City: `scripts/world/ambience.gd` (camera-following motes and pollen by day, fireflies at night),
  `scripts/world/ambient_fish.gd` (fish leaping in ponds near the player, more at dawn and dusk),
  `scripts/world/ambient_birds.gd` (bird calls), `scripts/core/game_audio.gd` (sound levels by area),
  `scripts/world/day_night.gd` (the day cycle that the sounds follow).
- Cost: two fish and two rings, built on the first leap; splashes are one-shot particle bursts.
- Scene data: a `sounds[]` entry without `position` is ambient (not positional), with `loop: true` and
  `autoplay: true`; a sound with `position` fades out by `radius` (default 20 m). Files are `.ogg` only
  (schema: `audio`). The sample world has one ambient loop.
- Trap: a looping ambient wav with no fade at the loop point, or several loops at full volume at once.
  Keep one ambient bed plus a few positional sounds.

## Engineering versus style, in one table

| Recipe | Engineering (every world) | Style (iamar look) |
|---|---|---|
| Idle NPCs | throttle and sleep by distance; idle clips per job | clothing, poses, nameplates |
| Wind | `sway` flag, one shared wind | canopy colour, leaf density |
| Smoke and fire | capped emitters, one light per room | flame colours, ember count |
| Birds and butterflies | one MultiMesh, placed when seen | which species, flight colours |
| Doors | walkable when open, bounding-box test first | door and frame style |
| Ambient audio | one bed plus positional sounds, looped cleanly | which sounds set the mood |

## What is not verified

- The sample scene is checked as data (keys, types, file references and the feature list), not run.
  A rendered run in the real preview world (`iamar-world shots`) is the check that the NPCs idle, the
  trees sway and the sound plays. Until that runs, the status above stays WORKS-by-citation, not
  WORKS-by-run.
- Asset files named in the sample (`assets/*.glb`, `assets/*.ogg`) must exist in the world folder; the
  checker does not check them.
