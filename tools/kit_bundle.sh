#!/usr/bin/env bash
# The developer kit as it ships: its own download (downloads.vessences.com/kit/), unzipped
# beside the browser or anywhere with IAMAR_KIT set (tools/build_kit_release.sh makes the zip).
# One source, so a builder's agent reads the same files in the zip and on the public page.
#   tools/kit_bundle.sh <out_dir> [git rev, default HEAD]   -> <out_dir>/kit/
#   Optional: append --typescript-archive /approved/typescript-5.9.3.tgz
#   (rev WORKTREE: the working tree's files, for tests of uncommitted changes)
# What it does to the repo's kit/:
#   - the format docs AGENT_KIT.md points to (docs/WORLD_FORMAT.md, WORLD_API.md,
#     WORLD_TIERS.md, TYPESCRIPT_WORLDS.md) go in kit/docs/, and its "../docs/" links
#     become "docs/";
#   - kit/thumbnails and kit/turntables stay out unless KIT_BUNDLE_THUMBNAILS=1 (the release sets it: the
#     browser no longer carries them);
#   - KIT_BUNDLE_PACK=<iamar-kit.pck> is copied in as kit/iamar-kit.pck (the launchers pass it
#     to the browser; tools/build_pack.sh makes it);
#   - ts-world/ (the TypeScript packer, prebuilt guest, API files) comes from the BROWSER
#     repository (the iamar browser source (not public)): IAMAR_BROWSER_REPO=<checkout> at IAMAR_BROWSER_REV
#     (default HEAD). Without IAMAR_BROWSER_REPO it is read from the same root as the kit
#     (the tests' single synthetic tree);
#   - index.html: a plain page listing the files, for the public URL.
set -euo pipefail
OUT="${1:?usage: kit_bundle.sh <out_dir> [rev]}"
REV="${2:-HEAD}"
TS_ARCHIVE=""
if [ "$#" -gt 2 ]; then
  [ "$#" -eq 4 ] && [ "$3" = --typescript-archive ] && [ -n "$4" ] || {
    echo 'usage: kit_bundle.sh <out_dir> [rev] [--typescript-archive /approved/typescript-5.9.3.tgz]' >&2; exit 2;
  }
  TS_ARCHIVE="$4"
  # Refuse accidental deletion of the supplied input by the existing kit reset.
  # The assembler itself remains the authority for archive bytes and no-follow I/O.
  python3 - "$OUT" "$TS_ARCHIVE" <<'PY_PREFLIGHT'
import os, sys
out, archive = sys.argv[1:]
if any(not os.path.isabs(p) or os.path.normpath(p) != p for p in (out, archive)):
    sys.exit('kit_bundle: offline assembly requires canonical absolute output and archive paths')
if os.path.commonpath((os.path.realpath(out), os.path.realpath(archive))) == os.path.realpath(out):
    sys.exit('kit_bundle: approved archive must be outside the output directory')
PY_PREFLIGHT
fi
# KIT_BUNDLE_REPO: the repository to read when this script runs from a copy
# (oak_release.sh takes the script from origin/main, so the checkout need not be current).
ROOT="${KIT_BUNDLE_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
# The TypeScript packer and API files are the browser's (the iamar browser source (not public)), not the kit's.
TS_ROOT="${IAMAR_BROWSER_REPO:-$ROOT}"
if [ "$TS_ROOT" = "$ROOT" ]; then TS_REV="$REV"; else TS_REV="${IAMAR_BROWSER_REV:-HEAD}"; fi
EXCLUDE=(--exclude="kit/thumbnails" --exclude="kit/turntables")
[ "${KIT_BUNDLE_THUMBNAILS:-0}" = 1 ] && EXCLUDE=(--exclude="kit/.retired-none")
KIT="$OUT/kit"
rm -rf "$KIT"
mkdir -p "$OUT"
if [ "$REV" = WORKTREE ]; then
  (cd "$ROOT" && tar -c ${EXCLUDE[@]+"${EXCLUDE[@]}"} kit) | tar -x -C "$OUT"
