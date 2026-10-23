#!/usr/bin/env bash
# World UI pages offline in the agent kit (iamar-ui-pages U7):
# `iamar-world validate` checks page JSON (*.page.json, *.patch.json) alone and
# inside a world folder with the browser's rules, the package's images and its
# manifest budgets; `iamar-world preview <page.json>` renders overlay + modal.
#   GODOT=/path/to/godot tests/kit_page_check/run.sh            (headless checks)
#   PREVIEW=1 GODOT=... offscreen tests/kit_page_check/run.sh   (+ rendered preview)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
G="${GODOT:-godot}"
pass=0; fail=0
check() { if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); sed 's/^/    /' "$TMP/last.log" | head -20; fi; }
kit() { timeout 120 "$G" --headless --path "$ROOT" -- --kit "$@" > "$TMP/last.log" 2>&1; echo $? > "$TMP/rc"; }
rc() { cat "$TMP/rc"; }
has() { grep -q -- "$1" "$TMP/last.log"; }

# a PNG header (IHDR only: the checker reads sizes, it never decodes)
png() { python3 -c "import struct,sys,zlib;w,h=int(sys.argv[2]),int(sys.argv[3]);ihdr=struct.pack('>IIBBBBB',w,h,8,6,0,0,0);c=lambda t,d:struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff);raw=b''.join(b'\0'+b'\x80\x60\x30\xff'*w for _ in range(h));open(sys.argv[1],'wb').write(b'\x89PNG\r\n\x1a\n'+c(b'IHDR',ihdr)+c(b'IDAT',zlib.compress(raw))+c(b'IEND',b''))" "$@"; }

kit new "$TMP/w" --id page-check --title "Page check" --author kit-test
check "scaffold a world" "[ $(rc) = 0 ] && [ -f $TMP/w/manifest.json ]"
mkdir -p "$TMP/w/ui" "$TMP/w/img"
png "$TMP/w/img/lantern.png" 48 32
cat > "$TMP/w/ui/shop.page.json" <<'J'
{"theme": {"bg": "#2b2118ee", "fg": "#f3e6c8", "accent": "#d9a441", "font": "serif", "radius": 8, "padding": 16},
 "root": {"type": "column", "gap": 10, "children": [
  {"type": "heading", "text": "Mirela's Lanterns", "level": 1},
  {"type": "image", "src": "asset:img/lantern.png", "width": 240, "height": 160, "fit": "cover"},
  {"type": "text", "text": "Hand-blown glass, **3 gold** each."},
  {"type": "row", "gap": 8, "children": [
   {"type": "input", "id": 2, "placeholder": "How many?", "max_length": 3},
   {"type": "button", "id": 3, "text": "Buy"}]},
  {"type": "text", "id": 4, "text": "You have 10 gold."}]}}
J
echo '{"text": "You bought 2 lanterns."}' > "$TMP/w/ui/bought.patch.json"

kit validate "$TMP/w/ui/shop.page.json"
check "a good page file passes" "[ $(rc) = 0 ] && has 'PAGE .*shop.page.json OK nodes=8' && has '^OK'"
kit validate "$TMP/w/ui/bought.patch.json" "$TMP/w/ui/shop.page.json"
check "a good patch file passes, several files at once" "[ $(rc) = 0 ] && has 'bought.patch.json OK' && has 'shop.page.json OK'"
kit validate --cwd "$TMP/w/ui" shop.page.json
check "a relative page path uses --cwd (the wrappers' form)" "[ $(rc) = 0 ] && has 'shop.page.json OK nodes=8'"
kit validate "$TMP/w"
check "world validate checks its page files" "[ $(rc) = 0 ] && has 'PAGE ui/shop.page.json OK nodes=8' && has 'PAGE ui/bought.patch.json OK' && has '^PAGES 2 files'"

mkdir -p "$TMP/loose"
echo '{"root": {"type": "marquee", "text": "hi"}}' > "$TMP/loose/kind.page.json"
kit validate "$TMP/loose/kind.page.json"
check "an unknown node kind is refused with its path" "[ $(rc) = 1 ] && has 'ERROR .*kind.page.json \$.root' && has 'FAILED'"
echo '{"root": {"type": "text", "text": "x"}, "script": "alert(1)"}' > "$TMP/loose/extra.page.json"
kit validate "$TMP/loose/extra.page.json"
check "a property pages do not have is refused" "[ $(rc) = 1 ] && has 'script\": not a page property'"
echo '{"root": {"type": "text", "text": "x"' > "$TMP/loose/broken.page.json"
kit validate "$TMP/loose/broken.page.json"
check "broken JSON is refused" "[ $(rc) = 1 ] && has 'ERROR .*broken.page.json'"
echo '{"onclick": "x"}' > "$TMP/loose/bad.patch.json"
kit validate "$TMP/loose/bad.patch.json"
check "a patch property that is not patchable is refused" "[ $(rc) = 1 ] && has 'onclick\": not a patchable property'"
kit validate "$TMP/loose/missing.page.json"
check "a missing file is an error" "[ $(rc) = 1 ] && has 'no such file'"
# a loose page whose folder is no readable package: its images were never checked, so no OK
echo x > "$TMP/loose/My Notes.txt"
echo '{"root": {"type": "image", "src": "asset:img/lantern.png"}}' > "$TMP/loose/img.page.json"
kit validate "$TMP/loose/img.page.json"
check "images in an unreadable folder are not passed unchecked" "[ $(rc) = 1 ] && has 'image(s) were not checked'"
kit validate "$TMP/loose/img.page.json" --package "$TMP/w"
check "--package names the world folder for a loose page" "[ $(rc) = 0 ] && has 'img.page.json OK nodes=1'"
rm -f "$TMP/loose/My Notes.txt" "$TMP/loose/img.page.json"

