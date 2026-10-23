#!/usr/bin/env python3
"""Record the catalogue's insects (kit/catalog/assets/creatures/insects/*.glb, written by
export_insects.gd) in kit/catalog/sources/insects.json, which catalog.py turns into entries.

  python3 kit/catalog/assets/insects.py record     measure every file and write the source
  python3 kit/catalog/assets/insects.py --check    fail if a file or record is off

The files are made, not copied: run export_insects.gd from an the iamar browser source (not public) checkout first
(see its header). Each file carries its motion as glTF animation clips; `play` is the clip a
world loops with scene.json objects "animation". Python 3.8+, standard library only.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from import_city_models import HERE, LICENCE, measure

FOLDER = "creatures/insects"
SOURCE = HERE.parent / "sources" / "insects.json"
BUTTERFLY_CITE = ("the iamar browser source (not public) a025eeba scripts/world/butterflies.gd (mesh, SPECIES), "
                  "scripts/world/butterfly_motion.gd (wing poses), assets/butterflies/atlas.png "
                  "(tools/make_butterfly_atlas.py); exported by kit/catalog/assets/export_insects.gd")
KIT_CITE = ("made for the kit by kit/catalog/assets/export_insects.gd in the city butterflies' build "
            "(the city has no %s model: %s)")

BUTTERFLY_SYN = ["butterfly", "insect", "garden insect", "meadow", "flutter", "pollinator"]
BUTTERFLY_BEHAVIOURS = ["wingbeat (clip flap)", "glide (clip glide)", "perched basking (clip rest)"]

# file stem -> (name, origin, description, extra synonyms, behaviours, clip to loop)
INSECTS = {
    "butterfly_small_white": ("small white butterfly", "city",
        "A small white butterfly, white wings with a dark tip and a black spot; the commonest in the city's gardens. About 9 cm across.",
        ["cabbage white", "white butterfly"], BUTTERFLY_BEHAVIOURS, "flap"),
    "butterfly_brimstone": ("brimstone butterfly", "city",
        "A brimstone butterfly, sulphur-yellow leaf-shaped wings with a hooked point; rests with wings closed. About 10 cm across.",
        ["yellow butterfly", "sulphur"], BUTTERFLY_BEHAVIOURS, "flap"),
    "butterfly_small_tortoiseshell": ("small tortoiseshell butterfly", "city",
        "A small tortoiseshell butterfly, orange wings with black and yellow bars and a blue-studded border; basks with wings open.",
        ["orange butterfly", "tortoiseshell"], BUTTERFLY_BEHAVIOURS, "flap"),
    "butterfly_common_blue": ("common blue butterfly", "city",
        "A common blue butterfly, small bright violet-blue wings edged in dark grey, a pale spotted underside; the smallest of the six, about 6 cm across.",
        ["blue butterfly", "little blue"], BUTTERFLY_BEHAVIOURS, "flap"),
    "butterfly_peacock": ("peacock butterfly", "city",
        "A peacock butterfly, deep red wings each with a big blue-and-yellow eye spot; dark underside; basks with wings open.",
        ["eye spot butterfly", "red butterfly"], BUTTERFLY_BEHAVIOURS, "flap"),
    "butterfly_red_admiral": ("red admiral butterfly", "city",
        "A red admiral butterfly, velvety black wings crossed by red bands with white spots at the tips; the largest of the six.",
        ["black and red butterfly", "admiral"], BUTTERFLY_BEHAVIOURS, "flap"),
    "bumblebee": ("bumblebee", "kit",
        "A fuzzy bumblebee about 2 cm long, black with two yellow bands and a white tail, clear wings swept back; hovers buzzing over flowers.",
        ["bee", "bumble bee", "honeybee", "insect", "pollinator", "garden insect", "buzzing"],
        ["hovering buzz with a bob (clip fly)", "resting on a flower (clip rest)"], "fly"),
    "dragonfly": ("dragonfly", "kit",
        "An emperor-like dragonfly about 7.5 cm long: big green eyes, green thorax, a long sky-blue abdomen ringed in black, four long clear wings held straight out.",
        ["damselfly", "darner", "emperor dragonfly", "insect", "pond insect", "water insect"],
        ["hovering, fore and hind wings beating out of phase (clip fly)", "perched with wings out (clip rest)"], "fly"),
}
WHY_NOT_CITY = {"bumblebee": "bees are a sound there, MpSoundscape 'bees'",
                "dragonfly": "dragonflies are glowing motes over the mill pond, Waterworks/Fx.motes"}


def rows() -> list:
    out = []
    for stem, (name, origin, desc, syn, beh, play) in INSECTS.items():
        rel = "%s/%s.glb" % (FOLDER, stem)
        p = HERE / rel
        b = p.read_bytes()
        m = measure(b)
        out.append({
            "models_id": "insect_" + stem, "file": rel, "name": name, "category": "insect",
            "description": desc + " Real size: place it at scale 2-3 where it must read from eye height.",
            "synonyms": syn + (BUTTERFLY_SYN if stem.startswith("butterfly") else []),
            "collision": "none", "origin": origin,
            "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b), "place_scale": 1.0,
            "triangles": m["triangles"], "size": m["size"], "skinned": m["skinned"],
            "animations": m["animations"], "images": m["images"], "physics_body": m["physics_body"],
            "play": play, "behaviours": beh,
            "builder": "kit/catalog/assets/export_insects.gd",
            "cite": BUTTERFLY_CITE if origin == "city" else KIT_CITE % (name, WHY_NOT_CITY[stem]),
        })
    return out


def record() -> int:
    rs = rows()
    SOURCE.write_text(json.dumps({
        "format": "iamar-catalog-insects", "version": 1,
        "note": "Insects with their wing motion as glTF clips, in kit/catalog/assets/<file>, made by "
                "export_insects.gd and measured by insects.py record. Never edit by hand.",
        "licence": LICENCE, "models": rs}, indent=1) + "\n", encoding="utf-8")
    print("recorded %d insects (%d bytes)" % (len(rs), sum(r["bytes"] for r in rs)))
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
            errs.append("%s: sha256 differs from insects.json (rerun insects.py record)" % r["file"])
        m = measure(b)
        if m["triangles"] != r["triangles"]:
            errs.append("%s: %d triangles, record says %d" % (r["file"], m["triangles"], r["triangles"]))
        if r["play"] not in m["animations"]:
            errs.append("%s: no clip %r to loop (has %s)" % (r["file"], r["play"], m["animations"]))
    named = {r["file"] for r in src["models"]}
    for p in (HERE / FOLDER).glob("*.glb"):
        if "%s/%s" % (FOLDER, p.name) not in named:
            errs.append("%s/%s: GLB with no record in sources/insects.json" % (FOLDER, p.name))
    for e in errs:
        print("CHECK " + e)
    print("insects: %d records, %s" % (len(src["models"]), "OK" if not errs else "%d problems" % len(errs)))
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
