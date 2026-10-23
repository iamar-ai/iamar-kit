#!/usr/bin/env bash
# Build a plain-GDScript pack from one committed kit revision, never from a worktree glob.
#   tools/build_pack.sh [out.pck] [full-commit-oid]  defaults: build/iamar-kit.pck, HEAD
#   GODOT=/path/to/godot 4.7 binary                default: godot
# Local edits and untracked scripts are deliberately NOT included. Commit changes first.
# Release callers MUST pass the same resolved commit recorded in their metadata.
# PCKPacker keeps res://scripts/kit/*.gd paths; no browser/account scripts, project.binary,
# project.godot, UID files or .godot caches are copied into the pack.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GODOT_BIN="${GODOT:-godot}"
[[ $# -le 2 ]] || { echo "usage: build_pack.sh [out.pck] [full-commit-oid]" >&2; exit 2; }
OUT="${1:-$ROOT/build/iamar-kit.pck}"
REV="${2:-$(git --no-replace-objects -C "$ROOT" rev-parse --verify HEAD)}"
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT";; esac
echo "build_pack: committed inputs $REV; working-tree edits and untracked scripts are not included" >&2
# A unique private directory prevents stale files and concurrent builds sharing inputs.
W="$(mktemp -d "${TMPDIR:-/tmp}/iamar-kit-pack.XXXXXXXX")"
trap 'rm -rf -- "$W"' EXIT
python3 "$ROOT/tools/snapshot_pack_inputs.py" snapshot "$ROOT" "$REV" "$W/input"
I="$W/input"
mkdir -p "$(dirname "$OUT")"
# Build and check privately; do not replace a previous artifact on a failed build.
"$GODOT_BIN" --headless --path "$I" -s build_pack.gd -- "$W/kit.pck" "$I/scripts" > "$W/build.log" 2>&1 \
  || { cat "$W/build.log" >&2; echo "build_pack: godot failed" >&2; exit 1; }
[[ -s "$W/kit.pck" ]] || { cat "$W/build.log" >&2; echo "build_pack: pack was not written" >&2; exit 1; }
# The pack drivers and stub project are also exact blobs from the same commit.
C="$W/check"; mkdir "$C"; cp "$I/project.godot" "$I/list_pack.gd" "$C/"
"$GODOT_BIN" --headless --path "$C" -s list_pack.gd -- "$W/kit.pck" > "$W/listing" 2>&1 \
  || { cat "$W/listing" >&2; exit 1; }
got="$(python3 "$ROOT/tools/snapshot_pack_inputs.py" verify "$I/inputs.json" "$W/listing")" \
  || { cat "$W/listing" >&2; exit 1; }
mv -f -- "$W/kit.pck" "$OUT"
echo "built $OUT ($(wc -c < "$OUT") bytes, $got scripts, commit $REV)"
