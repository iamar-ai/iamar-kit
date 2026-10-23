#!/usr/bin/env python3
"""Closed variants of the catalogue's open-sided city houses: wall up the side each one shared
with a neighbour and cap the roof ends there, so the house stands alone.

  python3 kit/catalog/assets/close_open_sides.py            # write buildings/<id>_closed.glb + the source
  python3 kit/catalog/assets/close_open_sides.py --check    # files match sources/city_buildings_closed.json

A terraced city house has no wall where its party wall was (the city never builds a wall nobody
sees), and its roof sheets end there too, open along the gable. import_city_buildings.py
measures which footprint side is open (sources/city_buildings.json "open_sides"). For each such
side this script:

  1. takes the outermost plane of the house on that side (its wall ends and roof ends stop there),
  2. cuts the mesh with a plane 4 cm inside it and, along the side, measures the lowest and
     highest point of the cut (ground to roof top under the roof, roof underside to roof top
     under an overhang); the outline keeps the eave and ridge corners exactly,
  3. fills that outline with a cap 5 mm inside the outer plane, facing out, and a second one
     2 cm further in facing the rooms (seen through the windows): wall colour up to the roof
     underside, the roof's own colour across the roof's end,
  4. appends the cap to the house's mesh as one more primitive with the same material and the
     same vertex attributes (COLOR_0, TEXCOORD_0/1 copied from the house's own wall and roof
     vertices), so the file renders like the original.

The original file is untouched; the variant is buildings/<id>_closed.glb with its own record in
sources/city_buildings_closed.json (catalog.py turns it into an entry and points the original's
description at it). Rerun after import_city_buildings.py (or seal_trim_edges.py); the variant is
sealed like its original (seal_trim_edges.seal). Python 3.8+, standard library only.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from import_city_models import measure  # noqa: E402  (same folder)

CATALOG_DIR = HERE.parent
SOURCE = CATALOG_DIR / "sources" / "city_buildings.json"
CLOSED = CATALOG_DIR / "sources" / "city_buildings_closed.json"

SECTION_IN = 0.04   # cut this far inside the side's plane (a deeper cut under a sloping roof
                    # would lift the cap above the roof at the plane)
GROUND_TOUCH = 0.15 # a cut wall end this close to the ground stands on it
CAP_IN = 0.005      # outward cap this far inside it (the wall ends' edges are within the 3 cm
                    # ring that seals an edge)
BACK_IN = 0.025     # inward-facing cap
COVER_D = 0.06      # the house's own faces parallel to the cap this close already close that spot
FOOT_DEPTH = 0.3    # wall ends this far behind the side's plane still close it
CORNER = 0.4        # a corner's wall end is the outermost foot this close to the cap's end
SEG_DEPTH = 0.6     # a side with recorded ends: its wall feet lie this close to the footprint line
MIN_RUN = 0.02      # uncovered gaps smaller than this are left out
COLUMN = 0.4        # widest cap column
JUMP = 0.003        # outline samples either side of every kink, so a jump (eave end) stays vertical
GRID = 0.25         # plus a sample every this many metres
TOL = 0.01          # outline simplification tolerance
ROOF_MAX = 0.6      # a roof end is at most this thick; deeper means wall below the roof
ROOF_BAND = 0.15    # roof colour band when the roof's underside is not found
WALL_COLOUR_BAND = (0.3, 2.8)   # wall colour sampled from vertical faces this high (ground floor)

FLOAT, U32 = 5126, 5125
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
CSIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
CFMT = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}


# ------------------------------------------------------------------ glb in and out

def parse_glb(b: bytes):
    magic, _ver, _ln = struct.unpack_from("<III", b, 0)
    if magic != 0x46546C67:
        raise ValueError("not a GLB file")
    jl, _jt = struct.unpack_from("<II", b, 12)
    j = json.loads(b[20:20 + jl].decode("utf-8"))
    o = 20 + jl
    binary = b""
    if o < len(b):
        bl, _bt = struct.unpack_from("<II", b, o)
        binary = b[o + 8:o + 8 + bl]
    return j, binary


def write_glb(j: dict, binary: bytes) -> bytes:
    js = json.dumps(j, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binary), 0x004E4942) + binary)


def read_accessor(j: dict, binary: bytes, i: int) -> list:
    a = j["accessors"][i]
    bv = j["bufferViews"][a["bufferView"]]
    c, ct = NCOMP[a["type"]], a["componentType"]
    stride = bv.get("byteStride") or c * CSIZE[ct]
    o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    f = "<" + CFMT[ct] * c
    rows = [struct.unpack_from(f, binary, o + k * stride) for k in range(a["count"])]
    if a.get("normalized"):
        top = float((1 << (8 * CSIZE[ct] - (1 if ct in (5120, 5122) else 0))) - 1)
        rows = [tuple(v / top for v in r) for r in rows]
    return rows


def _mat(n: dict) -> list:
    """Node matrix, row-major 4x4 as a flat list (applied as m @ column vector)."""
    if "matrix" in n:
        m = n["matrix"]   # glTF stores column-major
        return [m[0], m[4], m[8], m[12], m[1], m[5], m[9], m[13], m[2], m[6], m[10], m[14], 0, 0, 0, 1]
    tx, ty, tz = n.get("translation", (0, 0, 0))
    qx, qy, qz, qw = n.get("rotation", (0, 0, 0, 1))
    sx, sy, sz = n.get("scale", (1, 1, 1))
    r = [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw),
         2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw),
         2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)]
    return [r[0] * sx, r[1] * sy, r[2] * sz, tx, r[3] * sx, r[4] * sy, r[5] * sz, ty,
            r[6] * sx, r[7] * sy, r[8] * sz, tz, 0, 0, 0, 1]


def _mul(a: list, b: list) -> list:
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def _pt(m: list, p) -> tuple:
    return tuple(m[r * 4] * p[0] + m[r * 4 + 1] * p[1] + m[r * 4 + 2] * p[2] + m[r * 4 + 3] for r in range(3))


def _inv_affine(m: list) -> list:
    a, b, c, d, e, f, g, h, i = m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    r = [(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det,
         (f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det,
         (d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]
    t = (m[3], m[7], m[11])
    tt = [-(r[k * 3] * t[0] + r[k * 3 + 1] * t[1] + r[k * 3 + 2] * t[2]) for k in range(3)]
    return [r[0], r[1], r[2], tt[0], r[3], r[4], r[5], tt[1], r[6], r[7], r[8], tt[2], 0, 0, 0, 1]


def mesh_nodes(j: dict) -> list:
    """[(node index, world matrix)] of every node with a mesh."""
    out = []

    def visit(i, parent):
        n = j["nodes"][i]
        m = _mul(parent, _mat(n))
        if "mesh" in n:
            out.append((i, m))
        for c in n.get("children", []):
            visit(c, m)

    for r in j["scenes"][j.get("scene", 0)]["nodes"]:
        visit(r, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
    return out


# ------------------------------------------------------------------ geometry

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def load_house(j: dict, binary: bytes):
    """The house's triangles in file coordinates, each (p0, p1, p2, attrs0, attrs1, attrs2), from
    its largest mesh node; plus that node's index, world matrix and the primitive copied from."""
    best = None
    for ni, m in mesh_nodes(j):
        mesh = j["meshes"][j["nodes"][ni]["mesh"]]
        for pi, p in enumerate(mesh["primitives"]):
            if p.get("mode", 4) != 4:
                continue
            cnt = j["accessors"][p["indices"]]["count"] if "indices" in p else j["accessors"][p["attributes"]["POSITION"]]["count"]
            if best is None or cnt > best[0]:
                best = (cnt, ni, m, pi)
    if best is None:
        raise ValueError("no triangle mesh")
    _, ni, m, pi = best
    prim = j["meshes"][j["nodes"][ni]["mesh"]]["primitives"][pi]
    attrs = {k: read_accessor(j, binary, v) for k, v in prim["attributes"].items()}
    pos = [_pt(m, q) for q in attrs["POSITION"]]
    idx = [r[0] for r in read_accessor(j, binary, prim["indices"])] if "indices" in prim else list(range(len(pos)))
    tris = [(idx[k], idx[k + 1], idx[k + 2]) for k in range(0, len(idx) - 2, 3)]
    return pos, attrs, tris, ni, m, prim


