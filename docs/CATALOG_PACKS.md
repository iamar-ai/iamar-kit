# Catalogue packs: worlds reuse public catalogue objects by hash

PUB16 (an internal task). Status: the **kit side ships** (`iamar-world assets ref`, the
package-step check); the **browser loader is on the iamar browser source (not public) main** (47267ddb,
an internal task: `scripts/worlds/catalog_fetch.gd` over `catalog_pack.gd`), so browsers
built from it advertise `catalog-packs`; the **release packs and the hub mirror
are designed here and filed as jobs** (end of this page). Browsers released
before the loader (and the kit's pinned runtime until it is re-pinned to such a
build) lack `catalog-packs` and refuse a world that references a pack, with that
reason. Carrying the file (`iamar-world assets use`) keeps working everywhere.

## Why

Built-in objects (the 879 models every browser ships) are already reused by
hash: a world lists them in `manifest.reused` and visitors download nothing
(WORLD_FORMAT.md 5a). Objects from the kit catalogue that are **not** built in
(the iamar city models, the harbour and coastal sets, sounds) are copied into
every world that uses them, so ten worlds with the same fountain make a visitor
download it ten times. The public kit repository (`iamar-ai/iamar-kit`) is a
stable, versioned home for those objects, so a world can point at one there and
every browser fetches it once.

## 1. The reference (kit side, shipped)

```
iamar-world assets ref <world folder> <catalogue id|name> [--as assets/<name>.glb]
```

writes one `manifest.reused` record and adds `catalog-packs` to `features`:

```json
{"path": "assets/fountain.glb", "sha256": "<hex of the .glb>", "bytes": 48213,
 "source": {"kind": "catalog", "repo": "iamar-ai/iamar-kit", "release": "v0.3.3",
            "pack": "iamar-city", "id": "94ce18be7a4d9489",
            "file": "kit/catalog/assets/props/fountain.glb"},
 "license": "CC0-1.0", "author": "iamar"}
```

* `repo` is always `iamar-ai/iamar-kit`: browsers fetch from that one origin
  (and its mirror), never from a URL the world names.
* `release` is the kit release tag (`v` + `kit/VERSION.json` `kit_version`).
  An object never changes inside a release; a newer release may add objects.
* `pack` is the catalogue entry's `source.pack` as a slug (`iamar city` ->
  `iamar-city`). One pack is one download (section 2).
* `sha256` and `bytes` are the object's, exactly as in `kit/catalog/catalog.json`.
  The manifest is signed, so the hash is what the browser trusts, not the pack.
* `license` and `author` are the catalogue's; the browser's credits list shows
  them like any reused object.

`ref` refuses what the public release cannot carry: built-in objects (use
`assets use`, which references them as `kind: builtin`), creatures and
generators (they have their own scene entries), locked objects, objects whose
licence is still `licence pending` (today every iamar original, until PUB2,
an internal task, clears them), objects that `kit/catalog/provenance.json` marks
`generative:*` (the public export withholds them), and objects with tier
variants (carry them so the tier files come along).

## 2. The package-step check (kit side, shipped)

`iamar-world package` and `pack` run `kit/catalog/refs.py check <world>` first
when Python 3 is there (both launchers; skipped without Python, as other
Python-only checks are). It fails the package when a catalogue reference:

* names an id that is not in this kit's catalogue, or an object that `ref`
  would refuse now (licence pending, generative, locked, tiered, built-in);
* has a different `sha256`, `bytes`, `pack`, `license` or `author` than the
  catalogue (attribution is part of the reference);
* names another repo, or a release other than this kit's own (`v` + `kit_version`
  in `kit/VERSION.json`): only that release's packs are known to hold these
  objects, so a reference made with an older or newer kit fails until you rerun
  `iamar-world assets ref` with this kit;
* has an unsafe or duplicate `path` (an unsafe path is never looked up on disk),
  or the package also carries that file;
* is present while `features` lacks `catalog-packs`.

