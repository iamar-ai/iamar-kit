#!/usr/bin/env python3
"""Style generators: masterplan houses, convex-wing roofs and round door arches as closed,
culled glTF, read from a style profile. Pure Python 3 (no Blender, no Godot, no numpy for the
build; the --check audit needs numpy).

    iamar-world style-gen house  out.glb [--profile iamar] [--region civic] [--seed 7]
                                 [--footprint rect|narrow|L|T|U|WxD|pts.json] [--storeys 3]
                                 [--jetty|--no-jetty] [--oriel|--no-oriel] [--tower|--no-tower]
                                 [--door-kind 0|1|2] [--timber 0-4|plain|post|studs|braced|crossed]
    iamar-world style-gen roof   out.glb [--footprint L] [--eaves 6] [--pitch 0.9] ...
    iamar-world style-gen arch   out.glb [--width 1.3] [--door-h 2.2] [--ceiling 3.6] ...
    iamar-world style-gen lantern out.glb [--mount post|wall] [--height 2.6] [--glow 1.3] ...
    iamar-world style-gen street out.glb --street street.json [--textures DIR] [--tile-m M]
                                 (many houses in one model: street.py)

Common options:
    --world DIR      also write a preview world (scene.json with ground, spawn and the model)
    --textures DIR   embed DIR/<layer>.png (from check_style.py --paint) as base colour textures
    --check          run the closure, roof and zfight audits (house: also flat-wall) on the preview world (needs --world)
    --budget N       triangle budget at LOD0 (default: the profile's building budget)
    --json           print the report as JSON
    --lods N         write only the first N LOD levels (1: LOD0 alone, e.g. for kit/blender/look.py)

Writes out.glb with nodes <name>_LOD0.._LOD2 (house, roof, lantern; the arch is one level) and
prints GEN_OK with triangles per LOD and the Efficiency score (100 at or under budget,
else 100 x budget / triangles). Exit 1 when LOD0 is over budget or --check fails.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from meshkit import Mesh, write_glb  # noqa: E402
from profile import Style  # noqa: E402
import arch as archmod  # noqa: E402
import house as housemod  # noqa: E402
import roof as roofmod  # noqa: E402
import lantern as lanternmod  # noqa: E402

KIT = HERE.parents[1]
AUDIT = KIT / "audit" / "audit.py"


def parse_footprint(s):
    p = Path(s)
    if s.endswith(".json") and p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return s


def gl_materials(st, mats):
    return {spec["name"]: {"color": spec["color"], "roughness": spec.get("roughness", 0.9),
                           "tint": (st.layers.get(spec.get("layer")) or {}).get("tint"),
                           **{k: spec[k] for k in ("emissive", "emissive_strength") if spec.get(k)}}
            for spec in mats.values()}


def build_house(st, a):
    h = housemod.House(st, parse_footprint(a.footprint), a.storeys, a.jetty, a.oriel, a.tower, a.door_kind, a.timber)
    budget = a.budget or st.budget["building"]
    lod0 = h.fit(budget)
    report = dict(h.report)
    nodes = {"house_LOD0": lod0, "house_LOD1": h.build(1), "house_LOD2": h.build(2)}
    h.report = report
    return nodes, h.mats, h.report, "building"


def build_roof(st, a):
    poly = housemod.footprint(parse_footprint(a.footprint))
    mats = st.materials("roof")
    eaves = a.eaves
    inr = max(w["inradius"] for w in roofmod.wings(poly))
    k = a.pitch if a.pitch is not None else st.pitch(eaves, inr)
    overhang = st.pick("eave_overhang_m", "eaves")
    nodes = {}
    for lod in (0, 1, 2):
        m = Mesh(st.tile_m)
        r = roofmod.Roof(poly, eaves, k=k)
        n = len(r.polygon)
        for e in range(n):
            pa, pb = r.polygon[e], r.polygon[(e + 1) % n]
            o = roofmod.outward(r.polygon, e)
            m.quad(mats["wall"]["name"], (pa[0], 0.0, pa[1]), (pb[0], 0.0, pb[1]), (pb[0], eaves, pb[1]),
                   (pa[0], eaves, pa[1]), (o[0], 0.0, o[1]))
        r.build(m, mats["roof"]["name"], mats["cap"]["name"] if lod == 0 else None)
        if lod <= 1:
            roofmod.eave_skirt(m, r.polygon, eaves, k, overhang, housemod.EAVE_FLARE, housemod.FASCIA,
                               mats["roof"]["name"], mats["timber"]["name"])
        nodes["roof_LOD%d" % lod] = m
        report = {"wings": len(r.wings), "wing_areas": [round(abs(roofmod.area(w["poly"])), 2) for w in r.wings],
                  "faces": len(r.faces()), "eaves": eaves, "ridge": round(r.ridge, 3), "pitch": round(k, 3),
                  "footprint_area": round(abs(roofmod.area(r.polygon)), 3),
                  "roof_area_plan": round(sum(abs(roofmod.area(f)) for _, f in r.faces()), 3)}
    return nodes, mats, report, "building"


def build_lantern(st, a):
    lan = lanternmod.Lantern(st, a.mount, a.height if a.height is not None else (2.6 if a.mount == "post" else 2.5),
                             a.glow)
    nodes = {"lantern_LOD%d" % lod: lan.build(lod) for lod in (0, 1, 2)}
    lan.build(0)
    return nodes, lan.mats, lan.report, "prop"


def build_arch(st, a):
    mats = st.materials("arch")
    m = Mesh(st.tile_m)
    width, door_h, ceiling = a.width, a.door_h, a.ceiling
    wall_w = max(3.0, width + 2.0)
    archmod.wall_panel(m, wall_w, ceiling + 0.6, 0.5, mats["stone"]["name"] if a.on_stone else mats["wall"]["name"])
    archmod.door(m, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), width, door_h, mats, a.door_kind if a.door_kind is not None else 2)
    ok = archmod.door_arch(m, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), width, door_h, ceiling, mats["stone"]["name"],
                           mats["timber"]["name"])
    if not ok:
        raise SystemExit("arch: no room for an arch under the ceiling (rise < 0.28 m); raise --ceiling")
    spring = door_h + archmod.LINTEL
    rise = min(width * 0.5, ceiling - spring - archmod.RING - 0.08)
    return {"arch_LOD0": m}, mats, {"spring": round(spring, 3), "rise": round(rise, 3), "span": width,
                                    "ceiling": ceiling}, "prop"


def preview_world(world: Path, glb: Path, name: str, size, cls="building", lights=None):
    world.mkdir(parents=True, exist_ok=True)
    (world / "assets").mkdir(exist_ok=True)
    target = world / "assets" / glb.name
    if target.resolve() != glb.resolve():
        target.write_bytes(glb.read_bytes())
    g = max(60.0, round(2.0 * size + 24.0))   # the ground reaches past every side (a long street too)
    scene = {
        "format": "iamar-scene", "format_version": 0,
        "primitives": [{"id": "ground", "shape": "box", "size": [g, 0.5, g], "position": [0, -0.25, 0],
                        "color": "#8f8a70", "collision": "box"}],
        "spawn_points": [{"id": "default", "position": [0, 0.1, -(size + 8.0)], "yaw": 180}],
        "objects": [{"id": name, "asset": "assets/" + glb.name, "position": [0, 0, 0], "collision": "mesh",
                     "x-class": cls}],
    }
    if lights:
        # a light source: show it at night (the kit's night preset), with its light
        scene["lights"] = [dict(l, id="%s_light_%d" % (name, i)) for i, l in enumerate(lights)]
        night = KIT / "style" / "lighting" / "presets" / "night.json"
        if night.is_file():
            scene["environment"] = json.loads(night.read_text(encoding="utf-8"))["environment"]
        scene["spawn_points"][0]["position"] = [0, 0.1, -4.0]
    (world / "scene.json").write_text(json.dumps(scene, indent=1), encoding="utf-8")
    return world


def roof_share_warning(st, report):
    """The roof's share of the whole height (ridge - eaves) / ridge, checked against the profile's
    roof_height_fraction with the lint's 5-point tolerance: style-gen fits the pitch to it, but a
    narrow wing (an L or U arm, a 6 m deep house of 3+ storeys) cannot reach it under the pitch
    ceiling, nor a very deep 1-storey house get under it above the pitch floor. Returns warning lines (empty when the share fits or the profile gives no fraction)."""
    if "ridge" not in report or "eaves" not in report or report["ridge"] <= 0:
        return []
    share = (report["ridge"] - report["eaves"]) / report["ridge"]
    report["roof_share"] = round(share, 3)
    f = st.dims.get("roof_height_fraction") if "roof_height_fraction" in st.own_dims else None
    if not f or float(f[0]) - 0.05 <= share <= float(f[1]) + 0.05:
        return []
    fix = ("use a deeper footprint (7 m or more for 3+ storeys), fewer storeys or a convex footprint"
           if share < float(f[0]) else "use more storeys, or split the footprint into narrower wings (L, T, U)")
    return ["WARN roof: the roof is %.0f %% of the height (ridge %.2f m, eaves %.2f m); the profile wants %.0f-%.0f %%: %s"
            % (share * 100, report["ridge"], report["eaves"], float(f[0]) * 100, float(f[1]) * 100, fix)]


AUDITS = ("closure", "roof", "zfight")
HOUSE_AUDITS = AUDITS + ("flat-wall",)   # houses and streets: no blank wall over lint.flat_wall_max_m (an internal task)


def run_audit(world: Path, audits=AUDITS):
    """The kit's geometry audits on every LOD of the preview world: (exit code, output)."""
    out, code = [], 0
    for name in audits:
        q = subprocess.run([sys.executable, str(AUDIT), name, str(world), "--lod", "all", "--quiet"],
                           capture_output=True, text=True)
        out.append(q.stdout + q.stderr)
        code = max(code, q.returncode)
    return code, "".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="style-gen", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["house", "roof", "arch", "lantern", "street"])
    ap.add_argument("out")
    ap.add_argument("--profile", default="iamar")
    ap.add_argument("--region")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--footprint", default="rect")
    ap.add_argument("--storeys", type=int)
    for flag in ("jetty", "oriel", "tower"):
        ap.add_argument("--" + flag, dest=flag, action="store_true", default=None)
        ap.add_argument("--no-" + flag, dest=flag, action="store_false")
    ap.add_argument("--door-kind", type=int, choices=[0, 1, 2])
    ap.add_argument("--timber", help="house: upper-storey timber frame, 0-4 or plain|post|studs|braced|crossed "
                    "(default: picked by the region's timber_frame_weights)")
    ap.add_argument("--eaves", type=float, default=6.0)
    ap.add_argument("--pitch", type=float)
    ap.add_argument("--width", type=float, default=1.3)
    ap.add_argument("--door-h", type=float, default=2.2)
    ap.add_argument("--ceiling", type=float, default=3.6)
    ap.add_argument("--on-stone", action="store_true", default=True)
    ap.add_argument("--mount", choices=["post", "wall"], default="post", help="lantern: on a post or a wall arm")
    ap.add_argument("--height", type=float, help="lantern: cap top (post, default 2.6) or arm height (wall, 2.5)")
    ap.add_argument("--glow", type=float, default=1.3, help="lantern: glass emissive strength (default 1.3; above ~2 the glass clips to white)")
    ap.add_argument("--world")
    ap.add_argument("--textures")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--budget", type=int)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lods", type=int, default=3, choices=[1, 2, 3], help="LOD levels to write (1 = LOD0 only, for a look)")
    ap.add_argument("--street", help="street: the houses and their places (street.json, see street.py)")
    ap.add_argument("--tile-m", type=float, help="street: metres per UV unit (default: map width / 256)")
    a = ap.parse_args(argv)
    if a.kind == "street":
        import street
        return street.run(a)
    try:
        st = Style(a.profile, a.region, a.seed)
        nodes, mats, report, cls = {"house": build_house, "roof": build_roof, "arch": build_arch,
                                    "lantern": build_lantern}[a.kind](st, a)
    except (ValueError, KeyError, OSError) as e:
        print("GEN_FAIL %s: %s" % (a.kind, e))
        return 1
    out = Path(a.out)
    nodes = dict(list(nodes.items())[:a.lods])
    counts = write_glb(out, nodes, gl_materials(st, mats), st.textures(mats, Path(a.textures) if a.textures else None),
                       extras={"generator": "kit/style/gen " + a.kind, "profile": st.prof.get("id"),
                               "region": st.region_name, "seed": a.seed})
    lods = [counts[k] for k in sorted(counts)]
    budget = a.budget or st.budget[cls]
    eff = 100.0 if lods[0] <= budget else 100.0 * budget / lods[0]
    report.update({"kind": a.kind, "out": str(out), "profile": st.prof.get("id"), "region": st.region_name,
                   "seed": a.seed, "triangles_per_lod": lods, "budget": budget, "efficiency": round(eff, 1),
                   "materials": sorted({s["name"] for s in mats.values()})})
    code = 0 if lods[0] <= budget else 1
    warnings = roof_share_warning(st, report)
    if warnings:
        report["warnings"] = warnings
    if a.world:
        xs = [abs(c) for m in nodes.values() for ts in m.tris.values() for t in ts for p in t for c in (p[0], p[2])]
        preview_world(Path(a.world), out, a.kind, max(xs) if xs else 5.0, cls,
                      [report["light"]] if "light" in report else None)
        report["world"] = a.world
        if a.check:
            rc, text = run_audit(Path(a.world), HOUSE_AUDITS if a.kind == "house" else AUDITS)
            report["audit"] = [ln for ln in text.splitlines() if "RESULT" in ln or ln.startswith("ERROR")]
            report["audit_ok"] = rc == 0
            code = max(code, 0 if rc == 0 else 1)
    elif a.check:
        print("GEN_FAIL --check needs --world")
        return 2
    if a.json:
        print(json.dumps(report, indent=1))
    else:
        for k in ("audit", "warnings"):
            for ln in report.get(k, []):
                print("  " + ln)
    if a.json:
        return code
    print("%s %s %s: triangles %s (LOD0 budget %d, efficiency %.0f)%s" % (
        "GEN_OK" if code == 0 else "GEN_FAIL", a.kind, out, " / ".join(map(str, lods)), budget, eff,
        "" if "audit_ok" not in report else (", audit ok" if report["audit_ok"] else ", AUDIT FAILED")))
    return code


if __name__ == "__main__":
    sys.exit(main())