def all_faces(j: dict, binary: bytes):
    """(positions, triangles) of every triangle primitive of every mesh node, in file
    coordinates: what already closes a spot may be another material (trim, frame, sill)."""
    pos, tris = [], []
    for ni, m in mesh_nodes(j):
        for p in j["meshes"][j["nodes"][ni]["mesh"]]["primitives"]:
            if p.get("mode", 4) != 4:
                continue
            base = len(pos)
            pts = read_accessor(j, binary, p["attributes"]["POSITION"])
            pos += [_pt(m, q) for q in pts]
            idx = [r[0] for r in read_accessor(j, binary, p["indices"])] if "indices" in p else list(range(len(pts)))
            tris += [(base + idx[k], base + idx[k + 1], base + idx[k + 2]) for k in range(0, len(idx) - 2, 3)]
    return pos, tris


def area_mode(pos, colours, tris, keep):
    """A vertex of the colour with the most face area among the faces keep(normal, centre)
    accepts (colours quantised to 1/32), or None; the cap copies that vertex's attributes."""
    area, first = {}, {}
    for a, b, c in tris:
        n = _cross(_sub(pos[b], pos[a]), _sub(pos[c], pos[a]))
        ln = math.sqrt(_dot(n, n))
        if ln < 1e-9:
            continue
        n = (n[0] / ln, n[1] / ln, n[2] / ln)
        ctr = tuple((pos[a][k] + pos[b][k] + pos[c][k]) / 3 for k in range(3))
        if not keep(n, ctr):
            continue
        key = tuple(int(round(v * 32)) for v in colours[a][:3])
        area[key] = area.get(key, 0.0) + ln / 2
        first.setdefault(key, a)
    if not area:
        return None
    return first[max(area, key=area.get)]


