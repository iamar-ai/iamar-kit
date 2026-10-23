# Scripted performance diagnostic regression cases

This is an acceptance-runner source change, not new performance evidence.
The historical result is 5/7, with no recorded failing assertions or logs. Nothing
here identifies those two failures or claims that the real acceptance test passes.

## Evidence contract

The runner prints `EVIDENCE <directory>` before work. Each invocation retains a
fresh `kit-perf-scripts.*` directory, optionally beneath `PERF_SCRIPTS_LOG_DIR`:

- `exits.tsv`: individual prerequisite, scaffold, copy, manifest, perf,
  classifier and final runner statuses; these come from the shell, not log text.
- `scaffold.log`, each setup-step log, `script_chickens.log`, `hostile_spin.log`:
  complete combined stdout/stderr, including failed setup steps.
- `assertions.log`: seven named assertions and the final count, when setup succeeds.

Generated worlds/screenshots are temporary. Logs remain after completion or
interruption. A capture/setup failure is a failure, not an ignored copy error.
An unwritable evidence destination fails immediately, since evidence cannot be
retained there. Interrupted runs retain the completed step records and final
runner status but may not have a completed status for the interrupted child.

The existing renderer-only skip remains (no offscreen wrapper and no xvfb-run).
It explicitly says that no scripted performance evidence was produced. Renderer
availability does not establish availability of the native WebAssembly runtime.
Scaffold, script copy, runtime loading, and process failures fail acceptance.

For split source trees, `IAMAR_PROJECT=/absolute/browser/checkout` supplies both
the launcher's browser project and `examples/wasm/{script_chickens,hostile_spin}.wasm`.
Those fixtures and native runtime artifacts belong to the browser repository;
this patch does not claim they are absent there and does not build them.
`IAMAR_BROWSER` remains the launcher's existing packaged-browser option; it does
not by itself provide the source-tree fixture directory.

## Exact source semantics

`world_view.gd` prints positive frame timing and per-export stats at the end of a
successful run. Millisecond values use three decimals and can round to zero; the
runner therefore also requires positive `on_tick` calls, `us_max`, and `us_total`
for the named chickens script, plus successful process/targets and no errors.

`world_script_preview.gd` checks script health before sampling. A fuel trap can
abort with exit 1 before either target output or the maximum-traps stopping
threshold. The runner accepts that specific failure reason, or a hostile-script
failure target, only alongside the fixture's exact startup marker and its
`[world perfscripts] ... on_tick trapped (fuel)` diagnostic. Generic preview
errors (including unavailable runtime or load failures) are insufficient.
Timeout/launcher/signal exits cannot substitute for the viewer's exit 1.

## Inert cases (33 passed, 2026-10-18 UTC)

`command_replacements.py` provides 33 cases covering successful preview-abort
and end-report forms, legitimate rounded-zero milliseconds, failed setup/copies/
manifest editing, missing or zero stats, empty/error logs, missing targets,
unrelated or wrong-world traps, generic runtime errors, spoofed EXIT text, and
successful/timeout/launcher/signal process statuses. It checks retained complete
logs and captured exit records. The synthetic repository has a fake launcher,
renderer and timeout; `.wasm` files contain inert text. No fixture is compiled,
loaded or executed. No engine, renderer or native binary is invoked.

The harness passes a minimal explicit child environment, with disposable
HOME/TMPDIR and a PATH limited to its replacements plus /usr/bin and /bin. Bash
is resolved only from those system directories. Generated Python replacements
use isolated mode. An authored environment-contract regression injects BASH_ENV,
ENV, PYTHONPATH, PYTHONHOME, PYTHONSTARTUP, loader injection variables and runtime
selectors into the parent, then verifies none reach the child allowlist. This
regression passed with the other 33 synthetic cases. The supervised execution
used a narrower replacement-only PATH with individually allowed system helpers
and Python -I -S -B shims.

Only if separately authorized to execute these inert regressions:

    python3 tests/kit_perf_scripts/diagnostics/command_replacements.py --run-inert

Initial source preparation performed Bash syntax checking, Python AST parsing
and diff inspection only. A later authorized isolated run on 2026-10-18 UTC
passed all 33 synthetic scenarios. Real performance, renderer and native
fixture execution remain unrun.
