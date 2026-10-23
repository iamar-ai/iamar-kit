"""World geometry for the kit audits: every triangle of a world folder (scene.json objects and
box/plane primitives) or of loose .glb files, in world space, with what it belongs to.

    from meshworld import load_world, load_models
    w = load_world(Path("my_world"))          # or load_models([Path("house.glb")])
    t, tri, front = w.raycast(origins, dirs, max_t)

Triangles come from LOD0 (a node or mesh named *_LOD<k> with k > 0 is skipped); lod="<k>"
takes level k, lod="all" keeps every level and records it in w.lod. glTF front faces are counter-clockwise; a
material with doubleSided=true makes both sides front (w.double). Needs numpy.
"""
from __future__ import annotations

import io
import copy
import json
import math
from pathlib import Path
import re
import sys

import numpy as np

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "lint"))
sys.path.insert(0, str(KIT / "style"))
import style_lint  # noqa: E402  (Glb reader, node matrices, model classes)

LOD_RE = re.compile(r"_LOD(\d+)$", re.I)
NP_TYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def accessor(g: style_lint.Glb, i: int) -> np.ndarray:
    a = g.g["accessors"][i]
    n = NCOMP[a["type"]]
    dt = np.dtype(NP_TYPES[a["componentType"]])
    if "bufferView" not in a:
        return np.zeros((a["count"], n), np.float32)
    v = g.g["bufferViews"][a["bufferView"]]
    base = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = v.get("byteStride") or dt.itemsize * n
    raw = np.frombuffer(g.bin, np.uint8, count=stride * (a["count"] - 1) + dt.itemsize * n, offset=base)
    rows = np.lib.stride_tricks.as_strided(raw, (a["count"], dt.itemsize * n), (stride, 1))
    out = np.ascontiguousarray(rows).view(dt).reshape(a["count"], n).astype(np.float64)
    if a.get("normalized"):
        out /= float(np.iinfo(dt).max)
    return out


def euler_yxz(deg) -> np.ndarray:
    """scene.json rotation in degrees (x, y, z), applied like Godot's default (Y, then X, then Z)."""
    x, y, z = (math.radians(float(v)) for v in (list(deg) + [0, 0, 0])[:3])
    rx = np.array([[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]])
    ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    rz = np.array([[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]])
    return ry @ rx @ rz


def object_matrix(o: dict) -> np.ndarray:
    m = np.eye(4)
    s = o.get("scale", 1)
    s = np.array(s if isinstance(s, list) else [s, s, s], float)
    m[:3, :3] = euler_yxz(o.get("rotation", [0, 0, 0])) * s
    m[:3, 3] = np.array(o.get("position", [0, 0, 0]), float)
    return m


def box_tris(size, centre) -> np.ndarray:
    lo = np.array(centre, float) - np.array(size, float) / 2
    hi = lo + np.array(size, float)
    out = []
    for face in style_lint_box_faces():
        q = [np.where(np.array(c, bool), hi, lo) for c in face]
        out += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
    return np.array(out)


def style_lint_box_faces():
    # same corner order as kit/tests/lint/glb_fixture.py BOX_FACES (outward, counter-clockwise)
    return [[(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)], [(1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0)],
            [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)], [(1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)],
            [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)], [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]]