else
  git -C "$ROOT" archive "$REV" kit | tar -x -C "$OUT" ${EXCLUDE[@]+"${EXCLUDE[@]}"}
fi
# Public allow-list: the same kit/export/rules.json excludes and leak scan as tools/export_public.py
# (the kit ships through this script, not through the exporter). Internal records stay out.
RULES_TMP="$(mktemp)"
if [ "$REV" = WORKTREE ]; then cp "$ROOT/kit/export/rules.json" "$RULES_TMP"; else git -C "$ROOT" show "$REV:kit/export/rules.json" > "$RULES_TMP"; fi
python3 "$(cd "$(dirname "$0")" && pwd)/kit_prune_public.py" "$KIT" "$RULES_TMP" || { rm -f "$RULES_TMP"; rm -rf "$KIT"; exit 1; }
rm -f "$RULES_TMP"
[ -x "$KIT/iamar-world" ] && [ -f "$KIT/iamar-world.cmd" ] && [ -f "$KIT/AGENT_KIT.md" ] || { echo "kit_bundle: kit/ incomplete at $REV" >&2; exit 1; }
mkdir -p "$KIT/docs"
for d in WORLD_FORMAT WORLD_API WORLD_TIERS TYPESCRIPT_WORLDS; do
  if [ "$REV" = WORKTREE ]; then cp "$ROOT/docs/$d.md" "$KIT/docs/"; else git -C "$ROOT" show "$REV:docs/$d.md" > "$KIT/docs/$d.md"; fi
done
# links: the docs sit beside AGENT_KIT.md now (kit/docs/), not one level up
sed -i 's#](\.\./docs/#](docs/#g' "$KIT/AGENT_KIT.md"
# the pack of the kit's tool scripts: the launchers export IAMAR_KIT_PACK when it sits beside them
if [ -n "${KIT_BUNDLE_PACK:-}" ]; then
  [ -f "$KIT_BUNDLE_PACK" ] || { echo "kit_bundle: KIT_BUNDLE_PACK $KIT_BUNDLE_PACK is not a file" >&2; exit 1; }
  cp "$KIT_BUNDLE_PACK" "$KIT/iamar-kit.pck"
  # the pack must be the browser's Godot minor (IAMAR_BROWSER_REPO names its checkout)
  if [ -n "${IAMAR_BROWSER_REPO:-}" ] && [ -f "$IAMAR_BROWSER_REPO/project.godot" ]; then
    python3 "$ROOT/tools/kit_pack_check.py" "$KIT/iamar-kit.pck" --browser "$IAMAR_BROWSER_REPO" >&2 || exit 1
  fi
fi
# TypeScript world fast path: packer + prebuilt QuickJS guest. Node remains an
# external prerequisite. Official TypeScript is included only by explicit offline
# assembly below; generated setup text records the actual selected mode.
mkdir -p "$KIT/ts-world/prebuilt"
ts_copy() { # <rev-path> <dest>   (from the browser repository, see TS_ROOT)
  if [ "$TS_REV" = WORKTREE ]; then cp "$TS_ROOT/$1" "$2"; else git -C "$TS_ROOT" show "$TS_REV:$1" > "$2"; fi
}
for f in pack.mjs compiler.mjs audit-wasm.mjs api_generated.mjs dependencies.mjs gen_bindings.mjs template-files.mjs; do
  ts_copy "tools/typescript-world/$f" "$KIT/ts-world/$f"
