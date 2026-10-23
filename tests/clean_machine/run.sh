#!/usr/bin/env bash
# Clean-machine test of the kit download (vision Done-when 2, an internal task): a fresh Ubuntu container with
# no Node and no Godot/iamar browser gets only the kit folder, runs kit/iamar-world new (which fetches
# the pinned browser). The Node kit app is retired (iamar-devmode); the kit UI is in the browser. Needs docker and the network.
#   tests/clean_machine/run.sh <kit folder | iamar-kit-N.N.N.zip>    (default: build/release zip)
#   CLEAN_IMAGE=ubuntu:24.04 (default)
#   CLEAN_BROWSER=<folder with a browser binary named iamar*/Oakhaven*>: mount that build read-only and
#     use it through IAMAR_BROWSER instead of fetching the pinned browser (for a browser newer than the
#     pin in kit/runtime.lock). The pinned 0.5.1 browser has no --kit loop.
# The container installs only ca-certificates and curl (what a desktop Linux already has).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
src="${1:-$(ls -1 "$ROOT"/build/release/iamar-kit-*.zip 2>/dev/null | tail -1)}"
[[ -n "$src" && -e "$src" ]] || { echo "clean_machine: give a kit folder or release zip (tools/build_kit_release.sh)" >&2; exit 2; }
image="${CLEAN_IMAGE:-ubuntu:24.04}"
W="$(mktemp -d "${TMPDIR:-/tmp}/kit-clean.XXXXXX")"; trap 'rm -rf -- "$W"' EXIT
mkdir -p "$W/home"
if [[ -d "$src" ]]; then cp -r "$src" "$W/home/kit"; else (cd "$W/home" && python3 -m zipfile -e "$src" . && chmod +x kit/iamar-world kit/runtime_fetch.sh); fi
[[ -f "$W/home/kit/iamar-kit.pck" ]] || { echo "clean_machine: $src has no iamar-kit.pck" >&2; exit 2; }
cp "$ROOT/tests/clean_machine/inside.sh" "$W/inside.sh"
mounts=(-v "$W:/w"); browser_env=""
if [[ -n "${CLEAN_BROWSER:-}" ]]; then
  b="$(cd "$CLEAN_BROWSER" && ls -1 iamar.[0-9]* iamar.x86_64 Oakhaven.x86_64 2>/dev/null | head -1)" || true
  [[ -n "$b" ]] || { echo "clean_machine: no iamar*/Oakhaven* binary in $CLEAN_BROWSER" >&2; exit 2; }
  mounts+=(-v "$(cd "$CLEAN_BROWSER" && pwd):/browser:ro"); browser_env="IAMAR_BROWSER=/browser/$b"
fi
docker run --rm "${mounts[@]}" "$image" bash -c '
  set -e; export DEBIAN_FRONTEND=noninteractive
  apt-get -qq update >/dev/null && apt-get -qq install -y --no-install-recommends ca-certificates curl >/dev/null
  ! command -v node && ! command -v godot && ! ls /usr/bin/*godot* 2>/dev/null || { echo "clean_machine: image already has node or godot" >&2; exit 9; }
  exec setpriv --reuid='"$(id -u)"' --regid='"$(id -g)"' --clear-groups env -i HOME=/w/home PATH=/usr/local/bin:/usr/bin:/bin '"$browser_env"' bash /w/inside.sh
'
