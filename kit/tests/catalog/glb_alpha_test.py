#!/usr/bin/env python3
"""No catalogue model cuts itself away with its vertex colour alpha (an internal task).

The browser's package worlds (WorldPackage._glb_vertex_colours) multiply COLOR_0 into the
albedo, alpha included. A material with alphaMode MASK (or BLEND) whose COLOR_0 alpha is
below the cutoff on some vertices discards those faces: the city griffin's shader kept a
pattern code in that alpha (0.0 on 2907 of 3951 vertices) and drew as loose feathers.
Cut-outs belong in the albedo texture's alpha. This scans every .glb under kit/catalog/assets
and fails on any MASK/BLEND primitive with a COLOR_0 vertex alpha under its cutoff, except an
unlit BLEND one: a light effect (a light shaft) that fades out by its vertex alpha on purpose.
Run: python3 kit/tests/catalog/glb_alpha_test.py
"""
import json
import struct
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
ASSETS = KIT / "catalog" / "assets"

# glTF componentType -> (struct code, size, normalised divisor)
COMP = {5126: ("f", 4, 1.0), 5121: ("B", 1, 255.0), 5123: ("H", 2, 65535.0)}


def low_alpha(path: Path) -> list[str]:
    """Primitives of `path` whose COLOR_0 alpha drops below their material's cutoff."""
    b = path.read_bytes()
    if b[:4] != b"glTF":
        return []
    n = struct.unpack_from("<I", b, 12)[0]
    j = json.loads(b[20:20 + n])
    binoff = 20 + n + 8
    out = []
    for mi, mesh in enumerate(j.get("meshes", [])):
        for pi, prim in enumerate(mesh["primitives"]):
            mat = j.get("materials", [{}])[prim["material"]] if "material" in prim else {}
            mode = mat.get("alphaMode", "OPAQUE")
            if mode == "OPAQUE" or "COLOR_0" not in prim["attributes"]:
                continue
            if mode == "BLEND" and "KHR_materials_unlit" in mat.get("extensions", {}):
                continue   # an unlit light effect fading out by its vertex alpha (the library's light shaft)
            a = j["accessors"][prim["attributes"]["COLOR_0"]]
            if a["type"] != "VEC4" or a["componentType"] not in COMP or "bufferView" not in a:
                continue
            code, size, div = COMP[a["componentType"]]
            bv = j["bufferViews"][a["bufferView"]]
            stride = bv.get("byteStride", 4 * size)
            o = binoff + bv.get("byteOffset", 0) + a.get("byteOffset", 0) + 3 * size
            cut = mat.get("alphaCutoff", 0.5) if mode == "MASK" else 0.999
            bad = sum(1 for i in range(a["count"])
                      if struct.unpack_from("<" + code, b, o + i * stride)[0] / div < cut)
            if bad:
                out.append("%s mesh %d prim %d: %s, %d/%d vertices with COLOR_0 alpha < %.2f"
                           % (path.relative_to(KIT), mi, pi, mode, bad, a["count"], cut))
    return out


def main() -> int:
    files = sorted(ASSETS.rglob("*.glb"))
    problems = [p for f in files for p in low_alpha(f)]
    for p in problems:
        print("FAIL", p)
    print("glb_alpha_test: %s (%d files, %d problems)" % ("FAIL" if problems else "OK", len(files), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
