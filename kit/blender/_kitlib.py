"""Shared helpers for the kit's Blender tools (kit/blender/*.py). Not a tool itself.

Each tool puts its own folder on sys.path and imports this module, so the tools
work from any current directory and from a copy of kit/blender/ anywhere.
Written for Blender 4.2-4.5 (tested on 4.5 LTS); only the Python API that ships
with Blender is used.
"""
import argparse
import json
import os
import struct
import sys

import bpy


def parse_args(parser):
    """argparse on the arguments after Blender's `--` (all of them when there is none)."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return parser.parse_args(argv)


def make_parser(prog, description):
    return argparse.ArgumentParser(prog="iamar-world blender-run kit/blender/%s --" % prog,
                                   description=description,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)


def log(*a):
    print(*a, flush=True)


def fail(msg):
    print("ERROR: " + msg, file=sys.stderr, flush=True)
    sys.exit(1)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    """Imports a .glb/.gltf into the current scene; returns the new objects."""
    if not os.path.isfile(path):
        fail("no such file: %s" % path)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(path))
    return [o for o in bpy.data.objects if o not in before]


def meshes(objs=None):
    return [o for o in (objs if objs is not None else bpy.context.scene.objects) if o.type == "MESH"]


def select_only(objs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)


def tris(objs):
    return sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons)


def setup_cycles(samples, device="auto"):
    """Cycles on the first GPU backend that really has a device of its type
    (OPTIX, CUDA, HIP, ONEAPI, METAL), else the CPU. Setting a backend succeeds on a
    machine without that hardware, so each one's device list is checked.
    device: auto | cpu. Returns a label such as 'ONEAPI GPU' or 'NONE CPU'."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    chosen = "NONE"
    if device != "cpu":
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
        except KeyError:
            prefs = None
        if prefs is not None:
            for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
                try:
                    prefs.compute_device_type = kind
                except TypeError:
                    continue
                prefs.refresh_devices()
                if any(d.type == kind for d in prefs.devices):
                    chosen = kind
                    break
            prefs.compute_device_type = chosen
            prefs.refresh_devices()
            for d in prefs.devices:
                d.use = d.type != "CPU"
    sc.cycles.device = "GPU" if chosen != "NONE" else "CPU"
    label = "%s %s" % (chosen, sc.cycles.device)
    log("BAKE_DEVICE", label)
    return label


def ensure_material(ob, name="kit_default"):
    """Bakes need a node material on every face; give bare meshes a plain grey one."""
    if not ob.data.materials or all(m is None for m in ob.data.materials):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        ob.data.materials.clear()
        ob.data.materials.append(m)
    for i, m in enumerate(ob.data.materials):
        if m is None:
            m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
            m.use_nodes = True
            ob.data.materials[i] = m
        elif not m.use_nodes:
            m.use_nodes = True


