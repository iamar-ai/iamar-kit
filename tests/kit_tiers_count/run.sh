#!/usr/bin/env bash
# `iamar-world tiers` counts triangles and texture memory as the browser does (an internal task):
# the tier builder on a small generated world, in a throwaway project with the browser's
# tier classes. Needs a browser source checkout (the iamar browser source (not public)): IAMAR_SRC=<checkout>.
#   GODOT=/path/to/godot IAMAR_SRC=/path/to/iamar tests/kit_tiers_count/run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[[ -f "${IAMAR_SRC:-}/scripts/worlds/world_tiers.gd" ]] || {
  echo "needs a browser source checkout: set IAMAR_SRC (a checkout of the iamar browser source (not public))" >&2; exit 3; }
TMP="$(mktemp -d "${TMPDIR:-/tmp}/kit-tiers-count.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/p/scripts/worlds" "$TMP/p/scripts/kit" "$TMP/p/scripts/world" "$TMP/p/shaders"
printf 'config_version=5\n\n[application]\nconfig/name="kit_tiers_count"\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n' > "$TMP/p/project.godot"
cp "$IAMAR_SRC/scripts/worlds/world_tiers.gd" "$IAMAR_SRC/scripts/worlds/world_impostors.gd" "$TMP/p/scripts/worlds/"
cp "$ROOT/scripts/kit/world_tiers_build.gd" "$IAMAR_SRC/scripts/kit/kit_loop.gd" "$TMP/p/scripts/kit/"
cp "$IAMAR_SRC/scripts/world/package_prewarm.gd" "$TMP/p/scripts/world/"
cp "$IAMAR_SRC/shaders/world_impostor.gdshader" "$TMP/p/shaders/"
cp "$ROOT/tests/kit_tiers_count/test.gd" "$TMP/p/"
export HOME="$TMP/home" XDG_DATA_HOME="$TMP/home/.local/share" XDG_CONFIG_HOME="$TMP/home/.config" XDG_CACHE_HOME="$TMP/home/.cache"
export APPDATA="$TMP/home/appdata" LOCALAPPDATA="$TMP/home/localappdata"
mkdir -p "$HOME" "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$APPDATA" "$LOCALAPPDATA"
BAD='SCRIPT ERROR|Parse Error|Compile Error|ERROR:|ObjectDB instances leaked|Resources still in use'
set +e
timeout 120 "${GODOT:-godot}" --headless --path "$TMP/p" --editor --quit > "$TMP/import.log" 2>&1
STATUS=$?
set -e
if [[ "$STATUS" != 0 ]] || grep -Eq "$BAD" "$TMP/import.log"; then cat "$TMP/import.log"; exit 1; fi
set +e
TIER_TMP="$TMP" timeout 300 "${GODOT:-godot}" --headless --path "$TMP/p" -s test.gd > "$TMP/run.log" 2>&1
STATUS=$?
set -e
cat "$TMP/run.log"
if [[ "$STATUS" != 0 ]] || grep -Eq "$BAD|^FAIL " "$TMP/run.log"; then exit 1; fi
grep -Eq '^KIT TIERS COUNT TEST [0-9]+ passed, 0 failed' "$TMP/run.log"
