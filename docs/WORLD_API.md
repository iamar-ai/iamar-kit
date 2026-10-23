# iamar world API — version 0.4

World scripts are how an iamar world gets behaviour: a flock that runs from
visitors, a door that opens for a password, a game with rules. They are
**WebAssembly modules** (`scripts/*.wasm` in a world package) that the browser
runs in a sandbox. A script can do exactly what this document lists and nothing
else: it has no files, no network, no clock beyond `time()`, no threads, and no
engine types. That is what lets a visitor walk into a world written by a
stranger's AI agent.

This is the successor of the 2009 Semblis world scripts
(`legacy/iserver_media/callbackTest.sem` in `the iamar browser source (not public)`): where Semblis
registered callbacks by name, a WebAssembly script *exports* them.

| Semblis (2009) | world API 0.4 |
|---|---|
| `(setPlayerEnterFunc "newUserEntered")` | export `on_enter(player)` |
| `(setPlayerLeaveFunc "UserLeft")` | export `on_leave(player)` |
| `(setSigReceivedFunc "msgReceived")` + `popFloat` | export `on_message(ptr, len)` |
| `sendMsgToWx`, `display` | `ui_note`, `log` |
| `clearBuffer` / `pushInt` / `sentBufferTo` | `world_message(ptr, len)` |

Code lives in the iamar repository:

| Path | What |
|---|---|
| `scripts/sandbox/world_api.gd` | the API table and limits (the source of truth this document describes) |
| `scripts/sandbox/world_script.gd` | the host: loads a script, answers its calls, dispatches events, enforces budgets |
| `scripts/sandbox/script_entity.gd` | what an entity handle is on the browser side |
| `scripts/sandbox/iamar_script_host.gd` | glue for running a script inside the iamar browser |
| `addons/wasm/` | the WebAssembly runtime (a GDExtension around Wasmtime) |
| `api/world_api.json` | the machine-readable spec every binding is generated from |
| `api/typescript/iamar-world.d.ts` | **the TypeScript declarations world creators write against** |
| `api/ui_page.schema.json` | the world UI page vocabulary (0.4): what `ui_page_set` / `ui_page_patch` accept |
| `tools/typescript-world/` | the TypeScript -> sandboxed `.wasm` build (`kit/iamar-world compile-typescript`) |
| `api/rust/iamar-world/`, `api/iamar_world.h` | internal: raw-ABI bindings for the sandbox's own test modules |
| `examples/scripts/` | internal: hostile and benchmark test modules; built `.wasm` in `examples/wasm/` |

## 1. Writing a script (for agents)

**World scripts are written in TypeScript** (the maintainer, 2026-10-10: the only
language offered to world creators). Ordinary strict TypeScript, checked and
compiled by the official compiler, then built into one sandboxed `.wasm` that
carries a small JavaScript engine (QuickJS). Every function in §3 is
`iamar.<name>(...)` with JavaScript types: strings, numbers, booleans,
`Uint8Array`, and return values instead of output pointers
(`api/typescript/iamar-world.d.ts`, generated from the spec). Callbacks (§4)
are plain global functions; `on_init` is required.

```ts
// world.ts: a chicken next to every visitor, and a greeting
function on_init(): void {
  iamar.log("welcome world started");
}

function on_enter(player: number): void {
  const p = iamar.player_pos(player);
  if (p === null) return;
  const x = p[0] + 2, z = p[2];
  const hen = iamar.entity_spawn("chicken", x, iamar.ground_y(x, z), z, 0);
  if (hen > 0) iamar.entity_set_grounded(hen, true);
  iamar.ui_note(`Welcome, ${iamar.player_name(player) ?? "traveller"}!`);
}
```

```sh
# Fast path (default): the pure-Node packer writes your compiled JavaScript
# into the prebuilt QuickJS guest. No toolchain, no downloads.
# Needs Node >= 20 and the official TypeScript 5.9.3 compiler:
#   npm i typescript@5.9.3 --prefix kit/ts-world
# In a Linux/macOS source checkout, point to that separate install:
#   export IAMAR_TS_COMPILER="$PWD/kit/ts-world/node_modules/typescript/lib/typescript.js"
#   (or set IAMAR_TS_COMPILER=/absolute/path/to/typescript.js)
kit/iamar-world compile-typescript world.ts <package-template> <fresh-out>
# -> <fresh-out>/world/scripts/world.wasm, listed in the package manifest
```

