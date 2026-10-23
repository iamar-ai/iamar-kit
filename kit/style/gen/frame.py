"""Timber framing on a house's upper storeys: the half-timbered look of the iamar city's houses
(the Warriors' street most of all).

Ported read-only from the iamar browser source (not public) scripts/world/masterplan/mp_buildings.gd: _base_style (the
timber-frame language and its quarter weights), _emit_facade_varied ("timber framing between the
windows", the stringcourse and eave beams, the single post of pattern 1), _beam_along and _post.

Patterns (mp_buildings.gd): 0 plain plaster, 1 a centre post, 2 close studding, 3 studs with
corner braces, 4 cross-braced panels. Every pattern from 1 up lays a rail on each upper storey's
floor line and one under the eaves; studs stand on the window grid's bay lines, so they fall
between the windows. A brace stands in a panel with no window from rail to rail; beside a window
it is a knee brace from the post to the rail above, and pattern 4's cross sits under the sills.

Depths (zfight PLANE_D is 2 cm): rails and posts 6 cm proud of the wall, braces 3 cm (behind the
posts and rails they run into, in front of the wall); every piece keeps clear of the windows
(frame 8 cm, shutters 3 cm proud), the quoins (5 cm), the oriel, the tower and the door. Timber
crossing timber is one material, so it never flickers.
"""
from __future__ import annotations

from meshkit import UP, DOWN, add, mul, sub

PATTERNS = ("plain", "post", "studs", "braced", "crossed")
# mp_buildings.gd _base_style: DIST_W [1, 1, 3, 3, 2], DIST_M [4, 2, 1, 1, 1], DIST_H [2, 2, 2, 2, 2];
# other zones [3, 2, 2, 1, 2]. A profile without weights builds plain walls (a non-timbered look).
PLAIN = [1, 0, 0, 0, 0]
RAIL_T, RAIL_OUT = 0.13, 0.06
POST_T, POST_OUT = 0.12, 0.06
BRACE_W, BRACE_OUT = 0.10, 0.03
SINK = 0.01          # side faces start this far inside the wall, so no seam shows at the wall line
CLEAR = 0.06         # gap kept to windows, quoins and reserved openings


def parse(value):
    """A pattern number or name (`--timber`), or None for the profile's pick."""
    if value is None or value == "auto":
        return None
    if isinstance(value, str) and value in PATTERNS:
        return PATTERNS.index(value)
    try:
        v = int(value)
    except ValueError:
        v = -1
    if not 0 <= v < len(PATTERNS):
        raise ValueError("timber must be 0-4 or one of %s" % ", ".join(PATTERNS))
    return v


def weights(style):
    """The region's `timber_frame_weights`, else the profile's `dimensions.timber_frame_weights`."""
    w = (style.region or {}).get("timber_frame_weights") or style.dims.get("timber_frame_weights") or PLAIN
    w = [max(0.0, float(x)) for x in list(w)[:len(PATTERNS)]]
    w += [0.0] * (len(PATTERNS) - len(w))
    return w if sum(w) > 0 else list(PLAIN)


def pick(style, value=None):
    v = parse(value)
    if v is not None:
        return v
    w = weights(style)
    r = style.rng("timber").random() * sum(w)
    for i, x in enumerate(w):
        r -= x
        if r < 0:
            return i
    return len(w) - 1


