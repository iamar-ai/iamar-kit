#!/usr/bin/env bash
# Fetch a runtime the kit needs when this computer has none: the pinned Node.js or the iamar
# browser that runs the kit commands. Pins and sha256 sums are in kit/runtime.lock.
#   runtime_fetch.sh node|browser    prints the runtime's executable; fetches it once into
#                                    kit/runtime/<name>/ (sha256-checked) when it is missing.
# IAMAR_KIT_RUNTIME=<dir> puts runtimes elsewhere; IAMAR_KIT_NO_FETCH=1 never downloads.
# The browser comes from the invitation-only iamar.ai: the download pass from `iamar-world
# download-login` (IAMAR_DOWNLOAD_TOKEN or its file) or the password in IAMAR_KIT_CODE.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
name="${1:?usage: runtime_fetch.sh node|browser}"
case "$name" in node|browser) ;; *) echo "runtime_fetch: unknown runtime '$name' (node or browser)" >&2; exit 2;; esac
base="${IAMAR_KIT_RUNTIME:-$here/runtime}"; dest="$base/$name"
case "$(uname -s)" in Linux) os=linux;; Darwin) os=darwin;; *) echo "runtime_fetch: unsupported system $(uname -s)" >&2; exit 2;; esac
case "$(uname -m)" in x86_64|amd64) arch=x64;; aarch64|arm64) arch=arm64;; *) echo "runtime_fetch: unsupported machine $(uname -m)" >&2; exit 2;; esac
platform="$os-$arch"
exe() {
  case "$name" in
    node) printf '%s\n' "$dest/bin/node";;
    browser) local c; for c in "$dest/iamar.AppImage" "$dest/iamar.x86_64" "$dest/Oakhaven.x86_64" "$dest/iamar.app/Contents/MacOS/Oakhaven" "$dest/iamar.app/Contents/MacOS/iamar" \
        "$dest/Oakhaven.app/Contents/MacOS/Oakhaven"; do [[ -f "$c" ]] && { printf '%s\n' "$c"; return; }; done
      printf '%s\n' "$dest/Oakhaven.x86_64";;
  esac
}
line="$(awk -v n="$name" -v p="$platform" '$1==n && $2==p {print; exit}' "$here/runtime.lock")"
[[ -n "$line" ]] || { echo "runtime_fetch: no $name runtime for $platform in kit/runtime.lock" >&2; exit 3; }
read -r _ _ version url sum top <<<"$line"
if [[ -f "$dest/.runtime" && "$(cat "$dest/.runtime")" == "$version $sum" && -x "$(exe)" ]]; then exe; exit 0; fi
[[ "${IAMAR_KIT_NO_FETCH:-0}" != 1 ]] || { echo "runtime_fetch: $name is missing and IAMAR_KIT_NO_FETCH=1" >&2; exit 3; }
mkdir -p "$base"
tmp="$(mktemp -d "$base/.fetch.XXXXXX")"; trap 'rm -rf -- "$tmp"' EXIT
echo "iamar kit: fetching $name $version for $platform (once) from $url" >&2
archive="$tmp/${url##*/}"
# iamar.ai downloads sit behind the invitation gate. First choice: the download pass that
# `iamar-world download-login` saved after the person approved it (sent as a Bearer header).
# Else the code is the HTTP Basic password (any user name).
# Invitation codes are opaque passwords. Escape curl's quoted config syntax rather than
# restricting their alphabet; keep both the original and escaped value out of shell traces.
set +x
code=""; token=""; case "$url" in https://iamar.ai/*)
  token="${IAMAR_DOWNLOAD_TOKEN:-}"
  tfile="${IAMAR_DOWNLOAD_TOKEN_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/iamar/download_token}"
  if [[ -z "$token" && -f "$tfile" ]]; then token="$(head -c 200 -- "$tfile" | tr -d '\r\n')"; fi
  [[ -z "$token" || "$token" =~ ^iamar-dl1\.[0-9]+\.[0-9a-f]{64}$ ]] || { echo "runtime_fetch: the download pass (IAMAR_DOWNLOAD_TOKEN or $tfile) is malformed: run iamar-world download-login again" >&2; exit 3; }
  [[ -n "$token" ]] || code="${IAMAR_KIT_CODE:-}"
  [[ -n "$token" || -n "$code" ]] || { echo "runtime_fetch: $name comes from iamar.ai, which is invitation-only." >&2
    echo "  HUMAN STEP: run iamar-world download-login and approve it in your web browser (your agent can run it and show you the link)," >&2
    echo "  or set IAMAR_KIT_CODE=<download password>; then run again" >&2; exit 3; };; esac
