#!/usr/bin/env python3
"""The iamar object catalogue: build catalog.json + CATALOG.md, check them, search them.

  python3 kit/catalog/catalog.py build                 regenerate catalog.json and CATALOG.md
  python3 kit/catalog/catalog.py check                 fail if they are stale or an entry is malformed
  python3 kit/catalog/catalog.py search <words...> [--category C] [--style S] [--limit N] [--json]
  python3 kit/catalog/catalog.py show <id|name>         one entry (exit 3 when unknown)
  python3 kit/catalog/catalog.py use <world folder> <id|name> [--as assets/<name>.glb]
                                                       put a catalogue object into a world (exit 3: not a
                                                       kit file, so the browser's `assets use` takes it)

`iamar-world assets search <words>` runs the search. Sources (never edit catalog.json by hand):
  sources/builtin_assets.json   the browser's built-in CC0 models (copy of the iamar browser source (not public)
                                scripts/worlds/builtin_assets.json; refresh with build --builtin <path>)
  sources/procedural.json       creatures built by kind and the town's procedural buildings
  sources/city_models.json      the city's own props, trees and creatures as glTF in kit/catalog/assets/
                                (assets/import_city_models.py copies them from the iamar-models mesh archive (not public))
  sources/insects.json          butterflies, bumblebee, dragonfly with their wing clips, in
                                kit/catalog/assets/creatures/insects/ (assets/export_insects.gd, insects.py)
  sources/harbour.json          boats, bollard, harbour bell, net pile, gull and the sea, bell and gull
                                sounds, in kit/catalog/assets/harbour/ (assets/export_harbour.gd, harbour.py)
  sources/coastal.json          beach and modern-home objects (palm, dock, umbrella, lounger, towel, shells,
                                coral, kelp, sofa, kitchen counter, bathtub, wardrobe, rug) in
                                kit/catalog/assets/coastal/ (assets/export_coastal.gd, coastal.py)
  sources/city_pieces.json      the city's furniture, crops and flora as single pieces in kit/catalog/assets/
                                (assets/export_city_pieces.gd, import_city_models.py --pieces)
  sources/city_buildings.json   houses and shops per city quarter and reusable landmarks, re-centred, in
                                kit/catalog/assets/{buildings,landmarks}/ (assets/import_city_buildings.py)
  sources/city_buildings_closed.json  closed variants of the open-sided houses, buildings/*_closed.glb
                                (assets/close_open_sides.py); the open original's description names its variant
  sources/city_interiors.json   room interiors, one per building purpose, in kit/catalog/assets/interiors/,
                                moved by their shell building's offset (assets/import_city_interiors.py);
                                a room and its catalogued shell name each other and pair
  vocabulary.json               categories, the words that find them, filing rules, placement hints
  overrides.json                hand-written fields per id (descriptions, synonyms, tags, behaviours...)
Python 3.8+, standard library only.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
# an exported (public) kit carries EXPORT_MANIFEST.json at its root; the private source repo never does
EXPORTED = (KIT.parent / "EXPORT_MANIFEST.json").is_file()
CATALOG = HERE / "catalog.json"
CATALOG_MD = HERE / "CATALOG.md"
BUILTIN = HERE / "sources" / "builtin_assets.json"
PROCEDURAL = HERE / "sources" / "procedural.json"
CITY = HERE / "sources" / "city_models.json"
INSECTS = HERE / "sources" / "insects.json"
PIECES = HERE / "sources" / "city_pieces.json"
BUILDINGS = HERE / "sources" / "city_buildings.json"
CLOSED = HERE / "sources" / "city_buildings_closed.json"
INTERIORS = HERE / "sources" / "city_interiors.json"
MOUNTS = HERE / "sources" / "city_mounts.json"
HARBOUR = HERE / "sources" / "harbour.json"
COASTAL = HERE / "sources" / "coastal.json"
ASSETS = HERE / "assets"
VOCAB = HERE / "vocabulary.json"
OVERRIDES = HERE / "overrides.json"
SCHEMA = HERE / "schema.json"
THUMBS = KIT / "thumbnails"   # in the source repo; a downloaded kit leaves them out unless asked
TURNTABLES = KIT / "turntables"   # 8 views per entry in one strip; shipped like the thumbnails
BUILTIN_COMMIT = "79512407"   # the iamar browser source (not public) commit sources/builtin_assets.json was copied from

PACKS = {   # names as in the iamar browser source (not public) CREDITS.md
    "castle": "Kenney Castle Kit", "town": "Kenney Fantasy Town Kit 2.0", "nature": "Kenney Nature Kit",
    "survival": "Kenney Survival Kit", "village": "Quaternius Medieval Village MegaKit",
    "props": "Quaternius Fantasy Props MegaKit", "naturekit": "Quaternius Stylized Nature MegaKit",
    "hair": "Quaternius Universal Base Characters", "chars": "Quaternius Universal Base Characters",
    "anims": "Quaternius Universal Animation Library",
}
ENTRY_KEYS = None   # filled from schema.json on first use


# ------------------------------------------------------------------ words

def split_words(text: str) -> list[str]:
    """'tree_pineTallA' -> ['tree', 'pine', 'tall', 'a']; 'Roof_RoundTiles_4x8' -> [..., '4x8']."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    text = re.sub(r"([a-zA-Z])(\d)(?!x\d)", r"\1 \2", text)
    return [w for w in re.split(r"[^a-z0-9]+", text.lower()) if w]


def stem(w: str) -> str:
    """Plural to singular, enough for search: horses->horse, benches->bench, berries->berry."""
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("ches", "shes", "xes", "sses")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def terms(text: str) -> set[str]:
    return {stem(w) for w in split_words(text)}


