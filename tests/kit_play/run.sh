#!/usr/bin/env bash
# `iamar-world play <folder>`: an unsigned draft opens in the real browser game at once,
# stays offline behind a DRAFT banner, and a save reloads it (an internal task).
#   IAMAR_PROJECT=<browser checkout with the kit merged over it> GODOT=godot tests/kit_play/run.sh
#   IAMAR_BROWSER=<browser binary> IAMAR_KIT_PACK=<iamar-kit.pck> tests/kit_play/run.sh
# tools/run_tests.sh runs it in its workspace (IAMAR_PROJECT set there). Headless: no window.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
check() { if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); grep -E '^(PLAY|WARN|ERROR|SCRIPT ERROR)' "$TMP/last.log" | head -20 | sed 's/^/    /'; fi; }
play() { timeout 600 "$ROOT/kit/iamar-world" play "$@" --headless > "$TMP/last.log" 2>&1; echo $? > "$TMP/rc"; }
rc() { cat "$TMP/rc"; }
has() { grep -q -- "$1" "$TMP/last.log"; }
cp -r "$ROOT/tests/kit_playtest/world" "$TMP/w"

play "$TMP/w" --quit-after 3
check "an unsigned folder opens in the game at once (no keygen/sign/package)" "[ $(rc) = 0 ] && has '^PLAY READY pt-sample after' && has '^PLAY END pt-sample'"
check "the run says it is a draft: unsigned, local only, offline, never hosted" "has '^PLAY pt-sample: a DRAFT (unsigned, local only, offline, never hosted)'"

# a save while playing: the world is rebuilt in place; a broken save keeps the last build
timeout 600 "$ROOT/kit/iamar-world" play "$TMP/w" --quit-after 40 --headless > "$TMP/last.log" 2>&1 &
pid=$!
for _ in $(seq 600); do has '^PLAY READY' && break; kill -0 $pid 2>/dev/null || break; sleep 1; done
python3 - "$TMP/w/scene.json" <<'EOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
d.setdefault("primitives", []).append({"id": "play_added_box", "shape": "box", "position": [3, 0.5, 3], "size": [1, 1, 1], "color": "#a05030"})
json.dump(d, open(p, "w"), indent=2)
EOF
for _ in $(seq 30); do has '^PLAY RELOADED' && break; sleep 1; done
cp "$TMP/w/scene.json" "$TMP/good.json"; printf '{ not json' > "$TMP/w/scene.json"
for _ in $(seq 30); do has '^PLAY RELOAD FAILED' && break; sleep 1; done
wait $pid; echo $? > "$TMP/rc"
check "saving scene.json reloads the world (PLAY RELOADED)" "has '^PLAY RELOADED pt-sample (1)'"
check "a save that does not open keeps the last build and says why" "has '^PLAY RELOAD FAILED' && [ $(rc) = 0 ] && has '^PLAY END pt-sample'"
cp "$TMP/good.json" "$TMP/w/scene.json"

play "$TMP/w" --quit-after 1 --no-reload
check "--no-reload plays without watching the folder" "[ $(rc) = 0 ] && has '^PLAY READY' && ! has 'saving any file of the world reloads it'"

play "$TMP/nope"
check "a folder that does not exist is bad input (exit 2)" "[ $(rc) = 2 ] && has 'is not a folder'"
play "$TMP/w" --fly
check "an unknown option is bad input (exit 2)" "[ $(rc) = 2 ] && has 'unknown option --fly'"
mkdir -p "$TMP/broken" && printf '{}' > "$TMP/broken/manifest.json"
play "$TMP/broken"
check "a folder that does not open says so and points at validate (exit 2)" "[ $(rc) = 2 ] && has 'the world does not open' && has 'iamar-world validate'"

mkdir -p "$TMP/rel" && cp -r "$TMP/w" "$TMP/rel/w"
(cd "$TMP/rel" && timeout 600 "$ROOT/kit/iamar-world" play w --quit-after 1 --headless > "$TMP/last.log" 2>&1; echo $? > "$TMP/rc")
check "a relative folder is the caller's folder" "[ $(rc) = 0 ] && has '^PLAY READY pt-sample'"

# never the player's profile, never the hub: the source says so
S="$ROOT/scripts/kit/world_play.gd"
check "the draft runs offline (net disabled for the run)" "grep -q 'Settings.set_value(\"net\", \"enabled\", false)' '$S'"
check "the draft is never signed, packaged or hosted" "! grep -qE 'world_sign|world_package|world_host|prepare_served_package' '$S'"
check "the launchers give play a draft profile, not the player's own" "grep -q 'iamar-draft-profile' '$ROOT/kit/iamar-world' && grep -q 'iamar-draft-profile' '$ROOT/kit/iamar-world.cmd'"

echo "play: $pass passed, $fail failed"
[[ $fail == 0 ]]