echo '{"root": {"type": "image", "src": "asset:img/none.png"}}' > "$TMP/w/ui/noimg.page.json"
kit validate "$TMP/w/ui/noimg.page.json"
check "an image missing from the package is refused" "[ $(rc) = 1 ] && has 'asset:img/none.png is not in the package'"
png "$TMP/w/img/huge.png" 4096 4
echo '{"root": {"type": "button", "text": "Go", "icon": "asset:img/huge.png"}}' > "$TMP/w/ui/huge.page.json"
kit validate "$TMP/w/ui/huge.page.json"
check "an image over max_image_px is refused" "[ $(rc) = 1 ] && has 'huge.png is 4096x4, over 2048 px'"
printf 'not an image' > "$TMP/w/img/fake.png"
echo '{"root": {"type": "image", "src": "asset:img/fake.png"}}' > "$TMP/w/ui/fake.page.json"
kit validate "$TMP/w/ui/fake.page.json"
check "a file that is not an image is refused" "[ $(rc) = 1 ] && has 'fake.png is not a PNG, JPEG or WebP'"
rm -f "$TMP/w/img/huge.png" "$TMP/w/img/fake.png" "$TMP/w/ui/huge.page.json" "$TMP/w/ui/fake.page.json"

kit validate "$TMP/w"
check "world validate fails on a bad page file" "[ $(rc) = 1 ] && has 'ERROR page ui/noimg.page.json' && has 'PAGE ui/shop.page.json OK'"
kit validate "$TMP/w" --report-v1
check "the machine report names the page file" "[ $(rc) = 0 ] && grep -q 'IAMAR_VALIDATION_V1 \[1,false' $TMP/last.log && grep -q 'reference.invalid\",\"ui/noimg.page.json' $TMP/last.log"
rm -f "$TMP/w/ui/noimg.page.json"

# the manifest may lower max_page_nodes (docs/WORLD_FORMAT.md, UI page budgets)
python3 - "$TMP/w/manifest.json" <<'P'
import json, sys
m = json.load(open(sys.argv[1])); m.setdefault("budgets", {})["max_page_nodes"] = 4; m["api_version"] = "0.4"
json.dump(m, open(sys.argv[1], "w"), indent=1)
P
kit validate "$TMP/w/ui/shop.page.json"
check "the manifest's max_page_nodes is applied" "[ $(rc) = 1 ] && has 'ERROR .*shop.page.json'"
kit validate "$TMP/w"
check "world validate applies it too" "[ $(rc) = 1 ] && has 'ERROR page ui/shop.page.json'"

if [ "${PREVIEW:-0}" = 1 ]; then
  python3 - "$TMP/w/manifest.json" <<'P'
import json, sys
m = json.load(open(sys.argv[1])); m["budgets"].pop("max_page_nodes"); json.dump(m, open(sys.argv[1], "w"), indent=1)
P
  timeout 180 "$G" --path "$ROOT" -- --kit preview "$TMP/w/ui/shop.page.json" "$TMP/shots/shop" --size 960x540 > "$TMP/last.log" 2>&1; echo $? > "$TMP/rc"
  check "preview renders overlay and modal" "[ $(rc) = 0 ] && has 'SHOT overlay 960x540' && has 'SHOT modal 960x540' && [ -s $TMP/shots/shop_overlay.png ] && [ -s $TMP/shots/shop_modal.png ]"
  # the page really is drawn where it sits (an internal task: the overlay was blank since U9b
  # and a whole-image byte sample still passed): the preview counts its page area
  check "the overlay page is drawn on the right" "grep -Eq 'SHOT overlay .*\\(page area ([1-9][0-9]*)% drawn\\)' $TMP/last.log"
  check "the modal page is drawn" "grep -Eq 'SHOT modal .*\\(page area ([1-9][0-9]*)% drawn\\)' $TMP/last.log"
  [ -n "${KEEP_SHOTS:-}" ] && cp "$TMP"/shots/*.png "$KEEP_SHOTS"/ 2>/dev/null
fi
echo "KIT PAGE CHECK TEST $pass passed, $fail failed"
[ $fail = 0 ]
