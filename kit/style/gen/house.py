"""The masterplan house: walls by storey, a dressed-stone (or limewash) ground storey, quoins
and timber corner posts, a jettied front on carved brackets, an oriel, a round corner tower,
a door under a round stone arch, windows with shutters, a timber frame on the upper storeys
(frame.py), and the convex-wing envelope roof with ridge caps and deep flared eaves.

Ported read-only from the iamar browser source (not public) scripts/world/masterplan/mp_buildings.gd (_emit_oriel,
jetty, storeys) and mp_style.gd (dress_corners, quoins, corner_post, jetty_brackets, bracket,
corner_tower, door_arch, eave_overhang). The city reads plan data (lanes, neighbours, the
facade layout); a kit house reads only its footprint, its storeys and a style profile, and
every choice is deterministic per seed.

Visibility rule as in the city: no face is emitted against a wall, a roof or the piece beside
it, everything else is closed, so `iamar-world audit closure` passes on the output.
"""
from __future__ import annotations

import math

from meshkit import Mesh, UP, DOWN, add, mul, sub, norm, basis_facing, at_basis
import arch as archmod
import frame as framemod
import roof as roofmod

# MpStyle constants (mp_style.gd)
QUOIN_H, QUOIN_LONG, QUOIN_SHORT, QUOIN_D = 0.36, 0.66, 0.36, 0.05
POST_ARM, POST_D = 0.24, 0.09
BRACKET_STEP, BRACKET_DROP, BRACKET_W = 1.45, 0.85, 0.16
EAVE_FLARE, FASCIA = 0.55, 0.15
TOWER_SIDES, TOWER_INSET = 12, 0.35
FRAME_PROUD = 0.15   # window frame front off the wall (kit: over the flat-wall audit's 5 cm relief)
# glass off the wall, 4 cm back in the frame (an internal task); 11 cm so the flat-wall audit sees it as
# relief against both the wall and the 5 cm corner posts it may start a run on
GLASS_Z = 0.11
BAR_W, BAR_D = 0.045, 0.035  # glazing bars: width, depth in front of the glass (zfight: 3 cm)

PRESETS = {
    # footprints in metres, counter-clockwise in (x, z); the front (door) is edge 0, facing -z
    "rect": [(-4.5, -3.0), (4.5, -3.0), (4.5, 3.0), (-4.5, 3.0)],
    "narrow": [(-3.0, -4.5), (3.0, -4.5), (3.0, 4.5), (-3.0, 4.5)],
    "L": [(-5.0, -4.0), (5.0, -4.0), (5.0, 1.0), (0.0, 1.0), (0.0, 6.0), (-5.0, 6.0)],
    "T": [(-6.0, -3.0), (6.0, -3.0), (6.0, 2.0), (2.0, 2.0), (2.0, 7.0), (-2.0, 7.0), (-2.0, 2.0), (-6.0, 2.0)],
    "U": [(-6.0, -4.0), (6.0, -4.0), (6.0, 6.0), (2.5, 6.0), (2.5, 0.5), (-2.5, 0.5), (-2.5, 6.0), (-6.0, 6.0)],
}


def footprint(spec):
    """A preset name, 'WxD' (a rectangle) or a list of [x, z] points."""
    if isinstance(spec, list):
        poly = [(float(p[0]), float(p[1])) for p in spec]
    elif spec in PRESETS:
        poly = list(PRESETS[spec])
    elif isinstance(spec, str) and "x" in spec:
        w, d = (float(t) for t in spec.lower().split("x"))
        poly = [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]
    else:
        raise ValueError("footprint must be a preset (%s), WxD or a point list" % ", ".join(PRESETS))
    poly = roofmod.clean(poly)
    if roofmod.area(poly) < 0:
        poly = poly[::-1]
    return poly


def p3(q, y):
    return (q[0], y, q[1])


