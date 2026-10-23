#!/usr/bin/env python3
"""Runs every kit Blender tool (kit/blender/*.py) headless on a tiny generated scene
and checks what it writes. Needs Blender 4.2+ (BLENDER=/path/to/blender, or on PATH,
or in a usual install folder); without it every check is reported SKIPPED and the
test exits 0. Takes about a minute on a laptop CPU.

    python3 kit/tests/blender_tools_test.py [--keep DIR]
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[1]
TOOLS = KIT / "blender"

# The test scene, built in Blender (+Z up) and exported as glTF:
#   scene.glb : a 6 m ground, a red 1 m box (blue top) on it, a glowing lamp block, an invisible
#               (alpha 0) collision plate that must stay live, all static
#   house.glb : a low-poly 8 x 6 x 3 m house with plaster (0.85) vertex colours
#   high.glb  : a 1 m cube with rounded (bevelled) edges; low.glb: the plain cube
#   lopsided.glb: a box right of the origin, a cone left of it (for mirror)
GEN = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
def mat(name, rgb, emit=0.0, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1); b.inputs["Emission Strength"].default_value = emit
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return m
def export(path, obs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True)
def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
clear()
bpy.ops.mesh.primitive_plane_add(size=6); g = bpy.context.object; g.name = "ground"; g.data.materials.append(mat("grass", (0.4, 0.6, 0.3)))
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5)); c = bpy.context.object; c.name = "box"; c.data.materials.append(mat("red", (0.8, 0.2, 0.15))); c.data.materials.append(mat("roof", (0.2, 0.3, 0.6))); c.data.polygons[5].material_index = 1
bpy.ops.mesh.primitive_cube_add(size=0.3, location=(1.5, 1.0, 0.15)); l = bpy.context.object; l.name = "lamp"; l.data.materials.append(mat("glow", (1.0, 0.8, 0.4), emit=5.0))
bpy.ops.mesh.primitive_plane_add(size=1, location=(-2, -2, 0.5)); p = bpy.context.object; p.name = "proxy"; p.data.materials.append(mat("invisible", (1, 1, 1), alpha=0.0))
export(out + "/scene.glb", [g, c, l, p])
clear()
# house.glb: a low-poly 8 x 6 x 3 m house (corner vertices only), plaster 0.85 in COLOR_0
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.5)); h = bpy.context.object; h.name = "house"
h.scale = (8, 6, 3); bpy.ops.object.transform_apply(scale=True)
ca = h.data.color_attributes.new("Color", "FLOAT_COLOR", "CORNER")
for d in ca.data: d.color = (0.694, 0.694, 0.694, 1)
hm = bpy.data.materials.new("plaster"); hm.use_nodes = True
vc = hm.node_tree.nodes.new("ShaderNodeVertexColor"); vc.layer_name = "Color"
hm.node_tree.links.new(vc.outputs["Color"], hm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
h.data.materials.append(hm)
export(out + "/house.glb", [h])
clear()
bpy.ops.mesh.primitive_cube_add(size=1); lo = bpy.context.object; lo.data.materials.append(mat("stone", (0.7, 0.7, 0.65)))
export(out + "/low.glb", [lo])
bev = lo.modifiers.new("b", "BEVEL"); bev.width = 0.12; bev.segments = 4
sub = lo.modifiers.new("s", "SUBSURF"); sub.levels = 1
bpy.ops.object.shade_smooth()
export(out + "/high.glb", [lo])
clear()
bpy.ops.mesh.primitive_cube_add(size=1, location=(1.0, 0, 0.5)); a = bpy.context.object
bpy.ops.mesh.primitive_cone_add(radius1=0.5, depth=1, location=(-1.5, 0, 0.5)); b = bpy.context.object
export(out + "/lopsided.glb", [a, b])
print("GEN_OK")
'''


def find_blender():
    cands = [os.environ.get("BLENDER", ""), shutil.which("blender") or ""]
    home = Path.home()
    cands += sorted(glob.glob(str(home / "opt" / "blender-*" / "blender*")), reverse=True)
    cands += sorted(glob.glob("/opt/blender*/blender"), reverse=True)
    cands += ["/usr/bin/blender", "/snap/bin/blender", "/Applications/Blender.app/Contents/MacOS/Blender"]
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    cands += sorted(glob.glob(os.path.join(pf, "Blender Foundation", "Blender*", "blender.exe")), reverse=True)
    for c in cands:
        if c and os.path.isfile(c) and os.path.basename(c).lower() in ("blender", "blender.exe"):
            return c
    return None


# ---- a tiny glTF reader (JSON chunk, accessors), no third-party modules
class Glb:
    def __init__(self, path):
        data = Path(path).read_bytes()
        assert data[:4] == b"glTF", path
        jlen = struct.unpack("<I", data[12:16])[0]
        self.js = json.loads(data[20:20 + jlen])
        rest = data[20 + jlen:]
        self.bin = rest[8:8 + struct.unpack("<I", rest[:4])[0]] if rest else b""

    def accessor(self, i):
        a = self.js["accessors"][i]
        bv = self.js["bufferViews"][a["bufferView"]]
        n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
        fmt, size, norm = {5126: ("f", 4, 1.0), 5121: ("B", 1, 255.0), 5123: ("H", 2, 65535.0)}[a["componentType"]]
        stride = bv.get("byteStride", size * n)
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        out = []
        for k in range(a["count"]):
            vals = struct.unpack_from("<%d%s" % (n, fmt), self.bin, off + k * stride)
            out.append([v / norm if a.get("normalized") or fmt != "f" else v for v in vals])
        return out

    def indices(self, i):
        """Index accessor as plain ints (accessor() would normalize them)."""
        a = self.js["accessors"][i]
        bv = self.js["bufferViews"][a["bufferView"]]
        fmt, size = {5121: ("B", 1), 5123: ("H", 2), 5125: ("I", 4)}[a["componentType"]]
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        return list(struct.unpack_from("<%d%s" % (a["count"], fmt), self.bin, off))

    def prims(self):
        for m in self.js.get("meshes", []):
            yield from m["primitives"]


RESULTS: list[tuple[str, str, str]] = []


def check(name, cond, detail=""):
    RESULTS.append((name, "PASS" if cond else "FAIL", detail))
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""), flush=True)


def run(blender, args, label, cwd=None):
    cmd = [blender, "-b", "--factory-startup"] + args
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=900)
    ok = p.returncode == 0
    if not ok:
        print("---- %s failed (%d):\n%s\n%s" % (label, p.returncode, p.stdout[-3000:], p.stderr[-3000:]), flush=True)
    return ok, p.stdout


def tool(name):
    return ["--python", str(TOOLS / name), "--"]


def main() -> int:
    keep = None
    if "--keep" in sys.argv:
        keep = Path(sys.argv[sys.argv.index("--keep") + 1]).resolve()
    names = ["generate", "bake_unlit", "bake_unlit_denoised", "bake_unlit_unlit_ext", "bake_unlit_texture", "bake_unlit_live_kept",
             "bake_unlit_not_black", "bake_vertex_ao", "bake_vertex_ao_dark_contact", "bake_vertex_ao_keeps_materials",
             "bake_vertex_ao_max_edge", "bake_vertex_ao_lowpoly_plaster", "bake_normals",
             "bake_normals_map", "mirror", "mirror_symmetric", "look", "help"]
    blender = find_blender()
    if blender is None:
        for n in names:
            print("SKIPPED " + n + "  (no Blender: set BLENDER=/path/to/blender)")
        print("kit blender tool tests: skipped (no Blender)")
        return 0
    print("BLENDER", blender, flush=True)
    work = Path(keep or tempfile.mkdtemp(prefix="iamar-kit-blender-"))
    work.mkdir(parents=True, exist_ok=True)
    try:
        ok, _ = run(blender, ["--python-expr", GEN, "--", str(work)], "generate")
        check("generate", ok and (work / "scene.glb").is_file())
        if not ok:
            return 1

        # bake_unlit: sky + sun + the glowing block, CPU, small and quick
        out = work / "baked.glb"
        ok, log = run(blender, tool("bake_unlit.py") + [str(work / "scene.glb"), str(out), "8", "--size", "128",
                                                        "--cpu", "--format", "png", "--save-images", str(work / "bake_images")],
                      "bake_unlit")
        check("bake_unlit", ok and out.is_file() and "BAKE_UNLIT_OK" in log)
        # the compositor API changed in Blender 5.0 (no scene.node_tree): the denoise must run on both
        check("bake_unlit_denoised", "DENOISED" in log and "DENOISE_SKIPPED" not in log,
              next((l for l in log.splitlines() if l.startswith("DENOISE")), "no DENOISE line"))
        if out.is_file():
            g = Glb(out)
            mats = g.js.get("materials", [])
            unlit = [m for m in mats if "KHR_materials_unlit" in m.get("extensions", {})]
            check("bake_unlit_unlit_ext", len(unlit) == 1 and "KHR_materials_unlit" in g.js.get("extensionsUsed", []),
                  "%d unlit of %d materials" % (len(unlit), len(mats)))
            tex_ok = bool(unlit) and "baseColorTexture" in unlit[0].get("pbrMetallicRoughness", {}) and len(g.js.get("images", [])) == 1
            check("bake_unlit_texture", tex_ok)
            live = [m for m in mats if m not in unlit]
            check("bake_unlit_live_kept", len(live) == 1 and live[0].get("name") == "invisible",
                  "live materials: %s" % [m.get("name") for m in live])
            imgs = sorted((work / "bake_images").glob("*.png"))
            bright = None
            try:
                from PIL import Image  # optional
                if imgs:
                    im = Image.open(imgs[0]).convert("L")
                    px = im.tobytes()
                    bright = sum(px) / len(px)
            except ImportError:
                pass
            if bright is None:
                check("bake_unlit_not_black", bool(imgs) and imgs[0].stat().st_size > 2000, "PIL missing: size only")
            else:
                check("bake_unlit_not_black", 30 < bright < 250, "mean grey %.0f of 255" % bright)

        # bake_vertex_ao: the box sits on the ground, so its bottom corners darken
        out = work / "ao.glb"
        ok, log = run(blender, tool("bake_vertex_ao.py") + [str(work / "scene.glb"), str(out), "--distance", "0.6",
                                                            "--samples", "16", "--cpu", "--floor", "0.0"], "bake_vertex_ao")
        check("bake_vertex_ao", ok and out.is_file() and "BAKE_VERTEX_AO_OK" in log)
        if out.is_file():
            g = Glb(out)
            cols = [c for p in g.prims() if "COLOR_0" in p["attributes"] for c in g.accessor(p["attributes"]["COLOR_0"])]
            lo = min((sum(c[:3]) / 3 for c in cols), default=1.0)
            hi = max((sum(c[:3]) / 3 for c in cols), default=0.0)
            check("bake_vertex_ao_dark_contact", bool(cols) and lo < 0.85 and hi > 0.9,
                  "%d colours, min %.2f max %.2f" % (len(cols), lo, hi))
            before = sorted(p.get("material", -1) for p in Glb(work / "scene.glb").prims())
            after = sorted(p.get("material", -1) for p in g.prims())
            check("bake_vertex_ao_keeps_materials", before == after, "%s -> %s" % (before, after))

        # bake_vertex_ao --max-edge on a low-poly style-gen house (harbour blind test, gaps G10):
        # the plaster (0.85) must stay at 0.6 or lighter, area-weighted, with the default floor
        house = work / "house.glb"
        if house.is_file():
            ref, out = work / "house_ref.glb", work / "house_ao.glb"
            common = ["--distance", "0.5", "--cpu", "--max-edge", "2"]
            ok1, _ = run(blender, tool("bake_vertex_ao.py") + [str(house), str(ref), "--samples", "4", "--strength", "0"] + common,
                         "bake_vertex_ao_ref")
            ok2, log = run(blender, tool("bake_vertex_ao.py") + [str(house), str(out), "--samples", "16"] + common,
                           "bake_vertex_ao_max_edge")
            tris = next((l for l in log.splitlines() if l.startswith("MAX_EDGE ")), "")
            check("bake_vertex_ao_max_edge", ok1 and ok2 and out.is_file() and "triangles" in tris, tris)
            if ok1 and ok2:
                def srgb(x):
                    return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
                area = val = 0.0
                gr, gb = Glb(ref), Glb(out)
                for pr, pb in zip(gr.prims(), gb.prims()):
                    pos = gr.accessor(pr["attributes"]["POSITION"])
                    cr = gr.accessor(pr["attributes"]["COLOR_0"])
                    cb = gb.accessor(pb["attributes"]["COLOR_0"])
                    idx = gr.indices(pr["indices"])
                    for t in range(0, len(idx), 3):
                        i, j, k = idx[t:t + 3]
                        if not all(abs(srgb(max(cr[v][:3])) - 0.85) < 0.02 for v in (i, j, k)):
                            continue
                        u = [pos[j][d] - pos[i][d] for d in range(3)]
                        w = [pos[k][d] - pos[i][d] for d in range(3)]
                        cx = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
                        ar = 0.5 * sum(c * c for c in cx) ** 0.5
                        area += ar
                        val += ar * sum(srgb(max(cb[v][:3])) for v in (i, j, k)) / 3
                mean = val / area if area else 0.0
                check("bake_vertex_ao_lowpoly_plaster", area > 50 and mean >= 0.6,
                      "plaster 0.85 -> %.2f over %.0f m2" % (mean, area))
        else:
            check("bake_vertex_ao_max_edge", True, "SKIPPED: no %s" % house)
            check("bake_vertex_ao_lowpoly_plaster", True, "SKIPPED")

        # bake_normals: the bevelled cube onto the plain one
        out = work / "normals.glb"
        ok, log = run(blender, tool("bake_normals.py") + [str(work / "high.glb"), str(work / "low.glb"), str(out),
                                                          "--size", "256", "--cpu", "--save-map", str(work / "normals_normal.png")], "bake_normals")
        check("bake_normals", ok and out.is_file() and "BAKE_NORMALS_OK" in log)
        if out.is_file():
            g = Glb(out)
            has_map = any("normalTexture" in m for m in g.js.get("materials", []))
            has_tan = all("TANGENT" in p["attributes"] for p in g.prims())
            png = work / "normals_normal.png"
            detail = "map=%s tangents=%s" % (has_map, has_tan)
            varied = png.is_file()
            try:
                from PIL import Image  # optional
                if png.is_file():
                    im = Image.open(png).convert("RGB")
                    reds = im.tobytes()[0::3]
                    varied = max(reds) - min(reds) > 40
                    detail += " red range %d..%d" % (min(reds), max(reds))
            except ImportError:
                detail += " (PIL missing: map content not checked)"
            check("bake_normals_map", has_map and has_tan and varied, detail)

        # mirror: keep +X, the result is symmetric about x = 0
        out = work / "mirrored.glb"
        ok, log = run(blender, tool("mirror.py") + [str(work / "lopsided.glb"), str(out), "--axis", "x", "--keep", "pos"], "mirror")
        check("mirror", ok and out.is_file() and "MIRROR_OK" in log)
        if out.is_file():
            g = Glb(out)
            xs = [v[0] for p in g.prims() for v in g.accessor(p["attributes"]["POSITION"])]
            check("mirror_symmetric", bool(xs) and abs(min(xs) + max(xs)) < 1e-3 and max(xs) > 1.4,
                  "x %.3f..%.3f" % (min(xs or [0]), max(xs or [0])))

        # look: two views of the bake
        prefix = work / "look" / "baked"
        ok, log = run(blender, tool("look.py") + [str(prefix), str(work / "baked.glb"), "--views", "35,top",
                                                  "--size", "128", "--shading", "flat"], "look")
        shots = sorted((work / "look").glob("baked_0_*.png"))
        check("look", ok and len(shots) == 2 and "LOOK_OK" in log, "%d images" % len(shots))

        # every tool explains itself
        helps = []
        for t in ("bake_unlit.py", "bake_vertex_ao.py", "bake_normals.py", "look.py", "mirror.py"):
            ok, log = run(blender, tool(t) + ["--help"], t + " --help")
            helps.append(ok and "usage:" in log)
        check("help", all(helps), "%d/%d tools" % (sum(helps), len(helps)))
    finally:
        if keep is None:
            shutil.rmtree(work, ignore_errors=True)
    failed = [r for r in RESULTS if r[1] == "FAIL"]
    print("kit blender tool tests: %d/%d" % (len(RESULTS) - len(failed), len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
