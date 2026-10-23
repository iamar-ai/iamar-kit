#!/usr/bin/env python3
"""Tests for kit/style/gen (an internal task): the masterplan house, convex-wing roof and door arch
generators run headless from a style profile (the iamar profile and the desert example), their
output passes the kit's closure, roof and zfight audits on every LOD, LOD0 meets the budget
(building 3000, the arch as a prop 300), each LOD is lighter than the one before, the same seed
gives the same file, the roof covers exactly its footprint, a seeded mistake fails, painted
textures embed, and the iamar profile lists the three generators as available.

    python3 kit/tests/style/gen/style_gen_test.py [--quick]

The audits need numpy (as `iamar-world audit` does); the texture part needs Pillow.
--quick runs one house instead of five.
"""
from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[3]
GEN = KIT / "style" / "gen" / "gen.py"
DESERT = KIT / "style" / "schema" / "examples" / "desert_trading_post.style.json"
sys.path.insert(0, str(KIT / "style" / "gen"))


def run(*args):
    p = subprocess.run([sys.executable, str(GEN), *map(str, args)], capture_output=True, text=True)
    rep = {}
    if "--json" in args:
        try:
            rep = json.loads(p.stdout)
        except ValueError:
            rep = {}
    return p, rep


def glb_json(path: Path) -> dict:
    data = path.read_bytes()
    n = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20:20 + n])


