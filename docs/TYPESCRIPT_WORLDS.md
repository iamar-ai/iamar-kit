# Writing IAMAR worlds in TypeScript

A world script can be one standard TypeScript file. The official TypeScript
compiler (5.9.3) checks it and emits ES2020 JavaScript; the build embeds that
JavaScript in a QuickJS interpreter compiled to a WebAssembly module whose only
imports are the `iamar` world API functions. The browser runs that `.wasm`
exactly like a script written in C or Rust. The whole of world API **0.3**
(`api/world_api.json`: 54 imports, 15 callbacks) is available as `iamar.<name>`.

This supersedes `docs/TYPESCRIPT_WORLD_AGENT_V1.md` (the 0.1 candidate, kept
for its evidence history). The [packer integration evidence](the iamar browser source (not public))
records Linux Godot sandbox loading and `on_init` for the packed showcase.
The broader API/conformance tests run the real compiled guest on V8 with a
modeled host. These are separate, limited results: Windows/macOS execution,
full released-browser qualification and creator/visitor flows remain unproven
by that evidence.

## 1. Set up once

The default is the pure-Node packer with a prebuilt QuickJS guest. Provide
**Node.js 20 or newer** on `PATH` (or set `IAMAR_TS_NODE` to its approved
executable path). The packer also requires the official **TypeScript 5.9.3**
compiler and its accompanying declaration files.

In a downloaded kit, read `kit/ts-world/TYPESCRIPT.md` first: it records whether
the compiler is included. An explicitly assembled kit may already contain the
pinned compiler and its libraries; in that case, skip the separate compiler
installation below. The default kit and a source checkout need a separately
provided compiler.

Ask before installing missing tools. If the compiler is missing, with approval
run this from the repository or complete browser-bundle root:

```sh
npm i typescript@5.9.3 --prefix kit/ts-world
```

Alternatively, set `IAMAR_TS_COMPILER` to the absolute path of an existing
`typescript/lib/typescript.js`, keeping its accompanying `lib.*.d.ts` files.
In a source checkout, also set that absolute `IAMAR_TS_COMPILER` path after
the `kit/ts-world` install above: when `kit/ts-world/pack.mjs` is absent, both
wrappers search beside the source-tree packer under `tools/typescript-world/`.
For Linux/macOS, from the repository root:

```sh
export IAMAR_TS_COMPILER="$PWD/kit/ts-world/node_modules/typescript/lib/typescript.js"
```

On Windows, set the same variable to that compiler file's absolute Windows path.
The compiler version is checked at pack time. No C compiler, QuickJS sources
or WASI SDK are needed for this route, and packing downloads nothing.

Use `kit/iamar-world` on Linux/macOS or `kit\iamar-world.cmd` on Windows.
The current `tools/kit_bundle.sh` includes the packer, guest, SDK, spec and
notices in `kit/ts-world/`, with compiler setup in `kit/ts-world/TYPESCRIPT.md`;
Node remains external, while TypeScript inclusion depends on the kit's recorded
assembly mode. The wrappers also support a source checkout. Check an actual
download for these files rather than assuming an older browser bundle includes
them. `compile-typescript` is a wrapper command,
not a direct browser `--kit` command.

For maintainers rebuilding the guest, `compile-typescript --from-source`
retains the **Linux x86_64 source-checkout** route. Follow
[`README_TOOLCHAIN.md`](../tools/typescript-world/README_TOOLCHAIN.md) only for
that route: its setup script requires Node 22+, downloads the pinned toolchain
after approval, and prints five `IAMAR_TS_*` exports to set as absolute paths
in the build shell. It does not generate an `env.sh` to source.

## 2. Write `world.ts`

A world is a global script: no `import`/`export`, no `async`/`await`. The SDK
declarations (`api/typescript/iamar-world.d.ts`) are supplied by the build; you
get completion and type errors for every call. Define `on_init` and any other
callback as a top-level function:

```ts
let lamp = 0;
function on_init(): void {
  lamp = iamar.entity_spawn("light", 0, iamar.ground_y(0, 0) + 3, 0, 0);
  iamar.entity_set_light(lamp, 4, 12, 0);
  iamar.timer_repeat(1000, 1);
}
function on_timer(tag: number): void {
  iamar.entity_set_color(lamp, Math.random(), 0.8, 0.5, 1); // Math.random = iamar.rand
}
```

Examples: `examples/typescript-showcase/world.ts` (every API group) and
`examples/typescript-driving/world.ts` (a small steering mechanic).

