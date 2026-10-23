#!/usr/bin/env python3
"""Statue v4 (GPU tier): a refined statue surface -> a split-budget game statue with baked maps and QA.

    python kit/gpu/statue/statue.py check  [--us-repo DIR] [--ckpt FILE] [--region CC] [--stage all|refine|chain] [--json]
    python kit/gpu/statue/statue.py patch  --us-repo DIR                 # write scripts/infer_fp16.py into YOUR UltraShape clone
    python kit/gpu/statue/statue.py refine x_rgba.png x_coarse.glb out/refine --us-repo DIR --ckpt FILE --region CC [--mem-cap 18G]
    python kit/gpu/statue/statue.py chain  work/x refined.glb [KEY=VAL ...] [--nb 3300 --nh 2400 --nf 4800] [--size 2048] [--name x]
    python kit/gpu/statue/statue.py uv-search work/x [KEY=VAL ...] [--fdir DEG --fgx X --fgz Z] [--radii 0.3,0.6,0.9,1.5,3.0]

The city's statue v4 workflow (the iamar-models mesh archive (not public) tools/mesh3d/statue_v4, kit/gpu/statue/README.md):
picture -> cut-out (sculpt.py cutout) -> coarse shape (sculpt.py shape, Hunyuan3D-2.1) -> `refine` (UltraShape 1.0
on the WHOLE statue, 3-9M faces) -> `chain`: prep (sole cut, removal boxes, face oval tagged) -> joint thinning (no face
rim crack) -> split cage (body / hat+hair / face, own budgets, one cylindrical face and neck chart) -> Cycles normal + sky
AO bake -> relight (face lift) -> dilate -> seam blend -> qa_statue. A QA FAIL stops the chain (exit 1; --qa-force goes
on). Nothing is installed anywhere: the result is <workdir>/out/<name>.gltf (+ .bin, _albedo.png, _normal.png) and
<workdir>/run.json (steps, triangles per part, QA lines, feet centre and figure height for placing it).

KEY=VAL arguments are the per-statue parameters (README "Parameters"): face oval FCX FCY FCZ FRXL FRXR FRZ FYAW, removal
BOXES SOLE CAPH LOOSE FZCUT, neck NECKX NECKY0 NECKY1 NECKR NECKZC NECKZR, UV CYLX CYLZ CYLR FCYLX FCYLZ FCYLR FACEUV SELDEC,
bake EXT RAY, relight RX0 RX1 RY0 RY1 RZ0 RZ1 FEATHER DESAT, MAGE_CLEAN. They reach every step's environment.

Settings: --python (IAMAR_STATUE_PYTHON, else IAMAR_GPU_PYTHON, else this Python; needs numpy scipy pillow trimesh
pymeshlab xatlas), BLENDER=path (Blender 4.2+), --us-repo (ULTRASHAPE_REPO), --ckpt (ULTRASHAPE_CKPT), --region
(IAMAR_REGION). Exit codes as sculpt.py: 0 ok, 1 a step or QA failed, 2 this computer cannot run it, 3 licence refuses.
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
STAGES = os.path.join(HERE, "stages")
sys.path.insert(0, os.path.dirname(HERE))
sys.dont_write_bytecode = True
import gpu_check  # noqa: E402  (read-only use: GPU, RAM, region and Blender helpers)
import pins  # noqa: E402  (kit/gpu/pins.json: pinned clone commit and checkpoint)

# Measured in the city (the GPU host, RTX A5000 24 GB, 32 GB RAM; iamar-models statue_v4/README.md): UltraShape 1.0 refine
# of a whole statue, 50 steps, octree 1024, about 10 minutes at about 19 GB of GPU memory, run under MemoryMax=18G with
# no swap. The stock script builds the models in fp32 on the CPU and is killed at 18 GB of RAM; `patch` builds them in
# fp16 straight on the GPU.
REFINE_VRAM_MIB = 19000
REFINE_RAM_GB = 18
REFINE_DISK_GB = 10          # UltraShape install with its checkpoint, about 10 GB
CHAIN_RAM_GB = 8             # prep + bake of a 3-9M-face surface in Blender
CHAIN_MODULES = ("numpy", "scipy", "PIL", "trimesh", "pymeshlab", "xatlas")
FALLBACK = {
    "refine": "skip the refine and run `chain` on the coarse Hunyuan3D-2.1 surface (sculpt.py shape output, softer "
              "detail; the face oval and neck still work), or use sculpt.py's single-step route (sculpt.py cage/game), "
              "or Tier 0: a catalogue statue (iamar-world assets search statue) or a Blender model",
    "chain": "install the Python modules (pip install numpy scipy pillow trimesh pymeshlab xatlas) into the --python "
             "environment and Blender 4.2+ (kit/blender/README.md); the chain runs on CPU on any computer",
}
NOTICE = ("# Modified by the iamar creator kit (kit/gpu/statue/statue.py patch) from scripts/infer_dit_refine.py:\n"
          "# the VAE, DiT and conditioner are built in fp16 straight on the GPU and the checkpoint is loaded to the GPU,\n"
          "# because the stock fp32 CPU build needs more than 18 GB of RAM. Tencent Hunyuan 3D 2.1 Community License\n"
          "# (s.3b: modified files carry a notice).\n")
# (anchor in the stock script, replacement): UltraShape-1.0 at 5e8dcef, scripts/infer_dit_refine.py
PATCH = [
    ('    print("Instantiating VAE...")\n'
     '    vae = instantiate_from_config(config.model.params.vae_config)\n'
     '    \n'
     '    print("Instantiating DiT...")\n'
     '    dit = instantiate_from_config(config.model.params.dit_cfg)\n'
     '    \n'
     '    print("Instantiating Conditioner...")\n'
     '    conditioner = instantiate_from_config(config.model.params.conditioner_config)\n',
     '    torch.set_default_dtype(torch.float16)   # fp16 models built straight on the GPU (the fp32 CPU build needs >18 GB RAM)\n'
     "    with torch.device('cuda'):\n"
     '        print("Instantiating VAE...")\n'
     '        vae = instantiate_from_config(config.model.params.vae_config)\n'
     '        print("Instantiating DiT...")\n'
     '        dit = instantiate_from_config(config.model.params.dit_cfg)\n'
     '        print("Instantiating Conditioner...")\n'
     '        conditioner = instantiate_from_config(config.model.params.conditioner_config)\n'
     '    torch.set_default_dtype(torch.float32)\n'),
    ("    weights = torch.load(ckpt_path, map_location='cpu')\n",
     "    weights = torch.load(ckpt_path, map_location='cuda', mmap=False, weights_only=True)\n"),
    ("    conditioner.load_state_dict(weights['conditioner'], strict=True)\n    \n",
     "    conditioner.load_state_dict(weights['conditioner'], strict=True)\n"
     "    \n"
     "    del weights\n"
     "    torch.cuda.empty_cache()\n"),
]
KV = re.compile(r"^[A-Z][A-Z0-9_]*=")


def py_of(a):
    return a.python or os.environ.get("IAMAR_STATUE_PYTHON") or os.environ.get("IAMAR_GPU_PYTHON") or sys.executable


def us_repo(a):
    return a.us_repo or os.environ.get("ULTRASHAPE_REPO")


def us_ckpt(a):
    c = a.ckpt or os.environ.get("ULTRASHAPE_CKPT")
    r = us_repo(a)
    if not c and r:
        c = os.path.join(r, "..", "checkpoints", "ultrashape_v1.pt")
        if not os.path.isfile(c):
            c = os.path.join(r, "checkpoints", "ultrashape_v1.pt")
    return os.path.normpath(c) if c else None


# ---------------------------------------------------------------- check
def check(a):
    want = ["refine", "chain"] if a.stage == "all" else [a.stage]
    res = {"steps": {}, "host": {}}
    total, avail = gpu_check.ram_gb()
    res["host"]["ram_total_gb"] = round(total, 1) if total else None
    res["host"]["ram_available_gb"] = round(avail, 1) if avail else None

    def put(step, why, notes=None):
        res["steps"][step] = {"ready": not why, "why": "; ".join(why), "notes": notes or [],
                              "fallback": FALLBACK[step] if why else None}

    py = py_of(a)
    if "refine" in want:
        why, notes = [], []
        rp = gpu_check.region_problem(a.region or os.environ.get("IAMAR_REGION"))
        if rp:
            why.append(rp.replace("Hunyuan3D", "UltraShape (Hunyuan3D 2.1 licence)"))
        g = gpu_check.gpus()
        res["host"]["gpus"] = g
        best = gpu_check.used_gpu(g)
        if g and not best:
            why.append("CUDA_VISIBLE_DEVICES=%r hides every GPU" % os.environ.get("CUDA_VISIBLE_DEVICES"))
        elif not best:
            why.append("no NVIDIA GPU found (nvidia-smi); UltraShape needs CUDA")
        elif best["total_mib"] < REFINE_VRAM_MIB:
            why.append("GPU %s has %.1f GB, the refine used about 19 GB" % (best["name"], best["total_mib"] / 1024))
        elif best["free_mib"] < REFINE_VRAM_MIB:
            why.append("only %.1f GB of GPU memory free on %s now (about 19 GB needed): stop other GPU work first"
                       % (best["free_mib"] / 1024, best["name"]))
        elif best["total_mib"] < 24 * 1024 - 512:
            notes.append("GPU %s %.1f GB: only a 24 GB card was measured" % (best["name"], best["total_mib"] / 1024))
        if avail is not None and avail < REFINE_RAM_GB:
            why.append("%.1f GB RAM available, the refine is capped at %d GB" % (avail, REFINE_RAM_GB))
        repo = us_repo(a)
        if not repo or not os.path.isdir(os.path.join(repo, "ultrashape")):
            why.append("UltraShape-1.0 clone not found (--us-repo or ULTRASHAPE_REPO; README 'Install')")
        else:
            gpu_check.pin_check(repo, "UltraShape-1.0", why)
            if not os.path.isfile(os.path.join(repo, "scripts", "infer_fp16.py")):
                why.append("fp16 script missing: run `statue.py patch --us-repo %s` (the stock script is killed at 18 GB RAM)" % repo)
            free = gpu_check.disk_free_gb(repo)
            if free is not None and free < 2:
                why.append("only %.1f GB free next to %s (the refined surface and its outputs)" % (free, repo))
        ck = us_ckpt(a)
        if not ck or not os.path.isfile(ck) or os.path.getsize(ck) < 100_000_000:
            why.append("UltraShape checkpoint not found or partial (--ckpt or ULTRASHAPE_CKPT; ultrashape_v1.pt "
                       "from Hugging Face infinith/UltraShape)")
        else:
            bad = pins.file_problem(ck, "infinith/UltraShape/ultrashape_v1.pt", full=getattr(a, "verify_hash", False))
            if bad:
                why.append("UltraShape checkpoint is not the pinned one: " + bad)
            notes.append("checkpoint: " + ck)
        mods, err = gpu_check.env_modules(py, ["omegaconf", "trimesh", "cubvh"], cuda=True)
        res["host"]["python"] = py
        if mods is None:
            why.append("the GPU environment's Python did not run (%s): pass --python" % err)
        else:
            if not mods.get("_cuda"):
                why.append("torch with CUDA not usable in %s" % py)
            miss = [m for m in ("omegaconf", "trimesh", "cubvh") if not mods.get(m)]
            if miss:
                why.append("missing in %s: %s (UltraShape requirements, README 'Install')" % (py, ", ".join(miss)))
        put("refine", why, notes)

    if "chain" in want:
        why = []
        mods, err = gpu_check.env_modules(py, list(CHAIN_MODULES))
        if mods is None:
            why.append("Python %s did not run (%s): pass --python" % (py, err))
        else:
            miss = [m for m in CHAIN_MODULES if not mods.get(m)]
            if miss:
                why.append("missing in %s: %s" % (py, ", ".join(miss)))
        path, ver = gpu_check.find_blender()
        res["host"]["blender"] = {"path": path, "version": ".".join(map(str, ver)) if ver else None}
        if not path:
            why.append("Blender not found (BLENDER=, PATH or a usual install folder)")
        elif ver[:2] < gpu_check.BLENDER_MIN:
            why.append("Blender %s is older than 4.2" % ".".join(map(str, ver)))
        if avail is not None and avail < CHAIN_RAM_GB:
            why.append("%.1f GB RAM available, needs %d" % (avail, CHAIN_RAM_GB))
        put("chain", why)
    res["ready"] = all(s["ready"] for s in res["steps"].values())
    return res


def refine_ready(a):
    """For gpu_check.py --stage refine: the refine part of check()."""
    a.stage = "refine"
    return check(a)["steps"]["refine"]


def print_check(res, as_json):
    if as_json:
        print(json.dumps(res, indent=1))
    else:
        for name, s in res["steps"].items():
            if s["ready"]:
                print("STEP %s READY" % name)
            else:
                print("STEP %s NOT_READY: %s\n  FALLBACK: %s" % (name, s["why"], s["fallback"]))
            for n in s["notes"]:
                print("  NOTE: " + n)
        print("STATUE_CHECK_OK" if res["ready"] else "STATUE_CHECK_NOT_READY")
    return 0 if res["ready"] else 2


# ---------------------------------------------------------------- patch
def patch_text(src):
    """The stock infer_dit_refine.py text -> the fp16 script, or raise ValueError naming the missing anchor."""
    s = src.replace("\r\n", "\n")
    for old, new in PATCH:
        if s.count(old) != 1:
            raise ValueError("anchor not found once in the stock script: %r" % old.strip().splitlines()[0])
        s = s.replace(old, new)
    return NOTICE + s


def cmd_patch(a):
    repo = us_repo(a)
    src = os.path.join(repo or "", "scripts", "infer_dit_refine.py")
    if not repo or not os.path.isfile(src):
        print("STATUE_FAIL %s not found (--us-repo: your UltraShape-1.0 clone)" % src, file=sys.stderr)
        return 2
    try:
        out = patch_text(open(src, encoding="utf-8").read())
    except ValueError as e:
        print("STATUE_FAIL %s (UltraShape changed since 5e8dcef: patch by hand, README 'Install')" % e, file=sys.stderr)
        return 1
    dst = os.path.join(repo, "scripts", "infer_fp16.py")
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print("PATCH_OK", dst)
    return 0


# ---------------------------------------------------------------- refine
def cmd_refine(a):
    why = gpu_check.region_problem(a.region or os.environ.get("IAMAR_REGION"))
    if why:
        print("STATUE_REFUSED %s. FALLBACK: %s" % (why, FALLBACK["refine"]), file=sys.stderr)
        return 3
    a.stage = "refine"
    a.verify_hash = True   # a run hashes the 7 GB checkpoint (it is unpickled on load); `check` only compares its size
    s = check(a)["steps"]["refine"]
    if not s["ready"]:
        print("STATUE_NOT_READY refine: %s\n  FALLBACK: %s" % (s["why"], s["fallback"]), file=sys.stderr)
        return 2
    for n in s["notes"]:
        print("  NOTE: " + n)
    repo = os.path.abspath(us_repo(a))
    img, mesh, out = (os.path.abspath(p) for p in (a.image, a.mesh, a.out_dir))
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=repo + os.pathsep + os.environ.get("PYTHONPATH", ""))
    env.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")   # so cuda:0 is nvidia-smi's first GPU, as gpu_check judged
    if not env.get("HF_HOME"):
        env["HF_HOME"] = os.path.join(os.path.dirname(repo), "hf")
    cmd = [py_of(a), os.path.join("scripts", "infer_fp16.py"), "--ckpt", us_ckpt(a), "--image", img, "--mesh", mesh,
           "--config", os.path.join("configs", "infer_dit_refine.yaml"), "--output_dir", out,
           "--steps", str(a.steps), "--seed", str(a.seed), "--octree_res", str(a.octree)]
    if a.mem_cap:
        if not (sys.platform.startswith("linux") and shutil.which("systemd-run")):
            print("STATUE_FAIL --mem-cap needs Linux with systemd-run; leave it out to run uncapped", file=sys.stderr)
            return 2
        cmd = ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=" + a.mem_cap, "-p", "MemorySwapMax=0"] + cmd
    t0 = time.time()
    r = subprocess.run(cmd, cwd=repo, env=env)
    res = os.path.join(out, os.path.splitext(os.path.basename(img))[0] + "_refined.glb")
    if r.returncode != 0 or not os.path.isfile(res):
        print("STATUE_FAIL refine exit %d (a kill at the cap means the fp16 script was not used)" % r.returncode,
              file=sys.stderr)
        return 1
    print("REFINE_OK %s (%.0fs). Licence of this output: Tencent Hunyuan 3D 2.1 Community License (output)"
          % (res, time.time() - t0))
    return 0


# ---------------------------------------------------------------- chain
def split_kv(extra):
    kv, rest = {}, []
    for x in extra:
        if KV.match(x):
            k, v = x.split("=", 1)
            kv[k] = v
        else:
            rest.append(x)
    return kv, rest


def blender_or_exit():
    path, ver = gpu_check.find_blender()
    if not path or ver[:2] < gpu_check.BLENDER_MIN:
        print("STATUE_FAIL Blender 4.2+ not found. FALLBACK: " + FALLBACK["chain"], file=sys.stderr)
        sys.exit(2)
    return path


class Steps:
    def __init__(self, work, env):
        self.work, self.env, self.rows, self.log = work, env, [], open(os.path.join(work, "chain.log"), "a")

    def run(self, name, cmd, keep=None):
        t0 = time.time()
        r = subprocess.run(cmd, cwd=self.work, env=self.env, capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        self.log.write("== %s: %s\n%s\n" % (name, " ".join(cmd), out))
        self.log.flush()
        lines = [l for l in out.splitlines() if keep and re.match(keep, l)]
        row = {"step": name, "ok": r.returncode == 0, "seconds": round(time.time() - t0, 1), "lines": lines}
        self.rows.append(row)
        print("STEP %s %s (%.0fs)" % (name, "ok" if row["ok"] else "FAILED", row["seconds"]))
        for l in lines:
            print("  " + l)
        if not row["ok"] and name != "qa":
            tail = [l for l in out.splitlines() if l.strip()][-12:]
            print("  " + "\n  ".join(tail))
        return row["ok"]


def chain(a, extra):
    kv, rest = split_kv(extra)
    if rest:
        print("STATUE_FAIL unknown arguments %s (parameters are KEY=VAL, upper case)" % rest, file=sys.stderr)
        return 2
    py = py_of(a)
    bl = blender_or_exit()
    work = os.path.abspath(a.workdir)
    os.makedirs(os.path.join(work, "out"), exist_ok=True)
    env = dict(os.environ)
    env.update(kv)
    st = Steps(work, env)
    S = lambda f: os.path.join(STAGES, f)
    combo, pre, low = (os.path.join(work, n) for n in ("combo.glb", "pre.glb", "low_low.glb"))
    out = os.path.join(work, "out")
    name = a.name
    alb, nrm, ao = (os.path.join(out, n) for n in (name + "_albedo.png", name + "_normal.png", "ao.png"))
    if a.combo:
        shutil.copyfile(os.path.abspath(a.combo), combo)
    else:
        if not os.path.isfile(a.refined):
            print("STATUE_FAIL refined mesh %s not found" % a.refined, file=sys.stderr)
            return 2
        if not st.run("prep", [bl, "-b", "--factory-startup", "--python", S("prep_full.py"), "--",
                               os.path.abspath(a.refined), combo], keep=r"PREP"):
            return finish(a, st, 1)
    ok = (st.run("predec", [py, S("predec_joint.py"), combo, pre, str(a.nf_pre), str(a.nb_pre)], keep=r"PREDEC")
          and st.run("cage", [py, S("lowsplit3.py"), pre, os.path.join(work, "low"), str(a.nb), str(a.nh), str(a.nf),
                              "0", str(a.collar), str(a.head_x0), str(a.head_x1), str(a.face_density)],
                     keep=r"(neck triangles|LOW|ATLAS|PRIM)")
          and st.run("bake", [bl, "-b", "--factory-startup", "--python", S("bake_split_env.py"), "--",
                              combo, low, os.path.join(out, name + ".gltf"), str(a.size), ao], keep=r"BAKE_SPLIT_OK")
          and st.run("relight", [py, S("relight.py"), low, ao, alb, str(a.lift)], keep=r"(lifted|albedo)")
          and st.run("dilate", [py, S("dilate_nn.py"), low, alb, nrm], keep=r"filled")
          and st.run("seam_blend", [py, S("seam_blend.py"), low, alb, str(a.seam_r)], keep=r"."))
    if not ok:
        return finish(a, st, 1)
    st.run("feet", [py, S("feet.py"), low], keep=r"FEET")
    qa = st.run("qa", [py, S("qa_statue.py"), low, alb], keep=r"^QA")
    if not qa and not a.qa_force:
        print("QA FAILED: see %s (fix the parameters, or --qa-force to keep going)" % os.path.join(work, "chain.log"))
        return finish(a, st, 1)
    print("STATUE_OK %s" % os.path.join(out, name + ".gltf"))
    return finish(a, st, 0)


def finish(a, st, rc):
    rep = {"name": a.name, "refined": os.path.abspath(a.refined) if a.refined else None, "rc": rc,
           "budgets": {"body": a.nb, "hat_hair": a.nh, "face": a.nf}, "steps": st.rows}
    for r in st.rows:
        for l in r["lines"]:
            m = re.match(r"PRIM (\w+) (\d+) tris", l)
            if m:
                rep.setdefault("triangles", {})[m.group(1)] = int(m.group(2))
            m = re.match(r"FEET (.*)", l)
            if m:
                rep["placement"] = json.loads(m.group(1))
            if l.startswith("QA RESULT"):
                rep["qa"] = l[len("QA RESULT "):]
    if "triangles" in rep:
        rep["triangles"]["total"] = sum(rep["triangles"].values())
    with open(os.path.join(st.work, "run.json"), "w") as f:
        json.dump(rep, f, indent=1)
    st.log.close()
    return rc


# ---------------------------------------------------------------- uv-search
def uv_search(a, extra):
    kv, rest = split_kv(extra)
    if rest:
        print("STATUE_FAIL unknown arguments %s" % rest, file=sys.stderr)
        return 2
    work = os.path.abspath(a.workdir)
    if not os.path.isfile(os.path.join(work, "pre.glb")):
        print("STATUE_FAIL %s has no pre.glb: run `chain` once first" % work, file=sys.stderr)
        return 2
    py = py_of(a)
    best, rows = None, []
    d = math.radians(a.fdir)
    for r in [float(x) for x in a.radii.split(",")]:
        ax, az = a.fgx - r * math.sin(d), a.fgz - r * math.cos(d)
        env = dict(os.environ)
        env.update(kv)          # the user's face params may already hold FCYL*: this try's axis wins
        env.update(FCYLX=repr(ax), FCYLZ=repr(az), FCYLR=repr(r))
        try_glb = os.path.join(work, "uvtry_low.glb")
        if os.path.exists(try_glb):
            os.remove(try_glb)  # never score the previous radius's cage when this one fails
        c = subprocess.run([py, os.path.join(STAGES, "lowsplit3.py"), "pre.glb", "uvtry", str(a.nb), str(a.nh), str(a.nf),
                            "0", str(a.collar), str(a.head_x0), str(a.head_x1), str(a.face_density)],
                           cwd=work, env=env, capture_output=True)
        q = subprocess.run([py, os.path.join(STAGES, "qa_uv.py"), "uvtry_low.glb"], cwd=work, env=env,
                           capture_output=True, text=True).stdout if c.returncode == 0 else ""
        m = re.search(r"UVQ ([\d.]+)", q or "")
        if not m:
            print("FCYLX=%.4f FCYLZ=%.4f FCYLR=%.3f UVQ failed (see lowsplit3/qa_uv)" % (ax, az, r))
            continue
        score = float(m.group(1))
        rows.append({"FCYLX": ax, "FCYLZ": az, "FCYLR": r, "score": score})
        print("FCYLX=%.4f FCYLZ=%.4f FCYLR=%.3f %s" % (ax, az, r, q.strip()))
        if best is None or score < best["score"]:
            best = rows[-1]
    if best is None:
        print("STATUE_FAIL no axis scored (every radius failed): nothing written", file=sys.stderr)
        return 1
    with open(os.path.join(work, "best_axis.env"), "w") as f:
        f.write("FCYLX=%r FCYLZ=%r FCYLR=%r\n" % (best["FCYLX"], best["FCYLZ"], best["FCYLR"]))
    print("BEST %.4f FCYLX=%.4f FCYLZ=%.4f FCYLR=%.3f (pass these to chain)" % (best["score"], best["FCYLX"], best["FCYLZ"], best["FCYLR"]))
    return 0


def cage_opts(p):
    p.add_argument("--nb", type=int, default=3300, help="body triangles")
    p.add_argument("--nh", type=int, default=2400, help="hat + hair triangles")
    p.add_argument("--nf", type=int, default=4800, help="face triangles")
    p.add_argument("--collar", type=float, default=0.575, help="hat+hair group starts above this height (glb y)")
    p.add_argument("--head-x0", type=float, default=-0.75, help="hat+hair group x range, low end (glb x)")
    p.add_argument("--head-x1", type=float, default=0.40, help="hat+hair group x range, high end (glb x)")
    p.add_argument("--face-density", type=float, default=3.0, help="texel density of face and neck vs the body")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--python", default=None)
        p.add_argument("--us-repo", default=None)
        p.add_argument("--ckpt", default=None)
        p.add_argument("--region", default=None)

    p = sub.add_parser("check"); common(p)
    p.add_argument("--stage", default="all", choices=("all", "refine", "chain")); p.add_argument("--json", action="store_true")
    p = sub.add_parser("patch"); common(p)
    p = sub.add_parser("refine"); common(p)
    p.add_argument("image"); p.add_argument("mesh"); p.add_argument("out_dir")
    p.add_argument("--steps", type=int, default=50); p.add_argument("--seed", type=int, default=42)
    p.add_argument("--octree", type=int, default=1024); p.add_argument("--mem-cap", default=None)
    p = sub.add_parser("chain"); common(p); cage_opts(p)
    p.add_argument("workdir"); p.add_argument("refined", nargs="?", default=None)
    p.add_argument("--name", default="statue"); p.add_argument("--size", type=int, default=2048)
    p.add_argument("--lift", type=float, default=1.0); p.add_argument("--seam-r", type=float, default=6)
    p.add_argument("--nf-pre", type=int, default=14000); p.add_argument("--nb-pre", type=int, default=160000)
    p.add_argument("--combo", default=None, help="reuse an earlier prep result (combo.glb): skips the slow prep")
    p.add_argument("--qa-force", action="store_true")
    p = sub.add_parser("uv-search"); common(p); cage_opts(p)
    p.add_argument("workdir")
    p.add_argument("--fdir", type=float, default=0.0, help="face direction, degrees from glb +z toward +x")
    p.add_argument("--fgx", type=float, default=0.0); p.add_argument("--fgz", type=float, default=0.0)
    p.add_argument("--radii", default="0.3,0.6,0.9,1.5,3.0")
    a, extra = ap.parse_known_args(argv)
    if a.cmd == "check":
        return print_check(check(a), a.json)
    if extra and a.cmd not in ("chain", "uv-search"):
        ap.error("unrecognized arguments: %s" % " ".join(extra))
    if a.cmd == "patch":
        return cmd_patch(a)
    if a.cmd == "refine":
        return cmd_refine(a)
    if a.cmd == "chain":
        if a.refined and KV.match(a.refined):      # `chain work --combo c.glb FCX=..`: the first KEY=VAL is not a mesh
            extra, a.refined = [a.refined] + extra, None
        if not a.refined and not a.combo:
            ap.error("chain needs <refined.glb> or --combo")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", a.name):
            ap.error("--name: letters, digits, _ and - only")
        return chain(a, extra)
    return uv_search(a, extra)


if __name__ == "__main__":
    sys.exit(main())