# ------------------------------------------------------------------ build

def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def file_category(rules: list, pack: str, name: str) -> str:
    words = set(split_words(pack + " " + name))
    for cat, keys in rules:
        if not keys or words & set(keys):
            return cat
    return "prop"


def human_name(file: str) -> str:
    base = Path(file).name
    base = re.sub(r"\.(glb|gltf)$", "", base)
    return " ".join(split_words(base))


def _size_text(size) -> str:
    if isinstance(size, list) and len(size) == 3:
        return "%g x %g x %g m" % tuple(size)
    return "size not measured"


def city_entry(r: dict, city: dict, place: dict) -> dict:
    """One city model (sources/city_models.json or sources/insects.json row) as a catalogue entry."""
    if r.get("kind") == "audio":
        return audio_entry(r, city)
    sid = r["sha256"][:16]
    rel = "kit/catalog/assets/" + r["file"]
    as_path = "assets/" + r["file"].split("/")[-1]
    tags = list(r["tags"]) if r.get("tags") else ["iamar city", r["file"].split("/")[0]]
    if r.get("animations"):
        tags.append("animated")
    if r.get("skinned"):
        tags.append("skinned")
    if r.get("physics_body"):
        tags.append("collision shape")
    if r.get("quarter"):
        tags.append(r["style"].split(": ")[-1])
    if r.get("open_sides"):
        tags.append("open side")
    e = {
        "id": sid, "name": r["name"], "kind": "model", "category": r["category"],
        "description": r["description"], "description_source": "written",
        "synonyms": r.get("synonyms", []), "tags": tags,
        "thumbnail": None, "style": r.get("style", "iamar city"), "style_compat": list(r.get("style_compat", [])),
        "size": r.get("size"), "pivot": "bottom-centre" if not r.get("skinned") else None,
        "triangles": dict(r["lods"]) if r.get("lods") else {"lod0": int(r["triangles"])}, "bytes": int(r["bytes"]),
        "textures": ["painted atlas %dx%d (the city's painted look baked, %g px/m)" % (
            r["painted_bake"]["atlas"][0], r["painted_bake"]["atlas"][1], r["painted_bake"]["px_per_m"])]
            if r.get("painted_bake") else None, "collision": r.get("collision"),
        "animations": r.get("animations", []), "behaviours": r.get("behaviours", []),
        "placement": (place.get(r["category"]) or "") + (
            " Place it at scale %g, as the city does (the file is %s m at scale 1)." % (
                r["place_scale"], "x".join("%g" % v for v in r["size"]))
            if r.get("place_scale", 1.0) != 1.0 else ""),
        "pairings": list(r.get("pairings", [])),
        "source": {"origin": r.get("origin", "city"), "pack": r.get("pack", "iamar city"), "file": rel, "sha256": r["sha256"], "cite": r["cite"]},
        "licence": r.get("licence") or city.get("licence", "iamar original work"), "attribution": "iamar",
        "reuse": "reusable",
        "use": ('copy %s, then scene.json objects: {"asset": "%s", "position": [x, 0, z]%s%s%s%s}' % (
            _tier_copies(r, as_path) or "%s to <world folder>/%s" % (rel, as_path), as_path,
            ', "scale": %g' % r["place_scale"] if r.get("place_scale", 1.0) != 1.0 else "",
            ', "collision": "%s"' % r["collision"] if r.get("collision") not in (None, "none") and not r.get("physics_body") else "",
            ', "animation": "%s"' % r["play"] if r.get("play") else "",
            ', "sway": true' if r["category"] == "tree" else "")),   # the shared wind (WindField.adopt_tree)
    }
    if r.get("tier_variants"):   # one file per tier (LODs): their entry ids
        e["tier_variants"] = dict(r["tier_variants"])
    return e


def audio_entry(r: dict, city: dict) -> dict:
    """One sound file (a sources/harbour.json row with kind audio) as a catalogue entry: its use line
    is the scene.json sounds entry (ambient without position, positional with one)."""
    rel = "kit/catalog/assets/" + r["file"]
    as_path = "audio/" + r["file"].split("/")[-1]
    a = r["audio"]
    snd = dict(r["sound"])
    snd["file"] = as_path
    order = ["id", "file", "position", "radius", "loop", "autoplay", "volume_db"]
    body = ", ".join('"%s": %s' % (k, json.dumps(snd[k])) for k in order if k in snd)
    return {
        "id": r["sha256"][:16], "name": r["name"], "kind": "audio", "category": "audio",
        "description": r["description"], "description_source": "written",
        "synonyms": r.get("synonyms", []),
        "tags": ["sound", "ogg vorbis", "mono", "loop" if snd.get("loop") else "one-shot",
                 "positional" if "position" in snd else "ambient"],
        "thumbnail": None, "style": None, "style_compat": [], "size": None, "pivot": None,
        "triangles": {"lod0": 0}, "bytes": int(r["bytes"]), "textures": None, "collision": None,
        "animations": [], "behaviours": r.get("behaviours", []),
        "placement": "%.1f s, mono Ogg Vorbis at %d Hz. %s" % (
            a["seconds"], a["rate"], "Positional: set position where it sounds from; it fades out by radius (m)."
            if "position" in snd else "Ambient: no position, heard everywhere in the world."),
        "pairings": [],
        "source": {"origin": r.get("origin", "kit"), "pack": "iamar kit", "file": rel, "sha256": r["sha256"], "cite": r["cite"]},
        "licence": r.get("licence") or city.get("licence", "iamar original work"), "attribution": "iamar",
        "reuse": "reusable",
        "use": "copy %s to <world folder>/%s, then scene.json sounds: {%s}" % (rel, as_path, body),
    }


