"""UV-map faces of a model onto one strip of a trim sheet (mouldings, frames, beams, straps).

Detail lives in painted textures, not triangles (the AGENT_KIT art bar): a cornice, a
door frame, a beam or an iron strap is a plain strip of faces whose UVs run along one
strip of a shared trim sheet. The kit's sheet (`python3 kit/tools/paint_materials.py
out --materials trim`) has 8 horizontal strips, top to bottom: cornice, frame, moulding,
carved, dentil, rope, beam, strap, each 1/8 of the height, tiling along u every 4 m.

For every flat face (coplanar triangles together), u runs along its longest outline edge at the sheet's scale (one
repeat per --tile-m metres, continuous across neighbouring faces of a straight run) and
v spans the strip across it (upper edge of an upright face at the strip's top).

    iamar-world blender-run kit/blender/trim_map.py -- in.glb out.glb --strip cornice [options]

Options:
  --strip NAME|N    strip by name (above) or index 0-7 (required)
  --material NAMES  only faces with these materials (comma-separated; default every face)
  --sheet PNG       give the mapped faces a material showing this trim sheet (default:
                    they keep their material, which must already use the sheet)
  --tile-m M        metres per repeat along u (default 4, as kit/tools/paint_materials.py)
  --strips N        strips in the sheet (default 8)
  --across-m M      metres across the strip's full height (default: fit each face)

Prints TRIM_MAP_OK with the number of faces mapped.

Blender 4.2-4.5 (tested 4.5 LTS). No add-ons.
"""
import os
import sys

import bmesh
import bpy

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402

STRIPS = ["cornice", "frame", "moulding", "carved", "dentil", "rope", "beam", "strap"]


def parse():
    p = K.make_parser("trim_map.py", __doc__.split("\n\n")[0])
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--strip", required=True)
    p.add_argument("--material", default="")
    p.add_argument("--sheet", metavar="PNG")
    p.add_argument("--tile-m", type=float, default=4.0)
    p.add_argument("--strips", type=int, default=8)
    p.add_argument("--across-m", type=float, default=0.0)
    a = K.parse_args(p)
    if a.strip.isdigit():
        a.index = int(a.strip)
    elif a.strip in STRIPS:
        a.index = STRIPS.index(a.strip)
    else:
        K.fail("unknown strip %r: give an index or one of %s" % (a.strip, ", ".join(STRIPS)))
    if not 0 <= a.index < a.strips:
        K.fail("strip index %d outside 0-%d" % (a.index, a.strips - 1))
    return a


def sheet_material(path):
    if not os.path.isfile(path):
        K.fail("no such trim sheet: %s" % path)
    img = bpy.data.images.load(os.path.abspath(path))
    img.pack()
    m = bpy.data.materials.new("trim_" + os.path.splitext(os.path.basename(path))[0])
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    tx = m.node_tree.nodes.new("ShaderNodeTexImage")
    tx.image = img
    m.node_tree.links.new(tx.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    b.inputs["Metallic"].default_value = 0.0
    return m


def flat_regions(faces):
    """Groups connected faces that lie in one plane (normals within about 2.5 degrees)."""
    todo = set(faces)
    out = []
    while todo:
        f = todo.pop()
        region, stack = [f], [f]
        while stack:
            g = stack.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if h in todo and h.normal.dot(f.normal) > 0.999 and h.material_index == f.material_index:
                        todo.discard(h)
                        region.append(h)
                        stack.append(h)
        out.append(region)
    return out


def main():
    a = parse()
    K.reset()
    obs = K.meshes(K.import_glb(a.input))
    if not obs:
        K.fail("no mesh in %s" % a.input)
    K.select_only(obs, obs[0])
    bpy.ops.object.make_single_user(object=True, obdata=True)
    wanted = {n.strip() for n in a.material.split(",") if n.strip()}
    sheet = sheet_material(a.sheet) if a.sheet else None
    top = 1.0 - a.index / float(a.strips)          # UV v of the strip's upper edge
    height = 1.0 / a.strips
    mapped = 0
    for ob in obs:
        me = ob.data
        names = [m.name if m else "" for m in me.materials]
        if wanted and not wanted.intersection(names):
            continue
        slot = None
        if sheet is not None:
            me.materials.append(sheet)
            slot = len(me.materials) - 1
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)   # triangles of a face connect
        uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
        mw = ob.matrix_world
        m3 = mw.to_3x3()
        chosen = [f for f in bm.faces if not wanted or (f.material_index < len(names) and names[f.material_index] in wanted)]
        for region in flat_regions(chosen):
            # long axis: the region's longest outline edge (a quad's diagonal is never on the outline)
            inside = set(region)
            outline = [e for f in region for e in f.edges if sum(1 for g in e.link_faces if g in inside) == 1]
            longest = max(outline or [e for f in region for e in f.edges], key=lambda e: e.calc_length())
            t = (m3 @ (longest.verts[1].co - longest.verts[0].co)).normalized()
            n = (m3 @ region[0].normal).normalized()
            across = n.cross(t).normalized()
            if across.z < 0 or (abs(across.z) < 1e-6 and across.y < 0):
                across = -across                    # upper edge of upright faces at the top
            vs_all = [(mw @ l.vert.co).dot(across) for f in region for l in f.loops]
            hi, lo = max(vs_all), min(vs_all)
            span = a.across_m if a.across_m > 0 else max(hi - lo, 1e-6)
            for f in region:
                for l in f.loops:
                    p = mw @ l.vert.co
                    frac = min(1.0, max(0.0, (hi - p.dot(across)) / span))   # 0 at the upper edge
                    l[uv].uv = (p.dot(t) / a.tile_m, top - frac * height)
                if slot is not None:
                    f.material_index = slot
                mapped += 1
        bm.to_mesh(me)
        bm.free()
        me.update()
    if mapped == 0:
        K.fail("no face matched (materials in the model: %s)" %
               ", ".join(sorted({m.name for o in obs for m in o.data.materials if m})))
    K.export_glb(a.output, None, colors=any(o.data.color_attributes for o in obs), animations=True)
    K.log("TRIM_MAP_OK", a.output, "faces %d" % mapped, "strip %d (%s)" % (a.index, STRIPS[a.index] if a.index < 8 else "?"))


K.run(main)