def section(pos, tris, n, t, s):
    """Segments where the plane dot(n, p) = s cuts the triangles: [((u0, v0), (u1, v1), tri)]."""
    out = []
    for ti, (a, b, c) in enumerate(tris):
        ps = (pos[a], pos[b], pos[c])
        d = [_dot(n, p) - s for p in ps]
        if min(d) > 0 or max(d) < 0:
            continue
        pts = []
        for k in range(3):
            p, q, dp, dq = ps[k], ps[(k + 1) % 3], d[k], d[(k + 1) % 3]
            if (dp <= 0 < dq) or (dq <= 0 < dp):
                f = dp / (dp - dq)
                x = tuple(p[i] + (q[i] - p[i]) * f for i in range(3))
                pts.append((_dot(t, x), x[1]))
        if len(pts) == 2:
            out.append((pts[0], pts[1], ti))
    return out


def crossings(segs, u):
    """[(v, tri)] where the vertical line at u meets the section."""
    out = []
    for (u0, v0), (u1, v1), ti in segs:
        if abs(u1 - u0) < 1e-6:
            if abs(u - u0) < 1e-4:
                out += [(v0, ti), (v1, ti)]
            continue
        if min(u0, u1) <= u <= max(u0, u1):
            out.append((v0 + (v1 - v0) * (u - u0) / (u1 - u0), ti))
    return out


