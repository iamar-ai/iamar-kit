#!/usr/bin/env bash
# `iamar-world playtest` in the real browser game: a visitor is driven through a world
# (talk, pick up, go to a trigger, use a script entity) and quest state and script
# effects are checked per step.
#   IAMAR_PROJECT=<browser checkout with the kit merged over it> GODOT=godot tests/kit_playtest/run.sh
#   IAMAR_BROWSER=<browser binary> IAMAR_KIT_PACK=<iamar-kit.pck> tests/kit_playtest/run.sh
#   SHOTS=1 offscreen tests/kit_playtest/run.sh ...   (+ a rendered run: one shot per step)
# tools/run_tests.sh runs it in its workspace (IAMAR_PROJECT set there).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/tests/kit_playtest"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
check() { if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); grep -E '^(STEP|QUEST|EXPECT|PLAYTEST|ERROR|SCRIPT ERROR)' "$TMP/last.log" | head -30 | sed 's/^/    /'; fi; }
pt() { timeout 1300 "$ROOT/kit/iamar-world" playtest "$@" > "$TMP/last.log" 2>&1; echo $? > "$TMP/rc"; }
rc() { cat "$TMP/rc"; }
has() { grep -q -- "$1" "$TMP/last.log"; }

pt "$HERE/world" "$TMP/sack" --steps "$HERE/sack.steps.json" --headless
check "3-step quest (pick up, talk, trigger) completes" "[ $(rc) = 0 ] && has '^PLAYTEST PASS: 7 step' && has '^QUEST sack done'"
check "each step prints its quest state" "has '^QUEST sack active step=1' && has '^QUEST sack active step=2' && has '^QUEST sack ready'"
check "the dialog and its choices are reported" "has '^DIALOG Miller Ada: Accept: The Flour Sack' && has '^REPLY My flour!'"
check "playtest.json is written" "python3 -c \"import json,sys;r=json.load(open('$TMP/sack/playtest.json'));sys.exit(0 if r['ok'] and len(r['steps'])==7 and r['steps'][-1]['quests']['sack']['state']=='done' else 1)\""

# a returning visitor (an internal task): the browser's welcome guides (Goodwife Alys, Guide Rowan)
# would otherwise walk into the world with a fresh profile; --hour only sets the clock
check "the run is a returning visitor (welcome quests done)" "has '^playtest: a returning visitor (thornbury_welcome, welcome_menus done' && python3 -c \"import json,sys;sys.exit(0 if json.load(open('$TMP/sack/playtest.json')).get('returning_visitor') else 1)\""
python3 -c "import json;d=json.load(open('$HERE/sack.steps.json'));d['new_visitor']=True;d['steps']=d['steps'][:1];json.dump(d,open('$TMP/newv.json','w'))"
pt "$HERE/world" "$TMP/newv" --steps "$TMP/newv.json" --headless --hour 20.5
check "new_visitor keeps the welcome quests; --hour says it sets the clock only" "! has '^playtest: a returning visitor' && has '^NOTE hour 20.5 sets the browser.s clock only.*time_of_day'"

pt "$HERE/world" "$TMP/bad" --steps "$HERE/wrong_order.steps.json" --headless
check "a step the world does not allow fails (exit 1) and says why" "[ $(rc) = 1 ] && has '^STEP 1 talk FAIL no choice Here is your sack.' && has '^EXPECT FAIL quest sack state done' && has '^PLAYTEST FAIL'"

echo '{"steps": [{"do": "fly"}]}' > "$TMP/fly.json"
pt "$HERE/world" "$TMP/x" --steps "$TMP/fly.json" --headless
check "an unknown step kind is bad input (exit 2)" "[ $(rc) = 2 ] && has 'every step needs'"

# Every wait (hero selection, entering play) comes out of the one --timeout budget (an internal task):
# a 1 s budget gives up at once instead of waiting minutes for the browser.
pt "$HERE/world" "$TMP/t1" --steps "$HERE/sack.steps.json" --headless --timeout 1
check "--timeout bounds the browser start too" "[ $(rc) = 1 ] && grep -qE 'within --timeout 1 s|timed out after 1 s' '$TMP/last.log' && python3 -c \"import json,sys;sys.exit(0 if json.load(open('$TMP/t1/playtest.json'))['seconds'] < 30 else 1)\""

