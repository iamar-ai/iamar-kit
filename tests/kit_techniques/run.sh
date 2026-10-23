#!/usr/bin/env bash
# `iamar-world techniques`: ADVICE for the recipes the kit cannot apply by itself, on a
# world that misses them, none once fixed. Needs an imported project at ROOT (a clean
# archive with its import cache; never import the shared working tree for this).
#   GODOT=/path/to/godot tests/kit_techniques/run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
G="${GODOT:-godot}"
pass=0; fail=0
check() { if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }
for kind in unfixed fixed; do
  timeout 120 "$G" --headless --path "$ROOT" -s res://tests/kit_techniques/make_world.gd -- "$TMP/$kind" $kind > /dev/null 2>&1
done
set +e
timeout 300 "$G" --headless --path "$ROOT" -s res://scripts/kit/world_techniques_check.gd -- "$TMP/unfixed" --strict > "$TMP/u.log" 2>&1; U=$?
timeout 300 "$G" --headless --path "$ROOT" -s res://scripts/kit/world_techniques_check.gd -- "$TMP/fixed" --strict > "$TMP/f.log" 2>&1; F=$?
set -e
grep -E "^(TECHNIQUE|ADVICE|OFF|ERROR)" "$TMP/u.log" "$TMP/f.log" || true
check "every automatic recipe reported" "[ \$(grep -c '^TECHNIQUE ' $TMP/u.log) = 6 ]"
check "far big model without a card is advised" "grep -q '^ADVICE impostor: 1 big' $TMP/u.log"
check "mesh collider on a detailed model is advised" "grep -q '^ADVICE collision_proxy' $TMP/u.log"
check "three shadowed lamps are advised" "grep -q '^ADVICE live_only_moving: 3' $TMP/u.log"
check "--strict fails with advice" "[ $U = 1 ]"
check "the fixed world gets no advice" "! grep -q '^ADVICE' $TMP/f.log && grep -q 'advice=0' $TMP/f.log"
check "--strict passes once fixed" "[ $F = 0 ]"
echo "KIT TECHNIQUES TEST $pass passed, $fail failed"
[ $fail = 0 ]
