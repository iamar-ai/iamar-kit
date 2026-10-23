#!/usr/bin/env python3
"""Can this computer run the kit's GPU tier (Tier 2)? Checks each step and names the fallback.

    python kit/gpu/gpu_check.py [--python ENV_PY] [--repo HY3D21_CLONE] [--region CC]
                                [--hf-home DIR] [--stage STAGE] [--json]
                                [--mvadapter CLONE] [--hy2-repo HY3D2_CLONE] [--views N]

Steps checked (kit/gpu/README.md):
  cutout  rembg + onnxruntime in the GPU environment's Python; CPU is enough
  shape   Hunyuan3D-2.1: an NVIDIA GPU with enough memory, torch with CUDA, the
          Hunyuan3D-2.1 clone, its weights (or room to download them), and a region
          the licence allows (not the EU, the UK or South Korea)
  cage    Blender 4.2+ (cage, normal bake, AO, LODs); CPU is enough
Multiview pipeline (--stage mv = cutout, views, shape_mv, cage; or one of them alone):
  concept   SDXL base 1.0 text-to-picture (optional step 0): CUDA, diffusers, 2 GB free GPU
  views     MV-Adapter on SDXL: an NVIDIA GPU with 10.8 GB free (4 views at 768 px peaked at
            9.7 GiB on an 11 GB card) and the MV-Adapter clone carrying
            kit/gpu/patches/mvadapter_11gb.patch (without it 14 GB; 6 views need more than 11)
  shape_mv  Hunyuan3D-2mv: CUDA, the Hunyuan3D-2 clone, its 2mv weights, a licensed region
  paint     Hunyuan3D-2 paint (optional): the clone's texture half built (custom_rasterizer),
            its paint and delight weights, a licensed region
--stage all is the single-view pipeline (cutout, shape, cage); --stage every checks both.

For every step it prints `STEP <name> READY` or `STEP <name> NOT_READY: <why>` followed by
`FALLBACK: <what to do instead>`, then GPU_CHECK_OK (every asked step ready) or
GPU_CHECK_NOT_READY, exit 0 or 2. --json prints the same as one JSON object.

Stdlib only: run it with any Python 3.8+. --python is the Python of the GPU environment
(default: the one running this script; env IAMAR_GPU_PYTHON). The numbers are measured
(kit/gpu/README.md "Hardware"). IAMAR_NVIDIA_SMI=path picks the nvidia-smi to ask (the
test points it at fake ones).
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pins  # noqa: E402

# Measured on an RTX A5000 24 GB, 2026-10-20 (kit/gpu/README.md "Hardware"): Hunyuan3D-2.1
# shape at octree 380 / 50 steps peaked at 14.8 GB allocated by torch, 17.0 GB in nvidia-smi
# (CUDA context and cache included) and 2.8 GB of RAM.
SHAPE_VRAM_MIB = 17000      # below this the shape step is not offered
SHAPE_VRAM_TIGHT_MIB = 20000  # 17-20 GB: should fit, never tested on such a card
SHAPE_RAM_GB = 8            # load needs headroom over the 2.8 GB measured peak
SHAPE_DISK_GB = 10          # weights 7.5 GB plus outputs
CUTOUT_RAM_GB = 2
CAGE_RAM_GB = 4
BLENDER_MIN = (4, 2)

# Multiview pipeline, measured in the iamar city on the build host's RTX 2080 Ti 11 GB (2026-10-14,
# the iamar-models mesh archive (not public) tools/mesh3d/README.md "Stable dragon breeds"): MV-Adapter 4 views at
# 768 px peaked at 9.7 GiB with the memory patch (unpatched they did not fit; MV-Adapter's
# README asks about 14 GB), 6 views did not fit; Hunyuan3D-2mv shape (fp16) and Hunyuan3D-2
# paint (model CPU offload) ran on the same 11 GB card. RAM was not recorded in the city:
# the RAM figures below are the kit's load headroom, not measurements.
VIEWS_VRAM_MIB = 10800          # 9.7 GiB peak + CUDA context; an 11 GB card (11264 MiB) passes
VIEWS_VRAM_UNPATCHED_MIB = 14336
VIEWS_MAX_ON_SMALL = 4          # more views need more than 11 GB even patched
SHAPE_MV_VRAM_MIB = 10800
PAINT_VRAM_MIB = 10800
CONCEPT_VRAM_MIB = 2000         # model CPU offload; --low-vram ran in about 1.5 GB
VIEWS_RAM_GB = 12
SHAPE_MV_RAM_GB = 16         # measured 15.7 GB peak (the GPU host A5000, 2026-10-22), octree 128 and 380 alike
PAINT_RAM_GB = 16
CONCEPT_RAM_GB = 12
VIEWS_DISK_GB = 12              # SDXL fp16 6.7 GB + MV-Adapter 3.4 GB + the fp16-fix VAE
SHAPE_MV_DISK_GB = 8
PAINT_DISK_GB = 16
CONCEPT_DISK_GB = 8
MV_PATCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patches", "mvadapter_11gb.patch")
MV_PIPE = os.path.join("mvadapter", "pipelines", "pipeline_mvadapter_i2mv_sdxl.py")

# Tencent Hunyuan 3D 2.1 Community License: the Territory excludes the European Union,
# the United Kingdom and South Korea.
EU = ("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE").split()
BARRED = set(EU) | {"EU", "GB", "UK", "KR"}


def region_problem(region, model="Hunyuan3D-2.1"):
    """None when `region` is an ISO 3166 alpha-2 code the licence covers, else why not.
    Hunyuan3D-2.1 and Hunyuan3D-2 / -2mv share the same Territory clause."""
    r = (region or "").strip().upper()
    if not r:
        return ("region unknown: ask the user which country the world is made and used in "
                "(--region CC); Hunyuan3D is not licensed in the EU, the UK or South Korea")
    if not re.fullmatch(r"[A-Z]{2}", r):
        return "region %r is not a two-letter ISO country code (US, JP, BR, ...)" % region
    if r in BARRED:
        return "region %s: the %s licence excludes the EU, the UK and South Korea" % (r, model)
    return None

FALLBACK = {
    "cutout": "install rembg into the GPU environment (pip install rembg onnxruntime), or cut the "
              "subject out by hand in any image editor and save a PNG with transparency "
              "(stages/cutout.py keeps a picture's own alpha)",
    "shape": "Tier 1: a hosted image-to-3D service on the user's own account (its own licence and "
             "region terms), then continue at `sculpt.py cage`; or Tier 0: reuse a catalogue "
             "object (iamar-world assets search) or model it in Blender (kit/blender/README.md)",
    "concept": "use a picture the user drew or has the rights to (never commercial art), or a hosted "
               "image generator on the user's own account; then continue at the cut-out",
    "views": "shape from the one picture instead (`sculpt.py shape`, Hunyuan3D-2.1, 17 GB), or "
             "draw or paint the side and back views by hand and save them as P_az090_rgba.png etc. "
             "for `sculpt.py shape --mv`; or Tier 0 (catalogue, Blender)",
    "shape_mv": "shape from the one picture (`sculpt.py shape`, Hunyuan3D-2.1) if that fits, else Tier 0: "
                "reuse a catalogue object (iamar-world assets search) or model it in Blender; a mesh from "
                "any source the user has rights to enters at `sculpt.py cage`",
    "paint": "skip painting: the kit's material library and the normal and light bake colour the cage "
             "(`sculpt.py game`, kit/style), or paint the cage's texture by hand",
    "cage": "install Blender 4.2 or newer (kit/blender/README.md, 'Install Blender'); without it "
            "no cage, normal bake or LODs can be made",
}


STAGE_SETS = {
    "all": ["cutout", "shape", "cage"],
    "mv": ["cutout", "views", "shape_mv", "cage"],
    "every": ["cutout", "shape", "cage", "concept", "views", "shape_mv", "paint"],
}

# every Hunyuan3D model (2.0, 2mv, 2.1) shares the Territory clause: no other generator in the
# kit replaces it in a barred region
FALLBACK_REGION = ("Tier 0: reuse a catalogue object (iamar-world assets search) or model it in Blender "
                   "(kit/blender/README.md, kit/style); a mesh from any source the user has rights to "
                   "enters at `sculpt.py cage`; paint with the kit's materials instead of Hunyuan3D paint")


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, "", str(e)


def gpus():
    """NVIDIA GPUs from nvidia-smi: [{name, total_mib, free_mib, driver}]."""
    smi = os.environ.get("IAMAR_NVIDIA_SMI") or shutil.which("nvidia-smi")
    if not smi or not os.path.isfile(smi):
        return []
    rc, out, _ = run([smi, "--query-gpu=name,memory.total,memory.free,driver_version",
                      "--format=csv,noheader,nounits"])
    res = []
    if rc != 0:
        return res
    for line in out.strip().splitlines():
        f = [x.strip() for x in line.split(",")]
        if len(f) >= 3:
            try:
                res.append({"name": f[0], "total_mib": int(float(f[1])), "free_mib": int(float(f[2])),
                            "driver": f[3] if len(f) > 3 else ""})
            except ValueError:
                pass
    return res


def used_gpu(g):
    """The GPU torch will run on (cuda:0): the first of CUDA_VISIBLE_DEVICES when it lists
    indexes, else nvidia-smi's first (valid because the launchers set CUDA_DEVICE_ORDER=PCI_BUS_ID;
    CUDA's own default FASTEST_FIRST would number the GPUs differently). None when there is none or the variable hides all."""
    if not g:
        return None
    vis = os.environ.get("CUDA_VISIBLE_DEVICES")
    if vis is None:
        return g[0]
    first = vis.split(",")[0].strip()
    if first == "" or first == "-1":
        return None
    if first.isdigit():
        i = int(first)
        return g[i] if i < len(g) else None
    return g[0]   # a UUID: nvidia-smi order is not known here; assume the first


