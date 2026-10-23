#!/usr/bin/env python3
"""Flat-wall audit: long stretches of wall a walker sees with no opening, arch or relief.

    python3 kit/audit/flat_wall.py <world folder | model.glb ...> [--style PROFILE] [--max-m M] [--json]

Track A rule (kit/interview/tracks/track_a.md, kit/review/REVIEWER.md): "a long flat wall with no
arch is a FAIL". The limit is the style profile's lint.flat_wall_max_m (iamar: 6 m); a profile
without it (Track B worlds, whose own style bible decides) skips the audit. PROFILE is a profile id
or a style.json (default: the world's own style.json, else iamar), resolved like the style lint.

How it measures, per building, landmark or structure (in the model's own frame, so a rotated
building is measured along its walls): from 1 m outside each of the four sides, horizontal rays
every 0.1 m along the side (finer than a 16 cm door jamb) at 0.9, 1.6 and 2.3 m above the model's base go towards the middle.
A column is wall when all three rays meet the model within 1 m of that side's front wall; a ray
that goes deeper (a door, an arch, an open front) or misses is an opening. A flat run is a chain of
wall columns whose depths (the middle of the three, so a pane or sill at one height is not relief) stay within 0.05 m of where the run started, so a door frame or recess, a pier,
a buttress or a lean-to 5 cm proud or deeper breaks it; paint and flush panes do not.
In a world folder, a column whose wall faces another object within 3 m (a party wall, a hillside)
is not seen and breaks the run. ERROR when the longest run of a side is over the limit.
Needs numpy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import meshworld  # noqa: E402
from meshworld import style_lint  # noqa: E402
sys.path.insert(0, str(HERE.parent / "style"))
import check_style  # noqa: E402

CLASSES = ("building", "landmark", "structure")
STEP = 0.1             # metres between columns along a side (finer than a 16 cm door jamb or pier)
EYE = (0.9, 1.6, 2.3)  # ray heights above the model's base
START = 1.0            # rays start this far outside the side
WALL_BAND = 1.0        # a hit deeper than this behind the side's front wall is an opening
RELIEF = 0.05          # depth change that breaks a flat run (a door frame, a pier)
HIDDEN = 3.0           # another object this close in front of the wall hides it
MIN_HEIGHT = 2.5       # lower objects (quays, walls, plinths) are not walls a walker faces
SIDES = (("+x", 0, 1), ("-x", 0, -1), ("+z", 2, 1), ("-z", 2, -1))


def profile_limit(ref: str) -> float | None:
    prof, _ = check_style.load(ref)
    v = (prof.get("lint") or {}).get("flat_wall_max_m")
    return float(v) if isinstance(v, (int, float)) and v > 0 else None


def water_y(water, x, z) -> np.ndarray:
    """Surface height of the scene's water planes over each (x, z), -inf where there is none."""
    y = np.full(len(x), -np.inf)
    for wp in water or []:
        px, py, pz = (list(wp.get("position") or [0, 0, 0]) + [0, 0, 0])[:3]
        sx, sz = (list(wp.get("size") or [0, 0]) + [0, 0])[:2]
        inside = (np.abs(x - px) <= sx / 2) & (np.abs(z - pz) <= sz / 2)
        y = np.where(inside, np.maximum(y, py), y)
    return y


