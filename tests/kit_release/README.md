# Split release harness

`run.sh` is a heavy native integration test, not an inert source check. It requires
an overlaid browser workspace containing this kit's tests and `kit/` folder,
Linux export templates, Godot, rsync, and the matching built kit pack supplied
through `IAMAR_KIT_PACK`. The existing `tools/run_tests.sh` supplies that pack and
keeps the suite behind `KIT_TESTS_HEAVY=1`; direct invocations now require the same
explicit opt-in. The harness does not build or silently substitute a pack.

The harness copies the browser workspace into private scratch, omitting the kit
folder, tests, build directory and packs. Before copying and pruning, it rejects symlinked directory ancestors, script/cache
roots, and allowlisted script files. It safely removes all nonallowlisted kit
entries, including nested directories and symlinks, without following their
targets. It retains only
`kit_loop`, `world_scaffold` and `world_techniques`, plus their UID files when present.
Only imported asset payloads survive from `.godot`; editor, class, UID and export
caches must be regenerated against the stripped source. The original workspace
is not modified. Installed export templates are copied read-only from the caller's
existing template tree into private scratch; symlinked template roots, ancestors
or entries are rejected. Export uses scratch-owned HOME and XDG data/config/cache
locations. Native export still needs the browser's normal prerequisites.

Before installing the kit, the exported browser must refuse `validate` with exit
status 3 and the specific missing-kit diagnostic. A success, timeout, crash or
unrelated status-3 failure is a failure. This check prevents a browser that still
embeds the tool from passing the subsequent pack tests.

The input pack is then copied byte-for-byte to `<browser>/kit/iamar-kit.pck`, with
the guide and launcher. Commands run with a clean environment and isolated HOME;
even the three-parent macOS fallback directory resolves inside private scratch.
`where` must identify this installed kit, pack and executable. The wrapper must
discover its adjacent browser without caller overrides. The exact installed file
list includes entry types and the sole allowed directory, rejecting extra files,
directories, symlinks, FIFOs and other special entries. Preview requires exit 0
and a VIEW 0 line with positive draw, primitive and object counts. A timeout or
failure after such a line fails; empty or zero-geometry logs fail. Missing offscreen
support is explicitly reported as a preview skip.

## Inert checks

`python3 tests/kit_release/test_setup_inert.py` evaluates only selected setup and
assertion shell blocks against text fixtures. It checks the opt-in gate, stripping
and cache cleanup, nested/symlink removal, ancestor-escape rejection without
outside mutation, exact pack copying, location isolation, and refusal assertion
acceptance/rejection cases. Further stand-ins exercise typed exact-layout checks,
preview success/failure/timeout evidence, and private template copying with
source-link rejection and unchanged external sentinels. It also reads the harness
to check the export path and
clean-environment routing. It never invokes Godot, builds a pack, exports a
browser, executes a browser/kit command, or performs a render.

These fixtures cannot prove that the exported browser actually refuses without a
kit, loads the installed pack, or renders. Only a separately authorized native run
can establish that. They also do not execute the rsync copy or check pack/browser
version compatibility. The caller is responsible for supplying the matching pack.

## Verification of this repair

Prepared against `iamar-ai/iamar-kit` commit
`b2707865ee0dd16dda9d1e327a39714664513b9d`.
Shell syntax (`bash -n`) and Python AST parsing were checked. On 2026-10-18 UTC,
all 10 inert setup unittest methods passed under isolated process supervision.
Godot export, native commands, real rsync staging and render checks were **not run**.
