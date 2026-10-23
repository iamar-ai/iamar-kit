"""A street of style-gen houses in one .glb (`iamar-world style-gen street`).

    iamar-world style-gen street out.glb --street street.json [--profile P] [--region R]
                                 [--textures DIR] [--tile-m M] [--world DIR --check] [--json]

street.json lists the houses with the same switches as `style-gen house`, and where they stand:

    {"region": "harbour",
     "houses": [{"id": "house_n1", "position": [3.0, 0, -10.0], "yaw": 180, "seed": 11,
                 "footprint": "7x8", "storeys": 2, "jetty": true, "oriel": false, "tower": false,
                 "door_kind": 1, "timber": "braced"}, ...]}

Why one file (blind test harbour attempt 4, gaps G9-G11):
  * every .glb pays for its own embedded maps, so ten separate painted houses blow the 64 MiB
    texture budget; here each painted map is embedded once for the whole street;
  * the browser's merge_static merges surfaces only when they share a texture, and textures are
    never shared between .glb files, so ten separate houses draw about 9 times each; here every
    house uses the same materials (its own weathering tint goes into COLOR_0, which glTF
    multiplies into the base colour), so merge_static draws the whole street with one call per
    material;
  * each house stays its own root node with extras {"x-class": "building"}, so lint and audit
    judge every house on its own (budget, doors, roof, closure, edge), not the row as one model.

The UV tile follows the maps: with DIR/<layer>.png N px wide, 1 UV unit = N / 256 m, so 512 px
maps (`check_style.py --paint DIR --size 512`) tile every 2 m at the texel rule's 256 px per
metre (kit/style/materials/README.md) for a quarter of the memory of 1024 maps. --tile-m overrides.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from meshkit import Mesh, hex_rgb, srgb_to_linear, write_glb  # noqa: E402
from profile import Style  # noqa: E402
import house as housemod  # noqa: E402

KIT = HERE.parents[1]
LIBRARY = KIT / "style" / "materials" / "library.json"
SWITCHES = ("jetty", "oriel", "tower")


def texel_rule() -> float:
    """Texels per metre the near surfaces must show (the materials library's rule, else 256)."""
    try:
        rule = json.loads(LIBRARY.read_text(encoding="utf-8")).get("rule") or {}
        return float(rule.get("px_per_m") or rule.get("near_px_per_m") or 256)
    except (OSError, ValueError, AttributeError):
        return 256.0


def png_width(raw: bytes) -> int:
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">I", raw[16:20])[0]


def load_street(path: Path) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    houses = spec.get("houses") if isinstance(spec, dict) else None
    if not houses:
        raise ValueError("%s: no houses" % path)
    seen = set()
    for i, h in enumerate(houses):
        hid = str(h.get("id") or "")
        if not hid or hid in seen:
            raise ValueError("%s: house %d needs a unique id" % (path, i))
        seen.add(hid)
        if len(list(h.get("position") or [])) != 3:
            raise ValueError("%s: house %s needs a position [x, y, z]" % (path, hid))
    return spec


def _ratio(color: str, tint: str | None):
    """What a material differs from its painted layer by, linear and clamped to 1 (as write_glb)."""
    rgb, t = hex_rgb(color), hex_rgb(tint or color)
    return tuple(min(1.0, srgb_to_linear(c) / max(1e-4, srgb_to_linear(k))) for c, k in zip(rgb, t))


