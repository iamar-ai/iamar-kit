#!/usr/bin/env python3
"""Build kit/catalog/provenance.json: where every shipped binary of the kit came from (an internal task, PUB3).

Every model, texture, image, sound and font the public export could ship gets a row
    path -> {made_by, evidence[, derived_from][, uses][, note]}
made_by is one of
    hand                      drawn or written by a person
    procedural                built by our own code (a script, a Godot builder, a render of such)
    blender                   modelled by a person in Blender
    third-party:<row>         someone else's asset under kit/inventory/licences.json row <row>
    generative:<row>          the output (or a render showing the output) of a generative model
                              whose licence row is not cleared; tools/export_public.py withholds it
Rows come from the catalogue (each entry's file, thumbnail and turntable) and from RULES below
for everything else. Every decision cites the commit or file that shows it; the audit itself
(which iamar builders use which generated pictures) is in the an internal task note on the board.

    python3 kit/catalog/provenance_build.py           # rewrite provenance.json
    python3 kit/catalog/provenance_build.py --check   # exit 1 when it is stale or a binary has no rule
"""
import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
ROOT = KIT.parent
CATALOG = HERE / "catalog.json"
OUT = HERE / "provenance.json"
LICENCES = KIT / "inventory" / "licences.json"
RULES_JSON = KIT / "export" / "rules.json"
# the binaries the export handles as assets (tools/export_public.py ASSET_EXT)
BIN_EXT = {".png", ".jpg", ".jpeg", ".webp", ".glb", ".gltf", ".bin", ".ogg", ".wav", ".mp3",
           ".ttf", ".otf", ".exr", ".hdr", ".ktx2", ".pck", ".zip"}
INCLUDE_TOP = ("docs/", "kit/", "pack/", "scripts/", "tests/", "tools/")

# built-in pack folder (the iamar browser source (not public) assets/<folder>) -> kit/inventory/licences.json row
PACK_ROWS = {
    "town": "kenney-fantasy-town-kit-2", "nature": "kenney-nature-kit", "castle": "kenney-castle-kit",
    "survival": "kenney-survival-kit", "village": "quaternius-medieval-village-megakit",
    "naturekit": "quaternius-stylized-nature-megakit", "forest_paint": "quaternius-stylized-nature-megakit",
    "props": "quaternius-fantasy-props-megakit", "chars": "quaternius-universal-base-characters",
    "hair": "quaternius-universal-base-characters", "anims": "quaternius-universal-animation-library",
}

# Package-world creatures (catalogue origin "creature"): WorldCreatures.kit_parts (the iamar browser source (not public)
# 98c2ecd2 scripts/worlds/world_creatures.gd) draws these looks with MpCreatures, whose shader
# samples a gpt-image-1 fur/feather/scale tile (MpCreatures.LOOK -> assets/masterplan/creatures/
# <tile>_d.png, painted in iamar d023c7eb / 21a9ed36 / 2633743e), so their renders show it.
GEN_CREATURE_TILE = {"deer": "deer_coat", "wolf": "wolf_coat", "duck": "feathers (drake, hen)",
                     "duckling": "fur_fluffy", "fish": "scales_fish", "frog": "fur_fluffy",
                     "turtle": "scales_fish"}

