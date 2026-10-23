#!/usr/bin/env python3
"""Copy the iamar city's room interiors (one room per building purpose, kit/catalog/public_selection.json)
from an the iamar-models mesh archive (not public) checkout into kit/catalog/assets/interiors/ and record them in
kit/catalog/sources/city_interiors.json.

  python3 kit/catalog/assets/import_city_interiors.py <iamar-models checkout>
  python3 kit/catalog/assets/import_city_interiors.py --check

The city builds a room inside its building (floor, inner walls, ceiling, counters, shelves,
lamps ...) and exports it in city coordinates, fitted to that building's footprint. So each room
is moved by its SHELL's offset, the same one import_city_buildings.py gives the building (the
shell's footprint centre to x = z = 0, its lowest point to y = 0): a room and its shell placed at
the same position and rotation line up exactly as in the city. catalog.py build pairs a room with
its shell's entries when the shell is catalogued, and says so in both descriptions.

Each room's mesh is put under a new empty root node (wrap_root: the city exports it as the
scene root itself, which loaders walking a scene's children miss). A room that the city builds
in parts (the library's archive, books, glass ..., the inn's fire glow) ships as one file: each
part is added under that root, in the room's frame, so it moves with it. The record lists every part's source file and sha256.

A room is its building's inner fittings (ceiling beams, inner wall frames and wainscot, counters,
shelves, stalls, lamps, inner doorways); the shell gives the floor, outer walls and roof. Seen
alone (a thumbnail) it is an open frame: that is the intended look, not a hole.
Python 3.8+, standard library only.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from import_city_models import measure  # noqa: E402  (same folder)
from import_city_buildings import _commit, bounds, glb_join, glb_split, recentre, wrap_root  # noqa: E402

CATALOG_DIR = HERE.parent
SOURCE = CATALOG_DIR / "sources" / "city_interiors.json"
FOLDER = "interiors"
LICENCE = "CC0-1.0"   # kit/inventory/licences.json original-procedural (an internal task)

QUARTER_STYLE = {   # as import_city_buildings.py QUARTERS names them
    "civic": "iamar city: civic heart", "herbalists": "iamar city: herbalists' quarter",
    "mages": "iamar city: mages' quarter", "warriors": "iamar city: warriors' quarter",
}

# models.json room id -> (shell models.json id or None, quarter or None, name, description, synonyms);
# None: models.json has no export of the building, so the room is centred on its own footprint
# Descriptions say what the room holds (checked against renders) and which building it fits.
PICK = {
    "Interior_B001": ("B001", "warriors", "warriors' quarter bird supply shop interior",
        "The inside of a long two-wing shop: an exposed timber ceiling grid under the roof pitch, framed inner walls, a row of wooden counters and shelves down the hall, hanging lanterns, a stone-arched inner doorway and a red rug at the door; 16 by 27 m.",
        ["bird shop", "pet shop", "shop interior", "store interior", "shelves", "counters"]),
    "Interior_B007": ("B007", "warriors", "warriors' quarter smithy interior",
        "The inside of a long narrow smithy: exposed ceiling beams, timber wall frames, a stone forge block, hanging lanterns, wall panels and a stone-arched doorway; 7 by 17 m.",
        ["smithy", "blacksmith", "forge", "workshop interior", "metalwork", "shop interior"]),
    "Interior_B012": ("B012", "mages", "mages' quarter rune shop interior",
        "The inside of a small rune carver's shop: exposed ceiling beams, violet wainscot walls, a wooden counter set with coloured runes, a violet rug, glowing blue hanging lamps and a stone-arched doorway; 7 by 14 m.",
        ["rune shop", "magic shop", "shop interior", "counter", "enchanter", "store interior"]),
    "Interior_B021": ("B021", "warriors", "warriors' quarter blacksmith forge interior",
        "The inside of a wide forge hall: a timber ceiling grid, wooden wainscot, a stone forge block, hanging lanterns and three stone-arched doorways along the front; 15 by 7 m.",
        ["forge", "blacksmith", "smithy", "workshop interior", "ironworks", "metalwork"]),
    "Interior_B034": ("B034", "mages", "mages' quarter curio shop interior",
        "The inside of a two-room curio shop: exposed ceiling beams, violet wainscot walls, wooden counters, a violet rug, glowing blue hanging lamps and two stone-arched doorways; 16 by 8 m.",
        ["curio shop", "curiosities", "antiques", "magic shop", "shop interior", "counters"]),
    "Interior_B039": ("B039", "civic", "civic heart jousting supply store interior",
        "The inside of a large L-shaped store: a timber ceiling grid under a stepped roof, framed inner walls, many wooden counters and wall shelves, a red rug and stone-arched doorways; 11 by 24 m.",
        ["jousting", "tack shop", "saddler", "store interior", "shop interior", "shelves"]),
    "Interior_B048": ("B048", "mages", "mages' quarter wandmaker interior",
        "The inside of a wandmaker's shop: exposed ceiling beams, violet wainscot walls, a wooden counter with wands and phials, a violet rug, glowing blue hanging lamps and two stone-arched doorways; 13 by 8 m.",
        ["wand shop", "wandmaker", "magic shop", "shop interior", "counter", "store interior"]),
    "Interior_B055": ("B055", "civic", "civic heart healer's shop interior",
        "The inside of a small healer's room: exposed ceiling beams, timber wall frames and panels, a cushioned treatment bed, a red rug, a hanging lantern and two stone-arched doorways; 8 by 6 m.",
        ["healer", "clinic", "infirmary", "apothecary", "sickroom", "shop interior"]),
    "Interior_B058": ("B058", None, "city hall interior",
        "The inside of a city hall's long chamber: tall white arches along both walls, dark timber roof trusses, a raised dais with high-backed council seats, a wooden railing before it and a lectern; 27 by 11 m and 9.5 m high.",
        ["city hall", "council chamber", "town hall", "court", "assembly hall", "throne room"]),
    "Interior_B075": ("B075", "herbalists", "herbalists' quarter tool shop interior",
        "The inside of a large L-shaped tool shop: a timber ceiling grid, framed inner walls, wooden counters and shelves, a green rug, hanging lanterns and stone-arched doorways; 21 by 32 m.",
        ["tool shop", "toolmaker", "hardware", "shop interior", "store interior", "counters"]),
    "Interior_B077": ("B077", "herbalists", "herbalists' quarter herb shop interior",
        "The inside of a shallow herb shop: exposed ceiling beams, timber wall frames, wall panels, a green rug, a hanging lantern and two stone-arched doorways; 12 by 3 m.",
        ["herb shop", "herbalist", "apothecary", "shop interior", "store interior", "healer"]),
    "Interior_B081": ("B081", None, "bank interior",
        "The inside of a long bank hall: pale timber roof trusses on tall pale pillars, a pale inner wall with a long wooden counter, arched doorways and small chests along the walls; 59 by 20 m and 10 m high.",
        ["bank", "counting house", "treasury", "vault", "hall", "money changer"]),
    "Interior_B082": ("B082", None, "trading hall interior",
        "The inside of a trading hall: heavy timber roof trusses over a floor of market stalls with blue and green awnings, crates, a notice board, a gallery and stone-arched doorways; 22 by 13 m and 9 m high.",
        ["trading hall", "market hall", "exchange", "bazaar", "stalls", "guild hall"]),
    "Interior_B086": ("B086", "herbalists", "herbalists' quarter bookshop interior",
        "The inside of a small bookshop: a timber ceiling grid, timber wall frames, wooden wainscot and two hanging lanterns; 8 by 6 m.",
        ["bookshop", "bookseller", "books", "shop interior", "store interior", "study"]),
    "Interior_B119": ("B119", "civic", "civic heart bakery interior",
        "The inside of a small bakery: exposed ceiling beams, wooden wainscot, a wooden counter with loaves, a red rug, a hanging lantern and a stone-arched doorway; 5 by 7 m.",
        ["bakery", "baker", "bakehouse", "shop interior", "counter", "store interior"]),
    "Interior_B129": (None, "civic", "civic heart horse supply shop interior",
        "The inside of a long L-shaped saddlery: a timber ceiling grid, framed inner walls lined with wooden racks and shelves, a red rug and stone-arched doorways; 39 by 24 m.",
        ["saddler", "tack shop", "horse supplies", "stable supplies", "shop interior", "store interior"]),
    "Interior_BIRD01": ("BIRD01", None, "giant-bird aerie interior",
        "The inside of a giant-bird aerie: a ring of open wooden roost stalls with straw beds around the walls and lamps hanging from the high roof; 28 by 29 m and 13.5 m high.",
        ["aerie", "eyrie", "roost", "bird stable", "mews", "stalls"]),
    "Interior_C02": ("C02", None, "library interior",
        "The inside of the city library, every part of the room in one file: a tall reading hall with a coffered timber ceiling, rows of reading desks and chairs, a red-carpeted aisle, an upper gallery with balusters, long book stacks, an archive, a scriptorium, a meeting room, glowing windows, a light shaft and a fireplace glow; 49 by 71 m and 18 m high.",
        ["library", "reading room", "archive", "scriptorium", "study hall", "books"]),
    "Interior_C03": ("C03", None, "inn and tavern interior",
        "The inside of a large inn and tavern: tall arched timber walls, long roof trusses, rows of trestle tables and benches, a long bar counter, a white kitchen wall with doors, a big hearth with a fire glow and hanging lamps; 39 by 28 m and 12 m high.",
        ["inn", "tavern", "pub", "alehouse", "dining hall", "hearth"]),
    "Interior_DRAGON01": ("DRAGON01", None, "small-dragon stable interior",
        "The inside of a small-dragon stable: rows of open wooden stalls with straw beds along the walls and blue lamps hanging from the high roof; 30 by 21 m and 10.5 m high.",
        ["dragon stable", "dragon pen", "stable", "stalls", "roost", "lair"]),
    "Interior_S01": ("S01", None, "horse stable interior",
        "The inside of a horse stable: a row of wooden stalls with straw beds along two walls and lanterns hanging from the beams; 29 by 16 m.",
        ["stable", "stables", "horse barn", "stalls", "livery", "barn"]),
    "Interior_W01": ("W01", None, "weapons hall interior",
        "The inside of a big weapons shop: a long timber ceiling grid, a wall of tall stone arches, wooden counters and weapon racks, a red rug and stone-arched doorways; 45 by 24 m.",
        ["weapons shop", "armory", "armoury", "weaponsmith", "arms hall", "shop interior"]),
}

# models.json part id -> its room (shipped inside the room's file)
PARTS = {
    "Interior_C02_FireplaceGlow": "Interior_C02", "Interior_C02_archive": "Interior_C02",
    "Interior_C02_balusters": "Interior_C02", "Interior_C02_books": "Interior_C02",
    "Interior_C02_coffers": "Interior_C02", "Interior_C02_glass": "Interior_C02",
    "Interior_C02_lightshaft": "Interior_C02", "Interior_C02_meeting": "Interior_C02",
    "Interior_C02_scriptorium": "Interior_C02",
    "Interior_C03_FireplaceGlow": "Interior_C03",
}


# ------------------------------------------------------------------ GLB merge

def _pad4(b: bytes) -> bytes:
    return b + b"\0" * ((4 - len(b) % 4) % 4)


def add_parts(room: bytes, parts: list) -> bytes:
    """room with each part's meshes added as children of the room's root node (same frame).
    Every file is a single-buffer GLB as Godot exports it; materials, accessors, buffer views,
    images, samplers and textures are appended with their indices shifted."""
    j, rest = glb_split(room)
    binary = bytearray(rest[8:8 + int.from_bytes(rest[0:4], "little")]) if rest else bytearray()
    root = j["nodes"][j["scenes"][j.get("scene", 0)]["nodes"][0]]
    for pb in parts:
        pj, prest = glb_split(pb)
        pbin = prest[8:8 + int.from_bytes(prest[0:4], "little")] if prest else b""
        binary = bytearray(_pad4(bytes(binary)))
        base = len(binary)
        binary += pbin
        off = {k: len(j.setdefault(k, [])) for k in
               ("bufferViews", "accessors", "materials", "meshes", "nodes", "images", "samplers", "textures")}
        for bv in pj.get("bufferViews", []):
            bv = dict(bv, buffer=0, byteOffset=bv.get("byteOffset", 0) + base)
            j["bufferViews"].append(bv)
        for a in pj.get("accessors", []):
            a = dict(a)
            if "bufferView" in a:
                a["bufferView"] += off["bufferViews"]
            j["accessors"].append(a)
        for im in pj.get("images", []):
            im = dict(im)
            if "bufferView" in im:
                im["bufferView"] += off["bufferViews"]
            j["images"].append(im)
        j["samplers"] += pj.get("samplers", [])
        for t in pj.get("textures", []):
            t = dict(t)
            if "source" in t:
                t["source"] += off["images"]
            if "sampler" in t:
                t["sampler"] += off["samplers"]
            j["textures"].append(t)
        for m in pj.get("materials", []):
            m = json.loads(json.dumps(m))

            def shift(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if k == "index" and isinstance(v, int):
                            o[k] = v + off["textures"]
                        else:
                            shift(v)
                elif isinstance(o, list):
                    for v in o:
                        shift(v)
            shift(m)
            j["materials"].append(m)
        for me in pj.get("meshes", []):
            me = json.loads(json.dumps(me))
            for p in me["primitives"]:
                p["attributes"] = {k: v + off["accessors"] for k, v in p["attributes"].items()}
                if "indices" in p:
                    p["indices"] += off["accessors"]
                if "material" in p:
                    p["material"] += off["materials"]
                for t in p.get("targets", []):
                    for k in t:
                        t[k] += off["accessors"]
            j["meshes"].append(me)
        if pj.get("skins") or pj.get("animations"):
            raise ValueError("part with skins or animations: not supported")
        for n in pj["nodes"]:
            n = dict(n)
            if "mesh" in n:
                n["mesh"] += off["meshes"]
            if "children" in n:
                n["children"] = [c + off["nodes"] for c in n["children"]]
            j["nodes"].append(n)
        root.setdefault("children", []).extend(r + off["nodes"] for r in pj["scenes"][pj.get("scene", 0)]["nodes"])
        for k in ("extensionsUsed", "extensionsRequired"):
            for x in pj.get(k, []):
                if x != "GODOT_single_root" and x not in j.setdefault(k, []):   # see wrap_root
                    j[k].append(x)
        for k in ("samplers", "textures", "images"):
            if not j.get(k):
                j.pop(k, None)
    binary = _pad4(bytes(binary))
    j["buffers"] = [{"byteLength": len(binary)}]
    return glb_join(j, len(binary).to_bytes(4, "little") + (0x004E4942).to_bytes(4, "little") + binary)


# ------------------------------------------------------------------ import / check

def shell_pivot(models_repo: Path, index: dict, shell: str) -> list:
    """The shell's pivot in city coordinates, as import_city_buildings.py computes it."""
    lo, hi = bounds((models_repo / index[shell]["file"]).read_bytes())
    return [(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2]


def import_from(models_repo: Path) -> int:
    index = json.loads((models_repo / "models.json").read_text(encoding="utf-8"))["models"]
    commit = _commit(models_repo)
    rows, bad = [], []
    for mid, (shell, quarter, name, desc, syn) in PICK.items():
        miss = [i for i in [mid, shell or mid] + [p for p, r in PARTS.items() if r == mid] if i not in index]
        bad += ["%s: not in models.json" % i for i in miss]
        if miss:
            continue
        rec = index[mid]
        src = (models_repo / rec["file"]).read_bytes()
        parts = sorted(p for p, r in PARTS.items() if r == mid)
        psrc = [(models_repo / index[p]["file"]).read_bytes() for p in parts]
        pivot = shell_pivot(models_repo, index, shell) if shell else None
        if pivot is None:   # the city exports no shell for it: the room's own footprint centre and floor
            lo, hi = bounds(add_parts(wrap_root(src), psrc) if parts else src)
            pivot = [(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2]
        b = add_parts(wrap_root(src), psrc) if parts else wrap_root(src)
        b = recentre(b, [-pivot[0], -pivot[1], -pivot[2]])
        m = measure(b)
        want = int(rec.get("triangles") or 0) + sum(int(index[p].get("triangles") or 0) for p in parts)
        if want and want != m["triangles"]:
            print("note %s: models.json says %d triangles with its parts, the file has %d (kept the file's count)"
                  % (mid, want, m["triangles"]))
        fname = mid.lower() + ".glb"
        dst = HERE / FOLDER / fname
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b)
        rows.append({
            "models_id": mid, "file": "%s/%s" % (FOLDER, fname), "name": name, "category": "interior",
            "description": desc, "synonyms": syn, "collision": "mesh",
            "style": QUARTER_STYLE.get(quarter, "iamar city"), "shell": shell,
            "tags": ["iamar city", "interior", "room"],
            "parts": [{"models_id": p, "source_sha256": hashlib.sha256(s).hexdigest(),
                       "cite": "the iamar-models mesh archive (not public) %s %s" % (commit, index[p]["file"])}
                      for p, s in zip(parts, psrc)],
            "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b),
            "source_sha256": hashlib.sha256(src).hexdigest(),
            "recentred_by": [round(-v, 3) for v in pivot],
            "place_scale": 1.0,
            "triangles": m["triangles"], "models_json_triangles": want or None, "size": m["size"],
            "skinned": m["skinned"], "animations": m["animations"], "images": m["images"],
            "physics_body": m["physics_body"], "licence": LICENCE,
            "builder": rec.get("builder", ""), "builder_commit": rec.get("builder_commit", ""),
            "cite": "the iamar-models mesh archive (not public) %s %s (the iamar browser source (not public) %s, plan sha256 %s...)" % (
                commit, rec["file"], rec.get("builder_commit", ""), rec.get("plan_sha256", "")[:12]),
        })
    for line in bad:
        print("IMPORT ERROR " + line, file=sys.stderr)
    if bad:
        return 1
    rows.sort(key=lambda r: r["file"])
    SOURCE.write_text(json.dumps({
        "format": "iamar-catalog-city-models", "version": 1,
        "note": "Room interiors of the iamar city, one per building purpose (public_selection.json), copied from "
                "the iamar-models mesh archive (not public) and moved by their shell building's offset by "
                "kit/catalog/assets/import_city_interiors.py, so a room and its shell placed at the same "
                "position line up. Files live in kit/catalog/assets/<file>. Never edit by hand: rerun the import.",
        "models_commit": commit, "licence": LICENCE, "models": rows}, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    print("imported %d rooms (%d bytes) from iamar-models %s" % (len(rows), sum(r["bytes"] for r in rows), commit))
    return 0


def check() -> int:
    errs = []
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    shells = {}
    bsrc = SOURCE.with_name("city_buildings.json")
    if bsrc.is_file():
        shells = {r["models_id"]: r for r in json.loads(bsrc.read_text(encoding="utf-8"))["models"]}
    for r in src["models"]:
        p = HERE / r["file"]
        if not p.is_file():
            errs.append("%s: file missing" % r["file"])
            continue
        b = p.read_bytes()
        if hashlib.sha256(b).hexdigest() != r["sha256"]:
            errs.append("%s: sha256 differs from city_interiors.json (rerun the import)" % r["file"])
        m = measure(b)
        if m["triangles"] != r["triangles"]:
            errs.append("%s: %d triangles, record says %d" % (r["file"], m["triangles"], r["triangles"]))
        if r["models_id"] not in PICK:
            errs.append("%s: %s is not in PICK" % (r["file"], r["models_id"]))
        sh = shells.get(r["shell"] or "")   # a catalogued shell must have been moved by the same offset
        if sh and any(abs(a - c) > 0.002 for a, c in zip(sh["recentred_by"], r["recentred_by"])):
            errs.append("%s: moved by %s, its shell %s by %s: they no longer line up (rerun the import)"
                        % (r["file"], r["recentred_by"], r["shell"], sh["recentred_by"]))
        lo, hi = bounds(b)   # the room sits inside its shell: near the origin, on or above the ground
        if lo[1] < -0.6 or max(abs(lo[0]), abs(hi[0]), abs(lo[2]), abs(hi[2])) > 60:
            errs.append("%s: bounds %s..%s are not around the origin" % (r["file"], lo, hi))
    listed = {(HERE / r["file"]).resolve() for r in src["models"]}
    for p in (HERE / FOLDER).rglob("*.glb"):
        if p.resolve() not in listed:
            errs.append("%s: GLB with no record in sources/city_interiors.json" % p.relative_to(HERE).as_posix())
    for e in errs:
        print("CHECK " + e)
    print("city interiors: %d records, %s" % (len(src["models"]), "OK" if not errs else "%d problems" % len(errs)))
    return 1 if errs else 0


def main(argv: list) -> int:
    if argv[:1] == ["--check"]:
        return check()
    if len(argv) != 1:
        print(__doc__)
        return 2
    return import_from(Path(argv[0]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
