"""Make a distance LOD chain of a model and report triangles per LOD (and against a budget).

Kit recipe `lod_chain`: far objects use much lower-poly versions, so the triangle budget
goes to what is near. Each level is cut from the full model (never from the level
before), at about 50% and 20% of the triangles by default. Buildings and hard-surface
props lose faces by planar dissolve first (flat walls keep their outline and UVs), then
by collapse if they are still over the target; organic shapes use collapse only.

    iamar-world blender-run kit/blender/lods.py -- in.glb out_prefix [options]

writes out_prefix_lod0.glb (the welded input), out_prefix_lod1.glb, ... and
out_prefix_lods.json (triangles per level, ratio reached, efficiency against --budget).

Options:
  --ratios R,R,...   triangle ratio per level after LOD0 (default 0.5,0.2)
  --targets N,N,...  triangle targets per level instead of ratios (e.g. 1500,600)
  --mode M           auto (planar, then collapse: buildings, furniture), collapse (organic:
                     creatures, trees, statues) or planar (only flat faces merged)
                     (default auto)
  --angle DEG        planar dissolve angle limit (default 5)
  --budget N         the asset's LOD0 triangle budget (AGENT_KIT art bar: building 3000,
                     landmark 15000, prop 300, creature 6000, character 12000); the report
                     gives Efficiency = 100 at or under it, else 100 x budget / triangles
  --weld M           merge vertices closer than this first (default 0.002; 0 = off)

The browser also makes LODs of every mesh by itself (Godot mesh LOD, threshold 4 px;
recipe `lod_chain`), so in a world package LOD0 goes in assets/ and the levels serve
the triangle report, impostor sources and worlds that place far versions themselves.
Prints LOD <n> <triangles> lines and LODS_OK.

Blender 4.2-4.5 (tested 4.5 LTS). No add-ons.
"""
import json
import math
import os
import sys

import bmesh
import bpy

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kitlib as K  # noqa: E402


def parse():
    p = K.make_parser("lods.py", __doc__.split("\n\n")[0])
    p.add_argument("input")
    p.add_argument("prefix")
    p.add_argument("--ratios", default="0.5,0.2")
    p.add_argument("--targets", default="")
    p.add_argument("--mode", choices=("auto", "collapse", "planar"), default="auto")
    p.add_argument("--angle", type=float, default=5.0)
    p.add_argument("--budget", type=int, default=0)
    p.add_argument("--weld", type=float, default=0.002)
    return K.parse_args(p)


def load(path, weld):
    K.reset()
    obs = K.meshes(K.import_glb(path))
    if not obs:
        K.fail("no mesh in %s" % path)
    K.select_only(obs, obs[0])
    bpy.ops.object.make_single_user(object=True, obdata=True)
    if weld > 0:
        for ob in obs:
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=weld)
            bm.to_mesh(ob.data)
            bm.free()
            K.reshade(ob, 30.0)
    return obs


def apply_mod(ob, mod):
    K.select_only([ob], ob)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def decimate(ob, target, mode, angle):
    """Cuts one mesh to about `target` triangles."""
    if K.tris([ob]) <= target:
        return
    if mode in ("auto", "planar"):
        m = ob.modifiers.new("lod_planar", "DECIMATE")
        m.decimate_type = "DISSOLVE"
        m.angle_limit = math.radians(angle)
        m.delimit = {"MATERIAL", "SEAM", "UV"}
        apply_mod(ob, m)
        # dissolve leaves n-gons; count what the export will triangulate
    now = K.tris([ob])
    if mode in ("auto", "collapse") and now > target:
        m = ob.modifiers.new("lod_collapse", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = max(0.001, min(1.0, target / float(now)))
        m.use_collapse_triangulate = True
        apply_mod(ob, m)


def efficiency(tris, budget):
    if budget <= 0:
        return None
    return 100.0 if tris <= budget else round(100.0 * budget / tris, 1)


def main():
    a = parse()
    obs = load(a.input, a.weld)
    per0 = {o.name: K.tris([o]) for o in obs}
    tris0 = sum(per0.values())
    if a.targets:
        targets = [int(t) for t in a.targets.split(",") if t.strip()]
        ratios = [t / float(tris0) for t in targets]
    else:
        ratios = [float(r) for r in a.ratios.split(",") if r.strip()]
    if any(not (0.0 < r < 1.0) for r in ratios):
        K.fail("every LOD ratio must be between 0 and 1 (got %s for %d triangles)" % (ratios, tris0))
    if ratios != sorted(ratios, reverse=True):
        K.fail("LOD levels must get smaller: %s" % ratios)
    levels = [{"lod": 0, "file": a.prefix + "_lod0.glb", "triangles": tris0, "ratio": 1.0}]
    K.export_glb(levels[0]["file"], None, colors=any(o.data.color_attributes for o in obs), animations=True)
    K.log("LOD", 0, tris0)
    for i, r in enumerate(ratios, start=1):
        obs = load(a.input, a.weld)
        for ob in obs:
            decimate(ob, max(4, int(per0.get(ob.name, K.tris([ob])) * r)), a.mode, a.angle)
        n = K.tris(obs)
        path = "%s_lod%d.glb" % (a.prefix, i)
        K.export_glb(path, None, colors=any(o.data.color_attributes for o in obs), animations=True)
        levels.append({"lod": i, "file": path, "triangles": n, "ratio_asked": round(r, 4),
                       "ratio": round(n / float(tris0), 4)})
        K.log("LOD", i, n, "(asked %.0f%%, reached %.0f%%)" % (100 * r, 100.0 * n / tris0))
    for lo, hi in zip(levels[1:], levels[:-1]):
        if lo["triangles"] >= hi["triangles"]:
            K.log("WARNING LOD%d (%d tris) is not smaller than LOD%d (%d): the shape has no faces left to cut"
                  % (lo["lod"], lo["triangles"], hi["lod"], hi["triangles"]))
    rep = {"input": a.input, "mode": a.mode, "angle_deg": a.angle, "weld_m": a.weld, "levels": levels,
           "budget": a.budget or None, "efficiency": efficiency(tris0, a.budget)}
    with open(a.prefix + "_lods.json", "w") as f:
        json.dump(rep, f, indent=1)
    K.log("LODS_OK", a.prefix, "tris", " / ".join(str(l["triangles"]) for l in levels),
          ("efficiency %.1f (budget %d)" % (rep["efficiency"], a.budget)) if a.budget else "")


K.run(main)