mkdir -p "$TMP/rel" && cp -r "$HERE/world" "$TMP/rel/w" && cp "$HERE/sack.steps.json" "$TMP/rel/s.json"
(cd "$TMP/rel" && timeout 600 "$ROOT/kit/iamar-world" playtest w out --steps s.json --headless > "$TMP/last.log" 2>&1; echo $? > "$TMP/rc")
check "relative paths are the caller's folder" "[ $(rc) = 0 ] && [ -f $TMP/rel/out/playtest.json ]"

pt "$HERE/reach/world" "$TMP/reach" --steps "$HERE/reach/steps.json" --headless
check "use reaches a low script entity the way the interact key does" "has '^STEP 1 use ok' && has '^EXPECT ok   note contains used the cylinder'"
check "a package sound (asset:audio/ding.ogg) is an EFFECT sound; expect matches its path or file name (an internal task)" "has '^EFFECT sound asset:audio/ding.ogg at \\[0.0, 0.5, 0.0\\]' && has '^EXPECT ok   sound asset:audio/ding.ogg played' && has '^EXPECT ok   sound ding played'"
check "use of an entity out of the key's 2.5 m reach fails and says how far it is" "[ $(rc) = 1 ] && has '^STEP 2 use FAIL no script entity within the key.s 2.5 m: sphere is' && ! has '^EFFECT note.*used the high sphere'"
check "use fails when the key would pick a nearer entity" "has '^STEP 3 use FAIL nearest script entity is sphere at' && ! has '^EFFECT note.*used the box' && ! has '^EFFECT note.*used the decoy'"

# The Little Harbour (blind test attempt 2, archived): its bell hangs 2.48 m up, out of the
# interact key's reach, so `use` must fail there while the rest of the errand still works
# (a trap recorded in kit/playtest/README.md; an internal task).
H="$ROOT/kit/blindtest/harbour/attempt-2/world"
if [[ -d "$H" ]]; then
  pt "$H" "$TMP/harbour" --steps "$ROOT/kit/playtest/harbour_lost_net.json" --headless
  check "harbour lost_net errand: net, talk, trigger, hand-in; the bell out of key reach fails" "[ $(rc) = 1 ] && has '^QUEST lost_net done' && has '^STEP 5 use FAIL no script entity within the key.s 2.5 m: asset:assets/bell.glb is 3.06 m away' && ! has '^EFFECT sound bell'"
fi

# Lantern Harbour (blind test attempt 3): a talk with no choice closes the dialog (the next
# talk is not blocked), and ring_bell's on_complete (scene objects and a light shown or
# hidden, a scene sound played: the browser's QuestEffects, not a world script) prints
# EFFECT lines that the expects see (an internal task).
H3="$ROOT/kit/blindtest/harbour/attempt-3/world"
if [[ -d "$H3" ]]; then
  pt "$H3" "$TMP/harbour3" --steps "$HERE/harbour_ring_bell.steps.json" --headless
  check "talk with no choice closes the dialog; quest on_complete shows/hides/plays as EFFECT lines" "[ $(rc) = 0 ] && has '^STEP 2 talk ok' && has '^EFFECT visible pier_lantern_lit true' && has '^EFFECT visible pier_lantern_dark false' && has '^EFFECT sound bell' && has '^EXPECT ok   light pier_lantern_light energy'"
  # offline by default (an internal task): online, a hub connect or scene admission restarts the
  # browser's progress lifetime; on a slow renderer that landed mid-run and dropped lost_net
  check "the run is offline: no hub, no progress reset during a step" "has '^playtest: offline' && ! has '^WARN playtest: the browser reset quest progress' && python3 -c \"import json,sys;sys.exit(0 if json.load(open('$TMP/harbour3/playtest.json')).get('online') is False else 1)\""
fi

