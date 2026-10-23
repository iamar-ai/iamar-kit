"""Convex-wing envelope roofs: a port of the iamar browser source (not public) scripts/world/masterplan/mp_roof.gd (A20).

A hip fan from one centre only roofs what that centre can see, so an L-, T- or U-shaped
footprint lost parts of its roof (the maintainer 2026-10-09: "when I fly, I want to be able to see
the roofs rather than mesh openings"). Here the footprint is cut at every real re-entrant
corner into convex WINGS, each wing is extended back across its cuts as far as its own wall
lines allow (an L is two overlapping rectangles), every wing gets a hipped roof of one
uniform slope, and the roof is the UPPER ENVELOPE of the wings: continuous and closed by
construction, valleys where wings meet. Every (wing, edge) plane is meshed exactly where it is
the lowest plane of its wing and no other wing stands higher (half-plane clipping; identical
planes from one wall line are emitted once). Ridges and hips get caps, valleys do not.

A convex footprint is one wing: a plain hipped roof with its ridge along the long axis.

Kept from the city, with the bugs they fixed (see the comments in mp_roof.gd):
* planes of wing edges on one wall line are taken from that ORIGINAL edge, so every wing holds
  a bit-identical plane (B095 lost 0.25 m^2 of roof to 2e-4 noise);
* SAME_G / SAME_H tolerances gate the half-plane builders (B133's 0.5 m^2 strip);
* the FIRST identical plane of another wing owns the shared face (C6 audit 4c111f77);
* faces are convex and triangulated as fans (triangulation of near-duplicate corners failed);
* creases on one line merge before capping, and caps stop short of junctions (C6 c307f752).
"""
from __future__ import annotations

import math

from meshkit import Mesh, UP

SPLIT_TURN = 8.0
SPLIT_MIN_EDGE = 0.25
CONVEX_TURN = 1.0
MAX_SLOPE = 2.0
MIN_AREA = 0.0025
MIN_EDGE = 0.04
CAP_W = 0.17
CAP_H = 0.09
SAME_G = 1e-4
SAME_H = 1e-3


# ------------------------------------------------------------------ 2D helpers

def d2(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def area(poly):
    s = 0.0
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        s += a[0] * b[1] - b[0] * a[1]
    return s * 0.5


def centroid(poly):
    a = area(poly)
    if abs(a) < 1e-9:
        return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    cx = cy = 0.0
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        f = p[0] * q[1] - q[0] * p[1]
        cx += (p[0] + q[0]) * f
        cy += (p[1] + q[1]) * f
    return (cx / (6 * a), cy / (6 * a))


def outward(poly, e):
    a, b = poly[e], poly[(e + 1) % len(poly)]
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy)
    if ln < 1e-5:
        return (0.0, 0.0)
    dx, dy = dx / ln, dy / ln
    return (dy, -dx) if area(poly) > 0 else (-dy, dx)