def ram_gb():
    """(total, available) GB, or (None, None) when unknown."""
    try:
        with open("/proc/meminfo") as f:
            m = dict(l.split(":", 1) for l in f)
        kb = lambda k: int(m[k].split()[0])
        return kb("MemTotal") / 1e6, kb("MemAvailable") / 1e6
    except (OSError, KeyError, ValueError):
        pass
    if sys.platform == "darwin":
        rc, out, _ = run(["sysctl", "-n", "hw.memsize"])
        if rc == 0:
            t = int(out.strip()) / 1e9
            return t, None
    return None, None


def disk_free_gb(path):
    p = path
    while p and not os.path.exists(p):
        p = os.path.dirname(p)
    try:
        return shutil.disk_usage(p or ".").free / 1e9
    except OSError:
        return None


def env_modules(py, mods, cuda=False):
    """Which modules the GPU environment's Python can import (find_spec, no import), and
    whether torch sees CUDA (that one imports torch)."""
    code = ("import json, importlib.util as u\n"
            "r = {m: bool(u.find_spec(m)) for m in %r}\n" % (list(mods),))
    if cuda:
        code += ("try:\n import torch; r['_cuda'] = bool(torch.cuda.is_available()); r['_torch'] = torch.__version__\n"
                 "except Exception as e: r['_cuda'] = False; r['_torch_error'] = str(e)[:200]\n")
    code += "print(json.dumps(r))"
    rc, out, err = run([py, "-c", code], timeout=180)
    if rc != 0:
        return None, (err.strip().splitlines() or ["python failed"])[-1]
    try:
        return json.loads(out.strip().splitlines()[-1]), None
    except (ValueError, IndexError):
        return None, "could not read the module check"


