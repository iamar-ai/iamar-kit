#!/usr/bin/env python3
"""Seal the single-sheet trim edges of the catalogue's city houses: give each open sheet a back.

  python3 kit/catalog/assets/seal_trim_edges.py            # seal buildings/*.glb in place, update the sources
  python3 kit/catalog/assets/seal_trim_edges.py --check    # every house is sealed (nothing left to add)

The city builds trim as single sheets: a window sill's front strip, a plinth face that stops
above the ground, a dormer cheek, a chimney's walls with no top. In the city the neighbours and
the street hide their open edges; a catalogue house standing alone shows them edge-on from eye
height, and past such an edge the player looks at the sheet's culled back (open sky through
the house), which 'iamar-world audit closure' reports (an internal task: 8.35 m on b124).

This step finds the same edges the audit does, with the same numbers (kit/audit/audit.py
"closure": edges used by one triangle, vertices welded at 2 mm, at least 12 cm long, with no
other triangle within 3 cm of a sample every 0.6 m), and gives the sheet each one belongs to a
back side: the sheet's triangles (the edge's triangle and every coplanar neighbour reached
across shared edges, normals within 10 degrees) are copied with the winding reversed and the
normal turned round, appended to the same mesh as one more primitive with the same material,
vertex colours and UVs. The edge is then shared by front and back, so it is no longer open,
and the sheet reads as a thin plate from both sides. Edges on a house's recorded open side
(the party wall: sources/city_buildings.json "open_sides") are left alone; the closed variant
(close_open_sides.py) walls that side up instead.

Run order: import_city_buildings.py and close_open_sides.py call seal() on the files they
write; this command reseals the files in place and rewrites the sha256, bytes and triangle
counts in both sources, then close_open_sides.py rebuilds the variants from the sealed
originals. A sheet the model already backs (a face turned the other way overlapping it in the
same plane, which a copy would z-fight with) gets no copy; its edges are not open to the audit
either, since that face lies within 3 cm of them. A sealed file has nothing left to seal, so the
step is idempotent and --check fails only when a sheet still lacks its back.
Python 3.8+, standard library only.
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
from close_open_sides import (CSIZE, CFMT, FLOAT, NCOMP, U32, _cross, _dot, _inv_affine,  # noqa: E402
                              _pt, _sub, mesh_nodes, parse_glb, read_accessor, write_glb)

CATALOG_DIR = HERE.parent
SOURCE = CATALOG_DIR / "sources" / "city_buildings.json"
CLOSED = CATALOG_DIR / "sources" / "city_buildings_closed.json"

WELD = 0.002        # kit/audit/audit.py closure numbers
MIN_EDGE = 0.12
RING_R = 0.03
SAMPLE_STEP = 0.6
SHEET_COS = math.cos(math.radians(10.0))   # a sheet's triangles face within 10 degrees ...
SHEET_D = 0.01                             # ... and lie within 1 cm of one plane
OPEN_SIDE_DEPTH = 0.6   # edges this close to a recorded open side's plane stay open
CELL = 0.5
BACKED_D = 0.02      # a face turned the other way in the same plane (audit zfight: 2 cm, 0.002 m2) ...
BACKED_AREA = 0.002  # ... overlapping a triangle this much already backs it
AXES = {"+x": (0, 1.0), "-x": (0, -1.0), "+z": (2, 1.0), "-z": (2, -1.0)}


# ------------------------------------------------------------------ geometry

def _norm(v):
    ln = math.sqrt(_dot(v, v))
    return (v[0] / ln, v[1] / ln, v[2] / ln) if ln > 1e-12 else (0.0, 0.0, 0.0)


def _seg_dist2(p, a, b):
    ab = _sub(b, a)
    t = _dot(_sub(p, a), ab) / max(_dot(ab, ab), 1e-18)
    t = min(1.0, max(0.0, t))
    q = (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t)
    d = _sub(p, q)
    return _dot(d, d)


def point_tri_dist(p, a, b, c) -> float:
    n = _cross(_sub(b, a), _sub(c, a))
    nn = _dot(n, n)
    if nn < 1e-18:
        return math.sqrt(min(_seg_dist2(p, a, b), _seg_dist2(p, b, c), _seg_dist2(p, c, a)))
    ap = _sub(p, a)
    s = _dot(ap, n) / nn
    q = (p[0] - n[0] * s, p[1] - n[1] * s, p[2] - n[2] * s)
    inside = all(_dot(_cross(_sub(v1, v0), _sub(q, v0)), n) >= 0 for v0, v1 in ((a, b), (b, c), (c, a)))
    if inside:
        return abs(s) * math.sqrt(nn)
    return math.sqrt(min(_seg_dist2(p, a, b), _seg_dist2(p, b, c), _seg_dist2(p, c, a)))


def load_all(j: dict, binary: bytes):
    """Every triangle of every triangle primitive in file coordinates: list of
    (corners, (node, prim index, i0, i1, i2)), plus per (node, prim) its attributes and matrix."""
    tris, prims = [], {}
    for ni, m in mesh_nodes(j):
        mesh = j["meshes"][j["nodes"][ni]["mesh"]]
        for pi, p in enumerate(mesh["primitives"]):
            if p.get("mode", 4) != 4:
                continue
            attrs = {k: read_accessor(j, binary, v) for k, v in p["attributes"].items()}
            pos = [_pt(m, q) for q in attrs["POSITION"]]
            idx = [r[0] for r in read_accessor(j, binary, p["indices"])] if "indices" in p else list(range(len(pos)))
            prims[(ni, pi)] = (attrs, m, p)
            for k in range(0, len(idx) - 2, 3):
                i0, i1, i2 = idx[k], idx[k + 1], idx[k + 2]
                tris.append(((pos[i0], pos[i1], pos[i2]), (ni, pi, i0, i1, i2)))
    return tris, prims


def open_edges(tris):
    """[(tri, a, b)] for the edges the audit calls open: used by one triangle (welded), long
    enough, with no other triangle within RING_R of some sample along them."""
    key = lambda p: (round(p[0] / WELD), round(p[1] / WELD), round(p[2] / WELD))
    count, owner = {}, {}
    for ti, (c, _) in enumerate(tris):
        k = [key(v) for v in c]
        for e in range(3):
            a, b = k[e], k[(e + 1) % 3]
            if a == b:
                continue
            s = (a, b) if a < b else (b, a)
            count[s] = count.get(s, 0) + 1
            owner[s] = (ti, e)
    grid = {}
    for ti, (c, _) in enumerate(tris):
        lo = [min(v[i] for v in c) - RING_R for i in range(3)]
        hi = [max(v[i] for v in c) + RING_R for i in range(3)]
        for x in range(math.floor(lo[0] / CELL), math.floor(hi[0] / CELL) + 1):
            for y in range(math.floor(lo[1] / CELL), math.floor(hi[1] / CELL) + 1):
                for z in range(math.floor(lo[2] / CELL), math.floor(hi[2] / CELL) + 1):
                    grid.setdefault((x, y, z), []).append(ti)
    out = []
    for s, n in count.items():
        if n != 1:
            continue
        ti, e = owner[s]
        c = tris[ti][0]
        a, b = c[e], c[(e + 1) % 3]
        ln = math.sqrt(_dot(_sub(b, a), _sub(b, a)))
        if ln < MIN_EDGE:
            continue
        k = max(1, int(round(ln / SAMPLE_STEP)))
        for q in range(k):
            f = (q + 0.5) / k
            p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f)
            cell = (math.floor(p[0] / CELL), math.floor(p[1] / CELL), math.floor(p[2] / CELL))
            if not any(t != ti and point_tri_dist(p, *tris[t][0]) <= RING_R for t in grid.get(cell, ())):
                out.append((ti, a, b))
                break
    return out


def on_open_side(a, b, sides, lo, hi) -> bool:
    for s in sides:
        ax, sg = AXES[s["faces"]]
        plane = hi[ax] if sg > 0 else lo[ax]
        if all(abs(v[ax] - plane) <= OPEN_SIDE_DEPTH for v in (a, b)):
            return True
    return False


def sheet(tris, seed, adj):
    """The seed triangle and its coplanar neighbours across shared edges."""
    def plane(ti):
        c = tris[ti][0]
        n = _norm(_cross(_sub(c[1], c[0]), _sub(c[2], c[0])))
        return n, _dot(n, c[0])

    n0, d0 = plane(seed)
    out, todo = {seed}, [seed]
    while todo:
        t = todo.pop()
        for u in adj.get(t, ()):
            if u in out:
                continue
            n, _ = plane(u)
            if _dot(n, n0) >= SHEET_COS and all(abs(_dot(n0, v) - d0) <= SHEET_D for v in tris[u][0]):
                out.add(u)
                todo.append(u)
    return out


def adjacency(tris):
    key = lambda p: (round(p[0] / WELD), round(p[1] / WELD), round(p[2] / WELD))
    by_edge = {}
    for ti, (c, _) in enumerate(tris):
        k = [key(v) for v in c]
        for e in range(3):
            a, b = k[e], k[(e + 1) % 3]
            by_edge.setdefault((a, b) if a < b else (b, a), []).append(ti)
    adj = {}
    for ts in by_edge.values():
        for t in ts:
            adj.setdefault(t, set()).update(u for u in ts if u != t)
    return adj


def overlap_area(p, q, n) -> float:
    """Area of the overlap of two coplanar triangles with plane normal n (kit/audit/audit.py clip_overlap)."""
    ax = max(range(3), key=lambda i: abs(n[i]))
    keep = [i for i in range(3) if i != ax]
    P = [(v[keep[0]], v[keep[1]]) for v in p]
    Q = [(v[keep[0]], v[keep[1]]) for v in q]

    def area(poly):
        return 0.5 * sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))

    if area(P) < 0:
        P = P[::-1]
    if area(Q) < 0:
        Q = Q[::-1]
    out = P
    for i in range(3):
        a, b = Q[i], Q[(i + 1) % 3]
        side = lambda v: (b[0] - a[0]) * (v[1] - a[1]) - (b[1] - a[1]) * (v[0] - a[0])
        inp, out = out, []
        for k in range(len(inp)):
            cur, prv = inp[k], inp[k - 1]
            sc, sp = side(cur), side(prv)
            if sc >= 0:
                if sp < 0:
                    f = sp / (sp - sc)
                    out.append((prv[0] + (cur[0] - prv[0]) * f, prv[1] + (cur[1] - prv[1]) * f))
                out.append(cur)
            elif sp >= 0:
                f = sp / (sp - sc)
                out.append((prv[0] + (cur[0] - prv[0]) * f, prv[1] + (cur[1] - prv[1]) * f))
        if len(out) < 3:
            return 0.0
    return abs(area(out)) / max(abs(n[ax]), 1e-9)


def backed(tris, chosen):
    """Chosen triangles the model already backs: a face turned the other way, in the same plane
    (within BACKED_D), overlaps it by BACKED_AREA or more; a copy there would z-fight with it."""
    def normal(c):
        return _norm(_cross(_sub(c[1], c[0]), _sub(c[2], c[0])))

    grid = {}
    for ti, (c, _) in enumerate(tris):
        for cell in _cells(c, BACKED_D):
            grid.setdefault(cell, []).append(ti)
    out = set()
    for ti in chosen:
        c = tris[ti][0]
        n = normal(c)
        d = _dot(n, c[0])
        cand = {u for cell in _cells(c, BACKED_D) for u in grid.get(cell, ())}
        for u in cand:
            q = tris[u][0]
            if (u != ti and _dot(normal(q), n) <= -SHEET_COS and all(abs(_dot(n, v) - d) <= BACKED_D for v in q)
                    and overlap_area(c, q, n) >= BACKED_AREA):
                out.add(ti)
                break
    return out


def _cells(c, pad):
    lo = [min(v[i] for v in c) - pad for i in range(3)]
    hi = [max(v[i] for v in c) + pad for i in range(3)]
    return [(x, y, z) for x in range(math.floor(lo[0] / CELL), math.floor(hi[0] / CELL) + 1)
            for y in range(math.floor(lo[1] / CELL), math.floor(hi[1] / CELL) + 1)
            for z in range(math.floor(lo[2] / CELL), math.floor(hi[2] / CELL) + 1)]


# ------------------------------------------------------------------ glb out

def append_backs(j: dict, binary: bytes, prims: dict, backs: dict) -> bytes:
    """backs: (node, prim) -> [(i0, i1, i2)] vertex indices of that primitive to copy reversed.
    Appends one primitive per source primitive, with NORMAL (and TANGENT xyz) turned round."""
    binary = bytearray(binary)
    for (ni, pi), faces in sorted(backs.items()):
        attrs, _m, prim = prims[(ni, pi)]
        verts = [v for i0, i1, i2 in faces for v in (i0, i2, i1)]
        new_attrs = {}
        for k, acc_i in prim["attributes"].items():
            src = j["accessors"][acc_i]
            rows = [attrs[k][v] for v in verts]
            if k == "NORMAL":
                rows = [(-r[0], -r[1], -r[2]) for r in rows]
            elif k == "TANGENT":
                rows = [(-r[0], -r[1], -r[2], r[3]) for r in rows]
            c, ct = NCOMP[src["type"]], src["componentType"]
            binary += b"\0" * (-len(binary) % 4)
            off = len(binary)
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
        j["accessors"].append({"bufferView": len(j["bufferViews"]) - 1, "componentType": U32,
                               "count": len(verts), "type": "SCALAR"})
        newp = {"attributes": new_attrs, "indices": len(j["accessors"]) - 1, "mode": 4}
        if "material" in prim:
            newp["material"] = prim["material"]
        j["meshes"][j["nodes"][ni]["mesh"]]["primitives"].append(newp)
    j["buffers"][0]["byteLength"] = len(binary)
    return bytes(binary)


def seal(src: bytes, open_sides=None):
    """(sealed file, info). Unchanged bytes when nothing is left to seal."""
    j, binary = parse_glb(src)
    tris, prims = load_all(j, binary)
    if not tris:
        return src, {"edges": 0, "back_triangles": 0}
    lo = [min(v[i] for c, _ in tris for v in c) for i in range(3)]
    hi = [max(v[i] for c, _ in tris for v in c) for i in range(3)]
    edges = [e for e in open_edges(tris) if not on_open_side(e[1], e[2], open_sides or [], lo, hi)]
    if not edges:
        return src, {"edges": 0, "back_triangles": 0}
    adj = adjacency(tris)
    chosen = set()
    for ti, _a, _b in edges:
        if ti not in chosen:
            chosen |= sheet(tris, ti, adj)
    chosen -= backed(tris, chosen)
    length = sum(math.sqrt(_dot(_sub(b, a), _sub(b, a))) for _t, a, b in edges)
    if not chosen:   # every sheet left is backed already (an earlier seal, or the model's own faces)
        return src, {"edges": len(edges), "edge_m": round(length, 2), "back_triangles": 0}
    backs = {}
    for ti in sorted(chosen):
        ni, pi, i0, i1, i2 = tris[ti][1]
        backs.setdefault((ni, pi), []).append((i0, i1, i2))
    out = write_glb(j, append_backs(j, binary, prims, backs))
    return out, {"edges": len(edges), "edge_m": round(length, 2), "back_triangles": len(chosen)}


# ------------------------------------------------------------------ command

def _rows(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    return d, [r for r in d["models"] if r["file"].startswith("buildings/")]


def build() -> int:
    d, rows = _rows(SOURCE)
    for r in rows:
        p = HERE / r["file"]
        b = p.read_bytes()
        out, info = seal(b, r.get("open_sides"))
        if out != b:
            p.write_bytes(out)
            m = measure(out)
            r.update({"sha256": hashlib.sha256(out).hexdigest(), "bytes": len(out), "triangles": m["triangles"]})
        print("sealed %s: %d open edges (%.2f m), +%d back triangles" % (
            r["file"], info["edges"], info.get("edge_m", 0.0), info["back_triangles"]))
    SOURCE.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("updated %s; now rerun close_open_sides.py (it seals the variants it writes)"
          % SOURCE.relative_to(CATALOG_DIR.parent.parent).as_posix())
    return 0


def check() -> int:
    errs = []
    for path in (SOURCE, CLOSED):
        if not path.is_file():
            continue
        _d, rows = _rows(path)
        for r in rows:
            b = (HERE / r["file"]).read_bytes()
            _out, info = seal(b, r.get("open_sides"))
            if info["back_triangles"]:
                errs.append("%s: %d trim triangles still have no back (rerun seal_trim_edges.py)"
                            % (r["file"], info["back_triangles"]))
    for e in errs:
        print("CHECK " + e)
    print("sealed trim edges: %s" % ("OK" if not errs else "%d problems" % len(errs)))
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
