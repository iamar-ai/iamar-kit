#!/usr/bin/env python3
"""Composition check (recipe book: kit/recipes/composition/README.md).

Reads a world's `composition.json` (format in the README) and fails when a rule
of the composition recipes breaks: sign legibility, sign mounting, vista
picture width, sightline clearance, skyline variation, first-view target.
Pure Python 3, no engine needed.  Usage:
    check_composition.py composition.json      exit 0 = COMPOSITION_OK, 1 = rules broken
"""

from __future__ import annotations

import json
import math
import statistics
import sys

LETTER_PER_M = 60.0          # recipe 4: 0.25 m letters read at 15 m
MOUNT_MIN, MOUNT_MAX = 2.5, 4.0
VISTA_WIDTH_DEG, VISTA_APART_DEG = 44.0, 8.0
MIN_ROOF_SPREAD_M = 0.6      # recipe 3: roof rise std dev across ordinary houses
FIRST_VIEW_DEG = 60.0        # recipe 5: a focal target within half this angle of the spawn heading


def bearing(frm, to):
    return math.degrees(math.atan2(to[0] - frm[0], to[1] - frm[1]))


def diff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def seg_hits_rect(p, q, rect):
    """Segment p-q against axis-aligned rect [x0, z0, x1, z1] (Liang-Barsky)."""
    x0, z0, x1, z1 = rect
    dx, dz = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dz, p[1] - z0), (dz, z1 - p[1])):
        if pp == 0:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def check(c: dict) -> list[str]:
    errs: list[str] = []
    for s in c.get("signs", []):
        sid = s.get("id", "?")
        need = s["read_distance_m"] / LETTER_PER_M
        if s["letter_m"] + 1e-9 < need:
            errs.append(f"sign {sid}: letters {s['letter_m']} m too small for {s['read_distance_m']} m (need >= {need:.2f})")
        if not MOUNT_MIN <= s["mount_m"] <= MOUNT_MAX:
            errs.append(f"sign {sid}: mounted at {s['mount_m']} m, rule is {MOUNT_MIN}-{MOUNT_MAX} m")
        if s.get("mirrored"):
            errs.append(f"sign {sid}: text is mirrored (single-sided face per reading direction)")
        if not s.get("lit"):
            errs.append(f"sign {sid}: not lit at night")
        if s.get("blocks_opening"):
            errs.append(f"sign {sid}: covers a door or window")
    for v in c.get("vistas", []):
        vid, eye = v.get("id", "?"), v["eye_xz"]
        bs = [bearing(eye, t["xz"]) for t in v["targets"]]
        if max(bs) - min(bs) > VISTA_WIDTH_DEG:
            errs.append(f"vista {vid}: targets span {max(bs) - min(bs):.0f} deg, one picture is <= {VISTA_WIDTH_DEG:.0f}")
        sb = sorted(bs)
        for a, b in zip(sb, sb[1:]):
            if b - a < VISTA_APART_DEG:
                errs.append(f"vista {vid}: two targets only {b - a:.0f} deg apart (< {VISTA_APART_DEG:.0f}), they merge")
        for t in v["targets"]:
            for ob in c.get("obstacles", []):
                if ob.get("id") in t.get("allowed", []):
                    continue
                if seg_hits_rect(eye, t["xz"], ob["rect"]):
                    errs.append(f"vista {vid}: sightline to {t['name']} blocked by {ob.get('id', 'obstacle')}")
    rises = [h["rise_m"] for h in c.get("roofs", [])]
    if len(rises) >= 4 and statistics.pstdev(rises) < MIN_ROOF_SPREAD_M:
        errs.append(f"skyline flat: roof rise std dev {statistics.pstdev(rises):.2f} m < {MIN_ROOF_SPREAD_M} m")
    fv = c.get("first_view")
    if fv:
        heading = fv["heading_deg"]
        offs = [abs(diff(bearing(fv["spawn_xz"], t["xz"]), heading)) for t in fv["focals"]]
        if not offs or min(offs) > FIRST_VIEW_DEG / 2:
            errs.append(f"first view: no focal target within {FIRST_VIEW_DEG / 2:.0f} deg of the spawn heading")
    return errs


def main() -> int:
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    errs = check(c)
    for e in errs:
        print("FAIL", e)
    print("COMPOSITION_OK" if not errs else f"COMPOSITION_FAIL {len(errs)}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