def hf_home(arg):
    if arg:
        return arg
    if os.environ.get("HF_HOME"):
        return os.environ["HF_HOME"]
    return os.path.join(os.path.expanduser("~"), ".cache", "huggingface")


def weights_cached(home, repo_id, folders, min_bytes=100_000_000):
    """A snapshot where every folder has a config.yaml and a model checkpoint of at least
    min_bytes (an interrupted download leaves the folders but not the files)."""
    base = os.path.join(home, "hub", "models--" + repo_id.replace("/", "--"), "snapshots")
    for snap in glob.glob(os.path.join(base, "*")):
        if os.path.basename(snap) != pins.hf(repo_id):
            continue   # only the pinned revision counts (kit/gpu/pins.json)
        good = True
        for d in folders:
            f = os.path.join(snap, d)
            cfg = os.path.join(f, "config.yaml")
            ck = [c for c in glob.glob(os.path.join(f, "model*")) if c.endswith((".ckpt", ".safetensors"))]
            if not (os.path.isfile(cfg) and os.path.getsize(cfg) > 0
                    and any(os.path.getsize(c) >= min_bytes for c in ck if os.path.isfile(c))):
                good = False
        if good:
            return snap
    return None


def hf_file(home, repo_id, rel, min_bytes):
    """A snapshot of repo_id holding `rel` (a file, or any file under a folder) of at least
    min_bytes, else None."""
    base = os.path.join(home, "hub", "models--" + repo_id.replace("/", "--"), "snapshots")
    for snap in glob.glob(os.path.join(base, "*")):
        if os.path.basename(snap) != pins.hf(repo_id):
            continue   # only the pinned revision counts (kit/gpu/pins.json)
        f = os.path.join(snap, rel)
        files = [f] if os.path.isfile(f) else glob.glob(os.path.join(f, "**", "*"), recursive=True)
        if any(os.path.isfile(x) and os.path.getsize(x) >= min_bytes for x in files):
            return snap
    return None