def outline(segs, ground, span):
    """Samples (u, lo, mid, hi, roof tri) along the side; None marks a gap (nothing cut there).
    lo..mid is wall, mid..hi the roof's end. Between the outermost cut wall ends that stand on
    the ground, the wall runs from the ground up (the open bay between them is what to close);
    outside them (an overhang, a flower box) only what the cut meets is capped. span: (u0, u1)
    of those wall ends (foot_span)."""
    if not segs:
        return []
    us = set()
    for (u0, _), (u1, _), _ in segs:
        for u in (u0, u1):
            us.update((u - JUMP, u + JUMP))
    umin = min(min(a[0], b[0]) for a, b, _ in segs)
    umax = max(max(a[0], b[0]) for a, b, _ in segs)
    k = math.ceil(umin / GRID)
    while k * GRID < umax:
        us.add(k * GRID)
        k += 1
    pts = []
    for u in sorted(x for x in us if umin + JUMP * 0.5 <= x <= umax - JUMP * 0.5):
        if pts and pts[-1] is not None and u - pts[-1][0] < JUMP * 0.5:
            continue
        cr = sorted(crossings(segs, u))
        if not cr:
            if pts and pts[-1] is not None:
                pts.append(None)
            continue
        lo, (hi, roof) = cr[0][0], cr[-1]
        if span[0] <= u <= span[1]:
            lo = ground
        if hi - lo < 0.02:
            if pts and pts[-1] is not None:
                pts.append(None)
            continue
        below = [v for v, _ in cr if v < hi - 0.02]
        if hi - lo <= ROOF_MAX and lo > ground:
            mid = lo                                   # all roof (an overhang)
        elif below and hi - below[-1] <= ROOF_MAX:
            mid = below[-1]                            # the roof's underside
        else:
            mid = hi - ROOF_BAND
        pts.append((u, lo, mid, hi, roof))
    while pts and pts[-1] is None:
        pts.pop()
    return simplify(pts)