def main() -> int:
    quick = "--quick" in sys.argv
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (("  " + str(detail)[-700:]) if detail and not cond else ""), flush=True)

    try:
        import numpy  # noqa: F401
        have_np = True
    except ImportError:
        have_np = False
        print("SKIPPED audits (numpy not installed)")

    with tempfile.TemporaryDirectory(prefix="iamar-style-gen-") as raw:
        tmp = Path(raw)
        houses = [("rect", 3, "civic"), ("L", 3, "warriors"), ("U", 1, "mages"), ("T", 6, "herbalists"),
                  ("narrow", 2, "civic")]
        for foot, seed, region in houses[:1 if quick else 5]:
            name = "house %s seed %d %s" % (foot, seed, region)
            args = ["house", tmp / ("h_%s.glb" % foot), "--footprint", foot, "--seed", seed, "--region", region, "--json"]
            if have_np:
                args += ["--world", tmp / ("w_%s" % foot), "--check"]
            p, rep = run(*args)
            lods = rep.get("triangles_per_lod", [])
            check(name + ": generated", p.returncode == 0 and len(lods) == 3, p.stdout + p.stderr)
            check(name + ": LOD0 within the building budget", lods and lods[0] <= 3000, lods)
            check(name + ": each LOD lighter than the one before", len(lods) == 3 and lods[0] > lods[1] > lods[2], lods)
            if have_np:
                check(name + ": closure, roof and zfight audits pass on every LOD", rep.get("audit_ok") is True,
                      rep.get("audit"))
            if foot == "rect":
                g = glb_json(tmp / "h_rect.glb")
                check("house: LOD nodes named for the lint", [n["name"] for n in g["nodes"]] ==
                      ["house_LOD0", "house_LOD1", "house_LOD2"])
                check("house: materials are the profile's layers", {"wall_plaster", "roof_slate", "timber"} <=
                      {m["name"] for m in g["materials"]}, [m["name"] for m in g["materials"]])
                win = [m for m in g["materials"] if m["name"] == "window"]
                # an internal task: lit at night, stays live in the bake; an internal task: the glow stays under daylit
                # glass (0.5 read as flat amber panes by day, dusk and night alike, harbour a5 R2)
                check("house: window glass is smooth and dark with a faint warm glow (0.1-0.3)",
                      win and win[0]["pbrMetallicRoughness"]["roughnessFactor"] <= 0.2
                      and max(win[0]["pbrMetallicRoughness"].get("baseColorFactor", [1, 1, 1])[:3]) < 0.3
                      and win[0]["emissiveFactor"][0] > win[0]["emissiveFactor"][2]
                      and 0.1 <= win[0].get("extensions", {}).get("KHR_materials_emissive_strength", {})
                      .get("emissiveStrength", 0) <= 0.3, win)
                gl = rep.get("glazing") or {}
                check("house: windows are framed glazing: glass set back 3 cm or more in its frame, with "
                      "glazing bars (an internal task; the old pane lay flat on the frame's front)",
                      rep.get("windows", 0) > 0 and gl.get("bars") is True
                      and gl.get("glass_set_back_m", -1) >= 0.03, {"windows": rep.get("windows"), "glazing": gl})
                p2, _ = run("house", tmp / "h_rect2.glb", "--footprint", foot, "--seed", seed, "--region", region)
                check("house: same seed, same bytes", (tmp / "h_rect.glb").read_bytes() == (tmp / "h_rect2.glb").read_bytes())
                feats = all(rep.get(k) for k in ("jetty", "tower", "oriel", "door"))
                check("house: seed 3 has a jetty, a corner tower, an oriel and a door", feats,
                      {k: rep.get(k) for k in ("jetty", "tower", "oriel", "door")})

        # every feature forced on, on an L (tower, jetty, oriel, arch on a stone ground storey)
        p, rep = run("house", tmp / "full.glb", "--footprint", "L", "--seed", 5, "--storeys", 3, "--jetty", "--tower",
                     "--oriel", "--door-kind", 2, "--json", *(["--world", tmp / "w_full", "--check"] if have_np else []))
        check("house with every feature on: within budget" + (" and audits pass" if have_np else ""),
              p.returncode == 0 and rep.get("triangles_per_lod", [99999])[0] <= 3000, p.stdout[-600:] + p.stderr)

        # a custom profile (Track B): the desert example drives colours, dimensions, layers
        p, rep = run("house", tmp / "desert.glb", "--profile", DESERT, "--region", "caravanserai", "--seed", 2, "--json",
                     *(["--world", tmp / "w_desert", "--check"] if have_np else []))
        check("desert profile: generated" + (" and audits pass" if have_np else ""), p.returncode == 0, p.stdout[-600:] + p.stderr)
        check("desert profile: its own layers", {"adobe", "palm_wood"} <= set(rep.get("materials", [])), rep.get("materials"))
        check("desert profile: shallow roof from roof_height_fraction", 0 < rep.get("pitch", 9) < 0.5, rep.get("pitch"))

        # roof share (an internal task): Track A wants the roof 1/3-1/2 of the height; a three-storey house
        # on a 7 m+ deep footprint gets it (it took a quarter before), a narrow U arm warns
        harbour = KIT / "blindtest" / "harbour" / "attempt-3" / "world" / "style.json"
        profiles = [("iamar", [])] + ([(harbour, ["--region", "harbour"])] if harbour.is_file() else [])
        shares = []
        for prof, reg in profiles:
            for foot in ("10x8", "7x7"):
                for seed in ((31,) if quick else (1, 5, 11, 31, 41)):
                    p, rep = run("house", tmp / "share.glb", "--profile", prof, *reg, "--footprint", foot, "--storeys", 3,
                                 "--seed", seed, "--lods", 1, "--json")
                    shares.append((rep.get("roof_share", 0), str(prof)[-10:], foot, seed, rep.get("warnings")))
        check("roof share: 3-storey houses (iamar%s) have roofs 33-50 %% of the height, no warning"
              % (", harbour" if len(profiles) > 1 else ""),
              all(0.33 <= s[0] <= 0.5 and not s[4] for s in shares), [s for s in shares if not 0.33 <= s[0] <= 0.5 or s[4]])
        p, rep = run("house", tmp / "share_u.glb", "--footprint", "U", "--storeys", 3, "--seed", 5, "--lods", 1, "--json")
        check("roof share: a 3-storey U house (narrow arms) warns", any("WARN roof" in w for w in rep.get("warnings", [])),
              rep.get("roof_share"))
        p, rep = run("house", tmp / "share_w.glb", "--footprint", "20x16", "--storeys", 1, "--seed", 1, "--lods", 1, "--json")
        check("roof share: a deep 1-storey house keeps a pitch within the profile's range (>= 0.72 - 15 %%, an internal task)",
              rep.get("pitch", 0) >= 0.612, (rep.get("pitch"), rep.get("roof_share")))
        p, rep = run("house", tmp / "share_x.glb", "--footprint", "30x24", "--storeys", 1, "--seed", 1, "--lods", 1,
                     "--budget", 9000, "--json")
        check("roof share: a very deep 1-storey house warns that its roof is too tall",
              rep.get("pitch", 0) >= 0.612 and any("WARN roof" in w and "more storeys" in w for w in rep.get("warnings", [])),
              (rep.get("pitch"), rep.get("warnings")))
        p, rep = run("house", tmp / "share_d.glb", "--profile", DESERT, "--region", "caravanserai", "--seed", 2, "--json")
        check("roof share: the flat-roofed desert profile does not warn", not rep.get("warnings"), rep.get("warnings"))

        # roofs: the envelope covers exactly the footprint, one wing per arm
        for foot, wings in (("rect", 1), ("L", 2), ("T", 2), ("U", 3)):
            p, rep = run("roof", tmp / ("r_%s.glb" % foot), "--footprint", foot, "--json",
                         *(["--world", tmp / ("wr_%s" % foot), "--check"] if have_np and foot != "rect" else []))
            check("roof %s: generated%s" % (foot, " and audits pass" if have_np and foot != "rect" else ""),
                  p.returncode == 0, p.stdout[-600:] + p.stderr)
            fa, ra = rep.get("footprint_area", 0), rep.get("roof_area_plan", -1)
            check("roof %s: roof plan area = footprint area" % foot, abs(fa - ra) <= 0.005 * fa, (fa, ra))
            check("roof %s: %d wing(s)" % (foot, wings), rep.get("wings") == wings, rep.get("wing_areas"))
        p, rep = run("roof", tmp / "r_pts.glb", "--footprint", "8x5", "--pitch", 1.0, "--eaves", 5, "--json")
        check("roof WxD footprint: ridge = eaves + pitch x half depth", abs(rep.get("ridge", 0) - 7.5) < 0.05, rep.get("ridge"))

        # lanterns (an internal task): glass visible from every side, emissive, light at the glass centre
        for mount in ("post", "wall"):
            p, rep = run("lantern", tmp / ("lan_%s.glb" % mount), "--mount", mount, "--json",
                         *(["--world", tmp / ("wl_%s" % mount), "--check"] if have_np else []))
            check("lantern %s: generated%s, LOD0 within the prop budget (300)" % (mount, " and audits pass" if have_np else ""),
                  p.returncode == 0 and rep.get("triangles_per_lod", [999])[0] <= 300, p.stdout[-600:] + p.stderr)
            g = glb_json(tmp / ("lan_%s.glb" % mount))
            glass = [m for m in g["materials"] if m["name"] == "lamp_glass"]
            check("lantern %s: glass emissive with KHR_materials_emissive_strength" % mount,
                  glass and max(glass[0].get("emissiveFactor", [0])) > 0.9
                  and glass[0].get("extensions", {}).get("KHR_materials_emissive_strength", {}).get("emissiveStrength", 0) > 1
                  and "KHR_materials_emissive_strength" in g.get("extensionsUsed", []), glass)
            lt = rep.get("light", {})
            check("lantern %s: report gives a point light at the glass centre" % mount,
                  lt.get("type") == "point" and lt.get("position") == rep.get("glass_centre") and lt.get("energy", 0) > 0,
                  (lt, rep.get("glass_centre")))
            if have_np and mount == "post":
                check("lantern preview world: night environment and its light",
                      json.loads((tmp / "wl_post" / "scene.json").read_text())["lights"][0]["position"] == lt.get("position"))
        import profile as profmod
        import lantern as lanmod
        lan = lanmod.Lantern(profmod.Style("iamar", None, 1))
        mesh = lan.build(0)
        cx, cy, cz = lan.report["glass_centre"]

        def blocked(o, d):
            """Does a non-glass triangle cross the ray o + t d (0 < t < 0.4)?"""
            for mat, tris in mesh.tris.items():
                if mat == "lamp_glass":
                    continue
                for a, b, c in tris:
                    e1 = [b[i] - a[i] for i in range(3)]
                    e2 = [c[i] - a[i] for i in range(3)]
                    pv = [d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]]
                    det = sum(e1[i] * pv[i] for i in range(3))
                    if abs(det) < 1e-12:
                        continue
                    tv = [o[i] - a[i] for i in range(3)]
                    u = sum(tv[i] * pv[i] for i in range(3)) / det
                    qv = [tv[1] * e1[2] - tv[2] * e1[1], tv[2] * e1[0] - tv[0] * e1[2], tv[0] * e1[1] - tv[1] * e1[0]]
                    v = sum(d[i] * qv[i] for i in range(3)) / det
                    t = sum(e2[i] * qv[i] for i in range(3)) / det
                    if u >= 0 and v >= 0 and u + v <= 1 and 0 < t < 0.4:
                        return True
            return False
        h = lanmod.GLASS / 2 + 1e-3
        sides = [((cx + h, cy + dy, cz + dz), (1, 0, 0)) for dy in (-0.08, 0, 0.08) for dz in (-0.05, 0, 0.05)]
        sides += [((cx + dx, cy + dy, cz - h), (0, 0, -1)) for dy in (-0.08, 0, 0.08) for dx in (-0.05, 0, 0.05)]
        check("lantern: nothing in front of the glass (the harbour lantern hid it in an iron shell)",
              not any(blocked(o, d) for o, d in sides), [o for o, d in sides if blocked(o, d)])

        # arch
        p, rep = run("arch", tmp / "a.glb", "--json", *(["--world", tmp / "wa", "--check"] if have_np else []))
        check("arch: generated" + (" and audits pass" if have_np else ""), p.returncode == 0, p.stdout[-600:] + p.stderr)
        check("arch: within the prop budget (300)", rep.get("triangles_per_lod", [999])[0] <= 300, rep.get("triangles_per_lod"))
        check("arch: semicircle at most (rise <= half span)", 0.28 <= rep.get("rise", 0) <= 1.3 / 2 + 1e-6, rep.get("rise"))
        p, _ = run("arch", tmp / "a_low.glb", "--ceiling", 2.6)
        check("arch: refused with no room under the ceiling", p.returncode != 0 and "no room" in (p.stdout + p.stderr))

        # a Track A region gets its own roof layer, not the civic slate (an internal task, harbour a4 G4)
        harbour = KIT / "style" / "schema" / "examples" / "harbour_quarter.style.json"
        p, _ = run("house", tmp / "harbour.glb", "--profile", harbour, "--region", "harbour", "--seed", 2,
                   "--footprint", "8x8", "--storeys", 3)
        names = {m["name"] for m in glb_json(tmp / "harbour.glb").get("materials", [])} if p.returncode == 0 else set()
        check("harbour example: region roof is shingle, not civic slate",
              "harbour_roof_shingle" in names and "roof_slate" not in names, (p.stdout[-300:], names))

        # seeded mistakes fail
        p, _ = run("house", tmp / "bad.glb", "--region", "atlantis")
        check("unknown region fails", p.returncode == 1 and "no region" in p.stdout, p.stdout)
        p, _ = run("house", tmp / "big.glb", "--footprint", "U", "--seed", 1, "--budget", 400)
        check("over budget fails (GEN_FAIL, exit 1)", p.returncode == 1 and "GEN_FAIL" in p.stdout, p.stdout)
        if have_np:
            import gen as genmod
            from meshkit import Mesh, write_glb
            m = Mesh()
            m.quad("wall", (0, 0, 0), (4, 0, 0), (4, 3, 0), (0, 3, 0), (0, 0, -1))   # one wall, nothing closing it
            bad = tmp / "open.glb"
            write_glb(bad, {"open_LOD0": m}, {"wall": {"color": "#d0c8b8"}})
            genmod.preview_world(tmp / "w_open", bad, "open", 4.0)
            rc, text = genmod.run_audit(tmp / "w_open")
            check("an open wall fails the audit the generators use", rc == 1 and "closure" in text, text[-400:])

            # flat-wall (an internal task): 5 cm frames and 16 cm door jambs read as blank walls; 10 of 24 7x9 houses failed
            sys.path.insert(0, str(KIT / "audit"))
            import flat_wall
            fw = []
            for seed in range(1, 25):
                f = tmp / ("fw%d.glb" % seed)
                run("house", f, "--seed", seed, "--footprint", "7x9", "--lods", "1")
                fw.append(str(f))
            rep = flat_wall.run(fw)
            errs = [i["where"] for i in rep["items"] if i["level"] == "ERROR"]
            check("24 seeded 7x9 houses pass the flat-wall audit", rep["checked"] == 24 and not errs, errs)
            check("house --check runs flat-wall", "flat-wall" in genmod.HOUSE_AUDITS)

        # painted textures embed (Pillow)
        try:
            import PIL  # noqa: F401
        except ImportError:
            print("SKIPPED textures (Pillow not installed)")
        else:
            tex = tmp / "tex"
            q = subprocess.run([sys.executable, str(KIT / "style" / "check_style.py"), "--paint", str(tex), "--profile", "iamar",
                                "--size", "256", "--only", "wall_plaster,roof_slate,timber"], capture_output=True, text=True)
            p, _ = run("house", tmp / "tex.glb", "--textures", tex, "--seed", 3)
            g = glb_json(tmp / "tex.glb") if p.returncode == 0 else {}
            textured = {m["name"] for m in g.get("materials", []) if "baseColorTexture" in m.get("pbrMetallicRoughness", {})}
            check("painted layers embed as textures", q.returncode == 0 and {"wall_plaster", "roof_slate", "timber"} <= textured,
                  (q.stdout[-300:], textured))

    prof = json.loads((KIT / "style" / "iamar" / "style.json").read_text(encoding="utf-8"))
    gens = prof.get("generators", {})
    check("iamar profile: masterplan_house, roof, arch available with a command",
          all(gens.get(k, {}).get("status") == "available" and "style-gen" in gens.get(k, {}).get("command", "")
              for k in ("masterplan_house", "roof", "arch")), {k: gens.get(k) for k in ("masterplan_house", "roof", "arch")})

    print("kit style generator tests: %d/%d" % (sum(checks), len(checks)))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
