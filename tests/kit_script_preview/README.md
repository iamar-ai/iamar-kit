# Kit scripted-preview source contract

The standalone kit viewer previously called the live visitor host with its
playerless Window from SceneTree._init. The live host requires a valid captured
Player and live main/root identities, so the viewer silently got an empty script
list. This correction adds only a kit-side adapter and moves script startup to
the first process callback, after tree entry and before bounds/performance
sampling. PackageScriptHost, WorldSwitcher and the sandbox/API are unchanged.

Run the inert checks from the repository root:

    PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_script_preview/source_contract_test.py -v

The checks inspect the actual viewer/helper call order and capability fences and
exercise a small attachment/cleanup model. They do not parse or execute GDScript,
load Wasm, invoke a TypeScript compiler, render, contact a service, or demonstrate
runtime correctness. Exact live-host/runtime source pins record this reviewed
baseline; reconcile their expected hashes deliberately if those files change.

## Runtime contract of the source change

- Validate-only still exits before any script setup. Data-only previews need no
  Wasm runtime. A scripted package requires every declared script to load/start;
  missing runtime/source, load failure, trap, stale custody or lost script is an
  explicit nonzero preview failure, never "no world scripts".
- Only an already accepted package's exact source, root and parent Window are
  used. The root must be in the tree. Capture/read, parent, load and start each
  retain exact package/root/source ownership; each later sample rechecks it and
  requires every retained script to remain loaded, healthy and parented there.
  Lifecycle arguments are Variant until checked, so freed Node references reach
  explicit failure handling. A separate viewer request flag distinguishes a
  never-requested preview from a root freed before its first process callback.
- The existing WorldScript.load_bytes/start path applies declared budgets/API
  and the normal import allowlist. No alternative compiler/loader is introduced.
  The normal Wasm compiled-code cache may be written when this source is later
  run with an approved runtime. KV uses an empty path and stays in memory.
- No player is registered and no Net bridge, account identity, browser note or
  audio service is supplied. The sandbox's default local is_authority() remains
  true for an isolated copy; this is no visitor or network authority. Existing
  sandbox UI/camera/input behavior and limits remain available.
- on_init is excluded from per-frame timing. The viewer camera is created after
  startup to retain its original precedence over on_init camera requests. Script
  initialization precedes automatic bounds/views, so script-owned content can be
  included. Later script camera effects remain governed by the existing sandbox.
- Partial attachment/start failure stops and frees only newly created preview
  scripts. Later stale/failure detection stops those same retained instances;
  normal completion disposes them after reporting. External window close/quit
  retains SceneTree/WorldScript's existing root-child teardown. No replacement
  root, package or unrelated scene child is freed.
- The load is synchronous, like the prior intended kit path. There is no new
  cancellation action or immediate-cancellation promise. Ownership is rechecked
  after the indivisible load returns. This does not qualify player-dependent
  callbacks, interaction, audio, networking or the full visitor journey.

## Still unrun

Target Godot 4.7 parsing, script startup, loading/refusal/trap/teardown fixtures,
rendered showcase output, scripted performance accounting and exported kits need
an authorized native run. The older Godot lifecycle implementation is supporting
context only; this change also explicitly checks tree-entry state at runtime.
No native/compiler/guest execution was performed for this source packet.