def _tier_copies(r: dict, as_path: str) -> str:
    """For a model with one file per tier (LODs): the copy part of its use line. WorldTiers
    reads the low file at the path itself and the finer ones from tiers/<tier>/<path>."""
    tf = r.get("tier_files")
    if not tf:
        return ""
    parts = ["kit/catalog/assets/%s to <world folder>/%s" % (tf[t], as_path if t == "low" else "tiers/%s/%s" % (t, as_path))
             for t in ("low", "medium", "high", "ultra") if t in tf]
    finer = [t for t in ("medium", "high", "ultra") if t in tf]
    return "%s (manifest.json tiers lists %s)" % (", ".join(parts), " and ".join(finer))


def style_compat(e: dict, rules: dict) -> list[str]:
    """C5 tags from vocabulary.json style_rules; overrides.json replaces them per id."""
    if e["category"] in rules.get("neutral_categories", []):
        return ["neutral"]
    src = e.get("source", {})
    if src.get("pack") in rules.get("medieval_packs", []) or src.get("origin") in rules.get("medieval_origins", []):
        return ["iamar-medieval"]
    return ["neutral"]


def build_entries(builtin: dict, procedural: dict, vocab: dict, overrides: dict, city: dict | None = None) -> list[dict]:
    cats = {c["id"]: c for c in vocab["categories"]}
    place = vocab.get("placement", {})
    out = []
    for o in builtin["objects"]:
        parts = o["file"].split("/")
        pack = parts[1] if len(parts) > 2 else ""
        name = human_name(o["file"])
        cat = file_category(vocab["rules"], pack, name)
        sid = o["sha256"][:16]
        packname = PACKS.get(pack, pack)
        thumb = "thumbnails/%s.png" % sid
        e = {
            "id": sid, "name": name, "kind": "model", "category": cat,
            "description": "%s: %s from the %s (%s, %s). %s, %d triangles." % (
                name[:1].upper() + name[1:], cats[cat]["label"], packname, o.get("author", ""), o["license"],
                _size_text(o.get("size")), int(o.get("triangles", 0))),
            "description_source": "generated",
            "synonyms": [], "tags": [pack] + ([cats[cat]["group"]] if cat in cats else []),
            "thumbnail": thumb if (KIT / thumb).is_file() or not THUMBS.is_dir() else None,
            "style_compat": [],
            "size": o.get("size") or None,
            "triangles": {"lod0": int(o.get("triangles", 0))},
            "bytes": int(o.get("bytes", 0)),
            "behaviours": [],
            "placement": place.get(cat),
            "pairings": ["pack:" + pack] if pack else [],
            "source": {"origin": "builtin", "pack": packname, "file": o["file"], "sha256": o["sha256"],
                       "cite": "the iamar browser source (not public) %s scripts/worlds/builtin_assets.json" % BUILTIN_COMMIT},
            "licence": o["license"], "attribution": o.get("author", ""),
            "reuse": "reusable",
            "use": "iamar-world assets use <world folder> %s --as assets/%s.glb" % (sid, "_".join(name.split())),
        }
        out.append(e)
    for c in procedural.get("creatures", []):
        out.append({
            "id": "creature:" + c["kind"], "name": c["name"], "kind": "creature", "category": c["category"],
            "description": c["description"], "description_source": "written",
            "synonyms": c.get("synonyms", []), "tags": ["creature", "animal", "living"],
            "thumbnail": None, "style_compat": [], "size": None,
            "triangles": c.get("triangles", {"lod0": None}), "bytes": 0,
            "behaviours": c.get("behaviours", []),
            "placement": c.get("placement", "In open ground; give it a wander_radius that stays inside fences."),
            "pairings": [],
            "source": {"origin": "creature", "cite": procedural.get("creature_cite", "")},
            "licence": "CC0-1.0", "attribution": "iamar", "reuse": "reusable",
            "use": 'scene.json creatures: {"kind": "%s", "position": [x, 0, z], "count": 3, "wander_radius": 8} '
                   '(and "creatures" in manifest features)' % c["kind"],
        })
    for g in procedural.get("generators", []):
        out.append({
            "id": "generator:" + g["kind"], "name": g["name"], "kind": "generator", "category": "building",
            "description": g["description"], "description_source": "written",
            # its own name and kind are synonyms too, so 'inn' finds the inn generator before furniture that says inn
            "synonyms": list(dict.fromkeys([g["name"], g["kind"].replace("_", " ")] + g.get("synonyms", []))),
            "tags": ["building", "procedural", "walkable interior", "iamar"],
            "thumbnail": None, "style": "iamar old town", "style_compat": [], "size": None,
            "triangles": {"lod0": None}, "bytes": None,
            "behaviours": [], "collision": "mesh",
            "placement": "Door facing a path or square; place with \"collision\": \"mesh\" so the interior is walkable.",
            "pairings": [],
            "source": {"origin": "generator", "cite": procedural.get("generator_cite", "")},
            "licence": "CC0-1.0",
            "attribution": "iamar", "reuse": "reusable",
            "use": "iamar-world assets building %s <out.glb>%s" % (g["kind"], " " + g["options"] if g.get("options") else ""),
        })
    for r in (city or {}).get("models", []):
        out.append(city_entry(r, city, place))
    for e in out:
        e["style_compat"] = e["style_compat"] or style_compat(e, vocab.get("style_rules", {}))   # a row may set its own
        ov = overrides.get("entries", {}).get(e["id"])
        if ov:
            for k, v in ov.items():
                e[k] = v
            if "description" in ov and "description_source" not in ov:
                e["description_source"] = "written"
    out.sort(key=lambda e: (e["category"], e["name"], e["id"]))
    return out


