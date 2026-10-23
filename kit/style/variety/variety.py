#!/usr/bin/env python3
"""Anti-repetition tools: per-object jitter, prop scatter, and a variety check for scene.json.

    python3 kit/style/variety/variety.py check  <world folder | scene.json> [--style P] [--json]
    python3 kit/style/variety/variety.py jitter <scene.json> [--seed N] [--yaw 180] [--scale 0.06] [--tint 0.04] [--write]
    python3 kit/style/variety/variety.py scatter <asset> [<asset> ...] --area X0 Z0 X1 Z1 --count N
                                           [--min-dist 2.5] [--seed N] [--avoid x z r ...] [--out scene.json]

Engineering practice (every world): repeated placements read as copies. The profile's
weathering.neighbour_rule states the look rule; this tool enforces the measurable part:

  neighbours  the same asset closer than lint.neighbour_m (default 12 m) must differ by yaw
              (>= min_yaw_deg), scale (>= min_scale_delta) or tint ("x-tint")
  sequence    no run of 3+ placements of the same asset in a row on the ground: each within run_m
              (default 20 m) of the previous with nothing else between them, evenly spaced (gaps
              within run_even, 0.95) and straight (bend under run_deg, 4 deg), as a placed street
              row is; random scatters pass (>= 19 of 20 seeds); scene.json order does not matter
  share       with 6+ placements, one asset may not be more than max_share (0.4) of them
  props       prop placements of one asset closer than prop_min_dist (default 1.0 m) overlap

jitter gives every object a seeded, repeatable yaw / scale / "x-tint" shift (same seed and ids,
same result). scatter places props by Poisson-disc sampling (no two closer than --min-dist),
rotating through the assets but never the same twice in a row, with a seeded yaw and scale.
Thresholds come from the profile's optional "variety" block (keys of DEFAULTS), else DEFAULTS.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import math
from pathlib import Path
import random
import sys

DEFAULTS = {
    "neighbour_m": 12.0,
    "min_yaw_deg": 20.0,
    "min_scale_delta": 0.05,
    "min_tint_delta": 0.02,
    "max_run": 2,
    "run_m": 20.0,
    "run_deg": 4.0,
    "run_even": 0.95,
    "max_share": 0.4,
    "share_min_objects": 6,
    "prop_min_dist": 1.0,
}


def load_scene(p):
    p = Path(p)
    f = p / "scene.json" if p.is_dir() else p
    return json.loads(f.read_text(encoding="utf-8")), f


def load_thresholds(style, world):
    t = dict(DEFAULTS)
    cand = None
    if style:
        cand = Path(style) if style.endswith(".json") else Path(__file__).resolve().parents[1] / style / "style.json"
    elif (world / "style.json").is_file():
        cand = world / "style.json"
    if cand and cand.is_file():
        prof = json.loads(cand.read_text(encoding="utf-8"))
        t["neighbour_m"] = float((prof.get("lint") or {}).get("neighbour_m", t["neighbour_m"]))
        t.update({k: v for k, v in (prof.get("variety") or {}).items() if k in t})
    return t


def yaw(o):
    r = o.get("rotation") or [0, 0, 0]
    return float(r[1]) if len(r) > 1 else 0.0


def scl(o):
    s = o.get("scale", 1)
    return float(s[0] if isinstance(s, list) else s)


def tint_hsv(o):
    h = o.get("x-tint")
    if not (isinstance(h, str) and len(h) >= 7 and h[0] == "#"):
        return None
    return colorsys.rgb_to_hsv(*(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)))


def yaw_diff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def differs(a, b, t):
    """True when two placements of the same asset look different enough."""
    if yaw_diff(yaw(a), yaw(b)) >= t["min_yaw_deg"]:
        return True
    if abs(scl(a) - scl(b)) >= t["min_scale_delta"] * min(scl(a), scl(b)):
        return True
    ta, tb = tint_hsv(a), tint_hsv(b)
    if ta and tb:
        dh = abs(ta[0] - tb[0])
        dh = min(dh, 1 - dh)
        return dh + abs(ta[1] - tb[1]) + abs(ta[2] - tb[2]) >= t["min_tint_delta"]
    return bool(ta) != bool(tb)


def runs(objs, t):
    """Straight runs of more than max_run placements of one asset on the ground (x, z).

    Two placements of one asset link when they are within run_m and no other placement lies in
    their lune (closer to both than they are to each other), so an interleaved model breaks the
    run. Two links through a middle placement, about equally long (shorter >= run_even x longer)
    and bending less than run_deg, are a row of three;
    rows sharing links join into one run. The result depends on positions only, not list order."""
    pts = [((o.get("position") or [0, 0, 0])[0], (o.get("position") or [0, 0, 0])[2]) for o in objs]
    ident = [str(o.get("id", i)) for i, o in enumerate(objs)]
    n, rm = len(objs), t["run_m"]
    links = {i: [] for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if objs[i]["asset"] != objs[j]["asset"]:
                continue
            d = math.dist(pts[i], pts[j])
            if d > rm or any(k not in (i, j) and math.dist(pts[i], pts[k]) < d and math.dist(pts[j], pts[k]) < d
                             for k in range(n)):
                continue
            links[i].append(j)
            links[j].append(i)
    parent = {}

    def find(e):
        while parent.setdefault(e, e) != e:
            e = parent[e]
        return e

    cos_max = -math.cos(math.radians(t["run_deg"]))
    for m in range(n):
        for a in links[m]:
            for b in links[m]:
                if a >= b:
                    continue
                va = (pts[a][0] - pts[m][0], pts[a][1] - pts[m][1])
                vb = (pts[b][0] - pts[m][0], pts[b][1] - pts[m][1])
                la, lb = math.hypot(*va), math.hypot(*vb)
                if la and lb and min(la, lb) >= t["run_even"] * max(la, lb) \
                        and (va[0] * vb[0] + va[1] * vb[1]) / (la * lb) <= cos_max:
                    ea, eb = (min(a, m), max(a, m)), (min(b, m), max(b, m))
                    parent[find(ea)] = find(eb)
    groups = {}
    for e in list(parent):
        groups.setdefault(find(e), set()).update(e)
    out = []
    for members in groups.values():
        if len(members) > t["max_run"]:
            ids = sorted(ident[i] for i in members)
            out.append((ids, objs[next(iter(members))]["asset"]))
    return sorted(out)


def check(scene, t):
    """Returns a list of (rule, where, message)."""
    objs = [o for o in scene.get("objects") or [] if o.get("asset")]
    out = []
    pos = lambda o: o.get("position") or [0, 0, 0]
    for i, a in enumerate(objs):
        for b in objs[i + 1:]:
            if a["asset"] != b["asset"]:
                continue
            d = math.dist(pos(a), pos(b))
            if "prop" in (str(a.get("x-class", "")) + a["asset"]).lower() and d < t["prop_min_dist"]:
                out.append(("props", b.get("id"), "%s is %.2f m from %s (closer than %.1f m)" % (b.get("id"), d, a.get("id"), t["prop_min_dist"])))
            if d < t["neighbour_m"] and not differs(a, b, t):
                out.append(("neighbours", b.get("id"),
                            "same %s as %s %.1f m away with the same yaw, scale and tint: rotate >= %g deg, rescale >= %g %% or add x-tint"
                            % (a["asset"], a.get("id"), d, t["min_yaw_deg"], t["min_scale_delta"] * 100)))
    for ids, asset in runs(objs, t):
        out.append(("sequence", ids[-1], "%d placements in a row use %s (%s): interleave another model"
                    % (len(ids), asset, ", ".join(ids))))
    if len(objs) >= t["share_min_objects"]:
        counts = {}
        for o in objs:
            counts[o["asset"]] = counts.get(o["asset"], 0) + 1
        for asset, n in counts.items():
            if n / len(objs) > t["max_share"]:
                out.append(("share", asset, "%s is %d of %d placements (%.0f %%, max %.0f %%): add models"
                            % (asset, n, len(objs), 100 * n / len(objs), 100 * t["max_share"])))
    return out


def jitter(scene, seed="1", yaw_range=180.0, scale_range=0.06, tint_range=0.04):
    """Seeded per-object yaw / scale / tint shift; the seed and object id decide, so it is repeatable."""
    for o in scene.get("objects") or []:
        r = random.Random("%s:%s" % (seed, o.get("id")))
        rot = list(o.get("rotation") or [0, 0, 0])
        rot[1] = round((rot[1] + r.uniform(-yaw_range, yaw_range)) % 360, 1)
        o["rotation"] = rot
        o["scale"] = round(scl(o) * (1 + r.uniform(-scale_range, scale_range)), 3)
        h, s, v = tint_hsv(o) or (0.1, 0.0, 0.8)
        h = (h + r.uniform(-tint_range, tint_range)) % 1
        s = min(1.0, max(0.0, s + r.uniform(-tint_range, tint_range)))
        v = min(1.0, max(0.2, v + r.uniform(-tint_range, tint_range)))
        o["x-tint"] = "#%02x%02x%02x" % tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, s, v))
    return scene


def scatter(assets, area, count, min_dist=2.5, seed="1", avoid=(), y=0.0, prefix="scatter"):
    """Poisson-disc dart throwing in area (x0, z0, x1, z1); avoid is (x, z, radius) circles."""
    x0, z0, x1, z1 = area
    r = random.Random(seed)
    pts, tries = [], 0
    while len(pts) < count and tries < count * 200:
        tries += 1
        x, z = r.uniform(x0, x1), r.uniform(z0, z1)
        if any(math.hypot(x - ax, z - az) < ar for ax, az, ar in avoid):
            continue
        if any(math.hypot(x - px, z - pz) < min_dist for px, pz in pts):
            continue
        pts.append((x, z))
    objs, last = [], None
    for i, (x, z) in enumerate(pts):
        choices = [a for a in assets if a != last] or list(assets)
        asset = choices[i % len(choices)]
        last = asset
        objs.append({"id": "%s_%03d" % (prefix, i + 1), "asset": asset, "position": [round(x, 2), y, round(z, 2)],
                     "rotation": [0, round(r.uniform(0, 360), 1), 0], "scale": round(r.uniform(0.9, 1.1), 3)})
    return objs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("world")
    c.add_argument("--style")
    c.add_argument("--json", action="store_true")
    j = sub.add_parser("jitter")
    j.add_argument("scene")
    j.add_argument("--seed", default="1")
    j.add_argument("--yaw", type=float, default=180.0)
    j.add_argument("--scale", type=float, default=0.06)
    j.add_argument("--tint", type=float, default=0.04)
    j.add_argument("--write", action="store_true")
    s = sub.add_parser("scatter")
    s.add_argument("assets", nargs="+")
    s.add_argument("--area", nargs=4, type=float, required=True, metavar=("X0", "Z0", "X1", "Z1"))
    s.add_argument("--count", type=int, required=True)
    s.add_argument("--min-dist", type=float, default=2.5)
    s.add_argument("--seed", default="1")
    s.add_argument("--avoid", nargs="*", type=float, default=[])
    s.add_argument("--out")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        scene, f = load_scene(a.world)
        found = check(scene, load_thresholds(a.style, f.parent))
        if a.json:
            print(json.dumps([{"rule": r, "where": w, "message": m} for r, w, m in found], indent=1))
        else:
            for r, w, m in found:
                print("ERROR [%s] %s: %s" % (r, w, m))
            print("VARIETY_OK" if not found else "VARIETY_FAIL %d" % len(found))
        return 1 if found else 0
    if a.cmd == "jitter":
        scene, f = load_scene(a.scene)
        jitter(scene, a.seed, a.yaw, a.scale, a.tint)
        if a.write:
            f.write_text(json.dumps(scene, indent=1) + "\n", encoding="utf-8")
            print("jittered %d objects in %s" % (len(scene.get("objects") or []), f))
        else:
            print(json.dumps(scene.get("objects"), indent=1))
        return 0
    objs = scatter(a.assets, a.area, a.count, a.min_dist, a.seed, list(zip(a.avoid[0::3], a.avoid[1::3], a.avoid[2::3])))
    if a.out:
        f = Path(a.out)
        scene = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {"format": "iamar-scene", "format_version": 0}
        scene.setdefault("objects", []).extend(objs)
        f.write_text(json.dumps(scene, indent=1) + "\n", encoding="utf-8")
        print("placed %d of %d requested into %s" % (len(objs), a.count, f))
    else:
        print(json.dumps(objs, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
