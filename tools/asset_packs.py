#!/usr/bin/env python3
"""Release packs: catalogue objects ship as zips on the public kit's GitHub Release, not in git (PUB7b, an internal task).

  python3 tools/asset_packs.py build --out <dir> [--release vX.Y.Z] [--max-mb 64]
  python3 tools/asset_packs.py fetch <sha256> [--pack <pack>] [--base <release URL>] [--library <dir>]

`build` runs the kit's one release-pack builder, kit/catalog/packs.py (`write_packs`; the same as
`python3 kit/catalog/packs.py build <dir>`), and fails when it leaves any entry out. Per catalogue
pack (kit/catalog/refs.py pack_slug) it writes the files of docs/CATALOG_PACKS.md section 3:
`pack-<pack>.zip` holding only `objects/<sha256>.<ext>`, `pack-<pack>.json` (the pack index) and one
`packs.json` (rows `pack`, `file`, `index`, `sha256`, `bytes`, `objects`). Only objects `refs.py ref`
accepts go in, once per pack; a pack whose zip could exceed --max-mb (at most the 64 MB that `fetch`
accepts; zip headers and deflate growth counted) is split into `<pack>-1`, `<pack>-2`, ... Each
object is hashed while packing and must equal its catalogue sha256. The zips are reproducible
(sorted entries, fixed timestamps), so the same catalogue gives the same sha256.

`fetch` gets one object by its sha256 into a local library (`<library>/objects/<sha256>.<ext>`):
it reads `packs.json` and the pack indexes at the release URL, downloads the pack holding the
object once, checks the zip against `packs.json`, keeps every entry whose name is
`objects/<64 hex>.<ext>` and whose content hashes to that name (the whole pack is stored, so its
neighbours are local next time; a library file that no longer hashes to its name is replaced),
and fails when the object is still missing. An object already in the library is not downloaded again. The release URL defaults to
https://github.com/iamar-ai/iamar-kit/releases/download/v<kit version>/; plain http is accepted
only for localhost (tests).

Exit 0 on success, 1 on any error, 2 on bad arguments. Test: python3 tools/tests/test_asset_packs.py
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "kit" / "catalog"))
import refs  # noqa: E402  (kit/catalog/refs.py: pack_slug, refusal, release_tag)
import packs  # noqa: E402  (kit/catalog/packs.py: the one release-pack builder)
from packs import PackError  # noqa: E402

FORMAT_PACK = "iamar-catalog-pack"
FORMAT_INDEX = "iamar-catalog-packs"
EXTS = ("glb", "gltf", "ogg", "png")
OBJECT_RE = re.compile(r"^objects/([0-9a-f]{64})\.(%s)$" % "|".join(EXTS))
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PACK_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_PACK_BYTES = 64 << 20
MAX_JSON_BYTES = 8 << 20


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def default_base(release: str) -> str:
    return "https://github.com/%s/releases/download/%s/" % (refs.PUBLIC_REPO, release)


def default_library() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "iamar-kit" / "catalog"


# ---------------------------------------------------------------- build

def build(cat: dict, out: Path, release: str, prov: dict | None = None, kit_root: Path = KIT_ROOT,
          max_bytes: int = MAX_PACK_BYTES) -> dict:
    """Write the release packs with the kit's one builder (kit/catalog/packs.py write_packs, an internal task)
    and return the packs.json data; any entry the builder had to leave out is an error here."""
    index, problems = packs.write_packs(out, release, max_bytes, cat, prov, kit_root)
    if problems:
        raise PackError("; ".join(problems))
    return index


# ---------------------------------------------------------------- fetch

def _check_base(base: str) -> str:
    u = urllib.parse.urlparse(base)
    local = u.hostname in ("localhost", "127.0.0.1", "::1")
    if u.scheme != "https" and not (u.scheme == "http" and local):
        raise PackError("release URL must be https (http only for localhost): %s" % base)
    return base if base.endswith("/") else base + "/"


def _get(base: str, name: str, cap: int) -> bytes:
    with urllib.request.urlopen(base + name, timeout=60) as r:
        data = r.read(cap + 1)
    if len(data) > cap:
        raise PackError("%s is larger than %d bytes" % (name, cap))
    return data


def _store(library: Path, data: bytes, pack_row: dict) -> int:
    """Check a downloaded pack zip and store each verified object; return how many were stored."""
    if len(data) != pack_row["bytes"] or _sha(data) != pack_row["sha256"]:
        raise PackError("pack-%s.zip does not match packs.json (sha256/bytes)" % pack_row["pack"])
    objdir = library / "objects"
    objdir.mkdir(parents=True, exist_ok=True)
    kept = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            m = OBJECT_RE.match(info.filename)
            if not m or info.file_size > MAX_PACK_BYTES:
                continue
            body = z.read(info)
            if _sha(body) != m.group(1):
                continue
            dest = objdir / ("%s.%s" % m.groups())
            if dest.is_file() and refs.sha256_file(dest) == m.group(1):
                kept += 1
                continue
            fd, tmp = tempfile.mkstemp(dir=objdir, prefix=".part-")
            with os.fdopen(fd, "wb") as f:
                f.write(body)
            os.replace(tmp, dest)
            kept += 1
    return kept


def local(library: Path, sha: str) -> Path | None:
    for ext in EXTS:
        p = library / "objects" / ("%s.%s" % (sha, ext))
        if p.is_file() and refs.sha256_file(p) == sha:
            return p
    return None


def fetch(sha: str, base: str, library: Path, pack: str | None = None) -> Path:
    """The library path of object `sha`, downloading its pack from the release at `base` when needed."""
    sha = sha.lower()
    if not SHA_RE.match(sha):
        raise PackError("not a sha256: %s" % sha)
    if pack is not None and not PACK_RE.match(pack):
        raise PackError("bad pack name: %s" % pack)
    have = local(library, sha)
    if have:
        return have
    base = _check_base(base)
    index = json.loads(_get(base, "packs.json", MAX_JSON_BYTES))
    if index.get("format") != FORMAT_INDEX:
        raise PackError("packs.json at %s is not an %s index" % (base, FORMAT_INDEX))
    rows = [p for p in index.get("packs", []) if PACK_RE.match(str(p.get("pack", "")))]
    if pack is not None:
        rows = [p for p in rows if p["pack"] == pack or re.fullmatch(re.escape(pack) + r"-\d+", p["pack"])]
    for row in rows:
        meta = json.loads(_get(base, "pack-%s.json" % row["pack"], MAX_JSON_BYTES))
        if not any(o.get("sha256") == sha for o in meta.get("objects", [])):
            continue
        if int(row.get("bytes", 0)) > MAX_PACK_BYTES:
            raise PackError("pack-%s.zip is %s bytes, over the %d-byte limit" % (row["pack"], row["bytes"], MAX_PACK_BYTES))
        _store(library, _get(base, "pack-%s.zip" % row["pack"], MAX_PACK_BYTES), row)
        have = local(library, sha)
        if have:
            return have
        raise PackError("pack-%s.zip lists %s but holds no object that hashes to it" % (row["pack"], sha))
    raise PackError("no pack%s at %s lists %s" % (" " + pack if pack else "", base, sha))


# ---------------------------------------------------------------- CLI

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="asset_packs.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="write the release packs of this kit's catalogue")
    b.add_argument("--out", required=True, type=Path)
    b.add_argument("--release", help="release tag (default v<kit/VERSION.json kit_version>)")
    b.add_argument("--max-mb", type=float, default=MAX_PACK_BYTES / (1 << 20))
    b.add_argument("--catalog", type=Path, default=refs.CATALOG)
    f = sub.add_parser("fetch", help="get one catalogue object by sha256 into the local library")
    f.add_argument("sha256")
    f.add_argument("--pack")
    f.add_argument("--base", help="release download URL (default the public kit release of this kit's version)")
    f.add_argument("--library", type=Path, default=None)
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 2
    try:
        if a.cmd == "build":
            index = build(refs.load(a.catalog), a.out, a.release or refs.release_tag(),
                          max_bytes=int(a.max_mb * (1 << 20)))
            for p in index["packs"]:
                print("%-40s %4d objects %10d bytes  %s" % (p["file"], p["objects"], p["bytes"], p["sha256"]))
            print("%d packs, %d bytes -> %s" % (len(index["packs"]), sum(p["bytes"] for p in index["packs"]), a.out))
        else:
            path = fetch(a.sha256, a.base or default_base(refs.release_tag()), a.library or default_library(), a.pack)
            print(path)
    except (PackError, OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        print("ERROR %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