def simplify(pts):
    """Drop samples whose lo, mid and hi all lie within TOL of the line between their neighbours."""
    runs, cur = [], []
    for p in pts:
        if p is None:
            if cur:
                runs.append(cur)
            cur = []
        else:
            cur.append(p)
    if cur:
        runs.append(cur)
    out = []
    for run in runs:
        keep = list(run)
        changed = True
        while changed and len(keep) > 2:
            changed = False
            i = 1
            while i < len(keep) - 1:
                a, p, b = keep[i - 1], keep[i], keep[i + 1]
                f = (p[0] - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0.0
                if all(abs(a[k] + (b[k] - a[k]) * f - p[k]) <= TOL for k in (1, 2, 3)):
                    del keep[i]
                    changed = True
                else:
                    i += 1
        if out:
            out.append(None)
        out += keep
    return out


def side_plane(pos, n, ground) -> float:
    """Where the side's walls end: the outermost vertex on the ground along n (the wall ends'
    feet; a roof overhang, a sign or a flower box can stick out further higher up)."""
    feet = [_dot(n, p) for p in pos if p[1] <= ground + GROUND_TOUCH]
    return max(feet) if feet else max(_dot(n, p) for p in pos)


def foot_span(pos, n, t, ground, d_out, length, centre):
    """(u0, u1) of the wall ends standing on the ground within FOOT_DEPTH of the side's plane.
    When they span much less than the side's measured length (one corner's wall stops short of
    the side), that length from the foot found, towards the house's middle (centre)."""
    us = [_dot(t, p) for p in pos if p[1] <= ground + GROUND_TOUCH and _dot(n, p) >= d_out - FOOT_DEPTH]
    if not us:
        return (1.0, -1.0)
    span = (min(us), max(us))
    if length and span[1] - span[0] < 0.8 * length:
        span = (span[0], span[0] + length) if centre > (span[0] + span[1]) / 2 else (span[1] - length, span[1])
    return span


def corner_depth(pos, n, t, ground, u, d_out, reach=math.inf):
    """How far out the wall end at one corner of the side (along u) reaches on the ground:
    the outermost foot within CORNER of u (and at most reach beyond the plane), else the side's plane."""
    ds = [_dot(n, p) for p in pos if p[1] <= ground + GROUND_TOUCH and abs(_dot(t, p) - u) <= CORNER
          and d_out - 0.3 <= _dot(n, p) <= d_out + reach]
    return max(ds) if ds else d_out


def _lerp(p, q, u, k):
    f = (u - p[0]) / (q[0] - p[0]) if q[0] != p[0] else 0.0
    return p[k] + (q[k] - p[k]) * f


def covered_cells(pos, tris, n, t, plane, facing):
    """2D (u, v) triangles of the house's own faces facing the same way as a cap layer (facing
    +1 out, -1 in) within COVER_D of its plane (a number, or plane(u) where the cap runs between
    corners at different depths): that layer leaves those spots out (they are already closed that
    way, and a second face there would z-fight)."""
    at = plane if callable(plane) else (lambda _u: plane)
    out = []
    for a, b, c in tris:
        nv = _cross(_sub(pos[b], pos[a]), _sub(pos[c], pos[a]))
        ln = math.sqrt(_dot(nv, nv))
        if ln < 1e-9 or facing * _dot(nv, n) / ln < 0.9:
            continue
        if any(abs(_dot(n, pos[x]) - at(_dot(t, pos[x]))) > COVER_D for x in (a, b, c)):
            continue
        out.append(tuple((_dot(t, pos[x]), pos[x][1]) for x in (a, b, c)))
    return out


def free_runs(cover, u, lo, hi):
    """Parts of [lo, hi] at u that no covering triangle (2D) spans: [(va, vb)]."""
    spans = []
    for tr in cover:
        vs = []
        for k in range(3):
            (u0, v0), (u1, v1) = tr[k], tr[(k + 1) % 3]
            if min(u0, u1) <= u <= max(u0, u1) and u1 != u0:
                vs.append(v0 + (v1 - v0) * (u - u0) / (u1 - u0))
        if len(vs) >= 2 and max(vs) - min(vs) > 1e-4:
            spans.append((min(vs), max(vs)))
    out, v = [], lo
    for a, b in sorted(spans):
        if b <= v:
            continue
        if a > v + MIN_RUN:
            out.append((v, min(a, hi)))
        v = max(v, b)
        if v >= hi:
            break
    if hi > v + MIN_RUN:
        out.append((v, hi))
    return [(a, b) for a, b in out if b > a]


def cap_side(pos, attrs, tris, side, wall_v, every=None):
    """Cap triangles for one open side: [(p, normal, tangent, donor vertex)] x 3 per triangle."""
    a = math.radians(side["angle_deg"])
    n = (math.cos(a), 0.0, math.sin(a))
    t = (-math.sin(a), 0.0, math.cos(a))
    ground = min(p[1] for p in pos)
    ends = side.get("ends")
    if ends:   # this footprint side only: a house can have two open sides facing the same way at
        # different depths (a recessed bay), each closed in its own plane and along its own length
        ue = sorted(e[0] * t[0] + e[1] * t[2] for e in ends)
        d_seg = sum(e[0] * n[0] + e[1] * n[2] for e in ends) / 2
        feet = [_dot(n, p) for p in pos if p[1] <= ground + GROUND_TOUCH
                and abs(_dot(n, p) - d_seg) <= SEG_DEPTH and ue[0] - CORNER <= _dot(t, p) <= ue[1] + CORNER]
        d_out = max(feet) if feet else d_seg
        segs = [sg for sg in section(pos, tris, n, t, d_out - SECTION_IN)
                if ue[0] - CORNER <= (sg[0][0] + sg[1][0]) / 2 <= ue[1] + CORNER]
        span = (ue[0], ue[1])
    else:
        d_out = side_plane(pos, n, ground)
        segs = section(pos, tris, n, t, d_out - SECTION_IN)
        us = [_dot(t, p) for p in pos]
        span = foot_span(pos, n, t, ground, d_out, side.get("length_m"), (min(us) + max(us)) / 2)
    pts = outline(segs, ground, span)
    run = [p for p in pts if p is not None]
    ua0, ub0 = (run[0][0], run[-1][0]) if run else (0.0, 1.0)
    reach = 0.05 if ends else math.inf   # a recessed side's corner meets a wall running further out
    dl, dr = corner_depth(pos, n, t, ground, ua0, d_out, reach), corner_depth(pos, n, t, ground, ub0, d_out, reach)

    def depth(u):   # the cap runs from one corner's wall end to the other's
        f = min(1.0, max(0.0, (u - ua0) / (ub0 - ua0))) if ub0 != ua0 else 0.0
        return dl + (dr - dl) * f
    out, covered = [], 0
    for face, inset in ((1, CAP_IN), (-1, BACK_IN)):
        cpos, ctris = every if (ends and every) else (pos, tris)
        cover = covered_cells(cpos, ctris, n, t, (lambda u, i=inset: depth(u) - i) if ends else d_out, face)
        covered += len(cover)
        out += _layer(pts, cover, face, inset, n, t, depth, wall_v, tris)
    return out, {"plane_m": round(d_out, 3), "corners_m": [round(dl, 3), round(dr, 3)],
                 "samples": sum(1 for p in pts if p is not None),
                 "section_segments": len(segs), "covered_faces": covered}


def _layer(pts, cover, face, inset, n, t, depth, wall_v, tris):
    """One cap layer (face +1 out, -1 in) as columns (at most COLUMN wide) of bands (wall
    lo..mid, roof mid..hi), each band cut into the runs that no face of the house already
    covers; a run's bottom and top follow the outline (k) or are a fixed height (v) where a
    covered spot cuts it."""
    quads = []
    for p, q in zip(pts, pts[1:]):
        if p is None or q is None:
            continue
        k = max(1, int(math.ceil((q[0] - p[0]) / COLUMN)))
        cuts = {p[0] + (q[0] - p[0]) * c / k for c in range(k + 1)}
        # a column also ends where a covering face starts or stops, so no column half-overlaps one
        cuts |= {x[0] for tr in cover for x in tr if p[0] + MIN_RUN < x[0] < q[0] - MIN_RUN}
        cuts = sorted(cuts)
        for ua, ub in zip(cuts, cuts[1:]):
            if ub - ua < 1e-4:
                continue
            uc = (ua + ub) / 2
            near = [tr for tr in cover if min(x[0] for x in tr) <= uc <= max(x[0] for x in tr)]
            for lo_k, hi_k, donor in ((1, 2, wall_v), (2, 3, tris[p[4]][0])):
                lo, hi = _lerp(p, q, uc, lo_k), _lerp(p, q, uc, hi_k)
                if hi - lo < 0.01:
                    continue
                for va, vb in free_runs(near, uc, lo, hi):
                    quads.append((ua, ub, p, q, lo_k, None if va <= lo else va,   # None: follow the line
                                  hi_k, None if vb >= hi else vb, donor))
    out = []
    nn = (n[0] * face, 0.0, n[2] * face)
    tg = (t[0] * face, 0.0, t[2] * face, 1.0)

    def at(u, v):
        s = depth(u) - inset
        return (n[0] * s + t[0] * u, v, n[2] * s + t[2] * u)

    for ua, ub, p, q, lo_k, va, hi_k, vb, donor in quads:
        def bot(u):
            return _lerp(p, q, u, lo_k) if va is None else va

        def top(u):
            return _lerp(p, q, u, hi_k) if vb is None else vb

        quad = (at(ua, bot(ua)), at(ub, bot(ub)), at(ub, top(ub)), at(ua, top(ua)))
        for tri in ((quad[0], quad[1], quad[2]), (quad[0], quad[2], quad[3])):
            cr = _cross(_sub(tri[1], tri[0]), _sub(tri[2], tri[0]))
            if math.sqrt(_dot(cr, cr)) < 1e-6:
                continue
            if _dot(cr, nn) < 0:
                tri = (tri[0], tri[2], tri[1])
            out.append([(v, nn, tg, donor) for v in tri])
    return out


def append_cap(j: dict, binary: bytes, ni: int, m: list, prim: dict, attrs: dict, cap: list) -> bytes:
    """Append the cap as one more primitive of node ni's mesh (vertices in its local space)."""
    inv = _inv_affine(m)
    rot = [inv[0], inv[1], inv[2], inv[4], inv[5], inv[6], inv[8], inv[9], inv[10]]
    verts = [v for tri in cap for v in tri]
    cols = {"POSITION": [], "NORMAL": [], "TANGENT": []}
    extra = [k for k in prim["attributes"] if k not in cols]
    for k in extra:
        cols[k] = []
    for p, nn, tg, donor in verts:
        cols["POSITION"].append(_pt(inv, p))
        cols["NORMAL"].append(tuple(sum(rot[r * 3 + c] * nn[c] for c in range(3)) for r in range(3)))
        cols["TANGENT"].append(tuple(sum(rot[r * 3 + c] * tg[c] for c in range(3)) for r in range(3)) + (tg[3],))
        for k in extra:
            cols[k].append(attrs[k][donor])
    binary = bytearray(binary)
    new_attrs = {}
    for k in prim["attributes"]:
        rows = cols[k]
        src = j["accessors"][prim["attributes"][k]]
        c = NCOMP[src["type"]]
        binary += b"\0" * (-len(binary) % 4)
        off = len(binary)
        ct = src["componentType"]
        if src.get("normalized") and ct != FLOAT:
            top = (1 << (8 * CSIZE[ct] - (1 if ct in (5120, 5122) else 0))) - 1
            data = b"".join(struct.pack("<" + CFMT[ct] * c, *(int(round(v * top)) for v in r)) for r in rows)
        else:
            data = b"".join(struct.pack("<" + CFMT[ct] * c, *r) for r in rows)
        binary += data
        j["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": len(data)})
        acc = {"bufferView": len(j["bufferViews"]) - 1, "componentType": ct, "count": len(rows), "type": src["type"]}
        if src.get("normalized"):
            acc["normalized"] = True
        if k == "POSITION":
            acc["min"] = [min(r[i] for r in rows) for i in range(3)]
            acc["max"] = [max(r[i] for r in rows) for i in range(3)]
        j["accessors"].append(acc)
        new_attrs[k] = len(j["accessors"]) - 1
    binary += b"\0" * (-len(binary) % 4)
    off = len(binary)
    data = struct.pack("<%dI" % len(verts), *range(len(verts)))
    binary += data
    j["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": len(data)})
    j["accessors"].append({"bufferView": len(j["bufferViews"]) - 1, "componentType": U32, "count": len(verts), "type": "SCALAR"})
    newp = {"attributes": new_attrs, "indices": len(j["accessors"]) - 1, "mode": 4}
    if "material" in prim:
        newp["material"] = prim["material"]
    j["meshes"][j["nodes"][ni]["mesh"]]["primitives"].append(newp)
    j["buffers"][0]["byteLength"] = len(binary)
    return bytes(binary)