class Frame:
    """Lays one house's framing into a mesh; reads the house's walls, storeys and what is
    already on each wall (windows, oriel, tower, door) and never covers any of it."""

    def __init__(self, house, m, lod):
        self.h, self.m, self.lod = house, m, lod
        self.mat = house.mats["timber"]["name"]
        self.pieces = {"rails": 0, "posts": 0, "braces": 0}

    # ---------------------------------------------------------------- what is on a wall
    def rects(self, e):
        h = self.h
        out = []
        for r in h.reserved.get(e, []):
            whole_height = r[2] <= -1 and r[3] >= 99
            # the corners' own reservations (quoins, corner posts) are replaced by corner_clear;
            # the tower's stays
            if whole_height and r[0] <= -1 and e != h.tower_v:
                continue
            if whole_height and r[1] >= h.lens[e] + 1 - 1e-6 and (e + 1) % h.n != h.tower_v:
                continue
            out.append(r)
        return out + list(h.win_rects.get(e, []))

    def corner_clear(self, v, e):
        """How far from vertex v the framing of wall e keeps off: the corner's dressing."""
        from house import convex_at, corner, QUOIN_LONG, POST_ARM
        h = self.h
        n = h.n
        if not convex_at(h.poly, v):
            return 0.0, False                    # concave: rails run into the other wall
        prev = (v - 1) % n
        dressed = (self.lod == 0 and v != h.tower_v and h.lens[prev] >= 1.4 and h.lens[v] >= 1.4
                   and corner(h.poly, v) is not None
                   and not (h.economy >= 3 and v not in (h.front, (h.front + 1) % n)))
        if not dressed:
            return -RAIL_OUT, True               # rails of the two walls overlap at the corner
        if h.stone_ground and h.eaves - h.first > 0.6:
            return POST_ARM - 0.04, True         # rails end inside the timber corner post
        return min(QUOIN_LONG, h.lens[e] * 0.4) + CLEAR, True

    def free_spans(self, rects, u0, u1, y0, y1):
        spans = [(u0, u1)]
        for r in rects:
            if r[2] >= y1 or r[3] <= y0:
                continue
            a, b = r[0] - CLEAR, r[1] + CLEAR
            nxt = []
            for s, t in spans:
                if b <= s or a >= t:
                    nxt.append((s, t))
                    continue
                if a > s:
                    nxt.append((s, a))
                if b < t:
                    nxt.append((b, t))
            spans = nxt
        return [s for s in spans if s[1] - s[0] >= 0.05]

    def blocked(self, rects, u0, u1, y0, y1):
        return any(r[0] - CLEAR < u1 and r[1] + CLEAR > u0 and r[2] - CLEAR < y1 and r[3] + CLEAR > y0
                   for r in rects)

    # ---------------------------------------------------------------- pieces
    def slab(self, at, pts, out, sides):
        """A piece proud of the wall: front face at `out` on the (u, y) outline `pts`
        (counter-clockwise seen from outside), side faces for the outline edges in `sides`."""
        m, mat = self.m, self.mat
        front = [at(u, y, out) for u, y in pts]
        m.poly(mat, front, self.normal)
        k = len(pts)
        for i in sides:
            (ua, ya), (ub, yb) = pts[i], pts[(i + 1) % k]
            du, dy = ub - ua, yb - ya
            # outward in the wall plane: right of the edge for a counter-clockwise outline
            side = add(mul(self.d3, dy), mul(UP, -du))
            m.quad(mat, at(ua, ya, -SINK), at(ub, yb, -SINK), at(ub, yb, out), at(ua, ya, out), side)

    def rail(self, at, u0, u1, y, end0, end1):
        t = RAIL_T * 0.5
        pts = [(u0, y - t), (u1, y - t), (u1, y + t), (u0, y + t)]
        sides = [0, 2] + ([1] if end1 else []) + ([3] if end0 else [])
        self.slab(at, pts, RAIL_OUT, sides)
        self.pieces["rails"] += 1

    def post(self, at, u, y0, y1, cap0, cap1):
        t = POST_T * 0.5
        pts = [(u - t, y0), (u + t, y0), (u + t, y1), (u - t, y1)]
        self.slab(at, pts, POST_OUT, [1, 3] + ([0] if cap0 else []) + ([2] if cap1 else []))
        self.pieces["posts"] += 1

    def brace(self, at, foot, head):
        """A diagonal plank with level ends, foot (u, y) to head (u, y); its ends lie in the post
        and rail it joins, so only the front and the two long sides are built."""
        t = BRACE_W * 0.5
        (fu, fy), (hu, hy) = foot, head
        pts = [(fu - t, fy), (fu + t, fy), (hu + t, hy), (hu - t, hy)]
        self.slab(at, pts, BRACE_OUT, [1, 3])
        self.pieces["braces"] += 1

    # ---------------------------------------------------------------- one wall
    def wall(self, e, pattern):
        h = self.h
        a, b, d, o, L = h.edge(e)
        self.normal = (o[0], 0.0, o[1])
        self.d3 = (d[0], 0.0, d[1])

        def at(u, y, out):
            return (a[0] + d[0] * u + o[0] * out, y, a[1] + d[1] * u + o[1] * out)

        rects = self.rects(e)
        ca, ra = self.corner_clear(e, e)
        cb, rb = self.corner_clear((e + 1) % h.n, e)
        lo, hi = ca, L - cb
        if hi - lo < 0.6:
            return
        ys = h.ys
        top = len(ys) - 1
        # rail heights: each upper storey's floor line, and one under the eaves' soffit
        rails = [ys[s] + 0.12 for s in range(1, top)]
        rails.append(h.eaves - 0.12 - h.k * RAIL_OUT * 0.55)
        for y in rails:
            for s, t in self.free_spans(rects, lo, hi, y - RAIL_T * 0.5, y + RAIL_T * 0.5):
                self.rail(at, s, t, y, end0=s > lo + 1e-6 or ra, end1=t < hi - 1e-6 or rb)
        if pattern < 1 or h.economy >= 5:
            return
        # posts: pattern 1 one in the middle; 2-4 on the window grid's bay lines and at the ends
        if pattern == 1:
            us = [L * 0.5] if L > 2.2 else []
        else:
            bay = h.st.pick("window_bay_m", "bay")
            nb = int((L - 1.2) // bay)
            if nb >= 1:
                us = [0.6 + (L - 1.2) * i / nb for i in range(nb + 1)]
            else:
                bays = max(1, int(round(L / bay)))
                us = [L * i / bays for i in range(bays + 1)]
            us += [lo + POST_T * 0.5 + 0.02, hi - POST_T * 0.5 - 0.02]
            us = sorted(u for u in us if lo + POST_T * 0.5 <= u <= hi - POST_T * 0.5)
            kept = []
            for u in us:
                if not kept or u - kept[-1] >= 0.35:
                    kept.append(u)
                elif u > hi - POST_T:            # keep the end post, drop the one beside it
                    kept[-1] = u
            us = kept
        tp = POST_T * 0.5
        for s in range(1, top):
            yb = rails[s - 1] + RAIL_T * 0.5 - 0.01
            yt = rails[s] - RAIL_T * 0.5 + 0.01
            standing = []
            for u in us:
                pieces = self._heights(rects, u - tp, u + tp, yb, yt)
                for p0, p1 in pieces:
                    self.post(at, u, p0, p1, cap0=p0 > yb + 1e-6, cap1=p1 < yt - 1e-6)
                if pieces == [(yb, yt)]:
                    standing.append(u)
            if pattern >= 3 and self.lod == 0 and h.economy < 4:
                self._braces(at, e, rects, standing, pattern, yb, yt)

    def _heights(self, rects, u0, u1, y0, y1):
        pieces = [(y0, y1)]
        for r in rects:
            if r[0] - CLEAR >= u1 or r[1] + CLEAR <= u0:
                continue
            a, b = r[2] - CLEAR, r[3] + CLEAR
            nxt = []
            for s, t in pieces:
                if b <= s or a >= t:
                    nxt.append((s, t))
                    continue
                if a > s:
                    nxt.append((s, a))
                if b < t:
                    nxt.append((b, t))
            pieces = nxt
        return [p for p in pieces if p[1] - p[0] >= 0.25]

    def _braces(self, at, e, rects, us, pattern, yb, yt):
        if len(us) < 2:
            return
        tp, tb = POST_T * 0.5, BRACE_W * 0.5
        panels = list(zip(us[:-1], us[1:]))
        wins = [r for r in self.h.win_rects.get(e, []) if r[2] < yt and r[3] > yb]
        for i, (pa, pb) in enumerate(panels):
            if pattern == 3 and i not in (0, len(panels) - 1):
                continue
            inner0, inner1 = pa + tp, pb - tp
            if inner1 - inner0 < 0.5:
                continue
            here = [r for r in wins if r[0] < pb and r[1] > pa]
            if pattern == 4:
                if not here:
                    y1 = yt
                else:
                    y1 = min(r[2] for r in here) - CLEAR
                if y1 - yb < 0.5:
                    continue
                f0, f1 = (inner0 + tb, yb), (inner1 - tb, y1)
                g0, g1 = (inner1 - tb, yb), (inner0 + tb, y1)
                if self.blocked(rects, inner0, inner1, yb, y1 - 0.01):
                    continue
                self.brace(at, f0, f1)
                self.brace(at, g0, g1)
                continue
            # pattern 3: in the panel at the wall's end, rising from the end post inward
            toward = 1.0 if i == 0 else -1.0
            post_u = pa if i == 0 else pb
            if not here:
                run = min(inner1 - inner0 - BRACE_W, 1.1)
                foot = (post_u + toward * (tp + tb - 0.02), yb)
            else:
                near = min(r[0] for r in here) - CLEAR if toward > 0 else max(r[1] for r in here) + CLEAR
                run = min(abs(near - post_u) - tp - BRACE_W, 1.1)
                if run < 0.3:
                    continue
                foot = (post_u + toward * (tp + tb - 0.02), max(yb, yt - 1.3 * run))
            head = (post_u + toward * (tp + run), yt)
            u0, u1 = sorted((foot[0], head[0]))
            if run < 0.3 or self.blocked(rects, u0 - tb, u1 + tb, foot[1], yt - 0.01):
                continue
            self.brace(at, foot, head)
            if len(panels) == 1:
                break


def emit(house, m, lod):
    """Frames every upper-storey wall of `house` (pattern house.timber); LOD0 and LOD1 (no braces
    on LOD1), nothing on LOD2. Returns the counts of rails, posts and braces."""
    f = Frame(house, m, lod)
    if lod >= 2 or house.timber <= 0 or house.n_storeys < 2 or house.economy >= 6:
        return f.pieces
    for e in range(house.n):
        f.wall(e, house.timber)
    return f.pieces
