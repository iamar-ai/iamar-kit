#!/usr/bin/env python3
"""Geometry audits for any iamar world: the iamar city's own audits, made generic.

    iamar-world audit <NAME | all> <world folder | model.glb ...> [--json] [--quiet] [--lod 0|all]
    python3 kit/audit/audit.py   (same arguments; iamar-world audit runs this)

NAME is one of the audits below (or "all"). A world folder is read from its scene.json
(objects placed as the browser places them, box/plane primitives such as the ground); a .glb is
audited alone at the origin. Exit 1 when any audit reports an ERROR. Needs numpy (dark-bake
also Pillow). Each audit is the generic form of a city audit in the iamar browser source (not public) (named in
brackets); kit/audit/README.md gives the thresholds and what to do about each finding.

  closure    open edges a player can see into [tools/masterplan_closure_audit.gd]: boundary
             edges (one triangle only, after welding vertices 2 mm apart) that no other surface
             passes within 3 cm of, and that a viewer at eye height around the object or at a
             spawn point sees with a line of sight that lands on the back of a one-sided face or
             in the void
  zfight     coplanar overlaps that flicker [tests/masterplan_city/zfight_audit.gd]: pairs of
             same-facing triangles of different parts within 2 cm and 2 degrees whose areas
             overlap; plus objects placed twice at the same transform. A pair is skipped (INFO,
             naming the quest) when one object id is in a quest's on_complete.show and the other
             in the same quest's hide: the quest never draws them together
  roof       what a flyer sees from above [tests/masterplan_city/mp_roof_audit_test.gd]: on each
             building and landmark, vertical and oblique (52, 28 degrees, four quarters) sky rays
             must first meet a front face of the object; "open" (vertical ray meets nothing of it),
             "back" (first face is a back face: an open wall top, a roof with no top side) and
             "sunk" (first face is low inside the object: a floor seen through a missing roof)
  edge       see-through walls at eye height [tools/masterplan_edge_audit.py]: from 2 m outside each
             side of a building, rays at 1.6 m towards its middle must meet a front face near the
             outside (within 40 % of the building's depth); a side where two of three rays miss,
             show back faces or reach deep into the building (a missing wall of a hollow house)
             is an open side, unless the start point is inside another object (a party wall)
  door       walk-through doors [tests/masterplan_city/door_audit.gd]: every node named *door*
             (not frame, arch or knocker) in a building that leads into a room (behind it, rays
             meet the inside faces of walls; a door painted on a solid block is decorative): rays from 2 m outside to 1.2 m inside at
             knee, chest and head height, mid and either side, must not hit other geometry
             (BLOCKED); the wall above the door must be there (HOLE); the floor outside and
             inside may differ by at most 0.45 m (STEP)
  dark-bake  black spots in the light bake [tools/dark_bake_audit.py]: on models with baked light
             (KHR_materials_unlit colour textures from kit/blender/bake_unlit.py, or a lightmap
             PNG <model>.lightmap.png read through TEXCOORD_1, red = sky and green = sun like the
             city's bakes), texels on sky-facing faces that come out near black and that a
             viewer can see (not covered by other surfaces, not a seam one or two texels wide);
             patches of 0.05 m2 or more are errors
  flat-wall  long walls with no opening or relief [kit/audit/flat_wall.py, Track A rule]: on each
             building, landmark and structure, a run of wall at eye height longer than the style
             profile's lint.flat_wall_max_m (iamar: 6 m) with no door, arch, pier or frame. Judged
             against the world's own style.json (else iamar); a profile without the limit skips it
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import re
import json
import math
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import meshworld  # noqa: E402

AUDITS = ("closure", "zfight", "roof", "edge", "door", "dark-bake", "flat-wall")
BUILDINGS = ("building", "landmark", "interior")
UP = np.array([0.0, 1.0, 0.0])

# closure
WELD = 0.002
MIN_EDGE = 0.12
RING_R = 0.03
SAMPLE_STEP = 0.6
EYES = (1.6, 2.8)
MAX_OPEN_M = 0.0
# zfight
PLANE_D = 0.02
ANGLE_DEG = 2.0
MIN_AREA = 0.002
PASS_AREA = 0.05
# roof
ROOF_STEP = 0.75
INSET = 0.2
ELEVATIONS = (52.0, 28.0)
AZIMUTHS = (45.0, 135.0, 225.0, 315.0)
SUNK_FRACTION = 0.35
# edge
EDGE_DEPTH = 0.4
# door
DOOR_OUT, DOOR_IN = 2.0, 1.2
MAX_STEP = 0.45
DOOR_SKIP = ("frame", "arch", "knocker", "handle", "hinge", "lintel", "surround", "trim")
# dark-bake
DARK_SKY, DARK_SUN, DARK_UNLIT = 0.16, 0.06, 0.05
UP_Y = 0.5
MIN_PATCH_M2 = 0.05
HIDDEN_TILTS = ((25.0, 6), (50.0, 8), (75.0, 10))   # view-ray rings: degrees from the normal, rays
HIDDEN_CELL = 0.1
HIDDEN_FAR = 10.0   # a view ray that meets nothing this far reaches the open


class Report:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, level, audit, where, msg, **data):
        self.items.append(dict({"level": level, "audit": audit, "where": where, "message": msg}, **data))

    def errors(self):
        return [i for i in self.items if i["level"] == "ERROR"]


def where_of(w, oi, part=None):
    o = w.objects[oi]
    s = "%s:%s" % (w.name, o["id"])
    if part:
        s += "/" + part
    return s


def fmt(p):
    return "(%.2f, %.2f, %.2f)" % tuple(p)


# ------------------------------------------------------------------ closure

def boundary_edges(w, tri_idx):
    """Edges used by exactly one triangle of tri_idx (welded by position): (tri, a, b) rows."""
    t = w.tris[tri_idx]
    q = np.round(t / WELD).astype(np.int64)
    keys = {}
    vid = np.zeros(q.shape[:2], np.int64)
    for i in range(len(q)):
        for k in range(3):
            vid[i, k] = keys.setdefault(tuple(q[i, k]), len(keys))
    e = np.concatenate([vid[:, [0, 1]], vid[:, [1, 2]], vid[:, [2, 0]]])
    owner = np.concatenate([np.arange(len(q))] * 3)
    corner = np.concatenate([np.full(len(q), 0), np.full(len(q), 1), np.full(len(q), 2)])
    s = np.sort(e, axis=1)
    _, inv, cnt = np.unique(s, axis=0, return_inverse=True, return_counts=True)
    one = cnt[inv.ravel()] == 1
    out = []
    for i in np.nonzero(one)[0]:
        ti, c = owner[i], corner[i]
        a, b = t[ti, c], t[ti, (c + 1) % 3]
        out.append((tri_idx[ti], a, b))
    return out


def viewpoints(w, oi):
    lo, hi = w.objects[oi]["box"]
    c = (lo + hi) / 2
    r = max(hi[0] - lo[0], hi[2] - lo[2]) / 2
    base = w.ground_y(c[0], c[2], top=hi[1] + 50)
    out = [s + np.array([0, EYES[0], 0]) for s in w.spawns]
    for dist in (r + 3.0, r + 10.0):
        for k in range(16):
            ang = k * math.tau / 16
            x, z = c[0] + math.cos(ang) * dist, c[2] + math.sin(ang) * dist
            g = w.ground_y(x, z, top=hi[1] + 50)
            gy = g if g is not None else (base if base is not None else lo[1])
            for eye in EYES:
                out.append(np.array([x, gy + eye, z]))
    return np.array(out)


CATALOG_SOURCES = HERE.parent / "catalog" / "sources"
SEAL_PROPS = HERE.parent / "catalog" / "assets" / "seal_props.py"


VARIANT_WORDS = {"closed", "sealed", "lod0", "lod1", "lod2", "lod3"}


def sealed_catalogue():
    """Catalogue entries that were sealed after a world could already have copied them:
    (file stem words, current sha256, sha256 of the unsealed original or None)."""
    rows = []
    try:
        files = {}
        for src in sorted(CATALOG_SOURCES.glob("*.json")):
            files[src.name] = json.loads(src.read_text(encoding="utf-8"))
        listed = ast.literal_eval(re.search(r"^SEALED = (\{.*?^\})", SEAL_PROPS.read_text(encoding="utf-8"),
                                            re.S | re.M).group(1))
        for name, data in files.items():
            for r in data.get("models", []) if isinstance(data, dict) else []:
                old = (r.get("sealed") or r.get("closed_from") or {})
                old = old.get("source_sha256") or old.get("sha256")
                if old or (listed.get(r.get("file")) == name):
                    rows.append((re.sub(r"[^a-z0-9]+", " ", Path(r["file"]).stem.lower()).split(), r["sha256"], old, r["file"]))
    except (OSError, ValueError, AttributeError, SyntaxError):
        return []
    return rows


def stale_copy_hints(w, rep, bad):
    """bad: object index -> closure ERROR part names. Say which of them look like an older copy of
    a catalogue model that was sealed later (the world keeps its own copy and nothing refreshes it)."""
    rows = sealed_catalogue()
    if not rows:
        return
    seen = set()
    for oi, names in bad.items():
        asset = w.objects[oi]["asset"]
        if asset in seen:
            continue
        seen.add(asset)
        digest = ""
        f = Path(w.root) / asset if getattr(w, "root", None) else None
        if f is not None and f.is_file():
            digest = hashlib.sha256(f.read_bytes()).hexdigest()
        words = set(re.sub(r"[^a-z0-9]+", " ", " ".join([asset] + list(names)).lower()).split())
        for stem, cur, old, rel in rows:
            if digest and digest == cur:
                continue   # this very file is the current sealed model
            exact = bool(digest and digest == old)
            # the last-word rule (an old "Fishing Boat Hull" for fishing_boat) reads the object's
            # own last word: "closed" or "lod1" says which variant, not what it is (every
            # *_closed house would match every other one)
            core = [x for x in stem if x not in VARIANT_WORDS]
            if exact or (len(stem) > 0 and (set(stem) <= words or (len(core) > 1 and core[-1] in words and len(core[-1]) >= 4))):
                rep.add("WARN", "closure", w.name,
                        "%s %s the catalogue model %s, which was sealed after this copy was made (current id %s): refresh it "
                        "with `iamar-world assets use <world folder> %s --as %s`, or rebuild the merged file from the sealed model"
                        % (asset, "is an unsealed copy of" if exact else "looks like an older copy of", rel, cur[:16], cur[:16], asset),
                        stale_catalogue=rel)


def audit_closure(w, rep, objs):
    total_open = 0.0
    bad = {}
    for oi in objs:
        o = w.objects[oi]
        idx = np.nonzero((w.obj == oi) & ~w.double)[0]
        if not len(idx):
            continue
        edges = [e for e in boundary_edges(w, idx) if np.linalg.norm(e[2] - e[1]) >= MIN_EDGE]
        # sealed: some other triangle passes within RING_R of a sample point along the edge
        samples = []
        for ti, a, b in edges:
            ln = float(np.linalg.norm(b - a))
            n = max(1, int(round(ln / SAMPLE_STEP)))
            for k in range(n):
                f = (k + 0.5) / n
                samples.append((ti, a + (b - a) * f, ln / n, a, b))
        unsealed = []
        if samples:
            pts = np.array([s[1] for s in samples])
            for s0 in range(0, len(pts), 256):
                blk = pts[s0:s0 + 256]
                lo, hi = blk.min(0) - RING_R, blk.max(0) + RING_R
                cand = np.nonzero(np.all((w.hi >= lo) & (w.lo <= hi), axis=1))[0]
                d = w.point_tri_dist(blk, cand) if len(cand) else np.full((len(blk), 0), np.inf)
                for j in range(len(blk)):
                    ti = samples[s0 + j][0]
                    near = cand[d[j] <= RING_R] if d.shape[1] else cand[:0]
                    near = near[near != ti]
                    if not len(near):
                        unsealed.append(samples[s0 + j])
        # visible: from some viewpoint, the sight line reaches the point and, past it, lands on a back face or nothing
        vis = []
        if unsealed:
            vp = viewpoints(w, oi)
            for ti, p, seg, a, b in unsealed:
                d = p[None] - vp
                dist = np.linalg.norm(d, axis=1)
                order = [k for k in np.argsort(dist) if dist[k] < 90.0]
                # nearest viewers first, a few at a time: stop at the first that sees through
                for s0 in range(0, len(order), 8):
                    ks = np.array(order[s0:s0 + 8])
                    v, dl = vp[ks], dist[ks]
                    dd = d[ks] / dl[:, None]
                    t, hit, front = w.raycast(v, dd, dl - 0.02)
                    reach = hit < 0
                    if not reach.any():
                        continue
                    start = p[None] + dd[reach] * 0.02
                    t2, h2, f2 = w.raycast(start, dd[reach], 60.0)
                    through = (h2 < 0) | ~f2
                    if through.any():
                        vis.append((ti, p, seg, a, b, v[reach][np.argmax(through)]))
                        break
        open_m = sum(s[2] for s in vis)
        total_open += open_m
        if vis:
            bad[oi] = sorted({w.parts[w.part[ti]][1]["name"] for ti, *_ in vis})
            parts = {}
            for ti, p, seg, a, b, eye in vis:
                pn = w.parts[w.part[ti]][1]["name"]
                parts.setdefault(pn, []).append((seg, p, eye))
            for pn, rows in sorted(parts.items(), key=lambda kv: -sum(r[0] for r in kv[1])):
                m = sum(r[0] for r in rows)
                rep.add("ERROR" if m > MAX_OPEN_M else "WARN", "closure", where_of(w, oi, pn),
                        "%.2f m of open edge a player can see into, e.g. at %s from %s"
                        % (m, fmt(rows[0][1]), fmt(rows[0][2])), open_m=round(m, 3), at=list(map(float, rows[0][1])))
        rep.add("INFO", "closure", where_of(w, oi), "%d boundary edges, %d unsealed samples, %.2f m visible open"
                % (len(edges), len(unsealed), open_m))
    stale_copy_hints(w, rep, bad)
    rep.add("INFO", "closure", w.name, "RESULT open_m=%.2f" % total_open)


# ------------------------------------------------------------------ zfight

def clip_overlap(p, q, n):
    """Area of the overlap of two coplanar triangles (3x3 each) with plane normal n."""
    ax = int(np.argmax(np.abs(n)))
    keep = [i for i in range(3) if i != ax]
    P, Q = p[:, keep], q[:, keep]

    def area(poly):
        x, y = poly[:, 0], poly[:, 1]
        return 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

    if area(P) < 0:
        P = P[::-1]
    if area(Q) < 0:
        Q = Q[::-1]
    out = list(P)
    for i in range(3):
        a, b = Q[i], Q[(i + 1) % 3]
        inp, out = out, []
        if not inp:
            break
        side = lambda v: (b[0] - a[0]) * (v[1] - a[1]) - (b[1] - a[1]) * (v[0] - a[0])
        for j in range(len(inp)):
            cur, prv = inp[j], inp[j - 1]
            sc, sp = side(cur), side(prv)
            if sc >= 0:
                if sp < 0:
                    out.append(prv + (cur - prv) * (sp / (sp - sc)))
                out.append(cur)
            elif sp >= 0:
                out.append(prv + (cur - prv) * (sp / (sp - sc)))
    if len(out) < 3:
        return 0.0
    a2 = abs(area(np.array(out)))
    return a2 / max(abs(n[ax]), 1e-9)


def quest_swaps(w):
    """frozenset({show id, hide id}) -> quest id, for quests whose on_complete swaps the pair.

    A quest that shows one object and hides another on completion means the two are never
    drawn together, so a zfight between them is not a real defect (desert a2: the
    'water_for_the_driver' quest shows cart_lamp_glow and hides cart_lamp_dark)."""
    swaps = {}
    for q in getattr(w, "quests", None) or []:
        if not isinstance(q, dict):
            continue
        qid = q.get("id", "?")
        oc = q.get("on_complete") or {}
        if not isinstance(oc, dict):
            continue
        show = {str(s) for s in (oc.get("show") or [])}
        hide = {str(h) for h in (oc.get("hide") or [])}
        for s in show:
            for h in hide:
                if s != h:
                    swaps.setdefault(frozenset((s, h)), qid)
    return swaps


def swapped_by(swaps, a_id, b_id):
    """Quest id whose on_complete shows one object id and hides the other, else None.

    Audit object ids of multi-model files carry a '<id>/<node>' suffix; the base id still
    names the scene object the quest swaps, so both are tried."""
    def cand(oid):
        ids = {str(oid)}
        if "/" in str(oid):
            ids.add(str(oid).split("/", 1)[0])
        return ids
    for a in cand(a_id):
        for b in cand(b_id):
            if a != b and frozenset((a, b)) in swaps:
                return swaps[frozenset((a, b))]
    return None


def audit_zfight(w, rep, objs):
    prim = np.array([o["cls"] == "primitive" for o in w.objects], bool)
    sel = np.isin(w.obj, list(objs)) | prim[w.obj]
    idx = np.nonzero(sel & (w.area > 1e-6))[0]
    n = w.normal[idx]
    d = np.einsum("ij,ij->i", n, w.tris[idx, 0])
    cos_tol = math.cos(math.radians(ANGLE_DEG))
    base = np.array([o["box"][0][1] if o["box"] is not None else -1e9 for o in w.objects])
    # bucket by quantised normal direction and plane offset; compare within neighbouring buckets
    qn = np.round(n * 20).astype(np.int64)
    qd = np.floor(d / (2 * PLANE_D)).astype(np.int64)
    buckets = {}
    for k, i in enumerate(idx):
        buckets.setdefault((tuple(qn[k]), qd[k]), []).append(k)
    pairs = {}
    seen = set()
    for (kn, kd), members in buckets.items():
        others = []
        for ddd in (-1, 0, 1):
            others += buckets.get((kn, kd + ddd), [])
        A = np.array(members)
        B = np.array(sorted(set(others)))
        for a in A:
            ia = idx[a]
            m = B[(B > a)]
            if not len(m):
                continue
            ib = idx[m]
            ok = (w.part[ib] != w.part[ia])
            ok &= np.einsum("j,ij->i", n[a], n[m]) >= cos_tol
            ok &= np.abs(d[m] - d[a]) <= PLANE_D
            ok &= np.all((w.hi[ib] >= w.lo[ia] - 1e-4) & (w.lo[ib] <= w.hi[ia] + 1e-4), axis=1)
            if n[a, 1] < -0.9 and w.hi[ia, 1] <= base[w.obj[ia]] + PLANE_D:
                # two undersides, each at the bottom of its object (a crate standing where a
                # paving slab ends): only a camera under the ground could see them flicker
                ok &= ~(w.hi[ib, 1] <= base[w.obj[ib]] + PLANE_D)
            for j in ib[ok]:
                key = (min(ia, j), max(ia, j))
                if key in seen:
                    continue
                seen.add(key)
                ar = clip_overlap(w.tris[ia], w.tris[j], n[a])
                if ar >= MIN_AREA:
                    pk = tuple(sorted((int(w.part[ia]), int(w.part[j]))))
                    rec = pairs.setdefault(pk, [0.0, w.tris[ia].mean(0)])
                    rec[0] += ar
    total = 0.0
    n_pairs = 0
    swaps = quest_swaps(w)
    for (pa, pb), (ar, at) in sorted(pairs.items(), key=lambda kv: -kv[1][0]):
        oa, A = w.parts[pa]
        ob, B = w.parts[pb]
        qid = swapped_by(swaps, w.objects[oa]["id"], w.objects[ob]["id"])
        if qid is not None:
            rep.add("INFO", "zfight", where_of(w, oa, A["name"]),
                    "%.3f m2 coplanar with %s: skipped, quest '%s' on_complete shows one and hides the other, so they are never drawn together"
                    % (ar, where_of(w, ob, B["name"]).split(":", 1)[1], qid),
                    area_m2=round(ar, 4), at=list(map(float, at)))
            continue
        n_pairs += 1
        total += ar
        rep.add("ERROR" if ar >= PASS_AREA else "WARN", "zfight", where_of(w, oa, A["name"]),
                "%.3f m2 coplanar with %s near %s: move one surface %.0f mm or more, or cut it"
                % (ar, where_of(w, ob, B["name"]).split(":", 1)[1], fmt(at), PLANE_D * 1000 * 1.5),
                area_m2=round(ar, 4), at=list(map(float, at)))
    # duplicated placements
    seen_t = {}
    for oi in objs:
        o = w.objects[oi]
        key = (o["asset"], o.get("part"), tuple(np.round(o["matrix"].ravel(), 3)))   # part: one model of several in a file
        if o["asset"] and key in seen_t:
            rep.add("ERROR", "zfight", where_of(w, oi), "placed twice: same asset and transform as %s" % seen_t[key])
        seen_t.setdefault(key, o["id"])
    rep.add("INFO", "zfight", w.name, "RESULT coplanar_m2=%.3f pairs=%d" % (total, n_pairs))


# ------------------------------------------------------------------ roof

def footprint_points(box, step, inset):
    lo, hi = box
    xs = np.arange(lo[0] + inset, hi[0] - inset + 1e-9, step)
    zs = np.arange(lo[2] + inset, hi[2] - inset + 1e-9, step)
    if not len(xs):
        xs = np.array([(lo[0] + hi[0]) / 2])
    if not len(zs):
        zs = np.array([(lo[2] + hi[2]) / 2])
    X, Z = np.meshgrid(xs, zs)
    return np.stack([X.ravel(), Z.ravel()], 1)


def footprint_mask(w, oi, xz):
    """Points over the object's own geometry seen from straight above (anything of it below)."""
    lo, hi = w.objects[oi]["box"]
    o = np.column_stack([xz[:, 0], np.full(len(xz), hi[1] + 1), xz[:, 1]])
    t, i, _ = w.raycast(o, np.tile(-UP, (len(o), 1)), hi[1] - lo[1] + 2, mask=w.obj == oi)
    return i >= 0


