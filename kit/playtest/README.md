# iamar-world playtest: walk a visitor through a world

`preview` and `shots` show what a world looks like. `playtest` shows whether it **works**: it
starts the real browser game, picks a hero, enters your world the way a visitor does (its NPCs,
quests and world scripts all live), and then plays a list of steps: walk somewhere, talk to an
NPC and pick a dialog choice, pick up a quest item, use a script entity, wait. After every step
it prints the state of every quest of the world and what the world's scripts changed, checks
your expectations, and (with a renderer) saves a screenshot.

```bash
iamar-world playtest worlds/harbour /tmp/harbour_pt --steps steps.json
iamar-world playtest worlds/harbour /tmp/harbour_pt --steps steps.json --headless   # no shots, faster
iamar-world playtest worlds/beach /tmp/beach_pt --auto                               # walk and swim everywhere
```

For a world to explore (a house, a beach, a lake) rather than a quest, `--auto` needs no steps
file: it walks a visitor from the spawn to every room of every generated house, every portal,
NPC and named object, and swims in every swimmable water body (in, dive, back up, out), with
the browser's own movement, and reports what could not be reached (see "Exploring: --auto and
the walking steps" below). That is the "walked it" evidence for a world, instead of "walking
unverified".

Options: `--headless` (no renderer, no shots), `--hero human_male` (the hero to play),
`--hour 17.5` (the browser's clock only, see "What the visitor is" below), `--timeout 600` (seconds for the whole run, including starting
the browser: every wait, hero selection and entering play too, comes out of this one budget).
A first run with a renderer builds the whole city before hero selection, which can take 5 to
10 minutes on a busy computer; when it fails with "did not reach hero selection within
--timeout", raise it (`--timeout 1800`; `tests/kit_playtest/run.sh` takes `PLAYTEST_TIMEOUT`
for its rendered `SHOTS=1` run, default 1800). With a renderer the browser normally opens on
its sign-in start page; the playtest skips it and goes straight to the city (a kit older than
an internal task waited on that page until the timeout, "CITY_PRELOAD done" being its last line: update
the kit, or use `--headless`). Exit status 0 when
every step and expectation passed, 1 when one failed, 2 for bad input (a world that does not
open, a malformed steps file). The browser runs with a private profile for the run: your own
settings, saves and world data are never read or changed, and nothing is kept afterwards.

## What the visitor is

