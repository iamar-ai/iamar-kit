"""A small mesh builder and binary glTF writer for the style generators (pure Python).

The city's builders (the iamar browser source (not public) scripts/world/masterplan/mp_*.gd) emit triangles through
MeshKit and MpBuildings._tri_facing / _quad_facing: every triangle is wound so it faces a
given direction, and faces nobody can see are never emitted. This is the same contract in
Python, so the ports read like their originals:

    m = Mesh()
    m.quad("wall", a, b, c, d, facing)      # wound to face `facing`
    m.box("timber", centre, size, basis, back=False)   # back face (-z of basis) left out
    m.beam("timber", a, b, 0.10)            # square beam from a to b, closed
    write_glb(path, {"house_LOD0": m, "house_LOD1": m1}, materials)

UVs are planar per triangle (the dominant axis of its normal), 1 UV unit = `tile_m` metres,
matching the painted layers of `kit/style/check_style.py --paint` (4 m per tile).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct

Vec = tuple


def v3(x, y, z):
    return (float(x), float(y), float(z))


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def norm(a):
    ln = length(a)
    return (0.0, 0.0, 0.0) if ln < 1e-12 else (a[0] / ln, a[1] / ln, a[2] / ln)


UP = (0.0, 1.0, 0.0)
DOWN = (0.0, -1.0, 0.0)


def basis_facing(normal):
    """(x, y, z) axes with z = normal (horizontal), y = up, x = y cross z (Buildings._basis_facing)."""
    z = norm((normal[0], 0.0, normal[2]))
    if length(z) < 0.5:
        z = (0.0, 0.0, 1.0)
    x = norm(cross(UP, z))
    return (x, UP, z)


def at_basis(b, c, x, y, z):
    return (c[0] + b[0][0] * x + b[1][0] * y + b[2][0] * z,
            c[1] + b[0][1] * x + b[1][1] * y + b[2][1] * z,
            c[2] + b[0][2] * x + b[1][2] * y + b[2][2] * z)


class Mesh:
    def __init__(self, tile_m: float = 4.0):
        self.tris: dict[str, list] = {}   # material -> [(p0, p1, p2), ...]
        self.tile_m = tile_m

    def count(self) -> int:
        return sum(len(t) for t in self.tris.values())

    def extend(self, other: "Mesh"):
        for mat, ts in other.tris.items():
            self.tris.setdefault(mat, []).extend(ts)

    def tri(self, mat, a, b, c, facing=None):
        n = cross(sub(b, a), sub(c, a))
        if length(n) < 1e-9:
            return
        if facing is not None and dot(n, facing) < 0.0:
            b, c = c, b
        self.tris.setdefault(mat, []).append((a, b, c))

    def quad(self, mat, a, b, c, d, facing=None):
        self.tri(mat, a, b, c, facing)
        self.tri(mat, a, c, d, facing)

    def poly(self, mat, pts, facing=None):
        """A convex polygon as a fan."""
        for i in range(1, len(pts) - 1):
            self.tri(mat, pts[0], pts[i], pts[i + 1], facing)

    def box(self, mat, c, size, b=None, back=True, bottom=True, top=True):
        """Box centred on c with half sizes along basis b; back=False leaves out its -z face."""
        b = b or ((1.0, 0.0, 0.0), UP, (0.0, 0.0, 1.0))
        hx, hy, hz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
        P = lambda x, y, z: at_basis(b, c, x * hx, y * hy, z * hz)
        faces = [((0, 0, 1), [P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1)]),
                 ((1, 0, 0), [P(1, -1, 1), P(1, -1, -1), P(1, 1, -1), P(1, 1, 1)]),
                 ((-1, 0, 0), [P(-1, -1, -1), P(-1, -1, 1), P(-1, 1, 1), P(-1, 1, -1)])]
        if top:
            faces.append(((0, 1, 0), [P(-1, 1, 1), P(1, 1, 1), P(1, 1, -1), P(-1, 1, -1)]))
        if bottom:
            faces.append(((0, -1, 0), [P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1)]))
        if back:
            faces.append(((0, 0, -1), [P(1, -1, -1), P(-1, -1, -1), P(-1, 1, -1), P(1, 1, -1)]))
        for f, q in faces:
            self.quad(mat, q[0], q[1], q[2], q[3], at_basis(b, (0, 0, 0), *f))

    def beam(self, mat, a, b, thick, ends=True):
        """A closed square beam from a to b (MeshKit.beam)."""
        d = sub(b, a)
        ln = length(d)
        if ln < 1e-4:
            return
        z = mul(d, 1.0 / ln)
        ref = UP if abs(z[1]) < 0.9 else (1.0, 0.0, 0.0)
        x = norm(cross(ref, z))
        y = cross(z, x)
        h = thick * 0.5
        ring = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        pa = [add(a, add(mul(x, sx * h), mul(y, sy * h))) for sx, sy in ring]
        pb = [add(b, add(mul(x, sx * h), mul(y, sy * h))) for sx, sy in ring]
        for i in range(4):
            j = (i + 1) % 4
            mid = add(mul(x, ring[i][0] + ring[j][0]), mul(y, ring[i][1] + ring[j][1]))
            self.quad(mat, pa[i], pa[j], pb[j], pb[i], mid)
        if ends:
            self.poly(mat, pa, mul(z, -1.0))
            self.poly(mat, pb, z)

    def prism(self, mat, base, radius, height, sides, top=True, bottom=False):
        """Upright prism (a finial, a post)."""
        pts0, pts1 = [], []
        for i in range(sides):
            a = math.tau * (i + 0.5) / sides
            pts0.append((base[0] + math.cos(a) * radius, base[1], base[2] + math.sin(a) * radius))
            pts1.append((base[0] + math.cos(a) * radius, base[1] + height, base[2] + math.sin(a) * radius))
        for i in range(sides):
            j = (i + 1) % sides
            a = math.tau * (i + 1.0) / sides
            self.quad(mat, pts0[i], pts0[j], pts1[j], pts1[i], (math.cos(a), 0.0, math.sin(a)))
        if top:
            self.poly(mat, pts1, UP)
        if bottom:
            self.poly(mat, pts0, DOWN)


# ------------------------------------------------------------------ glTF

def srgb_to_linear(v: float) -> float:
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def hex_rgb(h: str):
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


def _uv(p, n, tile):
    ax = max(range(3), key=lambda i: abs(n[i]))
    if ax == 1:
        return (p[0] / tile, p[2] / tile)
    if ax == 0:
        return (p[2] / tile, -p[1] / tile)
    return (p[0] / tile, -p[1] / tile)


def write_glb(path: Path, nodes: dict, materials: dict, textures: dict | None = None,
              extras: dict | None = None, colors: dict | None = None, placements: dict | None = None,
              node_extras: dict | None = None) -> dict:
    """nodes: name -> Mesh (one node and mesh each, a primitive per material).
    materials: name -> {"color": "#rrggbb", "roughness": 0.9, "tint": the texture's own colour,
               "emissive": "#rrggbb", "emissive_strength": 3.0 (optional: a glowing light source)}.
    textures: material name -> PNG bytes (embedded as its base colour texture; the same bytes
              are embedded once however many materials use them).
    colors: node name -> {material name: linear (r, g, b)}: written as COLOR_0 on that node's
            primitive (glTF multiplies it into the base colour), e.g. a street's per-house tints.
    placements: node name -> (x, y, z, yaw degrees about +Y): the node's translation and rotation.
    node_extras: node name -> dict written as the node's extras (e.g. {"x-class": "building"}).
    Returns {node name: triangles}."""
    textures = textures or {}
    colors = colors or {}
    placements = placements or {}
    node_extras = node_extras or {}
    bin_ = bytearray()
    views, accessors, meshes, gnodes = [], [], [], []
    mat_names = sorted({m for mesh in nodes.values() for m in mesh.tris})
    mat_index = {m: i for i, m in enumerate(mat_names)}
    images, gtex = [], []

    def view(data: bytes, target=None) -> int:
        while len(bin_) % 4:
            bin_.append(0)
        v = {"buffer": 0, "byteOffset": len(bin_), "byteLength": len(data)}
        if target:
            v["target"] = target
        bin_.extend(data)
        views.append(v)
        return len(views) - 1

    counts = {}
    for name, mesh in nodes.items():
        prims = []
        for mat in sorted(mesh.tris):
            pos, nrm, uv = [], [], []
            for a, b, c in mesh.tris[mat]:
                n = norm(cross(sub(b, a), sub(c, a)))
                for p in (a, b, c):
                    pos.append(p)
                    nrm.append(n)
                    uv.append(_uv(p, n, mesh.tile_m))
            if not pos:
                continue
            pv = view(b"".join(struct.pack("<3f", *p) for p in pos), 34962)
            accessors.append({"bufferView": pv, "componentType": 5126, "count": len(pos), "type": "VEC3",
                              "min": [min(p[i] for p in pos) for i in range(3)],
                              "max": [max(p[i] for p in pos) for i in range(3)]})
            nv = view(b"".join(struct.pack("<3f", *p) for p in nrm), 34962)
            accessors.append({"bufferView": nv, "componentType": 5126, "count": len(nrm), "type": "VEC3"})
            tv = view(b"".join(struct.pack("<2f", *t) for t in uv), 34962)
            accessors.append({"bufferView": tv, "componentType": 5126, "count": len(uv), "type": "VEC2"})
            k = len(accessors)
            attrs = {"POSITION": k - 3, "NORMAL": k - 2, "TEXCOORD_0": k - 1}
            col = (colors.get(name) or {}).get(mat)
            if col is not None:
                cv = view(struct.pack("<3f", *col) * len(pos), 34962)
                accessors.append({"bufferView": cv, "componentType": 5126, "count": len(pos), "type": "VEC3"})
                attrs["COLOR_0"] = len(accessors) - 1
            prims.append({"attributes": attrs, "material": mat_index[mat], "mode": 4})
        counts[name] = mesh.count()
        meshes.append({"name": name, "primitives": prims})
        gn = {"name": name, "mesh": len(meshes) - 1}
        if name in placements:
            x, y, z, yaw = placements[name]
            h = math.radians(float(yaw)) / 2.0
            gn["translation"] = [float(x), float(y), float(z)]
            if abs(h) > 1e-9:
                gn["rotation"] = [0.0, math.sin(h), 0.0, math.cos(h)]
        if node_extras.get(name):
            gn["extras"] = node_extras[name]
        gnodes.append(gn)
    gmats, ext_used = [], set()
    tex_of: dict = {}
    for m in mat_names:
        spec = materials.get(m, {})
        rgb = hex_rgb(spec.get("color", "#cccccc"))
        pbr = {"baseColorFactor": [srgb_to_linear(c) for c in rgb] + [1.0],
               "metallicFactor": 0.0, "roughnessFactor": float(spec.get("roughness", 0.9))}
        if m in textures:
            if textures[m] not in tex_of:     # one image and texture per distinct map
                iv = view(textures[m])
                images.append({"bufferView": iv, "mimeType": "image/png", "name": m})
                gtex.append({"source": len(images) - 1})
                tex_of[textures[m]] = len(gtex) - 1
            pbr["baseColorTexture"] = {"index": tex_of[textures[m]]}
            # the painted layer is tinted to the layer's colour: the factor carries what this material
            # differs by (a door paint on the timber layer), clamped to 1
            tint = hex_rgb(spec.get("tint") or spec.get("color", "#ffffff"))
            pbr["baseColorFactor"] = [min(1.0, srgb_to_linear(c) / max(1e-4, srgb_to_linear(t)))
                                      for c, t in zip(rgb, tint)] + [1.0]
        mat = {"name": m, "pbrMetallicRoughness": pbr}
        if spec.get("emissive"):
            if spec.get("emissive_strength"):
                # a light source (lantern glass): full emissive colour, made brighter than 1 with
                # KHR_materials_emissive_strength (the browser's glTF import reads it)
                mat["emissiveFactor"] = [srgb_to_linear(c) for c in hex_rgb(spec["emissive"])]
                mat["extensions"] = {"KHR_materials_emissive_strength": {"emissiveStrength": float(spec["emissive_strength"])}}
                ext_used.add("KHR_materials_emissive_strength")
            else:
                mat["emissiveFactor"] = [srgb_to_linear(c) * 0.25 for c in hex_rgb(spec["emissive"])]
        gmats.append(mat)
    gltf = {"asset": {"version": "2.0", "generator": "iamar-kit style/gen"},
            "scene": 0, "scenes": [{"nodes": list(range(len(gnodes)))}],
            "nodes": gnodes, "meshes": meshes, "materials": gmats,
            "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(bin_)}]}
    if ext_used:
        gltf["extensionsUsed"] = sorted(ext_used)
    if images:
        gltf["images"] = images
        gltf["textures"] = gtex
        gltf["samplers"] = [{"wrapS": 10497, "wrapT": 10497}]
        for t in gtex:
            t["sampler"] = 0
    if extras:
        gltf["asset"]["extras"] = extras
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    while len(bin_) % 4:
        bin_.append(0)
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bytes(bin_)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(out)
    return counts