def walled(w, oi, xz, y):
    """True when the object stands around a low point on all four sides (a floor inside walls),
    not when the point is an outside ledge: the base step of a tower, the deck of a quay."""
    o = np.array([[xz[0], y + 0.8, xz[1]]] * 4)
    d = np.array([[1.0, 0, 0], [-1.0, 0, 0], [0, 0, 1.0], [0, 0, -1.0]])
    _, i, _ = w.raycast(o, d, 100.0, mask=w.obj == oi)
    return bool((i >= 0).all())


def on_stair(xz, hy, mine, fr, k):
    """True when a sky-visible point of the object one grid step away stands 5 cm to 1.2 m higher or lower:
    a tread of an open-air stair or ramp, not the flat floor of a room whose roof is missing."""
    d = np.abs(xz - xz[k]).max(1)
    near = mine & fr & (d < ROOF_STEP * 1.01) & (d > 1e-6)
    rise = hy[near] - hy[k]
    return bool(((np.abs(rise) > 0.05) & (np.abs(rise) <= 1.2)).any())


def audit_roof(w, rep, objs):
    total = 0
    for oi in objs:
        o = w.objects[oi]
        if o["cls"] not in BUILDINGS or o["box"] is None:
            continue
        lo, hi = o["box"]
        height = hi[1] - lo[1]
        xz = footprint_points(o["box"], ROOF_STEP, INSET)
        # the object's own outline: where a ray down meets any of it (concave footprints, towers)
        inside = footprint_mask(w, oi, xz)
        found = {"open": [], "back": [], "sunk": []}
        top = hi[1] + 60.0
        org = np.column_stack([xz[:, 0], np.full(len(xz), top), xz[:, 1]])
        dn = np.tile(-UP, (len(org), 1))
        t, ti, fr = w.raycast(org, dn, top - lo[1] + 1)
        mine = (ti >= 0) & (w.obj[np.maximum(ti, 0)] == oi)
        # open: inside the box, but the only things hit are other objects or nothing, while
        # the object surrounds the point on all sides (a hole, not an outside corner)
        for k in np.nonzero(~inside)[0]:
            p = xz[k]
            ring = [footprint_mask(w, oi, np.array([p + dv]))[0] for dv in
                    (np.array([ROOF_STEP * 2, 0]), np.array([-ROOF_STEP * 2, 0]),
                     np.array([0, ROOF_STEP * 2]), np.array([0, -ROOF_STEP * 2]))]
            if all(ring):
                found["open"].append(np.array([p[0], hi[1], p[1]]))
        hy = top - t
        for k in np.nonzero(mine)[0]:
            if not fr[k]:
                found["back"].append(np.array([xz[k, 0], hy[k], xz[k, 1]]))
            elif height > 3.0 and hy[k] < lo[1] + SUNK_FRACTION * height and walled(w, oi, xz[k], hy[k]) \
                    and not on_stair(xz, hy, mine, fr, k):
                found["sunk"].append(np.array([xz[k, 0], hy[k], xz[k, 1]]))
        # oblique flight rays aimed at points of the roof
        tgt = np.column_stack([xz[:, 0], hy, xz[:, 1]])[mine & fr]
        for el in ELEVATIONS:
            for az in AZIMUTHS:
                e, a = math.radians(el), math.radians(az)
                dv = np.array([math.cos(e) * math.cos(a), -math.sin(e), math.cos(e) * math.sin(a)])
                if not len(tgt):
                    continue
                orig = tgt - dv * 80.0
                t2, i2, f2 = w.raycast(orig, np.tile(dv, (len(orig), 1)), 81.0)
                bad = (i2 >= 0) & (w.obj[np.maximum(i2, 0)] == oi) & ~f2
                if bad.any():
                    # a back hit that rays 3 mm to the side meet as a front face is a numerical leak
                    side = np.cross(dv, UP)
                    side /= max(np.linalg.norm(side), 1e-9)
                    keep = []
                    for k in np.nonzero(bad)[0]:
                        ok = [w.raycast(orig[k] + side * s, dv, 81.0)[2][0] for s in (-0.003, 0.003)]
                        if not any(ok):
                            keep.append(orig[k] + dv * t2[k])
                    found["back"] += keep
        n = sum(len(v) for v in found.values())
        total += n
        for kind, pts in found.items():
            if pts:
                rep.add("ERROR", "roof", where_of(w, oi), "%d %s ray(s), e.g. at %s: %s" % (
                    len(pts), kind, fmt(pts[0]), {"open": "a hole in the roof (nothing of the building above)",
                                                    "back": "the flyer sees a back face (open wall top, one-sided roof)",
                                                    "sunk": "a floor seen through a missing roof"}[kind]),
                        kind=kind, rays=len(pts), at=list(map(float, pts[0])))
        rep.add("INFO", "roof", where_of(w, oi), "%d sky points, %d findings" % (int(mine.sum()), n))
    rep.add("INFO", "roof", w.name, "RESULT findings=%d" % total)