It also checks copies made by `assets use`: the credit it wrote
(`"source": "iamar kit catalogue <id>"`) must keep the catalogue's licence, and
the copied object must still hash to the catalogue's `sha256` (an edited copy
is the builder's own work and gets its own credit).

`python3 kit/catalog/refs.py check <world> [--json]` runs it alone. Test:
`python3 kit/tests/catalog/refs_test.py` (record, refusals, thirteen seeded
reference mistakes, edited copy, both launchers).

## 3. Release packs (builder shipped, an internal task; attached to the release, an internal task)

Each public kit release (PUB18 keeps the public repo in step with kit
releases; PUB7, an internal task, keeps big assets out of git and in GitHub Releases)
attaches, per catalogue pack:

* `pack-<pack>.zip`: the pack's objects stored flat as
  `objects/<sha256>.<ext>` (`glb`, `gltf` with its embedded data, `ogg`,
  `png`); nothing else, no folders, no paths from the source tree;
* `pack-<pack>.json`: `{"format": "iamar-catalog-pack", "version": 1,
  "pack", "release", "objects": [{"sha256", "bytes", "ext", "id", "license",
  "author"}]}`;
* one `packs.json` per release: `{"format": "iamar-catalog-packs", "version": 1,
  "repo", "release", "packs": [{"pack", "file", "index", "sha256", "bytes",
  "objects"}]}`, where `file` is the zip, `index` its `pack-<pack>.json`, and
  `sha256`/`bytes` are the zip's. This is the only `packs.json` schema; both
  fetchers read it (`packs.py fetch`/`fetch-pack` by world or pack,
  `tools/asset_packs.py fetch <sha256>` by hash).

Only objects `ref` accepts go into packs, so every reference that passes the
package check resolves in the release it names. A pack larger than 64 MB is
split (`iamar-city-1`, `iamar-city-2`, ...) and `ref` names the part.

There is one builder, `python3 kit/catalog/packs.py build <out dir> [--release vX.Y.Z]
[--max-mb 64]` (`write_packs`; `tools/asset_packs.py build --out <dir>` calls the
same code, an internal task): it writes the three files above for this kit's catalogue
(objects in sha256 order, once per pack, split when a zip could pass the cap,
zip headers and deflate growth counted; reproducible zips), and fails when a
catalogue file is missing or no longer hashes to its entry, when one object
cannot fit in a pack, or when `--max-mb` is over the 64 MB fetch accepts. Measured on kit main 2026-10-23:
148 referenceable objects in 2 packs, 6.1 MB (`iamar-city`,
`iamar-coastal-and-home`), far under the cap, so nothing is split today.

The release step is `tools/publish_public.sh --packs` (an internal task): after the
export passes its checks it runs `packs.py build` for release `v<VERSION>`,
refuses when `kit/VERSION.json` `kit_version` differs from `VERSION` (references
would name another release) or when `packs.json` does not match the built zips
(sha256, bytes, one `pack-<pack>.json` per zip, no unlisted file), and attaches
the folder to the GitHub release with `gh`. Without `--push` it only prints
`DRY_RUN_RELEASE: would attach N files ...`. Test:
`python3 tools/tests/test_publish_public.py`.

### Fetching by hash in the kit (shipped, an internal task)

`iamar-world assets fetch <world> [--json]` (`kit/catalog/packs.py fetch`)
makes every catalogue reference of a world available on the creator's
computer, with the same rules the browser loader follows (section 4): look in
this kit's own tree, then the shared cache (`IAMAR_CATALOG_CACHE`, default the
OS cache folder `iamar/catalog_cache/objects/<sha256>.<ext>`); download each
missing `(release, pack)` once from the GitHub release URL, then the hub
mirror; HTTPS only, 64 MB cap, redirects only to GitHub's and the hub's
hosts; repo, release and pack checked against fixed patterns before any URL is
built; keep only zip entries `objects/<64 hex>.<ext>` whose bytes hash to the
name, never extract by path. A missing object prints the pack and release it
needs and exits 1. `packs.py fetch-pack <release> <pack>` fills the cache
with one pack. Test: `python3 kit/tests/catalog/packs_test.py` (build,
one download for two worlds sharing a pack, tampered, misnamed and
path-traversal entries, oversized pack, names off the patterns, off-host
redirect, offline, both launchers) against a loopback server
(`IAMAR_CATALOG_BASE`, accepted only for 127.0.0.1/localhost).