class Model:
    """One .glb in its own space: triangles per node, materials, UVs."""

    def __init__(self, path: Path, lod: str = "0"):
        self.path = path
        self.glb = g = style_lint.Glb(path)
        names = g.node_names()
        mats = g.g.get("materials", [])
        self.parts = []   # dicts: node, root, name, lod, tris (n,3,3), uv0, uv1 (n,3,2) or None, material
        self.levels = set()   # every LOD level the model has
        # several models in one file (`style-gen street`): root nodes with extras x-class
        self.part_roots = g.part_roots()
        root_of = g.root_of()
        for ni, node, m in g.instances():
            chain = names.get(ni, [])
            level = 0
            for nm in chain:
                hit = LOD_RE.search(nm or "")
                if hit:
                    level = int(hit.group(1))
                    break
            self.levels.add(level)
            if lod != "all" and level != int(lod):
                continue
            mat = np.array(m, float).reshape(4, 4).T
            for p in g.g["meshes"][node["mesh"]]["primitives"]:
                if p.get("mode", 4) != 4 or "POSITION" not in p["attributes"]:
                    continue
                pos = accessor(g, p["attributes"]["POSITION"])
                pos = pos @ mat[:3, :3].T + mat[:3, 3]
                idx = (accessor(g, p["indices"]).astype(np.int64).ravel() if "indices" in p
                       else np.arange(len(pos)))
                idx = idx[: len(idx) // 3 * 3].reshape(-1, 3)
                if np.linalg.det(mat[:3, :3]) < 0:   # mirrored node: glTF flips the winding
                    idx = idx[:, ::-1]
                uv = {}
                for k in ("TEXCOORD_0", "TEXCOORD_1"):
                    if k in p["attributes"]:
                        uv[k] = accessor(g, p["attributes"][k])[idx]
                mi = p.get("material")
                md = mats[mi] if mi is not None and mi < len(mats) else {}
                self.parts.append({"node": ni, "root": root_of.get(ni), "name": node.get("name") or "/".join(c for c in chain if c),
                                   "chain": [c.lower() for c in chain if c], "lod": level, "tris": pos[idx],
                                   "uv0": uv.get("TEXCOORD_0"), "uv1": uv.get("TEXCOORD_1"),
                                   "material": mi, "double": bool(md.get("doubleSided"))})

    def split(self) -> list[tuple[str, str, "Model"]]:
        """(name, class, model of that root node's parts) per part root; [] for an ordinary model."""
        out = []
        for ri, name, cls in self.part_roots:
            sub = copy.copy(self)
            sub.parts = [p for p in self.parts if p.get("root") == ri]
            sub.part_roots = []
            out.append((name, cls, sub))
        tagged = {ri for ri, _, _ in self.part_roots}
        rest = [p for p in self.parts if p.get("root") not in tagged]
        if self.part_roots and rest:   # root nodes without x-class are drawn too: audit them together
            sub = copy.copy(self)
            sub.parts, sub.part_roots = rest, []
            out.append(("untagged", None, sub))
        return out

    def image(self, tex_index: int):
        """A glTF texture as a float RGB(A) array (0-1), or None."""
        try:
            from PIL import Image
        except ImportError:
            return None
        t = self.glb.g.get("textures", [])[tex_index]
        raw = self.glb.image_bytes(t.get("source", 0))
        if raw is None:
            uri = self.glb.g["images"][t.get("source", 0)].get("uri")
            if not uri or uri.startswith("data:"):
                return None
            raw = (self.path.parent / uri).read_bytes()
        im = Image.open(io.BytesIO(raw))
        return np.asarray(im.convert("RGB"), np.float32) / 255.0


class World:
    def __init__(self, name: str):
        self.name = name
        self.objects = []   # dicts: id, asset, model (Model or None), cls, matrix, box (lo, hi)
        a, part, obj, dbl, lod = [], [], [], [], []
        self._a, self._part, self._obj, self._dbl, self._lod = a, part, obj, dbl, lod
        self.parts = []     # (object index, part dict)
        self.spawns = []
        self.quests = []    # scene.json "quests": quest dicts (id, on_complete.show/hide)
        self.environment = {}  # scene.json "environment" (time_of_day, day_length_minutes, ...)

    def add(self, oid: str, asset: str, model: Model | None, matrix: np.ndarray, cls: str, tris=None, double=False):
        oi = len(self.objects)
        lo = hi = None
        chunks = []
        if model is not None:
            for p in model.parts:
                t = p["tris"] @ matrix[:3, :3].T + matrix[:3, 3]
                if np.linalg.det(matrix[:3, :3]) < 0:
                    t = t[:, ::-1]
                chunks.append((p, t))
        else:
            chunks.append(({"node": -1, "name": oid, "chain": [oid.lower()], "lod": 0, "uv0": None, "uv1": None,
                            "material": None, "double": double}, tris))
        for p, t in chunks:
            pi = len(self.parts)
            self.parts.append((oi, p))
            self._a.append(t)
            self._part.append(np.full(len(t), pi))
            self._obj.append(np.full(len(t), oi))
            self._dbl.append(np.full(len(t), p["double"]))
            self._lod.append(np.full(len(t), p["lod"]))
            if len(t):
                lo = t.reshape(-1, 3).min(0) if lo is None else np.minimum(lo, t.reshape(-1, 3).min(0))
                hi = t.reshape(-1, 3).max(0) if hi is None else np.maximum(hi, t.reshape(-1, 3).max(0))
        self.objects.append({"id": oid, "asset": asset, "model": model, "cls": cls, "matrix": matrix,
                             "box": (lo, hi) if lo is not None else None})
        return oi

    def finish(self):
        self.tris = np.concatenate(self._a) if self._a else np.zeros((0, 3, 3))
        self.part = np.concatenate(self._part).astype(np.int64) if self._part else np.zeros(0, np.int64)
        self.obj = np.concatenate(self._obj).astype(np.int64) if self._obj else np.zeros(0, np.int64)
        self.double = np.concatenate(self._dbl).astype(bool) if self._dbl else np.zeros(0, bool)
        self.lod = np.concatenate(self._lod).astype(np.int64) if self._lod else np.zeros(0, np.int64)
        e1 = self.tris[:, 1] - self.tris[:, 0]
        e2 = self.tris[:, 2] - self.tris[:, 0]
        n = np.cross(e1, e2)
        ln = np.linalg.norm(n, axis=1)
        self.area = ln / 2
        self.normal = n / np.maximum(ln, 1e-12)[:, None]
        self.lo = self.tris.min(1)
        self.hi = self.tris.max(1)
        return self

    # ---------------------------------------------------------------- queries

    def raycast(self, o: np.ndarray, d: np.ndarray, max_t, mask: np.ndarray | None = None,
                chunk: int = 400_000):
        """First hit of each ray (o + t d, 0 < t <= max_t; d need not be unit).
        Returns t (inf on a miss), triangle index (-1) and front (True when the ray meets the
        triangle's front side or the material is double-sided). Ties within 1 mm go to front faces."""
        o = np.atleast_2d(np.asarray(o, float))
        d = np.atleast_2d(np.asarray(d, float))
        r = len(o)
        mt = np.broadcast_to(np.asarray(max_t, float), (r,))
        best = np.full(r, np.inf)
        best_i = np.full(r, -1, np.int64)
        best_f = np.zeros(r, bool)
        cand = np.arange(len(self.tris)) if mask is None else np.nonzero(mask)[0]
        if not len(cand) or not r:
            return best, best_i, best_f
        # cull triangles by the rays' joint box, then chunk rays x triangles
        end = o + d * mt[:, None]
        blo, bhi = np.minimum(o, end).min(0) - 1e-3, np.maximum(o, end).max(0) + 1e-3
        keep = np.all((self.hi[cand] >= blo) & (self.lo[cand] <= bhi), axis=1)
        cand = cand[keep]
        if not len(cand):
            return best, best_i, best_f
        step = max(1, chunk // max(1, len(cand)))
        a = self.tris[cand, 0]
        e1 = self.tris[cand, 1] - a
        e2 = self.tris[cand, 2] - a
        nrm = self.normal[cand]
        dbl = self.double[cand]
        for s in range(0, r, step):
            oo, dd, mm = o[s:s + step, None, :], d[s:s + step, None, :], mt[s:s + step, None]
            p = np.cross(dd, e2[None])
            det = np.einsum("rtk,tk->rt", p, e1)
            ok = np.abs(det) > 1e-12
            inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
            tv = oo - a[None]
            u = np.einsum("rtk,rtk->rt", tv, p) * inv
            q = np.cross(tv, e1[None])
            v = np.einsum("rk,rtk->rt", dd[:, 0], q) * inv
            t = np.einsum("tk,rtk->rt", e2, q) * inv
            eps = 1e-7
            hit = ok & (u >= -eps) & (v >= -eps) & (u + v <= 1 + eps) & (t > 1e-6) & (t <= mm)
            t = np.where(hit, t, np.inf)
            front = (np.einsum("rk,tk->rt", dd[:, 0], nrm) < 0) | dbl[None]
            tmin = t.min(1)
            # ties: prefer a front face within 1 mm (in units of |d|) of the nearest hit
            dl = np.linalg.norm(dd[:, 0], axis=1)
            near = t <= (tmin + 1e-3 / np.maximum(dl, 1e-9))[:, None]
            fr_near = near & front
            pick = np.where(fr_near.any(1), np.argmax(np.where(fr_near, -t, -np.inf), 1), np.argmin(t, 1))
            rows = np.arange(len(tmin))
            got = np.isfinite(tmin)
            sl = slice(s, s + len(tmin))
            best[sl] = np.where(got, tmin, np.inf)
            best_i[sl] = np.where(got, cand[pick], -1)
            best_f[sl] = got & front[rows, pick]
        return best, best_i, best_f

    def point_tri_dist(self, pts: np.ndarray, idx: np.ndarray) -> np.ndarray:
        """Distance from each point to each triangle in idx: (P, len(idx))."""
        a, b, c = self.tris[idx, 0][None], self.tris[idx, 1][None], self.tris[idx, 2][None]
        p = np.asarray(pts, float)[:, None, :]
        ab, ac, ap = b - a, c - a, p - a
        n = np.cross(ab, ac)
        nn = np.maximum(np.einsum("ptk,ptk->pt", n, n), 1e-18)
        # inside the prism: plane distance
        c1 = np.einsum("ptk,ptk->pt", np.cross(ab, ap), n)
        c2 = np.einsum("ptk,ptk->pt", np.cross(c - b, p - b), n)
        c3 = np.einsum("ptk,ptk->pt", np.cross(a - c, p - c), n)
        inside = (c1 >= 0) & (c2 >= 0) & (c3 >= 0)
        plane = np.abs(np.einsum("ptk,ptk->pt", ap, n)) / np.sqrt(nn)

        def seg(x, y):
            xy = y - x
            t = np.clip(np.einsum("ptk,ptk->pt", p - x, xy) / np.maximum(np.einsum("ptk,ptk->pt", xy, xy), 1e-18), 0, 1)
            return np.linalg.norm(p - (x + xy * t[..., None]), axis=2)

        edge = np.minimum(np.minimum(seg(a, b), seg(b, c)), seg(c, a))
        return np.where(inside, plane, edge)

    def ground_y(self, x: float, z: float, top: float = 1e4) -> float | None:
        t, i, _ = self.raycast([[x, top, z]], [[0, -1, 0]], 2 * top)
        return None if i[0] < 0 else top - t[0]


def classify(oid: str, asset: str, size, given: str | None, path: Path | None = None) -> str:
    """The lint's model class; a file copied from the kit catalogue keeps its catalogue class."""
    budgets = {k: 1 for k in ("building", "landmark", "prop", "creature", "character", "hero_statue", "tree",
                              "plant", "furniture", "interior", "structure", "vehicle")}
    entry = style_lint.catalogue_entry(path) if path is not None and not given and path.is_file() else None
    return style_lint.classify(asset or oid, list(size), given, budgets, entry)[0]


def world_levels(world: Path) -> list[int]:
    """Every LOD level any model of a world folder (or a .glb) has."""
    if world.suffix.lower() == ".glb":
        return sorted(Model(world).levels)
    scene = json.loads((world / "scene.json").read_text(encoding="utf-8"))
    out = {0}
    for a in {o.get("asset", "") for o in scene.get("objects") or []}:
        p = world / a
        if p.is_file() and p.suffix.lower() == ".glb":
            out |= Model(p).levels
    return sorted(out)


def terrain_tris(world: Path, t: dict) -> np.ndarray | None:
    """The ground mesh of a `terrain` section (`flat` or `heightmap`), as the browser builds it:
    `resolution` vertices per side over `size`, heights from the greyscale image (top row = -Z edge,
    left column = -X edge). Procedural terrain is the browser's noise and is not audited."""
    kind = t.get("type", "none")
    px, py, pz = (list(t.get("position") or [0, 0, 0]) + [0, 0, 0])[:3]
    sx, sz = (list(t.get("size") or [256, 256]) + [256, 256])[:2]
    if kind == "flat":
        q = np.array([[-sx / 2, 0, sz / 2], [sx / 2, 0, sz / 2], [sx / 2, 0, -sz / 2], [-sx / 2, 0, -sz / 2]])
        return np.array([[q[0], q[1], q[2]], [q[0], q[2], q[3]]]) + [px, py, pz]
    if kind != "heightmap" or not t.get("heightmap"):
        return None
    try:
        from PIL import Image
        img = np.asarray(Image.open(world / t["heightmap"]).convert("L"), float) / 255.0
    except (OSError, ImportError, ValueError):
        return None
    n = max(2, min(int(t.get("resolution", 129)), 1025))
    lo, hi = float(t.get("min_height", 0)), float(t.get("max_height", 10))
    ii = np.rint(np.linspace(0, img.shape[0] - 1, n)).astype(int)
    jj = np.rint(np.linspace(0, img.shape[1] - 1, n)).astype(int)
    y = py + lo + img[np.ix_(ii, jj)] * (hi - lo)
    xs = px - sx / 2 + sx * np.arange(n) / (n - 1)
    zs = pz - sz / 2 + sz * np.arange(n) / (n - 1)
    v = np.stack([np.broadcast_to(xs, (n, n)), y, np.broadcast_to(zs[:, None], (n, n))], axis=-1)
    a, b, c, d = v[:-1, :-1], v[:-1, 1:], v[1:, 1:], v[1:, :-1]   # a=(-x,-z) b=(+x,-z) c=(+x,+z) d=(-x,+z)
    return np.concatenate([np.stack([a, d, c], 2).reshape(-1, 3, 3), np.stack([a, c, b], 2).reshape(-1, 3, 3)])


def load_world(world: Path, lod: str = "0") -> World:
    scene = json.loads((world / "scene.json").read_text(encoding="utf-8"))
    w = World(world.resolve().name)
    w.root = world.resolve()
    try:
        manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    reused = {str(r.get("path", "")): r for r in (manifest.get("reused") or []) if isinstance(r, dict)}
    cache: dict[str, Model | None] = {}
    for o in scene.get("objects") or []:
        asset = o.get("asset", "")
        vr = o.get("visible_range", 0)
        if isinstance(vr, (int, float)) and 0 < vr < 0.5:
            continue   # collision-only proxy, never drawn
        p = world / asset
        if not p.is_file() and asset in reused:
            p = style_lint.reused_file(reused[asset])[0] or p   # reused by hash: the kit's copy
        if asset not in cache:
            cache[asset] = Model(p, lod) if p.is_file() and p.suffix.lower() == ".glb" else None
        model = cache[asset]
        if model is None:
            continue
        m = object_matrix(o)
        if model.part_roots:   # one audit object per model in the file, with its own class
            for name, cls, sub in model.split():
                oi = w.add("%s/%s" % (o.get("id", asset), name), asset, sub, m, cls or "")
                w.objects[oi]["part"] = name
                if not cls:
                    box = w.objects[oi]["box"]
                    w.objects[oi]["cls"] = classify(str(o.get("id", "")), asset, (box[1] - box[0]) if box else np.zeros(3),
                                                    o.get("x-class"), p)
            continue
        oi = w.add(str(o.get("id", asset)), asset, model, m, "")
        box = w.objects[oi]["box"]
        size = (box[1] - box[0]) if box else np.zeros(3)
        w.objects[oi]["cls"] = classify(str(o.get("id", "")), asset, size, o.get("x-class"), p)
    for pr in scene.get("primitives") or []:
        shape = pr.get("shape")
        if pr.get("visible") is False:
            continue
        col = pr.get("color")
        if isinstance(col, str) and len(col) == 9 and col[7:] == "00":
            continue   # fully transparent: an invisible collision proxy, never drawn
        m = object_matrix(pr)
        if shape == "box":
            t = box_tris(pr.get("size", [1, 1, 1]), [0, 0, 0])
        elif shape == "plane":
            sx, sz = (pr.get("size", [1, 1]) + [1, 1])[:2] if isinstance(pr.get("size"), list) else (1, 1)
            q = np.array([[-sx / 2, 0, sz / 2], [sx / 2, 0, sz / 2], [sx / 2, 0, -sz / 2], [-sx / 2, 0, -sz / 2]])
            t = np.array([[q[0], q[1], q[2]], [q[0], q[2], q[3]]])
        else:
            continue   # spheres, cylinders: closed analytic shapes, nothing to audit
        t = t @ m[:3, :3].T + m[:3, 3]
        w.add("primitive:" + str(pr.get("id", shape)), "", None, m, "primitive", tris=t)
    terrain = terrain_tris(world, scene.get("terrain") or {})
    if terrain is not None:
        w.add("primitive:terrain", "", None, np.eye(4), "primitive", tris=terrain)
    for s in scene.get("spawn_points") or []:
        w.spawns.append(np.array(s.get("position", [0, 0, 0]), float))
    w.quests = [q for q in (scene.get("quests") or []) if isinstance(q, dict)]
    env = scene.get("environment")
    w.environment = env if isinstance(env, dict) else {}
    return w.finish()


def load_models(paths: list[Path], lod: str = "0", cls: str | None = None) -> World:
    """Loose .glb files, each at the origin of its own audit (they are not placed together)."""
    w = World(", ".join(p.name for p in paths))
    for p in paths:
        model = Model(p, lod)
        if model.part_roots:
            for name, pcls, sub in model.split():
                oi = w.add("%s/%s" % (p.stem, name), p.name, sub, np.eye(4), cls or pcls or "")
                w.objects[oi]["part"] = name
                if not (cls or pcls):
                    box = w.objects[oi]["box"]
                    w.objects[oi]["cls"] = classify(p.stem, p.name, (box[1] - box[0]) if box else np.zeros(3), cls, p)
            continue
        oi = w.add(p.stem, p.name, model, np.eye(4), "")
        box = w.objects[oi]["box"]
        w.objects[oi]["cls"] = classify(p.stem, p.name, (box[1] - box[0]) if box else np.zeros(3), cls, p)
    return w.finish()