# ------------------------------------------------------------------ edge (see-through walls)

def inside_other(w, oi, p):
    for oj, o in enumerate(w.objects):
        if oj == oi or o["box"] is None or o["cls"] == "primitive":
            continue
        lo, hi = o["box"]
        if np.all(p >= lo - 0.05) and np.all(p <= hi + 0.05):
            return True
    return False


def audit_edge(w, rep, objs):
    total = 0
    for oi in objs:
        o = w.objects[oi]
        if o["cls"] not in BUILDINGS or o["box"] is None:
            continue
        lo, hi = o["box"]
        c = (lo + hi) / 2
        eye = lo[1] + EYES[0]
        if eye > hi[1] - 0.2:
            continue
        sides = []
        for axis, sign in ((0, 1), (0, -1), (2, 1), (2, -1)):
            other = 2 - axis
            out = (hi if sign > 0 else lo)[axis] + sign * 2.0
            hits = []
            for f in (0.25, 0.5, 0.75):
                p = np.array(c, float)
                p[axis] = out
                p[other] = lo[other] + (hi[other] - lo[other]) * f
                p[1] = eye
                if inside_other(w, oi, p):
                    continue
                d = np.zeros(3)
                d[axis] = -sign
                reach = abs(out - c[axis])
                t, ti, fr = w.raycast(p, d, reach)
                deep = 2.0 + EDGE_DEPTH * (hi[axis] - lo[axis])
                if ti[0] < 0:
                    hits.append(("open", p))
                elif not fr[0]:
                    hits.append(("back", p + d * t[0]))
                elif w.obj[ti[0]] == oi and t[0] > deep:
                    hits.append(("deep", p + d * t[0]))
            if len(hits) >= 2:
                sides.append((("+" if sign > 0 else "-") + "xyz"[axis], hits))
        total += len(sides)
        for name, hits in sides:
            rep.add("ERROR", "edge", where_of(w, oi), "side %s: eye-height rays see %s (e.g. %s): add the wall or "
                    "close the side" % (name, " / ".join(sorted({h[0] for h in hits})), fmt(hits[0][1])), side=name)
    rep.add("INFO", "edge", w.name, "RESULT open_sides=%d" % total)


