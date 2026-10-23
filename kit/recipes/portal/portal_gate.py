#!/usr/bin/env python3
"""A dressed, free-standing stone portal gate: an open round arch you walk through, to stand at a
scene.json portal (recipe `portal_gate`, README.md here). Pure Python 3 on the style generators'
mesh kit (kit/style/gen), so it reads the same style profile as `iamar-world style-gen`.

    python3 kit/recipes/portal/portal_gate.py out.glb [--profile iamar] [--region civic] [--seed 1]
            [--variant auto|stone|plaster] [--width 3.0] [--spring 3.0] [--pier 0.9] [--depth 0.9] [--textures DIR]
            [--world DIR [--check]] [--json]

The body is one closed solid: the gate's outline (two piers and the head over a semicircular
opening) cut out of a slab `--depth` thick. On both faces stand a voussoir ring with a keystone,
impost blocks at the springing, and pier plinths; a coping caps the top. The opening is
`--width` wide with its springing at `--spring` metres, so a portal of size [2.4, 3.2, 0.8]
fits the defaults with room to spare. The node is `portal_arch_LOD0`, so `iamar-world lint`
measures the arch ring (rise / half span 1.0, a semicircle).

Place it at the portal's `position` and `yaw`, and give the portal `"visual": "none"` (or keep
`ring` for the glowing threshold inside the arch). Prints GATE_OK with the triangles; exit 1 when
the budget or the --check audit fails.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "style" / "gen"))

from meshkit import Mesh, write_glb  # noqa: E402
from profile import Style  # noqa: E402
import gen  # noqa: E402

SEGS = 12          # arch segments; must be a multiple of 4 (the head's corners fall on rays 3 and 9)
RING = 0.3         # voussoir ring width across the arch
PROUD = 0.1        # how far the ring, imposts and plinths stand out of each face


def _n(x, y):
    ln = math.hypot(x, y)
    return (x / ln, y / ln) if ln > 1e-12 else (0.0, 0.0)


def png_width(data: bytes) -> int:
    return int.from_bytes(data[16:20], "big") if data[:8] == b"\x89PNG\r\n\x1a\n" else 0


def pick_variant(st: Style, variant: str) -> str:
    """`auto`: coursed stone when the profile paints a stone layer, else the plain plastered gate."""
    if variant != "auto":
        return variant
    # granite is rock and terrain in a desert profile, not masonry: only ashlar / stone layers count
    dressed = any(isinstance(v, dict) and v.get("layer") in ("ashlar", "stone") for v in st.layers.values())
    return "stone" if dressed else "plaster"


def gate(st: Style, width: float, spring: float, pier: float, depth: float, tile: float, variant: str = "stone"):
    mats = st.materials("portal")
    stone, trim = mats["stone"]["name"], mats["wall"]["name"]
    plaster = variant == "plaster"
    if plaster:                         # one plastered/adobe body: wall layer, no dressed-stone courses
        stone = trim
    m = Mesh(tile)
    span = width * 0.5
    hw = span + pier                    # half the gate's width
    top = spring + hw                   # the head's top: a 45 degree ray from the arch centre hits its corners
    zf, zb = depth * 0.5, -depth * 0.5
    inner = [(math.cos(math.pi * i / SEGS) * span, spring + math.sin(math.pi * i / SEGS) * span)
             for i in range(SEGS + 1)]

    def outer(i):
        """Where the ray through inner[i] meets the head's outline (right side, top, left side)."""
        t = math.pi * i / SEGS
        c, s = math.cos(t), math.sin(t)
        if i * 4 <= SEGS:
            return (hw, spring + hw * s / c)
        if i * 4 >= SEGS * 3:
            return (-hw, spring + hw * s / -c)
        return (hw * c / s, top)

    # --- the body: front and back faces, outside, jambs and soffit -------------------------------
    for z, nz in ((zf, 1.0), (zb, -1.0)):
        for x0, x1 in ((span, hw), (-hw, -span)):          # piers below the springing
            m.quad(stone, (x0, 0, z), (x1, 0, z), (x1, spring, z), (x0, spring, z), (0, 0, nz))
        for i in range(SEGS):                               # the head around the arch
            a, b, oa, ob = inner[i], inner[i + 1], outer(i), outer(i + 1)
            m.quad(stone, (a[0], a[1], z), (oa[0], oa[1], z), (ob[0], ob[1], z), (b[0], b[1], z), (0, 0, nz))
    for sx in (1.0, -1.0):
        m.quad(stone, (sx * hw, 0, zf), (sx * hw, 0, zb), (sx * hw, top, zb), (sx * hw, top, zf), (sx, 0, 0))
        m.quad(stone, (sx * span, 0, zf), (sx * span, 0, zb), (sx * span, spring, zb), (sx * span, spring, zf),
               (-sx, 0, 0))
    for i in range(SEGS):                                   # soffit, facing the arch centre
        a, b = inner[i], inner[i + 1]
        d = _n(-(a[0] + b[0]) * 0.5, spring - (a[1] + b[1]) * 0.5)
        m.quad(stone, (a[0], a[1], zf), (a[0], a[1], zb), (b[0], b[1], zb), (b[0], b[1], zf), (d[0], d[1], 0))
    # the coping covers the top, so the body's own top face is never seen: leave it out

    # --- dressing on both faces ----------------------------------------------------------------
    ring = [(math.cos(math.pi * i / SEGS) * (span + RING), spring + math.sin(math.pi * i / SEGS) * (span + RING))
            for i in range(SEGS + 1)]
    for z, nz in ((zf, 1.0), (zb, -1.0)):
        if plaster:                                         # rounded: no voussoirs, keystone or imposts
            b = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, nz))
            for sx in (1.0, -1.0):                          # a plinth keeps the pier's foot
                m.box(trim, (sx * (span + pier * 0.5), 0.3, z + nz * PROUD * 0.5), (pier, 0.6, PROUD), b,
                      back=False, bottom=False)
            continue
        zp = z + nz * PROUD
        for i in range(SEGS):                               # voussoirs: face, soffit, extrados
            a, b, ea, eb = inner[i], inner[i + 1], ring[i], ring[i + 1]
            m.quad(trim, (a[0], a[1], zp), (ea[0], ea[1], zp), (eb[0], eb[1], zp), (b[0], b[1], zp), (0, 0, nz))
            d = _n(-(a[0] + b[0]) * 0.5, spring - (a[1] + b[1]) * 0.5)
            m.quad(trim, (a[0], a[1], z), (b[0], b[1], z), (b[0], b[1], zp), (a[0], a[1], zp), (d[0], d[1], 0))
            m.quad(trim, (ea[0], ea[1], z), (eb[0], eb[1], z), (eb[0], eb[1], zp), (ea[0], ea[1], zp), (-d[0], -d[1], 0))
        # the ring's feet stand on the impost blocks below; close them
        for sx in (1.0, -1.0):
            m.quad(trim, (sx * span, spring, z), (sx * (span + RING), spring, z), (sx * (span + RING), spring, zp),
                   (sx * span, spring, zp), (0, -1, 0))
        # keystone, imposts, plinths: boxes whose back lies on the face
        b = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, nz))
        kd = PROUD + 0.08
        m.box(trim, (0.0, spring + span + (RING + 0.12) * 0.5, z + nz * kd * 0.5), (0.42, RING + 0.12, kd), b, back=False)
        for sx in (1.0, -1.0):
            m.box(trim, (sx * (span + pier * 0.5), spring - 0.13, z + nz * (PROUD + 0.02) * 0.5),
                  (pier, 0.26, PROUD + 0.02), b, back=False)
            m.box(trim, (sx * (span + pier * 0.5), 0.3, z + nz * PROUD * 0.5), (pier, 0.6, PROUD), b,
                  back=False, bottom=False)
    # coping: a slab over the top, overhanging every side
    if plaster:
        m.box(trim, (0.0, top + 0.1, 0.0), (hw * 2 + 0.16, 0.2, depth + 0.16 + PROUD * 2), None)
    else:
        m.box(trim, (0.0, top + 0.14, 0.0), (hw * 2 + 0.3, 0.28, depth + 0.3 + PROUD * 2), None)
    over = 0.16 if plaster else 0.3
    return m, mats, {"variant": variant, "width": width, "spring": spring, "rise": round(span, 3), "span": width,
                     "height": round(top + (0.2 if plaster else 0.28), 3), "gate_width": round(hw * 2 + over, 3),
                     "depth": round(depth + over + PROUD * 2, 3)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="portal_gate", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--profile", default="iamar")
    ap.add_argument("--region")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--width", type=float, default=3.0, help="opening width (m)")
    ap.add_argument("--spring", type=float, default=3.0, help="height of the springing line (m)")
    ap.add_argument("--pier", type=float, default=0.9, help="width of each pier (m)")
    ap.add_argument("--depth", type=float, default=0.9, help="thickness of the gate (m)")
    ap.add_argument("--variant", choices=("auto", "stone", "plaster"), default="auto",
                    help="stone: dressed-stone body with voussoir ring; plaster: rounded adobe/plaster body "
                         "from the wall layer; auto: stone only if the profile paints an ashlar/stone layer")
    ap.add_argument("--textures", help="embed DIR/<layer>.png as base colour (check_style.py --paint)")
    ap.add_argument("--world", help="also write a preview world with the gate and a portal through it")
    ap.add_argument("--check", action="store_true", help="run the closure/zfight audits on --world")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.width < 1.0 or a.spring < 1.5 or a.pier < 0.4 or a.depth < 0.3:
        print("GATE_FAIL: --width >= 1, --spring >= 1.5, --pier >= 0.4, --depth >= 0.3")
        return 2
    st = Style(a.profile, a.region, a.seed)
    variant = pick_variant(st, a.variant)
    tex = st.textures(st.materials("portal"), Path(a.textures) if a.textures else None)
    # 256 px per metre whatever the painted size (a 512 map tiles every 2 m, 1024 every 4 m)
    tile = (max(png_width(b) for b in tex.values()) / 256.0) if tex else st.tile_m
    m, mats, report = gate(st, a.width, a.spring, a.pier, a.depth, tile or st.tile_m, variant)
    out = Path(a.out)
    counts = write_glb(out, {"portal_arch_LOD0": m}, gen.gl_materials(st, mats), tex,
                       extras={"generator": "kit/recipes/portal/portal_gate.py", "profile": st.prof.get("id"),
                               "region": st.region_name, "seed": a.seed})
    tris = counts["portal_arch_LOD0"]
    # lint classes a *gate* or *arch* model as a structure
    budget = int(((st.prof.get("budgets") or {}).get("triangles") or {}).get("structure", 3000))
    report.update({"out": str(out), "triangles": tris, "budget": budget, "profile": st.prof.get("id"),
                   "region": st.region_name})
    code = 0 if tris <= budget else 1
    if a.world:
        w = gen.preview_world(Path(a.world), out, "portal_gate", report["gate_width"] * 0.5, "structure")
        scene = json.loads((w / "scene.json").read_text(encoding="utf-8"))
        scene["portals"] = [{"id": "home", "to": "oakhaven", "label": "To the iamar city", "position": [0, 0, 0],
                             "yaw": 0, "size": [min(2.4, a.width - 0.2), min(3.2, a.spring + a.width * 0.3), 0.8],
                             "visual": "none"}]
        (w / "scene.json").write_text(json.dumps(scene, indent=1), encoding="utf-8")
        report["world"] = str(w)
        if a.check:
            rc, text = gen.run_audit(w)
            report["audit"] = [ln for ln in text.splitlines() if "RESULT" in ln or ln.startswith("ERROR")]
            report["audit_ok"] = rc == 0
            code = max(code, 0 if rc == 0 else 1)
    if a.json:
        print(json.dumps(report, indent=1))
    else:
        for ln in report.get("audit", []):
            print("  " + ln)
        print("%s portal_gate %s: %d triangles (budget %d), opening %.2f x %.2f m, gate %.2f x %.2f x %.2f m%s" % (
            "GATE_OK" if code == 0 else "GATE_FAIL", out, tris, budget, a.width, a.spring + a.width * 0.5,
            report["gate_width"], report["height"], report["depth"],
            "" if "audit_ok" not in report else (", audit ok" if report["audit_ok"] else ", AUDIT FAILED")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
