#!/usr/bin/env bash
# Run the kit's tests against a browser.
#   tools/run_tests.sh <browser-checkout | browser-binary> [options] [suite ...]
#     --pack FILE   use this iamar-kit.pck (default: build it with tools/build_pack.sh)
#     --pack-mode   in the source workspace delete the kit tool scripts first, so the browser
#                   must mount the pack (suites that read scripts/kit sources are then skipped)
#     --ws DIR      source workspace (default build/ws, reused between runs)
#     --no-overlay  do not merge this repository over the checkout (baseline: run the same suites on a
#                   browser checkout that still holds the kit, e.g. the tree before the split)
#     --list        print the suites and exit
#     suite ...     only these (names as printed by --list)
#   GODOT=/path/to/godot 4.7 (default godot); KIT_TESTS_HEAVY=1 also runs the suites that export a browser
#
# Two parts:
#  1. tools/smoke.sh against the browser: kit commands through its --kit dispatcher with the
#     pack, and the "kit not installed" refusal without it. Works with an exported binary.
#  2. (browser given as a checkout) the kit's own test suites. They were written for the
#     pre-split tree, so they run in a WORKSPACE: a copy of the browser checkout (working
#     tree incl. .godot import cache, no .git) with this repository's kit files merged over
#     it. Nothing in the checkout is modified. The suites are listed in SUITES below with the
#     reason for every one that is skipped.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GODOT="${GODOT:-godot}"
NOOVERLAY=0 BROWSER="" PACK="" WS="$ROOT/build/ws" PACKMODE=0 LIST=0; ONLY=()
while (( $# )); do
  case "$1" in
    --pack) PACK="$2"; shift 2;;
    --pack-mode) PACKMODE=1; shift;;
    --ws) WS="$2"; shift 2;;
    --list) LIST=1; shift;;
    --no-overlay) NOOVERLAY=1; shift;;
    -h|--help) sed -n "2,21p" "${BASH_SOURCE[0]}"; exit 0;;
    -*) echo "run_tests: unknown option $1" >&2; exit 2;;
    *) if [[ -z "$BROWSER" ]]; then BROWSER="$1"; else ONLY+=("$1"); fi; shift;;
  esac
done