# ------------------------------------------------------------------ door

def door_parts(w, oi):
    out = []
    for pi, (o2, p) in enumerate(w.parts):
        if o2 != oi:
            continue
        names = " ".join(p["chain"]) or p["name"].lower()
        if "door" in names and not any(s in names for s in DOOR_SKIP):
            out.append(pi)
    return out


def enterable(w, oi, dc, axis, sign, y, mask):
    """A door leads somewhere when, 1.2 m behind it, rays to the sides, inwards and up meet front faces
    (the inside of a room); inside a solid block they meet back faces or nothing."""
    p = dc.copy()
    p[axis] = dc[axis] - sign * DOOR_IN
    p[1] = y
    dirs = [np.array(v, float) for v in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0))]
    t, ti, fr = w.raycast(np.tile(p, (5, 1)), np.array(dirs), 60.0, mask=mask & (w.obj == oi))
    return int(((ti >= 0) & fr).sum()) >= 3


def audit_door(w, rep, objs):
    doors = blocked = holes = steps = 0
    for oi in objs:
        o = w.objects[oi]
        if o["cls"] not in BUILDINGS or o["box"] is None:
            continue
        olo, ohi = o["box"]
        oc = (olo + ohi) / 2
        for pi in door_parts(w, oi):
            tri = np.nonzero(w.part == pi)[0]
            if not len(tri):
                continue
            lo, hi = w.lo[tri].min(0), w.hi[tri].max(0)
            ext = hi - lo
            axis = 0 if ext[0] < ext[2] else 2      # the door is thin along its walk-through axis
            across = 2 - axis
            dc = (lo + hi) / 2
            sign = 1.0 if dc[axis] >= oc[axis] else -1.0   # outside = away from the building's middle
            name = w.parts[pi][1]["name"]
            ignore = np.isin(w.part, [pi]) | np.isin(w.part, [q for q, (o2, p) in enumerate(w.parts)
                                                              if o2 == oi and any(s in " ".join(p["chain"]) for s in DOOR_SKIP)])
            mask = ~ignore
            if not enterable(w, oi, dc, axis, sign, lo[1] + 1.1, mask):
                rep.add("INFO", "door", where_of(w, oi, name), "decorative door (solid or no room behind it): not walked")
                continue
            doors += 1
            hgt = ext[1]
            half = max(0.0, ext[across] / 2 - 0.15)
            bad = []
            for hy in (0.4, 1.1, min(1.7, hgt - 0.15)):
                for off in (-half, 0.0, half):
                    p = dc.copy()
                    p[1] = lo[1] + hy
                    p[across] += off
                    p[axis] = dc[axis] + sign * DOOR_OUT
                    d = np.zeros(3)
                    d[axis] = -sign
                    t, ti, _ = w.raycast(p, d, DOOR_OUT + DOOR_IN, mask=mask)
                    if ti[0] >= 0:
                        bad.append((p + d * t[0], w.parts[w.part[ti[0]]][1]["name"], w.objects[w.obj[ti[0]]]["id"]))
            if bad:
                blocked += 1
                rep.add("ERROR", "door", where_of(w, oi, name), "BLOCKED: %d of 9 walk-through rays hit %s/%s at %s"
                        % (len(bad), bad[0][2], bad[0][1], fmt(bad[0][0])), kind="blocked")
            # hole above the door: the wall over it must exist
            if ohi[1] > hi[1] + 0.6:
                p = dc.copy()
                p[1] = hi[1] + 0.3
                p[axis] = dc[axis] + sign * DOOR_OUT
                d = np.zeros(3)
                d[axis] = -sign
                t, ti, _ = w.raycast(p, d, DOOR_OUT + DOOR_IN, mask=w.obj == oi)
                if ti[0] < 0:
                    t, ti, _ = w.raycast(p + d * -6.0, d, 6.0 + DOOR_OUT + 3.0, mask=w.obj == oi)
                    if ti[0] < 0:
                        holes += 1
                        rep.add("ERROR", "door", where_of(w, oi, name), "HOLE in the wall above the door at %s" % fmt(p),
                                kind="hole")
            # step: floor outside vs inside the door
            ys = []
            for s in (DOOR_OUT * 0.5, -DOOR_IN * 0.8):
                p = dc.copy()
                p[axis] = dc[axis] + sign * s
                p[1] = lo[1] + 1.0
                t, ti, _ = w.raycast(p, -UP, 3.0, mask=mask)
                ys.append(p[1] - t[0] if ti[0] >= 0 else None)
            if None not in ys and abs(ys[0] - ys[1]) > MAX_STEP:
                steps += 1
                rep.add("ERROR", "door", where_of(w, oi, name), "STEP: floor %.2f m outside, %.2f m inside (%.2f m > %.2f): "
                        "add a step or ramp" % (ys[0], ys[1], abs(ys[0] - ys[1]), MAX_STEP), kind="step")
            elif None in ys:
                rep.add("WARN", "door", where_of(w, oi, name), "no floor found %s the door" % ("outside" if ys[0] is None else "inside"))
    rep.add("INFO", "door", w.name, "RESULT %s blocked=%d holes=%d steps=%d doors=%d"
            % ("ok" if not (blocked or holes or steps) else "fail", blocked, holes, steps, doors))