def build_street(spec: dict, profile: str, region: str | None, tex_dir: Path | None, tile_m: float | None,
                 budget: int | None = None):
    """(nodes, shared materials, textures, colors, placements, node_extras, report)."""
    rule = texel_rule()
    nodes, colors, placements, extras, shared, textures, houses = {}, {}, {}, {}, {}, {}, []
    tile_used = None
    for h in spec["houses"]:
        st = Style(profile, h.get("region") or spec.get("region") or region, int(h.get("seed", 1)))
        mats = st.materials("house")
        tex = st.textures(mats, tex_dir)
        if tile_m:
            st.tile_m = float(tile_m)
        elif tex:
            st.tile_m = png_width(next(iter(tex.values()))) / rule
        tile_used = st.tile_m
        house = housemod.House(st, _footprint(h.get("footprint", "rect")), h.get("storeys"),
                               *(h.get(k) for k in SWITCHES), h.get("door_kind"), h.get("timber"))
        b = budget or st.budget["building"]
        lod0 = house.fit(b)
        hid = str(h["id"])
        nodes[hid] = lod0
        x, y, z = (float(v) for v in h["position"])
        placements[hid] = (x, y, z, float(h.get("yaw", 0)))
        extras[hid] = {"x-class": "building", "seed": int(h.get("seed", 1)), "region": st.region_name}
        colors[hid] = {}
        for spec_m in mats.values():
            name = spec_m["name"]
            if name not in lod0.tris:
                continue
            tint = (st.layers.get(spec_m.get("layer")) or {}).get("tint")
            if name in tex:
                textures.setdefault(name, tex[name])
                colors[hid][name] = _ratio(spec_m["color"], tint)
                base = {"color": tint or spec_m["color"], "tint": tint}
            else:
                colors[hid][name] = tuple(srgb_to_linear(c) for c in hex_rgb(spec_m["color"]))
                base = {"color": "#ffffff"}
            if name not in shared:
                shared[name] = dict(base, roughness=spec_m.get("roughness", 0.9),
                                    **{k: spec_m[k] for k in ("emissive", "emissive_strength") if spec_m.get(k)})
        tri = lod0.count()
        houses.append({"id": hid, "triangles": tri, "budget": b,
                       "efficiency": round(100.0 if tri <= b else 100.0 * b / tri, 1),
                       "storeys": house.report.get("storeys"), "door": house.report.get("door")})
    maps = {}
    for raw in textures.values():
        maps.setdefault(raw, png_width(raw))
    report = {"houses": houses, "materials": len(shared), "images": len(maps), "tile_m": round(tile_used or 4.0, 3),
              "texture_bytes": sum(w * w * 4 for w in maps.values()),
              "px_per_m": round(max(maps.values()) / tile_used, 1) if maps and tile_used else None,
              "texel_rule": rule}
    return nodes, shared, textures, colors, placements, extras, report


def _footprint(f):
    if isinstance(f, list):
        return f
    p = Path(str(f))
    if str(f).endswith(".json") and p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return f


def run(a) -> int:
    """`style-gen street` (called by gen.py with its parsed arguments)."""
    import gen   # noqa: E402 (gen imports this module lazily too)
    if not a.street:
        print("GEN_FAIL street needs --street street.json")
        return 2
    try:
        spec = load_street(Path(a.street))
        nodes, mats, tex, colors, places, extras, report = build_street(
            spec, a.profile, a.region, Path(a.textures) if a.textures else None, a.tile_m, a.budget)
    except (ValueError, KeyError, OSError) as e:
        print("GEN_FAIL street: %s" % e)
        return 1
    out = Path(a.out)
    write_glb(out, nodes, mats, tex, extras={"generator": "kit/style/gen street", "profile": a.profile,
                                             "parts": list(nodes), "iamar_vertex_colour": "linear"},
              colors=colors, placements=places, node_extras=extras)
    over = [h for h in report["houses"] if h["triangles"] > h["budget"]]
    code = 1 if over else 0
    rule = report["texel_rule"]
    if report["px_per_m"] is not None and report["px_per_m"] < rule * 0.8:
        report.setdefault("warnings", []).append(
            "WARN texel: %.0f px per metre < the %.0f rule: use --tile-m %.2f or bigger maps"
            % (report["px_per_m"], rule, report["tile_m"] * report["px_per_m"] / rule))
    report.update({"kind": "street", "out": str(out)})
    if a.world:
        xs = [abs(c) for hid, m in nodes.items() for ts in m.tris.values() for t in ts for p in t
              for c in (p[0] + places[hid][0], p[2] + places[hid][2])]
        gen.preview_world(Path(a.world), out, "street", (max(xs) if xs else 10.0) + 4.0, "street")
        report["world"] = a.world
        if a.check:
            rc, text = gen.run_audit(Path(a.world), gen.HOUSE_AUDITS)
            report["audit"] = [ln for ln in text.splitlines() if "RESULT" in ln or ln.startswith("ERROR")]
            report["audit_ok"] = rc == 0
            code = max(code, 0 if rc == 0 else 1)
    elif a.check:
        print("GEN_FAIL --check needs --world")
        return 2
    if a.json:
        print(json.dumps(report, indent=1))
        return code
    for ln in report.get("audit", []) + report.get("warnings", []):
        print("  " + ln)
    for h in report["houses"]:
        print("  %-12s %5d triangles (budget %d, efficiency %.0f)" % (h["id"], h["triangles"], h["budget"], h["efficiency"]))
    print("%s street %s: %d houses, %d materials, %d maps (%.1f MiB, %s px/m, tile %.2f m)%s" % (
        "GEN_OK" if code == 0 else "GEN_FAIL", out, len(nodes), report["materials"], report["images"],
        report["texture_bytes"] / 2 ** 20, report["px_per_m"] if report["px_per_m"] is not None else "-",
        report["tile_m"], "" if "audit_ok" not in report else (", audit ok" if report["audit_ok"] else ", AUDIT FAILED")))
    return code
