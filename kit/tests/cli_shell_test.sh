#!/usr/bin/env bash
# The POSIX launcher contains discovery/headless policy only; every kit command is
# dispatched by the browser binary itself.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/iamar-kit-shell.XXXXXX")"
trap 'python3 -c '"'"'import shutil,sys; shutil.rmtree(sys.argv[1])'"'"' "$tmp"' EXIT
mkdir -p "$tmp/bundle/kit" "$tmp/work"
cp "$root/iamar-world" "$tmp/bundle/kit/"
cat >"$tmp/bundle/Oakhaven.x86_64" <<'PY'
#!/usr/bin/env python3
import json, os, sys
print(json.dumps({"argv":sys.argv[1:], "pwd":os.getcwd()}))
PY
chmod +x "$tmp/bundle/Oakhaven.x86_64"
cd "$tmp/work"
"$tmp/bundle/kit/iamar-world" validate "world with spaces" >validate.json
"$tmp/bundle/kit/iamar-world" preview world shots >preview.json
python3 - "$tmp/work" validate.json preview.json <<'PY'
import json,sys
cwd=sys.argv[1]
v=json.load(open(sys.argv[2])); p=json.load(open(sys.argv[3]))
assert v['argv']==['--audio-driver','Dummy','--headless','--','--kit','validate','--cwd',cwd,'world with spaces'],v
assert p['argv']==['--audio-driver','Dummy','--','--kit','preview','--cwd',cwd,'world','shots'],p
assert v['pwd']==cwd and p['pwd']==cwd
PY
# preview runs once more after an abort (exit 134, gaps G7), never after another failure.
cat >"$tmp/crashy" <<'SH'
#!/usr/bin/env bash
[[ " $* " == *" where "* ]] && exit 0   # the launcher's browser probe
n=$(( $(cat "$CRASH_COUNT" 2>/dev/null || echo 0) + 1 )); echo $n >"$CRASH_COUNT"
(( n <= ${CRASH_TIMES:-1} )) && exit "${CRASH_RC:-134}"
echo "RENDERED $n"
SH
chmod +x "$tmp/crashy"
CRASH_COUNT="$tmp/c1" IAMAR_BROWSER="$tmp/crashy" "$tmp/bundle/kit/iamar-world" preview w o >"$tmp/retry.log" 2>&1
grep -q '^RENDERED 2$' "$tmp/retry.log" && grep -q 'preview crashed (exit 134), running it once more' "$tmp/retry.log"
rc=0; CRASH_COUNT="$tmp/c2" CRASH_TIMES=2 IAMAR_BROWSER="$tmp/crashy" "$tmp/bundle/kit/iamar-world" preview w o >/dev/null 2>&1 || rc=$?
[[ $rc == 134 && $(cat "$tmp/c2") == 2 ]]
rc=0; CRASH_COUNT="$tmp/c3" CRASH_RC=1 IAMAR_BROWSER="$tmp/crashy" "$tmp/bundle/kit/iamar-world" preview w o >/dev/null 2>&1 || rc=$?
[[ $rc == 1 && $(cat "$tmp/c3") == 1 ]]
rc=0; CRASH_COUNT="$tmp/c4" IAMAR_PREVIEW_RETRY=0 IAMAR_BROWSER="$tmp/crashy" "$tmp/bundle/kit/iamar-world" preview w o >/dev/null 2>&1 || rc=$?
[[ $rc == 134 && $(cat "$tmp/c4") == 1 ]]
# Missing-browser diagnostics stay clear, but help/where now come from the binary.
mkdir -p "$tmp/lonely/kit"; cp "$root/iamar-world" "$tmp/lonely/kit/"
if env -u IAMAR_BROWSER -u IAMAR_PROJECT -u GODOT \
    "$tmp/lonely/kit/iamar-world" help >"$tmp/missing.log" 2>&1; then
  echo 'missing browser unexpectedly succeeded' >&2; exit 1
fi
grep -q '^iamar-world: no iamar browser found' "$tmp/missing.log"
# blender and blender-run need Blender only, never the browser (the Blender tier works on its own).
cat >"$tmp/fake-blender" <<'SH'
#!/usr/bin/env bash
if [[ "${1:-}" == --version ]]; then echo "Blender 4.5.3"; else echo "FAKEBLENDER $*"; fi
SH
chmod +x "$tmp/fake-blender"
env -u IAMAR_BROWSER -u IAMAR_PROJECT -u GODOT IAMAR_KIT_NO_FETCH=1 BLENDER="$tmp/fake-blender" \
  "$tmp/lonely/kit/iamar-world" blender >"$tmp/blender.log" 2>&1 || { cat "$tmp/blender.log" >&2; exit 1; }
grep -q 'Blender 4.5.3' "$tmp/blender.log"
env -u IAMAR_BROWSER -u IAMAR_PROJECT -u GODOT IAMAR_KIT_NO_FETCH=1 BLENDER="$tmp/fake-blender" \
  "$tmp/lonely/kit/iamar-world" blender-run tool.py -- a.glb >"$tmp/blender-run.log" 2>&1 || { cat "$tmp/blender-run.log" >&2; exit 1; }
grep -q '^FAKEBLENDER -b --factory-startup --python tool.py -- a.glb' "$tmp/blender-run.log"
# The all-zero guard moved into world_view, where direct binary calls get it too.
grep -Fq 'every VIEW had draw=0 prims=0 objects=0' "$root/../scripts/kit/world_view.gd"
# This is intentionally routing, not a second implementation of kit commands.
! grep -q '^  new)' "$root/iamar-world"
grep -Fq -- '-- --kit "$cmd" --cwd "$PWD"' "$root/iamar-world"
# materials dispatches to the Python tool (not the browser) in both launchers.
grep -Fq 'materials) tool=' "$root/iamar-world" || grep -Fq '== materials ]] && tool=../style/materials/materials.py' "$root/iamar-world"
grep -Fq 'PYTOOL=..\style\materials\materials.py' "$root/iamar-world.cmd"
mkdir -p "$tmp/bundle/kit/style/materials" "$tmp/bundle/kit/lint"
cp "$root/style/materials/materials.py" "$tmp/bundle/kit/style/materials/"
"$tmp/bundle/kit/iamar-world" materials -h 2>&1 | grep -q 'texel'
echo 'kit CLI shell tests: 13/13'