# ------------------------------------------------------------------ dark bake

def baked_light(w, oi):
    """(part index, image, uv key, kind) for every baked part of the object."""
    o = w.objects[oi]
    m = o["model"]
    if m is None:
        return []
    out = []
    mats = m.glb.g.get("materials", [])
    lm = m.path.with_name(m.path.stem + ".lightmap.png")
    lm_img = None
    if lm.is_file():
        from PIL import Image
        im = Image.open(lm)
        if im.mode == "LA":
            la = np.asarray(im, np.float32) / 255.0
            lm_img = np.dstack([la[:, :, 0], la[:, :, 1], np.zeros_like(la[:, :, 0])])
        else:
            lm_img = np.asarray(im.convert("RGB"), np.float32) / 255.0
    for pi, (o2, p) in enumerate(w.parts):
        if o2 != oi:
            continue
        if lm_img is not None and p["uv1"] is not None:
            out.append((pi, lm_img, "uv1", "lightmap"))
            continue
        mi = p["material"]
        md = mats[mi] if mi is not None and mi < len(mats) else {}
        tex = (md.get("pbrMetallicRoughness") or {}).get("baseColorTexture")
        if "KHR_materials_unlit" in (md.get("extensions") or {}) and tex is not None:
            img = m.image(tex["index"])
            if img is not None:
                out.append((pi, img, "uv1" if tex.get("texCoord", 0) == 1 else "uv0", "unlit"))
    return out


