#!/usr/bin/env python3
"""Copy the iamar city's single-object exports from an the iamar-models mesh archive (not public) checkout into
kit/catalog/assets/ and record them in kit/catalog/sources/city_models.json.

  python3 kit/catalog/assets/import_city_models.py <iamar-models checkout>   copy + write the source
  python3 kit/catalog/assets/import_city_models.py --pieces                  measure the exported pieces
  python3 kit/catalog/assets/import_city_models.py --mounts                  measure the exported mounts
  python3 kit/catalog/assets/import_city_models.py --baked                   fold the props' painted bake into their rows
  python3 kit/catalog/assets/import_city_models.py --check                   fail if a file or record is off

After a re-import the props are flat vertex colour again: bake them (bake_painted.gd, run from
an the iamar browser source (not public) checkout), then --baked. --check fails on a prop or furniture row without it.

The city builds these objects in code (the iamar browser source (not public) scripts/world/masterplan: MpProps,
TreeGen, MpCreatures, MpDragonKit, DragonKit); iamar-models holds them as glTF, one file per
kind, exported by the iamar browser source (not public) tools/masterplan_export_glb.gd and
tools/masterplan_export_creatures.gd. This script takes the ones a world can reuse as they are
(PICK below), measures each file itself (triangles, size) and checks the numbers against
iamar-models' models.json. `catalog.py build` then turns every record into a catalogue entry.

Left out on purpose (see README.md "Not imported"): city-wide batches (Kerbs_*, Hedgerows,
Horses ...). The iamar-models griffin LODs, dragon breeds and giant eagle are not copied
(2.6-3 MB each, the same textures embedded per file; the breeds and the eagle wear a
Hunyuan3D head, licence unconfirmed): export_city_mounts.gd rebuilds them with the city's
code-built heads and per-LOD textures, and --mounts measures them (sources/city_mounts.json).
Python 3.8+, standard library only.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG_DIR = HERE.parent
SOURCE = CATALOG_DIR / "sources" / "city_models.json"
# single pieces (furniture, crops, flora) exported from the city's builders by
# export_city_pieces.gd (its record: sources/pieces_export.json); --pieces measures them into
# sources/city_pieces.json, rows in city_models.json's format
PIECES_EXPORT = CATALOG_DIR / "sources" / "pieces_export.json"
PIECES = CATALOG_DIR / "sources" / "city_pieces.json"
# the griffin, dragon breeds and giant eagle, rebuilt by export_city_mounts.gd (its record:
# sources/mounts_export.json); --mounts measures them into sources/city_mounts.json
MOUNTS_EXPORT = CATALOG_DIR / "sources" / "mounts_export.json"
MOUNTS = CATALOG_DIR / "sources" / "city_mounts.json"
# the city's painted look baked into a texture per object (an internal task): bake_painted.gd writes
# sources/painted_bake.json for the props, --baked folds it into their rows; the furniture is
# baked by export_city_pieces.gd itself. --check fails on a row in these folders without it.
PAINTED = CATALOG_DIR / "sources" / "painted_bake.json"
PAINTED_FOLDERS = ("props", "furniture")
LICENCE = "CC0-1.0"   # kit/inventory/licences.json original-procedural (an internal task)

# models.json id -> (folder here, name, category, collision, description, synonyms)
# Descriptions say what it looks like and how the city uses it (read from the builder).
PICK = {
    # creatures: parts (body, head, legs, tail) in their standing rest pose, vertex-painted
    "creature_bunny": ("creatures", "rabbit", "animal-small", "none",
        "A small brown rabbit in its standing rest pose, body, head, ears and legs as separate parts so a script can hop it.",
        ["bunny", "hare", "critter", "small animal", "wildlife"]),
    "creature_chicken": ("creatures", "rooster", "bird", "none",
        "A farmyard rooster with a red comb, standing; separate head and legs for pecking and walking.",
        ["chicken", "cockerel", "poultry", "fowl", "farm animal", "small animal"]),
    "creature_hen": ("creatures", "hen", "bird", "none",
        "A plump brown laying hen, standing; lighter than the rooster, for farmyards and markets.",
        ["chicken", "poultry", "fowl", "farm animal", "small animal"]),
    "creature_cow": ("creatures", "cow", "livestock", "box",
        "A dairy cow with a patched coat, standing; separate head, legs and tail for grazing and walking.",
        ["cattle", "dairy cow", "bovine", "farm animal"]),
    "creature_deer": ("creatures", "deer", "wildlife", "none",
        "A slender red deer with antlers, standing alert; for meadows and forest edges.",
        ["stag", "doe", "hind", "wild animal", "forest animal"]),
    "creature_wolf": ("creatures", "wolf", "wildlife", "none",
        "A grey wolf with a thick ruff and bushy tail, standing; the city's wild-wood predator.",
        ["grey wolf", "wild dog", "predator", "forest animal"]),
    "creature_drake": ("creatures", "duck", "bird", "none",
        "A mallard drake with a green head, floating pose; for ponds and moats.",
        ["mallard", "drake", "waterfowl", "pond bird"]),
    "creature_duckling": ("creatures", "duckling", "bird", "none",
        "A small yellow duckling that follows its mother across a pond.",
        ["baby duck", "chick", "waterfowl", "pond bird", "small animal"]),
    "creature_fish": ("creatures", "fish", "fish", "none",
        "A small pond fish (carp-like) with body, tail and fins, for ponds, fountains and moats.",
        ["carp", "koi", "pond fish", "minnow"]),
    "creature_frog": ("creatures", "frog", "animal-small", "none",
        "A small green frog crouched on a lily pad or pond edge.",
        ["toad", "amphibian", "pond animal", "small animal"]),
    "creature_turtle": ("creatures", "turtle", "animal-small", "none",
        "A pond turtle with a domed shell, basking pose.",
        ["tortoise", "terrapin", "pond animal", "small animal"]),
    "MOUNT_stable_dragon": ("creatures", "young dragon", "mythical", "box",
        "A young stable dragon, skinned (one mesh on a bone skeleton, wings folded), painted scales; the city's rideable mount.",
        ["dragon", "drake", "wyrm", "mount", "stable dragon", "flying mount"]),
    "guardian_dragon": ("creatures", "guardian dragon", "mythical", "box",
        "The great red guardian dragon of the south gate: skinned, 33 bones, painted scales and glowing wing membranes; a hero creature.",
        ["dragon", "red dragon", "wyrm", "boss", "hero creature"]),
    # trees (TreeGen: welded trunk and leaf blobs, vertex colour)
    "prop_tree_oak": ("trees", "oak tree", "tree", "box",
        "A broad oak with a thick trunk and a round, lumpy crown of painted leaf blobs.",
        ["oak", "broadleaf", "deciduous tree", "shade tree"]),
    "prop_tree_elm": ("trees", "elm tree", "tree", "box",
        "A tall elm with a vase-shaped crown, for avenues and squares.",
        ["elm", "broadleaf", "deciduous tree", "street tree"]),
    "prop_tree_pine": ("trees", "pine tree", "tree", "box",
        "A slim conifer of stacked cones, very cheap; for hillsides and forest edges.",
        ["pine", "fir", "spruce", "conifer", "evergreen"]),
    # street and quarter props (MpProps Dresser kinds, faces nobody sees removed, OMI physics body)
    "prop_anvil": ("props", "anvil", "tool", "box", "A blacksmith's iron anvil on a wooden block.", ["smithy", "forge", "blacksmith"]),
    "prop_archery_target": ("props", "archery target", "prop", "box", "A round straw archery butt with painted rings on a wooden stand.", ["target", "butt", "bow range", "training"]),
    "prop_backstop": ("props", "archery backstop", "fence", "box", "A wooden board wall that stops stray arrows behind targets.", ["backboard", "range wall", "training"]),
    "prop_banner_mages": ("props", "mages banner", "signage", "none", "A hanging purple guild banner of the mages' quarter.", ["flag", "guild banner", "pennant", "mages"]),
    "prop_banner_warriors": ("props", "warriors banner", "signage", "none", "A hanging red guild banner of the warriors' quarter.", ["flag", "guild banner", "pennant", "warriors"]),
    "prop_basket": ("props", "basket", "prop", "box", "A woven wicker basket of goods for market stalls and doorsteps.", ["wicker basket", "hamper", "market goods"]),
    "prop_beehive": ("props", "beehive", "prop", "box", "A domed straw skep beehive on a stand, for gardens and herbalists.", ["skep", "bee skep", "hive", "garden"]),
    "prop_bench": ("props", "bench", "furniture", "box", "A plain wooden bench, the cheapest seat in the city.", ["seat", "plank bench", "pew"]),
    "prop_bench_park": ("props", "park bench", "furniture", "box", "A park bench with a backrest for squares and gardens.", ["seat", "garden bench", "backrest bench"]),
    "prop_brass_star": ("props", "brass star", "building-part", "none", "A small brass star ornament for doors and facades.", ["ornament", "star", "decoration"]),
    "prop_chimney": ("props", "chimney", "building-part", "box", "A square stone chimney stack with a cap, set on roofs.", ["chimney stack", "flue", "roof"]),
    "prop_coal_sacks": ("props", "coal sacks", "prop", "box", "A pile of filled coal sacks beside a forge.", ["sacks", "bags", "smithy", "fuel"]),
    "prop_crystal_finial": ("props", "crystal finial", "building-part", "none", "A glowing crystal spike that tops the mages' towers and posts.", ["finial", "crystal", "magic", "mages"]),
    "prop_fence": ("props", "fence", "fence", "box", "A short wooden post-and-rail fence section.", ["rail fence", "paddock fence", "fencing"]),
    "prop_floating_lantern": ("props", "floating lantern", "lamp", "none", "A small paper lantern that hovers in the mages' quarter.", ["lantern", "magic light", "sky lantern", "mages"]),
    "prop_forge_mouth": ("props", "forge mouth", "building-part", "none", "The arched glowing mouth of a smithy forge, set into a wall.", ["forge", "furnace", "smithy", "hearth"]),
    "prop_fountain": ("props", "fountain", "landmark", "mesh", "The market fountain: a stone basin with an upper bowl, a square's centrepiece.", ["water fountain", "basin", "market fountain", "square"]),
    "prop_grindstone": ("props", "grindstone", "tool", "box", "A round sharpening stone on a wooden frame with a crank.", ["whetstone", "sharpening wheel", "smithy"]),
    "prop_herb_bundles": ("props", "herb bundles", "prop", "none", "Bundles of drying herbs hung from a rail, for herbalists.", ["dried herbs", "herbs", "herbalist", "apothecary"]),
    "prop_hitching_rail": ("props", "hitching rail", "fence", "box", "A wooden rail on posts where riders tie their horses.", ["hitching post", "tie rail", "horse rail", "stable"]),
    "prop_iron_stack": ("props", "iron bar stack", "prop", "box", "A stack of iron bars and ingots outside a smithy.", ["ingots", "metal bars", "smithy", "materials"]),
    "prop_judges_box": ("props", "judges' box", "furniture", "box", "A raised wooden judges' box beside a tourney ground.", ["judges stand", "booth", "tourney", "training ground"]),
    "prop_lamp": ("props", "street lamp", "lamp", "box", "An iron street lamp on a post, lit at night; the city's standard lamp.", ["lamppost", "lantern post", "street light"]),
    "prop_lamp_herbal": ("props", "herbal lamp", "lamp", "box", "A street lamp in the herbalists' style with a green-tinted lantern.", ["lamppost", "street light", "herbalists"]),
    "prop_lamp_torch": ("props", "torch post", "lamp", "box", "A wooden post with a burning torch, for the warriors' quarter and rough roads.", ["torch", "brazier post", "fire light", "warriors"]),
    "prop_manikin": ("props", "manikin", "prop", "box", "A tailor's or armourer's wooden manikin on a stand.", ["mannequin", "dummy", "armour stand", "tailor"]),
    "prop_mascherone": ("props", "mascherone", "building-part", "none", "A carved stone face mask (fountain spout) for walls and fountains.", ["stone mask", "spout", "carved face", "gargoyle"]),
    "prop_notice_board": ("props", "notice board", "signage", "box", "A roofed wooden notice board with pinned papers.", ["bulletin board", "quest board", "posting board"]),
    "prop_planter": ("props", "planter", "flower", "box", "A wooden planter box of flowers for doorsteps and squares.", ["flower box", "window box", "flowers", "garden"]),
    "prop_quench_barrel": ("props", "quench barrel", "prop", "box", "A water barrel beside an anvil where smiths quench hot iron.", ["barrel", "water barrel", "smithy"]),
    "prop_quintain": ("props", "quintain", "prop", "box", "A jousting quintain: a pivoting arm with a shield on a post.", ["jousting target", "tilting post", "training", "tourney"]),
    "prop_rune_stone": ("props", "rune stone", "rock", "box", "A standing stone carved with glowing runes, for the mages' quarter.", ["standing stone", "menhir", "runestone", "magic"]),
    "prop_scroll_rack": ("props", "scroll rack", "furniture", "box", "A wooden rack of rolled scrolls for libraries and mages.", ["shelf", "scroll shelf", "library", "bookcase"]),
    "prop_sparring_ring": ("props", "sparring ring", "fence", "mesh", "A low wooden ring of rails marking a sparring ground.", ["arena", "fighting ring", "training ground"]),
    "prop_stall": ("props", "market stall", "furniture", "box", "A wooden market stall with a striped awning and counter.", ["stand", "booth", "market", "shop stall", "vendor"]),
    "prop_street_plaque": ("props", "street plaque", "signage", "none", "A small wall plaque with a street name.", ["street sign", "name plate", "sign"]),
    "prop_tilt_barrier": ("props", "tilt barrier", "fence", "box", "A long low tilt barrier that separates jousting riders.", ["tilt", "jousting barrier", "list", "tourney"]),
    "prop_training_dummy": ("props", "training dummy", "prop", "box", "A straw-stuffed training dummy on a post.", ["dummy", "practice dummy", "target", "training"]),
    "prop_trophy_shield": ("props", "trophy shield", "prop", "none", "A painted shield trophy for walls and halls.", ["shield", "heraldry", "wall shield", "trophy"]),
    "prop_viewing_stand": ("props", "viewing stand", "furniture", "box", "A small tiered wooden viewing stand for spectators.", ["bleachers", "stands", "grandstand", "tourney"]),
    "prop_wall_lantern": ("props", "wall lantern", "lamp", "none", "An iron lantern on a wall bracket, for doors and lanes.", ["lantern", "wall lamp", "sconce"]),
    "prop_wall_rack": ("props", "wall rack", "furniture", "none", "A wall-mounted wooden rack of tools or goods.", ["rack", "shelf", "tool rack"]),
    "prop_weapon_rack": ("props", "weapon rack", "furniture", "box", "A standing rack of swords, spears and shields.", ["arms rack", "armoury", "swords", "warriors"]),
    "prop_weathervane": ("props", "weathervane", "building-part", "none", "An iron weathervane for roof ridges and towers.", ["wind vane", "weather cock", "roof"]),
    "prop_well": ("props", "well", "landmark", "mesh", "A round stone well with a wooden roof, rope and bucket.", ["water well", "wishing well", "village well"]),
}

# export_city_mounts.gd name -> (category, collision, place scale, description, synonyms).
# LOD1/LOD2 rows ("<name> lodN") take their base row's words; the base row lists them as
# tier variants (WorldTiers: low = the package file, medium/high = tiers/<tier>/<path>).
MOUNT_WORDS = {
    "griffin": ("mythical", "box", 1.0,
        "The city's riding griffin: an eagle's head, wings and forelegs on a lion's body, skinned "
        "(34 bones), painted feather and fur atlas with a baked normal map, feather cards cut out; "
        "the code-built head with a hooked beak and ear tufts. Three LODs for the three tiers.",
        ["gryphon", "griffon", "eagle lion", "mount", "flying mount", "hero creature"]),
    "bronze wyrm": ("mythical", "box", 0.16,
        "A stabled dragon breed: lean, teal-green with golden belly plates, swept horns and wings "
        "raised high; skinned on the young dragon's rig, painted atlas, the city's code-built skull.",
        ["dragon", "wyrm", "teal dragon", "mount", "stable dragon", "flying mount", "dragon breed"]),
    "copper runner": ("mythical", "box", 0.16,
        "A stabled dragon breed: copper-red, lean and wiry, tall pale-orange wings and a spiny back "
        "ridge; skinned on the young dragon's rig, painted atlas, the city's code-built skull.",
        ["dragon", "red dragon", "drake", "mount", "stable dragon", "flying mount", "dragon breed"]),
    "teal drake": ("mythical", "box", 0.16,
        "A stabled dragon breed: a stocky teal drake with a finned back; skinned on the young "
        "dragon's rig, painted atlas, the city's code-built skull.",
        ["dragon", "drake", "blue dragon", "mount", "stable dragon", "flying mount", "dragon breed"]),
    "giant eagle": ("bird", "box", 1.0,
        "The city's giant riding eagle: white head, brown wings with spread primaries, skinned "
        "(23 bones), painted feathers; the code-built head (the city's own generated head is not "
        "shipped, its licence is unconfirmed).",
        ["eagle", "great eagle", "roc", "bird of prey", "mount", "flying mount", "hero creature"]),
}

# Models the city draws at another scale than the file (scene.json objects "scale"):
# the stable dragon is the great dragon's rig at Whelp.SIZE, the guardian at Dragon.SIZE.
PLACE_SCALE = {"MOUNT_stable_dragon": 0.16, "guardian_dragon": 1.35}


def glb_json(b: bytes) -> dict:
    if b[:4] != b"glTF":
        raise ValueError("not a GLB")
    n = struct.unpack("<I", b[12:16])[0]
    return json.loads(b[20:20 + n])


def _mat(node: dict) -> list:
    """4x4 column-major (glTF) local matrix of a node."""
    if "matrix" in node:
        return list(node["matrix"])
    t = node.get("translation", [0, 0, 0])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    r = [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w),
         2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w),
         2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)]
    return [r[0] * s[0], r[1] * s[0], r[2] * s[0], 0, r[3] * s[1], r[4] * s[1], r[5] * s[1], 0,
            r[6] * s[2], r[7] * s[2], r[8] * s[2], 0, t[0], t[1], t[2], 1]


def _mul(a: list, b: list) -> list:
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def _apply(m: list, p) -> tuple:
    return tuple(m[r] * p[0] + m[4 + r] * p[1] + m[8 + r] * p[2] + m[12 + r] for r in range(3))


def measure(b: bytes) -> dict:
    """Triangles (every mesh instance counted), bounding size in metres, skins, animations, images."""
    j = glb_json(b)
    acc = j.get("accessors", [])
    tris = 0
    lo, hi = [float("inf")] * 3, [float("-inf")] * 3

    def visit(i: int, parent: list) -> None:
        nonlocal tris
        node = j["nodes"][i]
        # a skinned mesh is drawn in skeleton space: glTF ignores the mesh node's own transform
        m = _mul(parent, _mat(node))
        if "mesh" in node:
            xf = parent if "skin" in node else m
            for p in j["meshes"][node["mesh"]]["primitives"]:
                if p.get("mode", 4) != 4:
                    continue
                count = acc[p["indices"]]["count"] if "indices" in p else acc[p["attributes"]["POSITION"]]["count"]
                tris += count // 3
                pa = acc[p["attributes"]["POSITION"]]
                if "min" in pa and "max" in pa:
                    for cx in (pa["min"][0], pa["max"][0]):
                        for cy in (pa["min"][1], pa["max"][1]):
                            for cz in (pa["min"][2], pa["max"][2]):
                                q = _apply(xf, (cx, cy, cz))
                                for k in range(3):
                                    lo[k] = min(lo[k], q[k])
                                    hi[k] = max(hi[k], q[k])
        for c in node.get("children", []):
            visit(c, m)

    ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    scene = j.get("scenes", [{}])[j.get("scene", 0)]
    for r in scene.get("nodes", []):
        visit(r, ident)
    size = [round(hi[k] - lo[k], 2) for k in range(3)] if lo[0] != float("inf") else None
    return {"triangles": tris, "size": size,
            "skinned": bool(j.get("skins")), "animations": [a.get("name", "") for a in j.get("animations", [])],
            "images": len(j.get("images", [])),
            "physics_body": "OMI_physics_body" in j.get("extensionsUsed", [])}


def import_from(models_repo: Path) -> int:
    index = json.loads((models_repo / "models.json").read_text(encoding="utf-8"))["models"]
    commit = ""
    head = models_repo / ".git" / "HEAD"
    if head.is_file():
        ref = head.read_text().strip()
        if ref.startswith("ref: "):
            rp = models_repo / ".git" / ref[5:]
            commit = rp.read_text().strip()[:8] if rp.is_file() else ""
        else:
            commit = ref[:8]
    rows, bad = [], []
    for mid, (folder, name, cat, coll, desc, syn) in PICK.items():
        rec = index.get(mid)
        if rec is None:
            bad.append("%s: not in models.json" % mid)
            continue
        src = models_repo / rec["file"]
        b = src.read_bytes()
        m = measure(b)
        if rec.get("triangles") is not None and int(rec["triangles"]) != m["triangles"]:
            # models.json counts the builder's opaque mesh; the file also holds effect cards
            # (fountain splash, water). The file's own count is what a world pays for.
            print("note %s: models.json says %s triangles, the file has %d (kept the file's count)"
                  % (mid, rec["triangles"], m["triangles"]))
        fname = "_".join(name.replace("'", "").split()) + ".glb"
        dst = HERE / folder / fname
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        rows.append({
            "models_id": mid, "file": "%s/%s" % (folder, fname), "name": name, "category": cat,
            "description": desc, "synonyms": syn, "collision": coll,
            "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b),
            "place_scale": PLACE_SCALE.get(mid, 1.0),
            "triangles": m["triangles"], "models_json_triangles": rec.get("triangles"), "size": m["size"], "skinned": m["skinned"],
            "animations": m["animations"], "images": m["images"], "physics_body": m["physics_body"],
            "builder": rec.get("builder", "MpProps.sample" if mid.startswith("prop_") else ""),
            "builder_commit": rec.get("builder_commit", ""),
            "cite": "the iamar-models mesh archive (not public) %s %s (the iamar browser source (not public) %s)" % (commit, rec["file"], rec.get("builder_commit", "")),
        })
    for line in bad:
        print("IMPORT ERROR " + line, file=sys.stderr)
    if bad:
        return 1
    rows.sort(key=lambda r: r["file"])
    SOURCE.write_text(json.dumps({
        "format": "iamar-catalog-city-models", "version": 1,
        "note": "The city's single-object exports, copied from the iamar-models mesh archive (not public) by "
                "kit/catalog/assets/import_city_models.py. Files live in kit/catalog/assets/<file>. "
                "Never edit by hand: rerun the import.",
        "models_commit": commit, "licence": LICENCE, "models": rows}, indent=1) + "\n", encoding="utf-8")
    print("imported %d models (%d bytes) from iamar-models %s" % (len(rows), sum(r["bytes"] for r in rows), commit))
    return 0


def piece_rows() -> list:
    """sources/pieces_export.json (written by export_city_pieces.gd) as city_models.json rows,
    each file measured here like the iamar-models imports."""
    src = json.loads(PIECES_EXPORT.read_text(encoding="utf-8"))
    rows = []
    for r in src["pieces"]:
        b = (HERE / r["file"]).read_bytes()
        m = measure(b)
        if m["triangles"] != int(r["triangles"]):
            raise SystemExit("%s: %d triangles in the file, the export says %s" % (r["file"], m["triangles"], r["triangles"]))
        rows.append({
            "models_id": None, "export": True, "file": r["file"], "name": r["name"], "category": r["category"],
            "description": r["description"], "synonyms": r["synonyms"], "collision": r["collision"],
            "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b), "place_scale": 1.0,
            "triangles": m["triangles"], "models_json_triangles": None, "size": m["size"], "skinned": m["skinned"],
            "animations": m["animations"], "images": m["images"], "physics_body": m["physics_body"],
            "seats": r.get("seats", []), "culled_faces": r.get("culled_faces", 0),
            **({"painted_bake": r["painted_bake"]} if r.get("painted_bake") else {}),
            "builder": r["builder"], "builder_commit": r["builder_commit"],
            "cite": "the iamar browser source (not public) %s %s (kit/catalog/assets/export_city_pieces.gd)" % (r["builder_commit"], r["builder"]),
        })
    return rows


def measure_pieces() -> int:
    """Write sources/city_pieces.json: the exported pieces measured, city_models.json's row format."""
    rows = sorted(piece_rows(), key=lambda r: r["file"])
    commit = json.loads(PIECES_EXPORT.read_text(encoding="utf-8")).get("iamar_commit", "")
    PIECES.write_text(json.dumps({
        "format": "iamar-catalog-city-models", "version": 1,
        "note": "Single pieces of the city's furniture, crops and flora, exported from the iamar browser source (not public)'s "
                "builders by kit/catalog/assets/export_city_pieces.gd and measured by "
                "import_city_models.py --pieces. Files live in kit/catalog/assets/<file>. Never edit by hand.",
        "iamar_commit": commit, "licence": LICENCE, "models": rows}, indent=1) + "\n", encoding="utf-8")
    print("measured %d exported pieces (%d bytes) from the iamar browser source (not public) %s" % (len(rows), sum(r["bytes"] for r in rows), commit))
    return 0


