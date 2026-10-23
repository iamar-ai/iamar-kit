#!/usr/bin/env python3
"""Record the catalogue's coastal and home set (kit/catalog/assets/coastal/) in
kit/catalog/sources/coastal.json, which catalog.py turns into entries: thirteen models written by
export_coastal.gd for a beach (palm tree, dock, beach umbrella, sun lounger, beach towel, sea
shells, coral, kelp) and a modern house (sofa, kitchen counter, bathtub, wardrobe, rug). The
rowboat is the harbour set's (harbour.py).

  python3 kit/catalog/assets/coastal.py record     measure every file, write the source
  python3 kit/catalog/assets/coastal.py --check    fail if a file or record is off, or a model
                                                   breaks the set's budget (3000 triangles)

The models are made, not copied: run export_coastal.gd first (see its header). Unlike the
harbour set these are not in the iamar city's look: their style is "iamar coastal and modern home"
and their style_compat is neutral, so `assets search --style` offers them to any world.
Python 3.8+, standard library only.
"""

from __future__ import annotations

import hashlib
import json
import sys

from import_city_models import HERE, LICENCE, measure

FOLDER = "coastal"
SOURCE = HERE.parent / "sources" / "coastal.json"
BUILDER = "kit/catalog/assets/export_coastal.gd"
CITE = "made for the kit by kit/catalog/assets/export_coastal.gd (an internal task, iamar-creator-ux: the beach-house brief)"
STYLE = "iamar coastal and modern home"
MAX_TRIANGLES = 3000
# clip -> [node it moves, least swing in radians] (tests/catalog/city_assets_test.gd checks it)
MOVES = {"kelp": {"sway": ["Blade3", 0.1]}}

# file stem -> (name, category, description, synonyms, behaviours, clip to loop, collision, pack tag)
MODELS = {
    "palm_tree": ("palm tree", "tree",
        "A coconut palm 6.4 m tall: a ringed trunk curving away from the wind, nine drooping fronds folded "
        "along their midribs and a bunch of four coconuts under the crown. Sways in the shared wind.",
        ["palm", "coconut palm", "coconut tree", "palm tree", "tropical tree", "beach", "coast", "seaside",
         "island", "tropical", "coconut"],
        ["sways in the wind (scene.json \"sway\": true)"], None, "box", "beach"),
    "dock": ("dock", "bridge",
        "A wooden dock 2 m wide and 9 m long on eight piles: weathered deck boards with gaps, stringers, a "
        "ladder down into the water at the far end and two mooring cleats. The origin is the water's surface at "
        "the shore end; the deck is 0.6 m above it and runs out along -Z, so place it at the water's height with "
        "the origin on the beach and turn it to face the sea. Walk on it with \"collision\": \"mesh\".",
        ["dock", "pier", "jetty", "boardwalk", "landing stage", "wharf", "quay", "boat dock", "beach", "lake",
         "harbour", "harbor", "walkway", "coast", "seaside"],
        [], None, "mesh", "beach"),
    "beach_umbrella": ("beach umbrella", "prop",
        "A beach umbrella 2.4 m tall: a white pole pushed 0.35 m into the sand, an eight-panel canopy 2.3 m "
        "across in alternating teal and off-white with a scalloped valance, and ribs underneath.",
        ["umbrella", "parasol", "sunshade", "beach umbrella", "sun umbrella", "shade", "beach", "seaside",
         "patio", "pool"],
        [], None, "box", "beach"),
    "sun_lounger": ("sun lounger", "furniture",
        "A teak sun lounger 1.95 m long: four legs, slatted bed, a backrest raised at 40 degrees at the +Z end "
        "and a striped cream and teal cushion pad. Pair it with the beach umbrella and towel.",
        ["lounger", "sun lounger", "deck chair", "deckchair", "sunbed", "chaise longue", "chaise", "beach chair",
         "pool chair", "recliner", "beach", "pool", "patio", "seaside"],
        [], None, "box", "beach"),
    "beach_towel": ("beach towel", "prop",
        "A striped beach towel 1.7 x 0.85 m laid flat on the sand in red, yellow, teal and off-white bands, one "
        "corner folded back. Flat (1 cm), so it needs no collision.",
        ["towel", "beach towel", "bath towel", "blanket", "picnic blanket", "beach", "seaside", "sunbathing"],
        [], None, "none", "beach"),
    "sea_shells": ("sea shells", "ground-flora",
        "A scatter of sea shells over about 1 x 0.8 m: four scallops, three whelks, three clams and an orange "
        "starfish, lying on the sand at the tide line. Scatter a few copies along the shore, turned differently.",
        ["shell", "shells", "seashell", "seashells", "sea shell", "scallop", "clam", "whelk", "conch",
         "starfish", "sea star", "beach", "tide line", "shore", "seaside"],
        [], None, "none", "beach"),
    "coral": ("coral cluster", "ground-flora",
        "A coral cluster 1.4 m across on a reef rock: a yellow brain coral dome, pink and orange staghorn "
        "coral, a purple sea fan and three orange tube sponges. The origin is the sea floor: place it under "
        "clear water, where fish swim over it.",
        ["coral", "reef", "coral reef", "brain coral", "staghorn", "sea fan", "sponge", "underwater",
         "sea floor", "seabed", "ocean", "tropical", "dive", "snorkel"],
        [], None, "box", "beach"),
    "kelp": ("kelp", "ground-flora",
        "A bed of giant kelp: eight olive-brown blades 1.4 to 2.6 m tall rising from a rocky holdfast, waving "
        "in the swell (clip sway, each blade out of phase). The origin is the sea floor: place it under "
        "water at least 2 m deep.",
        ["kelp", "seaweed", "sea weed", "algae", "sea grass", "seagrass", "kelp forest", "underwater",
         "sea floor", "seabed", "ocean", "water plant"],
        ["waving in the swell (clip sway)"], "sway", "none", "beach"),
    "sofa": ("sofa", "furniture",
        "A modern three-seat sofa 2.1 m wide with the seat at 0.45 m: slate-blue upholstery, three seat and three "
        "back cushions, rolled arms, walnut legs and a cream scatter cushion. It faces +Z; put its back (-Z) to a "
        "wall or behind a rug in a living room.",
        ["sofa", "couch", "settee", "lounge", "three-seater", "living room", "sitting room", "lounge room",
         "seat", "modern"],
        [], None, "box", "home"),
    "kitchen_counter": ("kitchen counter", "furniture",
        "A fitted kitchen counter 2.4 m long and 0.9 m high: sage-green base cabinets with doors and a drawer "
        "row, a pale stone worktop, an inset steel sink with a swan-neck tap, a black four-ring hob and a tiled "
        "splashback. Doors face +Z; put the back (-Z) against a wall.",
        ["kitchen", "counter", "kitchen counter", "worktop", "countertop", "cabinet", "cupboard", "sink",
         "hob", "stove", "cooker", "kitchenette", "modern"],
        [], None, "box", "home"),
    "bathtub": ("bathtub", "furniture",
        "A freestanding bath 1.7 x 0.78 m: an off-white enamel shell with a rolled rim and a deep basin, a "
        "walnut plinth and a chrome mixer tap at the +X end. Put it in a bathroom with its long side to a wall.",
        ["bath", "bathtub", "tub", "bath tub", "bathroom", "washroom", "soaking tub", "modern"],
        [], None, "box", "home"),
    "wardrobe": ("wardrobe", "furniture",
        "A double wardrobe 1.2 m wide, 0.6 m deep and 2.1 m tall in light oak: two doors with a shadow gap, "
        "long steel bar handles, a plinth and a top cornice. Doors face +Z; stand its back (-Z) against a bedroom wall.",
        ["wardrobe", "closet", "armoire", "cupboard", "clothes cabinet", "bedroom", "storage", "modern"],
        [], None, "box", "home"),
    "rug": ("rug", "furniture",
        "A woven rug 2.4 x 1.7 m: a red field with a central blue and gold medallion, a cream inner border, a "
        "deep blue outer border and a fringe at both short ends. Flat (1 cm), so it needs no collision; lay it "
        "under a sofa or beside a bed.",
        ["rug", "carpet", "mat", "floor rug", "area rug", "persian rug", "living room", "bedroom",
         "floor covering"],
        [], None, "none", "home"),
}