def preview_paths(entry_id: str) -> tuple[str, str]:
    """kit/-relative thumbnail and turntable of an entry, as kit/catalog/render_previews.gd writes them."""
    fid = entry_id.replace(":", "_").replace("/", "_")
    return "thumbnails/%s.png" % fid, "turntables/%s.png" % fid


def pair_rooms(entries: list) -> None:
    """Pair each room of sources/city_interiors.json with its shell's entries (the building and its
    closed variant): both get the other in pairings and a line in the description. A room whose
    shell is not catalogued says so: it needs a floor and walls around it (it is inner fittings only)."""
    by_sha = {e["source"].get("sha256"): e for e in entries}
    shells = {}
    if BUILDINGS.is_file():
        for r in load(BUILDINGS)["models"]:
            if r["sha256"] in by_sha:
                shells[r["models_id"]] = [by_sha[r["sha256"]]]
    if CLOSED.is_file():
        for r in load(CLOSED)["models"]:
            for mid, es in shells.items():
                if es[0]["source"]["sha256"] == r["closed_from"]["sha256"] and r["sha256"] in by_sha:
                    es.append(by_sha[r["sha256"]])
    for r in load(INTERIORS)["models"]:
        room = by_sha.get(r["sha256"])
        if room is None:
            continue
        es = shells.get(r.get("shell") or "")
        if not es:
            room["description"] += (" Its building is not in the catalogue and it has no floor or outer walls"
                                    " of its own: set it inside a building or walls of the same footprint"
                                    " (%g x %g m)." % (
                                        r["size"][0], r["size"][2]))
            continue
        for e in es:
            room["pairings"].append(e["id"])
            e["pairings"].append(room["id"])
            e["description"] += " Its interior is %s (%s): place it at the same position and rotation." % (
                room["id"], room["name"])
        room["description"] += " It fits inside %s: place it at the same position and rotation as %s." % (
            es[0]["name"], " or ".join("%s (%s)" % (e["id"], e["source"]["file"].split("/")[-1]) for e in es))


def build_catalog(builtin_path: Path = BUILTIN) -> dict:
    vocab = load(VOCAB)
    city = load(CITY) if CITY.is_file() else None
    for extra in (INSECTS, PIECES, BUILDINGS, CLOSED, INTERIORS, MOUNTS, HARBOUR, COASTAL):   # same row format as city_models.json
        if extra.is_file():
            city = dict(city or {"models": []})
            city["models"] = list(city.get("models", [])) + load(extra)["models"]
    entries = build_entries(load(builtin_path), load(PROCEDURAL), vocab,
                            load(OVERRIDES) if OVERRIDES.is_file() else {}, city)
    if CLOSED.is_file():   # an open-sided house points at its closed variant
        by_sha = {e["source"].get("sha256"): e for e in entries}
        for r in load(CLOSED)["models"]:
            parent, variant = by_sha.get(r["closed_from"]["sha256"]), by_sha.get(r["sha256"])
            if parent and variant:
                parent["description"] += " To stand it alone, use its closed variant %s (%s)." % (
                    variant["id"], variant["source"]["file"].split("/")[-1])
    if INTERIORS.is_file():   # a room and its shell (and the shell's closed variant) name each other
        pair_rooms(entries)
    counts = {}
    for e in entries:
        counts[e["category"]] = counts.get(e["category"], 0) + 1
        # every entry has both previews (render_previews.gd); check fails when a file is missing
        e["thumbnail"], e["turntable"] = preview_paths(e["id"])
    return {
        "format": "iamar-catalog", "version": 1,
        "generated_from": {"builtin": "sources/builtin_assets.json (the iamar browser source (not public) %s)" % BUILTIN_COMMIT,
                           "procedural": "sources/procedural.json", "city": "sources/city_models.json",
                           "insects": "sources/insects.json",
                           "pieces": "sources/city_pieces.json", "buildings": "sources/city_buildings.json",
                           "closed": "sources/city_buildings_closed.json",
                           "interiors": "sources/city_interiors.json",
                           "mounts": "sources/city_mounts.json",
                           "harbour": "sources/harbour.json",
                           "coastal": "sources/coastal.json",
                           "vocabulary": "vocabulary.json",
                           "overrides": "overrides.json"},
        "categories": [{"id": c["id"], "label": c["label"], "group": c["group"], "count": counts.get(c["id"], 0)}
                       for c in vocab["categories"]],
        "entries": entries,
    }


def render_md(cat: dict) -> str:
    n = len(cat["entries"])
    lines = ["# iamar object catalogue", "",
             "Generated by `python3 kit/catalog/catalog.py build`; do not edit. Search it with",
             "`iamar-world assets search <words>` (descriptions, synonyms, categories and tags).", "",
             "%d entries. Format: `kit/catalog/schema.json`. Sources: %s." % (
                 n, ", ".join("`%s`" % v for v in cat["generated_from"].values())), "",
             "## Coverage", "", "| Group | Category | Entries |", "|---|---|---|"]
    for c in cat["categories"]:
        lines.append("| %s | %s (`%s`) | %d%s |" % (c["group"], c["label"], c["id"], c["count"],
                                                 "" if c["count"] else " (gap)"))
    by = {}
    for e in cat["entries"]:
        by.setdefault(e["category"], []).append(e)
    for c in cat["categories"]:
        es = by.get(c["id"])
        if not es:
            continue
        lines += ["", "## %s (%d)" % (c["label"][:1].upper() + c["label"][1:], len(es)), "",
                  "| Name | Id | Triangles (LOD0) | Size (m) | Source | Licence |", "|---|---|---|---|---|---|"]
        for e in es:
            t = e["triangles"].get("lod0")
            sz = "x".join("%g" % v for v in e["size"]) if e.get("size") else ""
            lines.append("| %s | `%s` | %s | %s | %s | %s |" % (
                e["name"], e["id"], "?" if t is None else t, sz,
                e["source"].get("pack") or e["source"]["origin"], e["licence"].split(" (")[0]))
    return "\n".join(lines) + "\n"


