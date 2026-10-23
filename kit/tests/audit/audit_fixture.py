"""Small binary glTF models for the audit tests and the audit sample world: parts made of boxes
(any face may be left out), one material each, optionally baked (KHR_materials_unlit with a
colour texture, the output shape of kit/blender/bake_unlit.py).

    write_glb(path, [part(name, [box(lo, hi, drop=("top",))], color="#c8b48a", baked=(200, 190, 170))])
    hollow_house(...)  -> parts of an enterable house (floor, walls, doorway, lintel, roof, door leaf)

Pure Python plus the standard library.
"""
from __future__ import annotations

import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lint"))
from glb_fixture import png, srgb_to_linear  # noqa: E402

# outward, counter-clockwise; named for drop=(...)
FACES = {
    "pz": [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
    "nz": [(1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0)],
    "nx": [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],
    "px": [(1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)],
    "top": [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)],
    "bottom": [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
}


def box(lo, hi, drop=()):
    """Triangles of an axis-aligned box as a list of 3 corners each."""
    tris = []
    for name, face in FACES.items():
        if name in drop:
            continue
        q = [[hi[i] if c[i] else lo[i] for i in range(3)] for c in face]
        tris += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
    return tris


def part(name, boxes, color="#b8a888", baked=None, uv1=False):
    """uv1=True adds a TEXCOORD_1 set (a lightmap UV, same layout as TEXCOORD_0)."""
    tris = [t for b in boxes for t in b]
    return {"name": name, "tris": tris, "color": color, "baked": baked, "uv1": uv1}


def write_glb(path, parts):
    bin_ = bytearray()
    views, accessors, meshes, nodes, materials, images, textures = [], [], [], [], [], [], []

    def view(data, target=None):
        while len(bin_) % 4:
            bin_.append(0)
        v = {"buffer": 0, "byteOffset": len(bin_), "byteLength": len(data)}
        if target:
            v["target"] = target
        bin_.extend(data)
        views.append(v)
        return len(views) - 1

    for p in parts:
        pos = [c for t in p["tris"] for c in t]
        # a baked part gets an island wider than a seam (audit dark-bake drops lines 1-2 texels wide)
        uv = ([(0.05, 0.05), (0.95, 0.05), (0.05, 0.95)] if p.get("baked") is not None or p.get("uv1") else [(0.25, 0.25), (0.75, 0.25), (0.5, 0.75)]) * len(p["tris"])
        pv = view(b"".join(struct.pack("<3f", *c) for c in pos), 34962)
        accessors.append({"bufferView": pv, "componentType": 5126, "count": len(pos), "type": "VEC3",
                          "min": [min(c[i] for c in pos) for i in range(3)], "max": [max(c[i] for c in pos) for i in range(3)]})
        pa = len(accessors) - 1
        tv = view(b"".join(struct.pack("<2f", *t) for t in uv), 34962)
        accessors.append({"bufferView": tv, "componentType": 5126, "count": len(uv), "type": "VEC2"})
        ta = len(accessors) - 1
        h = p["color"]
        mat = {"name": p["name"] + "_mat", "pbrMetallicRoughness": {
            "baseColorFactor": [srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5)] + [1.0],
            "metallicFactor": 0.0, "roughnessFactor": 0.9}}
        if p.get("baked") is not None:
            images.append({"bufferView": view(png(8, 8, tuple(p["baked"]))), "mimeType": "image/png"})
            textures.append({"source": len(images) - 1})
            mat["pbrMetallicRoughness"] = {"baseColorFactor": [1, 1, 1, 1], "baseColorTexture": {"index": len(textures) - 1}}
            mat["extensions"] = {"KHR_materials_unlit": {}}
        materials.append(mat)
        attrs = {"POSITION": pa, "TEXCOORD_0": ta}
        if p.get("uv1"):
            attrs["TEXCOORD_1"] = ta
        meshes.append({"name": p["name"], "primitives": [{"attributes": attrs,
                                                         "material": len(materials) - 1}]})
        nodes.append({"name": p["name"], "mesh": len(meshes) - 1})
    while len(bin_) % 4:
        bin_.append(0)
    g = {"asset": {"version": "2.0", "generator": "iamar-kit audit test fixture"},
         "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": meshes,
         "materials": materials, "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(bin_)}]}
    if images:
        g["images"], g["textures"] = images, textures
        g["extensionsUsed"] = ["KHR_materials_unlit"]
    js = json.dumps(g, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    out = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(bin_))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bytes(bin_)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    return path


def hollow_house(w=6.0, d=6.0, h=4.0, t=0.3, door_w=1.2, door_h=2.2, floor_y=0.1, roof=True, roof_drop=(),
                 back_wall=True, lintel=True, roof_baked=(196, 184, 160)):
    """An enterable house, centred on x/z, standing on y=0, its doorway in the +z wall."""
    x0, x1, z0, z1 = -w / 2, w / 2, -d / 2, d / 2
    dl, dr = -door_w / 2, door_w / 2
    front = [box([x0, 0, z1 - t], [dl, h, z1]), box([dr, 0, z1 - t], [x1, h, z1])]
    if lintel:
        front.append(box([dl, floor_y + door_h, z1 - t], [dr, h, z1]))
    walls = [box([x0, 0, z0 + t], [x0 + t, h, z1 - t]), box([x1 - t, 0, z0 + t], [x1, h, z1 - t])]
    if back_wall:
        walls.append(box([x0, 0, z0], [x1, h, z0 + t]))
    parts = [part("Floor", [box([x0 + t, 0, z0 + (t if back_wall else 0)], [x1 - t, floor_y, z1 - t])], "#8a7a62"),
             part("Walls", front + walls, "#d8c8a8"),
             part("Door", [box([dl, floor_y, z1 - t * 0.6], [dr, floor_y + door_h - 0.05, z1 - t * 0.45])], "#6f4526")]
    if roof:
        parts.append(part("Roof", [box([x0 - t, h, z0 - t], [x1 + t, h + 0.3, z1 + t], drop=roof_drop)], "#7a5a48",
                          baked=roof_baked))
    return parts


def scene(objects, ground=60.0):
    return {"format": "iamar-scene", "format_version": 0,
            "primitives": [{"id": "ground", "shape": "box", "size": [ground, 0.5, ground], "position": [0, -0.25, 0],
                            "color": "#8f8a70", "collision": "box"}],
            "spawn_points": [{"id": "default", "position": [0, 0.1, 12], "yaw": 0}],
            "objects": objects}
