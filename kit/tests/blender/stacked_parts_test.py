#!/usr/bin/env python3
"""Parts that touch exactly: a plain join welds into non-manifold edges, the starter's
boolean-union join passes the closure audit (an internal task, desert blind test gap 6).

Builds two 1 m boxes stacked face to face and a 12-sided dome standing on a drum of
the same radius, once with a plain join and once with starter_build.py's `join`
(exact boolean union), then runs weld.py and closure_audit.py on each. Also runs
starter_build.py itself and checks that its cottage and tree weld and close. Needs
Blender 4.2+ (BLENDER=..., on PATH or in a usual folder); without it every check is
SKIPPED and the test exits 0.

    python3 kit/tests/blender/stacked_parts_test.py [--keep DIR]
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
TOOLS = KIT / "blender"
sys.path.insert(0, str(KIT / "tests"))
from blender_tools_test import find_blender  # noqa: E402

GEN = r'''
import bpy, sys
args = sys.argv[sys.argv.index("--") + 1:]
out, tools = args[0], args[1]
sys.path.insert(0, tools)
import starter_build as S
def export(name, o):
    bpy.ops.object.select_all(action="DESELECT"); o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=out + "/" + name, export_format="GLB", use_selection=True, export_apply=True)
def plain_join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join(); objs[0].name = name
    return objs[0]
def boxes():
    m = S.material("stone", (.6, .6, .55))
    return [S.box("low", (1, 1, 1), (0, 0, 0.5), m, 0), S.box("high", (1, 1, 1), (0, 0, 1.5), m, 0)]
def dome():
    m = S.material("plaster", (.8, .75, .6))
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=1.0, depth=2.0, location=(0, 0, 1)); d = bpy.context.active_object
    d.data.materials.append(m)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=1.0, location=(0, 0, 2)); h = bpy.context.active_object
    h.data.materials.append(m)
    import bmesh
    bm = bmesh.new(); bm.from_mesh(h.data)
    # keep the upper half and close it with a cap on the drum's top (z = 2)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_inner=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bm.to_mesh(h.data); bm.free()
    return [d, h]
for name, make in (("boxes", boxes), ("dome", dome)):
    S.clear(); export(name + "_plain.glb", plain_join(make(), name))
    S.clear(); export(name + "_union.glb", S.join(make(), name))
print("GEN_OK")
'''

RESULTS: list[tuple[str, str]] = []
NAMES = ["generate", "boxes_plain_warns", "boxes_plain_fails", "boxes_union_closed", "dome_plain_fails",
         "dome_union_closed", "starter_build", "starter_cottage_closed", "starter_tree_closed"]


def check(name, cond, detail=""):
    RESULTS.append((name, "PASS" if cond else "FAIL"))
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""), flush=True)


def run(blender, args):
    p = subprocess.run([blender, "-b", "--factory-startup"] + args, capture_output=True, text=True, timeout=600)
    return p.returncode == 0, p.stdout + p.stderr


def weld_and_close(blender, w, name):
    """weld.py then closure_audit.py; returns (weld log, weld report, closure ok, closure report)."""
    src, welded = w / (name + ".glb"), w / (name + "_w.glb")
    ok, wlog = run(blender, ["--python", str(TOOLS / "weld.py"), "--", str(src), str(welded), "--report", str(w / (name + "_weld.json"))])
    wrep = json.loads((w / (name + "_weld.json")).read_text()) if ok else {}
    if not ok:
        print(wlog[-2000:])
        return wlog, wrep, False, {}
    cok, clog = run(blender, ["--python", str(TOOLS / "closure_audit.py"), "--", str(welded), "--report", str(w / (name + "_c.json"))])
    crep = json.loads((w / (name + "_c.json")).read_text()) if (w / (name + "_c.json")).is_file() else {}
    return wlog, wrep, cok and "CLOSURE_OK" in clog, crep


def main() -> int:
    keep = Path(sys.argv[sys.argv.index("--keep") + 1]).resolve() if "--keep" in sys.argv else None
    blender = find_blender()
    if blender is None:
        for n in NAMES:
            print("SKIPPED " + n + "  (no Blender: set BLENDER=/path/to/blender)")
        print("kit stacked parts tests: skipped (no Blender)")
        return 0
    print("BLENDER", blender, flush=True)
    w = Path(keep or tempfile.mkdtemp(prefix="iamar-kit-stacked-"))
    w.mkdir(parents=True, exist_ok=True)
    try:
        ok, log = run(blender, ["--python-expr", GEN, "--", str(w), str(TOOLS)])
        check("generate", ok and "GEN_OK" in log)
        if not ok:
            print(log[-3000:])
            return 1

        wlog, wrep, closed, crep = weld_and_close(blender, w, "boxes_plain")
        check("boxes_plain_warns", "WELD_NONMANIFOLD" in wlog and wrep.get("nonmanifold_edges", 0) > 0,
              "weld report nonmanifold_edges=%s" % wrep.get("nonmanifold_edges"))
        check("boxes_plain_fails", not closed and crep.get("totals", {}).get("nonmanifold", 0) > 0,
              "closure nonmanifold=%s" % crep.get("totals", {}).get("nonmanifold"))
        wlog, wrep, closed, crep = weld_and_close(blender, w, "boxes_union")
        check("boxes_union_closed", closed and "WELD_NONMANIFOLD" not in wlog and wrep.get("nonmanifold_edges") == 0,
              str(crep.get("totals")))
        _, _, closed, crep = weld_and_close(blender, w, "dome_plain")
        check("dome_plain_fails", not closed and crep.get("totals", {}).get("nonmanifold", 0) > 0,
              "closure nonmanifold=%s" % crep.get("totals", {}).get("nonmanifold"))
        _, wrep, closed, crep = weld_and_close(blender, w, "dome_union")
        check("dome_union_closed", closed and wrep.get("nonmanifold_edges") == 0, str(crep.get("totals")))

        world = w / "world"
        ok, log = run(blender, ["--python", str(TOOLS / "starter_build.py"), "--", str(world)])
        check("starter_build", ok and log.count("BUILT ") == 2, "; ".join(l for l in log.splitlines() if l.startswith("BUILT")))
        for name in ("cottage", "tree"):
            if (world / "assets" / (name + ".glb")).is_file():
                shutil.copy(world / "assets" / (name + ".glb"), w / ("starter_" + name + ".glb"))
                _, wrep, closed, crep = weld_and_close(blender, w, "starter_" + name)
                check("starter_%s_closed" % name, closed and wrep.get("nonmanifold_edges") == 0, str(crep.get("totals")))
            else:
                check("starter_%s_closed" % name, False, "not built")
    finally:
        if keep is None:
            shutil.rmtree(w, ignore_errors=True)
    failed = [r for r in RESULTS if r[1] == "FAIL"]
    print("kit stacked parts tests: %d/%d" % (len(RESULTS) - len(failed), len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