def dump(cat: dict) -> str:
    """One entry per line: a smaller file and one-line diffs per object."""
    head = json.dumps({k: v for k, v in cat.items() if k != "entries"}, indent=1, ensure_ascii=False)
    rows = ",\n  ".join(json.dumps(e, ensure_ascii=False, sort_keys=True) for e in cat["entries"])
    return head[:-2] + ',\n "entries": [\n  ' + rows + "\n ]\n}\n"


# ------------------------------------------------------------------ check

def validate(cat: dict) -> list[str]:
    """Checks the parts of schema.json a plain-Python checker can: required keys, no unknown
    keys, id pattern, kinds, categories, triangles per LOD, unique ids."""
    schema = load(SCHEMA)
    ent = schema["$defs"]["entry"]
    props, req = ent["properties"], ent["required"]
    cats = {c["id"] for c in load(VOCAB)["categories"]}
    idre = re.compile(props["id"]["pattern"])
    errs, seen = [], set()
    ids_all = {e.get("id") for e in cat.get("entries", [])}
    if cat.get("format") != "iamar-catalog" or cat.get("version") != 1:
        errs.append("catalog: format/version must be iamar-catalog/1")
    for e in cat.get("entries", []):
        i = e.get("id", "?")
        for k in req:
            if k not in e:
                errs.append("%s: missing %s" % (i, k))
        for k in e:
            if k not in props:
                errs.append("%s: unknown field %s" % (i, k))
        if not idre.match(str(i)):
            errs.append("%s: bad id" % i)
        if i in seen:
            errs.append("%s: duplicate id" % i)
        seen.add(i)
        if e.get("kind") not in props["kind"]["enum"]:
            errs.append("%s: bad kind %r" % (i, e.get("kind")))
        if e.get("category") not in cats:
            errs.append("%s: unknown category %r" % (i, e.get("category")))
        if e.get("description_source") not in props["description_source"]["enum"]:
            errs.append("%s: bad description_source" % i)
        if e.get("description_source") == "generated":
            # C3a: every entry needs a written description (add it under the id in overrides.json)
            errs.append("%s: description is generated, not written: add one in overrides.json" % i)
        if not e.get("synonyms"):
            errs.append("%s: no synonyms" % i)
        if len(str(e.get("description", ""))) < 10:
            errs.append("%s: description too short" % i)
        tri = e.get("triangles")
        if not isinstance(tri, dict) or "lod0" not in tri or any(
                not re.match(r"^lod[0-9]$", k) or (v is not None and (not isinstance(v, int) or v < 0))
                for k, v in tri.items()):
            errs.append("%s: triangles must be {lod0: n, ...}" % i)
        for p in e.get("pairings", []):
            if not str(p).startswith("pack:") and p not in ids_all:
                errs.append("%s: pairs with %s, which is not an entry" % (i, p))
        for k in ("synonyms", "tags", "behaviours", "pairings", "style_compat"):
            if k in e and not isinstance(e[k], list):
                errs.append("%s: %s must be a list" % (i, k))
        if not e.get("style_compat"):
            errs.append("%s: style_compat is empty (C5: tag every entry iamar-medieval, neutral or other)" % i)
        bad = set(e.get("style_compat", [])) - set(props["style_compat"]["items"]["enum"])
        if bad:
            errs.append("%s: unknown style_compat %s" % (i, sorted(bad)))
        if e.get("reuse") not in ("reusable", "locked"):
            errs.append("%s: reuse must be reusable or locked" % i)
        for field, folder in (("thumbnail", THUMBS), ("turntable", TURNTABLES)):
            if not e.get(field):
                errs.append("%s: no %s (render it: kit/catalog/render_previews.gd)" % (i, field))
            elif folder.is_dir() and not EXPORTED and not (KIT / e[field]).is_file():
                # an exported kit withholds previews rendered with uncleared generative textures (PUB3)
                errs.append("%s: %s %s does not exist (render it: kit/catalog/render_previews.gd -- --only %s)"
                            % (i, field, e[field], i))
    # tier variants name a tier (WorldTiers.ORDER) and an entry of this catalogue
    ids = {e.get("id") for e in cat.get("entries", [])}
    for e in cat.get("entries", []):
        tv = e.get("tier_variants")
        if tv is None:
            continue
        if not isinstance(tv, dict):
            errs.append("%s: tier_variants must be an object" % e.get("id"))
            continue
        for t, v in tv.items():
            if t not in ("low", "medium", "high", "ultra"):
                errs.append("%s: tier_variants.%s: not a tier (low, medium, high, ultra)" % (e.get("id"), t))
            elif v not in ids:
                errs.append("%s: tier_variants.%s: no entry %s" % (e.get("id"), t, v))
    return errs


MADE_BY = re.compile(r"^(hand|procedural|blender|(third-party|generative):[a-z0-9][a-z0-9.-]*)$")


