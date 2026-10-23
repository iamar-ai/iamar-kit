"""One command for a game-ready model: weld, closure audit, atlas, normal bake, light bake, LODs.

Runs the kit's Blender tools in the fixed build order of kit/blender/README.md, each in
its own headless Blender (the one running this script), and stops at the first step
that fails. A failed closure audit stops the build: fix the model (or name parts no
player can see past with --skip) before baking.

    iamar-world blender-run kit/blender/asset_pipeline.py -- model.glb out_dir [options]

Steps (each writes out_dir/<n>_<step>.glb; the last one is out_dir/<name>.glb plus its
LOD files):
  1 weld            weld.py (always)
  2 closure         closure_audit.py (always; --no-closure to skip, e.g. for cards)
  3 atlas           atlas.py, with --atlas (one material, one texture)
  4 normals         bake_normals.py, with --high HIGH.glb (detail from a high-poly model)
  5 light           bake_unlit.py with --light unlit, bake_vertex_ao.py with --light ao
  6 lods            lods.py (always): triangles per LOD and efficiency against --budget

Options:
  --name NAME         base name of the final files (default: the input's name)
  --budget N          LOD0 triangle budget (building 3000, landmark 15000, prop 300,
                      creature 6000, character 12000)
  --skip PATTERNS     closure audit: object names not audited (e.g. "ground*")
  --ground H          closure audit: edges at or below glTF height H are sealed
  --allow-nonmanifold closure audit: report edges shared by 3+ faces but do not fail on them
                      (style-gen houses: roof sheets meet culled wall tops; use with --ground 0)
  --min-edge M        closure audit: ignore boundary edges shorter than M (style-gen houses: 0.2)
  --no-closure        skip the closure audit
  --atlas             run the atlas step (--atlas-size N, default 1024)
  --high FILE         run the normal bake from this high-poly model (--normal-size N, default 1024)
  --light KIND        none | unlit | ao (default none)
  --samples N         light bake samples (default 64)
  --sun X,Y,Z         unlit bake: direction towards the sun, glTF axes (default 0.4,0.8,0.35)
  --sun-strength S    unlit bake: sun brightness (default 3.0)
  --no-sun            unlit bake: no sun (interiors lit by their lamps and the sky)
  --texel M           unlit bake: metres per light texel (default 0.1; 0.025 keeps
                      painted detail on a house)
  --max-size N        unlit bake: largest light texture side (default 4096)
  --light-size N      unlit bake: fixed light texture size, instead of --texel
  --mode M            LOD mode: auto | collapse | planar (default auto)
  --ratios R,R        LOD ratios (default 0.5,0.2)
  --cpu               bake on the CPU even when a GPU is available

Node extras of the input (x-class of each model in a multi-model file) are restored on
the final file and every LOD file.

Writes out_dir/pipeline.json (every step, its result and the triangles per LOD) and
prints PIPELINE_OK. Exits 1 on the first failed step.

Blender 4.2-5.0 (tested 4.5 LTS and 5.0.1). No add-ons.
"""
import json
import os
import shutil
import subprocess
import sys
import time

import bpy

sys.dont_write_bytecode = True   # no __pycache__ inside the kit
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _kitlib as K  # noqa: E402


def parse():
    p = K.make_parser("asset_pipeline.py", __doc__.split("\n\n")[0])
    p.add_argument("input")
    p.add_argument("out_dir")
    p.add_argument("--name")
    p.add_argument("--budget", type=int, default=0)
    p.add_argument("--skip", default="")
    p.add_argument("--ground", type=float, default=None)
    p.add_argument("--min-edge", type=float, default=None)
    p.add_argument("--allow-nonmanifold", action="store_true")
    p.add_argument("--no-closure", action="store_true")
    p.add_argument("--atlas", action="store_true")
    p.add_argument("--atlas-size", type=int, default=1024)
    p.add_argument("--high")
    p.add_argument("--normal-size", type=int, default=1024)
    p.add_argument("--light", choices=("none", "unlit", "ao"), default="none")
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--sun")
    p.add_argument("--sun-strength", type=float)
    p.add_argument("--no-sun", action="store_true")
    p.add_argument("--texel", type=float)
    p.add_argument("--max-size", type=int)
    p.add_argument("--light-size", type=int)
    p.add_argument("--mode", choices=("auto", "collapse", "planar"), default="auto")
    p.add_argument("--ratios", default="0.5,0.2")
    p.add_argument("--cpu", action="store_true")
    return K.parse_args(p)


def unlit_args(a):
    """The light-bake options given to the pipeline, as bake_unlit.py arguments."""
    out = []
    if a.sun:
        out.append("--sun=" + a.sun)   # "=": a leading minus is not read as an option
    if a.sun_strength is not None:
        out += ["--sun-strength", str(a.sun_strength)]
    if a.no_sun:
        out.append("--no-sun")
    if a.texel is not None:
        out += ["--texel", str(a.texel)]
    if a.max_size is not None:
        out += ["--max-size", str(a.max_size)]
    if a.light_size is not None:
        out += ["--size", str(a.light_size)]
    return out


def clips(path):
    return [x.get("name") for x in K.read_glb_json(path).get("animations", [])]


