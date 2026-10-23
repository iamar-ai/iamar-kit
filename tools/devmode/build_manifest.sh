#!/usr/bin/env bash
# Developer mode kit manifest: builds iamar-kit.pck twice from one committed revision, requires
# identical hashes (reproducible), and writes kit_manifest.json with the fields kit_pin.json copies.
#   tools/devmode/build_manifest.sh [out-dir] [--min-browser N.N.N]   default out-dir: build/devmode
#   GODOT=/path/to/godot 4.7 binary                                    default: godot
# Output: out-dir/iamar-kit.pck and out-dir/kit_manifest.json
#   {version, commit, pck, pck_bytes, pck_sha256, min_browser, packages: {}}
# `packages` (zip/exe sha256 and url) is filled in by the packaging step (an internal task).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/build/devmode"; MINB="0.0.0"
while [ $# -gt 0 ]; do
  case "$1" in
    --min-browser) MINB="${2:?--min-browser needs N.N.N}"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    -*) echo "build_manifest: unknown option $1" >&2; exit 2 ;;
    *) OUT="$1"; shift ;;
  esac
done
[[ "$MINB" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "build_manifest: min-browser '$MINB' is not N.N.N" >&2; exit 2; }
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT";; esac
REV="$(git --no-replace-objects -C "$ROOT" rev-parse --verify HEAD)"
# VERSION comes from the same commit as the pack, never the working tree (an uncommitted bump
# would label an old pack with the new version).
VERSION="$(git --no-replace-objects -C "$ROOT" show "$REV:VERSION" | tr -d '[:space:]')"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "build_manifest: VERSION '$VERSION' at $REV is not N.N.N" >&2; exit 2; }
mkdir -p "$OUT"
T="$(mktemp -d "${TMPDIR:-/tmp}/iamar-kit-manifest.XXXXXXXX")"
trap 'rm -rf -- "$T"' EXIT
"$ROOT/tools/build_pack.sh" "$T/a.pck" "$REV" >&2
"$ROOT/tools/build_pack.sh" "$T/b.pck" "$REV" >&2
A="$(sha256sum "$T/a.pck" | cut -d' ' -f1)"; B="$(sha256sum "$T/b.pck" | cut -d' ' -f1)"
[ "$A" = "$B" ] || { echo "build_manifest: NOT reproducible: $A != $B" >&2; exit 1; }
mv -f -- "$T/a.pck" "$OUT/iamar-kit.pck"
BYTES="$(wc -c < "$OUT/iamar-kit.pck" | tr -d ' ')"
python3 - "$OUT/kit_manifest.json" "$VERSION" "$REV" "$BYTES" "$A" "$MINB" <<'PY'
import json, sys
p, version, commit, nbytes, sha, minb = sys.argv[1:]
m = {"version": version, "commit": commit, "pck": "iamar-kit.pck", "pck_bytes": int(nbytes),
     "pck_sha256": sha, "min_browser": minb, "packages": {}}
with open(p, "w") as f:
    json.dump(m, f, indent=2, sort_keys=True); f.write("\n")
PY
echo "manifest $OUT/kit_manifest.json: kit $VERSION, pck sha256 $A (rebuild identical)"
