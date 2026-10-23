"""Writes small binary glTF files for the style-lint tests: named boxes, one material each
(a base colour, or an embedded PNG texture), optional LOD suffixes and padded triangle counts.

    write_glb(path, [{"name": "Door", "min": [-0.5, 0, 0], "max": [0.5, 2.2, 0.1], "color": "#6f4526"}, ...])

A part may give "tris": N (the box's 12 triangles are repeated up to N, so budgets can be
tested without big files), "texture": PNG bytes (UVs cover its top-left quarter, like one tile of an atlas) and "lod": k
(the node is named <name>_LOD<k>). Pure Python, no dependencies.
"""
from __future__ import annotations

import json
from pathlib import Path
import struct
import zlib

BOX_FACES = [  # (normal axis, sign, corner order) as 4 corners per face
    [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
    [(1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0)],
    [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],
    [(1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)],
    [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)],
    [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
]


def srgb_to_linear(v: float) -> float:
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def png(width: int, height: int, rgb: tuple[int, int, int] | list) -> bytes:
    """A PNG of one colour, or of a row-major list of (r, g, b) pixels."""
    if isinstance(rgb, tuple):
        rows = [bytes(rgb) * width] * height
    else:
        rows = [b"".join(bytes(p) for p in rgb[y * width:(y + 1) * width]) for y in range(height)]
    raw = b"".join(b"\x00" + r for r in rows)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def write_glb(path: Path, parts: list[dict]) -> Path:
    bin_ = bytearray()
    views, accessors, meshes, nodes, materials, images, textures = [], [], [], [], [], [], []

    def view(data: bytes, target=None) -> int:
        while len(bin_) % 4:
            bin_.append(0)
        v = {"buffer": 0, "byteOffset": len(bin_), "byteLength": len(data)}
        if target:
            v["target"] = target
        bin_.extend(data)
        views.append(v)
        return len(views) - 1

    for part in parts:
        lo, hi = part["min"], part["max"]
        pos, uv, idx = [], [], []
        for face in BOX_FACES:
            base = len(pos)
            for k, c in enumerate(face):
                pos.append([hi[i] if c[i] else lo[i] for i in range(3)])
                uv.append([(0.05, 0.05), (0.45, 0.05), (0.45, 0.45), (0.05, 0.45)][k])
            idx += [base, base + 1, base + 2, base, base + 2, base + 3]
        want = int(part.get("tris", 12))
        while len(idx) // 3 < want:
            idx += idx[:min(len(idx), (want - len(idx) // 3) * 3)]
        pv = view(b"".join(struct.pack("<3f", *p) for p in pos), 34962)
        accessors.append({"bufferView": pv, "componentType": 5126, "count": len(pos), "type": "VEC3",
                          "min": [min(p[i] for p in pos) for i in range(3)], "max": [max(p[i] for p in pos) for i in range(3)]})
        pa = len(accessors) - 1
        tv = view(b"".join(struct.pack("<2f", *t) for t in uv), 34962)
        accessors.append({"bufferView": tv, "componentType": 5126, "count": len(uv), "type": "VEC2"})
        ta = len(accessors) - 1
        iv = view(b"".join(struct.pack("<I", i) for i in idx), 34963)
        accessors.append({"bufferView": iv, "componentType": 5125, "count": len(idx), "type": "SCALAR"})
        ia = len(accessors) - 1
        h = part.get("color", "#cccccc")
        mat = {"name": part["name"] + "_mat", "pbrMetallicRoughness": {
            "baseColorFactor": [srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5)] + [1.0],
            "metallicFactor": 0.0, "roughnessFactor": 0.9}}
        if part.get("texture") is not None:
            images.append({"bufferView": view(part["texture"]), "mimeType": "image/png"})
            textures.append({"source": len(images) - 1})
            mat["pbrMetallicRoughness"]["baseColorFactor"] = [1, 1, 1, 1]
            mat["pbrMetallicRoughness"]["baseColorTexture"] = {"index": len(textures) - 1}
        if part.get("emissive"):
            mat["emissiveFactor"] = [1.0, 0.8, 0.4]
        materials.append(mat)
        meshes.append({"name": part["name"], "primitives": [{"attributes": {"POSITION": pa, "TEXCOORD_0": ta},
                                                             "indices": ia, "material": len(materials) - 1}]})
        name = part["name"] + ("_LOD%d" % part["lod"] if "lod" in part else "")
        nodes.append({"name": name, "mesh": len(meshes) - 1})
    while len(bin_) % 4:
        bin_.append(0)
    g = {"asset": {"version": "2.0", "generator": "iamar-kit style-lint test fixture"},
         "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": meshes,
         "materials": materials, "accessors": accessors, "bufferViews": views,
         "buffers": [{"byteLength": len(bin_)}]}
    if images:
        g["images"], g["textures"] = images, textures
    js = json.dumps(g, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    out = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(bin_))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bytes(bin_)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    return path


def house(roof_rise: float = 3.0, door_h: float = 2.2, wall="#ece1c6", roof="#3e5d8c", door="#6f4526",
          tris: int | None = None, width: float = 8.0, depth: float = 6.0, wall_h: float = 6.4, arch_rise: float | None = None):
    """Parts of a simple house: walls, a roof block, a door and (optionally) a door arch."""
    parts = [
        {"name": "Walls", "min": [-width / 2, 0, -depth / 2], "max": [width / 2, wall_h, depth / 2], "color": wall},
        {"name": "Roof", "min": [-width / 2 - 0.5, wall_h, -depth / 2 - 0.5], "max": [width / 2 + 0.5, wall_h + roof_rise, depth / 2 + 0.5], "color": roof},
        {"name": "Door", "min": [-0.6, 0, depth / 2], "max": [0.6, door_h, depth / 2 + 0.1], "color": door},
    ]
    if arch_rise is not None:
        parts.append({"name": "DoorArch", "min": [-0.9, door_h + 0.24, depth / 2], "max": [0.9, door_h + 0.24 + arch_rise, depth / 2 + 0.17], "color": "#cfc4ae"})
    if tris:
        parts[0]["tris"] = tris - 12 * (len(parts) - 1)
    return parts