def mv_patched(clone):
    """True when the MV-Adapter clone carries the memory patch, False when it does not,
    None when the clone is not there."""
    p = os.path.join(clone or "", MV_PIPE)
    if not clone or not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8", errors="replace") as f:
        src = f.read()
    return not re.search(r"v\.clone\(\)\s+for\s+k\s*,\s*v\s+in\s+ref_hidden_states", src)


def pin_check(clone, name, why):
    """Appends to `why` when the git clone is not at the commit pinned in pins.json."""
    p = pins.clone_problem(clone, name)
    if p:
        why.append(p)


def gpu_need(g, need_mib, what, why):
    """Appends to `why` when the GPU torch will use cannot hold `need_mib` (total or free now)."""
    best = used_gpu(g)
    if g and not best:
        why.append("CUDA_VISIBLE_DEVICES=%r hides every GPU" % os.environ.get("CUDA_VISIBLE_DEVICES"))
    elif not best:
        why.append("no NVIDIA GPU found (nvidia-smi); %s needs CUDA" % what)
    elif best["total_mib"] < need_mib:
        why.append("GPU %s has %.1f GB, %s needs %.1f GB" % (best["name"], best["total_mib"] / 1024, what, need_mib / 1024))
    elif best["free_mib"] < need_mib:
        why.append("only %.1f GB of GPU memory free on %s now (%.1f GB needed): stop other GPU work first"
                   % (best["free_mib"] / 1024, best["name"], need_mib / 1024))
    return best


def weights_need(home, found, label, disk_gb, why, notes):
    if found:
        notes.append("%s cached: %s" % (label, found))
        return
    free = disk_free_gb(home)
    if free is not None and free < disk_gb:
        why.append("%s not cached and only %.0f GB free in %s (needs %d)" % (label, free, home, disk_gb))
    else:
        notes.append("%s not cached: the first run downloads them to %s" % (label, home))


def find_blender():
    cands = []
    if os.environ.get("BLENDER"):
        cands.append(os.environ["BLENDER"])
    w = shutil.which("blender")
    if w:
        cands.append(w)
    home = os.path.expanduser("~")
    cands += sorted(glob.glob(os.path.join(home, "opt", "blender-*", "blender")), reverse=True)
    cands += sorted(glob.glob(os.path.join(home, "opt", "blender-*", "blender.exe")), reverse=True)
    cands += sorted(glob.glob("/opt/blender*/blender"), reverse=True)
    cands += ["/usr/bin/blender", "/snap/bin/blender", "/Applications/Blender.app/Contents/MacOS/Blender"]
    cands += sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"), reverse=True)
    old = (None, None)
    seen = set()
    for c in cands:
        if c and os.path.isfile(c) and os.path.realpath(c) not in seen:
            seen.add(os.path.realpath(c))
            rc, out, _ = run([c, "--version"], timeout=60)
            m = re.search(r"Blender (\d+)\.(\d+)(?:\.(\d+))?", out or "")
            if rc == 0 and m:
                ver = tuple(int(x or 0) for x in m.groups())
                if ver[:2] >= BLENDER_MIN:
                    return c, ver      # the first new-enough one wins
                old = old if old[0] else (c, ver)
    return old                         # only too-old ones (or none)


def _statue():
    """kit/gpu/statue/statue.py, which imports this module, so it is loaded on demand.
    Its fallback text becomes FALLBACK['refine'] (the statue chain owns it)."""
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statue")
    if here not in sys.path:
        sys.path.insert(0, here)
    import statue
    FALLBACK["refine"] = statue.FALLBACK["refine"]
    return statue


