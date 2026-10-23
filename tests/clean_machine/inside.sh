#!/usr/bin/env bash
# Runs inside the clean container as an ordinary user (see run.sh).
set -euo pipefail
cd "$HOME"
step() { printf '\n== %s\n' "$*"; }
step "kit/iamar-world new sample (${IAMAR_BROWSER:+browser $IAMAR_BROWSER, }fetches the browser once otherwise)"
# A browser without the --kit loop (the 0.5.1 pin) boots the game instead of exiting: fail, not hang.
timeout 600 kit/iamar-world new sample 2>&1 | tail -5
[[ -f sample/manifest.json ]] || { echo "FAIL: no sample world"; exit 1; }
step "runtimes"; cat kit/runtime/*/.runtime
echo "CLEAN MACHINE PASS: iamar-world new fetched the browser and made sample/manifest.json"