The source-checkout wrapper otherwise searches for TypeScript beside the
source packer under `tools/typescript-world/`, not the `kit/ts-world` install
above. Windows source checkouts likewise need an absolute `IAMAR_TS_COMPILER`
path to that install. See [TypeScript setup](TYPESCRIPT_WORLDS.md#1-set-up-once)
for the complete bundle and source-checkout prerequisites.

`compile-typescript` keeps a `--from-source` flag for maintainers: it
recompiles the whole QuickJS guest with clang from the WASI SDK (~1 GB Linux
toolchain, about 90 s per world) exactly as before. Everyone else uses the
packer (about a second per world): it type-checks and emits `world.ts` with
the official TypeScript 5.9.3 compiler and the same checks (callback
validation, no imports/async), writes the emitted JavaScript *source* into a
reserved 1 MiB slot in the prebuilt guest (`tools/typescript-world/prebuilt/`),
runs the static Wasm ABI audit, and writes the package exactly like the
source build. Packing is deterministic: the same input yields byte-identical
output on Windows, macOS and Linux. The old toolchain path is documented in
`tools/typescript-world/README_TOOLCHAIN.md`.

Rules that keep a script working:

* One global `world.ts`: no `import`/`export`, no `async`/`await`; callbacks
  return `void`. `Date` and `eval` do not exist; `Math.random()` is the
  world-seeded `iamar.rand()`, so every visitor's copy draws the same numbers.
* Keep state in top-level variables; there is one instance per world per
  visitor, and callbacks never run concurrently.
* Do the work in small pieces. Every callback has a fuel budget (§5): the
  engine itself costs ~7 M of the 20 M `on_init` budget; a long computation
  belongs in `on_tick`, spread over several ticks. Heavy work (movement,
  physics, particles) is the browser's: give orders, do not simulate.
* Check results: host failures come back as negative status codes or `null`;
  a malformed argument throws before it reaches the browser.
* Multiplayer: each visitor runs their own copy. Let the copy where
  `iamar.is_authority()` is 1 decide shared state and send it with
  `iamar.world_message` to the others (`on_message_from`).

The full example using every group is `examples/typescript-showcase/world.ts`;
the current build and limits are in [TYPESCRIPT_WORLDS.md](TYPESCRIPT_WORLDS.md).
The source-only toolchain is in `tools/typescript-world/README_TOOLCHAIN.md`.

*Internal:* the browser's own sandbox tests use small Rust/C/WAT modules
(`api/rust/iamar-world`, `api/iamar_world.h`, `examples/scripts/`,
`tests/sandbox/`). They speak the raw ABI below and are not an authoring path
for creators.

## 2. The ABI

* A script is a WebAssembly 1.0 module (plus bulk memory and the other
  proposals Wasmtime enables by default; no threads or shared memory).
* It imports functions only, only from module **`"iamar"`**, only names in §3,
  each with exactly the signature listed. Anything else fails instantiation
  with a message naming every offending import.
* Types are `i32`, `i64`, `f32`, `f64`. In signatures below, `i` = i32,
  `f` = f32, `F` = f64; `a b > r` means parameters `a b`, result `r`.
* Strings and byte strings are `(ptr: i32, len: i32)` pairs pointing into the
  script's exported memory, which must be named **`memory`**. Strings are UTF-8
  and not NUL-terminated.
* Names (entity kinds, animation and sound names) are printable ASCII. Text for
  `log` and `ui_note` must be valid UTF-8 (otherwise the call does nothing);
  control and bidi characters are removed, and notes are shown marked as the
  world's (`[world] ...`). `kv` keys are byte strings; a key longer than 128
  bytes returns `E_LIMIT`.
* Output arguments (`out4`, `out6`) point at 4 / 6 consecutive little-endian
  `f32`s (16 / 24 bytes) the host writes.
* A pointer range outside the script's memory **traps** the call (it is a bug
  in the script). A bad *value* (unknown handle, NaN coordinate, over a limit)
  returns a negative error code instead:

| code | name | meaning |
|---|---|---|
| 0 | `OK` | |
| -1 | `E_BAD_HANDLE` | no such entity / player |
| -2 | `E_BAD_ARG` | NaN, infinite, out-of-range or malformed argument |
| -3 | `E_LIMIT` | over a quota or rate limit |
| -4 | `E_NOT_FOUND` | unknown kind, asset, animation, sound or key |

Coordinates are metres in the world's frame: +Y up. `yaw` is radians about +Y;
yaw 0 faces −Z. Positions must be finite and within ±100 km.

## 3. Host functions (imports from `"iamar"`)

The full list, generated from [`api/world_api.json`](../api/world_api.json)
(the machine-readable spec; `python3 tools/world_api_docs.py` rewrites these
tables). TypeScript worlds call the same functions as `iamar.<name>(...)` with
JavaScript types ([TYPESCRIPT_WORLDS.md](TYPESCRIPT_WORLDS.md)).

