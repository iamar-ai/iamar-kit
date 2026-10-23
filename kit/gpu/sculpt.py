#!/usr/bin/env python3
"""GPU tier (Tier 2): concept picture -> generated mesh -> baked game asset, one command per step.

    python kit/gpu/sculpt.py check  [--region CC]                       # what this computer can run
    python kit/gpu/sculpt.py cutout concept.png out/x_rgba.png [--plinth-row N]
    python kit/gpu/sculpt.py shape  out/x_rgba.png out/x_high.glb --region CC [--octree 380 --steps 50 --seed 0]
    python kit/gpu/sculpt.py cage   out/x_high.glb out/game --height 2.0 --tris 3000 [--cut-below F]
    python kit/gpu/sculpt.py game   out/game/x_cage.glb out/game/x_high.glb out/final --budget 3000
    python kit/gpu/sculpt.py run    concept.png out --height 2.0 --budget 3000 --region CC [step options]

Multiview (several generated views, so the far side is modelled from its own view; heads,
creatures, statues with wings or staffs):
    python kit/gpu/sculpt.py concept out/concepts --prompt "..." [--count 4]    # optional, SDXL
    python kit/gpu/sculpt.py inpaint concept.png mask.png out/parts --prompt "..."  # optional: redraw one part
    python kit/gpu/sculpt.py clean   busy.png out/x [--poly ... --grabcut --bg ...] # hard cut-outs
    python kit/gpu/sculpt.py views   out/x_rgba.png out/views/x --text "what it is" [--az 0 90 180 270]
    python kit/gpu/sculpt.py recut   out/views/x out/x_rgba.png                  # pale figures
    python kit/gpu/sculpt.py shape   --mv out/views/x out/x_high.glb --region CC [--map front=000,...]
    python kit/gpu/sculpt.py paint   out/game/x_cage.glb out/views/x out/game/x_painted.glb --region CC
                                     [--paint 000,090,270 --base "#355e4c" --glow out/game/x_glow.png]
    python kit/gpu/sculpt.py paintfix albedo.png --base "#355e4c" [--glow mask.png]
    python kit/gpu/sculpt.py blade   out/x_high.glb out/x_high_blade.glb --root=x,y,z --tip=x,y,z  # thin blade the shape lost
    python kit/gpu/sculpt.py run     concept.png out --mv --text "what it is" --height 2.0 --budget 3000
                                     --region CC [--recut] [--paint 000,090,270 [--base "#hex"]]

`run` does all five in order, stops at the first failure and writes out/run.json (every
step, its seconds and result line, the triangles per LOD). The final asset is
out/final/<name>.glb with its LODs: weld, closure audit, normal map from the generated
surface, vertex AO (kit/blender/asset_pipeline.py). Put it into a world like any model.

Settings (flags win over environment):
  --python PY     Python of the GPU environment (IAMAR_GPU_PYTHON; default this one)
  --repo DIR      Hunyuan3D-2.1 clone (HY3D21_REPO)
  --hf-home DIR   Hugging Face cache holding the weights (HF_HOME)
  --region CC     the user's country (IAMAR_REGION); the shape step refuses EU, UK, KR
  --mvadapter DIR MV-Adapter clone, patched (MVADAPTER; views)
  --hy2-repo DIR  Hunyuan3D-2 clone (HY3D2_REPO; shape --mv and paint)
  --mem-cap SIZE  Linux with systemd: run the GPU step in a scope with MemoryMax=SIZE and no
                  swap (the city's rule on shared hosts: a runaway step is killed, not the desktop)
  BLENDER=path    Blender 4.2+ (else PATH and the usual install folders)

The shape step checks the computer first (gpu_check.py) and prints the fallback when it
cannot run: a hosted generator (Tier 1) or Blender and the catalogue (Tier 0). Exit codes:
0 ok, 1 a step failed, 2 this computer cannot run the step, 3 the licence does not allow it.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import gpu_check  # noqa: E402


def common(p):
    p.add_argument("--python", default=None)
    p.add_argument("--repo", default=None)
    p.add_argument("--mvadapter", default=None)
    p.add_argument("--hy2-repo", default=None)
    p.add_argument("--hf-home", default=None)
    p.add_argument("--region", default=None)
    p.add_argument("--mem-cap", default=None)


def settings(a):
    a.python = a.python or os.environ.get("IAMAR_GPU_PYTHON") or sys.executable
    a.repo = a.repo or os.environ.get("HY3D21_REPO")
    a.mvadapter = a.mvadapter or os.environ.get("MVADAPTER")
    a.hy2_repo = a.hy2_repo or os.environ.get("HY3D2_REPO")
    a.hf_home = a.hf_home or os.environ.get("HF_HOME")
    a.region = (a.region or os.environ.get("IAMAR_REGION") or "").strip().upper() or None
    return a


def blender():
    path, ver = gpu_check.find_blender()
    if not path or ver[:2] < gpu_check.BLENDER_MIN:
        print("SCULPT_FAIL Blender 4.2+ not found. FALLBACK: " + gpu_check.FALLBACK["cage"], file=sys.stderr)
        sys.exit(2)
    return path


def call(cmd, env=None, ok_prefix=None):
    """Runs one step, streams nothing but keeps the output; returns (ok, result line, seconds)."""
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = (r.stdout or "") + (r.stderr or "")
    line = ""
    for l in out.splitlines():
        if ok_prefix and l.startswith(ok_prefix):
            line = l
    ok = r.returncode == 0 and (not ok_prefix or bool(line))
    if not ok:
        tail = [l for l in out.splitlines() if l.strip()][-15:]
        line = line or "\n".join(tail)
    return ok, line, round(time.time() - t0, 1)


def capped(cmd, cap):
    if not cap:
        return cmd
    if not (sys.platform.startswith("linux") and shutil.which("systemd-run")):
        print("SCULPT_FAIL --mem-cap needs Linux with systemd-run; leave it out to run uncapped", file=sys.stderr)
        sys.exit(2)
    return ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=" + cap,
            "-p", "MemorySwapMax=0"] + cmd


def step_cutout(a, extra):
    cmd = [a.python, os.path.join(HERE, "stages", "cutout.py"), a.src, a.out] + extra
    return call(cmd, ok_prefix="CUTOUT_OK")


def licence_gate(a, model="Hunyuan3D-2.1", step="shape"):
    why = gpu_check.region_problem(a.region, model)
    if why:
        fb = gpu_check.FALLBACK[step] if step == "shape" else gpu_check.FALLBACK_REGION
        print("SCULPT_REFUSED %s. FALLBACK: %s" % (why, fb), file=sys.stderr)
        return 3
    return 0


def ready(a, stage, views=4):
    """gpu_check for one stage: None when ready, else exit code 2 after printing why."""
    chk = gpu_check.check(argparse.Namespace(python=a.python, repo=a.repo, region=a.region, hf_home=a.hf_home,
                                             mvadapter=a.mvadapter, hy2_repo=a.hy2_repo, views=views,
                                             stage=stage))
    s = chk["steps"][stage]
    if not s["ready"]:
        print("SCULPT_NOT_READY %s: %s\n  FALLBACK: %s" % (stage, s["why"], s["fallback"]), file=sys.stderr)
        return 2
    for n in s["notes"]:
        print("  NOTE: " + n)
    return None


def gpu_env(a):
    env = dict(os.environ)
    env.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")   # so cuda:0 is nvidia-smi's first GPU, as gpu_check judged
    if a.hf_home:
        env["HF_HOME"] = a.hf_home
    return env


def step_stage(a, script, args, ok_prefix, stage=None, gpu=False, views=4):
    """A stages/<script> run in the GPU environment's Python. With `stage`, gpu_check first
    (returns (None, 2) when not ready); `gpu` runs it under --mem-cap."""
    if stage:
        rc = ready(a, stage, views)
        if rc:
            return None, rc
    cmd = [a.python, os.path.join(HERE, "stages", script)] + args
    return call(capped(cmd, a.mem_cap) if gpu else cmd, env=gpu_env(a), ok_prefix=ok_prefix), 0


def step_shape_mv(a, extra):
    rc = licence_gate(a, "Hunyuan3D-2", "shape_mv")
    if rc:
        return None, rc
    return step_stage(a, "shape_mv.py", [a.src, a.out, "--repo", a.hy2_repo or ""] + extra, "SHAPE_OK",
                      stage="shape_mv", gpu=True)


def step_paint(a, extra):
    rc = licence_gate(a, "Hunyuan3D-2", "paint")
    if rc:
        return None, rc
    return step_stage(a, "paint_mv.py", [a.cage, a.views, a.out, "--repo", a.hy2_repo or ""] + extra, "PAINT_OK",
                      stage="paint", gpu=True)


def az_count(extra, default=4):
    """How many --az values the views step was given (the memory need depends on it)."""
    if "--az" not in extra:
        return default
    n = 0
    for x in extra[extra.index("--az") + 1:]:
        if x.startswith("--"):
            break
        n += 1
    return n


def step_shape(a, extra):
    if getattr(a, "mv", False):
        return step_shape_mv(a, extra)
    rc = licence_gate(a)
    if rc:
        return None, rc
    chk = gpu_check.check(argparse.Namespace(python=a.python, repo=a.repo, region=a.region,
                                             hf_home=a.hf_home, stage="shape"))
    s = chk["steps"]["shape"]
    if not s["ready"]:
        print("SCULPT_NOT_READY shape: %s\n  FALLBACK: %s" % (s["why"], s["fallback"]), file=sys.stderr)
        return None, 2
    for n in s["notes"]:
        print("  NOTE: " + n)
    env = dict(os.environ)
    env.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")   # so cuda:0 is nvidia-smi's first GPU, as gpu_check judged
    if a.hf_home:
        env["HF_HOME"] = a.hf_home
    cmd = capped([a.python, os.path.join(HERE, "stages", "shape_hy21.py"), a.src, a.out,
                  "--repo", a.repo] + extra, a.mem_cap)
    return call(cmd, env=env, ok_prefix="SHAPE_OK"), 0


def step_cage(a, extra):
    cmd = [blender(), "-b", "--factory-startup", "--python", os.path.join(HERE, "stages", "cage.py"),
           "--", a.high, a.out_dir] + extra
    return call(cmd, ok_prefix="CAGE_OK")


def step_blade(a, extra):
    cmd = [blender(), "-b", "--factory-startup", "--python", os.path.join(HERE, "stages", "add_blade.py"),
           "--", a.high, a.out] + extra
    return call(cmd, ok_prefix="BLADE_OK")


def step_game(a, extra):
    cmd = [blender(), "-b", "--factory-startup", "--python", os.path.join(KIT, "blender", "asset_pipeline.py"),
           "--", a.cage, a.out_dir, "--high", a.high, "--light", "ao"] + extra
    return call(cmd, ok_prefix="PIPELINE_OK")


def report(name, res):
    ok, line, secs = res
    print("%s %s (%.0fs)" % ("STEP " + name, "ok" if ok else "FAILED", secs))
    print("  " + line.replace("\n", "\n  "))
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check"); common(p); p.add_argument("--json", action="store_true")
    p.add_argument("--stage", default="all", help="all (single view), mv (multiview), every, or one step")
    p = sub.add_parser("cutout"); common(p); p.add_argument("src"); p.add_argument("out")
    p = sub.add_parser("shape"); common(p); p.add_argument("src"); p.add_argument("out")
    p.add_argument("--mv", action="store_true", help="src is a views prefix: Hunyuan3D-2mv from several views")
    p = sub.add_parser("concept"); common(p); p.add_argument("out_dir")
    p = sub.add_parser("inpaint"); common(p); p.add_argument("src"); p.add_argument("mask"); p.add_argument("out_dir")
    p = sub.add_parser("clean"); common(p); p.add_argument("src"); p.add_argument("out")
    p = sub.add_parser("views"); common(p); p.add_argument("src"); p.add_argument("out")
    p = sub.add_parser("recut"); common(p); p.add_argument("views"); p.add_argument("clean")
    p = sub.add_parser("paint"); common(p); p.add_argument("cage"); p.add_argument("views"); p.add_argument("out")
    p = sub.add_parser("paintfix"); common(p); p.add_argument("albedo")
    p = sub.add_parser("cage"); common(p); p.add_argument("high"); p.add_argument("out_dir")
    p = sub.add_parser("blade"); common(p); p.add_argument("high"); p.add_argument("out")
    p = sub.add_parser("game"); common(p); p.add_argument("cage"); p.add_argument("high"); p.add_argument("out_dir")
    p = sub.add_parser("run"); common(p); p.add_argument("src"); p.add_argument("out_dir")
    p.add_argument("--name", default=None)
    p.add_argument("--height", type=float, required=True)
    p.add_argument("--budget", type=int, required=True, help="LOD0 triangles (prop 300, building 3000, statue 5000-12000)")
    p.add_argument("--plinth-row", type=int, default=None)
    p.add_argument("--octree", type=int, default=380)
    p.add_argument("--steps", type=int, default=50)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--cut-below", type=float, default=0.0)
    p.add_argument("--normal-size", type=int, default=1024)
    p.add_argument("--color", default=None)
    p.add_argument("--mv", action="store_true", help="multiview: views, then Hunyuan3D-2mv shape")
    p.add_argument("--text", default=None, help="--mv: what the subject is (the views follow it)")
    p.add_argument("--az", default="0,90,180,270", help="--mv: view angles in degrees")
    p.add_argument("--map", default=None, help="--mv: which views the shape uses (front=000,left=090,...)")
    p.add_argument("--recut", action="store_true", help="--mv: re-cut the views (pale figures)")
    p.add_argument("--paint", default=None, help="--mv: paint the cage from these views (000,090,270)")
    p.add_argument("--base", default=None, help="--paint: recolour the unseen grey fill to #rrggbb")
    a, extra = ap.parse_known_args(argv)
    if a.cmd in ("check", "run") and extra:
        ap.error("unknown options for %s: %s" % (a.cmd, " ".join(extra)))
    a = settings(a)

    if a.cmd == "check":
        return gpu_check.main(["--python", a.python, "--stage", a.stage]
                              + (["--repo", a.repo] if a.repo else []) + (["--region", a.region] if a.region else [])
                              + (["--mvadapter", a.mvadapter] if a.mvadapter else [])
                              + (["--hy2-repo", a.hy2_repo] if a.hy2_repo else [])
                              + (["--hf-home", a.hf_home] if a.hf_home else []) + (["--json"] if a.json else []))
    if a.cmd == "cutout":
        return 0 if report("cutout", step_cutout(a, extra)) else 1
    if a.cmd == "shape":
        res, rc = step_shape(a, extra)
        return rc if res is None else (0 if report("shape", res) else 1)
    if a.cmd == "cage":
        return 0 if report("cage", step_cage(a, extra)) else 1
    if a.cmd == "blade":
        return 0 if report("blade", step_blade(a, extra)) else 1
    staged = {
        "concept": lambda: step_stage(a, "concept_sdxl.py", [a.out_dir] + extra, "CONCEPT_OK", stage="concept", gpu=True),
        "inpaint": lambda: step_stage(a, "inpaint_part.py", [a.src, a.mask, a.out_dir] + extra, "INPAINT_OK",
                                      stage="concept", gpu=True),
        "clean": lambda: step_stage(a, "clean_concept.py", [a.src, a.out] + extra, "CLEAN_OK"),
        "views": lambda: step_stage(a, "mv_views.py", [a.src, a.out, "--mvadapter", a.mvadapter or ""] + extra,
                                    "VIEWS_OK", stage="views", gpu=True, views=az_count(extra)),
        "recut": lambda: step_stage(a, "mv_recut.py", [a.views, a.clean] + extra, "RECUT_OK"),
        "paint": lambda: step_paint(a, extra),
        "paintfix": lambda: step_stage(a, "paint_fix.py", [a.albedo] + extra, "PAINT_FIX_OK"),
    }
    if a.cmd in staged:
        res, rc = staged[a.cmd]()
        return rc if res is None else (0 if report(a.cmd, res) else 1)
    if a.cmd == "game":
        return 0 if report("game", step_game(a, extra)) else 1

    # run: every step in order; check the numbers before the expensive GPU step
    name = a.name or os.path.splitext(os.path.basename(a.src))[0]
    bad = []
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name):
        bad.append("--name %r: letters, digits, _ . - only (no paths)" % name)
    if not (math.isfinite(a.height) and 0 < a.height <= 500):
        bad.append("--height must be in (0, 500] metres")
    if a.budget <= 0:
        bad.append("--budget must be positive")
    if not 0 <= a.cut_below < 0.9:
        bad.append("--cut-below must be in [0, 0.9)")
    mv_flags = [f for f, v in (("--text", a.text), ("--map", a.map), ("--recut", a.recut), ("--paint", a.paint),
                               ("--base", a.base)) if v]
    if mv_flags and not a.mv:
        bad.append("%s only with --mv" % ", ".join(mv_flags))
    if a.mv and not (a.text or "").strip():
        bad.append("--mv needs --text: what the subject is (the generated views follow it)")
    az = []
    try:
        az = [int(x) for x in a.az.split(",")]
    except ValueError:
        bad.append("--az: degrees, comma separated (0,90,180,270)")
    if a.mv and az and (0 not in az or len(set(az)) != len(az) or any(not 0 <= x < 360 for x in az)):
        bad.append("--az: distinct degrees in [0, 360) including 0")
    if a.base and not a.paint:
        bad.append("--base only with --paint")
    if bad:
        ap.error("; ".join(bad))
    out = os.path.abspath(a.out_dir)
    os.makedirs(out, exist_ok=True)
    rgba, high = os.path.join(out, name + "_rgba.png"), os.path.join(out, name + "_high.glb")
    game_dir, final_dir = os.path.join(out, "game"), os.path.join(out, "final")
    t_start = time.time()
    rep = {"src": a.src, "name": name, "region": a.region, "height_m": a.height, "budget": a.budget, "steps": []}

    def done(step, res, rc_fail=1):
        ok, line, secs = res
        rep["steps"].append({"step": step, "ok": ok, "seconds": secs, "result": line})
        with open(os.path.join(out, "run.json"), "w") as f:
            json.dump(rep, f, indent=1)
        report(step, res)
        return ok

    if a.mv:
        rep["multiview"] = {"text": a.text, "az": az, "map": a.map, "recut": a.recut, "paint": a.paint}
        # the licence gate before any work: the views are useless without the shape step
        rc = licence_gate(a, "Hunyuan3D-2", "shape_mv")
        if rc:
            rep["steps"].append({"step": "shape", "ok": False, "refused": rc})
            with open(os.path.join(out, "run.json"), "w") as f:
                json.dump(rep, f, indent=1)
            return rc
    s = argparse.Namespace(**vars(a)); s.src, s.out = a.src, rgba
    if not done("cutout", step_cutout(s, [] if a.plinth_row is None else ["--plinth-row", str(a.plinth_row)])):
        return 1
    def refused(step, rc):
        rep["steps"].append({"step": step, "ok": False, "refused": rc})
        with open(os.path.join(out, "run.json"), "w") as f:
            json.dump(rep, f, indent=1)
        return rc

    shape_opts = ["--octree", str(a.octree), "--steps", str(a.steps), "--seed", str(a.seed)]
    s = argparse.Namespace(**vars(a)); s.src, s.out = rgba, high
    if a.mv:
        prefix = os.path.join(out, "views", name)
        vx = ["--text", a.text, "--az"] + [str(x) for x in az]
        res, rc = step_stage(a, "mv_views.py", [rgba, prefix, "--mvadapter", a.mvadapter or ""] + vx,
                             "VIEWS_OK", stage="views", gpu=True, views=len(az))
        if res is None:
            return refused("views", rc)
        if not done("views", res):
            return 1
        if a.recut:
            res, _ = step_stage(a, "mv_recut.py", [prefix, rgba, "--az"] + [str(x) for x in az], "RECUT_OK")
            if not done("recut", res):
                return 1
        s.src = prefix
        mv_opts = ["--octree", str(a.octree), "--steps", str(a.steps), "--seed", str(a.seed)]
        if a.map:
            mv_opts += ["--map", a.map]
        else:
            # the default slots that have a view
            slots = [(k, d) for k, d in (("front", 0), ("left", 90), ("back", 180), ("right", 270)) if d in az]
            mv_opts += ["--map", ",".join("%s=%03d" % kd for kd in slots)]
        res, rc = step_shape_mv(s, mv_opts)
    else:
        res, rc = step_shape(s, shape_opts)
    if res is None:
        return refused("shape", rc)
    if not done("shape", res):
        return 1
    s = argparse.Namespace(**vars(a)); s.high, s.out_dir = high, game_dir
    cx = ["--height", str(a.height), "--tris", str(a.budget), "--cut-below", str(a.cut_below), "--name", name]
    if a.color:
        cx += ["--color", a.color]
    if not done("cage", step_cage(s, cx)):
        return 1
    cage_glb = os.path.join(game_dir, name + "_cage.glb")
    if a.mv and a.paint:
        s = argparse.Namespace(**vars(a))
        s.cage, s.views, s.out = cage_glb, os.path.join(out, "views", name), os.path.join(game_dir, name + "_painted.glb")
        px = ["--paint", a.paint] + (["--base", a.base] if a.base else [])
        res, rc = step_paint(s, px)
        if res is None:
            return refused("paint", rc)
        if not done("paint", res):
            return 1
        cage_glb = s.out
    s = argparse.Namespace(**vars(a))
    s.cage, s.high, s.out_dir = cage_glb, os.path.join(game_dir, name + "_high.glb"), final_dir
    if not done("game", step_game(s, ["--name", name, "--budget", str(a.budget), "--normal-size", str(a.normal_size)])):
        return 1
    try:
        with open(os.path.join(final_dir, "pipeline.json")) as f:
            pj = json.load(f)
        rep["final"], rep["triangles_per_lod"], rep["efficiency"] = pj.get("final"), pj.get("triangles_per_lod"), pj.get("efficiency")
    except (OSError, ValueError) as e:
        print("SCULPT_FAIL no readable final/pipeline.json: %s" % e, file=sys.stderr)
        return 1
    if not rep["final"] or not os.path.isfile(rep["final"]) or os.path.getmtime(rep["final"]) < t_start:
        print("SCULPT_FAIL the final asset %s was not written by this run" % rep["final"], file=sys.stderr)
        return 1
    with open(os.path.join(out, "run.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print("SCULPT_OK %s tris per LOD %s" % (rep.get("final"), rep.get("triangles_per_lod")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