def export_glb(path, objs=None, colors=False, tangents=False, animations=False):
    """glTF binary, +Y up, modifiers applied. objs None = every object in the scene.
    colors: write the active colour attribute as COLOR_0."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    if objs is not None:
        select_only(objs)
    kw = dict(filepath=os.path.abspath(path), export_format="GLB", use_selection=objs is not None,
              export_apply=True, export_yup=True, export_texcoords=True, export_normals=True,
              export_tangents=tangents, export_materials="EXPORT", export_image_format="AUTO",
              export_animations=animations, export_extras=False, export_cameras=False, export_lights=False)
    try:
        bpy.ops.export_scene.gltf(export_vertex_color="ACTIVE" if colors else "NONE", **kw)
    except TypeError:   # Blender before 4.2
        bpy.ops.export_scene.gltf(export_colors=colors, **kw)
    log("EXPORTED", path, os.path.getsize(path), "bytes")


def read_glb_json(path):
    with open(path, "rb") as f:
        data = f.read()
    jlen = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + jlen].decode("utf-8"))


def node_extras(path):
    """{node name: extras} for every node of a .glb that has extras (e.g. x-class)."""
    return {n["name"]: n["extras"] for n in read_glb_json(path).get("nodes", []) if n.get("name") and n.get("extras")}


def patch_node_extras(path, extras):
    """Puts node extras back on a .glb Blender re-exported: for each node whose name is in
    extras, the saved keys are set (other extras on the node are kept). Returns how many
    nodes were patched."""
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, _total = struct.unpack("<III", data[:12])
    jlen = struct.unpack("<I", data[12:16])[0]
    js = json.loads(data[20:20 + jlen].decode("utf-8"))
    rest = data[20 + jlen:]
    done = 0
    for n in js.get("nodes", []):
        if n.get("name") in extras:
            n.setdefault("extras", {}).update(extras[n["name"]])
            done += 1
    if done:
        jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
        jb += b" " * ((4 - len(jb) % 4) % 4)
        out = struct.pack("<II", len(jb), 0x4E4F534A) + jb + rest
        with open(path, "wb") as f:
            f.write(struct.pack("<III", magic, ver, 12 + len(out)) + out)
    return done


def patch_asset_extras(path, extras):
    """Sets keys of the .glb's asset.extras (other keys kept): a model-level note such as
    the kind of bake, which the Blender exporter drops (export_extras is off)."""
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, _total = struct.unpack("<III", data[:12])
    jlen = struct.unpack("<I", data[12:16])[0]
    js = json.loads(data[20:20 + jlen].decode("utf-8"))
    rest = data[20 + jlen:]
    js.setdefault("asset", {"version": "2.0"}).setdefault("extras", {}).update(extras)
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    out = struct.pack("<II", len(jb), 0x4E4F534A) + jb + rest
    with open(path, "wb") as f:
        f.write(struct.pack("<III", magic, ver, 12 + len(out)) + out)


def patch_unlit(path, names=None):
    """Marks the materials of a .glb unlit (KHR_materials_unlit), so the browser
    shows the baked texture as-is instead of lighting it a second time.
    names: only materials with these names (None = every material)."""
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, _total = struct.unpack("<III", data[:12])
    jlen = struct.unpack("<I", data[12:16])[0]
    js = json.loads(data[20:20 + jlen].decode("utf-8"))
    rest = data[20 + jlen:]
    for m in js.get("materials", []):
        if names is not None and m.get("name") not in names:
            continue
        m.setdefault("extensions", {})["KHR_materials_unlit"] = {}
        pbr = m.setdefault("pbrMetallicRoughness", {})
        pbr["metallicFactor"] = 0.0
        pbr["roughnessFactor"] = 1.0
        m.pop("normalTexture", None)
        m.pop("occlusionTexture", None)
    used = js.setdefault("extensionsUsed", [])
    if "KHR_materials_unlit" not in used:
        used.append("KHR_materials_unlit")
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    out = struct.pack("<II", len(jb), 0x4E4F534A) + jb + rest
    with open(path, "wb") as f:
        f.write(struct.pack("<III", magic, ver, 12 + len(out)) + out)


def reshade(ob, sharp_deg):
    """After welding: smooth shading with hard edges where faces meet at more than
    sharp_deg degrees (and on open borders), and no stale custom normals. Without this,
    welding a hard-edged model (a box, a wall) would smooth its corners."""
    import bmesh
    import math
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lim = math.radians(sharp_deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        e.smooth = e.is_manifold and e.calc_face_angle(math.pi) <= lim
    bm.to_mesh(ob.data)
    bm.free()
    select_only([ob], ob)
    if ob.data.has_custom_normals:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    ob.data.update()


# glTF is +Y up, Blender +Z up: glTF (x, y, z) is Blender (x, -z, y).
def gltf_to_blender(v):
    x, y, z = v
    return (x, -z, y)


def run(main):
    """Runs a tool's main(); any error exits Blender with status 1 (an uncaught
    exception in a --python script would otherwise still exit 0)."""
    import traceback
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()
        sys.exit(1)