def provenance_errors() -> list[str]:
    """PUB3 (an internal task): every shipped binary has a provenance.json row (made_by + evidence), made_by
    names a known licence row, and the file matches what provenance_build.py would write."""
    sys.path.insert(0, str(HERE))
    import provenance_build as pb
    if not pb.OUT.is_file():
        return ["provenance.json is missing: run python3 kit/catalog/provenance_build.py"]
    rows = load(pb.OUT).get("rows", {})
    lic = {r["id"] for r in load(pb.LICENCES)["rows"]} if pb.LICENCES.is_file() else None
    errs = []
    for p, r in rows.items():
        m = str(r.get("made_by", ""))
        if not MADE_BY.match(m):
            errs.append("provenance %s: made_by %r is not hand, procedural, blender, third-party:<row> or generative:<row>" % (p, m))
        elif ":" in m and lic is not None and m.split(":", 1)[1] not in lic:
            errs.append("provenance %s: %s is not a row of kit/inventory/licences.json" % (p, m))
        if not str(r.get("evidence", "")).strip():
            errs.append("provenance %s: no evidence" % p)
    if (pb.ROOT / ".git").exists() and not EXPORTED:   # the source repo: rows must match the builder (and cover every binary)
        fresh, unmatched = pb.build()
        errs += ["no provenance rule for %s (add one to RULES in kit/catalog/provenance_build.py)" % p for p in unmatched]
        if pb.dump(fresh) != pb.OUT.read_text(encoding="utf-8"):
            errs.append("provenance.json is stale: run python3 kit/catalog/provenance_build.py")
    else:   # an exported kit: every binary present needs its row
        for top in pb.INCLUDE_TOP:
            for f in sorted((pb.ROOT / top).rglob("*")) if (pb.ROOT / top).is_dir() else []:
                rel = f.relative_to(pb.ROOT).as_posix()
                if f.suffix.lower() in pb.BIN_EXT and f.is_file() and rel not in rows:
                    errs.append("no provenance row for %s" % rel)
    return errs


def check(builtin_path: Path = BUILTIN) -> int:
    fresh = build_catalog(builtin_path)
    errs = validate(fresh)
    if not CATALOG.is_file() or CATALOG.read_text(encoding="utf-8") != dump(fresh):
        errs.append("catalog.json is stale: run python3 kit/catalog/catalog.py build")
    if not CATALOG_MD.is_file() or CATALOG_MD.read_text(encoding="utf-8") != render_md(fresh):
        errs.append("CATALOG.md is stale: run python3 kit/catalog/catalog.py build")
    built = {e["source"].get("sha256") for e in fresh["entries"]}
    missing = [o["file"] for o in load(builtin_path)["objects"] if o["sha256"] not in built]
    errs += ["no catalogue entry for built-in %s" % f for f in missing]
    # every model shipped in kit/catalog/assets needs an entry (and the entry its file)
    cited = {e["source"]["file"] for e in fresh["entries"]
             if str(e["source"].get("file", "")).startswith("kit/catalog/assets/")}
    if ASSETS.is_dir():
        for g in sorted(list(ASSETS.rglob("*.glb")) + list(ASSETS.rglob("*.ogg"))):
            rel = "kit/catalog/assets/" + g.relative_to(ASSETS).as_posix()
            if rel not in cited:
                errs.append("shipped asset %s has no catalogue entry (add it to assets/import_city_models.py PICK, insects.py INSECTS, harbour.py MODELS, coastal.py MODELS, export_city_pieces.gd, import_city_buildings.py PICK or import_city_interiors.py PICK)" % rel)
    for rel in sorted(cited):
        if not (KIT.parent / rel).is_file():
            errs.append("catalogue entry names %s, which is not in the kit" % rel)
    errs += provenance_errors()
    for e in errs:
        print("FAIL", e)
    gen = sum(1 for e in fresh["entries"] if e["description_source"] == "generated")
    print("CATALOG %d entries, %d errors, %d with generated descriptions, %d without thumbnail, %d without turntable" % (
        len(fresh["entries"]), len(errs), gen,
        sum(1 for e in fresh["entries"] if not (KIT / str(e.get("thumbnail") or "-")).is_file()),
        sum(1 for e in fresh["entries"] if not (KIT / str(e.get("turntable") or "-")).is_file())))
    return 1 if errs else 0


# ------------------------------------------------------------------ search

WEIGHTS = (("name", 6), ("synonyms", 5), ("category", 4), ("tags", 2), ("description", 1), ("file", 1))


def _fields(e: dict, cats: dict) -> dict:
    c = cats.get(e["category"], {})
    return {
        "name": terms(e["name"]),
        "synonyms": terms(" ".join(e.get("synonyms", []))),
        "category": terms(" ".join([e["category"], c.get("label", "")] + c.get("synonyms", []))),
        "tags": terms(" ".join(e.get("tags", []) + e.get("behaviours", []))),
        "description": terms(e.get("description", "")),
        "file": terms(e.get("source", {}).get("file", "")),
    }


