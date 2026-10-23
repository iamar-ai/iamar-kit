#!/usr/bin/env python3
"""Copy representative iamar city buildings (houses and shops per quarter) and reusable landmarks
(gatehouses, bridge, gazebo, temple, statues ...) from an the iamar-models mesh archive (not public) checkout into
kit/catalog/assets/{buildings,landmarks}/ and record them in kit/catalog/sources/city_buildings.json.

  python3 kit/catalog/assets/import_city_buildings.py <iamar-models checkout> <city-masterplan.json>...
  python3 kit/catalog/assets/import_city_buildings.py --check

Each <city-masterplan.json> is the iamar browser source (not public) worlds/oakhaven_masterplan/city-masterplan.json at a
commit the models were built from; a house is measured against the plan whose sha256 equals its
models.json "plan_sha256" (iamar-models 0d15ab92 needs the plans of the iamar browser source (not public) 75f3268,
da40a302 and aa1ea196: `git show <commit>:worlds/oakhaven_masterplan/city-masterplan.json`).

The city places these files where they stand in the plan (vertices in city coordinates), so
each copy is re-centred: the root node is moved so the footprint centre sits at x = z = 0 and
the ground at y = 0 ("pivot bottom-centre", like every other catalogue model). The city's
mesh data is kept; a house gets back sides on its single-sheet trim (seal_trim_edges.py, so it
passes 'audit closure' standing alone), and the record keeps the source file's sha256 and the
offset applied.

Terraced city houses are built against their neighbours, and the city never builds a wall
nobody sees (per-face culling, a mandatory build rule), so a house taken out of its row has an
OPEN side where the party wall was. This script measures each footprint side of each house
(outward-facing wall area at ground-floor height against the side's length, from the plan's
footprint) and records the open sides, so the catalogue entry and its use line say where to
put a neighbour or a wall. Houses with no open side are preferred where a quarter has one.

Left out on purpose (README.md "Not imported"): landmarks over the selection's 25k-triangle bar
(the bank), the gate figures and South Gate statues made with Hunyuan3D (licence unconfirmed),
city-wide pieces (walls, moat, ground tiles).
Python 3.8+, standard library only.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from import_city_models import glb_json, measure  # noqa: E402  (same folder)
from seal_trim_edges import seal  # noqa: E402

CATALOG_DIR = HERE.parent
SOURCE = CATALOG_DIR / "sources" / "city_buildings.json"
LICENCE = "CC0-1.0"   # kit/inventory/licences.json original-procedural (an internal task)
STATUE_LICENCE = "CC0-1.0"   # posed from the CC0 Quaternius Universal Base Characters body

QUARTERS = {   # plan district_id -> (style tag, how the quarter looks in these files)
    "CIVIC": ("iamar city: civic heart", "the civic heart (homes and crafts): white plaster, dark timber frames, blue-slate roofs"),
    "DIST_H": ("iamar city: herbalists' quarter", "the herbalists' and healers' quarter: cream walls, ochre roofs, flower boxes"),
    "DIST_M": ("iamar city: mages' quarter", "the mages' quarter: pale walls with violet trim, tall blue roofs"),
    "DIST_W": ("iamar city: warriors' quarter", "the warriors' quarter: dark timber frames over grey stone, dark slate roofs"),
}

# models.json id -> (folder, name, category, description, synonyms, ground_y)
# Descriptions say what the file shows (checked against renders from four sides) and how the
# city uses it. ground_y: the city ground in the file's own coordinates when the foundation
# reaches below it (gatehouses stand in the moat, the bridge spans it); None = lowest vertex.
PICK = {
    # houses and shops, one of each per quarter; open sides are measured and added by the import
    "B124": ("buildings", "civic heart house", "building",
        "A two-storey town house with an L-shaped plan, half-timbered upper floor and a hipped roof with a chimney; closed on every side, so it stands alone.",
        ["house", "home", "town house", "dwelling", "residence", "half-timbered house"], None),
    "B055": ("buildings", "civic heart healer's shop", "building",
        "A two-storey healer's shop with a shop door, half-timbered walls, a gabled dormer and a hipped roof; closed on every side, so it stands alone.",
        ["shop", "healer", "apothecary", "clinic", "store", "half-timbered house"], None),
    "B107": ("buildings", "herbalists' quarter house", "building",
        "A two-storey house with a steep gable, timber frame, green shutters and flower boxes under the windows.",
        ["house", "home", "town house", "dwelling", "terraced house", "row house"], None),
    "B106": ("buildings", "herbalists' quarter healer's shop", "building",
        "A two-storey healer's shop with a front gable and dormer, shop windows, flower boxes and a broad roof.",
        ["shop", "healer", "apothecary", "herbalist", "store", "row house"], None),
    "B053": ("buildings", "mages' quarter house", "building",
        "A tall three-storey house with a steep front gable, rows of small framed windows and a high blue roof.",
        ["house", "home", "tall house", "dwelling", "magic", "terraced house"], None),
    "B033": ("buildings", "mages' quarter workshop", "building",
        "A narrow three-storey workshop (the plan's arcane smith) with a pointed blue roof and a chimney.",
        ["shop", "smith", "workshop", "magic shop", "store", "narrow house"], None),
    "B105": ("buildings", "warriors' quarter house", "building",
        "A two-storey house with a stone ground floor, dark timber frame above, a chimney and a dark slate roof.",
        ["house", "home", "town house", "dwelling", "terraced house", "row house"], None),
    "B069": ("buildings", "warriors' quarter cobbler", "building",
        "A two-storey cobbler's shop with a bay corner, dark timber frame over stone, a front gable and a slate roof.",
        ["shop", "cobbler", "shoemaker", "store", "workshop", "row house"], None),
    # landmarks
    "GZ01": ("landmarks", "community gazebo", "landmark",
        "A round open gazebo: white columns on a raised round platform under a red conical roof with a gilded finial, 13 m across; the city's community meeting place.",
        ["gazebo", "pavilion", "bandstand", "rotunda", "meeting place", "square"], None),
    "C05": ("landmarks", "the temple", "landmark",
        "A long classical temple ringed by white columns under a low roof, 33 by 30 m (the city's temple, without its statue).",
        ["temple", "shrine", "sanctuary", "colonnade", "classical temple", "columns"], None),
    "AMP01": ("landmarks", "amphitheatre", "landmark",
        "A small open-air amphitheatre: curved stone tiers inside an arcaded outer wall around a wooden stage with red banners on poles, 25 m across.",
        ["amphitheater", "theatre", "theater", "arena", "stage", "auditorium"], None),
    "S01": ("landmarks", "horse stable", "landmark",
        "A long horse stable: a row of open stalls under a broad blue-slate roof with a tack room at one end, 32 m long.",
        ["stable", "stables", "barn", "horse barn", "stalls", "livery"], None),
    "GRAND_MASCHERONE": ("landmarks", "grand mascherone fountain", "landmark",
        "A grand wall fountain: a carved stone face (mascherone) in an ornate frame spouting into a round basin on a stepped stone platform.",
        ["wall fountain", "fountain", "stone face", "mask fountain", "spout", "basin"], None),
    "GATEHOUSE_1": ("landmarks", "grand gatehouse", "gate",
        "The city's grand South Gate: twin round towers with blue conical spires, battlements, blue-and-gold banners and a tall arched gateway; 46 m above ground, its foundation reaching 5 m into the moat.",
        ["gate", "gatehouse", "city gate", "castle gate", "towers", "castle"], 0.0),
    "GATEHOUSE_2": ("landmarks", "gatehouse", "gate",
        "A side gatehouse of the city wall: tall stone towers under two blue conical roofs with a gate passage, 34 m above ground, its foundation reaching 4 m into the moat.",
        ["gate", "gatehouse", "city gate", "gate tower", "tower", "wall gate"], 0.0),
    "BRIDGE_1": ("landmarks", "stone causeway bridge", "bridge",
        "The South Gate's long stone causeway: a flat paved deck with low parapets that widens in the middle, on a stone pier; 57 m long and 31 m at its widest.",
        ["bridge", "stone bridge", "causeway", "moat bridge", "crossing", "viaduct"], 0.0),
    "STATUE_BRIDGE_1": ("landmarks", "statue plinth", "statue",
        "A plain round two-step stone plinth (pedestal), 2.9 m across, ready for any statue on top.",
        ["plinth", "pedestal", "statue base", "column base", "monument base"], None),
    "HERO_E1": ("landmarks", "hero statue with spear and shield", "statue",
        "A pale carved-stone warrior holding a tall spear and a round shield, 5.4 m to the spear tip; one of the heroes lining the South Gate bridge.",
        ["statue", "monument", "sculpture", "warrior", "stone figure", "spearman"], None),
    "HERO_W1": ("landmarks", "hero statue with sword", "statue",
        "A pale carved-stone knight in armour and a long cloak resting on a sword, 3.3 m tall; one of the heroes lining the South Gate bridge.",
        ["statue", "monument", "sculpture", "knight", "stone figure", "memorial"], None),
    # PUB6 batch 1 (an internal task): one shop or house per quarter and purpose the catalogue lacked
    # (kit/catalog/public_selection.json), descriptions checked against renders from four sides.
    # B003, the selection's first mages' curio shop, is left out: a sliver of a terrace house whose
    # +z party wall the import does not detect, so even its closed variant stays open (audit edge
    # +x, +z); B008 stands for the quarter's curio shops instead
    "B001": ("buildings", "warriors' quarter bird supply shop", "building",
        "A large two-storey corner shop on an L-shaped plan: whitewashed walls in a dark timber frame, red-brown window frames, two shop doors and broad hipped slate roofs with dormers and a chimney.",
        ["shop", "bird shop", "pet shop", "corner shop", "store", "half-timbered house"], None),
    "B008": ("buildings", "mages' quarter curio shop", "building",
        "A long two-storey curio shop: pale walls in a timber frame with violet trim, small framed windows, a shop door under a front gable, a dormer and broad blue hipped roofs with a chimney.",
        ["shop", "curio shop", "curiosities", "antiques", "magic shop", "store"], None),
    "B005": ("buildings", "mages' quarter wandmaker", "building",
        "A three-storey wandmaker's shop on an L-shaped plan: pale walls with violet string courses, ochre window surrounds, a shop door and a blue hipped roof with a chimney.",
        ["shop", "wand shop", "wandmaker", "magic shop", "store", "town house"], None),
    "B007": ("buildings", "warriors' quarter smithy", "building",
        "A two-storey smithy with an attic: plaster walls in a dark timber frame with cross braces, small red-framed windows, a hipped slate roof and two chimneys.",
        ["shop", "smith", "smithy", "blacksmith", "workshop", "half-timbered house"], None),
    "B021": ("buildings", "warriors' quarter blacksmith forge", "building",
        "A long two-storey forge: plaster walls with red-framed windows, an open timber arcade along the ground floor where the work is done, a hipped slate roof with a dormer; the city's working forge.",
        ["forge", "blacksmith", "smithy", "workshop", "smith", "ironworks"], None),
    "B023": ("buildings", "warriors' quarter bakery", "building",
        "A three-storey bakery with a half-timbered front (cross-braced panels), red window frames, a shop door, a gabled dormer and a slate roof with a chimney.",
        ["shop", "bakery", "baker", "bakehouse", "store", "half-timbered house"], None),
    "B024": ("buildings", "mages' quarter tailor", "building",
        "A tall three-storey tailor's shop: pale walls with violet trim, arched ground-floor doors, a bay window and a very steep blue hipped roof with dormers and a chimney.",
        ["shop", "tailor", "dressmaker", "clothier", "store", "tall house"], None),
    "B028": ("buildings", "herbalists' quarter armourer", "building",
        "A three-storey armourer's shop with a rounded corner bay: cream walls, green shutters, flower boxes under the windows and a broad ochre hipped roof with a chimney.",
        ["shop", "armourer", "armory", "armoury", "store", "corner house"], None),
    "B029": ("buildings", "herbalists' quarter bakery", "building",
        "A three-storey corner bakery: cream walls, green shutters and flower boxes, a canted corner bay and an ochre hipped roof with chimneys.",
        ["shop", "bakery", "baker", "bakehouse", "store", "corner house"], None),
    "B036": ("buildings", "mages' quarter rune carver", "building",
        "A three-storey rune carver's shop: pale walls with violet string courses, a canted corner, an arched shop window and a blue hipped roof with two chimneys.",
        ["shop", "rune carver", "runes", "magic shop", "stone carver", "store"], None),
    "B038": ("buildings", "herbalists' quarter bookshop", "building",
        "A small single-storey bookshop under a tall ochre pyramid roof: a half-timbered front gable, wide shop windows, a deep open entrance porch and a bench outside.",
        ["shop", "bookshop", "bookseller", "books", "library", "cottage"], None),
    "B039": ("buildings", "civic heart jousting supplies", "building",
        "A long two-storey shop on an irregular plan: white plaster with dark frames, a polygonal corner tower with a pointed spire, dormers and a blue slate roof; the city's jousting supply store.",
        ["shop", "jousting", "tack shop", "saddler", "store", "tower house"], None),
    "B043": ("buildings", "warriors' quarter wandmaker", "building",
        "A three-storey wandmaker's shop: grey-green plaster in a dark timber frame, a first-floor bay window, arched doors, dormers in a slate hipped roof and a chimney.",
        ["shop", "wandmaker", "magic shop", "store", "town house", "half-timbered house"], None),
    "B046": ("buildings", "mages' quarter armourer", "building",
        "A narrow three-storey armourer's shop, 5.6 m wide: pale walls, a shop window, a dormer in a steep blue hipped roof; built into a terrace between two neighbours.",
        ["shop", "armourer", "armory", "narrow house", "store", "terraced house"], None),
    "B051": ("buildings", "warriors' quarter weaponsmith", "building",
        "A long, shallow single-storey weaponsmith's shop (10 by 2.6 m): wide shop windows, a central door, a gabled dormer and a slate roof; a lean shopfront for a market row.",
        ["shop", "weaponsmith", "weapons", "armory", "market shop", "shopfront"], None),
    "B052": ("buildings", "warriors' quarter armourer", "building",
        "A long, very shallow three-storey frontage (19.5 by 2.8 m): rows of red-framed windows, a half-timbered gable, two shop doors and a slate roof; a street facade for a row.",
        ["shop", "armourer", "facade", "street front", "row house", "terraced house"], None),
    "B056": ("buildings", "civic heart town house", "building",
        "A two-storey town house with a cross-gabled dormer, two front doors and a blue hipped roof; its other walls are plain, as neighbours stood against them.",
        ["house", "home", "town house", "dwelling", "residence", "terraced house"], None),
    "B067": ("buildings", "warriors' quarter spice seller", "building",
        "A two-storey spice seller's shop with a curved street front: half-timbered upper floor, stone below, gabled dormers and a slate hipped roof.",
        ["shop", "spice seller", "spices", "grocer", "store", "half-timbered house"], None),
    "B084": ("buildings", "civic heart tailor", "building",
        "A single-storey tailor's shop: wide shop windows either side of a timber door, a hipped blue roof with a gabled dormer and a tall chimney.",
        ["shop", "tailor", "clothier", "cottage", "store", "bungalow"], None),
    "B098": ("buildings", "warriors' quarter chandler", "building",
        "A two-storey chandler's shop: plaster walls with red window frames, a half-timbered corner bay, a shop door and a dark hipped slate roof with a chimney.",
        ["shop", "chandler", "candle maker", "candles", "store", "town house"], None),
    "B099": ("buildings", "civic heart toolmaker", "building",
        "A two-storey toolmaker's shop: big ground-floor windows, a half-timbered gabled dormer with a finial and a blue hipped roof.",
        ["shop", "toolmaker", "tools", "hardware", "store", "town house"], None),
    "B120": ("buildings", "herbalists' quarter herbalist", "building",
        "A three-storey herbalist's shop with a bent street front: cream walls, green shutters and flower boxes, shop windows below and an ochre hipped roof.",
        ["shop", "herbalist", "herbs", "apothecary", "healer", "store"], None),
    "B127": ("buildings", "herbalists' quarter toolmaker", "building",
        "A large three-storey corner building: cream walls with dark frames, green shutters on every window, a dormer and broad ochre hipped roofs; the quarter's toolmaker.",
        ["shop", "toolmaker", "tools", "hardware", "corner house", "store"], None),
    "B132": ("buildings", "civic heart bakery", "building",
        "A two-storey bakery with a steep cross gable: half-timbered upper floor, shop windows and doors below, a small balcony and a blue roof.",
        ["shop", "bakery", "baker", "bakehouse", "store", "half-timbered house"], None),
    "B133": ("buildings", "civic heart rune carver", "building",
        "A three-storey rune carver's shop built as a cluster of blocks, each under its own blue hipped roof, with a chimney and a shop door.",
        ["shop", "rune carver", "runes", "stone carver", "store", "town house"], None),
    "B137": ("buildings", "herbalists' quarter arcaded shop row", "building",
        "A two-storey shop row: cream walls, green shutters and flower boxes, round-arched shop loggia on stone piers on the ground floor, gabled dormers and an ochre roof.",
        ["shop", "shop row", "arcade", "loggia", "market hall", "row house"], None),
    "B138": ("buildings", "warriors' quarter cloth merchant", "building",
        "A small two-storey cloth merchant's shop with steep front gables: half-timbered walls, red-framed windows, shop windows below and a slate roof.",
        ["shop", "cloth merchant", "draper", "fabric", "store", "half-timbered house"], None),
    # the remaining CC0 bridge heroes (posed Quaternius base characters baked to stone)
    "HERO_E2": ("landmarks", "statue of a woman holding up an orb", "statue",
        "A pale carved-stone woman in a long gown holding a ringed orb above her head with both hands, 4.1 m tall; one of the heroes lining the South Gate bridge.",
        ["statue", "monument", "sculpture", "woman", "stone figure", "orb", "astronomer"], None),
    "HERO_E3": ("landmarks", "statue of a woman with a flower", "statue",
        "A pale carved-stone woman in a long gown holding out a flower, a satchel of herbs at her hip; one of the heroes lining the South Gate bridge.",
        ["statue", "monument", "sculpture", "woman", "stone figure", "herbalist", "healer"], None),
    "HERO_E4": ("landmarks", "statue of a swordswoman", "statue",
        "A pale carved-stone warrior woman in pauldrons and a long cape, both hands resting on a sword point-down; one of the heroes lining the South Gate bridge.",
        ["statue", "monument", "sculpture", "warrior", "stone figure", "knight", "sword"], None),
    "HERO_E5": ("landmarks", "statue of a scholar with a book", "statue",
        "A pale carved-stone woman in a long gown and hood, one hand raised and an open book in the other; one of the heroes lining the South Gate bridge.",
        ["statue", "monument", "sculpture", "scholar", "stone figure", "mage", "book"], None),
    "HERO_W2": ("landmarks", "statue of a mage with a book", "statue",
        "A pale carved-stone mage in a long gown and hood, one hand raised in a spell and an open book in the other (the twin of the scholar statue across the bridge); one of the heroes lining the South Gate bridge.",
        ["statue", "monument", "sculpture", "mage", "stone figure", "wizard", "book"], None),
    "HERO_W3": ("landmarks", "statue of a huntress with arrows", "statue",
        "A pale carved-stone woman in a long gown holding a sheaf of arrows upright, a basket of fruit on her other arm; one of the heroes lining the South Gate bridge.",
        ["statue", "monument", "sculpture", "huntress", "stone figure", "archer", "harvest"], None),
    "HERO_W4": ("landmarks", "statue of a man with a lantern", "statue",
        "A pale carved-stone man in a cape holding a lantern high, a sword in his other hand; one of the heroes lining the South Gate bridge.",
        ["statue", "monument", "sculpture", "lantern bearer", "stone figure", "watchman", "guide"], None),
    "HERO_W5": ("landmarks", "statue of a spearman with shield", "statue",
        "A pale carved-stone warrior in a cape with a tall spear and a round shield; one of the heroes lining the South Gate bridge.",
        ["statue", "monument", "sculpture", "warrior", "stone figure", "spearman", "guard"], None),
    # PUB6 batch 3 (an internal task): the selection's landmarks (public_selection.json)
    "AQUEDUCT01": ("landmarks", "stone aqueduct", "landmark",
        "A long two-tier aqueduct of pale stone: a row of tall arches carrying a second arcade, 82 m long and 14.5 m above ground, its piers reaching 3.7 m below it (into a river or moat).",
        ["aqueduct", "arcade", "arches", "viaduct", "water channel", "roman bridge"], 0.0),
    "AqueductFalls": ("landmarks", "aqueduct waterfall", "landmark",
        "A waterfall as it pours from the city's aqueduct: a curved sheet of falling water about 9 m high, crossed spray sheets and a foam pool at its foot, with painted water textures; 15 by 10 m.",
        ["waterfall", "falls", "cascade", "water", "spray", "fountain"], None),
    "B058": ("landmarks", "city hall", "landmark",
        "A three-storey white city hall with rows of blue-shuttered windows under a blue hipped roof, a square clock tower with clock faces, an open belfry and a red flag, and a red-canopied entrance between blue banners; 29 by 13 m, 32 m to the flag.",
        ["city hall", "town hall", "council house", "clock tower", "guildhall", "civic building"], None),
    "B082": ("landmarks", "trading hall", "landmark",
        "A white trading hall in two wings under blue roofs with a tall bell tower and pointed blue spire, a green market awning at its side; 24 by 14 m, 38 m to the spire.",
        ["trading hall", "exchange", "market hall", "guild hall", "bell tower", "merchants"], None),
    "BIRD01": ("landmarks", "giant-bird aerie", "landmark",
        "A long pale hall with arched windows under a slate-blue hipped roof and a round lookout tower crowned by a gallery and a brown conical roof, where giant birds land; a timber porch at one end; 33 by 32 m, 38 m tall.",
        ["aerie", "eyrie", "roost", "bird stable", "tower", "lookout"], None),
    "C01": ("landmarks", "cathedral", "landmark",
        "A gothic cathedral: a long nave under a steep blue roof with pinnacled buttresses and tall arched windows, three spired towers over the west front, a rose window and a pointed arched portal; 61 by 38 m, 66 m tall.",
        ["cathedral", "church", "minster", "abbey", "gothic church", "spires"], None),
    "C02": ("landmarks", "library", "landmark",
        "The city library: a broad three-storey pale stone building under a blue roof with a green copper dome and a portico of white columns at the front; 58 by 76 m, 42 m tall.",
        ["library", "dome", "academy", "museum", "archive", "hall"], None),
    "C03": ("landmarks", "inn and tavern", "landmark",
        "A large two-storey inn and tavern: pale walls with rows of warmly lit windows under a broad slate roof with chimneys, an entrance with a hanging sign; 40 by 31 m.",
        ["inn", "tavern", "pub", "hostel", "alehouse", "lodging"], None),
    "C04": ("landmarks", "mage school", "landmark",
        "A mage school like a fairy-tale palace: white wings with rows of windows under blue roofs and dormers, framed by tall round lilac towers with blue conical roofs; 47 by 23 m, 59 m tall.",
        ["mage school", "wizard school", "academy", "palace", "towers", "magic"], None),
    "CASTLE01": ("landmarks", "castle", "landmark",
        "A great castle: a square curtain wall with crenellated walks and round corner and wall towers under blue conical roofs, a gate with a ramp, and inside a keep and hall with more spired towers; 81 by 87 m, 64 m tall.",
        ["castle", "fortress", "keep", "citadel", "towers", "stronghold"], None),
    "DRAGON01": ("landmarks", "small-dragon stable", "landmark",
        "A long pale stone stable for small dragons under a blue hipped roof: a row of tall stall doors with glowing interiors down one side and a timber-framed open front with big wooden doors; 38 by 26 m, 15 m tall.",
        ["dragon stable", "dragon pen", "stable", "barn", "lair", "stalls"], None),
    "Portal_PORTAL04": ("landmarks", "mage portal ring (open)", "landmark",
        "An upright ring of carved stone blocks 6.7 m across on a low round stone dais, a dark blue veil filling the ring and a light inside it (the city's mage portals; the city adds sparkles).",
        ["portal", "gate", "magic portal", "teleporter", "ring", "archway"], None),
    "W01": ("landmarks", "weapons hall", "landmark",
        "A long two-storey weapons hall bending around a corner: timber-framed pale walls, rows of blue-shuttered windows, a brown hipped roof and an arched stone entrance; 46 by 25 m.",
        ["weapons shop", "armory", "armoury", "weaponsmith", "arms hall", "barracks"], None),
}


# ------------------------------------------------------------------ GLB helpers

def glb_split(b: bytes):
    n = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + n])
    return j, b[20 + n:]   # rest = BIN chunk (header included) or nothing


def glb_join(j: dict, rest: bytes) -> bytes:
    js = json.dumps(j, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + rest
    return struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body


def recentre(b: bytes, offset: list) -> bytes:
    """Move every scene root by offset (city coordinates -> pivot at the origin)."""
    j, rest = glb_split(b)
    scene = j["scenes"][j.get("scene", 0)]
    for r in scene["nodes"]:
        node = j["nodes"][r]
        if "matrix" in node:
            m = node["matrix"]
            m[12] += offset[0]; m[13] += offset[1]; m[14] += offset[2]
        else:
            t = node.get("translation", [0.0, 0.0, 0.0])
            node["translation"] = [round(t[k] + offset[k], 4) for k in range(3)]
    return glb_join(j, rest)


def wrap_root(b: bytes) -> bytes:
    """Put the scene's root under a new empty root node of the same name. The city exports a
    room (and the mage portal ring) as one mesh node that is the scene root (GODOT_single_root);
    loaders that walk only a scene's children (find_children) then miss it: no vertex colours,
    no bounds. A file whose root holds no mesh is returned as it is. The extension
    is dropped (see below)."""
    j, rest = glb_split(b)
    scene = j["scenes"][j.get("scene", 0)]
    if len(scene["nodes"]) != 1 or "mesh" not in j["nodes"][scene["nodes"][0]]:
        return b
    old = j["nodes"][scene["nodes"][0]]
    j["nodes"].append({"name": old.get("name", "room"), "children": [scene["nodes"][0]]})
    old["name"] = old.get("name", "room") + "_mesh"
    scene["nodes"] = [len(j["nodes"]) - 1]
    # GODOT_single_root makes Godot's importer use that root as the scene's root node, and it then
    # drops the root's children: without it Godot adds its own root above the new one
    for k in ("extensionsUsed", "extensionsRequired"):
        if "GODOT_single_root" in j.get(k, []):
            j[k] = [x for x in j[k] if x != "GODOT_single_root"]
            if not j[k]:
                del j[k]
    return glb_join(j, rest)


def bounds(b: bytes):
    """Min and max corner (city coordinates) of every mesh, as measure() walks them."""
    j = glb_json(b)
    from import_city_models import _apply, _mat, _mul
    lo, hi = [math.inf] * 3, [-math.inf] * 3

    def visit(i, parent):
        node = j["nodes"][i]
        m = _mul(parent, _mat(node))
        if "mesh" in node:
            xf = parent if "skin" in node else m
            for p in j["meshes"][node["mesh"]]["primitives"]:
                pa = j["accessors"][p["attributes"]["POSITION"]]
                for cx in (pa["min"][0], pa["max"][0]):
                    for cy in (pa["min"][1], pa["max"][1]):
                        for cz in (pa["min"][2], pa["max"][2]):
                            q = _apply(xf, (cx, cy, cz))
                            for k in range(3):
                                lo[k] = min(lo[k], q[k]); hi[k] = max(hi[k], q[k])
        for c in node.get("children", []):
            visit(c, m)

    ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    for r in j["scenes"][j.get("scene", 0)]["nodes"]:
        visit(r, ident)
    return lo, hi


def triangles_world(b: bytes):
    """Every triangle (skinned meshes skipped) as three (x, y, z) points in file coordinates."""
    from import_city_models import _apply, _mat, _mul
    j, rest = glb_split(b)
    binary = rest[8:]
    fmt = {5126: "f", 5125: "I", 5123: "H", 5121: "B"}
    comps = {"SCALAR": 1, "VEC3": 3}

    def read(i):
        a = j["accessors"][i]
        bv = j["bufferViews"][a["bufferView"]]
        c = comps[a["type"]]
        f = fmt[a["componentType"]]
        size = struct.calcsize("<" + f) * c
        stride = bv.get("byteStride") or size
        o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        return [struct.unpack_from("<" + f * c, binary, o + k * stride) for k in range(a["count"])]

    out = []

    def visit(i, parent):
        n = j["nodes"][i]
        m = _mul(parent, _mat(n))
        if "mesh" in n and "skin" not in n:
            for p in j["meshes"][n["mesh"]]["primitives"]:
                if p.get("mode", 4) != 4:
                    continue
                pos = [_apply(m, q) for q in read(p["attributes"]["POSITION"])]
                idx = [v[0] for v in read(p["indices"])] if "indices" in p else list(range(len(pos)))
                out.extend((pos[idx[k]], pos[idx[k + 1]], pos[idx[k + 2]]) for k in range(0, len(idx) - 2, 3))
        for c in n.get("children", []):
            visit(c, m)

    for r in j["scenes"][j.get("scene", 0)]["nodes"]:
        visit(r, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
    return out


# Sides the measure below misses, found by `iamar-world audit edge` on the file standing alone and
# checked against renders (an internal task): a party wall the city built only in part (the share that
# shows above a lower neighbour), so the side has some wall and is still open at eye height.
# models.json id -> axes of footprint sides to record as open as well.
FORCE_OPEN = {
    "B084": ("+x",),   # the tailor's cottage: rear half open (the 2026-10-20 import dropped it for this)
    "B132": ("-z",),   # the civic bakery: its -z party wall stops short of the ground floor
}


# Landmarks the city built against neighbours or walls (PUB6 batch 3, an internal task): `audit edge` on
# the file standing alone (2026-10-23) sees the inside ("open"/"back") at eye height
# on these sides. They are not closed yet; the description says where, so a world sets them against
# something there. models.json id -> sides (file axes).
EYE_GAPS = {
    "B058": ("+z",), "B082": ("+x", "+z"), "BIRD01": ("+x",), "C03": ("+z", "-z"),
    "DRAGON01": ("+x", "+z"), "W01": ("-x",),
}


def open_sides(tris, footprint, floor_y, force=()):
    """Footprint sides with almost no outward-facing wall at ground-floor height, plus the
    sides facing an axis in force (FORCE_OPEN).
    Returns [{"side": k, "length_m": L, "faces": "+x"|..., "angle_deg": a, "ends": [a, b]}] (file
    axes; ends: the side's two footprint corners (x, z), in the coordinates of the triangles given)."""
    cx = sum(p[0] for p in footprint) / len(footprint)
    cz = sum(p[1] for p in footprint) / len(footprint)
    faces = []
    for t in tris:
        ux, uy, uz = (t[1][k] - t[0][k] for k in range(3))
        vx, vy, vz = (t[2][k] - t[0][k] for k in range(3))
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz)
        if ln < 1e-9 or abs(ny / ln) > 0.5:
            continue
        c = [(t[0][k] + t[1][k] + t[2][k]) / 3 for k in range(3)]
        if not (floor_y + 0.3 < c[1] < floor_y + 2.8):
            continue
        faces.append((c[0], c[2], nx / ln, nz / ln, ln / 2))
    out = []
    for k in range(len(footprint)):
        a, b = footprint[k], footprint[(k + 1) % len(footprint)]
        ex, ez = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ex, ez)
        if L < 1.0:
            continue
        tx, tz = ex / L, ez / L
        ox, oz = tz, -tx
        if ox * ((a[0] + b[0]) / 2 - cx) + oz * ((a[1] + b[1]) / 2 - cz) < 0:
            ox, oz = -ox, -oz
        area = 0.0
        for fx, fz, nx, nz, ar in faces:
            s = (fx - a[0]) * tx + (fz - a[1]) * tz
            d = (fx - a[0]) * ox + (fz - a[1]) * oz
            if -0.2 < s < L + 0.2 and abs(d) < 1.2 and nx * ox + nz * oz > 0.3:
                area += ar
        ang = math.degrees(math.atan2(oz, ox)) % 360
        axis = ["+x", "+z", "-x", "-z"][int(((ang + 45) % 360) // 90)]
        if area / (L * 2.5) < 0.4 or (axis in force and L >= 2.0):
            out.append({"side": k, "length_m": round(L, 1), "faces": axis, "angle_deg": round(ang),
                        "ends": [list(a), list(b)]})
    return out


# ------------------------------------------------------------------ import / check

def _commit(repo: Path) -> str:
    head = repo / ".git" / "HEAD"
    if not head.is_file():
        return ""
    ref = head.read_text().strip()
    if ref.startswith("ref: "):
        rp = repo / ".git" / ref[5:]
        if rp.is_file():
            return rp.read_text().strip()[:8]
        packed = repo / ".git" / "packed-refs"
        for line in (packed.read_text().splitlines() if packed.is_file() else []):
            if line.endswith(" " + ref[5:]):
                return line[:8]
        return ""
    return ref[:8]


def import_from(models_repo: Path, plan_paths: list) -> int:
    index = json.loads((models_repo / "models.json").read_text(encoding="utf-8"))["models"]
    plans = {}   # sha256 -> {building id: record}; the first plan given is the fallback
    for pp in plan_paths:
        pb_ = pp.read_bytes()
        plans[hashlib.sha256(pb_).hexdigest()] = {b["id"]: b for b in json.loads(pb_)["buildings"]}
    commit = _commit(models_repo)
    rows, bad = [], []
    for mid, (folder, name, cat, desc, syn, ground_y) in PICK.items():
        rec = index.get(mid)
        if rec is None:
            bad.append("%s: not in models.json" % mid)
            continue
        plan_sha = rec.get("plan_sha256", "")
        if folder == "buildings" and plan_sha not in plans:
            bad.append("%s: built from plan %s..., which was not given (pass the plan at its builder commit)"
                       % (mid, plan_sha[:12]))
            continue
        plan = plans.get(plan_sha) or next(iter(plans.values()))
        src = (models_repo / rec["file"]).read_bytes()
        lo, hi = bounds(src)
        src_sha = hashlib.sha256(src).hexdigest()
        src = wrap_root(src)   # the portal's ring is its scene root
        pivot = [(lo[0] + hi[0]) / 2, lo[1] if ground_y is None else ground_y, (lo[2] + hi[2]) / 2]
        b = recentre(src, [-pivot[0], -pivot[1], -pivot[2]])
        pb = plan.get(mid, {})
        quarter = pb.get("district_id")
        style, words = QUARTERS.get(quarter, ("iamar city", ""))
        sides = None
        if mid in plan and folder == "buildings":
            tris = triangles_world(src)
            sides = open_sides(tris, pb["footprint_xz"], pb.get("floor_y_m", 0.8), FORCE_OPEN.get(mid, ()))
        for s in sides or []:   # the side's footprint corners in the file's own coordinates
            s["ends"] = [[round(e[0] - pivot[0], 3), round(e[1] - pivot[2], 3)] for e in s["ends"]]
        if folder == "buildings":
            b, _info = seal(b, sides)   # back sides for the single-sheet trim (seal_trim_edges.py)
        m = measure(b)
        d = desc
        if words:
            d += " From " + words + "."
        if mid in EYE_GAPS:
            d += (" Standing alone it shows gaps into it at eye height on its %s side%s, where the city built"
                  " it against its neighbours: set it against a wall or another building there." % (
                      " and ".join(EYE_GAPS[mid]), "s" if len(EYE_GAPS[mid]) > 1 else ""))
        if sides:
            d += " Open on %s (it shared %s with a neighbour): set it against a wall or another building there." % (
                " and ".join("its %s side, %g m" % (s["faces"], s["length_m"]) for s in sides),
                "a party wall" if len(sides) == 1 else "party walls")
        fname = "_".join(mid.lower().split()) + ".glb"
        dst = HERE / folder / fname
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b)
        if rec.get("triangles") is not None and int(rec["triangles"]) != m["triangles"]:
            print("note %s: models.json says %s triangles, the file has %d (kept the file's count)"
                  % (mid, rec["triangles"], m["triangles"]))
        rows.append({
            "models_id": mid, "file": "%s/%s" % (folder, fname), "name": name, "category": cat,
            "description": d, "synonyms": syn, "collision": "mesh",
            "style": style, "quarter": quarter, "plan_purpose": pb.get("purpose"),
            "floors": pb.get("floors"), "open_sides": sides,
            "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b),
            "source_sha256": src_sha,
            "recentred_by": [round(-v, 3) for v in pivot],
            "place_scale": 1.0,
            "triangles": m["triangles"], "models_json_triangles": rec.get("triangles"), "size": m["size"],
            "skinned": m["skinned"], "animations": m["animations"], "images": m["images"],
            "physics_body": m["physics_body"],
            "licence": STATUE_LICENCE if mid.startswith("HERO_") else LICENCE,
            "builder": rec.get("builder", ""), "builder_commit": rec.get("builder_commit", ""),
            "cite": "the iamar-models mesh archive (not public) %s %s (the iamar browser source (not public) %s, plan sha256 %s...)" % (
                commit, rec["file"], rec.get("builder_commit", ""), plan_sha[:12]),
        })
    for line in bad:
        print("IMPORT ERROR " + line, file=sys.stderr)
    if bad:
        return 1
    rows.sort(key=lambda r: r["file"])
    SOURCE.write_text(json.dumps({
        "format": "iamar-catalog-city-models", "version": 1,
        "note": "Representative city buildings per quarter and reusable landmarks, copied from "
                "the iamar-models mesh archive (not public) and re-centred to a bottom-centre pivot by "
                "kit/catalog/assets/import_city_buildings.py. Files live in kit/catalog/assets/<file>. "
                "Never edit by hand: rerun the import.",
        "models_commit": commit, "licence": LICENCE, "models": rows},
        indent=1) + "\n", encoding="utf-8", newline="\n")
    print("imported %d buildings and landmarks (%d bytes) from iamar-models %s"
          % (len(rows), sum(r["bytes"] for r in rows), commit))
    return 0


def check() -> int:
    errs = []
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    for r in src["models"]:
        p = HERE / r["file"]
        if not p.is_file():
            errs.append("%s: file missing" % r["file"])
            continue
        b = p.read_bytes()
        if hashlib.sha256(b).hexdigest() != r["sha256"]:
            errs.append("%s: sha256 differs from city_buildings.json (rerun the import)" % r["file"])
        m = measure(b)
        if m["triangles"] != r["triangles"]:
            errs.append("%s: %d triangles, record says %d" % (r["file"], m["triangles"], r["triangles"]))
        lo, hi = bounds(b)
        if abs((lo[0] + hi[0]) / 2) > 0.05 or abs((lo[2] + hi[2]) / 2) > 0.05:
            errs.append("%s: not centred on x/z (%.2f, %.2f)" % (r["file"], (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2))
    listed = {(HERE / r["file"]).resolve() for r in src["models"]}
    closed = SOURCE.with_name("city_buildings_closed.json")   # close_open_sides.py --check verifies them
    if closed.is_file():
        listed |= {(HERE / r["file"]).resolve() for r in json.loads(closed.read_text(encoding="utf-8"))["models"]}
    for folder in ("buildings", "landmarks"):
        for p in (HERE / folder).rglob("*.glb"):
            if p.resolve() not in listed:
                errs.append("%s: GLB with no record in sources/city_buildings.json" % p.relative_to(HERE).as_posix())
    for e in errs:
        print("CHECK " + e)
    print("city buildings: %d records, %s" % (len(src["models"]), "OK" if not errs else "%d problems" % len(errs)))
    return 1 if errs else 0


def main(argv: list) -> int:
    if argv[:1] == ["--check"]:
        return check()
    if len(argv) < 2:
        print(__doc__)
        return 2
    return import_from(Path(argv[0]), [Path(a) for a in argv[1:]])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