def lost_clips(before, after):
    """Named clips missing after the pipeline, plus unnamed ones by count: Blender
    names an unnamed clip on import (Anim_0), so it comes back under a new name."""
    lost = sorted({n for n in before if n} - set(after))
    unnamed = before.count(None) - len([n for n in after if n not in before])
    return lost + (["%d unnamed clip(s)" % unnamed] if unnamed > 0 else [])


def step(rep, label, tool, args):
    cmd = [bpy.app.binary_path, "-b", "--factory-startup", "--python", os.path.join(HERE, tool), "--"] + args
    t = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = p.stdout + p.stderr
    ok = p.returncode == 0
    rep["steps"].append({"step": label, "tool": "kit/blender/" + tool, "ok": ok, "seconds": round(time.time() - t, 1),
                         "result": [l for l in out.splitlines() if l.split(" ")[0].endswith("_OK")
                                    or l.startswith(("CLOSURE", "OPEN_EDGE", "LOD ", "ATLAS_", "ERROR",
                                                     "LIGHTS", "DENOISE"))][-12:]})
    K.log("STEP", label, "ok" if ok else "FAILED", "%.1fs" % (time.time() - t))
    if not ok:
        K.log(out[-4000:])
    return ok


def main():
    a = parse()
    if not os.path.isfile(a.input):
        K.fail("no such file: %s" % a.input)
    os.makedirs(a.out_dir, exist_ok=True)
    name = a.name or os.path.splitext(os.path.basename(a.input))[0]
    o = lambda n, s: os.path.join(a.out_dir, "%d_%s.glb" % (n, s))   # noqa: E731
    rep = {"input": a.input, "name": name, "steps": [], "result": "fail"}
    cpu = ["--cpu"] if a.cpu else []

    def finish(ok):
        rep["result"] = "ok" if ok else "fail"
        with open(os.path.join(a.out_dir, "pipeline.json"), "w") as f:
            json.dump(rep, f, indent=1)
        if not ok:
            K.log("PIPELINE_FAIL", a.input, "at", rep["steps"][-1]["step"])
            sys.stdout.flush()
            sys.exit(1)

    cur = o(1, "weld")
    if not step(rep, "weld", "weld.py", [a.input, cur]):
        return finish(False)
    if not a.no_closure:
        args = [cur, "--report", os.path.join(a.out_dir, "closure.json")]
        if a.skip:
            args += ["--skip", a.skip]
        if a.ground is not None:
            args += ["--ground", str(a.ground)]
        if a.min_edge is not None:
            args += ["--min-edge", str(a.min_edge)]
        if a.allow_nonmanifold:
            args.append("--allow-nonmanifold")
        if not step(rep, "closure", "closure_audit.py", args):
            return finish(False)
    if a.atlas:
        nxt = o(3, "atlas")
        if not step(rep, "atlas", "atlas.py", [cur, nxt, "--size", str(a.atlas_size),
                                              "--save-atlas", os.path.join(a.out_dir, name + "_atlas.png")] + cpu):
            return finish(False)
        cur = nxt
    if a.high:
        nxt = o(4, "normals")
        if not step(rep, "normals", "bake_normals.py", [a.high, cur, nxt, "--size", str(a.normal_size)] + cpu):
            return finish(False)
        cur = nxt
    if a.light == "unlit":
        nxt = o(5, "light")
        if not step(rep, "light", "bake_unlit.py", [cur, nxt, str(a.samples)] + unlit_args(a) + cpu):
            return finish(False)
        cur = nxt
    elif a.light == "ao":
        nxt = o(5, "ao")
        if not step(rep, "light", "bake_vertex_ao.py", [cur, nxt, "--samples", str(min(a.samples, 64))] + cpu):
            return finish(False)
        cur = nxt
    prefix = os.path.join(a.out_dir, name)
    args = [cur, prefix, "--mode", a.mode, "--ratios", a.ratios]
    if a.budget:
        args += ["--budget", str(a.budget)]
    if not step(rep, "lods", "lods.py", args):
        return finish(False)
    with open(prefix + "_lods.json") as f:
        lods = json.load(f)
    # Blender's glTF export drops node extras (x-class of a multi-model file): put them back
    extras = K.node_extras(a.input)
    if extras:
        for l in lods["levels"]:
            K.patch_node_extras(l["file"], extras)
    shutil.copy(prefix + "_lod0.glb", prefix + ".glb")
    rep["final"] = prefix + ".glb"
    lost = lost_clips(clips(a.input), clips(rep["final"]))
    if lost:
        rep["steps"].append({"step": "animations", "tool": "kit/blender/asset_pipeline.py", "ok": False, "seconds": 0,
                             "result": ["ERROR animation clips lost: " + ", ".join(lost)]})
        K.log("ERROR animation clips lost in the pipeline:", ", ".join(lost), "- ship the raw file or fix the rig")
        return finish(False)
    rep["triangles_per_lod"] = [l["triangles"] for l in lods["levels"]]
    rep["budget"] = lods.get("budget")
    rep["efficiency"] = lods.get("efficiency")
    finish(True)
    K.log("PIPELINE_OK", rep["final"], "tris per LOD", rep["triangles_per_lod"],
          ("efficiency %.1f" % rep["efficiency"]) if rep["efficiency"] is not None else "")


K.run(main)