def dark_mask(img, kind, inside=None):
    """Near-black texels that are part of a spot. A line one or two texels wide (a seam at a UV
    island border, the fringe of texels half under a ridge cap) is filtering, not a black spot,
    and is dropped: a core texel has dark texels on both sides across and on both sides along,
    and a spot is its cores with every dark texel around them, so a 3 x 3 spot keeps its full
    area (erosion alone would count only its centre). `inside` marks the texels the mesh uses;
    the empty atlas around the islands is black too, and must not make the island borders a spot."""
    if kind == "lightmap":
        dark = (img[:, :, 0] <= DARK_SKY) & (img[:, :, 1] <= DARK_SUN)
    else:
        dark = img.max(2) <= DARK_UNLIT
    if inside is not None:
        dark &= inside
    p = np.pad(dark, 1)
    core = dark & p[1:-1, :-2] & p[1:-1, 2:] & p[:-2, 1:-1] & p[2:, 1:-1]
    c = np.pad(core, 1)
    h, w = dark.shape
    near = np.zeros_like(dark)
    for dy in range(3):
        for dx in range(3):
            near |= c[dy:dy + h, dx:dx + w]
    return dark & near


def tri_texels(px, h, wd):
    """Texel centres inside one triangle given in pixel coordinates: x, y, barycentrics (or None)."""
    lo = np.clip(np.floor(px.min(0)).astype(int), 0, [wd - 1, h - 1])
    hi = np.clip(np.ceil(px.max(0)).astype(int), 1, [wd, h])
    xs, ys = np.meshgrid(np.arange(lo[0], hi[0]) + 0.5, np.arange(lo[1], hi[1]) + 0.5)
    xs, ys = xs.ravel(), ys.ravel()
    p0, p1, p2 = px
    dd = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
    if abs(dd) < 1e-9:
        return None
    l0 = ((p1[1] - p2[1]) * (xs - p2[0]) + (p2[0] - p1[0]) * (ys - p2[1])) / dd
    l1 = ((p2[1] - p0[1]) * (xs - p2[0]) + (p0[0] - p2[0]) * (ys - p2[1])) / dd
    l2 = 1 - l0 - l1
    ins = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
    if not ins.any():
        return None   # thinner than a texel (a trim strip): it shows its neighbours' light, a seam
    return xs[ins], ys[ins], l0[ins], l1[ins], l2[ins]


