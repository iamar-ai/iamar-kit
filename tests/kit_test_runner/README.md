# Runner classification fixtures

Run from the kit repository root:

    python3 tests/kit_test_runner/test_inert.py

These tests exercise the actual `tools/run_tests.sh` summary and aggregate exit status
inside disposable directories. Smoke and rsync are inert replacements; a fake timeout
returns deterministic suite output/status without running its command arguments. A
closed PATH contains only those replacements and required filesystem/text utilities.
No engine, browser, pack builder, network request, or real suite is executed. The
missing-timeout fixture omits the replacement entirely and checks the real shell error.
Signal statuses are simulated (137/139/143); the tests do not kill processes.

The six historical suites are tested both with historical-looking output and a novel
failure. Both must FAIL until exact baselines have been reviewed and checked in. A
historical fragment plus a new error must also FAIL. This is intentional: the original
prose notes do not contain enough evidence to distinguish known from new regressions.
No real historical assertion log is claimed by these synthetic fixtures.

Success, timeout, infrastructure failure, missing tools, Blender's existing skip, and
smoke aggregate failure are also covered. This standalone test is not automatically
registered as a workspace suite: the runner currently overlays selected kit tools,
not `tools/run_tests.sh`, into that workspace. Run it directly in the kit checkout.

If XFAIL is reintroduced, require reviewed baseline provenance, exact expected exit
status and complete failure evidence, with deliberately narrow normalization. Reject
unknown output and additional failures; never use suite-name or substring matching
alone. Timeout, signal and tool/infrastructure failures must stay fatal. New fixtures
must prove that only the exact baseline is exempt, and that any extra failure fails.

The inert timeout child also records both explicit source roots, its working directory,
and an inherited environment sentinel. Assertions require `IAMAR_TEST_SOURCE_ROOT`
and `IAMAR_BROWSER_SOURCE_ROOT` to equal the exact absolute workspace, overriding
poisoned host-checkout values. Cases cover overlay and `--no-overlay`, absolute and
relative workspace arguments with spaces, and `--pack-mode` source skips versus command
suites. These assertions inspect child environment only; no source suite runs.

The tier-preflight command must carry the quoted `--dependency-root` argument bound
to that explicit browser root. This requires the matching tier-closure runner patch.
Injected workspace creation/resolution, browser-copy, overlay-copy and tool-copy
failures must stop before any suite child starts. No fake timeout executes the
captured command arguments, including tier preflight or native dependencies.

`IAMAR_PROJECT` is bound to the same absolute workspace for selected-suite runtime
project discovery. The poisoned inherited project value must also be overridden.
The explicit browser argument still supplies the browser files used to construct
that workspace; source and runtime selection cannot escape to a host checkout.
Existing per-suite HOME/XDG/cache/settings isolation and other inherited variables
are unchanged. Heavy/GPU/pack-mode gates are retained; no new execution is authorized.