def point_in(p, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < x:
                inside = not inside
    return inside


def closest_on_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return (a[0] + dx * t, a[1] + dy * t)


def boundary_distance(p, poly):
    return min(d2(p, closest_on_segment(p, poly[e], poly[(e + 1) % len(poly)])) for e in range(len(poly)))


def dedupe(poly):
    out = []
    for q in poly:
        if not out or d2(out[-1], q) > 0.02:
            out.append(q)
    while len(out) > 1 and d2(out[0], out[-1]) <= 0.02:
        out.pop()
    return out


def clean(poly):
    d = dedupe(poly)
    out = []
    n = len(d)
    for i in range(n):
        p0, p1, p2 = d[(i - 1) % n], d[i], d[(i + 1) % n]
        u = _unit((p1[0] - p0[0], p1[1] - p0[1]))
        v = _unit((p2[0] - p1[0], p2[1] - p1[1]))
        turn = u[0] * v[1] - u[1] * v[0]
        if abs(turn) < math.sin(math.radians(0.5)) and u[0] * v[0] + u[1] * v[1] > 0:
            continue
        out.append(p1)
    return out if len(out) >= 3 else d


def _unit(v):
    ln = math.hypot(v[0], v[1])
    return (0.0, 0.0) if ln < 1e-12 else (v[0] / ln, v[1] / ln)


def is_convex(poly, tol):
    n = len(poly)
    if n < 3:
        return False
    orient = 1.0 if area(poly) > 0 else -1.0
    for i in range(n):
        p0, p1, p2 = poly[(i - 1) % n], poly[i], poly[(i + 1) % n]
        if d2(p0, p1) < 1e-4 or d2(p1, p2) < 1e-4:
            continue
        u = _unit((p1[0] - p0[0], p1[1] - p0[1]))
        v = _unit((p2[0] - p1[0], p2[1] - p1[1]))
        if (u[0] * v[1] - u[1] * v[0]) * orient < -math.sin(math.radians(tol)):
            return False
    return True


def clip_half(poly, n, c):
    """Convex polygon clipped to {n . p <= c} (Sutherland-Hodgman, one plane)."""
    out = []
    m = len(poly)
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        da = n[0] * a[0] + n[1] * a[1] - c
        db = n[0] * b[0] + n[1] * b[1] - c
        if da <= 0:
            out.append(a)
        if (da < 0 < db) or (db < 0 < da):
            t = da / (da - db)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


# A half-plane is (n, c) meaning n . p <= c; "ALL" keeps everything, None drops everything.
ALL = "all"


def clip_each(pieces, half):
    if half is None:
        return []
    if half == ALL:
        return pieces
    n, c = half
    out = []
    for piece in pieces:
        r = clip_half(piece, n, c)
        if len(r) >= 3 and abs(area(r)) >= MIN_AREA:
            out.append(r)
    return out


def subtract_convex(pieces, region):
    """pieces minus a convex region, as strips by the region's edges (mp_roof._subtract_convex)."""
    out = []
    for piece in pieces:
        touch = 0.0
        x = piece
        for e in range(len(region)):
            a = region[e]
            if d2(a, region[(e + 1) % len(region)]) < MIN_EDGE:
                continue
            o = outward(region, e)
            x = clip_half(x, o, o[0] * a[0] + o[1] * a[1])
            if len(x) < 3:
                break
        if len(x) >= 3:
            touch = abs(area(x))
        if touch < MIN_AREA:
            out.append(piece)
            continue
        inner = []
        for e in range(len(region)):
            a, b = region[e], region[(e + 1) % len(region)]
            if d2(a, b) < MIN_EDGE:
                continue
            o = outward(region, e)
            if o[0] * o[0] + o[1] * o[1] < 0.5:
                continue
            part = clip_each([piece], ((-o[0], -o[1]), -(o[0] * a[0] + o[1] * a[1])))
            for h in inner:
                part = clip_each(part, h)
            out.extend(part)
            inner.append(((o[0], o[1]), o[0] * a[0] + o[1] * a[1]))
    return out


# ------------------------------------------------------------------ wings

def wings(polygon):
    """Convex wings covering polygon: [{poly, centre, inradius, src}]. A convex footprint is one wing."""
    poly = clean(polygon)
    if is_convex(poly, CONVEX_TURN):
        return [_wing(poly, poly)]
    pieces = _split_reflex(poly, 0)
    for p in pieces:
        if not is_convex(p, CONVEX_TURN):
            raise ValueError("footprint piece is not convex after the re-entrant cuts: %s" % (p,))
    out = []
    for piece in pieces:
        w = _extend(poly, pieces, piece)
        out.append(_wing(w, poly))
    if not _covers(out, poly):
        out = [_wing(p, poly) for p in pieces]
    return out


def _wing(poly, polygon):
    c, r = _chebyshev(poly)
    return {"poly": poly, "centre": c, "inradius": r, "src": _edge_sources(poly, polygon)}


def _split_reflex(poly, depth):
    n = len(poly)
    if n < 4 or depth >= 24:
        return [poly]
    orient = 1.0 if area(poly) > 0 else -1.0
    v, worst = -1, -math.sin(math.radians(SPLIT_TURN))
    for i in range(n):
        p0, p1, p2 = poly[(i - 1) % n], poly[i], poly[(i + 1) % n]
        if d2(p0, p1) < SPLIT_MIN_EDGE or d2(p1, p2) < SPLIT_MIN_EDGE:
            continue
        u = _unit((p1[0] - p0[0], p1[1] - p0[1]))
        w = _unit((p2[0] - p1[0], p2[1] - p1[1]))
        turn = (u[0] * w[1] - u[1] * w[0]) * orient
        if turn < worst:
            worst, v = turn, i
    if v < 0:
        return [poly]
    best, best_score = [], -1.0
    for q in (poly[(v - 1) % n], poly[(v + 1) % n]):
        dirv = _unit((poly[v][0] - q[0], poly[v][1] - q[1]))
        hit = _split_hit(poly, v, dirv)
        if hit is None:
            continue
        halves = _split_at(poly, v, hit[0], hit[1])
        if len(halves) != 2:
            continue
        score = min(abs(area(halves[0])), abs(area(halves[1])))
        if score > best_score:
            best_score, best = score, halves
    if not best:
        return [poly]
    out = []
    for h in best:
        out.extend(_split_reflex(h, depth + 1))
    return out


def _seg_hit(p, p2, a, b):
    r = (p2[0] - p[0], p2[1] - p[1])
    s = (b[0] - a[0], b[1] - a[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-12:
        return None
    t = ((a[0] - p[0]) * s[1] - (a[1] - p[1]) * s[0]) / den
    u = ((a[0] - p[0]) * r[1] - (a[1] - p[1]) * r[0]) / den
    if 0 <= t <= 1 and 0 <= u <= 1:
        return (p[0] + r[0] * t, p[1] + r[1] * t)
    return None


def _split_hit(poly, v, dirv):
    n = len(poly)
    frm = (poly[v][0] + dirv[0] * 0.02, poly[v][1] + dirv[1] * 0.02)
    to = (poly[v][0] + dirv[0] * 400, poly[v][1] + dirv[1] * 400)
    best, best_d = None, math.inf
    for e in range(n):
        if e == v or e == (v - 1) % n:
            continue
        h = _seg_hit(frm, to, poly[e], poly[(e + 1) % n])
        if h is not None:
            dd = d2(h, poly[v])
            if 0.3 < dd < best_d:
                best_d, best = dd, (e, h)
    return best


def _split_at(poly, v, e, p):
    n = len(poly)
    a, i = [], v
    while True:
        a.append(poly[i])
        if i == e:
            break
        i = (i + 1) % n
    a.append(p)
    b, i = [p], (e + 1) % n
    while True:
        b.append(poly[i])
        if i == v:
            break
        i = (i + 1) % n
    out = []
    for half in (a, b):
        c = dedupe(half)
        if len(c) >= 3 and abs(area(c)) > 0.05:
            out.append(c)
    return out


def _extend(polygon, pieces, piece):
    """The piece grown back across its cuts: the footprint inside the inner half-planes of the
    piece's own wall lines. The footprint is the union of the convex pieces, so each is clipped
    and the result is accepted when it is one convex polygon (else the piece stays as it is)."""
    src = _edge_sources(piece, polygon)
    halves = []
    for e in range(len(piece)):
        if src[e] < 0:
            continue
        a = piece[e]
        o = outward(piece, e)
        if o[0] * o[0] + o[1] * o[1] < 0.5:
            continue
        halves.append((o, o[0] * a[0] + o[1] * a[1]))
    parts = []
    for p in pieces:
        r = [p]
        for h in halves:
            r = clip_each(r, h)
        parts.extend(r)
    pts = [q for p in parts for q in p]
    hull = _hull(pts)
    if len(hull) < 3:
        return piece
    total = sum(abs(area(p)) for p in parts)
    if abs(abs(area(hull)) - total) > 0.01 * total + 0.02:
        return piece   # the union is not convex (or not connected)
    if area(hull) * area(piece) < 0:
        hull = hull[::-1]
    return dedupe(hull)


def _hull(pts):
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in pts))
    if len(pts) < 3:
        return pts
    cr = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 1e-9:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cr(hi[-2], hi[-1], p) <= 1e-9:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _covers(ws, polygon):
    xs = [p[0] for p in polygon]
    zs = [p[1] for p in polygon]
    x = min(xs) + 0.1137
    while x < max(xs):
        z = min(zs) + 0.1071
        while z < max(zs):
            p = (x, z)
            if point_in(p, polygon) and boundary_distance(p, polygon) > 0.05:
                if not any(point_in(p, w["poly"]) for w in ws):
                    return False
            z += 0.2
        x += 0.2
    return True


def _edge_sources(poly, polygon):
    out = []
    n = len(polygon)
    for e in range(len(poly)):
        a, b = poly[e], poly[(e + 1) % len(poly)]
        found = -1
        for f in range(n):
            fa, fb = polygon[f], polygon[(f + 1) % n]
            if d2(fa, fb) < MIN_EDGE:
                continue
            if d2(closest_on_segment(a, fa, fb), a) < 0.02 and d2(closest_on_segment(b, fa, fb), b) < 0.02:
                found = f
                break
        out.append(found)
    return out


def _depth(poly, p):
    d = math.inf
    for e in range(len(poly)):
        a = poly[e]
        if d2(a, poly[(e + 1) % len(poly)]) < MIN_EDGE:
            continue
        o = outward(poly, e)
        d = min(d, -((p[0] - a[0]) * o[0] + (p[1] - a[1]) * o[1]))
    return d


def _chebyshev(poly):
    xs = [p[0] for p in poly]
    zs = [p[1] for p in poly]
    cen = centroid(poly)
    best, best_r = cen, _depth(poly, cen)
    for step, lo, hi in ((0.25, (min(xs), min(zs)), (max(xs), max(zs))), (0.05, None, None)):
        if lo is None:
            lo, hi = (best[0] - 0.3, best[1] - 0.3), (best[0] + 0.3, best[1] + 0.3)
        x = lo[0]
        while x <= hi[0] + 1e-9:
            z = lo[1]
            while z <= hi[1] + 1e-9:
                p = (x, z)
                r = _depth(poly, p)
                if r > best_r + 1e-4 or (abs(r - best_r) <= 1e-4 and d2(p, cen) < d2(best, cen)):
                    best_r, best = r, p
                z += step
            x += step
    return best, best_r


# ------------------------------------------------------------------ the envelope

def slope(ws, eaves, ridge):
    r = max(w["inradius"] for w in ws)
    return min(MAX_SLOPE, (ridge - eaves) / max(r, 0.5))


def planes(ws, eaves, k, polygon):
    lines = []
    for e in range(len(polygon)):
        a, b = polygon[e], polygon[(e + 1) % len(polygon)]
        if d2(a, b) < MIN_EDGE:
            continue
        o = outward(polygon, e)
        if o[0] * o[0] + o[1] * o[1] > 0.5:
            lines.append((a, _unit((b[0] - a[0], b[1] - a[1])), o))
    out = []
    for wi, w in enumerate(ws):
        poly = w["poly"]
        for e in range(len(poly)):
            a, b = poly[e], poly[(e + 1) % len(poly)]
            if d2(a, b) < MIN_EDGE:
                continue
            o = outward(poly, e)
            if o[0] * o[0] + o[1] * o[1] < 0.5:
                continue
            dd = _unit((b[0] - a[0], b[1] - a[1]))
            for la, ld, lo in lines:
                if abs(dd[0] * ld[1] - dd[1] * ld[0]) > 2e-3:
                    continue
                cr = lambda q: abs((q[0] - la[0]) * ld[1] - (q[1] - la[1]) * ld[0])
                if cr(a) > 2e-3 or cr(b) > 2e-3:
                    continue
                if lo[0] * o[0] + lo[1] * o[1] < 0:
                    continue
                a, o = la, lo
                break
            g = (-o[0] * k, -o[1] * k)
            out.append({"w": wi, "e": e, "g": g, "h": eaves - (g[0] * a[0] + g[1] * a[1])})
    return out


def plane_y(pl, p):
    return pl["g"][0] * p[0] + pl["g"][1] * p[1] + pl["h"]


def roof_y(p, ws, pls, eaves):
    best = eaves
    for wi, w in enumerate(ws):
        if not point_in(p, w["poly"]):
            continue
        h = min((plane_y(pl, p) for pl in pls if pl["w"] == wi), default=math.inf)
        if h < math.inf:
            best = max(best, h)
    return best


def _same(p, q):
    return math.hypot(p["g"][0] - q["g"][0], p["g"][1] - q["g"][1]) < SAME_G and abs(p["h"] - q["h"]) < SAME_H


def _half(n, c):
    return ((n[0], n[1]), c)


def half_le(p, q, p_first):
    n = (p["g"][0] - q["g"][0], p["g"][1] - q["g"][1])
    c = q["h"] - p["h"]
    if math.hypot(*n) < SAME_G:
        if abs(c) < SAME_H:
            return ALL if p_first else None
        return ALL if c > 0 else None
    return _half(n, c)


def half_lt(p, q):
    n = (p["g"][0] - q["g"][0], p["g"][1] - q["g"][1])
    c = q["h"] - p["h"]
    if math.hypot(*n) < SAME_G:
        return ALL if c > SAME_H else None
    return _half(n, c)


def _seg_key(a, b):
    ka = "%.2f,%.2f" % a
    kb = "%.2f,%.2f" % b
    return ka + "|" + kb if ka < kb else kb + "|" + ka


class Roof:
    """The envelope of `polygon` (wings computed here) at `eaves` with slope k (rise per metre)."""

    def __init__(self, polygon, eaves, k=None, ridge=None):
        self.polygon = clean(polygon)
        self.wings = wings(self.polygon)
        self.eaves = eaves
        if k is None:
            k = slope(self.wings, eaves, ridge)
        self.k = min(MAX_SLOPE, k)
        self.planes = planes(self.wings, eaves, self.k, self.polygon)
        self.ridge = max(roof_y(w["centre"], self.wings, self.planes, eaves) for w in self.wings)

    def y(self, p):
        return roof_y(p, self.wings, self.planes, self.eaves)

    def faces(self):
        """[(plane, convex face)] of the envelope."""
        ws, pls = self.wings, self.planes
        out = []
        for i, pl in enumerate(pls):
            faces = [ws[pl["w"]]["poly"]]
            for j, q in enumerate(pls):
                if j == i or q["w"] != pl["w"]:
                    continue
                faces = clip_each(faces, half_le(pl, q, i < j))
                if not faces:
                    break
            for vi in range(len(ws)):
                if not faces:
                    break
                if vi == pl["w"]:
                    continue
                twin = next((j for j, q in enumerate(pls) if q["w"] == vi and _same(pl, q)), -1)
                region = [ws[vi]["poly"]]
                if twin >= 0:
                    if i < twin:
                        continue
                    for j, q in enumerate(pls):
                        if q["w"] == vi and j != twin:
                            region = clip_each(region, half_le(pls[twin], q, twin < j))
                else:
                    for j, q in enumerate(pls):
                        if q["w"] == vi:
                            region = clip_each(region, half_lt(pl, q))
                for r in region:
                    faces = subtract_convex(faces, r)
            for f in faces:
                f = dedupe(f)
                if len(f) >= 3 and abs(area(f)) >= MIN_AREA:
                    out.append((pl, f))
        return out

    def build(self, mesh: Mesh, roof_mat, cap_mat=None):
        """Emits the roof faces and (cap_mat) the ridge and hip caps. Returns the crease segments."""
        creases = {}
        for pl, f in self.faces():
            for t in range(1, len(f) - 1):
                p0, p1, p2 = f[0], f[t], f[t + 1]
                mesh.tri(roof_mat, (p0[0], plane_y(pl, p0), p0[1]), (p1[0], plane_y(pl, p1), p1[1]),
                         (p2[0], plane_y(pl, p2), p2[1]), UP)
            fc = centroid(f)
            for e in range(len(f)):
                a, b = f[e], f[(e + 1) % len(f)]
                if d2(a, b) < 0.15:
                    continue
                m = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)
                if boundary_distance(m, self.polygon) < 0.03:
                    continue
                if pl["g"][0] * (m[0] - fc[0]) + pl["g"][1] * (m[1] - fc[1]) <= 0:
                    continue   # a valley
                u = _unit((m[0] - fc[0], m[1] - fc[1]))
                away = (m[0] + u[0] * 0.15, m[1] + u[1] * 0.15)
                if abs(self.y(away) - plane_y(pl, away)) < 2e-3:
                    continue   # a seam between two faces of one plane
                if self.y(away) > plane_y(pl, m) - 0.01:
                    continue   # a kink, not a ridge
                creases.setdefault(_seg_key(a, b), [a, b])
        merged = []
        for a, b in creases.values():
            dd = _unit((b[0] - a[0], b[1] - a[1]))
            joined = False
            for seg in merged:
                sa, sb = seg
                sd = _unit((sb[0] - sa[0], sb[1] - sa[1]))
                if abs(dd[0] * sd[0] + dd[1] * sd[1]) < 0.9998:
                    continue
                off = (a[0] - sa[0], a[1] - sa[1])
                if abs(off[0] * sd[1] - off[1] * sd[0]) > 0.03:
                    continue
                t0 = (a[0] - sa[0]) * sd[0] + (a[1] - sa[1]) * sd[1]
                t1 = (b[0] - sa[0]) * sd[0] + (b[1] - sa[1]) * sd[1]
                lo, hi = min(t0, t1), max(t0, t1)
                ln = d2(sa, sb)
                if hi < -0.05 or lo > ln + 0.05:
                    continue
                nlo, nhi = min(0.0, lo), max(ln, hi)
                seg[0] = (sa[0] + sd[0] * nlo, sa[1] + sd[1] * nlo)
                seg[1] = (sa[0] + sd[0] * nhi, sa[1] + sd[1] * nhi)
                joined = True
                break
            if not joined:
                merged.append([a, b])
        if cap_mat:
            for seg in merged:
                a, b = seg
                dd = _unit((b[0] - a[0], b[1] - a[1]))
                ln = d2(a, b)
                cut_a = any(d2(q, a) < 0.05 for o in merged if o is not seg for q in o)
                cut_b = any(d2(q, b) < 0.05 for o in merged if o is not seg for q in o)
                t0 = CAP_W * 1.2 if cut_a else 0.0
                t1 = ln - (CAP_W * 1.2 if cut_b else 0.0)
                # a hip reaching the eaves: stop where both feet are still on the roof (past the
                # outline a foot hung over the eave skirt and left a slit under the cap)
                if boundary_distance(a, self.polygon) < 0.05:
                    t0 = max(t0, CAP_W * 2.0)
                if boundary_distance(b, self.polygon) < 0.05:
                    t1 = min(t1, ln - CAP_W * 2.0)
                if t1 - t0 < 0.2:
                    continue
                self._cap(mesh, (a[0] + dd[0] * t0, a[1] + dd[1] * t0), (a[0] + dd[0] * t1, a[1] + dd[1] * t1), cap_mat)
        return merged

    def _cap(self, mesh, a, b, mat):
        al = _unit((b[0] - a[0], b[1] - a[1]))
        perp = (-al[1], al[0])
        s = (a[0] + al[0] * 0.04, a[1] + al[1] * 0.04)
        e = (b[0] - al[0] * 0.04, b[1] - al[1] * 0.04)
        lift = 0.02

        def top(q):
            return (q[0], self.y(q) + CAP_H + lift, q[1])

        def low(q, side):
            r = (q[0] + perp[0] * CAP_W * side, q[1] + perp[1] * CAP_W * side)
            # the foot 2 cm into the roof: 2 cm above it left a slit a grazing flyer saw through
            return (r[0], min(self.y(r) - lift, self.y(q) + CAP_H + lift - 0.02), r[1])

        # split the strip where the roof under it bends (a ridge running into a higher wing):
        # a straight foot over a kink stood clear of the roof (C6 / A20: the strip twists there)
        def bent(q0, q1):
            qm = ((q0[0] + q1[0]) * 0.5, (q0[1] + q1[1]) * 0.5)
            for f in (lambda q: top(q)[1], lambda q: low(q, -1)[1], lambda q: low(q, 1)[1]):
                if abs(f(qm) - (f(q0) + f(q1)) * 0.5) > 0.008:
                    return True
            return False

        pts = [s, e]
        for _ in range(5):
            out = [pts[0]]
            changed = False
            for q0, q1 in zip(pts, pts[1:]):
                if d2(q0, q1) > 0.12 and bent(q0, q1):
                    out.append(((q0[0] + q1[0]) * 0.5, (q0[1] + q1[1]) * 0.5))
                    changed = True
                out.append(q1)
            pts = out
            if not changed:
                break
        for q0, q1 in zip(pts, pts[1:]):
            t0, t1 = top(q0), top(q1)
            for side in (-1.0, 1.0):
                out = (perp[0] * side, 1.0, perp[1] * side)
                l0, l1 = low(q0, side), low(q1, side)
                mesh.tri(mat, l0, l1, t1, out)
                mesh.tri(mat, l0, t1, t0, out)
        mesh.tri(mat, low(s, -1), low(s, 1), top(s), (-al[0], 0.0, -al[1]))
        mesh.tri(mat, low(e, -1), low(e, 1), top(e), (al[0], 0.0, al[1]))