def check(a):
    res = {"steps": {}, "host": {}}
    total, avail = ram_gb()
    res["host"]["ram_total_gb"] = round(total, 1) if total else None
    res["host"]["ram_available_gb"] = round(avail, 1) if avail else None
    g = gpus()
    res["host"]["gpus"] = g
    ram_ok = lambda need: avail is None or avail >= need
    want = STAGE_SETS.get(a.stage, [a.stage])
    mods = None
    mods_err = None
    if set(want) & {"cutout", "shape", "concept", "views", "shape_mv", "paint"}:
        mods, mods_err = env_modules(a.python, ["rembg", "onnxruntime", "PIL", "numpy", "trimesh",
                                                "diffusers", "pymeshlab", "transformers", "cv2",
                                                "custom_rasterizer"],
                                     cuda=bool(set(want) & {"shape", "concept", "views", "shape_mv", "paint"}))
        res["host"]["python"] = a.python
        res["host"]["modules"] = mods

    def put(step, why, notes=None):
        res["steps"][step] = {"ready": not why, "why": why, "notes": notes or [],
                              "fallback": FALLBACK[step] if why else None}

    if "cutout" in want:
        why = []
        if mods is None:
            why.append("the GPU environment's Python did not run (%s): pass --python" % mods_err)
        else:
            miss = [m for m in ("rembg", "onnxruntime", "PIL", "numpy") if not mods.get(m)]
            if miss:
                why.append("missing in %s: %s" % (a.python, ", ".join(miss)))
        if not ram_ok(CUTOUT_RAM_GB):
            why.append("%.1f GB RAM available, needs %d" % (avail, CUTOUT_RAM_GB))
        put("cutout", "; ".join(why))

    if "shape" in want:
        why, notes = [], []
        rp = region_problem(a.region or os.environ.get("IAMAR_REGION"))
        if rp:
            why.append(rp)
        best = used_gpu(g)
        if g and not best:
            why.append("CUDA_VISIBLE_DEVICES=%r hides every GPU" % os.environ.get("CUDA_VISIBLE_DEVICES"))
        elif not best:
            why.append("no NVIDIA GPU found (nvidia-smi); Hunyuan3D-2.1 needs CUDA")
        elif best["total_mib"] < SHAPE_VRAM_MIB:
            why.append("GPU %s has %.1f GB, the shape step peaked at 17.0 GB" % (best["name"], best["total_mib"] / 1024))
        else:
            if best["total_mib"] < SHAPE_VRAM_TIGHT_MIB:
                notes.append("GPU %s %.1f GB: should fit (17.0 GB measured peak) but untested; close other GPU work"
                             % (best["name"], best["total_mib"] / 1024))
            if best["free_mib"] < SHAPE_VRAM_MIB:
                why.append("only %.1f GB of GPU memory free on %s now (17.0 GB needed): stop other GPU work first"
                           % (best["free_mib"] / 1024, best["name"]))
        if mods is None:
            why.append("the GPU environment's Python did not run (%s): pass --python" % mods_err)
        else:
            if not mods.get("_cuda"):
                why.append("torch with CUDA not usable in %s (%s)" % (
                    a.python, mods.get("_torch_error") or ("torch " + mods["_torch"] if mods.get("_torch") else "no torch")))
            miss = [m for m in ("diffusers", "trimesh", "pymeshlab") if not mods.get(m)]
            if miss:
                why.append("missing in %s: %s (Hunyuan3D-2.1 requirements)" % (a.python, ", ".join(miss)))
        repo = a.repo or os.environ.get("HY3D21_REPO")
        if not repo or not os.path.isdir(os.path.join(repo, "hy3dshape", "hy3dshape")):
            why.append("Hunyuan3D-2.1 clone not found (--repo or HY3D21_REPO; README 'Install')")
        else:
            pin_check(repo, "Hunyuan3D-2.1", why)
        home = hf_home(a.hf_home)
        snap = weights_cached(home, "tencent/Hunyuan3D-2.1", ["hunyuan3d-dit-v2-1", "hunyuan3d-vae-v2-1"])
        free = disk_free_gb(home)
        if snap:
            notes.append("weights cached: " + snap)
        elif free is not None and free < SHAPE_DISK_GB:
            why.append("weights not cached and only %.0f GB free in %s (needs %d)" % (free, home, SHAPE_DISK_GB))
        else:
            notes.append("weights not cached: the first run downloads 7.5 GB to %s" % home)
        if not ram_ok(SHAPE_RAM_GB):
            why.append("%.1f GB RAM available, needs %d" % (avail, SHAPE_RAM_GB))
        put("shape", "; ".join(why), notes)

    home = hf_home(a.hf_home)
    region = a.region or os.environ.get("IAMAR_REGION")

    def env_needs(why, need, what):
        if mods is None:
            why.append("the GPU environment's Python did not run (%s): pass --python" % mods_err)
            return
        if not mods.get("_cuda"):
            why.append("torch with CUDA not usable in %s (%s)" % (
                a.python, mods.get("_torch_error") or ("torch " + mods["_torch"] if mods.get("_torch") else "no torch")))
        miss = [m for m in need if not mods.get(m)]
        if miss:
            why.append("missing in %s: %s (%s)" % (a.python, ", ".join(miss), what))

    if "concept" in want:
        why, notes = [], []
        gpu_need(g, CONCEPT_VRAM_MIB, "SDXL", why)
        env_needs(why, ("diffusers", "transformers"), "SDXL")
        weights_need(home, hf_file(home, "stabilityai/stable-diffusion-xl-base-1.0",
                                   "unet/diffusion_pytorch_model.fp16.safetensors", 1_000_000_000),
                     "SDXL fp16 weights", CONCEPT_DISK_GB, why, notes)
        if not ram_ok(CONCEPT_RAM_GB):
            why.append("%.1f GB RAM available, needs %d" % (avail, CONCEPT_RAM_GB))
        notes.append("SDXL base 1.0: CreativeML Open RAIL++-M (use restrictions; outputs are the user's)")
        put("concept", "; ".join(why), notes)

    if "views" in want:
        why, notes = [], []
        clone = getattr(a, "mvadapter", None) or os.environ.get("MVADAPTER")
        patched = mv_patched(clone)
        n = getattr(a, "views", 4)
        need = VIEWS_VRAM_MIB if patched else VIEWS_VRAM_UNPATCHED_MIB
        if n > VIEWS_MAX_ON_SMALL:
            need = max(need, VIEWS_VRAM_UNPATCHED_MIB)
            notes.append("%d views: more than 4 did not fit an 11 GB card even patched (city); "
                         "14 GB asked, untested" % n)
        best = gpu_need(g, need, "MV-Adapter (%d views at 768 px)" % n, why)
        if patched is None:
            why.append("MV-Adapter clone not found (--mvadapter or MVADAPTER; README 'Install multiview')")
        elif not patched and best and best["total_mib"] < VIEWS_VRAM_UNPATCHED_MIB:
            why.append("the MV-Adapter clone is not patched and this card is under 14 GB: "
                       "git -C %s apply %s" % (clone, MV_PATCH))
        elif not patched:
            notes.append("MV-Adapter clone not patched: fine on this card; the patch saves memory "
                         "(git -C %s apply %s)" % (clone, MV_PATCH))
        env_needs(why, ("diffusers", "transformers", "rembg", "PIL", "numpy"), "MV-Adapter requirements")
        for label, repo_id, rel, mb in (
                ("SDXL fp16 weights", "stabilityai/stable-diffusion-xl-base-1.0",
                 "unet/diffusion_pytorch_model.fp16.safetensors", 1_000_000_000),
                ("MV-Adapter weights", "huanngzh/mv-adapter", "mvadapter_i2mv_sdxl.safetensors", 1_000_000_000),
                ("fp16-fix VAE", "madebyollin/sdxl-vae-fp16-fix", "diffusion_pytorch_model.safetensors", 50_000_000)):
            weights_need(home, hf_file(home, repo_id, rel, mb), label, VIEWS_DISK_GB, why, notes)
        if not ram_ok(VIEWS_RAM_GB):
            why.append("%.1f GB RAM available, needs %d" % (avail, VIEWS_RAM_GB))
        notes.append("MV-Adapter Apache-2.0; SDXL base CreativeML Open RAIL++-M (use restrictions); no region limit")
        put("views", "; ".join(why), notes)

    hy2 = getattr(a, "hy2_repo", None) or os.environ.get("HY3D2_REPO")
    if "shape_mv" in want:
        why, notes = [], []
        rp = region_problem(region, "Hunyuan3D-2")
        if rp:
            why.append(rp)
        gpu_need(g, SHAPE_MV_VRAM_MIB, "Hunyuan3D-2mv", why)
        env_needs(why, ("trimesh", "pymeshlab", "diffusers"), "Hunyuan3D-2 requirements")
        if not hy2 or not os.path.isdir(os.path.join(hy2, "hy3dgen", "shapegen")):
            why.append("Hunyuan3D-2 clone not found (--hy2-repo or HY3D2_REPO; README 'Install multiview')")
        else:
            pin_check(hy2, "Hunyuan3D-2", why)
        weights_need(home, weights_cached(home, "tencent/Hunyuan3D-2mv", ["hunyuan3d-dit-v2-mv"]),
                     "Hunyuan3D-2mv weights", SHAPE_MV_DISK_GB, why, notes)
        if not ram_ok(SHAPE_MV_RAM_GB):
            why.append("%.1f GB RAM available, needs %d" % (avail, SHAPE_MV_RAM_GB))
        put("shape_mv", "; ".join(why), notes)

    if "paint" in want:
        why, notes = [], []
        rp = region_problem(region, "Hunyuan3D-2")
        if rp:
            why.append(rp)
        gpu_need(g, PAINT_VRAM_MIB, "Hunyuan3D-2 paint", why)
        env_needs(why, ("trimesh", "diffusers", "custom_rasterizer"), "Hunyuan3D-2 texture half, built")
        if not hy2 or not os.path.isdir(os.path.join(hy2, "hy3dgen", "texgen")):
            why.append("Hunyuan3D-2 clone not found (--hy2-repo or HY3D2_REPO; README 'Install multiview')")
        else:
            pin_check(hy2, "Hunyuan3D-2", why)
        found = [hf_file(home, "tencent/Hunyuan3D-2", d, 100_000_000)
                 for d in ("hunyuan3d-paint-v2-0", "hunyuan3d-delight-v2-0")]
        weights_need(home, found[0] if all(found) else None, "Hunyuan3D-2 paint and delight weights",
                     PAINT_DISK_GB, why, notes)
        if not ram_ok(PAINT_RAM_GB):
            why.append("%.1f GB RAM available, needs %d" % (avail, PAINT_RAM_GB))
        put("paint", "; ".join(why), notes)

    if "cage" in want:
        why = []
        path, ver = find_blender()
        res["host"]["blender"] = {"path": path, "version": ".".join(map(str, ver)) if ver else None}
        if not path:
            why.append("Blender not found (BLENDER=, PATH or a usual install folder)")
        elif ver[:2] < BLENDER_MIN:
            why.append("Blender %s at %s is older than 4.2" % (".".join(map(str, ver)), path))
        if not ram_ok(CAGE_RAM_GB):
            why.append("%.1f GB RAM available, needs %d" % (avail, CAGE_RAM_GB))
        put("cage", "; ".join(why))

    if "refine" in want:
        res["steps"]["refine"] = _statue().refine_ready(argparse.Namespace(
            python=a.python, us_repo=None, ckpt=None, region=a.region))

    res["ready"] = all(s["ready"] for s in res["steps"].values())
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--python", default=os.environ.get("IAMAR_GPU_PYTHON") or sys.executable)
    ap.add_argument("--repo", default=None, help="Hunyuan3D-2.1 clone (env HY3D21_REPO)")
    ap.add_argument("--region", default=None, help="ISO country code of the user (env IAMAR_REGION)")
    ap.add_argument("--hf-home", default=None, help="Hugging Face cache (env HF_HOME)")
    ap.add_argument("--stage", default="all", choices=sorted(set(STAGE_SETS) | set(FALLBACK) | {"refine"}))
    ap.add_argument("--mvadapter", default=None, help="MV-Adapter clone (env MVADAPTER)")
    ap.add_argument("--hy2-repo", default=None, help="Hunyuan3D-2 clone for shape_mv and paint (env HY3D2_REPO)")
    ap.add_argument("--views", type=int, default=4, help="views stage: how many views (default 4)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = check(a)
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        h = res["host"]
        print("HOST RAM %s GB total, %s GB available; GPU %s" % (
            h["ram_total_gb"], h["ram_available_gb"],
            ", ".join("%s %.1f GB (%.1f free)" % (x["name"], x["total_mib"] / 1024, x["free_mib"] / 1024)
                      for x in h["gpus"]) or "none (NVIDIA)"))
        for name, s in res["steps"].items():
            if s["ready"]:
                print("STEP %s READY" % name)
            else:
                print("STEP %s NOT_READY: %s" % (name, s["why"]))
                print("  FALLBACK: %s" % s["fallback"])
            for n in s["notes"]:
                print("  NOTE: %s" % n)
        print("GPU_CHECK_OK" if res["ready"] else "GPU_CHECK_NOT_READY")
    return 0 if res["ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