# name|kind|command (run in the workspace root; @GODOT@ and @OUT@ are replaced)|needs
# kind:  src = reads scripts/kit sources or runs them with -s, cmd = only drives kit commands
# needs: -  nothing special | gpu: a renderer (offscreen/xvfb-run) | heavy: exports a browser (KIT_TESTS_HEAVY=1)
#        | blender: the test reports SKIPPED itself when Blender is missing
SUITES=(
 "kit_recipes|src|python3 kit/tests/recipes_test.py|-"
 "kit_paint_materials|src|python3 kit/tests/paint_materials_test.py|-"
 "kit_style_profile|src|python3 kit/tests/style/style_profile_test.py|-"
 "kit_style_lint|src|python3 kit/tests/lint/style_lint_test.py|-"
 "kit_lint_parts|src|python3 kit/tests/lint/parts_untagged_test.py|-"
 "kit_compare_shots|src|python3 kit/tests/lint/compare_shots_test.py|-"
 "kit_audit|src|python3 kit/tests/audit/audit_test.py|-"
 "kit_flat_wall|src|python3 kit/tests/audit/flat_wall_test.py|-"
 "kit_style_street|src|GODOT=@GODOT@ python3 kit/tests/style/street/street_test.py|-"
 "kit_shots|src|python3 kit/tests/shots/shots_test.py|-"
 "kit_catalog|src|python3 kit/tests/catalog_test.py|-"
 "kit_blender_tools|src|python3 kit/tests/blender_tools_test.py|blender"
 "kit_blender_tier|src|python3 kit/tests/blender/blender_tier_test.py|blender"
 "kit_blender_stacked|src|python3 kit/tests/blender/stacked_parts_test.py|blender"
 "kit_cli_shell|src|bash kit/tests/cli_shell_test.sh|-"
 "kit_cli_audio|src|python3 tests/kit_cli_audio/argv_test.py|-"
 "kit_cwd_argv|src|python3 tests/kit_cwd_argv/test_inert.py|-"
 "kit_direct_cwd|src|python3 tests/kit_direct_cwd/test_inert.py|-"
 "kit_new_argv|src|python3 tests/kit_new_argv/test_inert.py|-"
 "kit_view_argv|src|python3 tests/kit_view_argv/test_inert.py|-"
 "kit_cmd_injection|src|python3 tests/kit_cmd_injection/test_cmd_injection.py|-"
 "kit_agent_output|src|python3 tests/kit_agent_output/test_agent_output.py|-"
 "kit_browser_layout|src|python3 tests/kit_browser_layout/test_layout.py|-"
 "kit_package_handoff|src|python3 tests/kit_package_handoff/test_contract.py|-"
 "kit_package_output|src|python3 tests/kit_package_output/test_inert.py|-"
 "kit_script_preview|src|python3 tests/kit_script_preview/source_contract_test.py|-"
 "kit_signer_input|src|python3 tests/kit_signer_input/test_model.py|-"
 "kit_signer_io|src|python3 tests/kit_signer_io/test_model.py|-"
 "kit_signer_text|src|python3 tests/kit_signer_text/test_model.py|-"
 "kit_page_check|cmd|bash tests/kit_page_check/run.sh|-"
 "kit_playtest|cmd|bash tests/kit_playtest/run.sh|-"
 "kit_playtest_routes|src|GODOT=@GODOT@ bash tests/kit_playtest/routes.sh|-"
 "kit_play|cmd|bash tests/kit_play/run.sh|-"
 "kit_techniques|src|bash tests/kit_techniques/run.sh|-"
 "kit_perf_scripts|cmd|bash tests/kit_perf_scripts/run.sh|gpu"
 "kit_impostor_colour|cmd|python3 kit/tests/shots/impostor_colour_test.py|gpu"
 "kit_perf_draws|src|bash tests/kit_perf_draws/run.sh|-"
 "kit_frame_spike|src|GODOT=@GODOT@ bash tests/kit_frame_spike/run.sh|-"
 "kit_key_exclusion|src|python3 tests/kit_key_exclusion/test_contract.py|-"
 "kit_private_keygen|src|python3 tests/kit_private_keygen/test_source_contract.py|-"
 "kit_test_runner|src|python3 tests/kit_test_runner/test_inert.py|-"
 "kit_tiers_count|src|GODOT=@GODOT@ IAMAR_SRC=\"\$IAMAR_BROWSER_SOURCE_ROOT\" bash tests/kit_tiers_count/run.sh|-"
 "kit_verify_signature|src|python3 tests/kit_verify_signature/test_contract.py|-"
 "kit_version|src|python3 tests/kit_version/test_version.py|-"
 "kit_view_bounds|src|GODOT=@GODOT@ bash tests/kit_view_bounds/run.sh|-"
 "kit_world_checks|src|GODOT=@GODOT@ bash tests/kit_world_checks/run.sh|-"
 "kit_release|src|bash tests/kit_release/run.sh|heavy"
 "creator_tool_bundle|src|bash tests/creator_tool_bundle/run.sh|-"
 "tier_preflight|src|python3 tests/tier_preflight/run.py --godot @GODOT@ --out @OUT@/tier-preflight --dependency-root \"\$IAMAR_BROWSER_SOURCE_ROOT\"|-"
 "ts_entry_routing|src|python3 tests/typescript-world/entry_routing_test.py .|-"
 "ts_node_override|src|python3 tests/typescript-world/node_override_inert.py|-"
)
# Historical failures on the pre-split tree (2026-10-18, browser 63519bcb).
# These notes are diagnostic context only: no recorded exit/output fingerprint proves
# a current failure is identical. Fail closed until a reviewed exact baseline exists.
declare -A HISTORICAL_FAILURES=(
 [kit_cwd_argv]="fails identically before the split (guard text check at test_inert.py:132; K1 note: PackagePrewarm line in _initialize)"
 [kit_direct_cwd]="fails identically before the split (pinned sha256 of KitLoop._cwd_error helper)"
 [kit_view_argv]="fails identically before the split (pinned sha256 of the projected world_view.gd)"
 [kit_script_preview]="fails identically before the split (pinned git blob sha1 of a runtime file)"
 [kit_perf_scripts]="fails identically before the split (5 of 7 checks, with a renderer)"
 [tier_preflight]="fails identically before the split (sidecar step 'valid-tiered-world')"
)
if (( LIST )); then
  for s in "${SUITES[@]}"; do IFS='|' read -r n k c need <<<"$s"; echo "$n  [$k, needs: $need]  $c"; done; exit 0
fi
[[ -n "$BROWSER" ]] || { echo "usage: run_tests.sh <browser-checkout|browser-binary> [options] [suite ...]" >&2; exit 2; }
[[ -e "$BROWSER" ]] || { echo "run_tests: $BROWSER does not exist" >&2; exit 2; }
BROWSER="$(cd "$(dirname "$BROWSER")" && pwd)/$(basename "$BROWSER")"

if [[ -z "$PACK" ]]; then "$ROOT/tools/build_pack.sh" || exit 1; PACK="$ROOT/build/iamar-kit.pck"; fi
PACK="$(cd "$(dirname "$PACK")" && pwd)/$(basename "$PACK")"

echo "=== smoke: pack against $BROWSER"
"$ROOT/tools/smoke.sh" "$BROWSER" "$PACK"; SMOKE=$?
declare -A RES REASON
RES[smoke]=$([[ $SMOKE == 0 ]] && echo PASS || echo FAIL)

