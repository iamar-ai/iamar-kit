#!/usr/bin/env bash
# WorldChecks unit test: headless Godot 4.7 in a throwaway stub project (no browser, no renderer).
#   GODOT=/path/to/godot tests/kit_world_checks/run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
W="$(mktemp -d "${TMPDIR:-/tmp}/kit-world-checks.XXXXXX")"
trap 'rm -rf -- "$W"' EXIT
printf 'config_version=5\n[application]\nconfig/name="world_checks_test"\n' > "$W/project.godot"
cp "$ROOT/scripts/kit/world_checks.gd" "$ROOT/tests/kit_world_checks/world_checks_test.gd" "$W/"
out="$("${GODOT:-godot}" --headless --audio-driver Dummy --path "$W" -s res://world_checks_test.gd 2>&1)" || true
printf '%s\n' "$out"
grep -q '^WORLD_CHECKS PASS' <<<"$out"
