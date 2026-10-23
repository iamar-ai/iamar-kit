#!/usr/bin/env bash
# The split kit CLI in a stripped, exported Linux browser. The installed runtime
# contains only the browser, a matching built pack, guide and thin wrapper.
# IAMAR_KIT_PACK must name the pack built for this kit/browser pair (run_tests.sh
# supplies it). No source checkout or ambient kit override reaches the commands.
# This is a heavy/native test: KIT_TESTS_HEAVY=1 explicitly opts in.
# Caller must apply the host's normal nice/ionice/flock policy to this script.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ "${KIT_TESTS_HEAVY:-0}" != 1 ]]; then
  echo "SKIP kit_release: native export requires KIT_TESTS_HEAVY=1"
  exit 0
fi
PACK="${IAMAR_KIT_PACK:-}"
[[ -f "$ROOT/project.godot" && -f "$ROOT/export_presets.cfg" ]] || {
  echo "FAIL kit_release: run in an overlaid browser workspace" >&2; exit 2;
}
[[ -n "$PACK" && -f "$PACK" && -s "$PACK" ]] || {
  echo "FAIL kit_release: IAMAR_KIT_PACK must name the matching built kit pack" >&2; exit 2;
}
PACK="$(cd "$(dirname "$PACK")" && pwd)/$(basename "$PACK")"
TMP="$(mktemp -d)"
trap 'python3 -c '"'"'import shutil,sys; shutil.rmtree(sys.argv[1])'"'"' "$TMP"' EXIT
G="${GODOT:-godot}"
# Three ancestors above the binary resolve inside TMP too, isolating the macOS
# fallback kit-folder probe even when this Linux harness runs under a shared /tmp.
INSTALL="$TMP/runtime/linux/bin"
STAGE="$TMP/browser-source"
mkdir -p "$TMP/export" "$TMP/home" "$TMP/work" "$INSTALL" "$STAGE"
# Reject symlinked traversal roots before rsync and again before pruning. The
# private stage is never traversed through a link back into the source checkout.
confine_browser_tree() {
  python3 - "$1" "$2" <<'PY_STAGE'
from pathlib import Path
import shutil
import stat
import sys

root = Path(sys.argv[1]).absolute()
prune = sys.argv[2] == "prune"

def real_directory(path):
    # lstat each ancestor before touching descendants: a real leaf directory
    # beneath a symlinked scripts/ ancestor is not confined.
    for part in reversed((path, *path.parents)):
        if not stat.S_ISDIR(part.lstat().st_mode):
            raise SystemExit("FAIL kit_release: directory must be real, not a symlink: " + str(part))

real_directory(root)
real_directory(root / "scripts" / "kit")
for relative in (".godot", ".godot/imported"):
    path = root / relative
    if path.exists() or path.is_symlink():
        real_directory(path)
keep = {name + suffix for name in ("kit_loop", "world_scaffold", "world_techniques")
        for suffix in (".gd", ".gd.uid")}
scripts = root / "scripts/kit"
for name in keep:
    path = scripts / name
    if name.endswith(".uid") and not path.exists() and not path.is_symlink():
        continue
    if not stat.S_ISREG(path.lstat().st_mode):
        raise SystemExit("FAIL kit_release: runtime script must be a regular file: " + str(path))

if prune:
    # rmtree's descriptor-based traversal refuses symlink races. Fail closed on
    # platforms without that support; unlink links themselves, never their targets.
    if not shutil.rmtree.avoids_symlink_attacks:
        raise SystemExit("FAIL kit_release: symlink-safe tree removal is unavailable")
    def remove_entry(path):
        if stat.S_ISDIR(path.lstat().st_mode):
            shutil.rmtree(path)
        else:
            path.unlink()
    for path in scripts.iterdir():
        if path.name not in keep:
            remove_entry(path)
    cache = root / ".godot"
    if cache.exists():
        for path in cache.iterdir():
            if path.name != "imported":
                remove_entry(path)
PY_STAGE
}
# Never export the overlaid workspace as-is: that would embed the kit scripts and
# let commands pass without mounting the pack. Keep only imported asset payloads
# from the cache; regenerate editor/class/UID/export caches for stripped source.
confine_browser_tree "$ROOT" check
rsync -a --exclude=/.git --exclude=/build --exclude=/kit --exclude=/tests \
  --exclude='*.pck' "$ROOT/" "$STAGE/"