# ------------------------------------------------------------------ variants

def close_file(src: bytes, sides: list):
    j, binary = parse_glb(src)
    pos, attrs, tris, ni, m, prim = load_house(j, binary)
    colours = attrs.get("COLOR_0") or [(1.0, 1.0, 1.0, 1.0)] * len(pos)
    wall_v = area_mode(pos, colours, tris,
                        lambda nv, c: abs(nv[1]) < 0.2 and WALL_COLOUR_BAND[0] < c[1] < WALL_COLOUR_BAND[1])
    if wall_v is None:
        wall_v = tris[0][0]
    cap, info = [], []
    every = all_faces(j, binary)
    for side in sides:
        c, i = cap_side(pos, attrs, tris, side, wall_v, every)
        cap += c
        info.append(dict(i, faces=side["faces"], length_m=side["length_m"], cap_triangles=len(c)))
    binary = append_cap(j, binary, ni, m, prim, attrs, cap)
    from seal_trim_edges import seal   # it imports this module's glb helpers
    out, _sealed = seal(write_glb(j, binary))   # the cap's own edges, if any are left open
    return out, info


def closed_name(file: str) -> str:
    stem = file.rsplit(".", 1)[0]
    return stem + "_closed.glb"


def build() -> int:
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = []
    for r in src["models"]:
        if not r.get("open_sides"):
            continue
        b = (HERE / r["file"]).read_bytes()
        if hashlib.sha256(b).hexdigest() != r["sha256"]:
            print("ERROR %s: differs from sources/city_buildings.json (rerun import_city_buildings.py)" % r["file"])
            return 1
        out, info = close_file(b, r["open_sides"])
        fname = closed_name(r["file"])
        (HERE / fname).write_bytes(out)
        m = measure(out)
        where = " and ".join("%s side (%g m)" % (s["faces"], s["length_m"]) for s in r["open_sides"])
        desc = r["description"].split(" Open on ")[0]
        row = dict(r)
        row.update({
            "file": fname, "name": r["name"] + " (closed)",
            "description": desc + " Closed variant: the %s it shared with a neighbour is walled up in its "
                           "wall colour and the roof ends there are capped, so it stands alone." % where,
            "synonyms": list(r.get("synonyms", [])) + ["free-standing house", "detached house"],
            "open_sides": [],
            "closed_from": {"file": r["file"], "sha256": r["sha256"], "sides": info},
            "sha256": hashlib.sha256(out).hexdigest(), "bytes": len(out),
            "triangles": m["triangles"], "size": m["size"],
            "cite": r["cite"] + "; closed by kit/catalog/assets/close_open_sides.py",
        })
        rows.append(row)
        print("closed %s -> %s: +%d triangles (%d total), %s" % (
            r["file"], fname, sum(i["cap_triangles"] for i in info), m["triangles"],
            ", ".join("%s plane %.2f m, %d samples" % (i["faces"], i["plane_m"], i["samples"]) for i in info)))
    CLOSED.write_text(json.dumps({
        "format": "iamar-catalog-city-models", "version": 1,
        "note": "Closed variants of the open-sided houses in sources/city_buildings.json, written by "
                "kit/catalog/assets/close_open_sides.py (party-wall side walled up, roof ends capped). "
                "Never edit by hand: rerun the script.",
        "licence": src.get("licence"), "models": rows}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("wrote %d closed variants to %s" % (len(rows), CLOSED.relative_to(CATALOG_DIR.parent.parent).as_posix()))
    return 0


def check() -> int:
    errs = []
    src = {r["file"]: r for r in json.loads(SOURCE.read_text(encoding="utf-8"))["models"]}
    closed = json.loads(CLOSED.read_text(encoding="utf-8"))["models"] if CLOSED.is_file() else []
    have = {r["closed_from"]["file"] for r in closed}
    for f, r in src.items():
        if r.get("open_sides") and f not in have:
            errs.append("%s has an open side and no closed variant (run close_open_sides.py)" % f)
    for r in closed:
        p = HERE / r["file"]
        parent = src.get(r["closed_from"]["file"])
        if parent is None or parent["sha256"] != r["closed_from"]["sha256"]:
            errs.append("%s: made from an older %s (rerun close_open_sides.py)" % (r["file"], r["closed_from"]["file"]))
        if not p.is_file():
            errs.append("%s: file missing" % r["file"])
        elif hashlib.sha256(p.read_bytes()).hexdigest() != r["sha256"]:
            errs.append("%s: sha256 differs from city_buildings_closed.json (rerun close_open_sides.py)" % r["file"])
    for e in errs:
        print("CHECK " + e)
    print("closed variants: %d records, %s" % (len(closed), "OK" if not errs else "%d problems" % len(errs)))
    return 1 if errs else 0


def main(argv: list) -> int:
    if argv[:1] == ["--check"]:
        return check()
    if argv:
        print(__doc__)
        return 2
    return build()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