## 3. Build and package

### Command-line route

```sh
kit/iamar-world compile-typescript path/to/world.ts path/to/template /fresh/out
```

On Windows use `kit\iamar-world.cmd compile-typescript` with the same three
arguments and Windows paths. On Linux x86_64, add `--from-source` immediately
after `compile-typescript` only when the source toolchain above is configured.
The output directory must not already exist, including for a rebuild.

The template folder holds `manifest.json` (with `"api_version": "0.3"` and
`"scripts": [{"path": "scripts/world.wasm"}]`) and `scene.json`; copy
`examples/typescript-showcase/package`. The output folder gets:

* `world/` — the package: `manifest.json`, `scene.json`, `scripts/world.wasm`,
  `THIRD_PARTY_NOTICES.txt` (keep it in the package), plus saved template assets
  and metadata, including non-generated files under `scripts/`.
* `source/` — your `world.ts`, the SDK, the emitted `world.js` and source map.
* `BUILD.json` — hashes of every input and output, compiler options, the spec
  version and the ABI audit.

Then use the normal kit flow on `world/`: `kit/iamar-world validate`, `preview`,
`package`. Both command-line build routes capture and copy ordinary local template
files within the browser's folder limits: 4,096 entries (directories included),
256 MiB per file, 512 MiB total, 12 path components and 200-character safe ASCII
package paths. The assembled output also stays within the package byte/entry
limits. Hidden contents are ignored, but enumerated hidden names count toward the entry
limit; links, nonregular files, ambiguous
case-colliding paths and paths conflicting with generated output are refused.
Choose a fresh output outside the template. Windows containment also resolves
existing ancestors to catch short-name (8.3) aliases; fresh missing output
components remain supported. Keep both folders under your
exclusive control during the build. These checks are not an atomic defense
against a concurrent hostile filesystem writer.

The generated manifest, scene and `scripts/world.wasm` replace those template
entries; the old `signature.json` is omitted. Guest notices remain, and distinct
template notices are retained under a collision-free
`TEMPLATE_THIRD_PARTY_NOTICES[-N].txt` name. `BUILD.json` inventories copied files
as well as compiler output. You can still add or edit assets manually in the
output `world/` before validation; revalidate after such edits, and remember the
build receipt describes the saved build snapshot, not later changes.

The packer fills
a missing script selection, reconciles `api_version` and raises `budgets.script_bytes` when
needed; it refuses a conflicting script selection. The source-build route
copies the manifest unchanged. Review all features and budgets yourself.
A successful build does not execute, sign or host the world.

The build refuses a source that does not type-check, a callback with
the wrong signature, a module whose imports are not exactly `iamar` functions
with the spec's signatures, and stale generated bindings.

### Desktop Build and validate (source-added)

The **Builders' Guild → Open local folder tools** panel has a source-added
Build/Validate path using the same Node packer. Native UI, real compiler/process
cancellation and exported-platform verification remain unrun for this path;
this is not a released-build or runtime acceptance claim. See the
[source/model checks and remaining gates](../tests/local_creator_build/README.md).

1. Use **Choose world folder** to select the saved template containing
   `manifest.json`, `scene.json` and its referenced assets, or use **Choose parent
   folder → Create starter folder** after filling in the new folder's details.
   Save any edits before building; the panel is not a source or scene editor.
2. Choose **Choose TypeScript source (.ts)** and one global `.ts` script
   (not `.d.ts`, at most 256 KiB). Use **Choose build output parent** to select
   an existing local folder outside the template. Use ordinary local paths
   without symlinks or network shares.
3. Choose **Build and validate**. Each attempt snapshots the saved source and
   template, writes source/manifest/scene inputs under a fresh
   `iamar-build-<random>/input/` and invokes the existing packer into its
   previously absent `output/` directory. It then copies saved template assets
   and metadata into `output/world/`, including other files under `scripts/`.
   The generated manifest, scene and `scripts/world.wasm` replace those template
   entries; the old package signature is omitted. Guest notices remain; distinct
   template notices get a collision-free `TEMPLATE_THIRD_PARTY_NOTICES[-N].txt` name.
4. Only after the assembled world passes the existing validator does the panel
   select `iamar-build-<random>/output/world/` and report its validated identity.
   The original editable template remains the input for retries. A failed or
   canceled attempt preserves the previous selection and previous output;
   **Cancel pending file action** or **Close** prevents a pending result from
   replacing it. Cancellation waits for any running compiler to exit and file
   resources to close. Partial files are retained at the reported path.

