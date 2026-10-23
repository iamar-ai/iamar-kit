#!/usr/bin/env bash
# Signs a kit release (tools/build_kit_release.sh output) with minisign, at a terminal (decision #96).
#
#   tools/sign_kit_release.sh <release dir> [--key ~/.minisign/iamar-kit.key]
#
# Writes <file>.minisig beside every download named in latest.json (the all-systems zip, the three
# per-system zips, the Windows setup .exe) and iamar-kit.pck when the build left it there. The secret key
# is passphrase-encrypted: minisign asks for the passphrase, so the maintainer signs; no agent holds the key.
# tools/publish_kit_release.sh verifies every signature against the pinned public key kit/minisign.pub.
set -euo pipefail
REL="${1:?usage: sign_kit_release.sh <release dir> [--key FILE]}"; shift
KEY="${HOME}/.minisign/iamar-kit.key"
while [ $# -gt 0 ]; do
  case "$1" in
    --key) KEY="${2:?--key needs a file}"; shift 2 ;;
    *) echo "sign_kit_release: unknown option $1" >&2; exit 2 ;;
  esac
done
[ -f "$REL/latest.json" ] || { echo "sign_kit_release: $REL has no latest.json" >&2; exit 2; }
[ -f "$KEY" ] || { echo "sign_kit_release: no secret key at $KEY (minisign -G -p kit/minisign.pub -s $KEY; docs/PUBLISHING.md 'Signing')" >&2; exit 2; }
command -v minisign >/dev/null || { echo "sign_kit_release: minisign is not installed" >&2; exit 2; }
NAMES="$(python3 - "$REL/latest.json" <<'PY'
import json, re, sys
m = json.load(open(sys.argv[1]))
names = [m["zip"]] + [p[k] for p in m["platforms"].values() for k in ("zip", "exe") if k in p]
for n in names:
    if not re.fullmatch(r"iamar-kit-[0-9.]+(-(windows|macos|linux))?(-windows-setup\.exe|\.zip)", n):
        sys.exit(f"sign_kit_release: unexpected file name {n!r} in latest.json")
print("\n".join(dict.fromkeys(names)))
PY
)"
[ ! -f "$REL/iamar-kit.pck" ] || NAMES="$NAMES"$'\n'"iamar-kit.pck"
while read -r name; do
  [ -f "$REL/$name" ] && [ ! -L "$REL/$name" ] || { echo "sign_kit_release: $REL/$name is missing" >&2; exit 2; }
  minisign -Sm "$REL/$name" -s "$KEY" -x "$REL/$name.minisig" -t "iamar-kit $name"
done <<<"$NAMES"
echo "signed $(wc -l <<<"$NAMES") files in $REL; next: tools/publish_kit_release.sh $REL"
