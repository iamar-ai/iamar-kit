#!/usr/bin/env bash
# ViewBounds unit test: headless Godot 4.7 in a throwaway stub project (no browser, no renderer).
#   GODOT=/path/to/godot tests/kit_view_bounds/run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
W="$(mktemp -d "${TMPDIR:-/tmp}/kit-view-bounds.XXXXXX")"
trap 'rm -rf -- "$W"' EXIT
printf 'config_version=5\n[application]\nconfig/name="view_bounds_test"\n' > "$W/project.godot"
cp "$ROOT/scripts/kit/view_bounds.gd" "$ROOT/scripts/kit/world_view.gd" "$ROOT/tests/kit_view_bounds/view_bounds_test.gd" "$W/"
out="$("${GODOT:-godot}" --headless --path "$W" -s res://view_bounds_test.gd 2>&1)" || true
printf '%s\n' "$out"
grep -q '^VIEW_BOUNDS PASS' <<<"$out"