confine_browser_tree "$STAGE" prune
# Copy installed templates into private XDG storage. Never create links or write
# inside the caller's HOME/XDG tree, and reject source symlinks before copying.
prepare_export_templates() {
  python3 - "$1" "$2" <<'PY_TEMPLATES'
from pathlib import Path
import os
import shutil
import stat
import sys

source, target = map(Path, sys.argv[1:])
for path in (source, target.parent):
    for part in reversed((path, *path.parents)):
        if not stat.S_ISDIR(part.lstat().st_mode):
            raise SystemExit("FAIL kit_release: template directory must be real: " + str(part))
for directory, dirs, files in os.walk(source, followlinks=False):
    for name in dirs + files:
        path = Path(directory) / name
        mode = path.lstat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise SystemExit("FAIL kit_release: template entry must be a real file or directory: " + str(path))
shutil.copytree(source, target)
PY_TEMPLATES
}
TEMPLATES="${XDG_DATA_HOME:-$HOME/.local/share}/godot/export_templates"
if [[ ! -e "$TEMPLATES" && ! -L "$TEMPLATES" ]]; then
  TEMPLATES="$HOME/.local/share/godot/export_templates"
fi
EXPORT_DATA="$TMP/export-data"
mkdir -p "$EXPORT_DATA/godot" "$TMP/export-home" "$TMP/export-config" "$TMP/export-cache"
prepare_export_templates "$TEMPLATES" "$EXPORT_DATA/godot/export_templates"
env HOME="$TMP/export-home" XDG_DATA_HOME="$EXPORT_DATA" \
  XDG_CONFIG_HOME="$TMP/export-config" XDG_CACHE_HOME="$TMP/export-cache" \
  timeout 1800 "$G" --headless --path "$STAGE" --export-release Linux "$TMP/export/Oakhaven.x86_64" >"$TMP/export.log" 2>&1 \
  || { echo "FAIL export-release (exit $?)"; tail -20 "$TMP/export.log"; exit 1; }
cp "$TMP/export/Oakhaven.x86_64" "$INSTALL/Oakhaven.x86_64"
chmod +x "$INSTALL/Oakhaven.x86_64"
B="$INSTALL/Oakhaven.x86_64"
E=(env -i HOME="$TMP/home" PATH=/usr/bin:/bin TERM=dumb)
pass=0; fail=0
check() { if grep -Eq "$2" "$3"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; cat "$3"; fail=$((fail+1)); fi; }
run() { "${E[@]}" timeout 300 "$B" --headless --audio-driver Dummy -- --kit "$@" --cwd "$TMP/work"; }
must() {
  local label="$1" pattern="$2" log="$3"; shift 3
  if run "$@" >"$log" 2>&1; then check "$label" "$pattern" "$log"; else
    echo "FAIL $label (exit status)"; cat "$log"; fail=$((fail+1))
  fi
}
cd "$TMP/work"
# This must happen before installing the pack. A successful command would expose
# an accidentally embedded tool or an ambient pack; an arbitrary crash is not a pass.
missing_rc=0
run validate missing-world >missing.log 2>&1 || missing_rc=$?
if [[ "$missing_rc" == 3 ]] && grep -Fq 'the developer kit is not installed' missing.log; then
  echo "PASS stripped browser refuses missing kit"; pass=$((pass+1))
else
  echo "FAIL stripped browser refuses missing kit (exit $missing_rc)"
  cat missing.log
  exit 1