<!-- world_api:imports -->
**Core**

| function | signature | since | notes |
|---|---|---|---|
| `api_version()` | ` > i` | 0.1 | (major << 16) \| minor of the browser's API: 4 for 0.4. |
| `log(text_ptr, text_len)` | `i i > ` | 0.1 | A line in the world's log (the author's console). <= 512 bytes, 50/s. |
| `rand()` | ` > f` | 0.1 | Uniform in [0, 1). Seeded per world, so every visitor's copy draws the same sequence. |
| `time()` | ` > F` | 0.1 | Seconds since the script started (game time; pauses with the game). |

**Entities**

| function | signature | since | notes |
|---|---|---|---|
| `entity_spawn(kind_ptr, kind_len, x, y, z, yaw)` | `i i f f f f > i` | 0.1 | A new entity; returns its handle (> 0). Kinds: chicken, box, sphere, marker, cylinder, capsule, cone, plane, light, spot, particles, label, mesh:<id> (from mesh_create), or asset:<path>.glb from the world's own package. <= 256 entities (manifest budget up to 1024). |
| `entity_remove(h)` | `i > i` | 0.1 | Remove one of this script's entities. |
| `entity_set_pos(h, x, y, z, yaw)` | `i f f f f > i` | 0.1 | Jump there; stops any move_to. |
| `entity_move_to(h, x, y, z, speed)` | `i f f f f > i` | 0.1 | Walk there in a straight line at speed m/s (<= 50), turning to face the way it goes. |
| `entity_pos(h, out)` | `i i > i` | 0.1 | Writes x, y, z, yaw. |
| `entity_play_anim(h, name_ptr, name_len)` | `i i i > i` | 0.1 | chicken: idle, walk, run, peck, flap; glTF assets: any animation in the file. |
| `entity_set_tint(h, r, g, b, a)` | `i f f f f > i` | 0.1 | Wash the entity in a colour (0-1); a = 0 removes it. |
| `entity_set_grounded(h, on)` | `i i > i` | 0.1 | A grounded entity stays on the terrain while it moves. |
| `entity_set_scale(h, sx, sy, sz)` | `i f f f > i` | 0.2 | Each axis clamped to 0.01-100. |
| `entity_set_visible(h, on)` | `i i > i` | 0.2 | Show or hide. |
| `entity_set_rot(h, pitch, yaw, roll)` | `i f f f > i` | 0.2 | Radians; pitch about +X, yaw about +Y, roll about +Z. |
| `entity_stop_anim(h)` | `i > i` | 0.2 | Stop the current animation. |

**Look: colour, lights, particles, labels, meshes**

| function | signature | since | notes |
|---|---|---|---|
| `entity_set_color(h, r, g, b, a)` | `i f f f f > i` | 0.3 | Base colour of a primitive or label, or the colour of a light / particles. a < 1 makes primitives see-through. Components clamped to 0-1. |
| `entity_set_material(h, metallic, roughness, emission, unshaded)` | `i f f f f > i` | 0.3 | Surface of a primitive or mesh entity: metallic 0-1, roughness 0-1, emission energy 0-16 (glows in its own colour), unshaded >= 0.5 ignores lighting. |
| `entity_set_light(h, energy, range, angle)` | `i f f f > i` | 0.3 | For light and spot entities: energy 0-16, range 0.1-60 m, spot cone angle 1-89 degrees (ignored for light). Colour comes from entity_set_color. No shadows. The cap is on lights *this script* spawned: `entity_spawn` of a `light` or `spot` returns `E_LIMIT` (-3) once the script holds 16 (manifest `limits.max_lights` may lower it); scene.json lights are not counted, and nothing is logged, so check the returned handle. |
| `entity_set_particles(h, preset_ptr, preset_len, rate)` | `i i i f > i` | 0.3 | For particles entities: preset smoke, fire, sparks, dust, magic, rain, snow, bubbles; rate 0-200 particles/s (0 stops it). <= 8 emitters per script (the cap counts only particle entities this script spawned; `entity_spawn` of `particles` returns `E_LIMIT` (-3) past it). |
| `entity_set_text(h, text_ptr, text_len, size)` | `i i i f > i` | 0.3 | For label entities: text floating in the world, always facing the camera. <= 128 bytes; size 0.05-4 m per line. |
| `mesh_create(vertices, vertex_count, indices, index_count)` | `i i i i > i` | 0.3 | A custom triangle mesh; returns a mesh id (> 0) to spawn as kind mesh:<id>. vertices: vertex_count x 8 f32 (x, y, z, nx, ny, nz, u, v); indices: index_count u32 (triangles, so a multiple of 3). <= 4096 vertices and 12288 indices per mesh (bigger models belong in a .glb asset), 64 meshes, 1,000,000 vertices and 3,000,000 indices per world, 4 calls per second. |

