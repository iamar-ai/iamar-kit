#!/usr/bin/env python3
"""Catalogue release packs: build them, and fetch catalogue objects by hash (PUB7, an internal task).

  python3 kit/catalog/packs.py build <out dir> [--release vX.Y.Z] [--max-mb 64]
  python3 kit/catalog/packs.py fetch <world folder> [--cache DIR] [--json]
  python3 kit/catalog/packs.py fetch-pack <release> <pack> [--cache DIR]

The public git repo stays lean: big catalogue objects travel as release packs attached to the
GitHub release of iamar-ai/iamar-kit (docs/CATALOG_PACKS.md section 3), not as git files or LFS.

`build` is the kit's one release-pack builder (tools/asset_packs.py build calls `write_packs`
too, an internal task). Per catalogue pack (refs.pack_slug) it writes `pack-<pack>.zip` holding only
`objects/<sha256>.<ext>` for every entry `refs.refusal()` accepts (once per pack; that includes the public
export's own gate, so an entry tools/export_public.py withholds for its licence or path never ships), `pack-<pack>.json`
(its index) and one `packs.json` whose rows are `pack`, `file` (the zip), `index` (the pack json),
`sha256`, `bytes` and `objects`. A pack whose zip could pass --max-mb (at most 64, what fetch
accepts; zip headers and deflate growth counted) is split into `<pack>-1`, `<pack>-2`, ... (objects
in sha256 order); one object that cannot fit fails the build. Zips are reproducible (sorted
entries, fixed time and mode). Attaching them to the release is the release step's job (PUB16b,
an internal task).

`fetch` (`iamar-world assets fetch <world>`) makes every `manifest.reused` catalogue reference of a
world available on this computer: a reference is found in this kit's own tree, then in the shared
catalogue cache (`objects/<sha256>.<ext>`, one copy per computer); for the misses each
(release, pack) is downloaded once from the fixed release URL (or the hub mirror when GitHub
fails). The world names no URL: repo, release and pack are matched against fixed patterns first.
Downloads are HTTPS, capped at 64 MB, and may redirect only to GitHub's and the hub's hosts. Only
zip entries named `objects/<64 hex>.<glb|gltf|ogg|png>` whose bytes hash to that name are kept;
nothing is extracted by path. Exit 0 when every reference is present, 1 when one is missing
(the reason is printed), 2 on bad arguments.

Tests: IAMAR_CATALOG_BASE=http://127.0.0.1:<port> replaces the release URL, accepted only for a
loopback host (kit/tests/catalog/packs_test.py).
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
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import refs  # noqa: E402

PUBLIC_REPO = refs.PUBLIC_REPO
RELEASE_RE = refs.RELEASE_RE
PACK_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ENTRY_RE = re.compile(r"^objects/([0-9a-f]{64})\.(glb|gltf|ogg|png)$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
EXTS = ("glb", "gltf", "ogg", "png")
MAX_PACK_BYTES = 64 << 20
MAX_ENTRIES = 20000
GITHUB = "https://github.com/%s/releases/download/%s/pack-%s.zip"
MIRROR = "https://hub.vessences.com/catalog/%s/pack-%s.zip"
REDIRECT_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
                  "hub.vessences.com")
LOOPBACK = ("127.0.0.1", "localhost", "::1")
TIMEOUT = 60
ZIP_ENTRY_OVERHEAD = 512  # local + central header with a 73-byte name and the end record, with room to spare


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def cache_dir() -> Path:
    """The shared catalogue cache: IAMAR_CATALOG_CACHE, else the OS cache folder."""
    c = os.environ.get("IAMAR_CATALOG_CACHE")
    if c:
        return Path(c)
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "iamar" / "catalog_cache"


# ---------------------------------------------------------------- build

def pack_entries(cat: dict, prov: dict, root: Path, rules=True) -> tuple[dict, list[str]]:
    """{pack slug: [(sha256, ext, entry, file path), ...]} of every referenceable entry, and problems."""
    packs: dict[str, list] = {}
    problems: list[str] = []
    for e in cat["entries"]:
        if refs.refusal(e, prov, rules):
            continue
        src = e["source"]
        ext = Path(src["file"]).suffix.lstrip(".").lower()
        f = root / src["file"]
        if ext not in EXTS:
            problems.append("%s: %s is not a pack file type (%s)" % (e["id"], src["file"], "/".join(EXTS)))
            continue
        if not f.is_file():
            problems.append("%s: %s is missing" % (e["id"], src["file"]))
            continue
        if refs.sha256_file(f) != src["sha256"]:
            problems.append("%s: %s no longer matches its catalogue sha256" % (e["id"], src["file"]))
            continue
        slug = refs.pack_slug(e)
        if not PACK_RE.match(slug):
            problems.append("%s: pack name %r is not a slug" % (e["id"], slug))
            continue
        packs.setdefault(slug, []).append((src["sha256"], ext, e, f))
    return packs, problems


ZIP_TIME = (2020, 1, 1, 0, 0, 0)


class PackError(ValueError):
    """A release-pack build that must not produce files (bad tag, limit, object over the limit)."""


def zip_cost(n: int) -> int:
    """Most bytes an n-byte object can add to a pack zip: deflate grows incompressible data by 5
    bytes per 16 KiB block, plus the entry's headers."""
    return n + 5 * (n // 16384 + 1) + ZIP_ENTRY_OVERHEAD


def split(objs: list, max_bytes: int) -> list[list]:
    """Objects in sha256 order, cut into parts whose zip stays within max_bytes."""
    objs = sorted({o[0]: o for o in objs}.values(), key=lambda o: o[0])
    parts: list[list] = [[]]
    size = 0
    for o in objs:
        cost = zip_cost(o[3].stat().st_size)
        if cost > max_bytes:
            raise PackError("%s (%s) is %d bytes, over the %d-byte pack limit" % (
                o[2]["id"], o[2]["source"]["file"], o[3].stat().st_size, max_bytes))
        if parts[-1] and size + cost > max_bytes:
            parts.append([])
            size = 0
        parts[-1].append(o)
        size += cost
    return [p for p in parts if p]


def write_packs(out: Path, release: str, max_bytes: int = MAX_PACK_BYTES, cat: dict | None = None,
                prov: dict | None = None, root: Path | None = None, say=None, rules=True) -> tuple[dict, list[str]]:
    """Write pack-<pack>.zip/.json per pack and packs.json into `out`.

    Returns (packs.json data, problems: entries left out). Raises PackError before writing
    anything when the release tag or the limit is wrong or one object cannot fit in a pack.
    The one builder of the release packs: tools/asset_packs.py build calls it too (an internal task)."""
    if not RELEASE_RE.fullmatch(release or ""):
        raise PackError("release %r must look like v1.2.3" % release)
    if max_bytes > MAX_PACK_BYTES:
        raise PackError("pack limit %d bytes is over the %d bytes fetch accepts" % (max_bytes, MAX_PACK_BYTES))
    cat = refs.load(refs.CATALOG) if cat is None else cat
    prov = refs.provenance_rows() if prov is None else prov
    root = refs.KIT.parent if root is None else root
    packs, problems = pack_entries(cat, prov, root, rules)
    plan = [(slug, split(packs[slug], max_bytes)) for slug in sorted(packs)]
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for slug, parts in plan:
        for i, part in enumerate(parts, 1):
            name = slug if len(parts) == 1 else "%s-%d" % (slug, i)
            zp = out / ("pack-%s.zip" % name)
            with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
                for sha, ext, e, f in part:
                    data = f.read_bytes()
                    if sha256_bytes(data) != sha:
                        raise PackError("%s: %s no longer matches its catalogue sha256" % (e["id"], e["source"]["file"]))
                    zi = zipfile.ZipInfo("objects/%s.%s" % (sha, ext), date_time=ZIP_TIME)
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zi.external_attr = 0o644 << 16
                    z.writestr(zi, data)
            objects = [{"sha256": sha, "bytes": f.stat().st_size, "ext": ext, "id": e["id"],
                        "license": e["licence"], "author": e.get("attribution") or "iamar"}
                       for sha, ext, e, f in part]
            (out / ("pack-%s.json" % name)).write_text(json.dumps(
                {"format": "iamar-catalog-pack", "version": 1, "pack": name, "release": release,
                 "objects": objects}, indent=1) + "\n", encoding="utf-8")
            data = zp.read_bytes()
            if len(data) > max_bytes:
                raise PackError("%s is %d bytes, over the %d-byte pack limit" % (zp.name, len(data), max_bytes))
            index.append({"pack": name, "file": zp.name, "index": "pack-%s.json" % name,
                          "sha256": sha256_bytes(data), "bytes": len(data), "objects": len(objects)})
        if len(parts) > 1 and say:
            say("NOTE %s split into %d parts: references must name the part (%s-1 ...)" % (slug, len(parts), slug))
    doc = {"format": "iamar-catalog-packs", "version": 1, "repo": PUBLIC_REPO, "release": release, "packs": index}
    (out / "packs.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return doc, problems


def build(out: Path, release: str, max_bytes: int = MAX_PACK_BYTES, cat: dict | None = None,
          prov: dict | None = None, root: Path | None = None, rules=True) -> int:
    if not RELEASE_RE.fullmatch(release or "") or max_bytes > MAX_PACK_BYTES:
        print("ERROR " + ("release %r must look like v1.2.3" % release if not RELEASE_RE.fullmatch(release or "")
                          else "--max-mb is over the %d MB fetch accepts" % (MAX_PACK_BYTES >> 20)))
        return 2
    try:
        doc, problems = write_packs(out, release, max_bytes, cat, prov, root, say=print, rules=rules)
    except PackError as e:
        print("ERROR %s" % e)
        return 1
    for p in problems:
        print("ERROR " + p)
    index = doc["packs"]
    total = sum(p["bytes"] for p in index)
    print("PACKS %d  OBJECTS %d  MB %.1f  -> %s" % (len(index), sum(p["objects"] for p in index),
                                                  total / 1048576, out))
    return 1 if problems else 0


# ---------------------------------------------------------------- fetch

class _Redirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to HTTPS on GitHub's or the hub's hosts (loopback while testing)."""

    def __init__(self, test: bool):
        self.test = test

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlsplit(newurl)
        ok = (u.scheme == "https" and u.hostname in REDIRECT_HOSTS) or \
             (self.test and u.scheme in ("http", "https") and u.hostname in LOOPBACK)
        if not ok:
            raise urllib.error.URLError("redirect off the allowed hosts refused: %s" % u.hostname)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def test_base() -> str | None:
    b = os.environ.get("IAMAR_CATALOG_BASE", "").rstrip("/")
    if not b:
        return None
    u = urllib.parse.urlsplit(b)
    if u.scheme in ("http", "https") and u.hostname in LOOPBACK:
        return b
    print("WARN IAMAR_CATALOG_BASE ignored: only a loopback test server may replace the release URL")
    return None


def pack_urls(release: str, pack: str, repo: str = PUBLIC_REPO) -> list[str]:
    """Where (release, pack) may come from; [] when a name does not match its fixed pattern."""
    if repo != PUBLIC_REPO or not RELEASE_RE.fullmatch(release or "") or not PACK_RE.fullmatch(pack or "") \
            or len(pack) > 64:
        return []
    base = test_base()
    if base:
        return ["%s/%s/pack-%s.zip" % (base, release, pack)]
    return [GITHUB % (PUBLIC_REPO, release, pack), MIRROR % (release, pack)]


def download(url: str, cap: int | None = None) -> bytes:
    cap = MAX_PACK_BYTES if cap is None else cap
    test = test_base() is not None
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" and not (test and u.hostname in LOOPBACK):
        raise ValueError("not HTTPS: %s" % url)
    opener = urllib.request.build_opener(_Redirects(test))
    req = urllib.request.Request(url, headers={"User-Agent": "iamar-kit-packs/1"})
    with opener.open(req, timeout=TIMEOUT) as r:
        n = r.headers.get("Content-Length")
        if n and n.isdigit() and int(n) > cap:
            raise ValueError("pack is %d bytes, over the %d MB cap" % (int(n), cap >> 20))
        buf = io.BytesIO()
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            buf.write(chunk)
            if buf.tell() > cap:
                raise ValueError("pack is over the %d MB cap" % (cap >> 20))
        return buf.getvalue()


def store(data: bytes, cache: Path, cap: int | None = None) -> tuple[list[str], list[str]]:
    """Keep every verified object of a pack zip in cache/objects. Returns (stored sha256s, rejects)."""
    cap = MAX_PACK_BYTES if cap is None else cap
    kept: list[str] = []
    rejects: list[str] = []
    objdir = cache / "objects"
    objdir.mkdir(parents=True, exist_ok=True)
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return [], ["not a zip file"]
    with z:
        infos = z.infolist()
        if len(infos) > MAX_ENTRIES:
            return [], ["%d entries, over the %d limit" % (len(infos), MAX_ENTRIES)]
        total = 0
        for zi in infos:
            m = ENTRY_RE.fullmatch(zi.filename)
            if not m or zi.is_dir():
                rejects.append("%s: not objects/<sha256>.<%s>" % (zi.filename, "|".join(EXTS)))
                continue
            total += zi.file_size
            if zi.file_size > cap or total > 4 * cap:
                rejects.append("%s: too large unpacked" % zi.filename)
                continue
            with z.open(zi) as f:
                b = f.read(cap + 1)
            if len(b) > cap or sha256_bytes(b) != m.group(1):
                rejects.append("%s: bytes do not hash to the name" % zi.filename)
                continue
            dest = objdir / ("%s.%s" % m.groups())
            if not dest.is_file() or refs.sha256_file(dest) != m.group(1):
                fd, tmp = tempfile.mkstemp(dir=objdir, suffix=".part")
                with os.fdopen(fd, "wb") as out:
                    out.write(b)
                os.replace(tmp, dest)
            kept.append(m.group(1))
    return kept, rejects


def fetch_pack(release: str, pack: str, cache: Path, repo: str = PUBLIC_REPO) -> tuple[list[str], str]:
    """Download (release, pack) once and keep its verified objects. ([sha256...], "" or why it failed)."""
    urls = pack_urls(release, pack, repo)
    if not urls:
        return [], "refused: repo %r release %r pack %r do not match the public kit release patterns" % (
            repo, release, pack)
    why = []
    for url in urls:
        try:
            data = download(url)
        except (OSError, ValueError, urllib.error.URLError) as e:
            why.append("%s: %s" % (urllib.parse.urlsplit(url).hostname, getattr(e, "reason", e)))
            continue
        kept, rejects = store(data, cache)
        for r in rejects:
            print("WARN pack-%s.zip %s (skipped)" % (pack, r))
        return kept, ""
    return [], "; ".join(why) or "no source"


def find_local(sha: str, ext: str, cache: Path, by_sha: dict, root: Path) -> Path | None:
    """The object in this kit's tree (checked against its hash) or in the shared cache."""
    e = by_sha.get(sha)
    if e:
        f = root / e["source"]["file"]
        if f.is_file() and refs.sha256_file(f) == sha:
            return f
    c = cache / "objects" / ("%s.%s" % (sha, ext))
    if c.is_file() and refs.sha256_file(c) == sha:
        return c
    return None


def fetch_world(world: Path, cache: Path, cat: dict | None = None, root: Path | None = None,
                as_json: bool = False) -> int:
    mp = world / "manifest.json"
    if not mp.is_file():
        print("ERROR no manifest.json in %s" % world)
        return 2
    try:
        man = json.loads(mp.read_text(encoding="utf-8"))
    except ValueError as e:
        print("ERROR manifest.json is not JSON: %s" % e)
        return 2
    cat = refs.load(refs.CATALOG) if cat is None else cat
    root = refs.KIT.parent if root is None else root
    by_sha = {e["source"]["sha256"]: e for e in cat["entries"] if e.get("source", {}).get("sha256")}
    wanted = []
    for r in man.get("reused", []) if isinstance(man.get("reused"), list) else []:
        if not isinstance(r, dict) or not isinstance(r.get("source"), dict) or r["source"].get("kind") != "catalog":
            continue
        sha = str(r.get("sha256", "")).lower()
        ext = Path(str(r.get("path", ""))).suffix.lstrip(".").lower()
        wanted.append((r, sha, ext))
    rows = []
    missing: dict[tuple, list] = {}
    for r, sha, ext in wanted:
        if not SHA_RE.match(sha) or ext not in EXTS:
            rows.append({"path": r.get("path"), "sha256": sha, "status": "error",
                         "why": "sha256 must be 64 hex and the path a .glb/.gltf/.ogg/.png"})
            continue
        f = find_local(sha, ext, cache, by_sha, root)
        if f:
            rows.append({"path": r["path"], "sha256": sha, "status": "present", "file": str(f)})
        else:
            s = r["source"]
            missing.setdefault((str(s.get("repo")), str(s.get("release")), str(s.get("pack"))), []).append((r, sha, ext))
    for (repo, release, pack), items in sorted(missing.items()):
        _kept, why = fetch_pack(release, pack, cache, repo)
        for r, sha, ext in items:
            f = find_local(sha, ext, cache, by_sha, root)
            if f:
                rows.append({"path": r["path"], "sha256": sha, "status": "fetched", "file": str(f),
                             "pack": pack, "release": release})
            else:
                rows.append({"path": r["path"], "sha256": sha, "status": "missing", "pack": pack, "release": release,
                             "why": why or "pack %s of %s %s does not hold an object with this sha256" % (
                                 pack, repo, release)})
    bad = [x for x in rows if x["status"] in ("missing", "error")]
    if as_json:
        print(json.dumps({"world": str(world), "cache": str(cache), "refs": rows, "ok": not bad}, indent=1))
    else:
        for x in rows:
            if x["status"] in ("missing", "error"):
                print("ERROR %s: %s" % (x["path"], x["why"]))
            else:
                print("%-7s %s" % (x["status"].upper(), x["path"]))
        print("REFS %d  PRESENT %d  FETCHED %d  MISSING %d  cache %s" % (
            len(rows), sum(x["status"] == "present" for x in rows), sum(x["status"] == "fetched" for x in rows),
            len(bad), cache))
        print("NEXT %s" % ("fix the references above (iamar-world assets ref <world> <id>) or go online"
                           if bad else "iamar-world preview %s" % world))
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="iamar-world assets", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the release packs of this kit's catalogue")
    b.add_argument("out")
    b.add_argument("--release")
    b.add_argument("--max-mb", type=int, default=MAX_PACK_BYTES >> 20)
    f = sub.add_parser("fetch", help="make a world's catalogue references available on this computer")
    f.add_argument("world")
    f.add_argument("--cache")
    f.add_argument("--json", action="store_true")
    p = sub.add_parser("fetch-pack", help="download one release pack into the cache")
    p.add_argument("release")
    p.add_argument("pack")
    p.add_argument("--cache")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        return build(Path(a.out), a.release or refs.release_tag(), max(1, a.max_mb) << 20)
    cache = Path(a.cache) if a.cache else cache_dir()
    if a.cmd == "fetch":
        return fetch_world(Path(a.world), cache, as_json=a.json)
    kept, why = fetch_pack(a.release, a.pack, cache)
    if why:
        print("ERROR pack-%s.zip of %s: %s" % (a.pack, a.release, why))
        return 1
    print("STORED %d objects in %s" % (len(kept), cache / "objects"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