def lerp2(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def line_hit(a, d, b, e):
    """Intersection of line a + t d with line b + s e (2D)."""
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((b[0] - a[0]) * e[1] - (b[1] - a[1]) * e[0]) / den
    return (a[0] + d[0] * t, a[1] + d[1] * t)


# ------------------------------------------------------------------ corners (MpStyle)

def corner(poly, v):
    n = len(poly)
    p, q1, q2 = poly[v], poly[(v - 1) % n], poly[(v + 1) % n]
    if roofmod.d2(p, q1) < 0.2 or roofmod.d2(p, q2) < 0.2:
        return None
    n1, n2 = roofmod.outward(poly, (v - 1) % n), roofmod.outward(poly, v)
    dt = n1[0] * n2[0] + n1[1] * n2[1]
    if dt < -0.5:
        return None
    u = lambda a, b: roofmod._unit((b[0] - a[0], b[1] - a[1]))
    return {"p": p, "d1": u(p, q1), "d2": u(p, q2), "n1": n1, "n2": n2,
            "k": ((n1[0] + n2[0]) / (1 + dt), (n1[1] + n2[1]) / (1 + dt)),
            "len1": roofmod.d2(p, q1), "len2": roofmod.d2(p, q2)}


def convex_at(poly, v):
    n = len(poly)
    a, b, c = poly[(v - 1) % n], poly[v], poly[(v + 1) % n]
    cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
    return cr > 1e-6   # left turn in a counter-clockwise footprint


def _pt(q, s, d):
    return (q[0] + s[0] * d, q[1] + s[1] * d)


def l_sides(m, c, l1, l2, d, y0, y1, mat):
    if y1 - y0 < 0.003:
        return
    p, d1, d2, n1, n2 = c["p"], c["d1"], c["d2"], c["n1"], c["n2"]
    cc = _pt(p, c["k"], d)
    a1, a2 = _pt(p, d1, l1), _pt(p, d2, l2)
    a1o, a2o = _pt(a1, n1, d), _pt(a2, n2, d)
    for qa, qb, nn in ((a1, a1o, d1), (a1o, cc, n1), (cc, a2o, n2), (a2o, a2, d2)):
        if roofmod.d2(qa, qb) >= 0.004:
            m.quad(mat, p3(qa, y0), p3(qb, y0), p3(qb, y1), p3(qa, y1), (nn[0], 0.0, nn[1]))


def l_caps(m, c, l, other, d, y, facing, mat):
    p, d1, d2, n1, n2 = c["p"], c["d1"], c["d2"], c["n1"], c["n2"]
    cc = _pt(p, c["k"], d)
    if other is None:
        a1, a2 = _pt(p, d1, l[0]), _pt(p, d2, l[1])
        m.quad(mat, p3(p, y), p3(a1, y), p3(_pt(a1, n1, d), y), p3(cc, y), facing)
        m.quad(mat, p3(p, y), p3(cc, y), p3(_pt(a2, n2, d), y), p3(a2, y), facing)
        return
    if l[0] > other[0] + 0.01:
        s, e = _pt(p, d1, other[0]), _pt(p, d1, l[0])
        m.quad(mat, p3(s, y), p3(e, y), p3(_pt(e, n1, d), y), p3(_pt(s, n1, d), y), facing)
    if l[1] > other[1] + 0.01:
        s, e = _pt(p, d2, other[1]), _pt(p, d2, l[1])
        m.quad(mat, p3(s, y), p3(e, y), p3(_pt(e, n2, d), y), p3(_pt(s, n2, d), y), facing)


def quoins(m, c, y0, y1, mat, seed):
    courses = max(1, int(round((y1 - y0) / QUOIN_H)))
    h = (y1 - y0) / courses
    lim1, lim2 = c["len1"] * 0.4, c["len2"] * 0.4
    start = abs(seed) % 2

    def arms(i):
        lf = (i + start) % 2 == 0
        return (min(QUOIN_LONG if lf else QUOIN_SHORT, lim1), min(QUOIN_SHORT if lf else QUOIN_LONG, lim2))

    for i in range(courses):
        ya, yb = y0 + h * i, y0 + h * (i + 1)
        l = arms(i)
        l_sides(m, c, l[0], l[1], QUOIN_D, ya, yb, mat)
        l_caps(m, c, l, arms(i + 1) if i < courses - 1 else None, QUOIN_D, yb, UP, mat)
        if i > 0:
            l_caps(m, c, l, arms(i - 1), QUOIN_D, ya, DOWN, mat)
        elif y0 > 0.05:   # standing on the ground: no underside
            l_caps(m, c, l, None, QUOIN_D, ya, DOWN, mat)
    return max(QUOIN_LONG, QUOIN_SHORT)


def corner_post(m, c, y0, y1, mat):
    l = (min(POST_ARM, c["len1"] * 0.3), min(POST_ARM, c["len2"] * 0.3))
    l_sides(m, c, l[0], l[1], POST_D, y0, y1, mat)
    l_caps(m, c, l, None, POST_D, y1, UP, mat)
    l_caps(m, c, l, None, POST_D, y0, DOWN, mat)


# ------------------------------------------------------------------ jetty brackets

def bracket(m, base, d, out, top_y, reach, drop, mat):
    steps = 5
    prof = []
    for i in range(steps + 1):
        t = i / steps * math.pi * 0.5
        prof.append((reach * (1.0 - math.cos(t)), top_y - drop + drop * 0.86 * math.sin(t)))
    prof.append((reach, top_y))
    half = (d[0] * BRACKET_W * 0.5, d[1] * BRACKET_W * 0.5)

    def pt(q, side):
        w = (base[0] + out[0] * q[0] + half[0] * side, base[1] + out[1] * q[0] + half[1] * side)
        return (w[0], q[1], w[1])

    corner_q = (0.0, top_y)
    for side in (-1.0, 1.0):
        nrm = (d[0] * side, 0.0, d[1] * side)
        for i in range(len(prof) - 1):
            m.tri(mat, pt(corner_q, side), pt(prof[i], side), pt(prof[i + 1], side), nrm)
    for i in range(len(prof) - 1):
        q0, q1 = prof[i], prof[i + 1]
        seg = (q1[0] - q0[0], q1[1] - q0[1])
        nn = roofmod._unit((seg[1], -seg[0]))
        if nn[0] * (q0[0] - corner_q[0]) + nn[1] * (q0[1] - corner_q[1]) < 0:
            nn = (-nn[0], -nn[1])
        m.quad(mat, pt(q0, -1), pt(q0, 1), pt(q1, 1), pt(q1, -1), (out[0] * nn[0], nn[1], out[1] * nn[0]))


# ------------------------------------------------------------------ the house

def _block(m, mat, b, c, x0, x1, y0, y1, z0, z1, faces):
    """An axis box in basis b around c with only the named faces: f front (+z), l/r (-x/+x),
    t/b (+y/-y); the faces left out lie against a wall, the glass or a neighbouring rail."""
    P = lambda x, y, z: at_basis(b, c, x, y, z)
    N = lambda x, y, z: at_basis(b, (0.0, 0.0, 0.0), x, y, z)
    if "f" in faces:
        m.quad(mat, P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1), N(0, 0, 1))
    if "l" in faces:
        m.quad(mat, P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0), N(-1, 0, 0))
    if "r" in faces:
        m.quad(mat, P(x1, y0, z1), P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), N(1, 0, 0))
    if "t" in faces:
        m.quad(mat, P(x0, y1, z1), P(x1, y1, z1), P(x1, y1, z0), P(x0, y1, z0), N(0, 1, 0))
    if "b" in faces:
        m.quad(mat, P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1), N(0, -1, 0))


