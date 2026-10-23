# Package-to-import filename handoff

Run `python3 tests/kit_package_handoff/test_contract.py` from a complete source
checkout. `--root <checkout>` supports an isolated exact-source composition.
These are source checks and independent inert specification models. They never
launch Godot, create keys, sign, create archives, compile or run world scripts,
copy real packages, contact a host or change a user's browser.

The producer must pair any requested `<name>.iamar` with adjacent
`<name>.pieces.json`. Before this correction, `package world out/release.iamar`
could succeed but write `<manifest-id>-<version>.pieces.json`, which neither
CLI/UI import nor self-host discovery associated with the selected archive.
`--baseline --root <old-checkout>` reproduces that mismatch from the old helper
source without executing it. Canonical id-version filenames remain unchanged.

Coverage includes relative, Unix, Windows, dotted, spaced and Unicode paths;
distinct outputs with the same signed identity; matching importer/discovery
source; the existing two-argument helper API and returned sidecar path; existing
archive/sidecar files, directories and dangling links; partial-output failure
and retry; preservation of unrelated old identity-named sidecars; and retained
signing/verification calls. Collision/failure tests use dictionary markers and
do not establish actual filesystem or native failure behavior.

The pack API still permits uppercase or absent output extensions; this does not
make those paths importable. The importer retains its lowercase `.iamar` suffix
requirement. Use that suffix for the normal package-to-import flow. Paths such
as `release.IAMAR` and `release` derive `release.pieces.json` but remain refused
as import selections until the user explicitly gives both files matching valid
names. No automatic rename is performed.

Output preflight refuses an existing archive or sidecar before opening either.
It is single-writer, not atomic against concurrent writers or a filesystem
sandbox. Later write failures may leave partial files and no rollback is added.
The CLI signs the source folder before the packing preflight, so an output
collision can still follow a source manifest/signature rewrite. Use fresh output
names, keep the resulting pair together, and preserve partial files for review.

Next native gate, only with separate authorization: package an already-approved
inert world to a noncanonical fresh filename using an approved signing key;
verify both signatures and every piece; import the exact pair through the shared
CLI/UI verifier into an isolated destination; verify canonical installed names
and exact bytes; repeat with collisions, failure injection and supported-platform
symlinks. No key generation, signing, native parse/runtime, actual import,
visitor entry, performance or platform acceptance is claimed by this fixture.

The existing native release fixture `tests/kit_release/run.sh` now also checks
that its `out/myworld.iamar` package produces `out/myworld.pieces.json`. Its
native export/keygen/sign/package operations remain unrun for this source-only
change; a shell syntax check is not evidence those operations pass.