def search(cat: dict, query: str, category: str | None = None, style: str | None = None) -> list[dict]:
    """Entries matching every query word in some field, best first. A query that is a
    category label or synonym ('small animal') matches that category as a phrase."""
    words = [stem(w) for w in split_words(query)]
    vocab = load(VOCAB)
    cats = {c["id"]: c for c in vocab["categories"]}
    aliases = {stem(k): {stem(a) for a in v} for k, v in vocab.get("aliases", {}).items()}
    q = " ".join(split_words(query))
    phrase_cats = {cid for cid, c in cats.items()
                   if q and (q == " ".join(split_words(c["label"])) or q == cid.replace("-", " ")
                             or q in [" ".join(split_words(s)) for s in c.get("synonyms", [])])}
    scored = []
    for e in cat["entries"]:
        if category and e["category"] != category:
            continue
        if style and style not in e.get("style_compat", []):
            continue
        f = _fields(e, cats)
        phrase_syn = q and q in [" ".join(split_words(s)) for s in e.get("synonyms", [])]
        if e["category"] in phrase_cats or phrase_syn:
            score = 50 if e["category"] in phrase_cats else 60
            if phrase_syn and e["category"] in phrase_cats and " " not in q:
                # one word that names the category and this entry ("bee"): the bumblebee
                # before the butterflies; a phrase ("small animal") names a class, ranks unchanged
                score += 10
            if q and q == " ".join(split_words(e["name"])):
                score += 20   # "wolf" names the wildlife category too: the wolf itself first
            elif phrase_syn and e["kind"] == "generator":
                score += 5    # "house", "home": the generator that builds one to any size first, then the models
            scored.append((score, e))
            continue
        score = 0
        for w in words:
            best = max((wt for k, wt in WEIGHTS if w in f[k]), default=0)
            if best == 0 and w in aliases:   # 'ship' finds the boats, one point below the word itself
                best = max((wt - 1 for k, wt in WEIGHTS for a in aliases[w] if a in f[k]), default=0)
            if best <= 0:
                score = -1
                break
            score += best
        if score > 0 or (not words and score == 0):
            scored.append((score, e))
    scored.sort(key=lambda se: (-se[0], se[1]["kind"] != "creature", se[1]["name"], se[1]["id"]))
    return [e for _, e in scored]


def _known_words(cat: dict) -> list[str]:
    """Every searchable word of the catalogue, its categories and aliases (for 'did you mean')."""
    vocab = load(VOCAB)
    cats = {c["id"]: c for c in vocab["categories"]}
    known = {stem(k) for k in vocab.get("aliases", {})}
    for e in cat["entries"]:
        for v in _fields(e, cats).values():
            known |= v
    return sorted(w for w in known if len(w) > 2 and not w.isdigit())


def near(cat: dict, query: str, category: str | None = None, style: str | None = None,
         limit: int = 5) -> tuple[str, list[dict], list[str]]:
    """For a search with no hits: (corrected query or '', nearest entries, MAKE hints).
    A misspelt word is corrected to the closest catalogue word ('sofaa' -> sofa); otherwise the
    entries that match the most query words are the nearest; the make hints come from
    vocabulary.json make (a building generator for building words, else the Blender starter)."""
    words = split_words(query)
    known = _known_words(cat)
    fixed, changed = [], False
    for w in words:
        if stem(w) in known or w.isdigit():
            fixed.append(w)
            continue
        m = difflib.get_close_matches(stem(w), known, n=1, cutoff=0.75)
        fixed.append(m[0] if m else w)
        changed = changed or bool(m)
    corrected = " ".join(fixed) if changed else ""
    hits = search(cat, corrected, category, style) if corrected else []
    if not hits and len(words) > 1:   # 'red spaceship lamp': the entries with the most of these words
        counts: dict[str, tuple[int, dict]] = {}
        for w in fixed:
            for e in search(cat, w, category, style):
                n, _ = counts.get(e["id"], (0, e))
                counts[e["id"]] = (n + 1, e)
        hits = [e for n, e in sorted(counts.values(), key=lambda ne: -ne[0])]
    make, rules = [], load(VOCAB).get("make", [])
    qs = {stem(w) for w in words} | {stem(w) for w in fixed}
    for r in rules:
        if r["words"] and qs & {stem(w) for w in r["words"]}:
            make.append(r["say"])
    make += [r["say"] for r in rules if not r["words"]]
    return corrected, hits[:limit], make


def download_bytes(e: dict) -> int:
    """What the entry adds to a world's download. A built-in is referenced by hash (the browser has
    it), so 0: its `bytes` are the hash input, glTF plus the shared trim-sheet textures (an internal task:
    the twin bed read as 6 MB). A kit object adds the files its use line copies (tier files too)."""
    if e["source"].get("origin") == "builtin":
        return 0
    files = [KIT.parent / src for src, _ in copies(e)]
    if files and all(f.is_file() for f in files):
        return sum(f.stat().st_size for f in files)
    return int(e.get("bytes") or 0)


def line(e: dict) -> str:
    t = e["triangles"].get("lod0")
    sz = " %sm" % "x".join("%g" % v for v in e["size"]) if e.get("size") else ""
    b = download_bytes(e)
    if e["source"].get("origin") == "builtin":
        mb = " built in (0 MB download)"
    else:
        mb = " %.1f MB" % (b / 1048576) if b >= 102400 else ""
    if b > 1048576:
        mb += " WARN large download (over 1 MB; prefer a lighter object)"
    return "CATALOG %s %s [%s] %s tris%s%s %s%s\n  %s\n  use: %s" % (
        e["id"], e["name"], e["category"], "?" if t is None else t, sz, mb, e["licence"].split(" (")[0],
        "" if e["reuse"] == "reusable" else " LOCKED", e["description"], e["use"])


def find(cat: dict, key: str) -> dict | None:
    """The entry whose id (or leading part of it, 4+ chars) or exact name is `key`."""
    k = key.strip().lower()
    for e in cat["entries"]:
        if k == e["id"].lower() or k == e["name"].lower():
            return e
    pre = [e for e in cat["entries"] if len(k) >= 4 and e["id"].lower().startswith(k)]
    return pre[0] if len(pre) == 1 else None


COPY_RE = re.compile(r"(kit/catalog/assets/[^ ,]+) to <world folder>/([^ ,]+)")


def copies(e: dict) -> list[tuple[str, str]]:
    """(kit file, path in the world) pairs of an entry whose use line copies files: the iamar-original
    models and sounds, which are not built into the browser. [] for built-ins, creatures, generators."""
    u = e.get("use", "")
    if not u.startswith("copy "):
        return []
    return COPY_RE.findall(u.split(", then ", 1)[0])


