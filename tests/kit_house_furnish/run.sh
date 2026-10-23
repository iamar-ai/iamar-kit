#!/usr/bin/env bash
# House furnishing (scripts/kit/kit_house_furnish.gd, an internal task), headless in a
# throwaway project: the generator needs no browser classes.
#   GODOT=/path/to/godot tests/kit_house_furnish/run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/kit-house-furnish.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/p/scripts/kit"
printf 'config_version=5\n\n[application]\nconfig/name="kit_house_furnish"\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n' > "$TMP/p/project.godot"
cp "$ROOT/scripts/kit/kit_house_rooms.gd" "$TMP/p/scripts/kit/"
cp "$ROOT/scripts/kit/kit_house_furnish.gd" "$TMP/p/scripts/kit/"
cp "$ROOT/tests/kit_house_furnish/test.gd" "$TMP/p/"
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
IAMAR_KIT_CATALOG="${IAMAR_KIT_CATALOG:-$ROOT/kit/catalog}" HOUSE_TMP="$TMP" timeout 120 "${GODOT:-godot}" --headless --audio-driver Dummy --path "$TMP/p" -s test.gd > "$TMP/run.log" 2>&1
STATUS=$?
set -e
cat "$TMP/run.log"
if [[ "$STATUS" != 0 ]] || grep -Eq "$BAD|^FAIL " "$TMP/run.log"; then exit 1; fi
grep -Eq '^KIT HOUSE FURNISH TEST [0-9]+ passed, 0 failed' "$TMP/run.log"