fi
mkdir -p "$INSTALL/kit"
cp "$PACK" "$INSTALL/kit/iamar-kit.pck"
cmp "$PACK" "$INSTALL/kit/iamar-kit.pck"
cp "$ROOT/kit/AGENT_KIT.md" "$ROOT/kit/iamar-world" "$INSTALL/kit/"
chmod +x "$INSTALL/kit/iamar-world"
must "built-in help" '^iamar-world <command>' h.log help
must "new" '^NEW myworld' n.log new myworld --title "My World"
must "validate" '^OK' v.log validate myworld
must "keygen" '^KEY_ID' k.log keygen "$TMP/work/test.key"
must "sign" '^SIGNED ' s.log sign myworld "$TMP/work/test.key" Tester
must "package" '^PACKED ' p.log package myworld "$TMP/work/out/myworld.iamar" "$TMP/work/test.key" Tester
if [ -f "$TMP/work/out/myworld.pieces.json" ]; then echo present >sidecar.log; else echo missing >sidecar.log; fi
check "package writes same-basename sidecar" '^present$' sidecar.log
[ "$(grep -c '^PACKED ' p.log)" = 1 ] && echo once >o.log || echo wrong >o.log; check "package runs once" '^once$' o.log
must "verify package" '^OK$' r.log verify "$TMP/work/out/myworld.iamar"
# Compare the complete layout, rather than accepting one matching line among extras.
printf '%s\n' 'd kit' 'f Oakhaven.x86_64' 'f kit/AGENT_KIT.md' \
  'f kit/iamar-kit.pck' 'f kit/iamar-world' >expected-layout.log
find -P "$INSTALL" -mindepth 1 -printf '%y %P\n' | LC_ALL=C sort >installed-layout.log
if cmp -s expected-layout.log installed-layout.log; then
  echo "PASS isolated split install"; pass=$((pass+1))
else echo "FAIL isolated split install"; cat installed-layout.log; fail=$((fail+1)); fi
must "where" '^KIT ' w.log where
for expected in "KIT $INSTALL/kit" "PACK $INSTALL/kit/iamar-kit.pck" "BROWSER $B"; do
  if grep -Fxq "$expected" w.log; then
    echo "PASS where: $expected"; pass=$((pass+1))
  else echo "FAIL where: $expected"; cat w.log; fail=$((fail+1)); fi
done
# The wrapper discovers the installed browser and adjacent pack without overrides.
if "${E[@]}" timeout 300 "$INSTALL/kit/iamar-world" validate "$TMP/work/myworld" >wrapper.log 2>&1; then
  check "thin wrapper" '^OK$' wrapper.log
else echo 'FAIL thin wrapper (exit status)'; cat wrapper.log; fail=$((fail+1)); fi
# Preview must finish successfully and report actual geometry. Partial VIEW lines
# followed by a timeout/crash, or an empty log without the old error, cannot pass.
preview_result() {
  local rc="$1" log="$2"
  if [[ "$rc" == 0 ]] && grep -Eq '^VIEW 0 .* draw=[1-9][0-9]* prims=[1-9][0-9]* objects=[1-9][0-9]* ' "$log"; then
    echo "PASS preview geometry"; pass=$((pass+1))
  else
    echo "FAIL preview geometry (exit $rc)"; cat "$log"; fail=$((fail+1))
  fi
}
if command -v offscreen >/dev/null; then
  preview_rc=0
  "${E[@]}" timeout 600 "$(command -v offscreen)" "$B" --audio-driver Dummy -- --kit preview \
    --cwd "$TMP/work" myworld "$TMP/work/shot" --view "0,2,12>0,1,0" >preview.log 2>&1 || preview_rc=$?
  preview_result "$preview_rc" preview.log
else
  echo "SKIP preview geometry: offscreen renderer unavailable"
fi
echo "KIT RELEASE TEST $pass passed, $fail failed"
[ "$fail" = 0 ]
