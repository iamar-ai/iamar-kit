#!/usr/bin/env bash
# Acceptance evidence, not a benchmark result. Requires a renderer AND a browser
# project/runtime supporting Wasm. Never launches on the real display or builds
# missing dependencies. IAMAR_PROJECT has the same meaning as in kit/iamar-world;
# with split repositories it also supplies examples/wasm from the browser tree.
# GODOT=/path/to/godot IAMAR_PROJECT=/path/to/browser tests/kit_perf_scripts/run.sh
# PERF_SCRIPTS_LOG_DIR optionally selects the parent of a fresh evidence directory.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)" || exit 1
K="$ROOT/kit/iamar-world"
FIXTURES="${IAMAR_PROJECT:-$ROOT}/examples/wasm"
if [[ -n "${PERF_SCRIPTS_LOG_DIR:-}" ]]; then
  mkdir -p "$PERF_SCRIPTS_LOG_DIR" || exit 1
  E="$(mktemp -d "$PERF_SCRIPTS_LOG_DIR/kit-perf-scripts.XXXXXX")" || exit 1
else
  E="$(mktemp -d "${TMPDIR:-/tmp}/kit-perf-scripts.XXXXXX")" || exit 1
fi
E="$(cd "$E" && pwd)" || exit 1
T="$E/work"
printf 'EVIDENCE %s\n' "$E"
# Logs and exit records survive success, failure and interruption. No log-copy
# step can hide a failed capture, and each invocation starts without stale logs.
printf 'step\texit\tlog\n' > "$E/exits.tsv" || exit 1
finish() {
  local rc=$?
  trap - EXIT
  printf 'runner\t%s\tassertions.log\n' "$rc" >> "$E/exits.tsv" || rc=1
  rm -rf "$T" || rc=1
  printf 'EVIDENCE %s (runner exit %s)\n' "$E" "$rc"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Keep full stdout/stderr separately from trusted shell exit status.
run_step() {
  local name="$1" rc; shift
  "$@" > "$E/$name.log" 2>&1
  rc=$?
  printf '%s\t%s\t%s.log\n' "$name" "$rc" "$name" >> "$E/exits.tsv" || exit 1
  return "$rc"
}
require_step() {
  local name="$1"; shift
  if run_step "$name" "$@"; then return 0; else
    echo "FAIL setup: $name (see $E/$name.log)"
    exit 1
  fi
}
RUN=()
if command -v offscreen >/dev/null; then RUN=("$(command -v offscreen)")
elif [[ -x "${HOME:-}/.local/bin/offscreen" ]]; then RUN=("$HOME/.local/bin/offscreen")
elif command -v xvfb-run >/dev/null; then RUN=(xvfb-run -a -s "-screen 0 1280x720x24")
else
  echo 'SKIP: renderer prerequisite unavailable (no offscreen or xvfb-run); no scripted performance evidence'
  exit 0
fi
# A missing runtime is NOT a renderer skip and must not count as the hostile trap.
require_step timeout_available command -v timeout
require_step python_available command -v python3
require_step launcher_available test -x "$K"
for s in script_chickens hostile_spin; do
  require_step "${s}_fixture_available" test -r "$FIXTURES/$s.wasm"
done
require_step workspace mkdir -p "$T"
# Bound scaffolding too; keep the existing 600-second perf guard.
require_step scaffold timeout 600 "$K" new "$T/base" --id perfscripts --title 'Perf Scripts' --author Tester
for s in script_chickens hostile_spin; do
  require_step "${s}_copy_world" cp -r "$T/base" "$T/$s"
  require_step "${s}_mkdir_scripts" mkdir -p "$T/$s/scripts"
  require_step "${s}_copy_wasm" cp "$FIXTURES/$s.wasm" "$T/$s/scripts/"
  require_step "${s}_manifest" python3 - "$T/$s/manifest.json" "$s" <<'PY'
import json, sys
p, s = sys.argv[1:]
with open(p) as f:
    m = json.load(f)
m['scripts'] = [{'path': f'scripts/{s}.wasm'}]
with open(p, 'w') as f:
    json.dump(m, f, indent=2)
PY
  run_step "$s" timeout 600 "${RUN[@]}" "$K" perf "$T/$s" "$T/shots_$s/s"
  rc=$?
  if [[ "$s" == script_chickens ]]; then chickens_rc=$rc; else spin_rc=$rc; fi
done
# Parse complete captured logs, using the real process statuses rather than an
# EXIT-looking line printed by a child. Diagnostics stay useful on every failure.
run_step assertions python3 - "$E" "$chickens_rc" "$spin_rc" <<'PY'
import math, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
c = (root / 'script_chickens.log').read_text(errors='replace')
h = (root / 'hostile_spin.log').read_text(errors='replace')
c_rc, h_rc = map(int, sys.argv[2:])
passed = failed = 0

def check(name, ok):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"{'PASS' if ok else 'FAIL'} {name}")

