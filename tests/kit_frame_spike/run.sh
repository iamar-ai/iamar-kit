#!/usr/bin/env bash
# FrameSpike unit test: headless Godot 4.7 in a throwaway stub project (no browser, no renderer).
#   GODOT=/path/to/godot tests/kit_frame_spike/run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
W="$(mktemp -d "${TMPDIR:-/tmp}/kit-frame-spike.XXXXXX")"
trap 'rm -rf -- "$W"' EXIT
printf 'config_version=5\n[application]\nconfig/name="frame_spike_test"\n' > "$W/project.godot"
cp "$ROOT/scripts/kit/frame_spike.gd" "$ROOT/scripts/kit/world_view.gd" "$ROOT/tests/kit_frame_spike/frame_spike_test.gd" "$W/"
"${GODOT:-godot}" --headless --path "$W" -s res://frame_spike_test.gd
