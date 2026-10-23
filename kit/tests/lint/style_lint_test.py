#!/usr/bin/env python3
"""Checks kit/lint: the style lint passes the city's own sample (iamar profile) and a custom
world with its own style.json, fails seeded violations one by one, and compare-shots tells a
same-camera change from a moved camera, new pink, rising black and palette drift.

    python3 kit/tests/lint/style_lint_test.py

Texture and screenshot checks need numpy and Pillow; without them those parts report SKIPPED.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
LINT = KIT / "lint" / "style_lint.py"
SHOTS = KIT / "lint" / "compare_shots.py"
SAMPLES = KIT / "lint" / "samples"
sys.path.insert(0, str(HERE))
from glb_fixture import house, png, write_glb  # noqa: E402


def run(tool, *args):
    return subprocess.run([sys.executable, str(tool), *map(str, args)], capture_output=True, text=True)


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (("  " + detail.strip()[-700:]) if detail and not cond else ""), flush=True)

    try:
        import numpy  # noqa: F401
        from PIL import Image
        have_pil = True
    except ImportError as e:
        have_pil = False
        print("SKIPPED texture and screenshot checks (%s)" % e)

    # --- the samples
    p = run(LINT, SAMPLES / "iamar_city")
    check("city's own sample passes the iamar profile", p.returncode == 0 and "OK style lint (iamar)" in p.stdout, p.stdout)
    check("city sample reports triangles per model", "3635 triangles" in p.stdout and "placed triangles" in p.stdout, p.stdout)
    p = run(LINT, SAMPLES / "desert_post")
    check("custom world uses its own style.json and passes", p.returncode == 0 and "desert_trading_post" in p.stdout, p.stdout)
    p = run(LINT, "--style", "iamar", SAMPLES / "desert_post")
    check("custom world fails the iamar profile (flat roofs)", p.returncode == 1 and "[roof]" in p.stdout, p.stdout)
    p = run(LINT, "--json", SAMPLES / "iamar_city")
    try:
        j = json.loads(p.stdout)
        check("--json report", j["ok"] is True and j["profiles"] == ["iamar"] and j["items"], p.stdout)
    except ValueError:
        check("--json report", False, p.stdout)

    with tempfile.TemporaryDirectory(prefix="iamar-lint-") as raw:
        tmp = Path(raw)
        good = write_glb(tmp / "house.glb", house(arch_rise=0.9))
        p = run(LINT, good)
        check("a well-made house passes", p.returncode == 0, p.stdout)
        check("door, roof and arch are measured", "door 'Door' 2.20 m" in p.stdout and "roof 'Roof' pitch" in p.stdout
              and "arch 'DoorArch'" in p.stdout, p.stdout)

        seeded = {
            "over budget (efficiency under 60)": (house(tris=5400), [], "[budget]"),
            "black surface": (house(wall="#050505"), [], "forbidden colour"),
            "too dark": (house(wall="#140f0a"), [], "darker than min_albedo_value"),
            "neon colour": (house(roof="#39ff14"), [], "more saturated"),
            "off-palette walls": (house(wall="#5fa8d3"), [], "off the iamar palette"),
            "short door": (house(door_h=1.6), [], "door 'Door' is 1.60 m"),
            "giant door": (house(door_h=3.6), [], "door 'Door' is 3.60 m"),
            "landmark-size door on a house": (house(door_h=5.0), [], "door 'Door' is 5.00 m"),
            "roof too steep": (house(roof_rise=8.0), [], "roof 'Roof' pitch"),
            "roof too flat": (house(roof_rise=0.4), [], "roof 'Roof' pitch"),
            "flattened arch": (house(arch_rise=0.3), [], "arch 'DoorArch' rise / half span"),
            "giant person": ([{"name": "Body", "min": [-0.3, 0, -0.2], "max": [0.3, 2.6, 0.2], "color": "#b9874f"}],
                             ["--class", "character"], "character is 2.60 m tall"),
            "LOD1 not lighter": ([{"name": "Walls", "min": [-4, 0, -3], "max": [4, 6, 3], "color": "#ece1c6", "lod": 0, "tris": 600},
                                  {"name": "Walls", "min": [-4, 0, -3], "max": [4, 6, 3], "color": "#ece1c6", "lod": 1, "tris": 800}],
                                 [], "LOD1 has 800 triangles"),
        }
        if have_pil:
            seeded["missing-texture pink"] = ([{"name": "Walls", "min": [-4, 0, -3], "max": [4, 6, 3], "texture": png(8, 8, (255, 0, 255))}],
                                              [], "missing-texture pink")
            seeded["textured off-palette"] = ([{"name": "Walls", "min": [-4, 0, -3], "max": [4, 6, 3], "texture": png(8, 8, (40, 200, 220))}],
                                              [], "off the iamar palette")
        for name, (parts, extra, needle) in seeded.items():
            f = write_glb(tmp / "seeded" / ("%s.glb" % ("house" if "person" not in name else "body")), parts)
            p = run(LINT, *extra, f)
            check("seeded %s fails" % name, p.returncode == 1 and needle in p.stdout, p.stdout)

        if have_pil:
            # an atlas texture: black where no UV reaches is fine; sampled at the UVs it is plaster
            atlas = [(236, 225, 198) if x < 4 and y < 4 else (0, 0, 0) for y in range(8) for x in range(8)]
            f = write_glb(tmp / "atlas" / "house.glb", [{"name": "Walls", "min": [-4, 0, -3], "max": [4, 6, 3], "texture": png(8, 8, atlas)}])
            p = run(LINT, f)
            check("unused black atlas space is not judged", p.returncode == 0, p.stdout)

        # glow and allow_dark swatches are exempt
        f = write_glb(tmp / "glow" / "house.glb", house() + [
            {"name": "Opening", "min": [-0.5, 0, 3.0], "max": [0.5, 2.0, 3.05], "color": "#1e1a17"},
            {"name": "Ember", "min": [1, 1, 3.0], "max": [1.2, 1.2, 3.05], "color": "#ff5a10"}])
        p = run(LINT, f)
        check("profile glow and allow_dark colours are exempt", p.returncode == 0, p.stdout)

        # budgets come from the profile: 2800 triangles pass iamar (3000), fail the desert (2500)
        world = tmp / "budget_world"
        shutil.copytree(SAMPLES / "desert_post", world)
        write_glb(world / "assets" / "adobe_house_wide.glb",
                  house(width=10, depth=7, tris=2800, roof_rise=0.3, wall="#d6b48a", roof="#a9835c", door="#6b4a2e", wall_h=3.2))
        p = run(LINT, world)
        check("custom profile's tighter budget applies", p.returncode == 0 and "2800 triangles at LOD0 > building budget 2500" in p.stdout, p.stdout)
        b = json.loads((world / "style.json").read_text(encoding="utf-8"))
        b["lint"]["min_efficiency"] = 95
        (world / "style.json").write_text(json.dumps(b), encoding="utf-8")
        p = run(LINT, world)
        check("custom profile's own lint tolerances apply", p.returncode == 1 and "fails at 95" in p.stdout, p.stdout)

        # repeated neighbours, missing asset, forbidden primitive colour
        world = tmp / "street"
        shutil.copytree(SAMPLES / "iamar_city", world)
        sc = json.loads((world / "scene.json").read_text(encoding="utf-8"))
        sc["objects"].append({"id": "b005_twin", "asset": "assets/B005.glb", "position": [14, 0, 8], "rotation": [0, 90, 0]})
        (world / "scene.json").write_text(json.dumps(sc), encoding="utf-8")
        p = run(LINT, world)
        check("seeded repeated neighbour fails", p.returncode == 1 and "[neighbours]" in p.stdout and "b005_twin" in p.stdout, p.stdout)
        sc["objects"][-1]["scale"] = 1.2
        (world / "scene.json").write_text(json.dumps(sc), encoding="utf-8")
        p = run(LINT, world)
        check("a scaled twin is not a repeat", p.returncode == 0, p.stdout)
        sc["objects"].append({"id": "ghost", "asset": "assets/missing.glb", "position": [40, 0, 0]})
        sc["primitives"].append({"id": "void", "shape": "box", "size": [1, 1, 1], "position": [0, 0, 5], "color": "#000000"})
        (world / "scene.json").write_text(json.dumps(sc), encoding="utf-8")
        p = run(LINT, world)
        check("seeded missing asset and black primitive fail", p.returncode == 1 and "missing.glb is missing" in p.stdout
              and "primitives.void" in p.stdout, p.stdout)
        # an invisible collision proxy (fully transparent, AGENT_KIT "Invisible collision") is no colour
        sc["objects"].pop()
        sc["primitives"][-1]["color"] = "#00000000"
        (world / "scene.json").write_text(json.dumps(sc), encoding="utf-8")
        p = run(LINT, world)
        check("a fully transparent collision primitive has no colour rules", "primitives.void" in p.stdout
              and "[colour]" not in "".join(l for l in p.stdout.splitlines() if "primitives.void" in l and l.startswith("ERROR")),
              p.stdout)

        # a baked-light (unlit) material's dark texels are shade: audit dark-bake judges them
        sys.path.insert(0, str(KIT / "tests" / "audit"))
        from audit_fixture import box as fbox, part as fpart, write_glb as fwrite
        baked = tmp / "baked_shed.glb"
        fwrite(baked, [fpart("Walls", [fbox([-2, 0, -2], [2, 2.5, 2])], baked=(200, 190, 170)),
                       fpart("Eaves", [fbox([-2.2, 2.5, -2.2], [2.2, 2.8, 2.2])], baked=(3, 3, 3))])
        p = run(LINT, baked)
        check("baked (unlit) dark texels are left to audit dark-bake", p.returncode == 0 and "audit dark-bake" in p.stdout, p.stdout)
        flat = tmp / "black_shed.glb"
        fwrite(flat, [fpart("Walls", [fbox([-2, 0, -2], [2, 2.5, 2])], color="#020202")])
        p = run(LINT, flat)
        check("a black (lit) material still fails", p.returncode == 1 and "min_albedo_value" in p.stdout, p.stdout)
        # baked shade is no palette colour either (desert blind test gap 7): hidden undersides
        # baked black on most triangles, against a profile with no dark swatch to absorb them
        light = tmp / "salt_light.json"
        light.write_text(json.dumps({"id": "salt_light", "palette": {"sand": {"hex": "#c8beaa"}, "door": {"hex": "#3fa8a0"}}}),
                         encoding="utf-8")
        under = [fbox([-2, -0.3, -2], [2, 0, 2]), fbox([-1, -0.6, -1], [1, -0.3, 1]), fbox([-0.5, -0.9, -0.5], [0.5, -0.6, 0.5])]
        hidden = tmp / "baked_hidden.glb"
        fwrite(hidden, [fpart("Walls", [fbox([-2, 0, -2], [2, 2.5, 2])], baked=(200, 190, 170)),
                        fpart("Under", under, baked=(4, 4, 4))])
        p = run(LINT, hidden, "--style", light)
        check("baked black hidden faces are not off-palette", p.returncode == 0 and "OK style lint" in p.stdout
              and "[palette]" not in "".join(l for l in p.stdout.splitlines() if not l.startswith("INFO")), p.stdout)
        violet = tmp / "baked_violet.glb"
        fwrite(violet, [fpart("Walls", [fbox([-2, 0, -2], [2, 2.5, 2])], baked=(200, 190, 170)),
                        fpart("Under", under, baked=(110, 90, 130))])
        p = run(LINT, violet, "--style", light)
        check("a lit off-palette baked colour still fails the palette", p.returncode == 1 and "off the salt_light palette" in p.stdout, p.stdout)

        # model classes: the first class word wins (a person or animal after a place word wins); piers, masts and boats are not buildings
        sys.path.insert(0, str(KIT / "lint"))
        import style_lint as sl
        bud = json.loads((KIT / "style" / "iamar" / "style.json").read_text(encoding="utf-8"))["budgets"]["triangles"]
        got = {n: sl.classify(n, size, None, bud)[0] for n, size in
               (("fish_hall.glb", [12, 7, 8]), ("boat_fish.glb", [3, 2, 7]), ("pier.glb", [5, 2, 28]),
                ("flag_mast.glb", [1, 9, 1]), ("bell_frame.glb", [3, 4, 3]), ("harbour_ground.glb", [90, 1, 50]),
                ("guard_house.glb", [6, 6, 6]), ("hand_cart.glb", [1.5, 1, 2.5]), ("gull.glb", [1, 0.3, 1]))}
        want = {"fish_hall.glb": "landmark", "boat_fish.glb": "vehicle", "pier.glb": "structure", "flag_mast.glb": "structure",
                "bell_frame.glb": "structure", "harbour_ground.glb": "structure", "guard_house.glb": "building",
                "hand_cart.glb": "prop", "gull.glb": "creature"}
        check("model classes from names (hall, boat, pier, mast, frame, ground, small cart)", got == want, str(got))
        # people and animals named after a place stay people and animals (review of 39b12609)
        got = {n: sl.classify(n, [0.8, 1.8, 0.5], None, bud)[0] for n in
               ("gate_guard.glb", "arch_knight.glb", "dock_gull.glb", "pier_duck.glb", "tavern_merchant.glb",
                "blacksmith_npc.glb", "fountain_fish.glb")}
        want = {"gate_guard.glb": "character", "arch_knight.glb": "character", "dock_gull.glb": "creature",
                "pier_duck.glb": "creature", "tavern_merchant.glb": "character", "blacksmith_npc.glb": "character",
                "fountain_fish.glb": "creature"}
        check("model classes: a guard at a gate is a character, a gull on a dock a creature", got == want, str(got))
        # a building named after its people or sign stays a building (review of 48c8a798)
        got = {n: sl.classify(n, [12, 10, 12], None, bud)[0] for n in
               ("hall_of_heroes.glb", "tavern_of_the_fox.glb", "guildhall_merchants.glb", "tavern_merchant.glb")}
        want = {"hall_of_heroes.glb": "landmark", "tavern_of_the_fox.glb": "building",
                "guildhall_merchants.glb": "landmark", "tavern_merchant.glb": "building"}
        check("model classes: a 12 m hall of heroes is a hall, not a hero", got == want, str(got))

        # harbour blind test gaps G7, G8, G11 (an internal task)
        # trees and plants have their own class; furniture named after a place is furniture
        got = {n: sl.classify(n, size, None, bud)[0] for n, size in
               (("elm_tree.glb", [5.5, 9.7, 5.4]), ("hedge.glb", [4, 1.2, 1]), ("tree_house.glb", [6, 8, 6]),
                ("hall_bench.glb", [1.8, 0.9, 0.5]), ("tavern_table.glb", [2, 0.8, 1]), ("table_rock.glb", [12, 4, 9]))}
        want = {"elm_tree.glb": "tree", "hedge.glb": "tree", "tree_house.glb": "building", "hall_bench.glb": "prop",
                "tavern_table.glb": "prop", "table_rock.glb": "building"}
        check("model classes: trees and hedges are trees, a hall bench is a prop (G8, G11)", got == want, str(got))
        # a catalogue copy keeps its catalogue class whatever its file is called
        cat = KIT / "catalog" / "assets"
        shutil.copy(cat / "furniture" / "hall_bench.glb", tmp / "great_hall.glb")
        shutil.copy(cat / "trees" / "elm_tree.glb", tmp / "big_house.glb")
        p = run(LINT, tmp / "great_hall.glb", tmp / "big_house.glb")
        check("catalogue copies take the catalogue class, not name words", p.returncode == 0
              and "class prop by catalogue" in p.stdout and "class tree by catalogue" in p.stdout, p.stdout)
        # style-gen arch: the lint measures the arch ring, not the sample wall around it (G7)
        p = subprocess.run([sys.executable, str(KIT / "style" / "gen" / "gen.py"), "arch", str(tmp / "portal_arch.glb"),
                            "--width", "2.4", "--door-h", "3.0", "--ceiling", "4.2"], capture_output=True, text=True)
        p = run(LINT, tmp / "portal_arch.glb")
        check("style-gen arch passes the arch rule (ring rise / half span 0.55)", p.returncode == 0
              and "rise / half span 0.55" in p.stdout, p.stdout + p.stderr)
        # reused by hash (manifest.reused, `assets use <hash> --as`): resolved like validate, not missing (G8)
        world = tmp / "reuse"
        shutil.copytree(SAMPLES / "iamar_city", world)
        m = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
        entries = {e["id"]: e for e in json.loads((KIT / "catalog" / "catalog.json").read_text(encoding="utf-8"))["entries"]}
        def rec(eid, path):
            e = entries[eid]
            return {"path": path, "sha256": e["source"]["sha256"], "bytes": e["bytes"], "license": e["licence"],
                    "source": {"world": "iamar", "kind": "builtin" if e["source"]["origin"] == "builtin" else "world",
                               "file": e["source"]["file"]}}
        bench = next(e["id"] for e in entries.values() if e["source"].get("file") == "kit/catalog/assets/furniture/hall_bench.glb")
        m["reused"] = [rec("346eebd23986793b", "assets/crate.glb"), rec(bench, "assets/bench.glb")]
        (world / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        sc = json.loads((world / "scene.json").read_text(encoding="utf-8"))
        sc["objects"] += [{"id": "crate_0", "asset": "assets/crate.glb", "position": [30, 0, 30]}]
        sc["objects"] += [{"id": "bench_%d" % i, "asset": "assets/bench.glb", "position": [30 + 2 * i, 0, 34]} for i in range(6)]
        (world / "scene.json").write_text(json.dumps(sc), encoding="utf-8")
        p = run(LINT, world)
        check("reused (hash-referenced) assets are resolved, not missing", p.returncode == 0 and "is missing" not in p.stdout
              and "linting the kit's copy kit/catalog/assets/furniture/hall_bench.glb" in p.stdout
              and "catalogue 'box', 124 triangles" in p.stdout, p.stdout)

        # a reused built-in with bare metal (Kenney pot_large, metallicFactor 1) is flagged by name (an internal task)
        world = tmp / "reuse_pot"
        shutil.copytree(SAMPLES / "iamar_city", world)
        m = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
        m["reused"] = [rec("57e60214bc6ab1dc", "assets/pot_large.glb")]
        (world / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        sc = json.loads((world / "scene.json").read_text(encoding="utf-8"))
        sc["objects"] += [{"id": "pot_0", "asset": "assets/pot_large.glb", "position": [30, 0, 30]}]
        (world / "scene.json").write_text(json.dumps(sc), encoding="utf-8")
        p = run(LINT, world)
        check("reused pot_large: WARN [metal] names the material and the eye-height shot", p.returncode == 0
              and "WARN  reuse_pot/assets/pot_large.glb [metal]" in p.stdout and "eye-height shot" in p.stdout, p.stdout)


        # a placement's scene.json "tint" multiplies the reused object's albedo before the colour checks (an internal task)
        grass = "260e41d3e5f24724"   # built-in grass, mean colour #73eddd: off the iamar palette untinted
        def tinted(tint):
            w = tmp / "reuse_tint"
            shutil.rmtree(w, ignore_errors=True)
            shutil.copytree(SAMPLES / "iamar_city", w)
            mm = json.loads((w / "manifest.json").read_text(encoding="utf-8"))
            mm["reused"] = [rec(grass, "assets/grass.glb")]
            (w / "manifest.json").write_text(json.dumps(mm), encoding="utf-8")
            ss = json.loads((w / "scene.json").read_text(encoding="utf-8"))
            ss["objects"] += [dict({"id": "g0", "asset": "assets/grass.glb", "position": [30, 0, 30]}, **({"tint": tint} if tint else {}))]
            (w / "scene.json").write_text(json.dumps(ss), encoding="utf-8")
            return run(LINT, w).stdout
        out = tinted(None)
        check("reused grass untinted: WARN [palette]", "WARN  reuse_tint/assets/grass.glb [palette]" in out, out)
        out = tinted("#ffa8a7")
        check("reused grass tinted to a palette stone colour: no [palette] WARN, tint named",
              "WARN  reuse_tint/assets/grass.glb [palette]" not in out, out)
        out = tinted("#0a0a0a")
        check("reused grass tinted near black: WARN [colour]", "WARN  reuse_tint/assets/grass.glb [colour]" in out and "tinted #0a0a0a" in out, out)

        # the tint also applies to the world's own files and copied catalogue objects, and a visibly
        # different tint makes two same buildings different neighbours (an internal task)
        def own_tinted(edit):
            w = tmp / "own_tint"
            shutil.rmtree(w, ignore_errors=True)
            shutil.copytree(SAMPLES / "iamar_city", w)
            ss = json.loads((w / "scene.json").read_text(encoding="utf-8"))
            edit(ss["objects"])
            (w / "scene.json").write_text(json.dumps(ss), encoding="utf-8")
            return run(LINT, w)
        p = own_tinted(lambda objs: [o.update(tint="#0A0A0A") for o in objs if o["id"] == "b005"])
        check("own file tinted near black: ERROR [colour] on the tinted placement", p.returncode == 1
              and "ERROR own_tint/assets/B005.glb tinted #0a0a0a [colour]" in p.stdout, p.stdout)
        twin = {"id": "b003_twin", "asset": "assets/B003.glb", "position": [4, 0, 0]}
        p = own_tinted(lambda objs: objs.append(dict(twin, tint="#c08060")))
        check("same building 4 m away, visibly different tint: no [neighbours] ERROR", p.returncode == 0
              and "[neighbours]" not in p.stdout and "B003.glb tinted #c08060 [palette]" in p.stdout, p.stdout)
        for t in ("#ffffff", "#fefefe"):
            p = own_tinted(lambda objs: objs.append(dict(twin, tint=t)))
            check("same building 4 m away, tint %s (looks untinted): [neighbours] ERROR" % t, p.returncode == 1
                  and "ERROR own_tint:objects.b003_twin [neighbours]" in p.stdout, p.stdout)

        # compare-shots
        if have_pil:
            import numpy as np
            rng = np.random.default_rng(7)
            h, w = 180, 320
            yy, xx = np.mgrid[0:h, 0:w]
            sky = np.stack([np.full((h, w), 0.80), np.full((h, w), 0.86), np.full((h, w), 0.92)], axis=-1)
            scene_ = sky.copy()
            for _ in range(14):  # plaster and slate houses on a cobbled street
                x0, y0 = rng.integers(0, w - 60), rng.integers(60, h - 60)
                col = [(0.93, 0.88, 0.78), (0.24, 0.36, 0.55), (0.64, 0.61, 0.56), (0.36, 0.23, 0.13)][rng.integers(0, 4)]
                scene_[y0:y0 + rng.integers(20, 60), x0:x0 + rng.integers(20, 60)] = col
            scene_[150:] = (0.58, 0.56, 0.51)

            def save(arr, d, name="cam_street.png"):
                d.mkdir(parents=True, exist_ok=True)
                Image.fromarray((np.clip(arr, 0, 1) * 255).astype("uint8")).save(d / name)
                return d / name

            before = save(scene_, tmp / "before")
            p = run(SHOTS, before, save(scene_ * 0.97, tmp / "same"))
            check("compare-shots: same camera, small light change passes", p.returncode == 0 and "OK " in p.stdout, p.stdout)
            moved = np.roll(np.roll(scene_, 90, axis=1), 40, axis=0)
            p = run(SHOTS, before, save(moved, tmp / "moved"))
            check("compare-shots: moved camera is refused", p.returncode == 1 and "camera moved" in p.stdout, p.stdout)
            pink = scene_.copy()
            pink[20:60, 20:80] = (1.0, 0.0, 1.0)
            p = run(SHOTS, before, save(pink, tmp / "pink"))
            check("compare-shots: new missing-texture pink fails", p.returncode == 1 and "pink" in p.stdout, p.stdout)
            dark = scene_.copy()
            dark[60:150] = 0.0
            p = run(SHOTS, before, save(dark, tmp / "dark"), "--min-edge-corr", "0")
            check("compare-shots: rising black fails", p.returncode == 1 and "black pixels rose" in p.stdout, p.stdout)
            neon = scene_.copy()
            mask = (scene_ != sky).any(axis=-1)
            neon[mask] = (0.2, 1.0, 0.3)
            p = run(SHOTS, before, save(neon, tmp / "neon"), "--min-edge-corr", "0")
            check("compare-shots: palette drift fails", p.returncode == 1 and "on-palette share fell" in p.stdout, p.stdout)
            p = run(SHOTS, before, save(neon, tmp / "neon_d"), "--style", SAMPLES / "desert_post" / "style.json", "--min-edge-corr", "0", "--json")
            check("compare-shots: takes a custom profile", '"profile": "desert_trading_post"' in p.stdout, p.stdout)
            p = run(SHOTS, tmp / "before", tmp / "same", "--out", tmp / "sheets")
            check("compare-shots: folders pair by name and write a sheet", p.returncode == 0 and (tmp / "sheets" / "cam_street_compare.png").is_file(), p.stdout)
            p = run(SHOTS, before, save(scene_, tmp / "same2"), "--max-change", "0.0001")
            check("compare-shots: --max-change passes an unchanged shot", p.returncode == 0, p.stdout)

    n = len(checks)
    print("style lint tests: %d/%d" % (sum(checks), n))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
