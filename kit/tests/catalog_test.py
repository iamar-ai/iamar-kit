#!/usr/bin/env python3
"""The object catalogue (kit/catalog): fresh and valid, search by description finds the
right entries, seeded mistakes fail, and `iamar-world assets search` uses it."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "catalog"))
import catalog  # noqa: E402


def ids(hits):
    return [e["id"] for e in hits]


def quiet(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a)
    return rc, buf.getvalue()


def main() -> None:
    rc, out = quiet(catalog.check)
    assert rc == 0, out
    cat = catalog.load(catalog.CATALOG)
    entries = cat["entries"]
    builtin = catalog.load(catalog.BUILTIN)["objects"]
    city = catalog.load(catalog.CITY)["models"] + catalog.load(catalog.INSECTS)["models"] + catalog.load(catalog.PIECES)["models"] + catalog.load(catalog.BUILDINGS)["models"] + catalog.load(catalog.CLOSED)["models"] + catalog.load(catalog.INTERIORS)["models"] + catalog.load(catalog.MOUNTS)["models"] + catalog.load(catalog.HARBOUR)["models"] + catalog.load(catalog.COASTAL)["models"]
    creatures = catalog.load(catalog.PROCEDURAL)["creatures"]
    assert len(creatures) == 11, [c["kind"] for c in creatures]   # farm, wild and pond kinds (the iamar browser source (not public) 98c2ecd2)
    assert len(entries) == len(builtin) + len(creatures) + 7 + len(city), len(entries)   # + creatures + building generators + city models + insects + pieces + buildings + mounts + harbour + coastal
    cats = {c["id"] for c in catalog.load(catalog.VOCAB)["categories"]}
    assert all(e["category"] in cats for e in entries)

    # every open-sided city house has a closed variant (assets/close_open_sides.py, an internal task):
    # its own entry without the open side, and the open original's description names it
    by_file = {e["source"].get("file"): e for e in entries}
    opened = [r for r in catalog.load(catalog.BUILDINGS)["models"] if r.get("open_sides")]
    assert len(opened) >= 32, [r["file"] for r in opened]   # 6, then 32 after PUB6 batch 1 (an internal task)
    for r in opened:
        stem = r["file"].rsplit(".", 1)[0]
        variant = by_file["kit/catalog/assets/%s_closed.glb" % stem]
        original = by_file["kit/catalog/assets/" + r["file"]]
        assert "open side" not in variant["tags"] and "open side" in original["tags"], stem
        assert variant["id"] in original["description"], original["description"]
        assert variant["triangles"]["lod0"] > original["triangles"]["lod0"], stem
    assert any(e["name"].endswith("(closed)") for e in catalog.search(cat, "detached house"))
    sys.path.insert(0, str(catalog.ASSETS))
    import close_open_sides
    rc, out = quiet(close_open_sides.check)
    assert rc == 0, out
    # and every house's single-sheet trim has its back (assets/seal_trim_edges.py, an internal task)
    import seal_trim_edges
    rc, out = quiet(seal_trim_edges.check)
    assert rc == 0, out
    # room interiors (assets/import_city_interiors.py, PUB6 batch 2 an internal task): moved by their shell's
    # offset, so a room and its catalogued shell (and its closed variant) pair and name each other
    import import_city_interiors
    rc, out = quiet(import_city_interiors.check)
    assert rc == 0, out
    rooms = catalog.load(catalog.INTERIORS)["models"]
    assert len(rooms) >= 22 and all(by_file["kit/catalog/assets/" + r["file"]]["category"] == "interior" for r in rooms)
    shells = {r["models_id"]: r for r in catalog.load(catalog.BUILDINGS)["models"]}
    paired = 0
    for r in rooms:
        room = by_file["kit/catalog/assets/" + r["file"]]
        sh = shells.get(r["shell"] or "")
        if sh is None:
            assert not room["pairings"] and "not in the catalogue" in room["description"], r["file"]
            continue
        shell = by_file["kit/catalog/assets/" + sh["file"]]
        assert r["recentred_by"] == sh["recentred_by"], r["file"]
        assert shell["id"] in room["pairings"] and room["id"] in shell["pairings"], r["file"]
        assert shell["id"] in room["description"] and room["id"] in shell["description"], r["file"]
        paired += 1
    assert paired >= 13, paired   # B001 B007 B021 B039 B055 S01, and batch 3 (an internal task): B058 B082 BIRD01 C02 C03 DRAGON01 W01
    lib = by_file["kit/catalog/assets/interiors/interior_c02.glb"]   # the library ships its 9 parts inside
    assert len(next(r for r in rooms if r["models_id"] == "Interior_C02")["parts"]) == 9
    assert catalog.search(cat, "tavern interior")[0]["category"] == "interior", ids(catalog.search(cat, "tavern interior"))
    assert lib in catalog.search(cat, "library interior")[:3], ids(catalog.search(cat, "library interior"))
    # the harbour set's hashes: import_city_models.py --check leaves harbour/*.glb to harbour.py (4bc29dd)
    import harbour
    rc, out = quiet(harbour.check)
    assert rc == 0, out

    # the done-when sample: horse, small animal, chair
    horse = catalog.search(cat, "horse")
    assert horse and horse[0]["id"] == "creature:horse", ids(horse)
    assert catalog.search(cat, "horses")[0]["id"] == "creature:horse"
    assert catalog.search(cat, "pony")[0]["id"] == "creature:horse"
    small = catalog.search(cat, "small animal")
    assert {"creature:bunny", "creature:chicken"} <= set(ids(small)), ids(small)
    assert all(e["category"] in {"animal-small", "bird", "insect"} for e in small), ids(small)
    assert "creature:horse" not in ids(small) and "creature:cow" not in ids(small)
    chair = catalog.search(cat, "chair")
    assert chair and "chair" in chair[0]["name"] and chair[0]["category"] == "furniture", ids(chair)
    # the built-in chair and the city's oak chair (C2e) both near the top
    top = {e["name"]: e for e in chair[:5]}
    assert "chair 1" in top and "oak chair" in top, ids(chair)
    assert top["chair 1"]["use"].startswith("iamar-world assets use <world folder> " + top["chair 1"]["id"])
    # descriptions, synonyms and category words find things the file name does not say
    seat = catalog.search(cat, "seat")
    assert any(e["name"] in ("stool", "bench") for e in seat)
    assert catalog.search(cat, "tavern")[0]["id"] == "generator:inn"
    assert catalog.search(cat, "rabbit")[0]["id"] == "creature:bunny"
    oak = catalog.search(cat, "tree oak")
    assert oak and all(e["category"] == "tree" for e in oak) and any("oak" in e["name"] for e in oak)
    assert catalog.search(cat, "dragon griffin unicorn") == []
    # filters
    assert all(e["category"] == "rock" for e in catalog.search(cat, "stone", category="rock"))
    med = catalog.search(cat, "chair", style="iamar-medieval")
    assert med and all("iamar-medieval" in e["style_compat"] for e in med)
    # C5: every entry is tagged, nature and creatures are neutral, the filter splits the catalogue
    assert all(e["style_compat"] for e in cat["entries"])
    assert all(e["style_compat"] == ["neutral"] for e in cat["entries"] if e["category"] in ("tree", "rabbit", "animal-small"))
    assert "neutral" in catalog.search(cat, "rabbit", style="neutral")[0]["style_compat"]
    assert catalog.search(cat, "rabbit", style="iamar-medieval") == []
    e2 = dict(cat["entries"][0], style_compat=[])
    assert any("style_compat is empty" in m for m in catalog.validate(dict(cat, entries=[e2])))
    # C3a: a generated description or missing synonyms fails the check (seeded misses)
    e3 = dict(cat["entries"][0], description_source="generated", synonyms=[])
    errs3 = catalog.validate(dict(cat, entries=[e3]))
    assert any("description is generated" in m for m in errs3) and any("no synonyms" in m for m in errs3)
    assert all(e["description_source"] == "written" and e["synonyms"] for e in cat["entries"])

    # the city's own objects (C2): found by what they are, with a file in the kit and a use line
    for q, name in (("wolf", "wolf"), ("well", "well"), ("market stall", "market stall"), ("anvil", "anvil"),
                    ("lamppost", "street lamp"), ("hitching post", "hitching rail"), ("deer", "deer")):
        hits = [e for e in catalog.search(cat, q)[:3] if e["name"] == name and e["source"]["origin"] == "city"]
        assert hits, (q, ids(catalog.search(cat, q))[:3])
        e = hits[0]
        assert e["source"]["origin"] == "city" and (KIT.parent / e["source"]["file"]).is_file(), e["source"]
        assert e["use"].startswith("copy kit/catalog/assets/") and e["triangles"]["lod0"] > 0
    assert {"oak tree", "elm tree", "pine tree"} <= {e["name"] for e in catalog.search(cat, "tree", category="tree")}
    assert any(e["name"] == "young dragon" for e in catalog.search(cat, "dragon"))
    small = {e["name"] for e in catalog.search(cat, "small animal")}
    assert {"rabbit", "frog", "duckling"} <= small, small
    # insects (C2g): found by what they are, each with its wing clip in the use line
    for q, name in (("bee", "bumblebee"), ("dragonfly", "dragonfly"), ("peacock butterfly", "peacock butterfly"),
                    ("red admiral", "red admiral butterfly")):
        hit = catalog.search(cat, q)[0]
        assert hit["name"] == name and hit["category"] == "insect", (q, ids(catalog.search(cat, q))[:3])
        assert (KIT.parent / hit["source"]["file"]).is_file() and '"animation": "' in hit["use"], hit["use"]
        assert hit["behaviours"] and hit["animations"], hit
    assert sum("butterfly" in e["name"] for e in catalog.search(cat, "butterfly", category="insect")) == 6
    # harbour set (an internal task): every piece found by what a harbour builder types, models with their
    # clips in the use line, sounds as scene.json sounds entries with a file that exists
    for q, name, category in (("rowboat", "rowboat", "vehicle"), ("fishing boat", "fishing boat", "vehicle"),
                              ("bollard", "mooring bollard", "prop"), ("harbour bell", "harbour bell", "prop"),
                              ("fishing net", "pile of fishing net", "prop"), ("herring gull", "herring gull", "bird"),
                              ("sea waves", "sea waves (ambient loop)", "audio"), ("bell sound", "harbour bell strike", "audio"),
                              ("gull call", "gull calls", "audio")):
        hit = catalog.search(cat, q)[0]
        assert hit["name"] == name and hit["category"] == category, (q, ids(catalog.search(cat, q))[:3])
        assert (KIT.parent / hit["source"]["file"]).is_file() and (KIT / hit["thumbnail"]).is_file(), hit
    for q in ("boat", "gull", "bell", "bollard", "net", "sound", "sea"):
        assert any("harbour/" in e["source"].get("file", "") for e in catalog.search(cat, q)[:5]), (q, ids(catalog.search(cat, q))[:5])
    sea = catalog.search(cat, "sea waves")[0]
    assert sea["kind"] == "audio" and 'scene.json sounds: {"id": "sea", "file": "audio/sea_waves.ogg", "loop": true' in sea["use"], sea["use"]
    assert '"position": [0, 2, 0]' in catalog.search(cat, "bell sound")[0]["use"]
    assert '"animation": "bob"' in catalog.search(cat, "rowboat")[0]["use"]
    assert set(catalog.search(cat, "herring gull")[0]["animations"]) == {"perch", "fly"}
    # mounts (C2d): griffin with a file per tier, the dragon breeds and the giant eagle, code-built
    # heads, each creature under 1 MB in the kit (all its LOD files together)
    byid = {e["id"]: e for e in entries}
    grif = catalog.search(cat, "griffin")[0]
    assert grif["name"] == "griffin" and set(grif["triangles"]) == {"lod0", "lod1", "lod2"}, grif["triangles"]
    t = grif["triangles"]
    assert t["lod0"] > t["lod1"] > t["lod2"] > 0, t
    assert set(grif["tier_variants"]) == {"low", "medium", "high"} and grif["tier_variants"]["high"] == grif["id"]
    files = [KIT.parent / byid[i]["source"]["file"] for i in grif["tier_variants"].values()]
    assert all(f.is_file() for f in files) and sum(f.stat().st_size for f in files) < 1_000_000, files
    assert byid[grif["tier_variants"]["low"]]["triangles"]["lod0"] == t["lod2"]
    assert "tiers/medium/assets/griffin.glb" in grif["use"] and "tiers/high/assets/griffin.glb" in grif["use"], grif["use"]
    for q, name in (("bronze wyrm", "bronze wyrm"), ("copper runner", "copper runner"), ("teal drake", "teal drake"),
                    ("giant eagle", "giant eagle"), ("gryphon", "griffin")):
        hit = catalog.search(cat, q)[0]
        assert hit["name"] == name and hit["bytes"] < 1_000_000, (q, ids(catalog.search(cat, q))[:3])
        assert "code-built" in hit["description"] and (KIT.parent / hit["source"]["file"]).is_file(), hit
    assert {"bronze wyrm", "copper runner", "teal drake"} <= {e["name"] for e in catalog.search(cat, "dragon breed")}

    # seeded mistakes fail the validator
    bad = copy.deepcopy(cat)
    bad["entries"][0].pop("licence")
    bad["entries"][1]["category"] = "spaceship"
    bad["entries"][2]["triangles"] = {"lod0": -1}
    bad["entries"][3]["colour"] = "red"
    bad["entries"][4]["id"] = bad["entries"][5]["id"]
    bad["entries"][6]["tier_variants"] = {"low": "0000000000000000", "huge": bad["entries"][7]["id"]}
    errs = catalog.validate(bad)
    for want in ("missing licence", "unknown category", "triangles must be", "unknown field colour", "duplicate id",
                 "tier_variants.low: no entry 0000000000000000", "tier_variants.huge: not a tier"):
        assert any(want in e for e in errs), (want, errs)

    # a built-in object added to the source without rebuilding makes check fail
    with tempfile.TemporaryDirectory() as tmp:
        src = catalog.load(catalog.BUILTIN)
        src["objects"].append({"file": "assets/props/New_Thing.glb", "sha256": "ab" * 32, "bytes": 10,
                               "triangles": 12, "size": [1, 1, 1], "license": "CC0-1.0", "author": "x"})
        p = Path(tmp) / "builtin.json"
        p.write_text(json.dumps(src))
        rc, out = quiet(catalog.check, p)
        assert rc == 1 and "stale" in out, out

    # a model shipped in kit/catalog/assets without a catalogue entry makes check fail
    stray = catalog.ASSETS / "props" / "zz_unlisted_test.glb"
    try:
        stray.write_bytes(b"glTF")
        rc, out = quiet(catalog.check)
        assert rc == 1 and "zz_unlisted_test.glb has no catalogue entry" in out, out
    finally:
        stray.unlink()

    # the launcher: `iamar-world assets search` answers from the catalogue, no browser needed
    bash = shutil.which("bash")
    if bash:
        env = dict(os.environ, PYTHON=sys.executable, IAMAR_KIT_NO_FETCH="1", IAMAR_BROWSER="")
        r = subprocess.run([bash, str(KIT / "iamar-world"), "assets", "search", "small", "animal"],
                           env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "creature:bunny" in r.stdout and "rabbit" in r.stdout, (r.stdout, r.stderr)
    r = subprocess.run([sys.executable, str(KIT / "catalog" / "catalog.py"), "search", "horse", "--json"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and json.loads(r.stdout)[0]["id"] == "creature:horse"
    # every id search prints resolves in show (gap 8 of the harbour blind test)
    for e in entries:
        assert catalog.find(cat, e["id"]) is e, e["id"]
        assert catalog.find(cat, e["id"].upper()) is e, e["id"]
    assert catalog.find(cat, "no-such-object-zz") is None
    if bash:
        r = subprocess.run([bash, str(KIT / "iamar-world"), "assets", "show", entries[0]["id"]],
                           env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and entries[0]["id"] in r.stdout, (r.stdout, r.stderr)
    # `assets use` takes every id search prints (gap 2 of harbour attempt 5): iamar originals are copied
    # with their tier files, built-ins (exit 3) go on to the browser, creatures/generators print their line
    with tempfile.TemporaryDirectory() as td:
        w = Path(td) / "w"
        w.mkdir()
        assert quiet(catalog.use, w, "ee961f40f70dc167", None)[0] == 1   # no manifest.json yet
        (w / "manifest.json").write_text("{}\n")
        n_copy = 0
        for e in entries:
            pairs = catalog.copies(e)
            rc, out = quiet(catalog.use, w, e["id"], None)
            if e["source"].get("origin") == "builtin":
                assert rc == 3 and not pairs, (e["id"], out)
                continue
            assert rc == 0, (e["id"], out)
            if not pairs:
                assert e["kind"] in ("creature", "generator") and out.startswith("USE "), (e["id"], out)
                continue
            n_copy += 1
            for src, dst in pairs:
                assert (w / dst).read_bytes() == (KIT.parent / src).read_bytes(), (e["id"], dst)
                (w / dst).unlink()
        assert n_copy == sum(1 for e in entries if e["use"].startswith("copy ")) and n_copy > 100, n_copy
        assert quiet(catalog.use, w, "no-such-object-zz", None)[0] == 3
        rc, out = quiet(catalog.use, w, "3ad7613c7a959ab2", "assets/beasts/griffin.glb")   # griffin: 3 tier files
        assert rc == 0 and all((w / p).is_file() for p in ("assets/beasts/griffin.glb", "tiers/medium/assets/beasts/griffin.glb",
                                                          "tiers/high/assets/beasts/griffin.glb")), out
        assert "TIERS manifest.json tiers lists medium and high" in out and '"asset": "assets/beasts/griffin.glb"' in out, out
        cr = json.loads((w / "manifest.json").read_text(encoding="utf-8")).get("credits", [])
        assert "CREDIT written" in out and any("assets/beasts/griffin.glb" in c["files"] and c["license"] and c["author"]
                                               for c in cr), (out, cr)
        assert quiet(catalog.use, w, "3ad7613c7a959ab2", "assets/beasts/griffin.glb")[0] == 1   # already there
        mf = (w / "manifest.json").read_text(encoding="utf-8")   # credits not a list: copy, warn, manifest untouched
        (w / "manifest.json").write_text(json.dumps({**json.loads(mf), "credits": "CREDITS.md"}), encoding="utf-8")
        rc, out = quiet(catalog.use, w, "3ad7613c7a959ab2", "assets/beasts/griffin2.glb")
        assert rc == 0 and "WARN could not write" in out and (w / "assets/beasts/griffin2.glb").is_file(), out
        assert json.loads((w / "manifest.json").read_text(encoding="utf-8"))["credits"] == "CREDITS.md"
        (w / "manifest.json").write_text(mf, encoding="utf-8")
        assert quiet(catalog.use, w, "3ad7613c7a959ab2", "../griffin.glb")[0] == 2
        assert quiet(catalog.use, w, "3ad7613c7a959ab2", "audio/griffin.glb")[0] == 2
        if bash:
            r = subprocess.run([bash, str(KIT / "iamar-world"), "assets", "use", str(w), "ee961f40f70dc167"],
                               env=env, capture_output=True, text=True, timeout=60)
            assert r.returncode == 0 and (w / "assets/gull.glb").is_file() and "COPIED" in r.stdout, (r.stdout, r.stderr)
            r = subprocess.run([bash, str(KIT / "iamar-world"), "assets", "use", str(w), "ee961f40f70dc167"],
                               env=env, capture_output=True, text=True, timeout=60)
            assert r.returncode == 1 and "already a file" in r.stdout, (r.stdout, r.stderr)
    # an internal task: search lines show what an object adds to the world's download and WARN over 1 MB,
    # never on light ones; built-ins (the "6 MB" bed: shared trim textures, referenced by hash) add 0
    builtin = [e for e in entries if e["source"].get("origin") == "builtin"]
    assert builtin and all("built in (0 MB download)" in catalog.line(e) and "WARN" not in catalog.line(e)
                           for e in builtin), "built-in shown with a download size"
    kit = [e for e in entries if e["source"].get("origin") != "builtin"]
    big = [e for e in kit if catalog.download_bytes(e) > 1048576]
    small = [e for e in kit if 0 < catalog.download_bytes(e) < 102400]
    assert big and all(" MB WARN large download" in catalog.line(e) for e in big), "no size WARN on large entries"
    assert small and not any("MB" in catalog.line(e).split("\n")[0] for e in small), "size shown on a light entry"
    # an internal task: search never dead-ends. Everyday words reach the objects (aliases, synonyms), a house
    # query puts the generator first and no furniture before the houses, a misspelling is corrected,
    # and a miss prints the nearest objects and how to make it.
    for q, want in (("house", "generator:house"), ("home", "generator:house"), ("cottage", "generator:house"),
                    ("inn", "generator:inn"), ("tavern", "generator:inn"), ("couch", None), ("palm", None)):
        hits = catalog.search(cat, q)
        assert hits and (want is None or hits[0]["id"] == want), (q, ids(hits)[:3])
    assert not any(e["category"] == "furniture" for e in catalog.search(cat, "house")[:15]), ids(catalog.search(cat, "house"))[:15]
    assert catalog.search(cat, "couch")[0]["name"] == "sofa" and catalog.search(cat, "palm")[0]["name"] == "palm tree"
    vocab = catalog.load(catalog.VOCAB)
    for word, targets in vocab["aliases"].items():   # every alias reaches something, through the alias itself
        hits = catalog.search(cat, word)
        assert hits, (word, targets)
        assert any(catalog.stem(t) in catalog.terms(" ".join([e["name"], e["category"], e.get("description", "")]
                                                           + e.get("synonyms", []) + e.get("tags", [])))
                   for e in hits[:5] for t in targets), (word, targets, ids(hits)[:5])
    assert catalog.search(cat, "ship")[0]["name"] == "fishing boat" and catalog.search(cat, "pier")[0]["name"] == "dock"
    corrected, nearest, make = catalog.near(cat, "sofaa")
    assert corrected == "sofa" and nearest[0]["name"] == "sofa" and make, (corrected, ids(nearest), make)
    corrected, nearest, make = catalog.near(cat, "drgon")
    assert corrected == "dragon" and nearest and all(e["category"] == "mythical" for e in nearest), (corrected, ids(nearest))
    corrected, nearest, make = catalog.near(cat, "spaceship")
    assert corrected == "" and nearest == [] and len(make) == 1 and "starter_build.py" in make[0], (corrected, make)
    corrected, nearest, make = catalog.near(cat, "lamp spaceship")
    assert nearest and all(e["category"] == "lamp" or "lamp" in catalog.terms(e["name"]) for e in nearest), ids(nearest)
    corrected, nearest, make = catalog.near(cat, "skyscraper building")
    assert any("assets building" in m for m in make) and "starter_build.py" in make[-1], make
    rc, out = quiet(catalog.main, ["search", "spaceship"])
    assert rc == 0 and "COUNT 0" in out and "\nMAKE model it in Blender" in out, out
    rc, out = quiet(catalog.main, ["search", "drgon"])
    assert "DID-YOU-MEAN dragon" in out and "\nNEAREST " in out, out
    rc, out = quiet(catalog.main, ["search", "drgon", "--json"])
    assert json.loads(out) == [], out   # --json output stays a plain list

    # PUB3 provenance (an internal task): every entry's file and previews have a row; the audit's findings hold
    import provenance_build as pb
    prov = catalog.load(pb.OUT)["rows"]
    for e in entries:
        f = str(e["source"].get("file", ""))
        for p in ([f] if f.startswith("kit/catalog/assets/") else []) + ["kit/" + e["thumbnail"], "kit/" + e["turntable"]]:
            assert p in prov and catalog.MADE_BY.match(prov[p]["made_by"]) and prov[p]["evidence"], p
    assert prov["kit/turntables/creature_wolf.png"]["made_by"] == "generative:gpt-image-1"
    assert prov["kit/thumbnails/creature_cow.png"]["made_by"] == "procedural"
    assert prov["kit/gallery/city/civic_skyline.jpg"]["made_by"] == "generative:hunyuan3d-2"
    assert prov["kit/catalog/assets/creatures/mounts/giant_eagle.glb"]["made_by"] == "procedural"
    assert prov["kit/catalog/assets/props/well.glb"]["made_by"] == "procedural"
    assert all(prov["kit/" + e["thumbnail"]]["made_by"].startswith("third-party:")
               for e in entries if e["source"].get("origin") == "builtin")
    if catalog.EXPORTED:   # the public kit has no licences.json and no source repo to compare against
        print("catalog_test: OK (%d entries, exported kit: seeded provenance mistakes skipped)" % len(entries))
        return
    # seeded mistakes: bad made_by, unknown licence row, no evidence, and the file is then stale
    real_out = pb.OUT
    with tempfile.TemporaryDirectory() as td:
        bad = dict(catalog.load(real_out))
        bad["rows"] = dict(bad["rows"], **{
            "kit/thumbnails/creature_cow.png": {"made_by": "ai", "evidence": "x"},
            "kit/thumbnails/creature_frog.png": {"made_by": "generative:no-such-row", "evidence": "x"},
            "kit/thumbnails/creature_duck.png": {"made_by": "procedural", "evidence": ""}})
        pb.OUT = Path(td) / "provenance.json"
        pb.OUT.write_text(json.dumps(bad), encoding="utf-8")
        try:
            errs = "\n".join(catalog.provenance_errors())
        finally:
            pb.OUT = real_out
    for want in ("creature_cow.png: made_by 'ai'", "generative:no-such-row is not a row", "creature_duck.png: no evidence",
                 "provenance.json is stale"):
        assert want in errs, (want, errs)
    print("catalog_test: OK (%d entries)" % len(entries))


if __name__ == "__main__":
    main()