def runs(depth: np.ndarray, seen: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) column ranges of flat wall; depth is (heights, columns), inf = miss."""
    fin = np.isfinite(depth).all(0)
    front = np.min(np.where(fin, depth.min(0), np.inf)) if fin.any() else np.inf
    wall = fin & seen & (depth.max(0) <= front + WALL_BAND)
    mid = np.median(depth, 0)   # a sill or pane at one height alone is not relief
    out, start, ref = [], None, 0.0
    for c in range(depth.shape[1] + 1):
        ok = c < depth.shape[1] and wall[c]
        if ok and start is not None and abs(mid[c] - ref) < RELIEF:
            continue
        if start is not None:
            out.append((start, c))
        start, ref = (c, mid[c]) if ok else (None, 0.0)
    return out


def audit_object(w, oi: int, limit: float, in_world: bool, water=()) -> list[dict]:
    o = w.objects[oi]
    m = o["matrix"]
    inv = np.linalg.inv(m)
    sel = w.obj == oi
    local = w.tris[sel].reshape(-1, 3) @ inv[:3, :3].T + inv[:3, 3]
    if not len(local):
        return []
    lo, hi = local.min(0), local.max(0)
    scale = np.linalg.norm(m[:3, :3], axis=0)          # metres per model unit along x, y, z
    if (hi[1] - lo[1]) * scale[1] < MIN_HEIGHT:
        return []
    others = ~sel
    out = []
    for name, axis, sign in SIDES:
        other = 2 - axis
        n = int((hi[other] - lo[other]) * scale[other] / STEP)
        if n < 1:
            continue
        along = lo[other] + (np.arange(n) + 0.5) * (hi[other] - lo[other]) / n
        step_m = (hi[other] - lo[other]) * scale[other] / n
        face = hi[axis] if sign > 0 else lo[axis]
        d_loc = np.zeros(3)
        d_loc[axis] = -sign
        d_w = m[:3, :3] @ d_loc
        unit = np.linalg.norm(d_w)
        p0 = np.zeros((n, 3))
        p0[:, other] = along
        p0[:, axis] = face + sign * START / scale[axis]
        p0[:, 1] = lo[1]
        base = p0 @ m[:3, :3].T + m[:3, 3]                 # outside the side, at the model's base
        seen = np.ones(n, bool)
        if in_world:   # eye heights over the ground a walker stands on; ground under water: not seen
            top = float((hi[1] - lo[1]) * scale[1] + base[0, 1]) + 1.0
            t0, i0, _ = w.raycast(np.c_[base[:, 0], np.full(n, top), base[:, 2]], np.broadcast_to([0.0, -1.0, 0.0], (n, 3)), top + 1e3)
            gy = top - t0
            seen = ~(np.isfinite(t0) & (gy <= water_y(water, base[:, 0], base[:, 2])))   # no ground: assume a walker
            base[:, 1] = np.where(np.isfinite(t0), gy, base[:, 1])
        depth = np.full((len(EYE), n), np.inf)
        hits = np.zeros((n, 3))
        span = (hi[axis] - lo[axis]) * scale[axis] + START
        for k, h in enumerate(EYE):
            pw = base + [0.0, h, 0.0]
            t, _, _ = w.raycast(pw, np.broadcast_to(d_w / unit, pw.shape), span, mask=sel)
            depth[k] = t - START
            if h == 1.6:
                hits = pw + np.where(np.isfinite(t), t, 0)[:, None] * (d_w / unit)
        if in_world and others.any():
            back = -d_w / unit
            t2, _, _ = w.raycast(hits + back * 0.05, np.broadcast_to(back, hits.shape), HIDDEN, mask=others)
            seen &= ~np.isfinite(t2)
        best = max(runs(depth, seen), key=lambda r: r[1] - r[0], default=None)
        if best is None:
            continue
        length = (best[1] - best[0]) * step_m
        c = (best[0] + best[1] - 1) // 2
        at = hits[c] if np.isfinite(depth[1, c]) else None
        out.append({"side": name, "run_m": round(length, 2), "side_m": round(n * step_m, 2),
                    "at": [round(float(v), 2) for v in at] if at is not None else None, "over": length > limit})
    return out


def run(targets, style=None, max_m=None) -> dict:
    items, checked = [], 0
    for t in targets:
        p = Path(t)
        try:
            ref = style or (str(p / "style.json") if p.is_dir() and (p / "style.json").is_file() else "iamar")
            limit = max_m if max_m is not None else profile_limit(ref)
            if limit is None:
                items.append({"level": "INFO", "where": t, "message": "style profile %s sets no lint.flat_wall_max_m: audit skipped" % ref})
                continue
            water = []
            if p.is_dir():
                w, in_world = meshworld.load_world(p), True
                water = json.loads((p / "scene.json").read_text(encoding="utf-8")).get("water") or []
            elif p.suffix.lower() == ".glb":
                w, in_world = meshworld.load_models([p]), False
            else:
                items.append({"level": "ERROR", "where": t, "message": "not a world folder or .glb"})
                continue
        except (OSError, ValueError, KeyError) as e:
            items.append({"level": "ERROR", "where": t, "message": "cannot read: %s" % e})
            continue
        for oi, o in enumerate(w.objects):
            if o["cls"] not in CLASSES:
                continue
            checked += 1
            for s in audit_object(w, oi, limit, in_world, water):
                where = "%s:%s %s face" % (w.name, o["id"], s["side"])
                if s["over"]:
                    items.append({"level": "ERROR", "where": where, "run_m": s["run_m"], "at": s["at"],
                                  "message": "flat wall %.1f m at eye height (limit %.1f m) with no opening, arch or relief of %.2f m; centre %s: add a door, arch, pier, buttress, frame or lean-to"
                                  % (s["run_m"], limit, RELIEF, s["at"])})
                else:
                    items.append({"level": "INFO", "where": where, "run_m": s["run_m"],
                                  "message": "longest flat run %.1f m of %.1f m" % (s["run_m"], s["side_m"])})
    return {"ok": not any(i["level"] == "ERROR" for i in items), "checked": checked, "items": items}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("targets", nargs="+", help="world folder(s) or .glb file(s)")
    ap.add_argument("--style", help="profile id or style.json (default: the world's style.json, else iamar)")
    ap.add_argument("--max-m", type=float, help="limit in metres (default: the profile's lint.flat_wall_max_m)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--quiet", action="store_true", help="only ERROR lines")
    a = ap.parse_args(argv)
    rep = run(a.targets, a.style, a.max_m)
    errs = [i for i in rep["items"] if i["level"] == "ERROR"]
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for i in rep["items"]:
            if not (a.quiet and i["level"] == "INFO"):
                print("%-5s %s [flat-wall] %s" % (i["level"], i["where"], i["message"]))
        print("%s audit flat-wall: %d error(s), %d object(s) checked" % ("FAIL" if errs else "OK", len(errs), rep["checked"]))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