# Three-decimal SCRIPT_MS values may round to zero even when real work ran.
# Require finite nonnegative timing over positive frames, plus strictly positive
# measured on_tick microseconds/calls from the named chickens script below.
times = re.findall(r'^SCRIPT_MS mean=(\d+\.\d+) worst=(\d+\.\d+) in view (\S+) over ([1-9]\d*) frames$', c, re.M)
check('chickens: script time measured over positive frames', bool(times) and all(
    math.isfinite(float(mean)) and math.isfinite(float(worst)) and
    0 <= float(mean) <= float(worst) for mean, worst, _, _ in times))
stats = re.findall(r'^SCRIPT perfscripts/scripts/script_chickens\.wasm on_tick calls=([1-9]\d*) us_max=([1-9]\d*) us_total=([1-9]\d*)$', c, re.M)
check('chickens: positive per-export calls and timing', bool(stats) and all(
    int(total) >= int(maximum) for _, maximum, total in stats))
check('chickens: under the 2 ms target', bool(re.search(r'^TARGET world_scripts_ms\s+PASS(?:\s|$)', c, re.M)) and
      bool(times) and all(float(worst) <= 2 for _, worst, _, _ in times))
check('chickens: successful script and process', c_rc == 0 and
      bool(re.search(r'^SCRIPTS 1 running \(playerless preview\)$', c, re.M)) and
      bool(re.search(r'^TARGETS PASS$', c, re.M)) and
      not re.search(r'^TARGET \S+\s+FAIL\b|script problem:|^ERROR\b|^SCRIPT ERROR:| DISABLED$', c, re.M))
# world_script_preview checks immediately after on_tick. It may abort before any
# target report or before max_traps stops the script, so do not require that report.
# The fixture's startup marker, world ID and fuel trap jointly identify real spin
# execution; missing runtime/load failures and generic preview errors cannot pass.
spin_started = '[world perfscripts] spin: loaded, will loop forever in on_tick' in h.splitlines()
spin_trap = bool(re.search(r'^\[world perfscripts\] script problem: on_tick trapped \(fuel\): .+$', h, re.M))
check('spin: actual hostile on_tick fuel trap', spin_started and spin_trap)
preview_failure = 'ERROR: world script preview failed: A declared preview script failed, trapped or stopped.' in h.splitlines()
reported_failure = bool(re.search(r'^TARGET world_scripts_ok\s+FAIL\s+.*perfscripts/scripts/hostile_spin\.wasm(?:\s|,|$)', h, re.M)) and bool(re.search(r'^TARGETS FAIL \([1-9]\d*\)$', h, re.M))
unexpected_runtime_error = any(
    re.match(r'^(?:ERROR\b|SCRIPT ERROR:)', line) and
    line != 'ERROR: world script preview failed: A declared preview script failed, trapped or stopped.'
    for line in h.splitlines())
check('spin: trap causes perf failure', (preview_failure or reported_failure) and
      spin_started and spin_trap and not unexpected_runtime_error)
# The pinned viewer explicitly quits(1). Timeout (124), launcher errors (126/127),
# signals and other unrelated process failures must never satisfy this assertion.
check('spin: expected perf failure exit', h_rc == 1)
print(f'KIT PERF SCRIPTS TEST {passed} passed, {failed} failed')
sys.exit(0 if failed == 0 else 1)
PY
result=$?
cat "$E/assertions.log" || exit 1
exit "$result"
