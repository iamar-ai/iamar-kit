#!/usr/bin/env python3
"""Catalogue references: a world uses a public catalogue object by hash instead of carrying it (PUB16, an internal task).

  python3 kit/catalog/refs.py ref <world folder> <catalogue id|name> [--as assets/<name>.glb]
  python3 kit/catalog/refs.py check <world folder> [--json]

`ref` writes a `manifest.reused` record whose source is the public kit release
(`{"kind": "catalog", "repo": "iamar-ai/iamar-kit", "release": "v<kit version>", "pack": ..., "id": ...}`)
and adds the `catalog-packs` feature, so a browser that cannot fetch packs refuses the world
with a clear reason instead of showing a hole. Nothing is copied: the browser fetches the pack
once from the release, checks every object against its sha256 and shares it across worlds
(docs/CATALOG_PACKS.md).

`check` is the package-step gate (`iamar-world package` and `pack` run it first when Python is
there): every catalogue reference must name an object of this kit's catalogue with the same
sha256 and size, this kit's own release tag, a cleared licence (no `licence pending`), a
provenance that the public export does not withhold (`generative:*`), `reuse: reusable`, the
same licence and author and the public repo; the world must not also carry the file. Catalogue
objects that were copied instead (`assets use`) must still hash to their entry and keep the credit `assets use` wrote.
Exit 0 clean, 1 on any ERROR, 2 on bad arguments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
CATALOG = HERE / "catalog.json"
PROVENANCE = HERE / "provenance.json"
VERSION = KIT / "VERSION.json"
EXPORT_RULES = KIT / "export" / "rules.json"
LICENCE_ROWS = KIT / "inventory" / "licences.json"
PUBLIC_REPO = "iamar-ai/iamar-kit"
FEATURE = "catalog-packs"
RELEASE_RE = re.compile(r"^v\d+\.\d+\.\d+$")
PATH_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}$")
CREDIT_PREFIX = "iamar kit catalogue "


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pack_slug(e: dict) -> str:
    """The release pack an entry ships in: its catalogue pack name as a slug ("iamar city" -> iamar-city)."""
    return re.sub(r"[^a-z0-9]+", "-", str(e["source"].get("pack") or e["source"].get("origin") or "")).strip("-")


def release_tag(version_path: Path = VERSION) -> str:
    return "v" + str(load(version_path)["kit_version"])


def provenance_rows(path: Path = PROVENANCE) -> dict:
    return load(path).get("rows", {}) if path.is_file() else {}


_rules_cache: list = []


def export_rules() -> dict | None:
    """kit/export/rules.json with kit/inventory/licences.json rows under "_licence_rows", or None in
    the public copy, which ships neither (everything in it already passed the export)."""
    if not _rules_cache:
        rules = load(EXPORT_RULES) if EXPORT_RULES.is_file() else None
        if rules is not None:
            rows = load(LICENCE_ROWS).get("rows", []) if LICENCE_ROWS.is_file() else []
            rules["_licence_rows"] = {r["id"]: r for r in rows}
        _rules_cache.append(rules)
    return _rules_cache[0]


def _glob(path: str, pattern: str) -> bool:
    """tools/export_public.py glob_match: ** spans folders and a trailing / means the whole folder."""
    if pattern.endswith("/"):
        return path.startswith(pattern)
    rx = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.fullmatch(rx, path) is not None


def _first(path: str, items: list) -> dict | str | None:
    return next((it for it in items if _glob(path, it["glob"] if isinstance(it, dict) else it)), None)


def export_refusal(e: dict, rules: dict | None) -> str | None:
    """Why tools/export_public.py would withhold `e`'s file from the public repo (an internal task): an excluded
    or not include-listed path, or a licence outside shippable_licences. None when it ships."""
    if not rules:
        return None
    path = e["source"]["file"]
    ex = _first(path, rules.get("exclude", []))
    if ex:
        return "the public export excludes %s (%s)" % (path, ex.get("reason", ""))
    if not _first(path, rules.get("include", [])):
        return "the public export does not allow-list %s" % path
    ship = rules.get("shippable_licences", [])
    rule = _first(path, rules.get("asset_licences", []))
    if rule and "licence_row" in rule:
        row = rules.get("_licence_rows", {}).get(rule["licence_row"])
        lic, ok = (row["licence"], bool(row.get("shippable"))) if row else (rule["licence_row"], False)
    elif rule:
        lic, ok = rule["licence"], rule["licence"] in ship
    else:
        lic = e.get("licence") or ""
        ok = lic in ship
    if not ok:
        return "its licence %r is not one the public export ships (%s); copy it with `iamar-world assets use` instead" % (
            lic, ", ".join(ship))
    return None


def refusal(e: dict, prov: dict, rules: dict | None | bool = True) -> str | None:
    """Why `e` cannot be referenced from the public release, or None when it can. `rules` are the
    export rules (default: this kit's, export_rules()); None skips the export gate."""
    src = e.get("source", {})
    if src.get("origin") == "builtin":
        return "a built-in object: reference it with `iamar-world assets use` (source kind builtin), not from a pack"
    if e.get("kind") != "model" or not src.get("sha256") or not src.get("file"):
        return "not a single model file (creatures and generators have their own scene.json entries)"
    if e.get("reuse") != "reusable":
        return "locked: %s" % e.get("reuse")
    if "pending" in str(e.get("licence", "")).lower():
        return "its licence is not cleared yet (%s); copy it with `iamar-world assets use` instead" % e["licence"]
    made = str(prov.get(src["file"], {}).get("made_by", ""))
    if made.startswith("generative:"):
        return "made with a generative model (%s), which the public export withholds" % made
    if "(manifest.json tiers lists" in str(e.get("use", "")):
        return "it has tier variants; copy it with `iamar-world assets use` so the tier files come along"
    return export_refusal(e, export_rules() if rules is True else rules)


def find(cat: dict, key: str) -> dict | None:
    k = key.strip().lower()
    for e in cat["entries"]:
        if k == e["id"].lower() or k == e["name"].lower():
            return e
    pre = [e for e in cat["entries"] if len(k) >= 4 and e["id"].lower().startswith(k)]
    return pre[0] if len(pre) == 1 else None


def record(e: dict, path: str, release: str) -> dict:
    src = e["source"]
    return {"path": path, "sha256": src["sha256"], "bytes": int(e["bytes"]),
            "source": {"kind": "catalog", "repo": PUBLIC_REPO, "release": release, "pack": pack_slug(e),
                       "id": e["id"], "file": src["file"]},
            "license": e["licence"], "author": e.get("attribution") or "iamar"}


def ref(world: Path, key: str, as_path: str | None, cat: dict | None = None, prov: dict | None = None,
        release: str | None = None) -> int:
    cat = load(CATALOG) if cat is None else cat
    prov = provenance_rows() if prov is None else prov
    e = find(cat, key)
    if e is None:
        print("ERROR %s is not in the catalogue (iamar-world assets search <words>)" % key)
        return 1
    why = refusal(e, prov)
    if why:
        print("ERROR %s cannot be referenced: %s" % (e["name"], why))
        return 1
    mp = world / "manifest.json"
    if not mp.is_file():
        print("ERROR no manifest.json in %s (make the world first: iamar-world new)" % world)
        return 1
    ext = Path(e["source"]["file"]).suffix
    path = as_path or "assets/%s%s" % (re.sub(r"[^a-z0-9_]+", "_", e["name"].lower()).strip("_") or e["id"], ext)
    if not PATH_RE.match(path) or ".." in path or "//" in path or not path.endswith(ext):
        print("ERROR --as must be a path like assets/<name>%s (letters, digits, _ . / - only)" % ext)
        return 2
    if (world / path).exists():
        print("ERROR %s is a file in the world; a referenced object must not also be carried (pick another --as)" % path)
        return 1
    man = load(mp)
    reused = man.get("reused", [])
    if not isinstance(reused, list):
        print("ERROR manifest.json reused is not a list; fix it by hand first")
        return 1
    if any(isinstance(r, dict) and r.get("path") == path and r.get("sha256") != e["source"]["sha256"] for r in reused):
        print("ERROR %s already references another object; pick another --as path" % path)
        return 1
    rec = record(e, path, release or release_tag())
    man["reused"] = [r for r in reused if not (isinstance(r, dict) and r.get("path") == path)] + [rec]
    feats = man.get("features", [])
    if isinstance(feats, list) and FEATURE not in feats:
        man["features"] = feats + [FEATURE]
    mp.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print("REFERENCED %s as %s (0 bytes in your package; visitors fetch pack %s of %s %s once, %d bytes, "
          "checked by sha256; licence: %s)" % (e["name"], path, rec["source"]["pack"], PUBLIC_REPO,
                                               rec["source"]["release"], rec["bytes"], e["licence"]))
    print("WARN the world now needs feature %s: browsers without catalogue packs refuse it; "
          "use `iamar-world assets use` to carry the file instead" % FEATURE)
    print("THEN scene.json objects: {\"asset\": \"%s\", \"position\": [x, 0, z]}" % path)
    return 0


def check(world: Path, cat: dict | None = None, prov: dict | None = None, release: str | None = None) -> list[str]:
    """ERROR lines for the world's catalogue references and catalogue copies ([] when clean).

    A reference must name `release` (default: this kit's release_tag()): no shipped index lists which
    other releases hold an object, so any other tag could name a release that does not exist."""
    mp = world / "manifest.json"
    if not mp.is_file():
        return ["no manifest.json in %s" % world]
    try:
        man = load(mp)
    except ValueError as ex:
        return ["manifest.json is not JSON (%s)" % ex]
    if not isinstance(man, dict):
        return ["manifest.json is not an object"]
    cat = load(CATALOG) if cat is None else cat
    prov = provenance_rows() if prov is None else prov
    release = release_tag() if release is None else release
    by_id = {e["id"]: e for e in cat["entries"]}
    errs: list[str] = []
    refs = [r for r in man.get("reused", []) if isinstance(r, dict)
            and isinstance(r.get("source"), dict) and r["source"].get("kind") == "catalog"] \
        if isinstance(man.get("reused"), list) else []
    seen: set[str] = set()
    for r in refs:
        p, s = str(r.get("path", "")), r["source"]
        tag = "reused %s" % (p or "<no path>")
        safe = bool(PATH_RE.match(p)) and ".." not in p and "//" not in p
        if not safe:
            errs.append("%s: path must be a relative path like assets/<name>.glb" % tag)
        if p in seen:
            errs.append("%s: listed twice" % tag)
        seen.add(p)
        if safe and (world / p).exists():   # an unsafe path is never probed on the host disk
            errs.append("%s: the package also carries this file; delete it or drop the reference" % tag)
        if s.get("repo") != PUBLIC_REPO:
            errs.append("%s: source.repo must be %s (got %r)" % (tag, PUBLIC_REPO, s.get("repo")))
        if str(s.get("release", "")) != release:
            errs.append("%s: source.release must be this kit's release %s, the one whose packs hold these objects "
                        "(got %r); rerun `iamar-world assets ref` with this kit" % (tag, release, s.get("release")))
        e = by_id.get(str(s.get("id", "")))
        if e is None:
            errs.append("%s: source.id %r is not in this kit's catalogue" % (tag, s.get("id")))
            continue
        why = refusal(e, prov)
        if why:
            errs.append("%s: %s cannot be referenced: %s" % (tag, e["name"], why))
            continue
        if r.get("sha256") != e["source"]["sha256"]:
            errs.append("%s: sha256 differs from catalogue %s (%s)" % (tag, e["id"], e["source"]["sha256"]))
        if r.get("bytes") != e["bytes"]:
            errs.append("%s: bytes %r differ from catalogue %s (%d)" % (tag, r.get("bytes"), e["id"], e["bytes"]))
        if s.get("pack") != pack_slug(e):
            errs.append("%s: source.pack must be %s" % (tag, pack_slug(e)))
        if r.get("license") != e["licence"]:
            errs.append("%s: license must be the catalogue's %r (attribution)" % (tag, e["licence"]))
        if r.get("author") != (e.get("attribution") or "iamar"):
            errs.append("%s: author must be the catalogue's %r (attribution)" % (tag, e.get("attribution") or "iamar"))
    feats = man.get("features", [])
    if refs and not (isinstance(feats, list) and FEATURE in feats):
        errs.append("manifest features must list %s when reused has catalogue references" % FEATURE)
    # Copies made by `assets use`: the credit it wrote must still match the files and the entry.
    for c in man.get("credits", []) if isinstance(man.get("credits"), list) else []:
        if not (isinstance(c, dict) and str(c.get("source", "")).startswith(CREDIT_PREFIX)):
            continue
        cid = str(c["source"])[len(CREDIT_PREFIX):].strip()
        e = by_id.get(cid)
        tag = "credit %s" % cid
        if e is None:
            errs.append("%s: not in this kit's catalogue" % tag)
            continue
        if c.get("license") != e["licence"]:
            errs.append("%s: license must be the catalogue's %r" % (tag, e["licence"]))
        files = c.get("files") if isinstance(c.get("files"), list) else []
        first = files[0] if files and isinstance(files[0], str) else None   # `assets use` lists the object first
        if first and PATH_RE.match(first) and ".." not in first and (world / first).is_file() \
                and e["source"].get("sha256") and sha256_file(world / first) != e["source"]["sha256"]:
            errs.append("%s: %s no longer hashes to the catalogue object (edited copies are your own work: "
                        "drop this credit and credit your change)" % (tag, first))
    return errs


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="refs.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ref", help="reference a catalogue object from the public kit release (nothing copied)")
    r.add_argument("world", type=Path)
    r.add_argument("key")
    r.add_argument("--as", dest="as_path")
    c = sub.add_parser("check", help="package-step gate for catalogue references and copies")
    c.add_argument("world", type=Path)
    c.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "ref":
        return ref(a.world, a.key, a.as_path)
    errs = check(a.world)
    if a.json:
        print(json.dumps({"ok": not errs, "errors": errs}))
    else:
        for e in errs:
            print("ERROR " + e)
        print("REFS_OK" if not errs else "REFS_FAILED %d" % len(errs))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