def eave_skirt(mesh: Mesh, polygon, eaves, k, overhang, flare, fascia, roof_mat, trim_mat, soffit_mat=None):
    """The deep flared eave all round (MpStyle.eave_overhang / eave_drop): a ring standing out
    `overhang` from the walls, its top falling `k * overhang * flare` (flatter than the roof),
    a fascia `fascia` deep and a soffit back to the wall. Its inner top edge is the envelope's
    outline at the eaves and its soffit meets the wall face, so the ring is closed."""
    poly = clean(polygon)
    n = len(poly)
    drop = k * overhang * flare
    off = []
    for v in range(n):
        n1, n2 = outward(poly, (v - 1) % n), outward(poly, v)
        dt = n1[0] * n2[0] + n1[1] * n2[1]
        kk = ((n1[0] + n2[0]) / (1 + dt), (n1[1] + n2[1]) / (1 + dt))
        off.append((poly[v][0] + kk[0] * overhang, poly[v][1] + kk[1] * overhang))
    y1 = eaves - drop
    y2 = y1 - fascia
    for e in range(n):
        f = (e + 1) % n
        a, b, ao, bo = poly[e], poly[f], off[e], off[f]
        o = outward(poly, e)
        tn = (o[0] * drop, overhang, o[1] * drop)
        mesh.quad(roof_mat, (a[0], eaves, a[1]), (b[0], eaves, b[1]), (bo[0], y1, bo[1]), (ao[0], y1, ao[1]), tn)
        mesh.quad(trim_mat, (ao[0], y1, ao[1]), (bo[0], y1, bo[1]), (bo[0], y2, bo[1]), (ao[0], y2, ao[1]), (o[0], 0, o[1]))
        mesh.quad(soffit_mat or trim_mat, (a[0], y2, a[1]), (b[0], y2, b[1]), (bo[0], y2, bo[1]), (ao[0], y2, ao[1]), (0, -1, 0))
    return y2