## 4. The browser loader (on browser main, 47267ddb; an internal task)

On opening a world whose `reused` lists `kind: catalog` records:

1. Look each `sha256` up locally first: the built-in library, then the shared
   catalogue cache `user://catalog_cache/objects/<sha256>.<ext>`. Shared means
   one copy per object per computer, whichever world needed it first.
2. For the misses, group by `(release, pack)` and download each pack **once**,
   only from `https://github.com/iamar-ai/iamar-kit/releases/download/<release>/pack-<pack>.zip`
   or the hub mirror (`https://hub.vessences.com/catalog/<release>/pack-<pack>.zip`,
   tried first when GitHub is slow or blocked). `repo`, `release` and `pack`
   are matched against fixed patterns before any URL is built; a world cannot
   name a host. Size cap 64 MB per pack, HTTPS only, no redirects off those
   hosts.
3. Read the zip without extracting paths: accept only entries named
   `objects/<64 hex>.<allowed ext>`, recompute each entry's sha256 and keep it
   only when it equals its name. Store every verified object of the pack (the
   next world probably wants its neighbours), not just the one asked for.
4. The world loads when every referenced `sha256` is present; otherwise it is
   refused with the reason ("needs pack iamar-city of iamar-ai/iamar-kit
   v0.3.3; offline"). A pack whose objects do not hash to what the signed
   manifest says changes nothing and the world is refused, as for a tampered
   reused object today.
5. The cache counts against the browser's download cache budget; objects used
   by installed worlds are kept, the rest leave least-recently-used first.

The browser advertises `catalog-packs` in its feature list, and its manifest
schema and `validate` accept `source.kind: catalog` (only with that feature).

As built: GitHub is tried first, then the mirror; the first real failure reason
is reported ("HTTP 404", "the pack is larger than 64 MB", "the pack was refused
(...)"), "offline" only when neither answered. A redirect may go only to another
pack URL or to GitHub's release-asset hosts (`release-assets.githubusercontent.com`,
`objects.githubusercontent.com`). Two worlds opening at once share one download.
Only `WorldPackage.open_async` (a visit) downloads; `WorldPackage.open` (the kit,
tools) uses what is cached and otherwise refuses ("not downloaded yet"). The cache
cap is 512 MB (`CatalogFetch.CAP_BYTES`; the browser has no single download-cache
budget); `IAMAR_CATALOG_CACHE` moves it. A cache file that no longer hashes to its
name is deleted and the world refused, so the next open fetches the pack again.
Reused catalogue objects are `.glb` only for now (as all `manifest.reused`
records are); `ogg`/`png` pack entries are stored but not yet usable by a world.
Test: the iamar browser source (not public) `tests/catalog_packs/run.sh`.

## 5. Hub mirror (designed; job filed in iamar-devkit)

When a world is published, the hub runs the same reference check (repo,
release pattern, pack name) and, the first time it sees a `(release, pack)`,
fetches the pack from GitHub, checks it against that release's `packs.json`
and serves it at `/catalog/<release>/pack-<pack>.zip`. The mirror holds no
secrets and needs no trust: the browser checks every object against the signed
manifest's hash, so a wrong mirror can only fail a load, never change a world.

## Jobs

* Kit side: an internal task (this page, `kit/catalog/refs.py`).
* Release packs: builder and kit-side fetch, an internal task (PUB7, `kit/catalog/packs.py`); attaching them to
  each release: an internal task (iamar-creator-knowledge, PUB16b).
* Browser loader: an internal task (iamar-creator-ux, the iamar browser source (not public)), on main as 47267ddb.
* Hub mirror: an internal task (iamar-devkit, the iamar hub source (not public)).