def _glazing_bars(m, mat, b, c, hx, hy, gz):
    """A mullion and a transom (two over two lights) in front of
    glass at gz, so a window reads as framed glazing, not one flat pane (harbour a5 R2, an internal task).
    The sides stay at LOD1 too: a front alone off the glass is an open edge (closure audit)."""
    z1, w = gz + BAR_D, BAR_W * 0.5
    _block(m, mat, b, c, -w, w, -hy, hy, gz, z1, "flr")
    for x0, x1 in ((-hx, -w), (w, hx)):
        _block(m, mat, b, c, x0, x1, -w, w, gz, z1, "ftb")


class House:
    def __init__(self, style, foot="rect", storeys=None, jetty=None, oriel=None, tower=None, door_kind=None,
                 timber=None):
        self.st = st = style
        self.poly = footprint(foot)
        rng = st.rng("house")
        self.n_storeys = int(storeys) if storeys else rng.choice([2, 3, 3, 4])
        sm = st.pick("storey_m", "storey")
        ground_s = st.dims["storey_scale"]["ground"]
        top_s = st.dims["storey_scale"]["top"]
        ys = [0.0, sm * max(1.12, rng.uniform(*ground_s))]
        for i in range(1, self.n_storeys):
            ys.append(ys[-1] + sm * (rng.uniform(*top_s) if i == self.n_storeys - 1 else 1.0))
        self.ys = ys
        self.first, self.eaves = ys[1], ys[-1]
        reg = st.region or {}
        share = float(reg.get("ground_stone_share", 0.7 if reg.get("ground_stone") or reg.get("ground_storeys") else 0.0))
        self.stone_ground = rng.random() < share
        self.mats = st.materials("house")
        self.n = len(self.poly)
        lens = [roofmod.d2(self.poly[e], self.poly[(e + 1) % self.n]) for e in range(self.n)]
        self.lens = lens
        self.front = 0
        # jetty on the front when the house has an upper storey and the front's corners are convex
        can_jetty = self.n_storeys >= 2 and convex_at(self.poly, 0) and convex_at(self.poly, 1) and lens[0] >= 4.0
        self.jetty = {}
        if (jetty if jetty is not None else rng.random() < 0.6) and can_jetty:
            self.jetty[0] = st.pick("jetty_m", "jetty")
        self.door_kind = int(door_kind) if door_kind is not None else (2 if self.stone_ground and rng.random() < 0.5 else rng.randrange(2))
        # corner tower at a convex corner off the jettied front, both walls 4.6 m+
        self.tower_v = None
        if tower if tower is not None else rng.random() < 0.5:
            cands = [v for v in range(self.n) if convex_at(self.poly, v) and lens[(v - 1) % self.n] >= 4.6
                     and lens[v] >= 4.6 and v not in (0, 1) and self.n_storeys >= 2]
            if not cands and not self.jetty:
                cands = [v for v in range(self.n) if convex_at(self.poly, v) and lens[(v - 1) % self.n] >= 4.6 and lens[v] >= 4.6]
            if cands:
                self.tower_v = cands[rng.randrange(len(cands))]
        self.want_oriel = oriel if oriel is not None else rng.random() < 0.7
        self.timber = framemod.pick(st, timber) if self.n_storeys >= 2 else 0
        inr = max(w["inradius"] for w in roofmod.wings(self.poly))
        self.k = st.pitch(self.eaves, inr)
        self.overhang = st.pick("eave_overhang_m", "eaves")
        self.reserved = {e: [] for e in range(self.n)}   # edge -> [(u0, u1, y0, y1)]
        self.report = {}
        self.economy = 0   # raised by fit() until LOD0 meets the budget

    # ---------------------------------------------------------------- geometry helpers
    def edge(self, e):
        a, b = self.poly[e], self.poly[(e + 1) % self.n]
        L = roofmod.d2(a, b)
        return a, b, ((b[0] - a[0]) / L, (b[1] - a[1]) / L), roofmod.outward(self.poly, e), L

    def ground_line(self, e):
        """The ground storey's wall line of edge e (set back on a jettied edge, shortened next to one)."""
        a, b, d, o, L = self.edge(e)
        n = self.n
        if e in self.jetty:
            j = self.jetty[e]
            ia = (a[0] - o[0] * j, a[1] - o[1] * j)
            pa, _, pd, _, _ = self.edge((e - 1) % n)
            na, _, nd, _, _ = self.edge((e + 1) % n)
            return line_hit(ia, d, pa, pd), line_hit(ia, d, na, nd)
        ga, gb = a, b
        if (e - 1) % n in self.jetty:
            pa, _, pd, po, _ = self.edge((e - 1) % n)
            j = self.jetty[(e - 1) % n]
            ga = line_hit(a, d, (pa[0] - po[0] * j, pa[1] - po[1] * j), pd)
        if (e + 1) % n in self.jetty:
            na, _, nd, no, _ = self.edge((e + 1) % n)
            j = self.jetty[(e + 1) % n]
            gb = line_hit(a, d, (na[0] - no[0] * j, na[1] - no[1] * j), nd)
        return ga, gb

    def free(self, e, u0, u1, y0, y1, margin=0.2):
        for r in self.reserved[e]:
            if u0 < r[1] + margin and u1 > r[0] - margin and y0 < r[3] and y1 > r[2]:
                return False
        return True

    def reserve(self, e, u0, u1, y0, y1):
        self.reserved[e].append((u0, u1, y0, y1))

    # ---------------------------------------------------------------- build
    def build(self, lod=0) -> Mesh:
        st, M = self.st, self.mats
        m = Mesh(st.tile_m)
        self.reserved = {e: [] for e in range(self.n)}
        self.win_rects = {}   # wall key -> [(u0, u1, y0, y1)] of each window with its sill and shutters
        wall = M["wall"]["name"]
        ground = M["stone"]["name"] if self.stone_ground else wall
        timber, trim = M["timber"]["name"], M["trim"]["name"]
        roof = roofmod.Roof(self.poly, self.eaves, k=self.k)
        self.roof = roof
        # walls
        for e in range(self.n):
            a, b, d, o, L = self.edge(e)
            ga, gb = self.ground_line(e)
            nn = (o[0], 0.0, o[1])
            m.quad(ground, p3(ga, 0.0), p3(gb, 0.0), p3(gb, self.first), p3(ga, self.first), nn)
            m.quad(wall, p3(a, self.first), p3(b, self.first), p3(b, self.eaves), p3(a, self.eaves), nn)
        # jetty underside (timber joists painted in its texture)
        for e, j in self.jetty.items():
            a, b, d, o, L = self.edge(e)
            ga, gb = self.ground_line(e)
            m.quad(timber, p3(a, self.first), p3(b, self.first), p3(gb, self.first), p3(ga, self.first), DOWN)
        tower = self._tower(m, roof, lod) if self.tower_v is not None else False
        self._door(m, lod)
        if lod == 0:
            self._corners(m)
            self._brackets(m)
        if self.want_oriel:
            self._oriel(m, lod)
        self._windows(m, lod)
        frame = framemod.emit(self, m, lod)
        roof.build(m, M["roof"]["name"], M["cap"]["name"] if lod <= 1 else None)
        roofmod.eave_skirt(m, self.poly, self.eaves, self.k, self.overhang, EAVE_FLARE, FASCIA,
                           M["roof"]["name"], timber)
        self.report.update({"storeys": self.ys, "eaves": round(self.eaves, 3), "ridge": round(roof.ridge, 3),
                            "pitch": round(self.k, 3), "wings": len(roof.wings), "jetty": bool(self.jetty),
                            "tower": bool(tower), "stone_ground": self.stone_ground, "door_kind": self.door_kind,
                            "timber_frame": framemod.PATTERNS[self.timber]})
        if lod == 0:
            self.report["timber_pieces"] = frame
        return m

    def fit(self, budget):
        """Builds LOD0, dropping dressing step by step until it meets `budget`: 1 no shutters,
        2 no sills, 3 quoins only where the front meets its neighbours, 4 no timber braces,
        5 timber rails only, 6 no timber frame. Returns the LOD0 mesh."""
        for level in range(7):
            self.economy = level
            m = self.build(0)
            if m.count() <= budget:
                break
        self.report["economy"] = self.economy
        return m

    def _corners(self, m):
        """MpStyle.dress_corners."""
        M = self.mats
        stone = M["stone"]["name"]
        quoin_mat = stone
        for v in range(self.n):
            if v == self.tower_v or not convex_at(self.poly, v):
                continue
            if self.economy >= 3 and v not in (self.front, (self.front + 1) % self.n):
                continue
            prev = (v - 1) % self.n
            if self.lens[prev] < 1.4 or self.lens[v] < 1.4:
                continue
            c = corner(self.poly, v)
            if c is None:
                continue
            set_back = prev in self.jetty or v in self.jetty
            if self.stone_ground:
                if not set_back:
                    quoins(m, c, 0.0, self.first, quoin_mat, self.st.seed + v)
                if self.eaves - self.first > 0.6:
                    corner_post(m, c, self.first + 0.03, self.eaves - 0.02, M["timber"]["name"])
            elif set_back:
                quoins(m, c, self.first, self.eaves - 0.02, quoin_mat, self.st.seed + v)
            else:
                quoins(m, c, 0.0, self.eaves - 0.02, quoin_mat, self.st.seed + v)
            arm = QUOIN_LONG + 0.1
            self.reserve(prev, self.lens[prev] - arm, self.lens[prev] + 1, -1, 99)
            self.reserve(v, -1, arm, -1, 99)

    def _brackets(self, m):
        """MpStyle.jetty_brackets under each jetty, clear of the door."""
        for e, j in self.jetty.items():
            ga, gb = self.ground_line(e)
            a, b, d, o, L = self.edge(e)
            length = roofmod.d2(ga, gb)
            drop = min(BRACKET_DROP, self.first - 0.6)
            count = max(1, int(round((length - 0.3) / BRACKET_STEP)))
            for i in range(count + 1):
                u = 0.15 + (length - 0.3) * i / count
                if any(u > r[0] - 0.25 and u < r[1] + 0.25 and r[2] < self.first and r[3] > self.first - drop
                       for r in self.reserved.get(("g", e), [])):
                    continue
                base = (ga[0] + d[0] * u, ga[1] + d[1] * u)
                bracket(m, base, d, o, self.first, j - 0.03, drop, self.mats["timber"]["name"])

    def _door(self, m, lod):
        e = self.front
        ga, gb = self.ground_line(e)
        a, b, d, o, L = self.edge(e)
        gl = roofmod.d2(ga, gb)
        rng = self.st.rng("door")
        dh = min(self.st.pick("door_m", "door_h"), self.first - 0.9)
        dw = 1.15 if self.door_kind != 2 else 1.3
        u = gl * 0.5 + rng.uniform(-0.15, 0.15) * max(0.0, gl - dw - 3.0)
        if self.tower_v in (0, 1):
            u = gl * 0.5
        foot = (ga[0] + d[0] * u, 0.0, ga[1] + d[1] * u)
        normal = (o[0], 0.0, o[1])
        if lod <= 1:
            top = archmod.door(m, foot, normal, dw, dh, self.mats, self.door_kind, details=lod == 0)
            arched = False
            if self.door_kind == 2 or self.stone_ground:
                arched = archmod.door_arch(m, foot, normal, dw, dh, self.first - 0.12, self.mats["stone"]["name"],
                                           self.mats["timber"]["name"])
            top = top + (archmod.RING + 0.5 if arched else 0.0)
        else:
            b3 = basis_facing(normal)
            hx = dw * 0.5
            P = lambda x, y, z: at_basis(b3, foot, x, y, z)
            m.quad(self.mats["paint"]["name"], P(-hx, 0, 0.02), P(hx, 0, 0.02), P(hx, dh, 0.02), P(-hx, dh, 0.02), normal)
            top = dh + 0.3
        key = e if e not in self.jetty else ("g", e)
        self.reserved.setdefault(key, []).append((u - dw * 0.5 - 0.5, u + dw * 0.5 + 0.5, 0.0, top))
        self.report["door"] = {"edge": e, "u": round(u, 2), "width": dw, "height": round(dh, 2)}

    def _windows(self, m, lod):
        st, M = self.st, self.mats
        rng = st.rng("windows")
        bay = st.pick("window_bay_m", "bay")
        frac = st.dims["window_height_storey_fraction"]
        shutters = rng.random() < 0.6
        count = 0
        for e in range(self.n):
            a, b, d, o, L = self.edge(e)
            for s in range(len(self.ys) - 1):
                y0, y1 = self.ys[s], self.ys[s + 1]
                sh = y1 - y0
                if s == 0:
                    la, lb = self.ground_line(e)
                    key = ("g", e) if e in self.jetty else e
                else:
                    la, lb, key = a, b, e
                ll = roofmod.d2(la, lb)
                ww = min(max(st.dims["window_width_m"][0], 0.55), st.dims["window_width_m"][1], 0.95)
                wh = sh * min(frac[1], max(frac[0], 0.42))
                if s == len(self.ys) - 2:
                    wh = min(wh, sh - 0.9)   # under the eave's soffit
                nb = int((ll - 1.2) // bay)
                if nb < 1 or wh < 0.5:
                    continue
                cy = y0 + sh * 0.5 + (0.1 if s else 0.15)
                for i in range(nb):
                    u = 0.6 + (ll - 1.2) * (i + 0.5) / nb
                    u0, u1 = u - ww * 0.5 - 0.35, u + ww * 0.5 + 0.35
                    if key == e and not self.free(e, u0, u1, cy - wh * 0.5, cy + wh * 0.5):
                        continue
                    if key != e and not all(not (u0 < r[1] and u1 > r[0] and cy - wh < r[3] and cy + wh > r[2])
                                            for r in self.reserved.get(key, [])):
                        continue
                    if u0 < 0.3 or u1 > ll - 0.3:
                        continue
                    centre = (la[0] + d[0] * u, cy, la[1] + d[1] * u)
                    hung = shutters and s <= 1 and self.economy < 1
                    self._window(m, centre, (o[0], 0.0, o[1]), ww, wh, lod, hung, self.economy < 2)
                    side = ww * 0.51 + 0.08 if hung and lod == 0 else 0.15
                    self.win_rects.setdefault(key, []).append((u - ww * 0.5 - side, u + ww * 0.5 + side,
                                                               cy - wh * 0.5 - 0.16, cy + wh * 0.5 + 0.08))
                    count += 1
        self.report["windows"] = count
        self.report["glazing"] = {"bars": True, "glass_set_back_m": round(FRAME_PROUD - GLASS_Z, 3)}

    def _window(self, m, c, normal, ww, wh, lod, shutters, sill=True):
        M = self.mats
        b = basis_facing(normal)
        if lod >= 2:
            hx, hy = ww * 0.5, wh * 0.5
            m.quad("window", at_basis(b, c, -hx, -hy, 0.02), at_basis(b, c, hx, -hy, 0.02),
                   at_basis(b, c, hx, hy, 0.02), at_basis(b, c, -hx, hy, 0.02), normal)
            return
        # A frame of four rails (MpBuildings._emit_oriel's frame, sunk 1 cm into the wall) standing
        # 15 cm proud, over the flat-wall audit's 5 cm relief (an internal task), with the glass set back in it
        # (an internal task: the glass laid on the front of a solid frame box read as a flat amber panel).
        trim = M["trim"]["name"]
        hx, hy, fw = ww * 0.5, wh * 0.5, 0.08
        z0, z1 = -0.01, FRAME_PROUD
        # the underside of a sill rail resting on its sill is left out (nobody sees it; the head
        # rail's top stays: the closure audit sees it from 2.8 m)
        sill_drawn = lod == 0 and sill
        _block(m, trim, b, c, -hx - fw, hx + fw, hy, hy + fw, z0, z1, "flrtb")
        _block(m, trim, b, c, -hx - fw, hx + fw, -hy - fw, -hy, z0, z1, "flrt" if sill_drawn else "flrtb")
        for sx in (-1.0, 1.0):
            x0, x1 = (-hx - fw, -hx) if sx < 0 else (hx, hx + fw)
            _block(m, trim, b, c, x0, x1, -hy, hy, z0, z1, "flr")
        gz = GLASS_Z
        m.quad(M["window"]["name"], at_basis(b, c, -hx, -hy, gz), at_basis(b, c, hx, -hy, gz),
               at_basis(b, c, hx, hy, gz), at_basis(b, c, -hx, hy, gz), normal)
        _glazing_bars(m, trim, b, c, hx, hy, gz)
        if lod >= 1 or not sill:
            return
        # sill, 3 cm out past the frame
        m.box(M["stone"]["name"] if self.stone_ground else M["timber"]["name"],
              add(add(c, mul(UP, -wh * 0.5 - 0.11)), mul(normal, (FRAME_PROUD + 0.02) * 0.5)),
              (ww + 0.3, 0.07, FRAME_PROUD + 0.04), b, back=False)
        if shutters:
            for sx in (-1.0, 1.0):
                sc = add(add(c, mul(b[0], sx * (ww * 0.5 + 0.08 + ww * 0.26))), mul(normal, 0.015))
                m.box(M["paint"]["name"], sc, (ww * 0.5, wh + 0.1, 0.03), b, back=False)

    def _oriel(self, m, lod):
        """MpBuildings._emit_oriels / _emit_oriel on the longest free wall off the front."""
        if self.n_storeys < 2:
            return
        rng = self.st.rng("oriel")
        order = sorted(range(self.n), key=lambda e: (e == self.front and bool(self.jetty), -self.lens[e]))
        for e in order:
            a, b, d, o, L = self.edge(e)
            if L < 4.0:
                continue
            w = min(max(self.st.pick("oriel_m", "oriel_w", "width"), 1.6), 2.4, L - 2.4)
            depth = self.st.pick("oriel_m", "oriel_d", "depth")
            tall = len(self.ys) >= 5 and rng.random() < 0.3
            top_i = 3 if tall else 2
            y0 = self.ys[1] + 0.55
            y1 = self.ys[top_i] - 0.15
            rise = min(0.6, depth * 1.1)
            if top_i == len(self.ys) - 1:
                drop = self.k * self.overhang * EAVE_FLARE + FASCIA
                y1 = self.ys[top_i] - drop - 0.12 - rise
            if y1 - y0 < 1.6:
                continue
            u = L * 0.5 + rng.uniform(-0.15, 0.15) * (L - w - 2.0)
            if not self.free(e, u - w * 0.5 - 0.15, u + w * 0.5 + 0.15, y0 - 0.45, y1 + rise + 0.1):
                continue
            self.reserve(e, u - w * 0.5 - 0.15, u + w * 0.5 + 0.15, y0 - 0.45, y1 + rise + 0.1)
            self._emit_oriel(m, (a[0] + d[0] * (u - w * 0.5), a[1] + d[1] * (u - w * 0.5)), d, o, w, depth, y0, y1,
                             rise, lod)
            self.report["oriel"] = {"edge": e, "width": round(w, 2), "depth": round(depth, 2)}
            return

    def _emit_oriel(self, m, p0, d, out, w, depth, y0, y1, rise, lod):
        M = self.mats
        wall, timber, roof = M["wall"]["name"], M["timber"]["name"], M["roof"]["name"]

        def at(u, y, dd):
            return (p0[0] + d[0] * u + out[0] * dd, y, p0[1] + d[1] * u + out[1] * dd)

        n3, d3 = (out[0], 0.0, out[1]), (d[0], 0.0, d[1])
        m.quad(wall, at(0, y0, depth), at(w, y0, depth), at(w, y1, depth), at(0, y1, depth), n3)
        m.quad(wall, at(0, y0, 0), at(0, y0, depth), at(0, y1, depth), at(0, y1, 0), mul(d3, -1))
        m.quad(wall, at(w, y0, 0), at(w, y0, depth), at(w, y1, depth), at(w, y1, 0), d3)
        m.quad(timber, at(0, y0, 0), at(w, y0, 0), at(w, y0, depth), at(0, y0, depth), DOWN)
        slope_n = norm(add(mul(n3, rise), mul(UP, depth)))
        m.quad(roof, at(0, y1, depth), at(w, y1, depth), at(w, y1 + rise, 0), at(0, y1 + rise, 0), slope_n)
        m.tri(wall, at(0, y1, 0), at(0, y1, depth), at(0, y1 + rise, 0), mul(d3, -1))
        m.tri(wall, at(w, y1, 0), at(w, y1, depth), at(w, y1 + rise, 0), d3)
        b = basis_facing(n3)
        ww, wh = min(1.3, w - 0.55), min(1.15, y1 - y0 - 0.55)
        wc = at(w * 0.5, (y0 + y1) * 0.5 + 0.05, depth)
        if lod >= 2:
            m.quad("window", at(w * 0.5 - ww * 0.5, wc[1] - wh * 0.5, depth + 0.02), at(w * 0.5 + ww * 0.5, wc[1] - wh * 0.5, depth + 0.02),
                   at(w * 0.5 + ww * 0.5, wc[1] + wh * 0.5, depth + 0.02), at(w * 0.5 - ww * 0.5, wc[1] + wh * 0.5, depth + 0.02), n3)
            return
        if lod == 0:
            m.beam(timber, at(-0.04, y0 + 0.03, depth + 0.03), at(w + 0.04, y0 + 0.03, depth + 0.03), 0.14)
            m.beam(timber, at(-0.04, y1 - 0.05, depth + 0.03), at(w + 0.04, y1 - 0.05, depth + 0.03), 0.1)
            for u in (0.08, w - 0.08):
                m.beam(timber, at(u, y0 + 0.1, depth + 0.02), at(u, y1 - 0.1, depth + 0.02), 0.1)
        m.box(timber, add(wc, mul(n3, 0.02)), (ww + 0.16, wh + 0.16, 0.06), b, back=False)
        g = add(wc, mul(n3, 0.075))
        hx, hy = mul(d3, ww * 0.5), mul(UP, wh * 0.5)
        m.quad(M["window"]["name"], sub(sub(g, hx), hy), sub(add(g, hx), hy), add(add(g, hx), hy), add(sub(g, hx), hy), n3)
        _glazing_bars(m, timber, b, wc, ww * 0.5, wh * 0.5, 0.075)
        for u in (0.25, w - 0.25):   # brackets under it (LOD1 too: they carry the silhouette)
            m.beam(timber, at(u, y0 - 0.4, 0.05), at(u, y0 - 0.02, depth * 0.85), 0.09)

    def _tower(self, m, roof, lod):
        """MpStyle.corner_tower: a round tower on a convex corner, from the ground to a cone well
        above the ridge; facets inside the footprint start at the roof surface."""
        v = self.tower_v
        c = corner(self.poly, v)
        if c is None or len(self.ys) < 3:
            return False
        M = self.mats
        n = self.n
        l = min(self.lens[(v - 1) % n], self.lens[v])
        rmin, rmax = self.st.dims["corner_tower_radius_m"]
        r = max(rmin, min(rmax, l * 0.3))
        bis = roofmod._unit((c["n1"][0] + c["n2"][0], c["n1"][1] + c["n2"][1]))
        cen = (self.poly[v][0] - bis[0] * TOWER_INSET, self.poly[v][1] - bis[1] * TOWER_INSET)
        rot = math.atan2(bis[1], bis[0]) - math.pi / TOWER_SIDES
        S = TOWER_SIDES

        def at(i, rad, y):
            a = rot + math.tau * i / S
            return (cen[0] + math.cos(a) * rad, y, cen[1] + math.sin(a) * rad)

        def mid(i, rad):
            a = rot + math.tau * (i + 0.5) / S
            return (cen[0] + math.cos(a) * rad, cen[1] + math.sin(a) * rad)

        def normal(i):
            a = rot + math.tau * (i + 0.5) / S
            return (math.cos(a), 0.0, math.sin(a))

        wall = M["wall"]["name"]
        stone = M["stone"]["name"]
        timber = M["timber"]["name"]
        first, eaves = self.ys[1], self.eaves
        outside = []
        roof_top = eaves
        P = self.poly
        for i in range(S):
            q = mid(i, r)
            e0, e1 = at(i, r, 0), at(i + 1, r, 0)
            inside = roofmod.point_in(q, P) and roofmod.point_in((e0[0], e0[2]), P) and roofmod.point_in((e1[0], e1[2]), P)
            outside.append(not inside)
            if inside:
                roof_top = max(roof_top, roof.y(q))
        roof_top = max(roof_top, roof.y(cen))
        base_y = -0.05
        top_y = max(eaves + 1.7, roof_top + 0.35)
        for i in range(S):
            nrm = normal(i)
            if outside[i]:
                m.quad(stone, at(i, r, base_y), at(i + 1, r, base_y), at(i + 1, r, first), at(i, r, first), nrm)
                m.quad(wall, at(i, r, first), at(i + 1, r, first), at(i + 1, r, top_y), at(i, r, top_y), nrm)
            else:
                q0, q1 = at(i, r, 0), at(i + 1, r, 0)
                y0 = roof.y((q0[0], q0[2])) - 0.02
                y1 = roof.y((q1[0], q1[2])) - 0.02
                if top_y - max(y0, y1) > 0.05:
                    m.quad(wall, (q0[0], y0, q0[2]), (q1[0], y1, q1[2]), at(i + 1, r, top_y), at(i, r, top_y), nrm)
        if lod == 0:
            self._band(m, at, normal, outside, r, r + 0.07, first - 0.08, first + 0.08, timber, False)
            for s in range(2, len(self.ys) - 1):
                self._band(m, at, normal, outside, r, r + 0.05, self.ys[s] - 0.06, self.ys[s] + 0.06, timber, False)
        self._band(m, at, normal, outside, r, r + 0.1, top_y - 0.2, top_y, timber, True, top=False)
        rr = r + 0.32
        apex = (cen[0], top_y + rr * 2.2, cen[1])
        cone = M["roof"]["name"]
        for i in range(S):
            p0, p1 = at(i, rr, top_y), at(i + 1, rr, top_y)
            m.tri(cone, p0, p1, apex, add(normal(i), mul(UP, 0.4)))
            m.quad(timber, at(i, r + 0.1, top_y), at(i + 1, r + 0.1, top_y), p1, p0, DOWN)
        if lod == 0:
            m.prism(M["iron"]["name"], sub(apex, (0, 0.16, 0)), 0.05, 0.7, 4, top=True)
        if lod <= 1:
            facet_d = r * math.cos(math.pi / S)
            facet_w = 2 * r * math.sin(math.pi / S)
            fw = min(0.56, facet_w - 0.08)
            for s in range(1, len(self.ys) - 1):
                y = (self.ys[s] + self.ys[s + 1]) * 0.5 + 0.1
                if self.ys[s + 1] - self.ys[s] < 1.6:
                    continue
                for f in (0, 3, S - 3):
                    if not outside[f]:
                        continue
                    nrm = normal(f)
                    b = basis_facing(nrm)
                    mm = (cen[0] + nrm[0] * facet_d, cen[1] + nrm[2] * facet_d)
                    wc = (mm[0], y, mm[1])
                    slit = f != 0 and s < len(self.ys) - 2
                    ww = 0.3 if slit else fw
                    wh = 0.85 if slit else 1.05
                    fc = add(wc, mul(nrm, 0.04))
                    side = b[0]
                    for sy in (-1.0, 1.0):
                        m.box(timber, add(fc, mul(UP, sy * (wh * 0.5 - 0.0425))), (ww, 0.085, 0.08), b, back=False)
                    for sx in (-1.0, 1.0):
                        m.box(timber, add(fc, mul(side, sx * (ww * 0.5 - 0.04))), (0.08, wh - 0.17, 0.08), b,
                              back=False, top=False, bottom=False)
                    g = add(wc, mul(nrm, 0.04))
                    hx, hy = mul(b[0], ww * 0.5 - 0.08), mul(UP, wh * 0.5 - 0.085)
                    m.quad(M["window"]["name"], sub(sub(g, hx), hy), sub(add(g, hx), hy), add(add(g, hx), hy),
                           add(sub(g, hx), hy), nrm)
                    if not slit:
                        _glazing_bars(m, timber, b, wc, ww * 0.5 - 0.08, wh * 0.5 - 0.085, 0.04)
        # walls next to the tower keep no windows
        self.reserve((v - 1) % n, self.lens[(v - 1) % n] - (r + TOWER_INSET + 0.6), self.lens[(v - 1) % n] + 1, -1, 99)
        self.reserve(v, -1, r + TOWER_INSET + 0.6, -1, 99)
        return True

    def _band(self, m, at, normal, outside, r0, r1, y0, y1, mat, all_round, top=True):
        for i in range(TOWER_SIDES):
            if not all_round and not outside[i]:
                continue
            nrm = normal(i)
            m.quad(mat, at(i, r1, y0), at(i + 1, r1, y0), at(i + 1, r1, y1), at(i, r1, y1), nrm)
            if top:
                m.quad(mat, at(i, r0, y1), at(i + 1, r0, y1), at(i + 1, r1, y1), at(i, r1, y1), UP)
            m.quad(mat, at(i, r0, y0), at(i + 1, r0, y0), at(i + 1, r1, y0), at(i, r1, y0), DOWN)