def mount_rows() -> list:
    """sources/mounts_export.json (written by export_city_mounts.gd) as city_models.json rows,
    each file measured here; the LOD0 row carries lod1..lodN triangles and tier variants."""
    src = json.loads(MOUNTS_EXPORT.read_text(encoding="utf-8"))
    rows, base = [], {}
    for r in src["mounts"]:
        b = (HERE / r["file"]).read_bytes()
        m = measure(b)
        if m["triangles"] != int(r["triangles"]):
            raise SystemExit("%s: %d triangles in the file, the export says %s" % (r["file"], m["triangles"], r["triangles"]))
        lod = int(r.get("lod", 0))
        key = r["name"] if lod == 0 else r["name"].rsplit(" lod", 1)[0]
        cat, coll, scale, desc, syn = MOUNT_WORDS[key]
        if lod:
            desc = "LOD%d of the %s (%d triangles, %d px albedo%s): the %s tier file of the LOD0 entry. %s" % (
                lod, key, m["triangles"], r["albedo_px"],
                ", %d px normal map" % r["normal_px"] if r.get("normal_px") else ", no normal map",
                {1: "medium", 2: "low"}.get(lod, "low"), desc)
        row = {
            "models_id": None, "export": True, "file": r["file"], "name": r["name"], "category": cat,
            "description": desc, "synonyms": syn if lod == 0 else [key] + syn, "collision": coll,
            "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b), "place_scale": scale,
            "triangles": m["triangles"], "models_json_triangles": None, "size": m["size"], "skinned": m["skinned"],
            "animations": m["animations"], "images": m["images"], "physics_body": m["physics_body"],
            "lod": lod, "albedo_px": r["albedo_px"], "normal_px": r["normal_px"],
            "builder": r["builder"], "builder_commit": r["builder_commit"],
            "cite": "the iamar browser source (not public) %s %s (kit/catalog/assets/export_city_mounts.gd)" % (r["builder_commit"], r["builder"]),
        }
        rows.append(row)
        base.setdefault(key, []).append(row)
    for key, group in base.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda x: x["lod"])
        top = group[0]
        # the package file is the coarsest LOD (low tier); finer LODs go under tiers/<tier>/
        names = ["high", "medium", "low"][-len(group):] if len(group) <= 3 else None
        if names is None:
            raise SystemExit("%s: more than three LODs" % key)
        top["lods"] = {"lod%d" % g["lod"]: g["triangles"] for g in group}
        top["tier_variants"] = {t: g["sha256"][:16] for t, g in zip(names, group)}
        top["tier_files"] = {t: g["file"] for t, g in zip(names, group)}
        top["bytes_all_lods"] = sum(g["bytes"] for g in group)
    return rows


