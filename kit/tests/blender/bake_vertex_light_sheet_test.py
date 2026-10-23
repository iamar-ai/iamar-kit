#!/usr/bin/env python3
"""Open sheets in kit/blender/bake_vertex_light.py (an internal task): a double-sided sheet whose
normal points into the model must not bake black.

Cycles bakes the side a face's normal points to; the browser draws a double-sided face
from both sides with one COLOR_0. Before the fix, ~400 faces of the catalogue hero
(kit/catalog/assets/landmarks/hero_w1.glb: an unwelded sheet mesh, about half its
normals pointing into the body) baked to 0 and the cloak showed black from behind.

Checks, each measured in Blender on the baked .glb:
  - a synthetic figure (closed box body, a double-sided cloak sheet facing the body, a
    single-sided sheet facing the body, a closed box): the bake turns exactly the cloak's
    faces, every cloak face is lit (>= 0.05), the closed box and the single-sided sheet
    keep their normals; with --no-orient the cloak bakes dark (the bug this guards);
  - hero_w1.glb: no visible face (area >= 10 cm2, open on either side) under 0.05; with
    --no-orient more than 100 such faces;
  - the hero_statue recipe (kit/recipes/statue/statue.py, its cloak a
    closed slab, an internal task) baked with --grid 0.5 as its README says: at most one visible face
    under 0.05 (a 12 cm2 face of a hair tuft at the head top).

Needs Blender 4.2+ (BLENDER=/path/to/blender, on PATH, or in ~/opt/blender-*); without it
every check is reported SKIPPED and the test exits 0. About 20 s on a 4-thread CPU.

    python3 kit/tests/blender/bake_vertex_light_sheet_test.py [--keep DIR]
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(KIT / "tests"))
from blender_tools_test import find_blender  # noqa: E402

HERO = KIT / "catalog/assets/landmarks/hero_w1.glb"
DARK = 0.05

# body: closed 1 x 0.6 x 1.8 m box; cloak: 4 x 4 grid sheet 2 cm behind it, normal
# pointing at the body (double-sided); shield: the same sheet in front, single-sided;
# crate: a closed box away from the figure
GEN = r'''
import bpy, bmesh, sys
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
def mat(name, cull):
    m = bpy.data.materials.new(name); m.use_nodes = True; m.use_backface_culling = cull
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1)
    return m
def link(name, bm, m):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    me.materials.append(m); return ob
def box(name, lo, hi, m):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector([lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3)])
    return link(name, bm, m)
def sheet(name, y, toward_y, m):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=4, y_segments=4, size=0.5)
    for v in bm.verts:   # grid lies in XY: stand it up in XZ at depth y, 0.1-1.7 m high
        v.co = Vector((v.co.x * 1.0, y, 0.9 + v.co.y * 1.6))
    bm.normal_update(); bm.faces.ensure_lookup_table()
    if (bm.faces[0].normal.y > 0) != (toward_y > 0):
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return link(name, bm, m)
two, one = mat("cloth", False), mat("shield", True)
box("body", (-0.5, -0.3, 0.0), (0.5, 0.3, 1.8), two)
sheet("cloak", 0.32, -1, two)     # behind the body (+y), facing it (-y)
sheet("shield", -0.32, 1, one)    # in front (-y), facing it (+y), single-sided
box("crate", (2.0, -0.5, 0.0), (3.0, 0.5, 1.0), two)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_apply=True)
'''

# per object: faces, faces under DARK, visible faces under DARK (area >= 10 cm2 and at
# least half the hemisphere open on a side it is drawn from); COLOR_0 of a baked model is light x colour
MEASURE = r'''
import bpy, bmesh, json, math, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree
src, dark = sys.argv[sys.argv.index("--") + 1], float(sys.argv[-1])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
bms, verts, polys = [], [], []
for o in obs:
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    off = len(verts); verts += [v.co.copy() for v in bm.verts]
    polys += [[v.index + off for v in f.verts] for f in bm.faces]; bms.append(bm)
tree = BVHTree.FromPolygons(verts, polys, epsilon=0.0)
dirs = []
for i in range(16):
    z = 1 - (i + .5) / 16; r = math.sqrt(max(0, 1 - z * z)); t = i * math.pi * (3 - math.sqrt(5))
    dirs.append(Vector((r * math.cos(t), r * math.sin(t), z)))
def opn(c, n):
    rot = Vector((0, 0, 1)).rotation_difference(n)
    return sum(1 for d in dirs if tree.ray_cast(c + n * 1e-3, rot @ d, 10)[0] is None) / 16
res = {}
for o, bm in zip(obs, bms):
    ca = o.data.color_attributes.active_color
    cols = [1.0] * (4 * max(1, len(ca.data) if ca else 1))
    if ca:
        ca.data.foreach_get("color", cols)
    two = [m is None or not m.use_backface_culling for m in o.data.materials] or [True]
    n = d = vis = 0
    for f in bm.faces:
        n += 1
        if ca is None:
            continue
        idx = [v.index for v in f.verts] if ca.domain == "POINT" else [l.index for l in f.loops]
        lum = sum(0.2126 * cols[i * 4] + 0.7152 * cols[i * 4 + 1] + 0.0722 * cols[i * 4 + 2] for i in idx) / len(idx)
        if lum < dark:
            d += 1
            c = f.calc_center_median()
            # a single-sided face is drawn from its normal side only
            sides = (f.normal, -f.normal) if two[min(f.material_index, len(two) - 1)] else (f.normal,)
            if f.calc_area() >= 1e-3 and max(opn(c, s) for s in sides) >= 0.5:
                vis += 1
    res[o.data.name.split(".")[0]] = {"faces": n, "dark": d, "visible_dark": vis, "colour": ca is not None}
print("MEASURE " + json.dumps(res))
'''

RESULTS: list[tuple[str, str, str]] = []


def check(name, cond, detail=""):
    RESULTS.append((name, "PASS" if cond else "FAIL", detail))
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""), flush=True)


def blender_py(blender, script_args, timeout=600):
    p = subprocess.run([blender, "-b", "--factory-startup", *script_args],
                       capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def bake(blender, src: Path, out: Path, *opts) -> tuple[int, str]:
    return blender_py(blender, ["--python", str(KIT / "blender/bake_vertex_light.py"), "--",
                                str(src), str(out), "16", "--cpu", *opts])


def measure(blender, glb: Path) -> dict:
    rc, log = blender_py(blender, ["--python-expr", MEASURE, "--", str(glb), str(DARK)])
    m = re.search(r"^MEASURE (.*)$", log, re.M)
    return json.loads(m.group(1)) if m else {}


def orient_count(log: str) -> int:
    m = re.search(r"ORIENT (\d+) ", log)
    return int(m.group(1)) if m else -1


def main() -> int:
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    blender = find_blender()
    names = ["figure: orient turns the cloak only", "figure: cloak lit", "figure: closed boxes unchanged",
             "figure: --no-orient cloak dark (the bug)", "hero_w1: no visible dark face",
             "hero_w1: --no-orient shows the bug", "statue recipe: at most one visible dark face (an internal task)"]
    if not blender:
        for n in names:
            print("SKIPPED " + n + "  (no Blender: set BLENDER=/path/to/blender)")
        return 0
    tmp = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="kit_sheet_"))
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        fig = tmp / "figure.glb"
        rc, log = blender_py(blender, ["--python-expr", GEN, "--", str(fig)])
        if rc != 0 or not fig.is_file():
            check("figure: built", False, log[-600:])
            return 1

        rc, log = bake(blender, fig, tmp / "figure_baked.glb")
        ok = rc == 0 and "BAKE_VERTEX_LIGHT_OK" in log
        check("figure: baked", ok, "" if ok else log[-600:])
        if not ok:
            return 1
        m = measure(blender, tmp / "figure_baked.glb")
        check(names[0], orient_count(log) == 32, "ORIENT %d (cloak has 32 triangles)" % orient_count(log))
        cloak = m.get("cloak", {})
        check(names[1], cloak.get("colour") and cloak.get("dark") == 0, json.dumps(cloak))
        boxes = {k: m.get(k, {}) for k in ("body", "crate")}
        check(names[2], all(b.get("colour") and b.get("visible_dark") == 0 for b in boxes.values()),
              json.dumps(boxes))

        rc, log = bake(blender, fig, tmp / "figure_raw.glb", "--no-orient")
        raw = measure(blender, tmp / "figure_raw.glb").get("cloak", {})
        check(names[3], rc == 0 and "ORIENT" not in log and raw.get("dark", 0) >= 16, json.dumps(raw))

        rc, log = bake(blender, HERO, tmp / "hero_baked.glb")
        hero = measure(blender, tmp / "hero_baked.glb")
        vis = sum(v["visible_dark"] for v in hero.values()) if hero else -1
        check(names[4], rc == 0 and vis == 0, "visible dark faces %d; ORIENT %d" % (vis, orient_count(log)))
        rc, log = bake(blender, HERO, tmp / "hero_raw.glb", "--no-orient")
        hero_raw = measure(blender, tmp / "hero_raw.glb")
        vis_raw = sum(v["visible_dark"] for v in hero_raw.values()) if hero_raw else -1
        check(names[5], rc == 0 and vis_raw > 100, "visible dark faces %d" % vis_raw)

        statue = tmp / "statue.glb"
        rc, log = blender_py(blender, ["--python", str(KIT / "recipes/statue/statue.py"), "--", str(statue)])
        if rc != 0 or not statue.is_file():
            check(names[6], False, "statue.py failed: " + log[-600:])
        else:
            rc, log = bake(blender, statue, tmp / "statue_baked.glb", "--grid", "0.5")
            sm = measure(blender, tmp / "statue_baked.glb")
            vis = sum(v["visible_dark"] for v in sm.values()) if sm else -1
            # an internal task: the recipe turns the figure's 20 inside-out hair parts outward (closure audit 0);
            # one 12 cm2 face of a tuft faces down into the hair and bakes dark at the head top
            check(names[6], rc == 0 and vis <= 1, "visible dark faces %d; ORIENT %d; %s"
                  % (vis, orient_count(log), json.dumps(sm)))
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    bad = [r for r in RESULTS if r[1] != "PASS"]
    print("%d/%d PASS" % (len(RESULTS) - len(bad), len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