done
ts_copy tools/typescript-world/prebuilt/iamar_ts_guest.wasm "$KIT/ts-world/prebuilt/iamar_ts_guest.wasm"
ts_copy tools/typescript-world/prebuilt/provenance.json "$KIT/ts-world/prebuilt/provenance.json"
ts_copy api/typescript/iamar-world.d.ts "$KIT/ts-world/iamar-world.d.ts"
ts_copy api/world_api.json "$KIT/ts-world/world_api.json"
ts_copy api/ui_page.schema.json "$KIT/ts-world/ui_page.schema.json"
ts_copy tools/typescript-world/guest/THIRD_PARTY_NOTICES.txt "$KIT/ts-world/THIRD_PARTY_NOTICES.txt"
ts_copy tools/typescript-world/guest/LICENSES_RECEIPT.json "$KIT/ts-world/LICENSES_RECEIPT.json"
if [ -n "$TS_ARCHIVE" ]; then
  # Use the selected revision's helper AND pinned manifest, not the checkout's
  # potentially different versions. Run only after reset and before the index.
  ASSEMBLER_STAGE="$(mktemp -d "$OUT/.typescript-assembler.XXXXXXXX")"
  trap 'rm -rf -- "$ASSEMBLER_STAGE"' EXIT
  ts_copy tools/typescript-world/bundle_runtime.py "$ASSEMBLER_STAGE/bundle_runtime.py"
  ts_copy tools/typescript-world/runtime_manifest.json "$ASSEMBLER_STAGE/runtime_manifest.json"
  mkdir -p "$KIT/ts-world/node_modules"
  python3 "$ASSEMBLER_STAGE/bundle_runtime.py" \
    --typescript-archive "$TS_ARCHIVE" \
    --destination "$KIT/ts-world/node_modules/typescript" \
    > "$KIT/ts-world/TYPESCRIPT_ASSEMBLY.json"
  # The copied guide must agree with this delivered kit. Refuse changed source
  # wording instead of silently leaving an external-install instruction behind.
  python3 - "$KIT/AGENT_KIT.md" <<'PY_GUIDE'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
replacements = {
    """Bash or Python. The optional TypeScript wrapper command needs separately
installed Node.js and TypeScript (see [TypeScript world scripts](#typescript-world-scripts)).""":
    """Bash or Python. The optional TypeScript wrapper command needs external Node.js;
this kit includes its compiler (see [delivered setup](ts-world/TYPESCRIPT.md)).""",
    """Provide **Node.js 20 or newer** on `PATH` (or an approved executable path in
`IAMAR_TS_NODE`) and the official **TypeScript 5.9.3** package, installed
separately. Ask before installing missing tools. With approval, run
`npm i typescript@5.9.3 --prefix kit/ts-world` from the bundle or repository
root, or set `IAMAR_TS_COMPILER` to the absolute path of an existing
`typescript/lib/typescript.js` with its accompanying declaration files.
In a Windows source checkout, set `IAMAR_TS_COMPILER` explicitly when using
that `kit/ts-world` install: the Windows wrapper otherwise looks beside its
selected packer under `tools/typescript-world/`.""":
    """Provide **Node.js 20 or newer** on `PATH` (or an approved executable path in
`IAMAR_TS_NODE`). Ask before installing missing tools. This kit already contains
the pinned official **TypeScript 5.9.3** compiler API and standard libraries at
`kit/ts-world/node_modules/typescript`; no separate compiler install is needed.
See [delivered setup](ts-world/TYPESCRIPT.md) for retained licenses, overrides
and the separate native validation/preview workflow.""",
}
for old, new in replacements.items():
    if text.count(old) != 1:
        sys.exit('kit_bundle: AGENT_KIT.md compiler guidance changed; reconcile before offline bundling')
    text = text.replace(old, new)
path.write_text(text)
PY_GUIDE
  cat > "$KIT/ts-world/TYPESCRIPT.md" <<'EOF'
# TypeScript for the world packer: bundled compiler

This kit includes the pinned official TypeScript **5.9.3** compiler API subset
at `node_modules/typescript/lib/typescript.js`: 104 files, including all 100
standard-library declarations, official package metadata, `LICENSE.txt` and
`ThirdPartyNoticeText.txt`. These notices stay with the creator tools; they are
separate from the guest notice copied into compiled worlds. The retained package
metadata does not mean optional npm/CLI entrypoints are included.