def measure_mounts() -> int:
    """Write sources/city_mounts.json: the exported mounts measured, city_models.json's row format."""
    rows = sorted(mount_rows(), key=lambda r: r["file"])
    commit = json.loads(MOUNTS_EXPORT.read_text(encoding="utf-8")).get("iamar_commit", "")
    MOUNTS.write_text(json.dumps({
        "format": "iamar-catalog-city-models", "version": 1,
        "note": "The city's griffin (LOD0-2), dragon breeds and giant eagle with code-built heads, exported "
                "from the iamar browser source (not public) by kit/catalog/assets/export_city_mounts.gd and measured by "
                "import_city_models.py --mounts. Files live in kit/catalog/assets/<file>. Never edit by hand.",
        "iamar_commit": commit, "licence": LICENCE, "models": rows}, indent=1) + "\n", encoding="utf-8")
    print("measured %d exported mounts (%d bytes) from the iamar browser source (not public) %s" % (len(rows), sum(r["bytes"] for r in rows), commit))
    return 0


def fold_bake() -> int:
    """Fold sources/painted_bake.json (written by bake_painted.gd) into the props' rows of
    city_models.json: the row then describes the baked file (sha256, bytes, images) and keeps
    the iamar-models copy it was baked from as painted_bake.source_sha256."""
    if not PAINTED.is_file():
        print("no %s: run bake_painted.gd first" % PAINTED.name)
        return 1
    bake = {r["file"]: r for r in json.loads(PAINTED.read_text(encoding="utf-8"))["files"]}
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    errs, folded = [], 0
    for row in src["models"]:
        b_rec = bake.get(row["file"])
        if b_rec is None:
            continue
        pb = row.get("painted_bake")
        if pb and pb.get("sha256") == b_rec["sha256"]:
            continue
        if not pb and row["sha256"] != b_rec["source_sha256"]:
            errs.append("%s: baked from %s but the row records %s (re-import, then bake again)"
                        % (row["file"], b_rec["source_sha256"][:12], row["sha256"][:12]))
            continue
        b = (HERE / row["file"]).read_bytes()
        if hashlib.sha256(b).hexdigest() != b_rec["sha256"]:
            errs.append("%s: the file is not the bake painted_bake.json records" % row["file"])
            continue
        m = measure(b)
        if m["triangles"] != row["triangles"]:
            errs.append("%s: the bake changed the triangles (%d, was %d)" % (row["file"], m["triangles"], row["triangles"]))
            continue
        row["painted_bake"] = {k: b_rec[k] for k in ("source_sha256", "sha256", "atlas", "px_per_m", "charts",
                                                     "patterns", "glow", "baker_commit")}
        if pb:   # a re-bake of a baked row keeps the original copy's hash
            row["painted_bake"]["source_sha256"] = pb["source_sha256"]
        row.update({"sha256": b_rec["sha256"], "bytes": len(b), "images": m["images"]})
        folded += 1
    for e in errs:
        print("BAKED " + e)
    if errs:
        return 1
    SOURCE.write_text(json.dumps(src, indent=1) + "\n", encoding="utf-8")
    print("folded %d painted bakes into %s" % (folded, SOURCE.name))
    return 0