def sample_dark(tris, uv, img, kind):
    """Dark texels on sky-facing triangles: list of (world point, m2 per texel, triangle normal)."""
    h, wd = img.shape[:2]
    fn = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    area = np.linalg.norm(fn, axis=1) / 2
    ny = fn[:, 1] / np.maximum(2 * area, 1e-12)
    texels = {}
    inside = np.zeros((h, wd), bool)
    for k in np.nonzero(area > 1e-6)[0]:
        t = tri_texels(uv[k] * np.array([wd, h]), h, wd)
        if t is None:
            continue
        inside[np.clip(t[1].astype(int), 0, h - 1), np.clip(t[0].astype(int), 0, wd - 1)] = True
        if ny[k] >= UP_Y:
            texels[k] = t
    mask = dark_mask(img, kind, inside)
    out = []
    for k, (xs, ys, l0, l1, l2) in texels.items():
        dark = mask[np.clip(ys.astype(int), 0, h - 1), np.clip(xs.astype(int), 0, wd - 1)]
        per = area[k] / len(xs)
        for j in np.nonzero(dark)[0]:
            out.append((l0[j] * tris[k, 0] + l1[j] * tris[k, 1] + l2[j] * tris[k, 2], per, fn[k] / (2 * area[k])))
    return out


def covered(w, dark):
    """Which dark texels no viewer can see: from the texel, no line of sight reaches the open.
    Rays leave each texel along its normal and in rings tilted up to HIDDEN_TILTS degrees from
    it; a texel whose every ray meets a surface within HIDDEN_FAR is covered (a wall top under the
    eaves, a roof under a ridge cap or inside a turret, the top of a plinth core under its cap).
    The bake cannot light such texels and nobody sees them, so they are not reported."""
    if not dark:
        return np.zeros(0, bool)
    allp = np.array([d[0] for d in dark])
    alln = np.array([d[2] for d in dark])
    # one test per 0.1 m cell and facing: neighbouring texels share the verdict
    key = np.hstack([np.floor(allp / HIDDEN_CELL), np.round(alln * 10)])
    _, first, back = np.unique(key, axis=0, return_index=True, return_inverse=True)
    pts, nrm = allp[first], alln[first]
    side = np.cross(nrm, np.where(np.abs(nrm[:, 1:2]) < 0.9, UP, [1.0, 0.0, 0.0]))
    side /= np.linalg.norm(side, axis=1)[:, None]
    other = np.cross(nrm, side)
    dirs = [nrm]
    for tilt, n in HIDDEN_TILTS:
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * (n % 2)) / n
            dirs.append(nrm * math.cos(math.radians(tilt))
                        + (side * math.cos(a) + other * math.sin(a)) * math.sin(math.radians(tilt)))
    hidden = np.ones(len(pts), bool)
    # rays in 4 m groups, so each raycast only tests the triangles near its group
    _, grp = np.unique(np.floor(pts / 4.0), axis=0, return_inverse=True)
    grp = grp.ravel()
    for g in range(grp.max() + 1):
        mine = np.nonzero(grp == g)[0]
        for d in dirs:
            idx = mine[hidden[mine]]
            if not len(idx):
                break
            t, _, _ = w.raycast(pts[idx] + nrm[idx] * 0.005, d[idx], HIDDEN_FAR)
            hidden[idx[~np.isfinite(t)]] = False
    return hidden[back.ravel()]


