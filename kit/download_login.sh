#!/usr/bin/env bash
# iamar-world download-login: get a download pass for the gated iamar browser without the
# download password (device code; docs/RUNTIME_FETCH_CREDENTIALS.md). The person approves once
# in their own web browser; the agent never sees the password.
#   download_login.sh          start, print the HUMAN STEP, wait for the approval (up to 10 min)
#   download_login.sh start    start and print the HUMAN STEP, then exit (an agent shows it to its person)
#   download_login.sh wait     wait for the approval of the code that `start` made
# The pass is saved in $IAMAR_DOWNLOAD_TOKEN_FILE (default ~/.config/iamar/download_token, mode 600)
# and kit/runtime_fetch.sh sends it. It lasts 30 days. It is never printed.
set -euo pipefail
set +x
mode="${1:-both}"
case "$mode" in both|start|wait) ;; *) echo "usage: iamar-world download-login [start|wait]" >&2; exit 2;; esac
site="${IAMAR_SITE:-https://iamar.ai}"; site="${site%/}"
proto='=https'   # plain http only for a test server on this computer
case "$site" in https://*) ;; http://127.0.0.1:*|http://localhost:*) proto='=http';; *) echo "download-login: IAMAR_SITE must be https://" >&2; exit 2;; esac
file="${IAMAR_DOWNLOAD_TOKEN_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/iamar/download_token}"
pending="$file.pending"
command -v curl >/dev/null || { echo "download-login: needs curl" >&2; exit 2; }
umask 077
mkdir -p "$(dirname "$file")"
field() { printf '%s' "$2" | grep -o "\"$1\": *\"[^\"]*\"" | head -1 | sed 's/^.*: *"//; s/"$//'; }
number() { printf '%s' "$2" | grep -o "\"$1\": *[0-9]*" | head -1 | sed 's/^.*: *//'; }

if [[ "$mode" != wait ]]; then
  reply="$(curl -q -sS --proto "$proto" --data-binary '' -w '\n%{http_code}' "$site/download/agent/start")" || {
    echo "download-login: could not reach $site/download/agent/start" >&2; exit 3; }
  status="${reply##*$'\n'}"; reply="${reply%$'\n'*}"
  [[ "$status" == 200 ]] || { echo "download-login: $site answered HTTP $status to start (it may not offer agent downloads yet; set IAMAR_KIT_CODE to the download password instead)" >&2; exit 3; }
  code="$(field code "$reply")"; secret="$(field device_secret "$reply")"; url="$(field verify_url "$reply")"
  ttl="$(number expires_in "$reply")"; ttl="${ttl:-600}"
  [[ "$code" =~ ^[A-Z0-9]{4}-[A-Z0-9]{4}$ && "$secret" =~ ^[A-Za-z0-9_-]{20,200}$ && ( "$url" == "$site/download/agent?code=$code" || "$url" == "https://iamar.ai/download/agent?code=$code" ) ]] || {
    echo "download-login: unexpected reply from $site/download/agent/start" >&2; exit 3; }
  printf '%s %s %s\n' "$code" "$secret" "$(( $(date +%s) + ttl ))" > "$pending"
  echo "HUMAN STEP: open $url in your web browser, check that it shows the code $code,"
  echo "  enter the iamar download password if it asks, and press Allow. The code works for $(( ttl / 60 )) minutes."
  if [[ "$mode" == start ]]; then
    echo "Then run: iamar-world download-login wait"
    exit 0
  fi
fi

[[ -f "$pending" ]] || { echo "download-login: no code is waiting; run iamar-world download-login start first" >&2; exit 2; }
read -r code secret deadline < "$pending"; deadline="${deadline%$'\r'}"
[[ "$code" =~ ^[A-Z0-9]{4}-[A-Z0-9]{4}$ && "$secret" =~ ^[A-Za-z0-9_-]{20,200}$ && "$deadline" =~ ^[0-9]+$ ]] || {
  rm -f -- "$pending"; echo "download-login: the waiting code is damaged; run iamar-world download-login start again" >&2; exit 2; }
echo "waiting for the approval of $code ..." >&2
while (( $(date +%s) <= deadline + 5 )); do
  reply="$(printf '{"code": "%s", "device_secret": "%s"}' "$code" "$secret" |
    curl -q -sS --proto "$proto" -X POST -H 'Content-Type: application/json' --data-binary @- -w '\n%{http_code}' "$site/download/agent/poll")" || { sleep 3; continue; }
  status="${reply##*$'\n'}"; reply="${reply%$'\n'*}"
  if [[ "$status" == 410 ]]; then
    rm -f -- "$pending"; echo "download-login: code $code expired or was used; run iamar-world download-login again" >&2; exit 4
  fi
  if [[ "$status" == 200 && "$(field status "$reply")" == approved ]]; then
    token="$(field token "$reply")"
    [[ "$token" =~ ^iamar-dl1\.[0-9]+\.[0-9a-f]{64}$ ]] || { echo "download-login: unexpected token format from $site" >&2; exit 3; }
    tmp="$(mktemp "$file.XXXXXX")"; printf '%s\n' "$token" > "$tmp"; chmod 600 "$tmp"; mv -f -- "$tmp" "$file"
    rm -f -- "$pending"
    echo "DOWNLOAD PASS saved in $file (30 days). kit/runtime_fetch.sh browser now downloads the iamar browser."
    exit 0
  fi
  sleep 3
done
rm -f -- "$pending"
echo "download-login: nobody approved $code in time; run iamar-world download-login again" >&2
exit 4
