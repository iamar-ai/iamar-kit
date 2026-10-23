#!/usr/bin/env bash
# Playtest routes (scripts/kit/world_playtest_routes.gd, an internal task), headless in a throwaway
# project: the routes need no browser classes.
#   GODOT=/path/to/godot tests/kit_playtest/routes.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/kit-playtest-routes.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/p/scripts/kit"
printf 'config_version=5\n\n[application]\nconfig/name="kit_playtest_routes"\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n' > "$TMP/p/project.godot"
cp "$ROOT/scripts/kit/kit_house_rooms.gd" "$ROOT/scripts/kit/world_playtest_routes.gd" "$TMP/p/scripts/kit/"
cp "$ROOT/tests/kit_playtest/routes_test.gd" "$TMP/p/"
export HOME="$TMP/home" XDG_DATA_HOME="$TMP/home/.local/share" XDG_CONFIG_HOME="$TMP/home/.config" XDG_CACHE_HOME="$TMP/home/.cache"
export APPDATA="$TMP/home/appdata" LOCALAPPDATA="$TMP/home/localappdata"
mkdir -p "$HOME" "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$APPDATA" "$LOCALAPPDATA"
BAD='SCRIPT ERROR|Parse Error|Compile Error|ERROR:|ObjectDB instances leaked|Resources still in use'
set +e
timeout 120 "${GODOT:-godot}" --headless --audio-driver Dummy --path "$TMP/p" --editor --quit > "$TMP/import.log" 2>&1
STATUS=$?
set -e
if [[ "$STATUS" != 0 ]] || grep -Eq "$BAD" "$TMP/import.log"; then cat "$TMP/import.log"; exit 1; fi
set +e
timeout 120 "${GODOT:-godot}" --headless --audio-driver Dummy --path "$TMP/p" -s routes_test.gd > "$TMP/run.log" 2>&1
STATUS=$?
set -e
cat "$TMP/run.log"
if [[ "$STATUS" != 0 ]] || grep -Eq "$BAD|^FAIL " "$TMP/run.log"; then exit 1; fi
grep -Eq '^KIT PLAYTEST ROUTES TEST [0-9]+ passed, 0 failed' "$TMP/run.log"