def audit_dark_bake(w, rep, objs):
    try:
        import PIL  # noqa: F401
    except ImportError:
        rep.add("WARN", "dark-bake", w.name, "Pillow not installed: dark-bake skipped")
        return
    total, baked_objs = 0.0, 0
    for oi in objs:
        parts = baked_light(w, oi)
        if not parts:
            continue
        baked_objs += 1
        dark = []
        for pi, img, key, kind in parts:
            tri = np.nonzero(w.part == pi)[0]
            uv = w.parts[pi][1][key]
            if uv is None or not len(tri):
                continue
            dark += sample_dark(w.tris[tri], uv, img, kind)
        # an object that can be entered (a door part, class interior) is seen from inside too
        enter = w.objects[oi]["cls"] == "interior" or bool(door_parts(w, oi))
        hid = np.zeros(len(dark), bool) if enter else covered(w, dark)
        hidden_m2 = sum(d[1] for d, h in zip(dark, hid) if h)
        dark = [d for d, h in zip(dark, hid) if not h]
        # patches: 0.5 m cells, 8-connected in x/z
        cells = {}
        for p, a, _ in dark:
            k = (int(math.floor(p[0] / 0.5)), int(math.floor(p[1] / 1.0)), int(math.floor(p[2] / 0.5)))
            c = cells.setdefault(k, [0.0, p])
            c[0] += a
        seen, patches = set(), []
        for k in cells:
            if k in seen:
                continue
            stack, area, at = [k], 0.0, cells[k][1]
            seen.add(k)
            while stack:
                q = stack.pop()
                area += cells[q][0]
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            n = (q[0] + dx, q[1] + dy, q[2] + dz)
                            if n in cells and n not in seen:
                                seen.add(n)
                                stack.append(n)
            patches.append((area, at))
        for area, at in sorted(patches, key=lambda x: -x[0]):
            if area >= MIN_PATCH_M2:
                total += area
                rep.add("ERROR", "dark-bake", where_of(w, oi), "%.2f m2 near-black baked patch on a sky-facing surface at %s: "
                        "check what shades it, the lightmap UVs (overlap, padding) and rebake" % (area, fmt(at)),
                        area_m2=round(area, 3), at=list(map(float, at)))
        rep.add("INFO", "dark-bake", where_of(w, oi), "%d baked part(s), %.3f m2 dark, %.3f m2 dark but covered (not seen)"
                % (len(parts), sum(a for a, _ in patches), hidden_m2))
    ao = sky_ao_objects(w, objs)
    if ao:
        rep.add("INFO", "dark-bake", w.name, "time-independent sky/AO bake (COLOR_0, lit materials) on %d object(s): %s"
                % (len(ao), ", ".join(ao[:8]) + (" ..." if len(ao) > 8 else "")))
    clock = float(w.environment.get("day_length_minutes", 0) or 0) > 0
    if clock and baked_objs:
        rep.add("WARN", "dark-bake", w.name, "the clock runs (day_length_minutes %g) but %d object(s) carry an unlit "
                "time-of-day bake, right at one hour only: bake them with bake_vertex_ao.py instead "
                "(kit/style/lighting/README.md, A running clock)" % (w.environment["day_length_minutes"], baked_objs))
    if not baked_objs and not ao:
        rep.add("INFO", "dark-bake", w.name, "no baked light in this world (no unlit bake, no <model>.lightmap.png, "
                "no sky/AO bake): nothing to check")
        if clock:
            rep.add("WARN", "dark-bake", w.name, "the clock runs and nothing is baked: the low tier draws no shadows, so "
                    "static models float; give them the time-independent AO bake (bake_vertex_ao.py, "
                    "lighting.py ao-args for neighbours)")
    rep.add("INFO", "dark-bake", w.name, "RESULT dark_m2=%.3f baked_objects=%d sky_ao_objects=%d"
            % (total, baked_objs, len(ao)))


def sky_ao_objects(w, objs):
    """Ids of objects whose model carries the time-independent bake of kit/blender/bake_vertex_ao.py
    (asset.extras.iamar_bake.kind == "sky_ao")."""
    out = []
    for oi in objs:
        m = w.objects[oi]["model"]
        if m is None:
            continue
        mark = ((m.glb.g.get("asset") or {}).get("extras") or {}).get("iamar_bake")
        if isinstance(mark, dict) and mark.get("kind") == "sky_ao":
            out.append(str(w.objects[oi].get("id") or m.path.name))
    return out


RUN = {"closure": audit_closure, "zfight": audit_zfight, "roof": audit_roof, "edge": audit_edge,
       "door": audit_door, "dark-bake": audit_dark_bake}


def audit_flat_wall(targets, rep):
    """flat_wall.py judges a whole target (it reads the style profile and the scene's water itself)."""
    import flat_wall
    for t in targets:
        r = flat_wall.run([t])
        for i in r["items"]:
            data = {k: v for k, v in i.items() if k not in ("level", "where", "message")}
            rep.add(i["level"], "flat-wall", i["where"], i["message"], **data)
        # one RESULT line per target, like the other audits (gen.py --check keeps only RESULT lines)
        if r["checked"]:
            rep.add("INFO", "flat-wall", Path(t).name, "RESULT longest_m=%.1f over=%d" % (
                max([i["run_m"] for i in r["items"] if "run_m" in i] or [0.0]),
                sum(1 for i in r["items"] if i["level"] == "ERROR" and "run_m" in i)))


def run(names, targets, lod="0", cls=None) -> Report:
    rep = Report()
    if "flat-wall" in names:
        audit_flat_wall(targets, rep)
    names = [n for n in names if n != "flat-wall"]
    for t in targets:
        p = Path(t)
        try:
            levels = meshworld.world_levels(p) if lod == "all" and (p.is_dir() or p.suffix.lower() == ".glb") else [0]
            if p.is_dir():
                worlds = [meshworld.load_world(p, str(k)) for k in levels]
            elif p.suffix.lower() == ".glb":
                worlds = [meshworld.load_models([p], str(k), cls) for k in levels]
            else:
                rep.add("ERROR", "file", t, "not a world folder or .glb")
                continue
        except (OSError, ValueError, KeyError) as e:
            rep.add("ERROR", "file", t, "cannot read: %s" % e)
            continue
        for k, w in zip(levels, worlds):
            if len(levels) > 1:
                w.name += "@LOD%d" % k
            objs = [i for i, o in enumerate(w.objects) if o["cls"] != "primitive"]
            for n in names:
                RUN[n](w, rep, objs)
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("audit", help="one of %s, or all" % ", ".join(AUDITS))
    ap.add_argument("targets", nargs="+", help="world folder(s) or .glb file(s)")
    ap.add_argument("--lod", default="0", choices=["0", "all"], help="audit LOD0 only (default) or every LOD level, each on its own")
    ap.add_argument("--class", dest="cls", help="asset class for .glb targets (building, landmark, prop ...)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--quiet", action="store_true", help="only WARN and ERROR lines (and RESULT lines)")
    a = ap.parse_args(argv)
    names = list(AUDITS) if a.audit == "all" else [a.audit]
    if any(n not in AUDITS for n in names):
        print("iamar-world audit: unknown audit %r (one of %s, or all)" % (a.audit, ", ".join(AUDITS)), file=sys.stderr)
        return 2
    rep = run(names, a.targets, a.lod, a.cls)
    errs = rep.errors()
    if a.json:
        print(json.dumps({"audits": names, "ok": not errs, "items": rep.items}, indent=1))
    else:
        for i in rep.items:
            if a.quiet and i["level"] == "INFO" and "RESULT" not in i["message"]:
                continue
            print("%-5s %s [%s] %s" % (i["level"], i["where"], i["audit"], i["message"]))
        print("%s audit %s: %d error(s), %d warning(s)" % ("FAIL" if errs else "OK", "+".join(names), len(errs),
                                                          sum(1 for i in rep.items if i["level"] == "WARN")))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
