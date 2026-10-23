"""Closure audit of a model: open edges, holes, non-manifold edges and inside-out parts.

The visibility rule of the iamar city (kit recipe `open_edge_check`): anything a player can see
must be closed. A wall top with no roof on it, a gap between a roof and its wall, a
floating panel or an inside-out part shows the back of a face or the void behind it.
This is the per-model version of the city's closure audit (the iamar browser source (not public)
tools/masterplan_closure_audit.gd): it welds by position, finds boundary edges, counts
an edge as sealed where another surface of the model passes within --ring of it (a roof
resting on a wall top, a wall standing on a floor), and reports the rest. It does not
judge visibility from player positions: skip parts no player can see past with --skip,
or seal the edges that sit on the terrain with --ground.

    iamar-world blender-run kit/blender/closure_audit.py -- model.glb [options]

Options:
  --weld M          weld distance before the edge count (default 0.002, as the city)
  --min-edge M      ignore boundary edges shorter than this (default 0.12, as the city)
  --ring M          a surface within this of an edge seals it (default 0.03)
  --ground H        edges at or below height H (glTF y, metres) sit on the ground: sealed
  --skip PATTERNS   comma-separated object or mesh name patterns not audited, e.g.
                    "ground*,card_*" (flat ground tiles and alpha cards are open on purpose;
                    they still seal edges of the others)
  --max-open N      allowed open edges before the audit fails (default 0)
  --allow-nonmanifold  report but do not fail on edges shared by 3+ faces
  --report FILE     write everything as JSON (default: print only)
  --top N           list the N longest open edges and the N longest non-manifold edges (default 20)

Prints CLOSURE <object> lines, OPEN_EDGE and NONMANIFOLD_EDGE lines (length and glTF position;
the report lists them all), then CLOSURE_OK or CLOSURE_FAIL, and exits 1 on a fail,
so it can gate a build. Positions are glTF coordinates (y up).

Blender 4.2-4.5 (tested 4.5 LTS). No add-ons.
"""
import fnmatch
import json
import os
import sys

import bmesh
import bpy
from mathutils.bvhtree import BVHTree

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402

SAMPLES = (0.25, 0.5, 0.75)        # points along an edge that must all be sealed


def parse():
    p = K.make_parser("closure_audit.py", __doc__.split("\n\n")[0])
    p.add_argument("input")
    p.add_argument("--weld", type=float, default=0.002)
    p.add_argument("--min-edge", type=float, default=0.12)
    p.add_argument("--ring", type=float, default=0.03)
    p.add_argument("--ground", type=float, default=None)
    p.add_argument("--skip", default="")
    p.add_argument("--max-open", type=int, default=0)
    p.add_argument("--allow-nonmanifold", action="store_true")
    p.add_argument("--report", metavar="FILE")
    p.add_argument("--top", type=int, default=20)
    return K.parse_args(p)


def world_bmesh(ob, weld):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=weld)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    return bm


def islands(bm):
    """Face islands joined through manifold edges: list of face lists."""
    seen = set()
    out = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, part = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            part.append(g)
            for e in g.edges:
                if len(e.link_faces) != 2:
                    continue
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        out.append(part)
    return out


def signed_volume(faces):
    v = 0.0
    for f in faces:
        cs = [l.vert.co for l in f.loops]
        for i in range(1, len(cs) - 1):
            v += cs[0].dot(cs[i].cross(cs[i + 1])) / 6.0
    return v


def gltf(co):
    return [round(co.x, 3), round(co.z, 3), round(-co.y, 3)]