# Notes on catalogue files whose builder in the city also uses generated work that the kit's
# copy leaves out (checked by reading the exporters and the files' embedded images).
FILE_NOTES = {
    "kit/catalog/assets/creatures/mounts/giant_eagle.glb":
        "export_city_mounts.gd sets MpGenHead.enabled = false: code-built head, not the city's Hunyuan3D-2 "
        "head_gen.glb; albedo is MpBirdKit's code painter (albedo_tex), not the gpt-image-1 feather tiles "
        "(tex_body/head/coverts/scales/primary/tail, iamar fe6eb707), which are not exported",
    "kit/catalog/assets/creatures/mounts/bronze_wyrm.glb":
        "code-built skull (MpGenHead off), DragonPainter coat; design after the maintainer's SDXL concept (iamar 93a09f70): "
        "no generated pixels or geometry in the file",
    "kit/catalog/assets/creatures/mounts/copper_runner.glb":
        "code-built skull (MpGenHead off), DragonPainter coat; design after the maintainer's SDXL concept (iamar 93a09f70): "
        "no generated pixels or geometry in the file",
    "kit/catalog/assets/creatures/mounts/teal_drake.glb":
        "code-built skull (MpGenHead off), DragonPainter coat; design after the maintainer's SDXL concept (iamar 93a09f70): "
        "no generated pixels or geometry in the file",
    "kit/catalog/assets/creatures/guardian_dragon.glb":
        "DragonKit v23; albedo painted by GuardianPainter (tools/make_dragon.gd, iamar d9c48e2b)",
    "kit/catalog/assets/creatures/young_dragon.glb":
        "MpDragonKit classic stabled dragon (no sculpted head), DragonPainter coat",
    "kit/catalog/assets/landmarks/hero_e1.glb":
        "MpStatues at iamar 15961b3: the game's CC0 Quaternius body posed in code, carved stone; "
        "older than the image-to-3D gate statues (iamar bdfbe887, 2026-10-13)",
    "kit/catalog/assets/landmarks/hero_w1.glb":
        "MpStatues at iamar 15961b3: the game's CC0 Quaternius body posed in code, carved stone; "
        "older than the image-to-3D gate statues (iamar bdfbe887, 2026-10-13)",
    "kit/catalog/assets/furniture/shop_shelf.glb":
        "MpInteriors._shelf only: the room's painted goods cards (gpt-image-1.5 mp_interior_goods.png) are "
        "separate card meshes that export_city_pieces.gd does not export",
    "kit/catalog/assets/furniture/bookshelf.glb":
        "MpInteriors._shelf only: the room's painted goods cards (gpt-image-1.5 mp_interior_goods.png) are "
        "separate card meshes that export_city_pieces.gd does not export",
}
FILE_USES = {
    "kit/catalog/assets/landmarks/hero_e1.glb": ["quaternius-universal-base-characters"],
    "kit/catalog/assets/landmarks/hero_w1.glb": ["quaternius-universal-base-characters"],
}
CITY_CREATURE_NOTE = ("vertex-painted parts (no embedded image): the city's gpt-image-1 fur tile is a shader "
                      "input there (MpCreatures.material) and is not in this file")

HUNYUAN_STATUES = ("the iamar browser source (not public) b648a60b render showing the gate statues made by the statue protocol "
                   "(Hunyuan3D-2.1 + UltraShape: iamar 07b0ab41, 115cdcd7); view in kit/gallery/city/views.json")

# Everything outside the catalogue: first matching glob wins. evidence "@add" = the kit commit
# that added the file (filled in by the build).
RULES = [
    ("kit/gallery/city/civic_skyline.jpg", "generative:hunyuan3d-2", HUNYUAN_STATUES, "South Gate statues in view"),
    ("kit/gallery/city/mages_skyline.jpg", "generative:hunyuan3d-2", HUNYUAN_STATUES, "East Gate statue in view"),
    ("kit/gallery/city/warriors_skyline.jpg", "generative:hunyuan3d-2", HUNYUAN_STATUES, "North Gate statue in view"),
    ("kit/gallery/city/*.jpg", "procedural", "@add",
     "render of the iamar city (the iamar browser source (not public) b648a60b) by kit/gallery/city/city_views.gd; no gate statue in view"),
    ("kit/gallery/styles/*", "procedural", "@add", "kit/tools contact_sheet.py style cards"),
    ("kit/style/materials/library/*", "procedural", "@add", "painted by kit/style/materials paint_materials.py"),
    ("kit/style/materials/**", "procedural", "@add", "render of a kit sample world"),
    ("kit/style/lighting/**", "procedural", "@add", "renders of kit sample worlds under the lighting presets"),
    ("kit/lint/samples/**", "procedural", "@add", "kit sample world made by kit tools / city export (code-built)"),
    ("kit/audit/samples/**", "procedural", "@add", "kit sample world made by kit tools"),
    ("kit/shots/samples/**", "procedural", "@add", "render of a kit sample world"),
    ("tests/kit_playtest/**", "procedural", "@add", "test fixture made by kit tools"),
    ("docs/evidence/**", "procedural", "@add",
     "render of kit worlds or catalogue objects (statue shots: kit/recipes/statue code-built statue)"),
    ("docs/shots/**", "procedural", "@add", "render of iamar-world play"),
    ("kit/catalog/assets/harbour/sounds/*.ogg", "procedural", "kit/catalog/assets/harbour.py sounds",
     "synthesised: seeded noise and partials, no recording"),
]


def git(*args) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def glob_match(path: str, pat: str) -> bool:
    if pat.endswith("/"):
        return path.startswith(pat)
    if "**" in pat:
        head, _, tail = pat.partition("**")
        return path.startswith(head) and fnmatch.fnmatchcase(path[len(head):], "*" + tail if tail else "*")
    return fnmatch.fnmatchcase(path, pat) and path.count("/") == pat.count("/")


def binaries() -> list[str]:
    """Binaries the export would consider: tracked, inside the include folders, not excluded."""
    excl = [e["glob"] for e in json.loads(RULES_JSON.read_text(encoding="utf-8"))["exclude"]] \
        if RULES_JSON.is_file() else []
    out = []
    for p in git("ls-files").splitlines():
        if Path(p).suffix.lower() in BIN_EXT and p.startswith(INCLUDE_TOP) \
                and not any(glob_match(p, g) for g in excl):
            out.append(p)
    return sorted(out)