`TYPESCRIPT_ASSEMBLY.json` records assembly, not a signature or an independent
trust anchor. Final distribution integrity must come from verified release bytes.
EOF
else
  cat > "$KIT/ts-world/TYPESCRIPT.md" <<'EOF'
# TypeScript for the world packer: external compiler

The official TypeScript **5.9.3** compiler is not bundled in this kit. Supply it
with its standard-library files, for example by installing it yourself:

```sh
npm i typescript@5.9.3 --prefix kit/ts-world
# -> kit/ts-world/node_modules/typescript/lib/typescript.js
```

Alternatively set `IAMAR_TS_COMPILER` to the absolute path of an approved
`typescript.js` alongside its standard libraries. The packer checks version
5.9.3; version equality alone does not authenticate an external compiler.
EOF
fi
cat >> "$KIT/ts-world/TYPESCRIPT.md" <<'EOF'

## Runtime and workflow

Node **20 or newer** is required separately, on PATH or selected explicitly by
`IAMAR_TS_NODE`. No Node executable is bundled or acquired by this operation.
`IAMAR_TS_COMPILER` can explicitly select an external compiler instead of the
bundled path. Existing CLI discovery is unchanged. The prebuilt QuickJS guest
needs no local guest build toolchain. `LICENSES_RECEIPT.json` is guest provenance,
not a substitute for `THIRD_PARTY_NOTICES.txt` or the compiler's license files.

The API spec and `ui_page.schema.json` ship together in `ts-world/`. A custom
spec path passed to `generate(specPath)` or the packer's `--spec` option must
have its matching `ui_page.schema.json` beside it. There is no fallback to the
source checkout or installed kit schema. Direct generator callers can pass an
explicit schema path as `generate(specPath, pageSchemaPath)`; the packer does
not expose a separate schema override.

From the download root, with a source file, package template and fresh output:

```sh
kit/iamar-world compile-typescript world.ts template fresh-output
kit/iamar-world validate fresh-output/world
kit/iamar-world preview fresh-output/world /absolute/path/to/screenshots
```

On Windows use `kit\iamar-world.cmd`. Compilation writes static build output;
it does not execute the guest, validate, render, sign or publish it. Validation
and preview are separate native-browser commands, and use the `world` subfolder,
not the build-output root. Inspect the preview screenshots before proceeding.
A bundled compiler is not evidence of supported-target or native preview success.

The native creator UI uses a separately configured scoped creator service and
permissions. This kit does not configure that service or add an in-app compiler.
Its Private preview opens an already signed artifact, not raw compiler output.
EOF
VERSION="$(git -C "$ROOT" describe --tags --always "$REV" 2>/dev/null || echo "$REV")"
{
  echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
  echo '<title>iamar world kit</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem}code{background:#eef}</style></head><body>'
  echo '<h1>iamar world kit</h1>'
  echo '<p>Everything an AI agent needs to build an iamar world. Start with <a href="AGENT_KIT.md">AGENT_KIT.md</a>. The kit (the <code>iamar-world</code> command) is its own download: unzip it next to the iamar browser (a folder named <code>kit</code>) or anywhere with <code>IAMAR_KIT</code> set; it runs through the browser, needs no Godot editor and no source checkout. TypeScript compilation needs external Node and the compiler setup described in <a href="ts-world/TYPESCRIPT.md">TYPESCRIPT.md</a>.</p><ul>'
  (cd "$KIT" && find . -type f ! -name index.html ! -path './thumbnails/*' ! -path './turntables/*' | sed 's#^\./##' | sort) | while read -r f; do
    echo "<li><a href=\"$f\">$f</a></li>"
  done
  [ -d "$KIT/thumbnails" ] && echo "<li>thumbnails/ (a preview of every catalogue entry, used by <code>assets search</code>)</li>"
  [ -d "$KIT/turntables" ] && echo "<li>turntables/ (8 views of every catalogue entry in one strip)</li>"
  echo "</ul><p>Kit revision $VERSION.</p></body></html>"
} > "$KIT/index.html"
echo "KIT $KIT ($VERSION)"