**World**

| function | signature | since | notes |
|---|---|---|---|
| `ground_y(x, z)` | `f f > f` | 0.1 | Terrain height at (x, z). |

**Physics**

| function | signature | since | notes |
|---|---|---|---|
| `raycast(x1, y1, z1, x2, y2, z2, out)` | `f f f f f f i > i` | 0.2 | Read-only ray query (<= 10 km): writes hit x, y, z and normal x, y, z; returns the hit entity's handle, 0 for world geometry, -4 on a miss. |
| `entity_set_collider(h, shape, sx, sy, sz)` | `i i f f f > i` | 0.3 | Give an entity a solid shape players bump into and raycasts hit: shape 0 none, 1 box (sx, sy, sz = full size), 2 sphere (sx = radius), 3 capsule (sx = radius, sy = height). Sizes 0.01-100. |
| `entity_set_physics(h, mode, mass)` | `i i f > i` | 0.3 | mode 0 scripted (the default: only the script moves it), 1 dynamic (falls, bounces and is pushed; needs a collider), 2 static. mass 0.01-10000 kg. <= 128 dynamic bodies per world. |
| `entity_apply_impulse(h, x, y, z)` | `i f f f > i` | 0.3 | Push a dynamic entity (N*s). Its velocity afterwards is capped at 200 m/s however many impulses a callback gives, and a dynamic entity never moves faster than 200 m/s. |
| `entity_set_velocity(h, x, y, z)` | `i f f f > i` | 0.3 | Set a dynamic entity's velocity (m/s, each component clamped to +/-200). |
| `entity_velocity(h, out)` | `i i > i` | 0.3 | Writes the entity's velocity x, y, z (0 for scripted entities that are not moving). |
| `entity_set_trigger(h, radius)` | `i f > i` | 0.3 | Make the entity a trigger zone of this radius (0.1-50 m; 0 turns it off): on_trigger_enter / on_trigger_exit fire as players come and go. |

**Sound**

| function | signature | since | notes |
|---|---|---|---|
| `sound_play(name_ptr, name_len, x, y, z)` | `i i f f f > i` | 0.2 | A sound at a point: cluck, squawk, bell, click, door, jump, land, select, gear, or asset:<path>.ogg from the world's package (<= 2 MiB each, 32 files). 10/s. |

**Timers**

| function | signature | since | notes |
|---|---|---|---|
| `timer_after(ms, tag)` | `i i > i` | 0.2 | Calls on_timer(tag) after ms (0-86,400,000). <= 64 pending. |
| `timer_cancel(tag)` | `i > i` | 0.2 | Cancels every pending timer with this tag; returns how many. |
| `timer_repeat(ms, tag)` | `i i > i` | 0.2 | Calls on_timer(tag) every ms (1-86,400,000) until cancelled. |

**Players**

| function | signature | since | notes |
|---|---|---|---|
| `players_count()` | ` > i` | 0.2 | Players in the world now, including remote visitors. |
| `player_id(index)` | `i > i` | 0.2 | Id of the index-th player (0 <= index < count), ascending. |
| `player_pos(id, out)` | `i i > i` | 0.1 | Writes x, y, z, yaw. |
| `player_set_pos(id, x, y, z, yaw)` | `i f f f f > i` | 0.2 | Teleport the local player (portals, respawns, checkpoints). A remote player's own copy of the script moves them; here it returns -1. |
| `player_is_local(id)` | `i > i` | 0.3 | 1 for the player at this keyboard, 0 for a remote visitor, -1 for an unknown id. |
| `player_name(id, out, cap)` | `i i i > i` | 0.3 | Copies up to cap bytes of the player's display name (UTF-8); returns its full length. |
| `player_key(id, out, cap)` | `i i i > i` | 0.3 | A stable key for the player that is the same in every visitor's copy of the script (player ids are local to each copy). ASCII, <= 64 bytes; returns its full length. |

**Storage**

| function | signature | since | notes |
|---|---|---|---|
| `kv_get(key_ptr, key_len, out, cap)` | `i i i i > i` | 0.1 | Copies up to cap bytes of the value; returns its full length, or -4. |
| `kv_set(key_ptr, key_len, value_ptr, value_len)` | `i i i i > i` | 0.1 | A value of 0 bytes deletes the key. Keys <= 128 bytes, values <= 4 KiB, 64 KiB per world. Stored on this visitor's machine. |

**Network**