def main():
    a = parse()
    K.reset()
    obs = K.meshes(K.import_glb(a.input))
    if not obs:
        K.fail("no mesh in %s" % a.input)
    pats = [p.strip() for p in a.skip.split(",") if p.strip()]

    def skipped(ob):
        return any(fnmatch.fnmatch(ob.name, p) or fnmatch.fnmatch(ob.data.name, p) for p in pats)

    bms = {ob.name: world_bmesh(ob, a.weld) for ob in obs}
    trees = {n: BVHTree.FromBMesh(bm) for n, bm in bms.items() if bm.faces}
    rep = {"input": a.input, "weld_m": a.weld, "min_edge_m": a.min_edge, "ring_m": a.ring,
           "ground_y": a.ground, "skip": pats, "objects": [], "open_edges": [], "nonmanifold_edges": []}
    totals = {"boundary": 0, "open": 0, "open_length_m": 0.0, "nonmanifold": 0, "inverted_islands": 0,
              "degenerate_faces": 0}
    for ob in obs:
        name = ob.name
        bm = bms[name]
        if skipped(ob):
            rep["objects"].append({"name": name, "skipped": True})
            K.log("CLOSURE", name, "skipped")
            continue
        boundary = [e for e in bm.edges if len(e.link_faces) == 1]
        nonman = [e for e in bm.edges if len(e.link_faces) > 2]
        degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
        opened = []
        for e in boundary:
            length = e.calc_length()
            if length < a.min_edge:
                continue
            own = {f.index for f in e.link_faces}
            v0, v1 = e.verts[0].co, e.verts[1].co
            sealed_all = True
            for t in SAMPLES:
                p = v0.lerp(v1, t)
                if a.ground is not None and p.z <= a.ground + a.ring:
                    continue
                sealed = False
                for other, tree in trees.items():
                    hits = tree.find_nearest_range(p, a.ring)
                    if other != name:
                        if hits:
                            sealed = True
                    elif any(h[2] not in own for h in hits):
                        sealed = True
                    if sealed:
                        break
                if not sealed:
                    sealed_all = False
                    break
            if not sealed_all:
                opened.append((length, e))
        inverted = 0
        for part in islands(bm):
            closed = all(len(e.link_faces) == 2 for f in part for e in f.edges)
            if closed and signed_volume(part) < -1e-9:
                inverted += 1
        open_len = sum(l for l, _ in opened)
        row = {"name": name, "triangles": K.tris([ob]), "boundary_edges": len(boundary), "open_edges": len(opened),
               "open_length_m": round(open_len, 3), "nonmanifold_edges": len(nonman),
               "inverted_islands": inverted, "degenerate_faces": degenerate}
        rep["objects"].append(row)
        for length, e in opened:
            mid = (e.verts[0].co + e.verts[1].co) / 2
            rep["open_edges"].append({"object": name, "length_m": round(length, 3), "at": gltf(mid),
                                      "from": gltf(e.verts[0].co), "to": gltf(e.verts[1].co)})
        for e in nonman:
            mid = (e.verts[0].co + e.verts[1].co) / 2
            rep["nonmanifold_edges"].append({"object": name, "length_m": round(e.calc_length(), 3),
                                             "faces": len(e.link_faces), "at": gltf(mid),
                                             "from": gltf(e.verts[0].co), "to": gltf(e.verts[1].co)})
        totals["boundary"] += len(boundary)
        totals["open"] += len(opened)
        totals["open_length_m"] += open_len
        totals["nonmanifold"] += len(nonman)
        totals["inverted_islands"] += inverted
        totals["degenerate_faces"] += degenerate
        K.log("CLOSURE", name, "boundary=%d open=%d (%.2f m) nonmanifold=%d inverted=%d degenerate=%d"
              % (len(boundary), len(opened), open_len, len(nonman), inverted, degenerate))
    rep["open_edges"].sort(key=lambda r: -r["length_m"])
    for r in rep["open_edges"][:a.top]:
        K.log("OPEN_EDGE", r["object"], "%.2f m at" % r["length_m"], r["at"])
    rep["nonmanifold_edges"].sort(key=lambda r: -r["length_m"])
    for r in rep["nonmanifold_edges"][:a.top]:
        K.log("NONMANIFOLD_EDGE", r["object"], "%.2f m shared by %d faces at" % (r["length_m"], r["faces"]), r["at"])
    totals["open_length_m"] = round(totals["open_length_m"], 3)
    rep["totals"] = totals
    why = []
    if totals["open"] > a.max_open:
        why.append("%d open edges (allowed %d)" % (totals["open"], a.max_open))
    if totals["inverted_islands"]:
        why.append("%d inside-out parts" % totals["inverted_islands"])
    if totals["nonmanifold"] and not a.allow_nonmanifold:
        why.append("%d non-manifold edges" % totals["nonmanifold"])
    rep["result"] = "fail" if why else "ok"
    rep["why"] = why
    if a.report:
        with open(a.report, "w") as f:
            json.dump(rep, f, indent=1)
    for bm in bms.values():
        bm.free()
    if why:
        K.log("CLOSURE_FAIL", a.input, "; ".join(why))
        sys.stdout.flush()
        sys.exit(1)
    K.log("CLOSURE_OK", a.input, "open=%d nonmanifold=%d inverted=0" % (totals["open"], totals["nonmanifold"]))


K.run(main)
