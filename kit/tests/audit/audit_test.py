#!/usr/bin/env python3
"""Checks kit/audit: all six audits pass the audit sample world and the desert sample, and each
one fails a copy of the sample broken on purpose (one fault per audit), naming the fault.

    python3 kit/tests/audit/audit_test.py

Needs numpy and Pillow; without numpy the test reports SKIPPED.
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
AUDIT = KIT / "audit" / "audit.py"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT / "audit" / "samples"))
from audit_fixture import box, hollow_house, part, scene, write_glb  # noqa: E402
import make_samples  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(AUDIT), *map(str, args)], capture_output=True, text=True)


def items(p, audit, level="ERROR"):
    try:
        data = json.loads(p.stdout)
    except ValueError:
        return []
    return [i for i in data["items"] if i["audit"] == audit and i["level"] == level]


def world(tmp: Path, name: str, house_kw=None, extra=(), crate=None, objects=None) -> Path:
    """The audit yard with house_a replaced by a variant (and optional extra objects)."""
    w = make_samples.build(tmp / name)
    if house_kw is not None:
        write_glb(w / "assets" / "house_var.glb", hollow_house(**house_kw))
    if crate is not None:
        write_glb(w / "assets" / "crate.glb", crate)
    sc = json.loads((w / "scene.json").read_text())
    if house_kw is not None:
        sc["objects"][0]["asset"] = "assets/house_var.glb"
    sc["objects"] += list(extra)
    if objects is not None:
        sc["objects"] = objects(sc["objects"])
    (w / "scene.json").write_text(json.dumps(sc, indent=1))
    return w


def main() -> int:
    try:
        import numpy  # noqa: F401
    except ImportError:
        print("SKIPPED kit audit tests: numpy not installed")
        return 0
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (("  " + detail.strip()[-900:]) if detail and not cond else ""), flush=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        good = make_samples.build(tmp / "good")
        committed = KIT / "audit" / "samples" / "audit_yard"
        same = all((good / f).read_bytes() == (committed / f).read_bytes()
                   for f in ("scene.json", "manifest.json", "assets/house.glb", "assets/crate.glb"))
        check("sample: committed audit_yard matches make_samples.py", same)
        p = run("all", committed, "--json")
        check("sample: all six audits pass audit_yard", p.returncode == 0 and json.loads(p.stdout)["ok"], p.stdout + p.stderr)
        p = run("all", KIT / "lint" / "samples" / "desert_post")
        check("sample: all six audits pass the desert sample", p.returncode == 0, p.stdout + p.stderr)
        for name in ("closure", "zfight", "roof", "edge", "door", "dark-bake"):
            p = run(name, committed)
            check("cli: %s passes the sample alone" % name, p.returncode == 0 and "RESULT" in p.stdout, p.stdout + p.stderr)
        p = run("bogus", committed)
        check("cli: an unknown audit is refused (exit 2)", p.returncode == 2, p.stdout + p.stderr)
        long_house = write_glb(tmp / "loose" / "house.glb", hollow_house(w=8.0, d=8.0))   # 8 m blank sides: over 6 m
        p = run("all", long_house, "--class", "building", "--json")
        check("cli: a loose .glb is audited (only flat-wall, judged by the iamar profile, objects to the plain 8 m house)",
              "house" in p.stdout and {i["audit"] for i in json.loads(p.stdout)["items"] if i["level"] == "ERROR"} == {"flat-wall"},
              p.stdout + p.stderr)
        # closure: an open-topped crate; a viewer at the third-person eye looks into it
        w = world(tmp, "closure", crate=[part("Crate", [box([-0.4, 0, -0.4], [0.4, 0.8, 0.4], drop=("top",))], "#9a7a52")])
        p = run("closure", w, "--json")
        e = items(p, "closure")
        check("closure: an open-topped crate fails", p.returncode == 1 and e and "crate" in e[0]["where"], p.stdout)
        # closure: an open fishing boat (name matches a sealed catalogue prop) gets a refresh hint
        w = world(tmp, "stale", crate=[part("Fishing Boat Hull", [box([-0.4, 0, -0.4], [0.4, 0.8, 0.4], drop=("top",))], "#9a7a52")])
        p = run("closure", w, "--json")
        hints = [i for i in items(p, "closure", "WARN") if i.get("stale_catalogue")]
        check("closure: an old copy of a sealed catalogue prop is named with its refresh command",
              hints and "assets use" in hints[0]["message"] and "fishing_boat" in hints[0]["stale_catalogue"], p.stdout)
        p = run("closure", committed, "--json")
        check("closure: no stale-copy hint on a clean world", not [i for i in json.loads(p.stdout)["items"] if i.get("stale_catalogue")], p.stdout)
        # closure: a current closed house that keeps a sliver of open edge is not "an older copy" of
        # every other *_closed house; a renamed old (open) copy of b107_closed still gets its hint (an internal task)
        assets_dir = Path(__file__).resolve().parents[2] / "catalog" / "assets" / "buildings"
        for wname, src, dst in (("closed_current", "b021_closed.glb", "b021_closed.glb"),
                                ("closed_old", "b107.glb", "b107_closed.glb")):
            wd = tmp / wname
            (wd / "assets").mkdir(parents=True)
            shutil.copyfile(assets_dir / src, wd / "assets" / dst)
            (wd / "scene.json").write_text(json.dumps({
                "format": "iamar-scene", "format_version": 0,
                "primitives": [{"id": "ground", "shape": "box", "size": [80, 0.5, 80], "position": [0, -0.25, 0], "collision": "box"}],
                "spawn_points": [{"id": "default", "position": [0, 0.1, 20], "yaw": 0}],
                "objects": [{"id": "house", "asset": "assets/" + dst, "position": [0, 0, 0], "collision": "mesh",
                             "x-class": "building"}]}), encoding="utf-8")
            p = run("closure", wd, "--json")
            hints = [i["stale_catalogue"] for i in json.loads(p.stdout)["items"] if i.get("stale_catalogue")]
            if wname == "closed_current":
                check("closure: a current closed house with an open sliver gets no stale-copy hint",
                      items(p, "closure") and not hints, p.stdout)
            else:
                check("closure: an old copy named like a closed house is hinted at that house only",
                      hints == ["buildings/b107_closed.glb"], p.stdout)

        # closure on heightmap terrain: a crate with no underside stands on the terrain ground
        from PIL import Image
        bottomless = [part("Crate", [box([-0.4, 0, -0.4], [0.4, 0.8, 0.4], drop=("bottom",))], "#9a7a52")]
        for kind, rc in (("no ground", 1), ("heightmap", 0)):
            w = world(tmp, "terr_" + kind.replace(" ", ""), crate=bottomless)
            sc = json.loads((w / "scene.json").read_text())
            sc["primitives"] = [q for q in sc["primitives"] if q["id"] != "ground"]
            if kind == "heightmap":
                (w / "textures").mkdir()
                Image.new("L", (16, 16), 128).save(w / "textures" / "height.png")
                sc["terrain"] = {"type": "heightmap", "size": [60, 60], "position": [0, 0, 0], "min_height": -0.01,
                                 "max_height": 0.01, "resolution": 17, "heightmap": "textures/height.png"}
            (w / "scene.json").write_text(json.dumps(sc, indent=1))
            p = run("closure", w, "--json")
            check("closure: bottomless crate, %s -> exit %d" % (kind, rc), p.returncode == rc, p.stdout + p.stderr)

        # zfight: a sign flush (5 mm) with the crate's face, and a house placed twice
        sign = {"id": "sign", "asset": "assets/sign.glb", "position": [0, 0, 6], "x-class": "prop"}
        w = world(tmp, "zfight", extra=[sign], objects=lambda o: o + [dict(o[0], id="house_a_copy")])
        write_glb(w / "assets" / "sign.glb", [part("Sign", [box([-0.3, 0.2, 0.3], [0.3, 0.6, 0.405])], "#e0d0a0")])
        p = run("zfight", w, "--json")
        e = items(p, "zfight")
        msgs = " ".join(i["message"] for i in e)
        check("zfight: a flush sign fails with its area", any("coplanar" in i["message"] and i.get("area_m2", 0) >= 0.2 for i in e), p.stdout)
        check("zfight: a doubled placement fails", "placed twice" in msgs, p.stdout)

        # zfight: a pair a quest's on_complete swaps is never drawn together (desert a2: the
        # water_for_the_driver quest shows cart_lamp_glow and hides cart_lamp_dark)
        lamp = [part("Lamp", [box([-0.3, 0, -0.3], [0.3, 1.2, 0.3])], "#e0c060")]
        w = world(tmp, "zquest",
                  extra=[{"id": "cart_lamp_glow", "asset": "assets/lamp_glow.glb", "position": [20, 0, 6]},
                         {"id": "cart_lamp_dark", "asset": "assets/lamp_dark.glb", "position": [20, 0, 6]}])
        write_glb(w / "assets" / "lamp_glow.glb", lamp)
        write_glb(w / "assets" / "lamp_dark.glb", lamp)
        sc = json.loads((w / "scene.json").read_text())
        sc["quests"] = [{"id": "water_for_the_driver",
                         "on_complete": {"show": ["cart_lamp_glow"], "hide": ["cart_lamp_dark"]}}]
        (w / "scene.json").write_text(json.dumps(sc, indent=1))
        p = run("zfight", w, "--json")
        infos = items(p, "zfight", "INFO")
        check("zfight: a quest on_complete swap pair (glow vs dark) is not warned",
              p.returncode == 0 and not items(p, "zfight") and not items(p, "zfight", "WARN"), p.stdout)
        check("zfight: the skipped swap is an INFO naming the quest",
              any("water_for_the_driver" in i["message"] and "cart_lamp_glow" in i["where"] for i in infos), p.stdout)
        # ... but a quest that shows both lamps (no swap) does not skip the pair
        sc["quests"] = [{"id": "water_for_the_driver",
                         "on_complete": {"show": ["cart_lamp_glow", "cart_lamp_dark"], "hide": []}}]
        (w / "scene.json").write_text(json.dumps(sc, indent=1))
        p = run("zfight", w, "--json")
        check("zfight: a quest that shows both lamps does not skip the pair",
              p.returncode == 1 and any("cart_lamp_glow" in i["where"] and "coplanar" in i["message"]
                                        for i in items(p, "zfight")), p.stdout)

        # roof: no roof at all (a floor seen from the sky), and a roof without its top side
        w = world(tmp, "roof_none", house_kw={"roof": False})
        p = run("roof", w, "--json")
        check("roof: a missing roof fails as sunk", any(i.get("kind") == "sunk" for i in items(p, "roof")), p.stdout)
        w = world(tmp, "roof_back", house_kw={"roof_drop": ("top",)})
        p = run("roof", w, "--json")
        check("roof: a one-sided roof fails as back", any(i.get("kind") == "back" for i in items(p, "roof")), p.stdout)

        # --lod all: a far LOD whose roof lost its top side fails; LOD0 alone passes
        w = world(tmp, "lods")
        lod1 = [dict(q, name=q["name"] + "_LOD1") for q in hollow_house(roof_drop=("top",))]
        write_glb(w / "assets" / "house.glb", hollow_house() + lod1)
        p = run("all", w)
        check("lod: LOD0 audit ignores the LOD1 copy (no z-fight between levels)", p.returncode == 0, p.stdout)
        p = run("roof", w, "--lod", "all", "--json")
        e = items(p, "roof")
        check("lod: --lod all audits LOD1 on its own and finds its open roof",
              p.returncode == 1 and e and all("@LOD1" in i["where"] for i in e), p.stdout)

        # edge: a hollow house without its back wall
        w = world(tmp, "edge", house_kw={"back_wall": False})
        p = run("edge", w, "--json")
        e = items(p, "edge")
        check("edge: a missing back wall fails on side -z", any(i.get("side") == "-z" and "house_a" in i["where"] for i in e), p.stdout)

        # door: a crate in the doorway, a raised floor, no lintel
        w = world(tmp, "door_blocked", extra=[{"id": "crate_in_door", "asset": "assets/crate.glb", "position": [-6, 0, 3.6]}])
        p = run("door", w, "--json")
        check("door: a crate in the doorway is BLOCKED", any(i.get("kind") == "blocked" and "crate_in_door" in i["message"]
                                                            for i in items(p, "door")), p.stdout)
        w = world(tmp, "door_step", house_kw={"floor_y": 0.9})
        p = run("door", w, "--json")
        check("door: a 0.9 m sill fails as STEP", any(i.get("kind") == "step" for i in items(p, "door")), p.stdout)
        w = world(tmp, "door_hole", house_kw={"lintel": False})
        p = run("door", w, "--json")
        check("door: no wall over the door fails as HOLE", any(i.get("kind") == "hole" for i in items(p, "door")), p.stdout)

        # dark-bake: a roof baked black
        w = world(tmp, "dark", house_kw={"roof_baked": (4, 4, 6)})
        p = run("dark-bake", w, "--json")
        e = items(p, "dark-bake")
        check("dark-bake: a black-baked roof fails", e and "house_a" in e[0]["where"] and e[0]["area_m2"] > 1, p.stdout)
        p = run("dark-bake", KIT / "lint" / "samples" / "desert_post", "--json")
        check("dark-bake: a world without a bake is skipped, not failed",
              p.returncode == 0 and "no baked light" in p.stdout, p.stdout)
        # a separate lightmap (red sky, green sun) read through TEXCOORD_1: black fails, lit passes
        from glb_fixture import png
        lmcrate = [part("Crate", [box([-0.4, 0, -0.4], [0.4, 0.8, 0.4])], "#9a7a52", uv1=True)]
        w = world(tmp, "lightmap_dark", crate=lmcrate)
        (w / "assets" / "crate.lightmap.png").write_bytes(png(8, 8, (10, 5, 0)))
        p = run("dark-bake", w, "--json")
        e = items(p, "dark-bake")
        check("dark-bake: a black lightmap (TEXCOORD_1) fails", e and "crate" in e[0]["where"], p.stdout)
        w = world(tmp, "lightmap_lit", crate=lmcrate)
        (w / "assets" / "crate.lightmap.png").write_bytes(png(8, 8, (230, 180, 0)))
        p = run("dark-bake", w, "--json")
        check("dark-bake: a lit lightmap passes", p.returncode == 0 and "baked_objects=3" in p.stdout, p.stdout)

        # dark-bake on a running clock (an internal task): nothing baked warns; the time-independent
        # sky/AO bake (asset.extras.iamar_bake.kind sky_ao, bake_vertex_ao.py) is reported, not "no baked light"
        def clock(w, minutes=24):
            sj = json.loads((w / "scene.json").read_text())
            sj.setdefault("environment", {})["day_length_minutes"] = minutes
            (w / "scene.json").write_text(json.dumps(sj))
        w = tmp / "clock_desert"
        shutil.copytree(KIT / "lint" / "samples" / "desert_post", w)
        clock(w)
        p = run("dark-bake", w, "--json")
        check("dark-bake: a running clock with nothing baked warns", p.returncode == 0 and "no baked light" in p.stdout
              and any("clock runs and nothing is baked" in i["message"] for i in items(p, "dark-bake", "WARN")), p.stdout)
        w = world(tmp, "sky_ao")
        cg = w / "assets" / "crate.glb"
        raw = cg.read_bytes()
        n = int.from_bytes(raw[12:16], "little")
        js = json.loads(raw[20:20 + n])
        js["asset"]["extras"] = {"iamar_bake": {"kind": "sky_ao", "distance": 1.5}}
        jb = json.dumps(js).encode()
        jb += b" " * ((4 - len(jb) % 4) % 4)
        body = len(jb).to_bytes(4, "little") + b"JSON" + jb + raw[20 + n:]
        cg.write_bytes(raw[:4] + raw[4:8] + (12 + len(body)).to_bytes(4, "little") + body)
        p = run("dark-bake", w, "--json")
        check("dark-bake: a sky/AO bake (asset.extras.iamar_bake) is reported",
              p.returncode == 0 and "time-independent sky/AO bake" in p.stdout and "sky_ao_objects=0" not in p.stdout
              and "sky_ao_objects=" in p.stdout and not items(p, "dark-bake", "WARN"), p.stdout)
        clock(w)
        p = run("dark-bake", w, "--json")
        check("dark-bake: unlit time-of-day bakes on a running clock warn",
              p.returncode == 0 and any("unlit time-of-day bake" in i["message"] for i in items(p, "dark-bake", "WARN")), p.stdout)

        # dark-bake: the seam filter drops lines one or two texels wide but keeps a spot's full
        # area (4 m quad, 40 px, the 0.1 m texel bake_unlit uses by default)
        import numpy as np
        sys.path.insert(0, str(KIT / "audit"))
        import audit as audit_mod
        quad = np.array([[[0, 0, 0], [0, 0, 4], [4, 0, 4]], [[0, 0, 0], [4, 0, 4], [4, 0, 0]]], float)
        quv = np.array([[[0, 0], [0, 1], [1, 1]], [[0, 0], [1, 1], [1, 0]]], float)

        def dark_m2(*rects):
            img = np.ones((40, 40, 3), np.float32)
            for y0, y1, x0, x1 in rects:
                img[y0:y1, x0:x1] = 0.0
            return sum(d[1] for d in audit_mod.sample_dark(quad, quv, img, "unlit"))
        a = dark_m2((10, 13, 10, 13))
        check("dark-bake: a 3x3 texel black spot (0.09 m2) counts its full area", a >= audit_mod.MIN_PATCH_M2, a)
        a = dark_m2((10, 13, 5, 25))
        check("dark-bake: a black strip 3 texels wide counts", a >= 0.5, a)
        a = dark_m2((10, 12, 5, 25), (30, 31, 0, 40))
        check("dark-bake: seams one or two texels wide are dropped", a == 0, a)

        # dark-bake: black texels nobody can see (under a cap laid on a slab) are not reported;
        # the same slab without its cap fails
        slab = part("Slab", [box([-1, 0, -1], [1, 0.5, 1])], baked=(4, 4, 6))
        cap = part("Cap", [box([-1.2, 0.55, -1.2], [1.2, 0.8, 1.2])], baked=(200, 190, 170))
        write_glb(tmp / "capped.glb", [slab, cap])
        p = run("dark-bake", tmp / "capped.glb", "--json")
        check("dark-bake: black texels under a cap are covered, not reported", p.returncode == 0
              and "dark but covered" in p.stdout, p.stdout)
        write_glb(tmp / "slab.glb", [slab])
        p = run("dark-bake", tmp / "slab.glb", "--json")
        check("dark-bake: the uncovered black slab fails", p.returncode == 1 and items(p, "dark-bake"), p.stdout)
        # ... and inside a closed turret standing on it
        turret = part("Turret", [box([-0.6, 0.3, -0.6], [0.6, 3.0, 0.6], drop=("bottom",))], baked=(200, 190, 170))
        rim = part("Rim", [box([-1.5, 0.52, -1.5], [-0.6, 0.6, 1.5]), box([0.6, 0.52, -1.5], [1.5, 0.6, 1.5]),
                           box([-0.6, 0.52, -1.5], [0.6, 0.6, -0.6]), box([-0.6, 0.52, 0.6], [0.6, 0.6, 1.5])])
        write_glb(tmp / "turret.glb", [slab, turret, rim])
        p = run("dark-bake", tmp / "turret.glb", "--json")
        check("dark-bake: black texels shut inside a turret are covered", p.returncode == 0, p.stdout)

        # building audits skip what is not a building: a pier deck and an open boat hull
        deck = [part("Deck", [box([-1.5, 0, -10], [1.5, 0.3, 0])], "#8a7354")]
        hull = [part("Hull", [box([-1.2, 0, -3], [1.2, 0.2, 3]), box([-1.2, 0.2, -3], [-1.0, 1.0, 3]),
                              box([1.0, 0.2, -3], [1.2, 1.0, 3])], "#7a5a3a")]
        write_glb(tmp / "pier.glb", deck)
        write_glb(tmp / "boat_row.glb", hull)
        p = run("all", tmp / "pier.glb", tmp / "boat_row.glb", "--json")
        e = [i for i in json.loads(p.stdout)["items"] if i["level"] == "ERROR" and i["audit"] in ("roof", "edge", "door")]
        check("roof/edge/door: a pier and a boat are not audited as buildings", not e, p.stdout)
        write_glb(tmp / "pier_shed.glb", hollow_house(back_wall=False))
        p = run("edge", tmp / "pier_shed.glb", "--json")
        check("edge: a shed named pier_shed is a structure, not edge-audited", p.returncode == 0, p.stdout)
        p = run("edge", tmp / "pier_shed.glb", "--class", "building", "--json")
        check("edge: the same shed given --class building fails its open side", p.returncode == 1, p.stdout)

        # roof: the base step of a tower is an outside ledge, not a floor under a missing roof
        tower = [part("Base", [box([-3, 0, -3], [3, 1.0, 3])], "#a39c90"),
                 part("Shaft", [box([-1.2, 1.0, -1.2], [1.2, 12, 1.2], drop=("bottom",))], "#d8d0c0")]
        write_glb(tmp / "tower.glb", tower)
        p = run("roof", tmp / "tower.glb", "--json")
        check("roof: a tower's base step is not 'sunk'", p.returncode == 0, p.stdout)

        # roof: a flat floor walled in on all sides and open to the sky is sunk; the same pocket holding
        # an open-air stair (treads 0.3 m apart) is not (desert gap G10, an internal task)
        def pocket(stair):
            walls = [box([-3, 0, -4], [3, 4.5, -3.2]), box([-3, 0, 3.2], [3, 4.5, 4]),
                     box([-3, 0, -3.2], [-2.2, 4.5, 3.2]), box([2.2, 0, -3.2], [3, 4.5, 3.2])]
            floor = [box([-2.2, 0, -3.2], [2.2, 0.1, 3.2])]
            steps = [box([-2.2, 0.1, -3.2 + 0.8 * i], [2.2, 0.1 + 0.3 * (i + 1), -2.4 + 0.8 * i]) for i in range(8)] if stair else []
            return [part("Court", walls + floor + steps, "#c8b48a")]
        write_glb(tmp / "court_flat.glb", pocket(False))
        p = run("roof", tmp / "court_flat.glb", "--class", "building", "--json")
        check("roof: a walled flat floor under open sky is sunk", any(i.get("kind") == "sunk" for i in items(p, "roof")), p.stdout)
        write_glb(tmp / "court_stair.glb", pocket(True))
        p = run("roof", tmp / "court_stair.glb", "--class", "building", "--json")
        check("roof: an open-air stair is not a floor under a missing roof",
              not any(i.get("kind") == "sunk" for i in items(p, "roof")), p.stdout)

        # zfight: a crate standing where a paving slab ends (both undersides at y 0) is not a fight;
        # an invisible collision box (#rrggbb00) is not drawn and not audited
        w = world(tmp, "undersides", extra=[{"id": "crate_edge", "asset": "assets/crate.glb", "position": [10.2, 0, 8.0]}])
        sc = json.loads((w / "scene.json").read_text())
        sc["primitives"].append({"id": "slab", "shape": "box", "size": [4, 0.06, 4], "position": [8, 0.03, 8], "color": "#a39c90"})
        sc["primitives"].append({"id": "rail", "shape": "box", "size": [0.2, 1.1, 4], "position": [-9.0, 0.55, -9.0],
                                 "color": "#a39c9000"})
        (w / "scene.json").write_text(json.dumps(sc, indent=1))
        p = run("zfight", w, "--json")
        check("zfight: undersides at the foot of two objects do not fight", not items(p, "zfight"), p.stdout)
        check("zfight: a transparent collision primitive is not drawn", "primitive:rail" not in p.stdout, p.stdout)

        # a catalogue tree is not a building (harbour gap G11, an internal task): no x-class needed, also
        # when it is reused by hash (manifest.reused) instead of copied
        w = world(tmp, "trees")
        shutil.copy(KIT / "catalog" / "assets" / "trees" / "elm_tree.glb", w / "assets" / "elm_tree.glb")
        oak = next(e for e in json.loads((KIT / "catalog" / "catalog.json").read_text())["entries"]
                   if e["source"].get("file") == "kit/catalog/assets/trees/oak_tree.glb")
        m = json.loads((w / "manifest.json").read_text())
        m["reused"] = [{"path": "assets/oak.glb", "sha256": oak["source"]["sha256"], "bytes": oak["bytes"],
                        "source": {"world": "iamar", "kind": "world", "file": oak["source"]["file"]}, "license": oak["licence"]}]
        (w / "manifest.json").write_text(json.dumps(m))
        sc = json.loads((w / "scene.json").read_text())
        sc["objects"] += [{"id": "elm_0", "asset": "assets/elm_tree.glb", "position": [30, 0, 30]},
                          {"id": "oak_0", "asset": "assets/oak.glb", "position": [-30, 0, 30]}]
        (w / "scene.json").write_text(json.dumps(sc, indent=1))
        p = run("all", w, "--json")
        check("trees: catalogue elm and reused oak pass without x-class", p.returncode == 0
              and "trees:elm_0" in p.stdout and "trees:oak_0" in p.stdout, p.stdout)

        # flat-wall: runs under 'all'; an 8 m house under the iamar profile fails (6 m sides are at the limit, not over),
        # under the sample's own profile it is skipped
        w = world(tmp, "flat", house_kw={"w": 8.0, "d": 8.0})
        check("flat-wall: skipped by a profile without lint.flat_wall_max_m", run("flat-wall", w).returncode == 0)
        (w / "style.json").unlink()
        p = run("all", w, "--json")
        e = items(p, "flat-wall")
        check("flat-wall: 'audit all' runs it and a plain 8 m wall fails under the iamar profile",
              p.returncode == 1 and e and all(i["level"] == "ERROR" for i in e if "flat wall" in i["message"]), p.stdout)

    n = len(checks)
    print("kit audit tests: %d/%d" % (sum(checks), n))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