| function | signature | since | notes |
|---|---|---|---|
| `world_message(data_ptr, data_len)` | `i i > i` | 0.1 | Send bytes (<= 1 KiB, 20/s) to every other visitor's copy of this script; they arrive in on_message_from (or on_message). Peer-to-peer over the room's encrypted links. |
| `message_to(id, data_ptr, data_len)` | `i i i > i` | 0.3 | Send bytes to one remote player's copy of this script (same limits as world_message, sharing its rate). |
| `is_authority()` | ` > i` | 0.3 | 1 if this copy is the world's authority, else 0: the copy whose visitor has the smallest player key among everyone in the room, so normally exactly one copy is. Use it to coordinate (who spawns, who keeps score), never as security: a hostile visitor can arrange to be the authority, so check what other copies send you. |

**Camera**

| function | signature | since | notes |
|---|---|---|---|
| `camera_set(mode, x, y, z, tx, ty, tz)` | `i f f f f f f > i` | 0.3 | mode 0 gives the camera back to the player; mode 1 looks from (x, y, z) at (tx, ty, tz) (cutscenes, puzzles). Esc, the browser's menus and leaving the world always give it back, and after Esc the script cannot take it again for 10 seconds (-3). |

**Input**

| function | signature | since | notes |
|---|---|---|---|
| `input_bind(key, on)` | `i i > i` | 0.3 | Ask for on_input events for a key: Godot key codes for A-Z (65-90), 0-9 (48-57), Space (32) and the arrows (4194319-4194322). Esc, Enter, Tab and the F keys are the browser's and are refused. The key keeps its normal game meaning too. <= 32 keys. |

**The world's screen layer**

