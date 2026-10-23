#!/usr/bin/env bash
# End-to-end check of the pack against a browser: the kit commands run through the
# browser's `--kit` dispatcher with iamar-kit.pck mounted, and the same browser refuses
# politely (exit 3) without the pack.
#   tools/smoke.sh <browser-binary | browser-source-checkout> [pack.pck]
#   GODOT=/path/to/godot   used for a source checkout (default: godot)
# A source checkout must not hold the kit tool scripts itself, or the pack is never needed
# (KitLoop.ensure_tool only mounts the pack for a tool the browser lacks); the script says so.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BROWSER="${1:?usage: smoke.sh <browser-binary|browser-checkout> [pack.pck]}"
PACK="${2:-$ROOT/build/iamar-kit.pck}"
PACK="$(cd "$(dirname "$PACK")" 2>/dev/null && pwd)/$(basename "$PACK")"
[[ -f "$PACK" ]] || { echo "smoke: no pack at $PACK (run tools/build_pack.sh)" >&2; exit 2; }
if [[ -d "$BROWSER" ]]; then
  BROWSER="$(cd "$BROWSER" && pwd)"
  [[ -f "$BROWSER/project.godot" ]] || { echo "smoke: $BROWSER has no project.godot" >&2; exit 2; }
  RUN=("${GODOT:-godot}" --audio-driver Dummy --headless --path "$BROWSER" --)
  [[ -f "$BROWSER/scripts/kit/world_new.gd" ]] && echo "smoke: NOTE $BROWSER still has the kit tool scripts; the pack will not be exercised"
else
  BROWSER="$(cd "$(dirname "$BROWSER")" && pwd)/$(basename "$BROWSER")"
  RUN=("$BROWSER" --audio-driver Dummy --headless --)
fi
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export HOME="$T/home" XDG_DATA_HOME="$T/home/d" XDG_CONFIG_HOME="$T/home/c" XDG_CACHE_HOME="$T/home/k" \
  IAMAR_CACHE="$T/cache" OAK_SETTINGS="$T/s.cfg" GODOT_SILENCE_ROOT_WARNING=1
mkdir -p "$HOME" "$T/w"
unset DISPLAY WAYLAND_DISPLAY IAMAR_KIT IAMAR_KIT_PACK
pass=0; fail=0
# check <name> <expected exit> <grep pattern in output> <args...>
check() {
  local name="$1" want="$2" pat="$3"; shift 3
  local out rc
  out="$(cd "$T/w" && timeout 300 "${RUN[@]}" --kit "$@" --cwd "$T/w" 2>&1)"; rc=$?
  if [[ "$rc" == "$want" ]] && grep -Eq -- "$pat" <<<"$out"; then echo "PASS $name"; pass=$((pass+1))
  else echo "FAIL $name (exit $rc, wanted $want, pattern: $pat)"; echo "$out" | tail -n 8 | sed 's/^/    /'; fail=$((fail+1)); fi
}
echo "-- without the pack"
check "no pack: not-installed message, exit 3" 3 "developer kit is not installed" where
check "help needs no pack" 0 "iamar-world|kit" help
export IAMAR_KIT_PACK="$PACK"
echo "-- with $PACK"
check "where" 0 "^KIT " where
check "new" 0 "^NEW demo " new "$T/w/demo" --id demo --title Demo --author me
check "validate" 0 "^OK$" validate "$T/w/demo"
check "techniques" 0 "^TECHNIQUES " techniques "$T/w/demo"
check "tiers" 0 "^TIERS " tiers "$T/w/demo"
check "keygen" 0 "^KEY_ID " keygen "$T/w/k.key"
check "package" 0 "." package "$T/w/demo" "$T/w/demo.iamar" "$T/w/k.key" me
check "verify" 0 "^OK$" verify "$T/w/demo.iamar"
check "assets list" 0 "^COUNT " assets list
check "assets building (KitBuildings preload)" 0 "^BUILDING " assets building house "$T/w/house.glb"
# A relative out.glb lands where the creator ran the kit (PWD), not in the process's folder
# (an internal task). No --cwd here: the wrappers only export PWD.
mkdir -p "$T/elsewhere" "$T/creator"
rel() {
  local name="$1" file="$2"; shift 2
  local out rc
  out="$(cd "$T/elsewhere" && PWD="$T/creator" timeout 300 "${RUN[@]}" --kit "$@" 2>&1)"; rc=$?
  if [[ "$rc" == 0 && -s "$T/creator/$file" && ! -e "$T/elsewhere/$file" ]] && grep -Fq -- "creator/$file" <<<"$out"; then echo "PASS $name"; pass=$((pass+1))
  else echo "FAIL $name (exit $rc, wanted $T/creator/$file)"; echo "$out" | tail -n 8 | sed 's/^/    /'; fail=$((fail+1)); fi
}
rel "assets building: relative out under PWD" rel/house.glb assets building house rel/house.glb
rel "assets building --rooms: relative out under PWD" rel/rooms.glb assets building house rel/rooms.glb --rooms bedroom:3,living,kitchen,bath:2
[[ -s "$T/creator/rel/rooms.rooms.json" ]] && { echo "PASS --rooms sidecar under PWD"; pass=$((pass+1)); } || { echo "FAIL --rooms sidecar missing under PWD"; fail=$((fail+1)); }
[[ -s "$T/w/demo.iamar" ]] && { echo "PASS package file written"; pass=$((pass+1)); } || { echo "FAIL package file missing"; fail=$((fail+1)); }
echo "-- a pack that is not a pack"
echo junk > "$T/bad.pck"
IAMAR_KIT_PACK="$T/bad.pck" check "bad pack: clear message, exit 3" 3 "cannot open the developer kit pack|pack" where
echo "smoke: $pass passed, $fail failed"
[[ "$fail" == 0 ]]