The [Node 20+ and official TypeScript 5.9.3 prerequisites](#1-set-up-once)
must already be available to the desktop app; nothing is installed or downloaded.
Desktop discovery selects the complete `kit/ts-world/` beside the executable
(beside the `.app` on macOS), falling back to the source checkout only when that
kit directory is absent. `IAMAR_TS_NODE` and `IAMAR_TS_COMPILER` overrides are
authoritative; invalid or empty values fail rather than falling back. Keep the
input, output and tool folders under your exclusive control and unchanged during
the build; path checks do not protect against a concurrent hostile writer.

`BUILD.json` is the packer's compiler-output receipt, not an inventory of the
desktop-added assets. Revalidate after edits and use the existing preview/gameplay
checks. Build does not run world scripts, sign, import or host. Signing/packaging
and the signed-pair import → audience choice → **Start Hosting** flow remain
the [existing creator-kit steps](../kit/AGENT_KIT.md#local-browser-folder-handoff).

## 4. The `iamar` API

Every method validates its arguments before calling the host and throws on a
malformed one (`TypeError`, or `RangeError` for sizes): numbers must be finite
f32, handles and player ids positive integers, other integers i32, flags
booleans. Host failures come back as negative status codes: `-1` bad handle,
`-2` bad argument, `-3` limit, `-4` not found. Methods with out-params return a
copied value or `null` when the call fails.

| Group | Methods |
|---|---|
| core | `api_version()` (3 for 0.3), `log(text)`, `rand()`, `time()` |
| ui | `ui_note(text)`, `ui_text(id, text, x, y, size)`, `ui_button(id, text, x, y, w, h)`, `ui_bar(id, value, x, y, w)`, `ui_color(id, r, g, b, a)`, `ui_remove(id)` |
| entity | `entity_spawn(kind, x, y, z, yaw)`, `entity_remove`, `entity_set_pos`, `entity_move_to`, `entity_pos(h)` → `[x,y,z,yaw]`, `entity_play_anim`, `entity_stop_anim`, `entity_set_tint`, `entity_set_grounded(h, bool)`, `entity_set_scale`, `entity_set_visible(h, bool)`, `entity_set_rot` |
| render | `entity_set_color`, `entity_set_material`, `entity_set_light`, `entity_set_particles(h, preset, rate)`, `entity_set_text(h, text, size)`, `mesh_create(vertices, indices)` |
| world / physics | `ground_y(x, z)`, `raycast(x1,y1,z1,x2,y2,z2)` → `{hit,x,y,z,nx,ny,nz}` or `null`, `entity_set_collider`, `entity_set_physics`, `entity_apply_impulse`, `entity_set_velocity`, `entity_velocity(h)` → `[x,y,z]`, `entity_set_trigger(h, radius)` |
| audio | `sound_play(name, x, y, z)` |
| time | `timer_after(ms, tag)`, `timer_repeat(ms, tag)`, `timer_cancel(tag)` |
| players | `players_count()`, `player_id(index)`, `player_pos(id)` → `[x,y,z,yaw]`, `player_set_pos`, `player_is_local(id)`, `player_name(id)` → string, `player_key(id)` → string |
| storage | `kv_get(key)` → `Uint8Array` or `null`, `kv_set(key, bytes)` |
| network | `world_message(bytes)`, `message_to(id, bytes)`, `is_authority()` |
| camera / input | `camera_set(mode, x, y, z, tx, ty, tz)`, `input_bind(key, bool)` |

The SDK file carries the spec's description of every method. One example per
group:

```ts
iamar.log(`api ${iamar.api_version()} at t=${iamar.time()}`);                  // core
iamar.ui_text(1, "Score: 0", 0.5, 0.05, 24);                                    // ui
const box = iamar.entity_spawn("box", 0, 1, -3, 0);                             // entity
iamar.entity_set_material(box, 0.8, 0.2, 0, 0);                                 // render
const hit = iamar.raycast(0, 10, 0, 0, -10, 0); if (hit) iamar.log(`${hit.y}`); // world
iamar.entity_set_collider(box, 1, 1, 1, 1); iamar.entity_set_physics(box, 1, 5); // physics
iamar.sound_play("bell", 0, 1, -3);                                             // audio
iamar.timer_after(2000, 7);                                                     // time
const who = iamar.player_name(1) ?? "visitor";                                  // players
iamar.kv_set("visits", new Uint8Array([1]));                                    // storage
if (iamar.is_authority() === 1) iamar.world_message("round:start");             // network
iamar.camera_set(1, 0, 12, 12, 0, 0, 0); iamar.input_bind(82, true);            // camera/input
```

Types worth knowing:

* `bytes` parameters take a `Uint8Array`, an `ArrayBuffer` or a string (sent as
  UTF-8); at most 4096 bytes (the host's own limits are lower: 1 KiB messages,
  4 KiB values).
* Strings are at most 512 UTF-8 bytes in the adapter; the host applies the
  spec's tighter limits (256 for `ui_text`, 128 for labels and keys).
* `mesh_create(vertices, indices)`: `vertices` is a `Float32Array` or
  `number[]` with 8 numbers per vertex (x, y, z, nx, ny, nz, u, v); `indices` a
  `Uint32Array` or `number[]` of whole triangles, each index below the vertex
  count. Typed arrays are passed to the host without copying. It returns a mesh
  id; spawn it as `` `mesh:${id}` ``.
* Entity kinds, particle presets and sound names are string-literal types, so a
  typo is a compile error.

## 5. Callbacks

Define any of these as top-level functions; `on_init` is required. The build
checks names, parameter counts and types, and that each returns `void`.

| Callback | Parameters |
|---|---|
| `on_init()` | once, after loading |
| `on_tick(dt: number)` | about `tick_hz` times a second |
| `on_enter(player)`, `on_leave(player)` | players arriving / leaving |
| `on_interact(player, entity)` | the interact key within 2.5 m |
| `on_timer(tag)` | a timer fired |
| `on_message(data: Uint8Array)` | bytes from another copy of the script |
| `on_message_from(player, data: Uint8Array)` | the same, with the sender |
| `on_trigger_enter(player, entity)`, `on_trigger_exit(player, entity)` | trigger zones |
| `on_contact(a, b)` | dynamic entities touching (`b = 0` is the world) |
| `on_click(player, entity)` | the local player clicked an entity |
| `on_input(key: number, pressed: boolean)` | a key bound with `input_bind` |
| `on_ui(id)` | a `ui_button` was clicked |

The guest exports every callback (plus `iamar_alloc`) and calls only the ones
you define, so an undefined callback costs one empty call. If you define only
`on_message`, messages delivered through `on_message_from` still reach it.

## 6. The profile's rules and limits

* Synchronous only: a callback that leaves a pending Promise job, throws, or
  returns a value stops the instance (it traps and must be reloaded).
* `Date`, `eval` and `WeakRef` are absent; there are no timers other than
  `iamar.timer_*`, no `TextEncoder`, no Node or browser APIs.
  `Math.random()` returns `iamar.rand()`, seeded per world, so every visitor's
  copy draws the same sequence.
* The QuickJS heap is capped at 8 MiB inside 16 MiB of Wasm memory; the source
  at 256 KiB. The prebuilt guest is about 2 MiB, including a 1 MiB slot for
  emitted JavaScript; the source-built guest is about 1 MB (limit 8 MiB). Declare
  `max_memory: 16777216` in the manifest budgets.
* Interpreting JavaScript costs more fuel than compiled C or Rust. The example
  manifests keep the API defaults (20M init / 2M event / 1M tick fuel); measure
  your world with `kit/iamar-world perf` before raising callback work, and keep
  `max_host_calls` above the calls one callback makes (the showcase's `on_init`
  makes about 45).

## 7. How it stays in step with the API

`api/world_api.json` is the single source of truth.
`tools/typescript-world/gen_bindings.mjs` writes from it the guest's import
declarations, the JavaScript method table with all argument marshalling and
every callback export (`guest/api_generated.h`), the ABI tables used by the
compiler and the Wasm audit (`api_generated.mjs`), and the SDK
(`api/typescript/iamar-world.d.ts`). After a spec change run
`node tools/typescript-world/gen_bindings.mjs`; builds and `source_audit.mjs`
refuse stale outputs (`--check` reports them). The audit
(`node tools/typescript-world/audit-wasm.mjs <wasm> api/world_api.json`) checks
that a module imports only `iamar` functions whose signatures equal the spec.

## 8. Tests

See `tests/typescript-world/README.md`. The main ones run the actual compiled
guest on V8: `api_conformance.mjs` drives every import and callback through a
modeled host that checks exact argument marshalling and error paths;
`showcase_run.mjs` plays the showcase world; `trace_parity.mjs` and
`guest_conformance.mjs` keep the 0.1 evidence.