def use(world: Path, key: str, as_path: str | None) -> int:
    """`iamar-world assets use` for catalogue ids. Built-in objects (exit 3) are left to the browser,
    which references them by hash; kit files are copied into the world, with their tier files."""
    cat = load(CATALOG)
    e = find(cat, key)
    if e is None or e["source"].get("origin") == "builtin":
        return 3
    if e["reuse"] != "reusable":
        print("ERROR %s is locked: %s" % (e["name"], e.get("reuse")))
        return 1
    pairs = copies(e)
    if not pairs:   # a creature or a generator: nothing to copy, its use line says what to write
        print("USE %s: %s" % (e["name"], e["use"]))
        return 0
    if not (world / "manifest.json").is_file():
        print("ERROR no manifest.json in %s (make the world first: iamar-world new)" % world)
        return 1
    low = pairs[0][1]
    if as_path:
        ext = Path(low).suffix
        if (not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", as_path) or ".." in as_path or "//" in as_path
                or as_path.split("/")[0] != low.split("/")[0] or not as_path.endswith(ext)):
            print("ERROR --as must be a path like %s/<name>%s (letters, digits, _ . / - only)" % (low.split("/")[0], ext))
            return 2
    else:
        as_path = low
    plan = [(KIT.parent / src, world / (as_path if dst == low else dst.replace(low, as_path)))
            for src, dst in pairs]
    for src, dst in plan:
        if not src.is_file():
            print("ERROR %s is missing from this kit" % src)
            return 1
        if dst.exists():
            print("ERROR %s is already a file in the world; pick another --as path" % dst.relative_to(world))
            return 1
    for src, dst in plan:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    credit_files = [str(d.relative_to(world)).replace("\\", "/") for _, d in plan]
    mp = world / "manifest.json"
    try:
        man = json.loads(mp.read_text(encoding="utf-8"))
        old = man.get("credits", []) if isinstance(man, dict) else None
        if not isinstance(old, list):   # leave a hand-written manifest alone rather than crash after the copy
            raise ValueError("manifest.json credits is not a list")
        credits = [c for c in old if not (isinstance(c, dict) and isinstance(c.get("files"), list)
                                          and set(c["files"]) & set(credit_files))]
        credits.append({"files": credit_files, "author": e.get("attribution") or "iamar", "license": e["licence"],
                        "source": "iamar kit catalogue " + e["id"]})
        man["credits"] = credits
        mp.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        print("CREDIT written to manifest.json credits for %s" % ", ".join(credit_files))
    except (OSError, ValueError) as ex:
        print("WARN could not write the manifest.json credits entry (%s); add one for %s by hand"
              % (ex, ", ".join(credit_files)))
    then = e["use"].split(", then ", 1)[1].replace(low, as_path)
    print("COPIED %s -> %s (%s bytes in your download: an iamar original, not built into the browser, so the "
          "world carries the file; licence: %s)" % (e["name"], ", ".join(str(d.relative_to(world)) for _, d in plan),
                                                  sum(s.stat().st_size for s, _ in plan), e["licence"]))
    tiers = re.search(r"\(manifest\.json tiers lists [^)]*\)", e["use"].split(", then ", 1)[0])
    if tiers:
        print("TIERS %s" % tiers.group(0)[1:-1])
    print("THEN %s" % then)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="catalog.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--builtin", type=Path, help="refresh sources/builtin_assets.json from this file first")
    sub.add_parser("check")
    s = sub.add_parser("search")
    s.add_argument("words", nargs="*")
    s.add_argument("--category")
    s.add_argument("--style")
    s.add_argument("--limit", type=int, default=25)
    s.add_argument("--json", action="store_true")
    sh = sub.add_parser("show", help="one entry by the id or name that search prints (exit 3 when unknown)")
    sh.add_argument("key")
    us = sub.add_parser("use", help="copy a kit catalogue object into a world (exit 3: a built-in or unknown id)")
    us.add_argument("world", type=Path)
    us.add_argument("key")
    us.add_argument("--as", dest="as_path")
    a = ap.parse_args(argv)
    if a.cmd == "use":
        return use(a.world, a.key, a.as_path)
    if a.cmd == "show":
        e = find(load(CATALOG), a.key)
        if e is None:
            return 3
        print(line(e))
        print(json.dumps(e, indent=1, ensure_ascii=False))
        return 0
    if a.cmd == "build":
        if a.builtin:
            shutil.copyfile(a.builtin, BUILTIN)
        cat = build_catalog()
        errs = validate(cat)
        for e in errs:
            print("FAIL", e)
        if errs:
            return 1
        CATALOG.write_text(dump(cat), encoding="utf-8", newline="\n")
        CATALOG_MD.write_text(render_md(cat), encoding="utf-8", newline="\n")
        print("BUILT %d entries -> %s, %s" % (len(cat["entries"]), CATALOG.name, CATALOG_MD.name))
        return 0
    if a.cmd == "check":
        return check()
    cat = load(CATALOG)
    hits = search(cat, " ".join(a.words), a.category, a.style)
    shown = hits[: a.limit] if a.limit > 0 else hits
    if a.json:
        print(json.dumps(shown, indent=1, ensure_ascii=False))
    else:
        for e in shown:
            print(line(e))
        print("COUNT %d%s" % (len(hits), "" if len(shown) == len(hits) else " (showing %d; --limit 0 for all)" % len(shown)))
        if not hits and a.words:   # never a dead end: the closest objects, then how to make it
            corrected, nearest, make = near(cat, " ".join(a.words), a.category, a.style)
            if corrected:
                print("DID-YOU-MEAN %s" % corrected)
            for e in nearest:
                print("NEAREST " + line(e)[len("CATALOG "):])
            for m in make:
                print("MAKE " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