def check() -> int:
    errs = []
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = list(src["models"])
    if PIECES.is_file():   # the exported pieces, same row format
        rows += json.loads(PIECES.read_text(encoding="utf-8"))["models"]
    if MOUNTS.is_file():   # the exported mounts, same row format
        rows += json.loads(MOUNTS.read_text(encoding="utf-8"))["models"]
    buildings = CATALOG_DIR / "sources" / "city_buildings.json"   # import_city_buildings.py (also --check there)
    if buildings.is_file():
        rows += json.loads(buildings.read_text(encoding="utf-8"))["models"]
    seen = set()
    for r in rows:
        p = HERE / r["file"]
        seen.add(p.resolve())
        if not p.is_file():
            errs.append("%s: file missing" % r["file"])
            continue
        b = p.read_bytes()
        if hashlib.sha256(b).hexdigest() != r["sha256"]:
            errs.append("%s: sha256 differs from its record (rerun the import or --pieces)" % r["file"])
        m = measure(b)
        if m["triangles"] != r["triangles"]:
            errs.append("%s: %d triangles, record says %d" % (r["file"], m["triangles"], r["triangles"]))
        if r["file"].split("/")[0] in PAINTED_FOLDERS and not r.get("painted_bake"):
            errs.append("%s: flat vertex colour, the city's painted look not baked (bake_painted.gd, then --baked)" % r["file"])
    # files another source records (harbour.json, city_buildings_closed.json, ...) are not orphans;
    # their own --check (harbour.py, close_open_sides.py) checks their hashes
    for other in sorted((CATALOG_DIR / "sources").glob("*.json")):
        models = json.loads(other.read_text(encoding="utf-8")).get("models")
        if isinstance(models, list):
            seen.update((HERE / r["file"]).resolve() for r in models if isinstance(r, dict) and r.get("file"))
    for p in HERE.rglob("*.glb"):
        # creatures/insects/ are made by export_insects.gd and checked by insects.py --check
        if p.resolve() not in seen and p.parent.name != "insects":
            errs.append("%s: GLB in kit/catalog/assets with no record in sources/city_models.json" % p.relative_to(HERE))
    for e in errs:
        print("CHECK " + e)
    print("city models: %d records, %s" % (len(rows), "OK" if not errs else "%d problems" % len(errs)))
    return 1 if errs else 0


def main(argv: list) -> int:
    if argv[:1] == ["--check"]:
        return check()
    if argv[:1] == ["--baked"]:
        return fold_bake()
    if argv[:1] == ["--pieces"]:
        return measure_pieces()
    if argv[:1] == ["--mounts"]:
        return measure_mounts()
    if len(argv) != 1:
        print(__doc__)
        return 2
    return import_from(Path(argv[0]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