curl_user_config() {
  local escaped="$code"
  escaped="${escaped//\\/\\\\}"
  escaped="${escaped//\"/\\\"}"
  escaped="${escaped//$'\t'/\\t}"
  escaped="${escaped//$'\n'/\\n}"
  escaped="${escaped//$'\r'/\\r}"
  escaped="${escaped//$'\v'/\\v}"
  printf 'user = "kit:%s"\n' "$escaped"
}
if command -v curl >/dev/null; then
  # -q must be first: a user curlrc must not add tracing or change credential handling.
  if [[ -n "$token" ]]; then
    printf 'header = "Authorization: Bearer %s"\n' "$token" | curl -q -fL --retry 3 --proto '=https' -K - -o "$archive" "$url" >&2 || {
      echo "runtime_fetch: iamar.ai refused the download pass (it lasts 30 days and ends when the download password changes): run iamar-world download-login again" >&2; exit 3; }
  elif [[ -n "$code" ]]; then curl_user_config | curl -q -fL --retry 3 --proto '=https' -K - -o "$archive" "$url" >&2
  else curl -q -fL --retry 3 --proto '=https' -o "$archive" "$url" >&2; fi
elif [[ -n "$code$token" ]]; then echo "runtime_fetch: downloading from iamar.ai needs curl (wget would show the code in the process list)" >&2; exit 3
elif command -v wget >/dev/null; then wget -q --https-only -O "$archive" "$url" >&2
elif command -v python3 >/dev/null; then python3 -I -c 'import sys,urllib.request,shutil
assert sys.argv[1].startswith("https://")
with urllib.request.urlopen(sys.argv[1]) as r, open(sys.argv[2],"wb") as f: shutil.copyfileobj(r,f)' "$url" "$archive"
else echo "runtime_fetch: need curl, wget or python3 to download $name" >&2; exit 3; fi
if command -v sha256sum >/dev/null; then got="$(sha256sum "$archive" | cut -d' ' -f1)"
else got="$(shasum -a 256 "$archive" | cut -d' ' -f1)"; fi
[[ "$got" == "$sum" ]] || { echo "runtime_fetch: $name download sha256 $got does not match kit/runtime.lock ($sum); not installed" >&2; exit 4; }
mkdir "$tmp/x"
case "$archive" in
  *.tar.gz|*.tgz) tar -xzf "$archive" -C "$tmp/x";;
  *.AppImage) cp "$archive" "$tmp/x/iamar.AppImage"; chmod +x "$tmp/x/iamar.AppImage";;
  *.zip) if command -v unzip >/dev/null; then unzip -q "$archive" -d "$tmp/x"; else tar -xf "$archive" -C "$tmp/x"; fi;;
  *) echo "runtime_fetch: unknown archive type $archive" >&2; exit 4;;
esac
# top "." keeps the whole archive (the macOS browser zip holds Oakhaven.app at its root)
src="$tmp/x"; [[ "$top" == . ]] || src="$tmp/x/$top"
[[ -d "$src" ]] || { echo "runtime_fetch: $archive has no $top/ folder" >&2; exit 4; }
printf '%s %s\n' "$version" "$sum" > "$src/.runtime"
rm -rf -- "$dest.old"; if [[ -e "$dest" ]]; then mv -- "$dest" "$dest.old"; fi
mv -- "$src" "$dest"; rm -rf -- "$dest.old"
[[ -x "$(exe)" ]] || { echo "runtime_fetch: $name unpacked but $(exe) is missing" >&2; exit 4; }
echo "iamar kit: $name $version ready in $dest" >&2
exe