def builtin_row(file: str) -> str:
    parts = file.split("/")
    return PACK_ROWS.get(parts[1] if len(parts) > 2 and parts[0] == "assets" else "", "")


def entry_rows(e: dict) -> dict:
    """Rows for one catalogue entry: its kit file (when it has one) and its two previews."""
    s, eid, rows = e["source"], e["id"], {}
    origin, f = s.get("origin"), str(s.get("file") or "")
    note, uses, derived = "", [], ""
    if origin == "builtin":
        row = builtin_row(f)
        made, ev = "third-party:" + row, "the iamar browser source (not public) 79512407 %s (%s)" % (f, s.get("pack", ""))
    elif origin == "creature":
        kind = eid.split(":", 1)[1]
        if kind in GEN_CREATURE_TILE:
            made = "generative:gpt-image-1"
            ev = ("the iamar browser source (not public) 98c2ecd2 scripts/worlds/world_creatures.gd kit_parts -> MpCreatures, detail tile "
                  "assets/masterplan/creatures/%s_d.png (gpt-image-1: iamar d023c7eb, 21a9ed36)" % GEN_CREATURE_TILE[kind])
        else:
            made = "procedural"
            ev = "the iamar browser source (not public) 98c2ecd2 scripts/worlds/world_creatures.gd kit_parts -> AnimalKit.rigid_parts (vertex colours)"
    elif origin == "generator":
        made, ev = "procedural", s.get("cite", "")
        uses = ["kenney-fantasy-town-kit-2", "kenney-survival-kit"]
        note = "town builder in code; its furniture props are Kenney CC0"
    else:   # city, kit, kit-coastal: made in code by the city builders or the kit's export scripts
        made, ev = "procedural", s.get("cite", "")
        note = FILE_NOTES.get(f, "")
        if not note and f.startswith("kit/catalog/assets/creatures/") and "/mounts/" not in f \
                and "/insects/" not in f:
            note = CITY_CREATURE_NOTE
        uses = FILE_USES.get(f, [])
    base = {"made_by": made, "evidence": ev}
    if uses:
        base["uses"] = uses
    if note:
        base["note"] = note
    if f.startswith("kit/catalog/assets/"):
        rows[f] = dict(base)
        derived = f
    for key in ("thumbnail", "turntable"):
        if e.get(key):
            r = dict(base)
            r["derived_from"] = derived or eid
            r["evidence"] = "rendered by kit/catalog/render_previews.gd from %s; source: %s" % (
                derived or eid, ev)
            r.pop("note", None)
            rows["kit/" + e[key]] = r
    return rows


def build() -> tuple[dict, list[str]]:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = {}
    for e in cat["entries"]:
        rows.update(entry_rows(e))
    unmatched, adds = [], {}
    for p in binaries():
        if p in rows:
            continue
        for pat, made, ev, note in RULES:
            if glob_match(p, pat):
                if ev == "@add":
                    if p not in adds:
                        adds[p] = git("log", "--diff-filter=A", "--format=%h %s", "--", p).strip().splitlines()
                    first = adds[p][-1] if adds[p] else ""
                    ev = "iamar-ai/iamar-kit %s" % first[:140] if first else "iamar-ai/iamar-kit (uncommitted)"
                rows[p] = {"made_by": made, "evidence": ev, "note": note}
                break
        else:
            unmatched.append(p)
    doc = {
        "format": "iamar-provenance", "version": 1,
        "about": "Where every shipped binary came from (an internal task, PUB3). made_by: hand | procedural | blender | "
                 "third-party:<row> | generative:<row> (rows: kit/inventory/licences.json). tools/export_public.py "
                 "withholds generative:*. Rebuild with python3 kit/catalog/provenance_build.py; "
                 "python3 kit/catalog/catalog.py check verifies it.",
        "rows": {k: rows[k] for k in sorted(rows)},
    }
    return doc, unmatched


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    doc, unmatched = build()
    for p in unmatched:
        print("FAIL no provenance rule for %s (add one to RULES in kit/catalog/provenance_build.py)" % p)
    gen = sorted(p for p, r in doc["rows"].items() if r["made_by"].startswith("generative:"))
    if a.check:
        stale = not OUT.is_file() or OUT.read_text(encoding="utf-8") != dump(doc)
        if stale:
            print("FAIL provenance.json is stale: run python3 kit/catalog/provenance_build.py")
        return 1 if stale or unmatched else 0
    OUT.write_text(dump(doc), encoding="utf-8", newline="\n")
    print("PROVENANCE %d rows, %d generative (withheld by the exporter), %d without a rule" % (
        len(doc["rows"]), len(gen), len(unmatched)))
    return 1 if unmatched else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
