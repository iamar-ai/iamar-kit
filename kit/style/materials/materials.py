#!/usr/bin/env python3
"""Painted material library, texel-density rule and texture budget check (job A10).

    python3 kit/style/materials/materials.py list
    python3 kit/style/materials/materials.py check            the library matches library.json
    python3 kit/style/materials/materials.py build            repaint the library (about 75 s)
    python3 kit/style/materials/materials.py use WORLD [--profile P] [--size N] [--only a,b]
                                       tinted copies of the profile's materials into WORLD/textures/materials/
    python3 kit/style/materials/materials.py texel TARGET ... [--rule 256] [--json]
                                       texel density of every textured surface (world folder or .glb)
    python3 kit/style/materials/materials.py budget WORLD [--profile P] [--json]
                                       texture memory and sizes against the manifest and the library budget
    python3 kit/style/materials/materials.py sample FOLDER --godot G --project P [--shot OUT]
                                       a sample world that uses every library material; validated by the browser

The library is 15 seamless, hand-painted-style colour maps (kit/tools/paint_materials.py,
1024 px, 4 m per tile = 256 px per metre), painted around a warm neutral grey so any style
can tint them: `use` scales each map's mean colour to the profile's `materials.layers` tint
(the painter's own --tint rule) and tints each trim-sheet strip to `trim_sheet.looks`.

THE TEXEL-DENSITY RULE: every near surface (LOD0 of anything a visitor walks up to:
buildings, props, ground, walls, terrain layers, textured primitives) shows at least 256
texels per metre, with 20 % tolerance (205). Less looks blurry next to the city; far LODs
(node or mesh names with LOD1..LOD9) need a quarter of it. More than 4 x the rule (1024 px/m)
wastes memory and is a warning. `texel` exits 1 when a near surface misses the rule.

THE TEXTURE BUDGET: `budget` counts texture memory the way the browser does (w x h x 4 per
image, each .glb once, each scene image once), and fails when it exceeds the manifest's
`texture_bytes` or `texture_size`, or the library's `budget.world_texture_bytes` (64 MiB,
the city's 13 shared layers at 1024 are 52 MiB). It warns for non-power-of-two images, a
model that embeds more than `budget.model_texture_bytes` (4 MiB, one 1024 map) and the same
image embedded in several models (each copy is paid again: models use 512 px maps tiled
every 2 m, still 256 px/m; light goes into vertex colours with kit/blender/bake_vertex_light.py).

Needs numpy and Pillow (the painter's own needs).
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
LIB_DIR = HERE / "library"
LIB_JSON = HERE / "library.json"
PAINTER = KIT / "tools" / "paint_materials.py"
sys.path.insert(0, str(KIT / "lint"))
sys.path.insert(0, str(KIT / "style"))

LOD_FAR = re.compile(r"lod[_\-. ]?[1-9]", re.I)


def load_library() -> dict:
    return json.loads(LIB_JSON.read_text(encoding="utf-8"))


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------ build / check

def build(out: Path = LIB_DIR, size: int = 1024, quality: int = 90) -> dict:
    """Repaint every layer with the painter and write out/<layer>.jpg + library.json entries."""
    import tempfile
    from PIL import Image
    lib = load_library()
    with tempfile.TemporaryDirectory(prefix="iamar-lib-") as tmp:
        r = subprocess.run([sys.executable, str(PAINTER), tmp, "--size", str(size)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("painter failed: " + (r.stderr or r.stdout)[-800:])
        meta = json.loads((Path(tmp) / "materials.json").read_text(encoding="utf-8"))
        out.mkdir(parents=True, exist_ok=True)
        for name, m in meta["materials"].items():
            dst = out / (name + ".jpg")
            Image.open(Path(tmp) / m["file"]).convert("RGB").save(dst, "JPEG", quality=quality,
                                                                  subsampling=0, optimize=True)
            e = lib["layers"].setdefault(name, {})
            e.update(file="library/" + dst.name, size=size, mean_rgb=m["mean_rgb"], sha256=sha256(dst))
            if "strips" in m:
                e["strips"] = m["strips"]
    lib["size"], lib["tile_m"], lib["texels_per_metre"] = size, meta["tile_m"], meta["texels_per_m"]
    LIB_JSON.write_text(json.dumps(lib, indent=1) + "\n", encoding="utf-8")
    return lib


def check_library() -> list[str]:
    """Problems with the committed library (missing files, hash or size drift, seams,
    not neutral, no licence); [] when it is sound."""
    import numpy as np
    from PIL import Image
    errs = []
    lib = load_library()
    for k in ("licence", "origin", "licences_row", "texels_per_metre", "tile_m", "budget", "rule"):
        if not lib.get(k):
            errs.append("library.json: no %s" % k)
    painter_src = PAINTER.read_text(encoding="utf-8")
    layers = re.search(r"LAYERS = \[(.*?)\]", painter_src, re.S)
    painter_layers = re.findall(r'"(\w+)"', layers.group(1)) if layers else []
    if sorted(painter_layers) != sorted(lib.get("layers", {})):
        errs.append("library layers %s != painter LAYERS %s" % (sorted(lib.get("layers", {})), sorted(painter_layers)))
    want_tpm = lib.get("size", 0) / float(lib.get("tile_m") or 1)
    if abs(want_tpm - float(lib.get("texels_per_metre", 0))) > 1e-6:
        errs.append("texels_per_metre %s != size / tile_m %s" % (lib.get("texels_per_metre"), want_tpm))
    for name, e in sorted(lib.get("layers", {}).items()):
        p = HERE / e.get("file", "")
        if not p.is_file():
            errs.append("%s: %s missing" % (name, e.get("file")))
            continue
        if sha256(p) != e.get("sha256"):
            errs.append("%s: sha256 differs from library.json (run build, or restore the file)" % name)
        a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) / 255.0
        if a.shape[:2] != (e.get("size"), e.get("size")):
            errs.append("%s: %s px, library.json says %s" % (name, a.shape[:2], e.get("size")))
        mean = a.reshape(-1, 3).mean(axis=0)
        if not 0.5 <= float(mean.mean()) <= 0.7:
            errs.append("%s: mean %.3f is not the painter's neutral ~0.6 (a tinted file got in?)" % (name, mean.mean()))
        if max(abs(float(x) - float(y)) for x, y in zip(mean, e.get("mean_rgb", [0, 0, 0]))) > 0.02:
            errs.append("%s: mean colour %s drifts from library.json %s" % (name, mean.round(3).tolist(), e.get("mean_rgb")))
        # seamless: the wrap-around step is no stronger than the strongest step inside the
        # tile (block layouts put a course joint on the wrap, as on any interior joint)
        g = a.mean(axis=2)
        cols = np.abs(np.diff(g, axis=1)).mean(axis=0)
        rows = np.abs(np.diff(g, axis=0)).mean(axis=1)
        seam_x = float(np.abs(g[:, 0] - g[:, -1]).mean())
        seam_y = float(np.abs(g[0, :] - g[-1, :]).mean())
        if seam_x > 1.25 * cols.max() + 0.01 or seam_y > 1.25 * rows.max() + 0.01:
            errs.append("%s: does not tile (wrap step %.3f/%.3f, strongest inner step %.3f/%.3f)"
                        % (name, seam_x, seam_y, cols.max(), rows.max()))
        for k in ("roles", "kind"):
            if not e.get(k):
                errs.append("%s: no %s" % (name, k))
    return errs


# ------------------------------------------------------------------ use

def tinted(layer: str, tint: str | None, size: int, lib: dict, strip_looks: dict | None = None):
    """The library map for `layer`, tinted (mean colour -> tint) and resized seamlessly; uint8 array."""
    import numpy as np
    from PIL import Image
    e = lib["layers"][layer]
    rgb = np.asarray(Image.open(HERE / e["file"]).convert("RGB"), dtype=np.float64) / 255.0

    def apply(block, col):
        c = [int(col.lstrip("#")[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
        return block / np.maximum(block.reshape(-1, 3).mean(axis=0), 1e-6) * np.array(c)

    if strip_looks and e.get("strips"):
        h = rgb.shape[0] // len(e["strips"])
        for i, s in enumerate(e["strips"]):
            if strip_looks.get(s):
                rgb[i * h:(i + 1) * h] = apply(rgb[i * h:(i + 1) * h], strip_looks[s])
    elif tint:
        rgb = apply(rgb, tint)
    out = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    if size != out.shape[0]:
        import importlib.util
        spec = importlib.util.spec_from_file_location("paint_materials", PAINTER)
        pm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pm)
        out = pm.resample_seamless(out, size)
    return out


def use(world: Path, profile: str | None, size: int, only=None) -> dict:
    from PIL import Image
    import check_style
    lib = load_library()
    ref = profile or (str(world / "style.json") if (world / "style.json").is_file() else "iamar")
    errs = [m for lvl, m in check_style.check(ref) if lvl == "ERROR"]
    if errs:
        raise SystemExit("profile %s does not pass check_style:\n  %s" % (ref, "\n  ".join(errs)))
    prof, _ = check_style.load(ref)
    mats = (prof.get("materials") or {}).get("layers") or {}
    looks = ((prof.get("materials") or {}).get("trim_sheet") or {}).get("looks")
    if only:
        bad = sorted(set(only) - set(mats))
        if bad:
            raise SystemExit("not in the profile's materials.layers: %s" % ", ".join(bad))
        mats = {k: v for k, v in mats.items() if k in only}
    out = world / "textures" / "materials"
    out.mkdir(parents=True, exist_ok=True)
    # metres one map covers at the library's texel rule (1024 px -> 4 m, 512 px -> 2 m)
    tile_m = size / float(lib["texels_per_metre"])
    tile_m = int(tile_m) if tile_m == int(tile_m) else tile_m
    index = {"library": "kit/style/materials", "profile": prof.get("id"), "size": size,
             "tile_m": tile_m, "texels_per_metre": size / tile_m, "materials": {}}
    old = out / "materials.json"
    if only and old.is_file():     # --only adds to the index instead of replacing it
        prev = json.loads(old.read_text(encoding="utf-8"))
        prev_mats = prev.get("materials", {})
        if prev.get("size") == size:
            index["materials"] = dict(prev_mats)
        elif prev_mats:
            # --only at a different size would silently drop the other entries from the
            # index while their jpgs stay on disk; refuse and say how to proceed instead
            raise SystemExit(
                "materials use --only: the existing index in %s is size %s, but --size %s was requested; "
                "--only cannot change the size without silently dropping the other %d material(s). "
                "Rerun without --only to regenerate all materials at size %s, or rerun with --size %s."
                % (out, prev.get("size"), size, len(prev_mats), size, prev.get("size")))
    for name, m in sorted(mats.items()):
        layer = m.get("layer")
        rgb = tinted(layer, m.get("tint"), size, lib, looks if layer == "trim" else None)
        f = out / (name + ".jpg")
        Image.fromarray(rgb).save(f, "JPEG", quality=90, subsampling=0, optimize=True)
        index["materials"][name] = {"file": "textures/materials/" + f.name, "layer": layer,
                                    "tint": m.get("tint"), "use": m.get("use", ""),
                                    "uv_scale": tile_m}
    (out / "materials.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    mp = world / "manifest.json"
    if mp.is_file():
        man = json.loads(mp.read_text(encoding="utf-8"))
        credits = [c for c in man.get("credits", []) if "textures/materials/*" not in c.get("files", [])]
        credits.append({"files": ["textures/materials/*"], "author": lib["author"],
                        "license": lib["licence"], "source": lib["source"]})
        man["credits"] = credits
        mp.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return index


# ------------------------------------------------------------------ glTF reading (numpy)

DT = {5120: "i1", 5121: "u1", 5122: "i2", 5123: "u2", 5125: "u4", 5126: "f4"}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def accessor(g, i: int):
    import numpy as np
    gj = g.g
    a = gj["accessors"][i]
    n = NCOMP[a["type"]]
    dt = np.dtype("<" + DT[a["componentType"]])
    if "bufferView" not in a:
        return np.zeros((a["count"], n), dtype=np.float64)
    v = gj["bufferViews"][a["bufferView"]]
    stride = v.get("byteStride") or dt.itemsize * n
    base = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    raw = np.frombuffer(g.bin, dtype=np.uint8, count=stride * (a["count"] - 1) + dt.itemsize * n, offset=base)
    rows = np.lib.stride_tricks.as_strided(raw, shape=(a["count"], dt.itemsize * n), strides=(stride, 1))
    out = np.ascontiguousarray(rows).view(dt).reshape(a["count"], n).astype(np.float64)
    if a.get("normalized") and dt.kind in "iu":
        out = out / float(np.iinfo(dt).max)
    return out


def image_size(raw: bytes):
    from PIL import Image
    return Image.open(io.BytesIO(raw)).size


def model_textures(path: Path) -> list[dict]:
    """[{index, w, h, bytes, sha}] for every image in a .glb."""
    import style_lint
    g = style_lint.Glb(path)
    out = []
    for i, im in enumerate(g.g.get("images", [])):
        raw = g.image_bytes(i)
        if raw is None:
            out.append({"index": i, "external": im.get("uri", "?")})
            continue
        w, h = image_size(raw)
        out.append({"index": i, "w": w, "h": h, "bytes": w * h * 4, "sha": hashlib.sha256(raw).hexdigest()})
    return out


def glb_density(path: Path, scale=(1.0, 1.0, 1.0)) -> list[dict]:
    """Texel density of every textured primitive in a .glb placed at `scale`:
    [{mesh, material, far, px_per_m, area_m2, low_share}] (low_share = share of the
    primitive's area under the rule, filled in by the caller)."""
    import numpy as np
    import style_lint
    g = style_lint.Glb(path)
    gj = g.g
    sizes = {}
    for i in range(len(gj.get("images", []))):
        raw = g.image_bytes(i)
        if raw is not None:
            sizes[i] = image_size(raw)
    names = g.node_names()
    out = []
    for ni, node, m in g.instances():
        M = np.array(m, dtype=np.float64).reshape(4, 4).T          # column-major -> row-major
        M = np.diag(list(scale) + [1.0]) @ M
        mesh = gj["meshes"][node["mesh"]]
        far = any(LOD_FAR.search(n or "") for n in names.get(ni, []))
        for p in mesh.get("primitives", []):
            if p.get("mode", 4) != 4 or "material" not in p:
                continue
            mat = gj.get("materials", [])[p["material"]]
            bct = (mat.get("pbrMetallicRoughness") or {}).get("baseColorTexture")
            if not bct:
                continue
            tex = gj.get("textures", [])[bct["index"]]
            src = tex.get("source")
            if src not in sizes:
                continue
            tw, th = sizes[src]
            uv_key = "TEXCOORD_%d" % bct.get("texCoord", 0)
            if uv_key not in p["attributes"]:
                continue
            pos = accessor(g, p["attributes"]["POSITION"])[:, :3]
            pos = (np.c_[pos, np.ones(len(pos))] @ M.T)[:, :3]
            uv = accessor(g, p["attributes"][uv_key])[:, :2]
            tr = (bct.get("extensions") or {}).get("KHR_texture_transform") or {}
            uv = uv * np.array(tr.get("scale", [1.0, 1.0]))
            idx = accessor(g, p["indices"])[:, 0].astype(np.int64) if "indices" in p else np.arange(len(pos))
            tri = idx[: len(idx) // 3 * 3].reshape(-1, 3)
            a, b, c = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
            area3 = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
            ua, ub, uc = uv[tri[:, 0]], uv[tri[:, 1]], uv[tri[:, 2]]
            d1, d2 = ub - ua, uc - ua
            area2 = 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) * tw * th
            ok = area3 > 1e-8
            if not ok.any():
                continue
            dens = np.sqrt(area2[ok] / area3[ok])
            out.append({"mesh": mesh.get("name") or "mesh%d" % node["mesh"], "material": mat.get("name") or "material%d" % p["material"],
                        "far": far, "texture": "%dx%d" % (tw, th), "area_m2": float(area3[ok].sum()),
                        "px_per_m": float(np.sqrt(area2[ok].sum() / area3[ok].sum())),
                        "_dens": dens, "_area": area3[ok]})
    return out


def obj_scale3(o):
    s = o.get("scale", 1)
    return tuple(float(x) for x in s) if isinstance(s, list) else (float(s),) * 3


def reused_records(manifest: dict) -> dict:
    """manifest.reused by path (`iamar-world assets use <hash> --as <path>`, AGENT_KIT step 3)."""
    return {str(r.get("path", "")): r for r in (manifest.get("reused") or []) if isinstance(r, dict)}


def resolve_asset(world: Path, asset: str, reused: dict) -> Path | None:
    """The file an object's asset stands for, as validate, lint and audit resolve it: the world's
    own file, else the kit's copy of a reused-by-hash object; None for a reused built-in object
    that has no file in the kit (the browser ships it)."""
    p = world / asset
    if p.is_file() or asset not in reused:
        return p
    import style_lint
    f, entry = style_lint.reused_file(reused[asset])
    if f is not None:
        return f
    return None if entry is not None else p     # unknown hash: still missing


# ------------------------------------------------------------------ texel

CITY_EXEMPT = ("; exempt: an unchanged catalogue model from the iamar city (origin city), painted as the "
               "city draws it (most city props are about 128 px/m), kept as the city has it")


def city_model(p: Path) -> bool:
    """Whether a file is byte for byte a catalogue model exported from the iamar city: those keep
    the city's own painting and are exempt from the texel rule (WARN, not ERROR; harbour a4 G8)."""
    import style_lint
    entry = style_lint.catalogue_entry(p)
    return (entry or {}).get("source", {}).get("origin") == "city"


def texel(targets: list[Path], rule: float, tol: float = 0.2) -> tuple[list[dict], int]:
    """Rows [{where, kind, px_per_m, level, msg}] and the number of errors."""
    import numpy as np
    lo, far_lo, hi = rule * (1 - tol), rule / 4 * (1 - tol), rule * 4
    rows = []

    def judge(where, kind, d, far=False, low_share=None):
        if far:
            lvl = "OK" if d >= far_lo else "ERROR"
            msg = "far LOD: %.0f px/m (needs %.0f)" % (d, far_lo)
        elif low_share is not None and low_share > 0.1:
            lvl, msg = "ERROR", "%.0f%% of the surface is under %.0f px/m (mean %.0f px/m): scale the UVs up or use a bigger map" % (low_share * 100, lo, d)
        elif d < lo:
            lvl, msg = "ERROR", "%.0f px/m < %.0f (rule %d px/m, %d%% tolerance): blurry next to the city" % (d, lo, rule, tol * 100)
        elif d > hi:
            lvl, msg = "WARN", "%.0f px/m > %.0f: more texels than anyone sees; halve the map or tile it" % (d, hi)
        else:
            lvl, msg = "OK", "%.0f px/m" % d
        rows.append({"where": where, "kind": kind, "px_per_m": round(d, 1), "level": lvl, "msg": msg})

    def do_glb(p: Path, label: str, scale=(1.0, 1.0, 1.0)):
        try:
            prims = glb_density(p, scale)
        except Exception as e:  # noqa: BLE001
            rows.append({"where": label, "kind": "glb", "px_per_m": 0, "level": "ERROR", "msg": "cannot read: %s" % e})
            return
        n = len(rows)
        for pr in prims:
            if float(pr["_area"][pr["_dens"] < 1.0].sum()) > 0.9 * float(pr["_area"].sum()):
                rows.append({"where": "%s %s/%s" % (label, pr["mesh"], pr["material"]), "kind": "palette", "px_per_m": 0,
                             "level": "OK", "msg": "palette swatches (each face samples one texel of a %s colour strip): no texel rule"
                             % pr["texture"]})
                continue
            share = None if pr["far"] else float(pr["_area"][pr["_dens"] < lo].sum() / pr["_area"].sum())
            judge("%s %s/%s" % (label, pr["mesh"], pr["material"]), "glb", pr["px_per_m"], pr["far"], share)
        if any(r["level"] == "ERROR" for r in rows[n:]) and city_model(p):
            for r in rows[n:]:
                if r["level"] == "ERROR":
                    r["level"], r["msg"] = "WARN", r["msg"] + CITY_EXEMPT

    for t in targets:
        if t.suffix.lower() == ".glb":
            do_glb(t, t.name)
            continue
        scene = json.loads((t / "scene.json").read_text(encoding="utf-8"))
        try:
            reused = reused_records(json.loads((t / "manifest.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            reused = {}
        seen = set()
        for o in scene.get("objects") or []:
            vr = o.get("visible_range", 0)
            if isinstance(vr, (int, float)) and 0 < vr < 0.5:
                continue        # collision-only
            key = (o.get("asset"), obj_scale3(o))
            p = resolve_asset(t, o.get("asset", ""), reused) if o.get("asset") else None
            if key in seen or p is None or not p.is_file():
                continue
            seen.add(key)
            do_glb(p, "%s:%s" % (t.name, o.get("asset")), obj_scale3(o))
        for pr in scene.get("primitives") or []:
            tex = pr.get("texture")
            if tex and (t / tex).is_file():
                w, _ = image_size((t / tex).read_bytes())
                judge("%s:primitives.%s" % (t.name, pr.get("id", pr.get("shape"))), "primitive",
                      w / float(pr.get("uv_scale", 1.0)))
        for i, layer in enumerate((scene.get("terrain") or {}).get("materials") or []):
            tex = layer.get("texture")
            if tex and (t / tex).is_file():
                w, _ = image_size((t / tex).read_bytes())
                judge("%s:terrain.materials[%d]" % (t.name, i), "terrain", w / float(layer.get("uv_scale", 4.0)))
    return rows, sum(r["level"] == "ERROR" for r in rows)


# ------------------------------------------------------------------ budget

def budget(world: Path, profile_budget: dict | None = None) -> tuple[dict, list[tuple[str, str]]]:
    lib = load_library()
    b = dict(lib["budget"], **(profile_budget or {}))
    man = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    scene = json.loads((world / "scene.json").read_text(encoding="utf-8"))
    mb = man.get("budgets") or {}
    notes: list[tuple[str, str]] = []
    total, edge, per_model, shas = 0, 0, {}, {}
    reused = reused_records(man)
    # every model the browser loads (WorldPackage._measure, validate's STATS): objects and
    # their attachments, NPC models and theirs, quest look models; each file once
    models = set()
    for o in scene.get("objects") or []:
        models.add(o.get("asset"))
        models.update(a.get("asset") for a in o.get("attach") or [])
    for n in scene.get("npcs") or []:
        if n.get("model"):
            models.add(n["model"])
            models.update(a.get("asset") for a in n.get("attach") or [])
    for q in scene.get("quests") or []:
        for st in q.get("steps") or []:
            for o in st if isinstance(st, list) else [st]:
                if isinstance(o, dict) and str(o.get("look", "")).endswith(".glb"):
                    models.add(o["look"])
    for asset in sorted(m for m in models if m):
        p = resolve_asset(world, asset, reused)
        if p is None:
            notes.append(("INFO", "%s: reused built-in object (manifest.reused); its maps belong to the browser" % asset))
            continue
        if not p.is_file():
            notes.append(("ERROR", "%s: missing" % asset))
            continue
        tb = 0
        for t in model_textures(p):
            if "external" in t:
                notes.append(("ERROR", "%s image %d is not embedded (%s)" % (asset, t["index"], t["external"])))
                continue
            tb += t["bytes"]
            edge = max(edge, t["w"], t["h"])
            shas.setdefault(t["sha"], []).append(asset)
            for d in (t["w"], t["h"]):
                if d & (d - 1):
                    notes.append(("WARN", "%s image %d is %dx%d: not a power of two" % (asset, t["index"], t["w"], t["h"])))
                    break
        per_model[asset] = tb
        total += tb
        if tb > b["model_texture_bytes"]:
            notes.append(("WARN", "%s embeds %.1f MiB of textures (> %.0f MiB): every .glb pays its own maps; use library maps at 512 px tiled every 2 m (materials use --size 512, still 256 px/m) or an atlas"
                          % (asset, tb / 2 ** 20, b["model_texture_bytes"] / 2 ** 20)))
    files = set()
    for pr in scene.get("primitives") or []:
        if pr.get("texture"):
            files.add(pr["texture"])
    terrain = scene.get("terrain") or {}
    for layer in terrain.get("materials") or []:
        if layer.get("texture"):
            files.add(layer["texture"])
    if terrain.get("heightmap"):
        files.add(terrain["heightmap"])
    sky = (scene.get("environment") or {}).get("sky") or scene.get("sky") or {}
    if sky.get("type") == "cubemap":   # the browser loads faces only for a cubemap sky
        for f in (sky.get("faces") or {}).values():
            files.add(f)
    # far-model cards (WorldImpostors), when they have been rendered
    for a in sorted({o.get("asset") for o in scene.get("objects") or [] if "impostor" in o and o.get("asset")}):
        cards = ["impostors/%s.%s" % (a, k) for k in ("albedo.png", "normal.png")]
        if (world / ("impostors/%s.json" % a)).is_file() and all((world / c).is_file() for c in cards):
            files.update(cards)
    scene_bytes = 0
    for f in sorted(files):
        p = world / f
        if not p.is_file():
            notes.append(("ERROR", "%s: missing" % f))
            continue
        w, h = image_size(p.read_bytes())
        scene_bytes += w * h * 4
        edge = max(edge, w, h)
    total += scene_bytes
    for sha, assets in shas.items():
        if len(assets) > 1:
            notes.append(("WARN", "the same image is embedded in %d models (%s): each copy is paid again "
                          "(fine within the budget; 512 px maps tiled every 2 m keep it small)"
                          % (len(assets), ", ".join(sorted(set(assets))[:4]))))
    limit_bytes = min(int(mb.get("texture_bytes", 1 << 30)), int(b["world_texture_bytes"]))
    limit_edge = min(int(mb.get("texture_size", 4096)), int(b["max_texture_size"]))
    if total > limit_bytes:
        notes.append(("ERROR", "texture memory %.1f MiB > budget %.1f MiB (manifest %s, library %s)"
                      % (total / 2 ** 20, limit_bytes / 2 ** 20, mb.get("texture_bytes"), b["world_texture_bytes"])))
    if edge > limit_edge:
        notes.append(("ERROR", "largest texture %d px > %d px" % (edge, limit_edge)))
    nums = {"texture_bytes": total, "texture_bytes_with_mips": int(total * 4 / 3), "scene_image_bytes": scene_bytes,
            "texture_size": edge, "limit_bytes": limit_bytes, "limit_size": limit_edge, "models": per_model}
    return nums, notes


# ------------------------------------------------------------------ sample

def _kit(godot: str, project: str, *args: str) -> str:
    flags = 0x00004000 if os.name == "nt" else 0       # BELOW_NORMAL_PRIORITY_CLASS
    p = subprocess.run([godot, "--headless", "--path", project, "--", "--kit", *args],
                       capture_output=True, text=True, timeout=600, creationflags=flags)
    if p.returncode != 0:
        raise SystemExit("materials sample: kit %s failed\n%s" % (args[0], (p.stdout + p.stderr)[-1500:]))
    return p.stdout


def sample(folder: Path, godot: str, project: str, profile: str = "iamar") -> Path:
    """The kit starter world plus one 4 m wall per library material (tinted by the
    profile), the cobble on the square, the trim sheet on a lintel; validated."""
    if folder.exists():
        raise SystemExit("materials sample: %s exists; give a new folder" % folder)
    _kit(godot, project, "new", str(folder), "--id", "materials_sample", "--title",
         "Material library sample", "--author", "iamar kit")
    idx = use(folder, profile, 1024)
    sp = folder / "scene.json"
    s = json.loads(sp.read_text(encoding="utf-8"))
    prims = list(s.get("primitives", []))
    names = [n for n in idx["materials"] if n != "cobble"]
    for i, n in enumerate(names):
        x = (i - (len(names) - 1) / 2.0) * 5.0
        prims.append({"id": "wall_" + n, "shape": "box", "size": [4, 4, 0.6], "position": [x, 2, -12],
                      "texture": idx["materials"][n]["file"], "uv_scale": idx["tile_m"], "collision": "box"})
    if "cobble" in idx["materials"]:
        prims.append({"id": "square_cobble", "shape": "box", "size": [64, 0.1, 12], "position": [0, 0.05, -4],
                      "texture": idx["materials"]["cobble"]["file"], "uv_scale": idx["tile_m"], "collision": "box"})
    s["primitives"] = prims
    sp.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
    mp = folder / "manifest.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    bud = m.setdefault("budgets", {})
    bud["objects"] = max(int(bud.get("objects", 0)), len(prims) + len(s.get("objects", [])) + 16)
    bud["texture_size"] = max(int(bud.get("texture_size", 0)), 1024)
    bud["texture_bytes"] = max(int(bud.get("texture_bytes", 0)), 64 << 20)
    mp.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    _kit(godot, project, "validate", str(folder))
    return folder


def shot(world: Path, out: Path, godot: str, project: str, size: str = "1280x720") -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    flags = 0x00004000 if os.name == "nt" else 0
    cmd = [godot, "--path", project, "--", "--kit", "preview", str(world), str(out / "shot"),
           "--npcs", "none", "--frames", "30", "--size", size,
           "--view", "0,1.7,0>0,2,-12", "--view", "-20,1.7,-4>-28,2,-12", "--view", "0,9,8>0,1,-10"]
    pre = [] if os.name == "nt" else ["nice", "-n", "19"]
    p = subprocess.run(pre + cmd, capture_output=True, text=True, timeout=600, creationflags=flags)
    return [ln for ln in p.stdout.splitlines() if ln.startswith(("VIEW ", "TARGET ", "ERROR"))] or [(p.stdout + p.stderr)[-1500:]]


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("check")
    b = sub.add_parser("build")
    b.add_argument("--size", type=int, default=1024)
    u = sub.add_parser("use")
    u.add_argument("world")
    u.add_argument("--profile")
    u.add_argument("--size", type=int, default=1024, choices=[256, 512, 1024, 2048])
    u.add_argument("--only")
    t = sub.add_parser("texel")
    t.add_argument("targets", nargs="+")
    t.add_argument("--rule", type=float)
    t.add_argument("--json", action="store_true")
    bu = sub.add_parser("budget")
    bu.add_argument("world")
    bu.add_argument("--profile")
    bu.add_argument("--json", action="store_true")
    s = sub.add_parser("sample")
    s.add_argument("folder")
    s.add_argument("--godot", required=True)
    s.add_argument("--project", required=True)
    s.add_argument("--profile", default="iamar")
    s.add_argument("--shot")
    a = ap.parse_args(argv)
    lib = load_library()

    if a.cmd == "list":
        for n, e in sorted(lib["layers"].items()):
            print("%-11s %-8s %s" % (n, e["kind"], e["roles"]))
        return 0
    if a.cmd == "check":
        errs = check_library()
        for e in errs:
            print("ERROR", e)
        print("LIBRARY_OK %d layers" % len(lib["layers"]) if not errs else "LIBRARY_FAIL %d problems" % len(errs))
        return 1 if errs else 0
    if a.cmd == "build":
        lib = build(size=a.size)
        print("BUILT %d layers in %s" % (len(lib["layers"]), LIB_DIR))
        return 0
    if a.cmd == "use":
        idx = use(Path(a.world), a.profile, a.size, [x.strip() for x in a.only.split(",")] if a.only else None)
        for n, e in idx["materials"].items():
            print("USE %-16s %s  (%s, uv_scale %s)" % (n, e["file"], e["layer"], e["uv_scale"]))
        return 0
    if a.cmd == "texel":
        rows, nerr = texel([Path(x) for x in a.targets], a.rule or float(lib["rule"]["near_px_per_m"]),
                           float(lib["rule"]["tolerance"]))
        if a.json:
            print(json.dumps(rows, indent=1))
        else:
            for r in rows:
                print("%-5s %-9s %s: %s" % (r["level"], r["kind"], r["where"], r["msg"]))
        print("TEXEL_%s %d surfaces, %d under the rule" % ("FAIL" if nerr else "OK", len(rows), nerr))
        return 1 if nerr else 0
    if a.cmd == "budget":
        prof_b = None
        if a.profile:
            import check_style
            prof, _ = check_style.load(a.profile)
            prof_b = (prof.get("materials") or {}).get("texture_budget")
        nums, notes = budget(Path(a.world), prof_b)
        if a.json:
            print(json.dumps({"numbers": nums, "notes": notes}, indent=1))
        else:
            for lvl, msg in notes:
                print("%-5s %s" % (lvl, msg))
            print("texture memory %.1f MiB (%.1f MiB with mipmaps) of %.1f MiB; largest %d px of %d"
                  % (nums["texture_bytes"] / 2 ** 20, nums["texture_bytes_with_mips"] / 2 ** 20,
                     nums["limit_bytes"] / 2 ** 20, nums["texture_size"], nums["limit_size"]))
        bad = any(lvl == "ERROR" for lvl, _ in notes)
        print("BUDGET_%s" % ("FAIL" if bad else "OK"))
        return 1 if bad else 0
    if a.cmd == "sample":
        w = sample(Path(a.folder), a.godot, a.project, a.profile)
        print("SAMPLE %s (validated)" % w)
        if a.shot:
            for ln in shot(w, Path(a.shot), a.godot, a.project):
                print(ln)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