The playtest plays a **returning visitor**: in the run's private profile the browser's tutorial
and its two first-visit quests (`thornbury_welcome`, `welcome_menus`) are marked done, and it
prints `playtest: a returning visitor (...)`. A first-time player is different: until those
quests are done, the browser's two welcome guides, Goodwife Alys ("Movement guide") and Guide
Rowan ("Menu guide"), walk into **every** world they enter, a kit world too, and stand near the
arrival point (the browser's SpawnGuides). They are the browser's, not your world's: do not
script around them and do not take them for city NPCs leaking into your world. A steps file
with `"new_visitor": true` keeps them, to see the world as a first-time player does. A playtest
from a kit older than an internal task shows them in every shot and its talk prompt may name them
("[G] Talk to Goodwife Alys") when they stand nearer than your NPC.

The visitor is **offline**: the run never connects to the iamar hub, so no other visitors
appear and quest progress is the browser's offline practice progress for the whole run
(`playtest: offline ...`). Online, the browser starts a new progress lifetime each time the hub
connection or the world's admission changes, and drops unsaved practice quests then. Headless
those changes land before step 1; with a renderer on a slow computer (llvmpipe) they landed
mid-run, so an accepted quest went back to `-` at the next pickup (kit older than an internal task).
`--online` (or `"online": true` in the steps file) connects anyway; a reset during a step is then
reported as `WARN playtest: the browser reset quest progress during step <n>`.

The city's quarter and street under the minimap ("City Centre", "Outside the South Gate")
showed in kit worlds in every browser built before iamar commit 12bc63d4, which hides it in
every world package (player build 26 still shows it). It is not your world's fault: ignore it in
shots from such a browser.

`hour` (or `--hour`) sets the browser's clock (the HUD time) and nothing else: the city's day
and night are parked while a world is open, and a world's light is fixed by its own
`scene.json` `environment` (`time_of_day`, or `sun.direction`). The playtest prints
`NOTE hour ... sets the browser's clock only` with the world's `time_of_day`. To check the
world at dusk or night, render it with `iamar-world shots <world> <out> --times day,dusk,night`
(kit/shots/README.md), which changes the world's own light for the shot.

To see what a **script effect** looks like (a lamp a quest or `use` step lights, a door that opens),
`shots` cannot: it starts a playerless preview where no step has run (only `--quest-done` redraws a
quest's `on_complete` show/hide). Run the steps with a renderer instead: `SHOTS=1`
(`tests/kit_playtest/run.sh`) or a playtest without `--headless` saves one screenshot per step, taken
after that step's effects (`shots/step_05_use.png`). End the steps with `{"do": "wait", "s": 1}` or a
`goto` to frame the lit result.

## Output

```
STEP 5 use ok
QUEST lost_net ready step=3 counts=[]
EFFECT moved asset:assets/flag.glb [19.1, 1.2, 3.5] -> [19.1, 3.6, 3.5] (2.40 m)
EFFECT light light energy 0.00 -> 8.00
EFFECT sound bell at [16.5, 2.48, 2.5]
EXPECT ok   sound bell played
SHOT /tmp/harbour_pt/shots/step_05_use.png
...
PLAYTEST PASS: 6 step(s), 0 failed -> /tmp/harbour_pt/playtest.json
```

- `STEP <n> <do> ok|FAIL <why>`: the step itself. A failure says why: no such NPC, the dialog
  did not offer that choice (and lists what it offered), no pickup is waiting, or why the
  interact key found nothing (an open panel, world geometry between the player and the target).
- `DIALOG <npc>: <choices>` and `REPLY <text>`: what the NPC offered and answered.
- `QUEST <id> <state> step=<i> counts=[..]`: every quest of the world after the step. State is
  `-` (not started), `active`, `ready` (hand it in), `done`, or `unregistered`: the world declares
  the quest but the browser has no definition for it, so nobody can ever be offered it.
- `EFFECT`: what the world's scripts did during the step: `moved` (an entity moved more than
  5 cm), `light` (a light's energy changed), `sound` (the script played a sound: a built-in
  one by its name, a package sound as `asset:<path>.ogg`), `note`
  (a note to the player), `visible`, `spawned`, `removed`. Entity kinds listed in `ignore`
  (gulls, boats: ambient motion) are left out.
- `EXPECT ok|FAIL <what>`: each expectation of the step.
- `<out>/playtest.json`: the same, per step, plus the player's position.
- `<out>/shots/step_<nn>_<do>.png`: one screenshot per step (not with `--headless`).

## The steps file

```json
{
  "about": "what this playtest checks",
  "hour": 17.5,
  "new_visitor": false,
  "online": false,
  "hero": "human_male",
  "ignore": ["gull.glb", "boat_sail.glb"],
  "steps": [
    {"do": "talk", "npc": "harbour_master", "choose": "accept",
     "expect": [{"quest": "lost_net", "state": "active", "step": 0}]},
    {"do": "pickup", "quest": "lost_net", "expect": [{"quest": "lost_net", "step": 1}]},
    {"do": "goto", "trigger": "bell", "expect": [{"quest": "lost_net", "state": "ready"}]},
    {"do": "use", "entity": "bell.glb", "settle": 2.0, "expect": [{"sound": "bell"}, {"moved": "flag.glb"}]},
    {"do": "talk", "npc": "harbour_master", "choose": "complete", "expect": [{"quest": "lost_net", "state": "done"}]}
  ]
}
```

Steps (`do`):

| do | fields | what it does |
|---|---|---|
| `goto` | `at: [x, z]` or `[x, y, z]`, or `npc`, `trigger`, `pickup` (quest id), `entity` (kind) | stands the player there (on the floor under it, facing it) |
| `talk` | `npc` (id or name), `choose` (optional), `close` (default true) | walks up, presses interact, picks the choice: `accept`, `complete`, `bye`, or the text of a choice (or its start). With no `choose` it only reads the greeting and choices; either way the dialog is closed after the step unless `close` is false (an open dialog blocks every later `talk`, `pickup` and `use`: "a gameplay panel is open") |
| `pickup` | `quest` (optional) | walks to the waiting quest item and presses interact |
| `use` | `entity` (kind: `bell.glb`, `asset:assets/bell.glb`, `light`, ...), `index` | stands 1.8 m from a world-script entity (on the spawn side) and presses interact the way the key does: the key acts on the **nearest** script entity within 2.5 m (3D, from the visitor's feet) of a script that exports `on_interact`. The step fails when that is not the named entity (`nearest script entity is ... at ... m`) or when nothing is in reach (`no script entity within the key's 2.5 m: ... m across, ... m up`): a bell hung 2.5 m up is out of reach of the key, so give it a handle or an interact point near the ground (`on_click` still works from 6 m) |
| `wait` | `s` (seconds) | lets time pass (timers, animations) |
| `walk_to` | `at`, `npc`, `trigger`, `pickup`, `entity` (as `goto`), or `object` (an object or primitive id), `portal`, `water`, `room` (`"<house>/<room>"`), `spawn: true`; `near` (m) | **walks** there with the move keys (see "Exploring" below) |
| `enter` | `object` (a house) or `room` (`"<house>/<room>"`) | walks in through the house's front door; with `room`, on along the corridor (and up the stair) into that room, and fails when the visitor does not end inside it |
| `climb` | `object` (a house with two floors) or `to: [x, y, z]` | walks up the house's stair (or to that point) and fails unless the feet end within 0.6 m of the top's height |
| `swim_to` | `water` (id, or index without one) or `at` | walks into the water to its middle and fails unless the visitor is swimming there |
| `dive` | `depth` (m of water over the head, default 1.5), `s` (most seconds, default 10) | holds swim-down while swimming and prints `UNDERWATER` (see "Exploring") |
| `surface` | | holds swim-up until the head is out (it does not jump out) |
| `look_at` | `at: [x, y, z]`, or `npc`, `entity`, `object`, `trigger`, `water`; `clear: true`; or `spawn_view: true` | turns the view to it from where the visitor stands and prints `LOOK <m> m, line of sight clear` or `blocked by <node>` (`clear: true` fails a blocked view); `spawn_view` stands on the spawn facing its way. With a renderer the step's shot is that view |
| any step | `from: "spawn"` | starts the step back on the spawn point |

Every step also takes `settle` (seconds to wait after it, default 1) and `expect`, a list of:

| expectation | passes when |
|---|---|
| `{"quest": id, "state": "active"\|"ready"\|"done"\|"", "step": i}` | the quest is in that state / on that step |
| `{"moved": kind}` | an entity of that kind moved during the step |
| `{"light": kind, "above": e}` | a light of that kind now has energy above `e` (0 while it is hidden) |
| `{"visible": kind, "is": true\|false}` | that entity or scene node is shown (default) or hidden now |
| `{"sound": name}` | the world's script, or a quest's `on_complete` `play`, played that sound during the step. A package sound (`sound_play("asset:audio/harbour_bell.ogg", ...)`) matches `asset:audio/harbour_bell.ogg`, `audio/harbour_bell.ogg` or `harbour_bell` |
| `{"note": text}` | the script showed a note containing the text |
| `{"dialog": text}` | the NPC's text or reply contains it |
| `{"choice": text}` | the dialog offered a choice containing it |
| `{"player_y": [min, max]}` | the visitor's feet are at that height after the step |
| `{"swimming": true\|false}` | the visitor is (not) swimming right after the step's action |
| `{"head_under": true\|false}` | the visitor's head is (not) under water right after the action |
| `{"underwater": true\|false}` | the browser's underwater view (water-tinted fog, no sky) is on (off) |
| `{"in_room": "<house>/<room>"}` | the visitor stands inside that room of a generated house |

`kind` is a world-script entity's kind, or the scene id of an object, primitive or light that
a quest's `on_complete` shows or hides (`"on_complete": {"show": [...], "hide": [...], "play": [...]}`,
applied by the browser's QuestEffects, not by a script). Those changes print as
`EFFECT visible <id> true|false`, `EFFECT light <id> energy a -> b` and `EFFECT sound <id>`
in the step that hands the quest in.

Trap: a world with more than 6 point and spot lights keeps only the 6 nearest the camera on
(the browser's light pool). A quest's lamp checked from where its quest giver stands can be off
for that reason alone: `goto` the lamp first, then `expect` its light
(`tests/kit_playtest/harbour_ring_bell.steps.json`). A lamp that `on_complete` still keeps
hidden stays off even next to it (browser iamar 9897cd7a and later; older browsers light it).

Seeing a script's result: `shots` has no flag that runs a world script (`--quest-done` only draws
a quest's `on_complete` show/hide/light as handed in; a lamp a script lights with `lightLamp()` stays
off there). To get a picture of a script-lit lamp, run the `use` step in `playtest` with a renderer:
it saves `shots/step_NN_<do>.png` after the step, with the script's effect in place. `goto` onto a
roofed room's floor works the same way: the visitor is placed on the floor under `[x, z]`, not the roof.

A step's `settle` and `wait` count script time, the clock of `iamar.time()` and `timer_after`,
not the wall clock. Below 15 fps (a busy computer, a software renderer) the engine caps each
frame's step at 1/15 s, so script time runs slower than the wall clock and a timer comes due
late. The waits then take longer, and the run ends with `NOTE slow frames: the steps' waits
ran N s longer than script time` (`slow_frames_s` in playtest.json). Kits before this change
waited on the wall clock: on a slow run, an effect started by a `timer_after` was missing from
its step even though the script was correct (harbour a5 gap G15b: the lighthouse lamp's light
and sphere, 1.8 s after the bell). Give a timer's effect a `settle` longer than the timer.

Quest, NPC and trigger ids are the ones in your `scene.json`. `goto`, `talk`, `pickup` and `use`
**place** the visitor: they check what happens at each place, not whether a path is walkable.
The walking steps below check the path.

## Exploring: --auto and the walking steps

`walk_to`, `enter`, `climb`, `swim_to`, `dive`, `surface` and `look_at` move the visitor the way
a player does (an internal task): the move key is held and the hero is steered toward each waypoint,
so the browser's own walking, stepping, swimming, diving and climbing out run. A wall in the
way, a step too high, a doorway too narrow, a gap to fall through or a shore without a low
edge shows up the way a visitor meets it:

```
STEP 4 enter FAIL stuck at [16.12, 0.15, 0.31], 2.1 m short of corridor at the doorway (waypoint 3/5)
FALL 3.4 m at [12.0, 0.0, 4.0] (on the way to the middle of water pool)
UNDERWATER head 1.52 m under, floor 1.38 m below, sight 14 m, fog #2d6a7a, view on
LOOK 12.4 m, line of sight clear
```

- `stuck`: no 0.3 m of progress for 2.5 s of script time; `did not reach`: the waypoint's time
  ran out. Both name where the visitor stands and the waypoint it was heading for.
- `FALL <m> m`: a drop of 3 m or more through the air (not into water) on the way; it fails the
  step. `playtest.json` keeps every step's `walked` (m), `route` (waypoints passed) and `falls`.
- `UNDERWATER`: after a `dive`, how deep the head is, how far the floor is below it, how far the
  water lets the visitor see (`clarity`, browser 8444e450 and later; `?` on older browsers) and
  its fog colour, and whether the underwater view is on. With a renderer the dive's shot is the
  underwater view: check it for the floor and the fish, not the sky.
- Houses: an object whose glTF has a rooms sidecar beside it (`assets/house.glb` and
  `assets/house.rooms.json`, written by `iamar-world assets building house`, see
  docs/HOUSE_ROOMS.md) is a house. Keep the sidecar in the world's `assets/` to walk its rooms:
  `enter` with `room` walks from outside the front door along the corridor (with two floors:
  beside the stair, up it, onto the landing) to the room's doorway and into the room. The route
  is straight between waypoints, so the way from the spawn to the front door must be open.
  A room route ends in the room's middle, where `assets building house --furnish` puts a
  "middle" piece (the dining room's trestle table): the walk may then stop short of the last
  waypoint and can fail the room. Furnish after you have walked the rooms, or check a failed
  room's `stuck at` point against its furniture before moving a wall.
- Water: give a swimmable body a shore the visitor can walk in from, a floor at `depth`, and
  (to get out) a bank, step or deck edge no more than about 1 m above the surface.
- Portals: `walk_to` a portal stops 2.5 m in front of it, so the run never travels.

`--auto` (on its own, or after a steps file's steps) adds one step per place, each from the
spawn: for every swimmable water body `swim_to`, `dive`, `surface` and a walk back to the spawn
(out of the water); for every house `enter` and an `enter` of every room; a `walk_to` of every
portal, NPC and named object or primitive (nearest first, at most 24; the ground, big slabs and
houses left out); and a `look_at` from the spawn. It ends with one line per place that failed
and a count:

```
AUTO unreachable room house/bedroom_4: stuck at [...], 1.2 m short of stair top (waypoint 6/10)
AUTO 14 step(s): 13 ok, 1 failed, 0 fall(s)
```

`<out>/playtest.json` then has `"auto": {"steps", "failed", "falls"}` and each auto step its
`"auto"` label. Walking takes real time (about 3 to 5 m/s): budget `--timeout` for the
distances (the default 600 s covers a house and a beach of a few hundred metres).

## Examples

- `kit/playtest/harbour_lost_net.json`: the errand of the harbour blind-test world, attempt 2
  (`kit/blindtest/harbour/attempt-2/world`: net, talk, the bell, then the hand-in). Its `use`
  step FAILS on purpose: the bell hangs 2.48 m up over the quay, 3.06 m from a visitor standing
  1.8 m out, so the interact key never reaches it (only a click does). A world that wants its
  bell rung by the key needs an interact point within 2.5 m of where a visitor stands.
- `tests/kit_playtest/harbour_ring_bell.steps.json`: Lantern Harbour (`kit/blindtest/harbour/attempt-3/world`,
  attempt 3) end to end: a `talk` with no choice, both quests, and ring_bell's `on_complete`
  (lantern shown, dark lantern hidden, bell sound, lantern light checked at the pier).
- `tests/kit_playtest/reach/`: script entities in and out of the key's reach (a low cylinder, a
  high sphere, a box with a nearer sphere beside it), with their TypeScript source.
- `tests/kit_playtest/explore/`: a generated two-floor house (with its rooms sidecar), a pool, a
  portal and a crate, walked, climbed, swum and dived (`steps.json`) and explored with `--auto`.
- `tests/kit_playtest/`: a sample world with a three-step quest and its test
  (`tests/kit_playtest/run.sh`; the routes alone, without a browser: `tests/kit_playtest/routes.sh`,
  which runs `tests/kit_playtest/routes_test.gd` on the route and `--auto` planners).

The command is `scripts/kit/world_playtest.gd` (routes for the walking steps and `--auto`:
`scripts/kit/world_playtest_routes.gd`; both in the kit pack), started by `kit/iamar-world`
and `kit/iamar-world.cmd` with a private browser profile.