| function | signature | since | notes |
|---|---|---|---|
| `ui_note(text_ptr, text_len)` | `i i > ` | 0.1 | A short note on the player's screen, marked as the world's. <= 512 bytes, 4/s. |
| `ui_text(id, text_ptr, text_len, x, y, size)` | `i i i f f f > i` | 0.3 | Create or update text on the world's screen layer at (x, y) in 0-1 of the window, size 8-64 px. <= 256 bytes. The layer sits under the browser's own UI and is framed as the world's. |
| `ui_button(id, text_ptr, text_len, x, y, w, h)` | `i i i f f f f > i` | 0.3 | Create or update a clickable button (position and size in 0-1 of the window); a click calls on_ui(id). |
| `ui_bar(id, value, x, y, w)` | `i f f f f > i` | 0.3 | Create or update a progress bar filled to value (0-1); its colour follows entity-style ui_color. |
| `ui_color(id, r, g, b, a)` | `i f f f f > i` | 0.3 | Colour of a UI element's text or fill (0-1). |
| `ui_remove(id)` | `i > i` | 0.3 | Remove a UI element. Ids are the script's own (1-2,147,483,647); <= 32 elements. |
| `ui_page_set(page, json_ptr, json_len)` | `i i i > i` | 0.4 | Create or replace page 1-8 from a JSON page (api/ui_page.schema.json): a tree of nodes the browser builds into its own controls. <= 64 KiB, <= 512 nodes per page, <= 2000 nodes across the world's pages. The page stays hidden until ui_page_show. Invalid JSON or schema gives E_BAD_ARG with the error path in the world's log. |
| `ui_page_patch(page, node, json_ptr, json_len)` | `i i i i > i` | 0.4 | Change one node's properties (text, value, style, visible, enabled, children...; $defs/patch in the schema) without rebuilding the page. <= 8 KiB, 60 patches/s per page. |
| `ui_page_show(page, mode, entity)` | `i i i > i` | 0.4 | mode 0 hidden, 1 overlay (a panel under the browser's own UI, framed as the world's), 2 modal (centred, takes mouse and keys; Esc always closes it; for 1.5 s after the player closes a modal no page may open as one, E_LIMIT), 3 surface drawn on entity (a box or plane of this script; the page fills its front face; <= 4 surfaces). entity is 0 unless mode is 3. |
| `ui_page_surface(page, px_w, px_h)` | `i i i > i` | 0.4 | Resolution of a page shown as a surface, 128-1024 pixels a side (default 512 x 512). |
| `ui_page_remove(page)` | `i > i` | 0.4 | Remove a page and its controls. |
| `ui_value(page, node, out, cap)` | `i i i i > i` | 0.4 | Copy an input's current value as UTF-8 (input/textarea text, checkbox "0"/"1", slider as decimal text, select as the chosen index) into out, up to cap bytes; returns its full length. |
| `ui_focus(page, node)` | `i i > i` | 0.4 | Move keyboard focus to an input on an overlay or modal page (a surface page needs the player's click first). E_BAD_ARG while the browser has the keyboard (address bar, chat, a browser panel, the Esc menu). |
<!-- /world_api -->

**World UI pages (0.4).** Beyond the 32 fixed `ui_*` elements, a script can
own up to 8 *pages*: a page is engine-neutral JSON (`column`, `row`, `grid`,
`stack`, `scroll`, `panel`, `text`, `heading`, `image`, `button`, `link`,
`input`, `textarea`, `checkbox`, `slider`, `select`, `progress`, `divider`,
`spacer`, `list`) defined by `api/ui_page.schema.json`, which the browser builds
into its own native controls. No HTML, no scripts, no URLs: `link` only fires
an event, images come only from the world's signed package. `ui_page_patch`
changes one node without rebuilding the page; `ui_page_show` places it as an
overlay, a modal (Esc always closes it) or a surface on one of the script's
entities; input values are read on demand with `ui_value`, and everything that
happens comes back through `on_ui_event(page, node, kind)`. In TypeScript,
`iamar.ui_page_set(1, { root: { type: "text", text: "Hello" } })` is checked
against the `IamarWorld.UiPage` types. Design: `docs/WORLD_UI_PAGES_DRAFT.md`.
A surface page is drawn on a `box` entity's +Z face (the glTF front) or a
`plane` entity's upper face, stretched with the entity's scale, so pick a
`ui_page_surface` resolution with the face's aspect. The page is laid out at
no more than 224 pixels per metre of face (a 2.4 x 1.5 m counter lays out at
538 x 336 even at 768 x 480), so its text stays readable a few metres away; the
chosen resolution only sharpens it. It is drawn unshaded, in its own colours,
so it reads the same by day and at night, inside a thin wood frame. At most 4 surfaces; the
player clicks one with the mouse within 15 m (not through walls), and a click
on a text field there takes the keys until Esc. Beyond 40 m a surface keeps its
last frame. Removing the entity leaves the page hidden, not removed.
A complete world with pages in every place (a shop counter and a notice board
on surfaces, a modal journal, an overlay) is `examples/typescript-ui-shop/`;
the page recipes are in `kit/recipes/TECHNIQUES.md` (area "Interface").

The key/value store belongs to the world and survives restarts when the host
gives it a file (`WorldScript.kv_path`); it lives with the world host once
worlds are hosted (phase 5).

**Quest state in `kv`** (browser 08285aa and later, package worlds). Keys
beginning `quest:` are the browser's read-only view of this visitor's quests
(WORLD_FORMAT.md 4.14): `kv_get("quest:<id>")` for a quest of this world, or
`"quest:<address>#<id>"` for another world's (`"quest:oakhaven#summons"`),
returns `active`, `ready` (objectives done, not handed in) or `done`; a quest
not taken yet is `E_NOT_FOUND` (`null` in TypeScript). `kv_set` on a `quest:`
key returns `E_BAD_ARG`. There is no quest event: check the key in `on_tick`
(or a `timer_repeat` of about a second) and react when it changes. For simple
effects (a light, a sound, an object that appears or goes) use the quest's
`on_complete` instead.

```ts
const st = iamar.kv_get("quest:mend_nets");             // Uint8Array or null
if (st !== null && String.fromCharCode(...st) === "done") { /* the boat sails */ }
```

## 4. Callbacks (exports)

All are optional. The browser calls only the ones a script exports, and
checks their signatures at load time (a mismatch refuses the script).

<!-- world_api:callbacks -->
| export | signature | since | when |
|---|---|---|---|
| `on_init()` | ` > ` | 0.1 | Once, after instantiation. |
| `on_tick(dt)` | `f > ` | 0.1 | About 10 times a second (tick_hz); dt is seconds since the last tick (<= 0.5). |
| `on_enter(player)` | `i > ` | 0.1 | A player arrives (after on_init for everyone already there). The local player is id 1. |
| `on_leave(player)` | `i > ` | 0.1 | A player leaves. |
| `on_interact(player, entity)` | `i i > ` | 0.1 | A player uses an entity (the interact key within 2.5 m). |
| `on_timer(tag)` | `i > ` | 0.2 | A timer_after / timer_repeat fired. |
| `on_message(data_ptr, data_len)` | `i i > ` | 0.1 | Bytes from another copy of the script (used when on_message_from is not exported). |
| `on_message_from(player, data_ptr, data_len)` | `i i i > ` | 0.3 | Bytes from the copy of the script running for this player. |
| `on_trigger_enter(player, entity)` | `i i > ` | 0.3 | A player walked into a trigger zone. |
| `on_trigger_exit(player, entity)` | `i i > ` | 0.3 | A player left a trigger zone. |
| `on_contact(a, b)` | `i i > ` | 0.3 | Two of the script's dynamic entities, or a dynamic entity and the world (b = 0), started touching. |
| `on_click(player, entity)` | `i i > ` | 0.3 | The local player clicked an entity with the mouse (needs a collider). |
| `on_input(key, pressed)` | `i i > ` | 0.3 | A key asked for with input_bind went down (1) or up (0). |
| `on_ui(id)` | `i > ` | 0.3 | A ui_button was clicked. |
| `on_ui_event(page, node, kind)` | `i i i > ` | 0.4 | Something happened on a page node: kind 1 click, 2 change (input, textarea, checkbox, slider, select; typing is coalesced to one per node per frame), 3 submit (Enter in an input), 4 link, 5 closed (the player closed a modal page). Shares the per-frame allowance with timers and messages. |
| `iamar_alloc(len)` | `i > i` | 0.1 | Required with on_message / on_message_from: returns a buffer of len bytes the host fills; the script owns it afterwards. |
<!-- /world_api -->

Order within a frame: due timers, then queued messages, then engine events
(`on_contact`, `on_click`, `on_input`, `on_ui`, trigger enter/exit, in the
order they happened), then `on_tick`; timers, messages and events share the
per-frame allowance (`frame_ms`, `frame_callbacks`) and what does not fit waits
a frame. No callback ever runs inside a host call. A
WebAssembly start function, if any, runs during instantiation on the init
budget and may use every import. `interact(player, entity)` from the network
is ignored unless that player is present and within reach of the entity.

## 5. Budgets and failure

Every call into a script runs under three limits enforced by the runtime:

* **Fuel** — WebAssembly instructions. Out of fuel traps the call.
* **A wall-clock deadline** — a backstop, since fuel counts instructions and not
  time.
* **Memory** — linear memory is capped; `memory.grow` past the cap returns −1
  (the TypeScript engine then throws, which traps). A module whose *initial* memory is
  over the cap does not instantiate.

Each host call also costs 1000 fuel, and a callback may make at most 20 000 host
calls, so a loop of cheap-looking imports is bounded too. Stack overflow,
out-of-bounds memory access, `unreachable`, integer divide by zero and bad
pointers passed to the host all trap.

| limit | default | a manifest may raise it to |
|---|---|---|
| memory | 16 MiB | 64 MiB |
| fuel: instantiation + `on_init` | 20 000 000 | 200 000 000 |
| fuel: each event callback | 2 000 000 | 20 000 000 |
| fuel: each `on_tick` | 1 000 000 | 5 000 000 |
| deadline: init / event / tick | 100 / 20 / 10 ms | 500 / 50 / 20 ms |
| `on_tick` rate | 10 Hz | 30 Hz |
| entities | 256 (spawns: 256/s) | 1024 |
| timer + message callbacks per frame | 32, and 8 ms of script time; the rest wait a frame | |
| distinct glTF assets / size of one | 64 / 32 MiB | |
| lights / particle emitters | 16 / 8, each counted per script: only the ones this script spawned (no shadows; ≤ 200 particles/s each); `entity_spawn` returns `E_LIMIT` (-3) past the cap | |
| dynamic bodies | 128 | |
| custom meshes | 64, ≤ 4 096 vertices and 12 288 indices each, 1 000 000 vertices and 3 000 000 indices in all | |
| world UI elements / text | 32 / 256 bytes (labels in the world: 128) | |
| bound keys | 32 (A–Z, 0–9, Space, arrows only) | |
| package sounds (`asset:*.ogg`) | 32 files, ≤ 2 MiB each | |
| messages (`world_message` + `message_to`) | 1 KiB each, 20/s together | |
| engine events (contacts, clicks, keys, buttons, triggers) | share the per-frame allowance above; ≤ 256 queued | |
| script file | 8 MiB | |
| bright/dark flashes (photosensitivity, WCAG 2.3.1) | 3 a second per thing (1 a second when the visitor turns on *Reduce flashing*); see [Flash budget](#flash-budget) | |

A world declares its needs in `manifest.json` (read by the package loader):
`"budgets": {"max_memory": 33554432, "tick_fuel": 2000000}`. A manifest may
lower any limit and raise only those with a maximum above; values are clamped
to [minimum, maximum], and non-numbers and unknown keys are ignored.

Fuel and deadlines bound the script's own code. Work the *host* does for it
(spawning, loading a glTF, playing a sound) is bounded by the quotas instead:
host calls per callback, spawns per second, entities, assets, and the per-frame
allowance. Assets from a downloaded package must be self-contained `.glb` files
(no external buffer or image URIs); `.gltf` is accepted only for assets built
into the browser.

**A trap never reaches the browser.** The call is abandoned, the error (with the
WebAssembly backtrace) is recorded in `WorldScript.errors` and printed to the
log, and the world carries on. A trap in `on_init`, or a third trap in any
callback, stops the script: no more callbacks, and its entities stand still. The
scripts in `examples/scripts/hostile_*` and the WAT cases in
`tools/sandbox_test.gd` exercise each of these.

Measured on the build host (Intel i9-11900KF, Linux, Godot 4.7.2; Windows build under Wine is 1.5–2× slower per call):

| | cost |
|---|---|
| empty callback, runtime only | 0.7 µs |
| empty callback through `WorldScript` | 2.5 µs |
| one host call (e.g. `rand`) through `WorldScript` | ~0.5 µs |
| 1 000 000 fuel of a tight loop | ~0.5 ms (about 10× less for straight arithmetic) |
| script chickens `on_tick` (6 hens, 1 player) | 60–180 µs, ~14 000–32 000 fuel |
| loading the 20 KB chickens module (compile + instantiate + spawn) | 30–370 ms, the first load in a session being the slow one |

So the default tick budget (1 M fuel) is about half a millisecond of worst-case
work per tick, and a runaway script costs at most 3 × that before it is stopped.

### Flash budget

A script may not strobe what the visitor sees. Every change that can make
something on screen much brighter or darker counts against a per-thing budget:
at most **3 large bright/dark changes in any second** (a step of at least 0.1
in relative luminance, with the darker side under 0.8, as in WCAG 2.3.1).
Visitors who turn on **Reduce flashing** in the Esc menu get **1 a second**,
and a smaller step (0.05) already counts. A manifest cannot raise this.

- **Held, never dropped:** `entity_set_light`, `entity_set_color`,
  `entity_set_material` (emission), `entity_set_tint`, `entity_set_visible`,
  `ui_color` and `ui_page_patch` still return success past the budget; the
  change waits and is applied as soon as the second has room, in call order,
  so the world always ends up as the script last asked. A held change back to
  what is already on screen applies at once (an on/off/on burst shows nothing).
  Bright entities appearing and disappearing (`entity_spawn`, `entity_remove`)
  share one budget, so spawn/remove strobes are held the same way.
- **Refused:** `ui_page_set`, `ui_page_show` and `ui_page_remove` return
  `E_LIMIT` (-3) with the error `flashing too fast` when the change would be a
  flash past the budget; nothing changes, and the script may try again later.

Small changes (dimming a lamp a little, colour shifts of similar brightness)
never count. To animate light, change it smoothly over several ticks rather
than switching between bright and dark.

## 6. Versioning

`api_version` is `major.minor`. Within a major version the API only grows: new
functions and new optional callbacks raise the minor version; existing
signatures and meanings never change. A browser runs a script built for
`0.x` when `x` ≤ its own minor version; the world package's manifest carries
the version the script was built against. Import names are unversioned; an
incompatible change would be `1.0`, with the 0.x names kept alongside.

## 7. Embedding (for browser code)

```gdscript
var ws := WorldScript.new()
ws.world_id = "oakhaven"
ws.asset_root = "res://worlds/oakhaven/assets"            # where "asset:..." resolves
ws.ground = func(x, z): return terrain.height_at(x, z)
ws.note = func(t): hud.show_note(t)
ws.sound = func(name, pos): return play(name, pos)        # true if the name exists
world_root.add_child(ws)
if ws.load_file("res://worlds/oakhaven/scripts/main.wasm", manifest.get("budgets", {}), manifest.api_version):
    ws.add_player(1, local_player)
    ws.start()
# networking (ScriptNetBridge does this for package worlds):
ws.add_player(2, remote_avatar, {"name": n, "key": peer_id, "local": false}); ws.remove_player(2)
ws.message_sent.connect(func(bytes): for p in peers: net.send_data(p, frame(bytes)))
ws.message_to_sent.connect(func(key, bytes): net.send_data(key, frame(bytes)))
net.data_received.connect(func(peer, ch, bytes): ws.deliver_message_from(peer, unframe(bytes)))
ws.interact(peer_id, handle)                              # a remote player's interaction
```

Package worlds: `WorldSwitcher._commit_package` runs the manifest's scripts for
every visitor through `PackageScriptHost.attach` (kv in
`user://world_kv/<world>/<script>.json`), unless the visitor turned scripts off
(`Settings` `sandbox/scripts = false`); they stop when the world is left.

`WorldScript.available()` is false when the runtime library is missing (for
example on a platform without a build); the world then runs without scripts.

The runtime binaries are in `addons/wasm/bin/` for Linux x86_64 and Windows
x86_64, built on the build host by `addons/wasm/build.sh [linux|windows]`; macOS
(universal) is built by `.github/workflows/iamar-wasm.yml`. Licences:
`addons/wasm/THIRD_PARTY.md`.