def rows() -> list:
    out = []
    for stem, (name, cat, desc, syn, beh, play, coll, pack) in MODELS.items():
        rel = "%s/%s.glb" % (FOLDER, stem)
        b = (HERE / rel).read_bytes()
        m = measure(b)
        r = {"models_id": "coastal_" + stem, "file": rel, "name": name, "category": cat, "description": desc,
             "synonyms": syn, "collision": coll, "origin": "kit-coastal", "pack": "iamar coastal and home", "style": STYLE,
             "style_compat": ["neutral"], "tags": [pack, "coastal and home"],
             "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b), "place_scale": 1.0,
             "triangles": m["triangles"], "size": m["size"], "skinned": m["skinned"],
             "animations": m["animations"], "images": m["images"], "physics_body": m["physics_body"],
             "behaviours": beh, "builder": BUILDER, "cite": CITE}
        if play:
            r["play"] = play
        if stem in MOVES:
            r["moves"] = MOVES[stem]
        out.append(r)
    return out


def record() -> int:
    rs = rows()
    SOURCE.write_text(json.dumps({
        "format": "iamar-catalog-coastal", "version": 1,
        "note": "The coastal and home set in kit/catalog/assets/coastal/: models made by export_coastal.gd, "
                "measured by coastal.py record. Never edit by hand.",
        "licence": LICENCE, "models": rs}, indent=1) + "\n", encoding="utf-8")
    print("recorded %d models (%d triangles, %d bytes)" % (
        len(rs), sum(r["triangles"] for r in rs), sum(r["bytes"] for r in rs)))
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
            errs.append("%s: sha256 differs from coastal.json (rerun coastal.py record)" % r["file"])
        m = measure(b)
        if m["triangles"] != r["triangles"]:
            errs.append("%s: %d triangles, record says %d" % (r["file"], m["triangles"], r["triangles"]))
        if m["triangles"] > MAX_TRIANGLES:
            errs.append("%s: %d triangles, over the set's %d" % (r["file"], m["triangles"], MAX_TRIANGLES))
        for clip in [r.get("play")] + list(r.get("moves", {})):
            if clip and clip not in m["animations"]:
                errs.append("%s: no clip %r (has %s)" % (r["file"], clip, m["animations"]))
    named = {r["file"] for r in src["models"]}
    for p in (HERE / FOLDER).glob("*.glb"):
        rel = p.relative_to(HERE).as_posix()
        if rel not in named:
            errs.append("%s: file with no record in sources/coastal.json" % rel)
    if set(MODELS) != {r["models_id"][len("coastal_"):] for r in src["models"]}:
        errs.append("coastal.json does not list exactly MODELS (rerun coastal.py record)")
    for e in errs:
        print("CHECK " + e)
    print("coastal: %d records, %s" % (len(src["models"]), "OK" if not errs else "%d problems" % len(errs)))
    return 1 if errs else 0


def main(argv: list) -> int:
    if argv[:1] == ["--check"]:
        return check()
    if argv[:1] == ["record"]:
        return record()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