if [[ -d "$BROWSER" ]]; then
  echo "=== workspace $WS"
  mkdir -p "$WS" || { echo "run_tests: creating the workspace failed" >&2; exit 1; }
  WS="$(cd "$WS" && pwd -P)" || { echo "run_tests: resolving the workspace failed" >&2; exit 1; }
  rsync -a --delete --exclude=.git --exclude=/build "$BROWSER/" "$WS/" || { echo "run_tests: copying the browser failed" >&2; exit 1; }
  if (( ! NOOVERLAY )); then
    for d in kit scripts/kit tests docs; do
      mkdir -p "$WS/$d" && rsync -a "$ROOT/$d/" "$WS/$d/" || { echo "run_tests: overlaying $d failed" >&2; exit 1; }
    done
    for f in tools/kit_bundle.sh tools/kit_test.gd tools/creator_kit_inventory.py; do
      if [[ -f "$ROOT/$f" ]]; then
        cp -p "$ROOT/$f" "$WS/$f" || { echo "run_tests: overlaying $f failed" >&2; exit 1; }
      fi
    done
  fi
  if (( PACKMODE )); then
    for f in "$ROOT"/scripts/kit/*.gd; do rm -f "$WS/scripts/kit/$(basename "$f")" "$WS/scripts/kit/$(basename "$f").uid"; done
    echo "pack mode: kit tool scripts removed from the workspace"
  fi
  OUT="$(mktemp -d "${TMPDIR:-/tmp}/iamar-kit-tests.XXXXXX")"; trap 'rm -rf "$OUT"' EXIT
  RENDER=()
  if command -v offscreen >/dev/null; then RENDER=("$(command -v offscreen)")
  elif [[ -x "$HOME/.local/bin/offscreen" ]]; then RENDER=("$HOME/.local/bin/offscreen")
  elif command -v xvfb-run >/dev/null; then RENDER=(xvfb-run -a -s "-screen 0 1280x720x24"); fi
  export IAMAR_KIT_PACK="$PACK" PYTHONDONTWRITEBYTECODE=1 GODOT_SILENCE_ROOT_WARNING=1
  unset DISPLAY WAYLAND_DISPLAY
  for s in "${SUITES[@]}"; do
    IFS='|' read -r name kind cmd need <<<"$s"
    if (( ${#ONLY[@]} )); then [[ " ${ONLY[*]} " == *" $name "* ]] || continue; fi
    cmd="${cmd//@OUT@/$OUT}"; cmd="${cmd//@GODOT@/$GODOT}"
    if (( PACKMODE )) && [[ $kind == src ]]; then RES[$name]=SKIP; REASON[$name]="reads scripts/kit sources, removed by --pack-mode"; continue; fi
    if [[ $need == heavy && "${KIT_TESTS_HEAVY:-0}" != 1 ]]; then RES[$name]=SKIP; REASON[$name]="exports a browser (export templates, minutes): set KIT_TESTS_HEAVY=1"; continue; fi
    if [[ $need == gpu && ${#RENDER[@]} == 0 ]]; then RES[$name]=SKIP; REASON[$name]="needs a renderer: no offscreen or xvfb-run on this host"; continue; fi
    prefix=(); [[ $need == gpu ]] && prefix=("${RENDER[@]}")
    log="$OUT/$name.log"
    echo "--- $name"
    # Source-contract tests and runtime project selection use this workspace, including --no-overlay,
    # rather than an inherited host checkout or a path relative to the child cwd.
    ( cd "$WS" && export IAMAR_TEST_SOURCE_ROOT="$WS" IAMAR_BROWSER_SOURCE_ROOT="$WS" IAMAR_PROJECT="$WS" \
        && export HOME="$OUT/home-$name" XDG_DATA_HOME="$OUT/home-$name/d" IAMAR_CACHE="$OUT/cache-$name" OAK_SETTINGS="$OUT/$name.cfg" \
        && mkdir -p "$HOME" && timeout "${KIT_TEST_TIMEOUT:-900}" nice -n 19 "${prefix[@]}" bash -c "$cmd" ) > "$log" 2>&1
    rc=$?
    if (( rc == 0 )); then
      if [[ $need == blender ]] && grep -q "SKIPPED" "$log"; then RES[$name]=SKIP; REASON[$name]="Blender not installed (the test reports SKIPPED itself)"
      else RES[$name]=PASS; fi
    elif (( rc == 124 )); then RES[$name]=TIMEOUT; tail -n 5 "$log" | sed 's/^/    /'
    else
      RES[$name]=FAIL
      if [[ -n "${HISTORICAL_FAILURES[$name]:-}" ]]; then
        REASON[$name]="historical baseline only; current failure unverified: ${HISTORICAL_FAILURES[$name]}"
      fi
      tail -n 15 "$log" | sed 's/^/    /'
    fi
  done
else
  echo "(a browser binary has no source tree: the suites need a checkout, only the smoke test ran)"
fi

echo; echo "=== results"
bad=0
printf '%-22s %-8s %s\n' suite result note
for n in smoke $(for s in "${SUITES[@]}"; do echo "${s%%|*}"; done); do
  [[ -n "${RES[$n]:-}" ]] || continue
  printf '%-22s %-8s %s\n' "$n" "${RES[$n]}" "${REASON[$n]:-}"
  [[ "${RES[$n]}" == FAIL || "${RES[$n]}" == TIMEOUT ]] && bad=1
done
exit $bad