# A rendered run with a fresh private profile builds the whole city before hero selection
# (minutes on a busy computer, plus any wait for a render slot), so it gets a longer budget:
# PLAYTEST_TIMEOUT seconds for the playtest (--timeout), and the outer limit a minute more.
if [[ "${SHOTS:-0}" == 1 ]]; then
  PT_LIMIT="${PLAYTEST_TIMEOUT:-1800}"
  (timeout $((PT_LIMIT + 60)) "$ROOT/kit/iamar-world" playtest "$HERE/world" "$TMP/shots" --steps "$HERE/sack.steps.json" --timeout "$PT_LIMIT" > "$TMP/last.log" 2>&1; echo $? > "$TMP/rc")
  n=$(ls "$TMP/shots/shots/"*.png 2>/dev/null | wc -l)
  check "a rendered run saves a shot after every step" "[ $(rc) = 0 ] && [ $n = 7 ] && has '^SHOT '"
  if [[ -d "$H3" ]]; then
    # the rendered harbour run lost lost_net at the pickup while it was online (an internal task)
    (timeout $((PT_LIMIT + 60)) "$ROOT/kit/iamar-world" playtest "$H3" "$TMP/shots3" --steps "$HERE/harbour_ring_bell.steps.json" --timeout "$PT_LIMIT" > "$TMP/last.log" 2>&1; echo $? > "$TMP/rc")
    n=$(ls "$TMP/shots3/shots/"*.png 2>/dev/null | wc -l)
    check "a rendered harbour ring_bell run keeps its quests (9/9, 9 shots)" "[ $(rc) = 0 ] && [ $n = 9 ] && has '^PLAYTEST PASS: 9 step' && ! has '^WARN playtest: the browser reset quest progress'"
  fi
fi

# goto [x, z] inside a roofed hall stands on its floor, not on the roof (an internal task)
pt "$HERE/roofed/world" "$TMP/roofed" --steps "$HERE/roofed/steps.json" --headless
check "goto [x, z] under a roof slab lands on the ground, not the roof" "[ $(rc) = 0 ] && has '^EXPECT ok   player y'"

# Exploration steps walk and swim the visitor with the browser's own movement (an internal task):
# a crate, the generated house's front door, its stair, an upstairs bedroom, the pool (swim,
# dive, back up, out at the spawn) and a look at the house; then --auto on the same world.
E="$HERE/explore"
pt "$E/world" "$TMP/explore" --steps "$E/steps.json" --headless --timeout 900
check "walk_to, enter, climb and enter a room walk the visitor there (house with a stair)" "has '^STEP 1 walk_to ok' && has '^STEP 2 enter ok' && has '^STEP 3 climb ok' && has '^STEP 4 enter ok' && has '^EXPECT ok   in room house/bedroom_4'"
check "swim_to, dive, surface, walk out: swimming, head under, underwater view, out of the water" "has '^STEP 5 swim_to ok' && has '^EXPECT ok   swimming true' && has '^STEP 6 dive ok' && has '^UNDERWATER head 1\\.[0-9]* m under' && has '^EXPECT ok   underwater true' && has '^STEP 7 surface ok' && has '^STEP 8 walk_to ok' && has '^EXPECT ok   swimming false'"
check "look_at reports the line of sight; the run passes with walked metres in playtest.json" "has '^LOOK [0-9.]* m, line of sight' && [ $(rc) = 0 ] && python3 -c \"import json,sys;r=json.load(open('$TMP/explore/playtest.json'));sys.exit(0 if r['ok'] and r['steps'][3]['walked'] > 10 and 'stair top' in r['steps'][3]['route'] else 1)\""
python3 -c "import json;json.dump({'steps':[{'do':'enter','room':'house/bedroom_4','from':'spawn','near':0.6},{'do':'swim_to','at':[30,30],'from':'spawn'}]},open('$TMP/bad_explore.json','w'))"
cp -r "$E/world" "$TMP/blocked" && python3 - "$TMP/blocked/scene.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p))
# a wall across the front door: the walk in gets stuck there
s["primitives"].append({"id": "wall", "shape": "box", "size": [0.4, 3, 6], "position": [14.8, 1.5, 0], "collision": "box"})
json.dump(s, open(p, "w"))
PY
pt "$TMP/blocked" "$TMP/blocked_out" --steps "$TMP/bad_explore.json" --headless
check "a blocked door is 'stuck' with where; swimming where there is no water fails" "[ $(rc) = 1 ] && has '^STEP 1 enter FAIL stuck at .* short of inside the front door' && has '^STEP 2 swim_to FAIL arrived but not swimming: no water here'"
pt "$E/world" "$TMP/auto" --auto --headless --timeout 1200
check "--auto visits the pool, the house and every room, the portal and the crate" "[ $(rc) = 0 ] && has '^playtest: --auto adds' && has '(auto: water pool)' && has '(auto: room house/bedroom_5)' && has '(auto: portal to_roofed)' && has '(auto: object crate)' && has '^AUTO [0-9]* step(s): [0-9]* ok, 0 failed, 0 fall(s)' && ! has '^PLAYTEST FAIL'"

echo "kit_playtest: $pass passed, $fail failed"
[[ $fail == 0 ]]
