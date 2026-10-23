#!/usr/bin/env python3
"""The time-independent bake for a world whose clock runs (an internal task): kit/blender/bake_vertex_ao.py
with neighbours from `lighting.py ao-args`.

Builds a world in a temporary folder: a 12 x 12 m ground grid (0.5 m vertices) placed at
[1, 0, -1] turned 90 degrees, and a long 8 x 2 x 4 m house turned 30 degrees beside it, with
`day_length_minutes` > 0. Then checks:
  - `lighting.py ao-args --world W --object ground` prints one --occluder (the house) and
    leaves out a far house and a swaying tree;
  - the ground baked alone stays white (a flat plane occludes nothing);
  - the ground baked with that occluder is dark only where the house really stands (every
    vertex under 0.9 lies within the AO distance of the house's world footprint, and the
    vertices under the house are dark), white far from it, so the matrices and the glTF ->
    Blender axis change are right;
  - the output keeps lit materials (no KHR_materials_unlit), exports only the ground and carries
    asset.extras.iamar_bake.kind == "sky_ao";
  - `iamar-world audit dark-bake` reports the sky/AO bake on the clock world without a warning;
  - --occluder with --local is refused.

Needs Blender 4.2+ (BLENDER=/path/to/blender, on PATH, or in ~/opt/blender-*); without it every
check is reported SKIPPED and the test exits 0. Under a minute on a 4-thread CPU.

    python3 kit/tests/blender/sky_ao_bake_test.py [--keep DIR]
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(KIT / "tests"))
from blender_tools_test import Glb, find_blender  # noqa: E402

NAMES = ["ao_args", "alone_white", "occluded_where_house", "under_house_dark", "far_white",
         "lit_materials", "only_ground_exported", "marker", "audit_reports", "local_refused"]
DIST = 1.5
GROUND = {"position": [1.0, 0.0, -1.0], "yaw": 90.0}
HOUSE = {"position": [2.0, 0.0, 1.5], "yaw": 30.0, "half": (4.0, 1.0)}   # 8 x 2 m footprint

GEN = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
def export(name, path):
    bpy.ops.object.select_all(action="DESELECT")
    ob = bpy.data.objects[name]; ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_yup=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=25, y_subdivisions=25, size=12)
bpy.context.active_object.name = "ground"
# glTF x 8 m, z 2 m (Blender y), 4 m high, standing on y = 0
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 2))
h = bpy.context.active_object; h.name = "house"; h.scale = (8, 2, 4)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
export("ground", out + "/assets/ground.glb")
export("house", out + "/assets/house.glb")
print("GEN_OK")
'''

RESULTS: list[tuple[str, str]] = []


def check(name, ok, detail=""):
    RESULTS.append((name, "PASS" if ok else "FAIL"))
    print(("PASS " if ok else "FAIL ") + name + (("  " + detail) if detail else ""), flush=True)


def yaw_apply(p, yaw_deg, pos):
    """glTF/Godot placement of a local point: Ry(yaw) then the position."""
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    x, y, z = p
    return (c * x + s * z + pos[0], y + pos[1], -s * x + c * z + pos[2])


def footprint_gap(wx, wz):
    """Horizontal distance from a world point to the house footprint (0 inside)."""
    c, s = math.cos(math.radians(HOUSE["yaw"])), math.sin(math.radians(HOUSE["yaw"]))
    dx, dz = wx - HOUSE["position"][0], wz - HOUSE["position"][2]
    lx, lz = c * dx - s * dz, s * dx + c * dz   # inverse of Ry
    hx, hz = HOUSE["half"]
    return math.hypot(max(abs(lx) - hx, 0.0), max(abs(lz) - hz, 0.0))


def ao_values(path):
    g = Glb(path)
    pts = []
    for p in g.prims():
        pos = g.accessor(p["attributes"]["POSITION"])
        col = g.accessor(p["attributes"]["COLOR_0"]) if "COLOR_0" in p["attributes"] else [[1, 1, 1]] * len(pos)
        pts += [(q, c[0]) for q, c in zip(pos, col)]
    return g, pts


def main() -> int:
    keep = Path(sys.argv[sys.argv.index("--keep") + 1]).resolve() if "--keep" in sys.argv else None
    blender = find_blender()
    if blender is None:
        for n in NAMES:
            print("SKIPPED " + n + "  (no Blender: set BLENDER=/path/to/blender)")
        print("kit sky/AO bake tests: skipped (no Blender)")
        return 0
    w = Path(keep or tempfile.mkdtemp(prefix="iamar-kit-skyao-"))
    (w / "assets").mkdir(parents=True, exist_ok=True)
    try:
        p = subprocess.run([blender, "-b", "--factory-startup", "--python-expr", GEN, "--", str(w)],
                           capture_output=True, text=True, timeout=300)
        if "GEN_OK" not in p.stdout:
            print(p.stdout[-2000:], p.stderr[-2000:])
            check("generate", False)
            return 1
        scene = {"format": "iamar-world", "environment": {"time_of_day": 10, "day_length_minutes": 24},
                 "objects": [
                     {"id": "ground", "asset": "assets/ground.glb", "position": GROUND["position"],
                      "rotation": [0, GROUND["yaw"], 0], "collision": "mesh"},
                     {"id": "house", "asset": "assets/house.glb", "position": HOUSE["position"],
                      "rotation": [0, HOUSE["yaw"], 0], "collision": "box"},
                     {"id": "far_house", "asset": "assets/house.glb", "position": [40, 0, 40]},
                     {"id": "tree", "asset": "assets/house.glb", "position": [0, 0, 0], "sway": True}]}
        (w / "scene.json").write_text(json.dumps(scene, indent=1))

        p = subprocess.run([sys.executable, str(KIT / "style" / "lighting" / "lighting.py"), "ao-args",
                            "--world", str(w), "--object", "ground"], capture_output=True, text=True)
        args = shlex.split(p.stdout)
        check("ao_args", p.returncode == 0 and len(args) == 1 and args[0].startswith("--occluder=")
              and "house.glb" in args[0] and "tree" in p.stderr, p.stdout + p.stderr)

        tool = KIT / "blender" / "bake_vertex_ao.py"
        base = [blender, "-b", "--factory-startup", "--python", str(tool), "--"]
        common = ["--distance", str(DIST), "--samples", "16", "--cpu"]
        p = subprocess.run(base + [str(w / "assets/ground.glb"), str(w / "alone.glb")] + common,
                           capture_output=True, text=True, timeout=600)
        _, pts = ao_values(w / "alone.glb") if (w / "alone.glb").is_file() else (None, [])
        check("alone_white", p.returncode == 0 and pts and min(a for _, a in pts) > 0.97,
              "min %.3f" % min((a for _, a in pts), default=0))

        p = subprocess.run(base + [str(w / "assets/ground.glb"), str(w / "assets/ground_ao.glb")] + common + args,
                           capture_output=True, text=True, timeout=600)
        if p.returncode != 0 or not (w / "assets/ground_ao.glb").is_file():
            print(p.stdout[-3000:], p.stderr[-3000:])
        g, pts = ao_values(w / "assets/ground_ao.glb") if (w / "assets/ground_ao.glb").is_file() else (None, [])
        world_pts = [(yaw_apply(q, GROUND["yaw"], GROUND["position"]), a) for q, a in pts]
        dark = [(q, a) for q, a in world_pts if a < 0.9]
        stray = [q for q, a in dark if footprint_gap(q[0], q[2]) > DIST + 0.3]
        check("occluded_where_house", len(dark) >= 20 and not stray,
              "%d dark vertices, %d away from the house (first %s)" % (len(dark), len(stray), stray[:1]))
        under = [a for q, a in world_pts if footprint_gap(q[0], q[2]) == 0.0]
        check("under_house_dark", len(under) >= 10 and max(under) < 0.6,
              "%d vertices under the house, lightest %.3f" % (len(under), max(under, default=1)))
        far = [a for q, a in world_pts if footprint_gap(q[0], q[2]) > DIST + 0.5]
        check("far_white", len(far) > 100 and min(far) > 0.97, "%d far vertices, darkest %.3f" % (len(far), min(far, default=0)))
        js = g.js if g else {}
        check("lit_materials", g is not None and not any("KHR_materials_unlit" in (m.get("extensions") or {})
                                                         for m in js.get("materials", [])))
        check("only_ground_exported", g is not None and len(js.get("meshes", [])) == 1,
              "%d meshes" % len(js.get("meshes", [])))
        mark = (js.get("asset", {}).get("extras") or {}).get("iamar_bake", {})
        check("marker", mark.get("kind") == "sky_ao" and mark.get("occluders") == 1, json.dumps(mark))

        scene["objects"][0]["asset"] = "assets/ground_ao.glb"
        scene["objects"] = scene["objects"][:2]
        (w / "scene.json").write_text(json.dumps(scene, indent=1))
        p = subprocess.run([sys.executable, str(KIT / "audit" / "audit.py"), "dark-bake", str(w), "--json"],
                           capture_output=True, text=True)
        try:
            items = json.loads(p.stdout)["items"]
        except ValueError:
            items = []
        check("audit_reports", p.returncode == 0 and "sky_ao_objects=1" in p.stdout
              and not [i for i in items if i["level"] in ("WARN", "ERROR")], p.stdout[-1500:])

        p = subprocess.run(base + [str(w / "assets/ground.glb"), str(w / "local.glb"), "--local"] + common + args,
                           capture_output=True, text=True, timeout=300)
        check("local_refused", p.returncode != 0 and not (w / "local.glb").exists())
    finally:
        if keep is None:
            shutil.rmtree(w, ignore_errors=True)
    bad = [n for n, r in RESULTS if r != "PASS"]
    print("kit sky/AO bake tests: %d/%d" % (len(RESULTS) - len(bad), len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
