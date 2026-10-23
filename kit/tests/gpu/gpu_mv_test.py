#!/usr/bin/env python3
"""Tests of the GPU tier's multiview pipeline (kit/gpu: views, recut, shape --mv, paint, paintfix).

    python3 kit/tests/gpu/gpu_mv_test.py [--keep DIR]

Runs on any computer (Linux, macOS, Windows), no GPU needed, a few seconds:
  - gpu_check.py --stage views / shape_mv / paint / concept against fake nvidia-smi programs:
    an 11 GB card passes the views step only with the memory patch in the MV-Adapter clone,
    6 views ask 14 GB, an 8 GB card is refused, a busy card is told to stop other GPU work;
    cached weights are found in HF_HOME (sparse files), half downloads are not
  - the region gate on shape --mv and paint (none, DE, GB, KR refused with the Tier 0 fallback)
  - sculpt.py argument checks (run --mv needs --text, --text/--base without --mv/--paint,
    bad --az) and each stage's own refusals before any GPU import (missing views, clone, map)
  - kit/gpu/patches/mvadapter_11gb.patch applies to the line it targets and flips the check
  - the CPU stages on generated pictures: paint_fix (grey fill recoloured, colours lifted,
    glow mask), mv_recut --no-rembg (az 0 framed from the clean cut-out like MV-Adapter's
    preprocess_image, other views cut from the flat grey), clean_concept --alpha (outline,
    plinth cut, square crop); SKIPPED without numpy + Pillow (+ opencv-python for the last two)
Opt-in GPU smoke run (an NVIDIA GPU with 11+ GB, the MV-Adapter and Hunyuan3D-2 installs):
  IAMAR_GPU_SMOKE_MV=1 IAMAR_GPU_PYTHON=... MVADAPTER=... HY3D2_REPO=... HF_HOME=... \\
      IAMAR_REGION=US python3 kit/tests/gpu/gpu_mv_test.py
  makes 4 views of a generated picture at 512 px / 10 steps, a Hunyuan3D-2mv shape at octree
  128 / 10 steps, then the cage and game steps when Blender is there.
Prints GPU_MV_TEST_OK and exits 0 when nothing failed.
"""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
GPU = KIT / "gpu"
sys.path.insert(0, str(GPU))
sys.path.insert(0, str(GPU / "stages"))
sys.dont_write_bytecode = True
import gpu_check  # noqa: E402
import pins  # noqa: E402
import paint_mv  # noqa: E402
import shape_mv  # noqa: E402

FAILS, PASSES, SKIPS = [], [], []
WIN = os.name == "nt"


def ok(cond, what, detail=""):
    (PASSES if cond else FAILS).append(what + ("" if cond else ": " + detail))
    print(("PASS " if cond else "FAIL ") + what + ("" if cond else "\n     " + str(detail)[:1500]))


def skip(what, why):
    SKIPS.append(what)
    print("SKIPPED %s (%s)" % (what, why))


def fake_smi(d, lines):
    """A fake nvidia-smi printing `lines` (a shell script, or a .cmd on Windows)."""
    d.mkdir(parents=True, exist_ok=True)
    if WIN:
        p = d / "nvidia-smi.cmd"
        p.write_text("@echo off\r\n" + "".join("echo %s\r\n" % l for l in lines))
    else:
        p = d / "nvidia-smi"
        p.write_text("#!/bin/sh\n" + "".join("echo '%s'\n" % l for l in lines))
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def check_json(tmp, smi, stage, *args, cvd=None):
    env = dict(os.environ)
    env["IAMAR_NVIDIA_SMI"] = str(smi)
    for k in ("CUDA_VISIBLE_DEVICES", "IAMAR_REGION", "MVADAPTER", "HY3D2_REPO", "HF_HOME"):
        env.pop(k, None)
    if cvd is not None:
        env["CUDA_VISIBLE_DEVICES"] = cvd
    r = subprocess.run([sys.executable, str(GPU / "gpu_check.py"), "--stage", stage, "--json",
                        "--python", sys.executable, "--hf-home", str(tmp / "hf")] + list(args),
                       capture_output=True, text=True, env=env)
    try:
        j = json.loads(r.stdout)
    except ValueError:
        j = {"_raw": r.stdout + r.stderr}
    st = j.get("steps", {}).get(stage, {})
    return r.returncode, st.get("why", "") or "", " ".join(st.get("notes", [])), st


def fake_clone(d, patched):
    f = d / gpu_check.MV_PIPE
    f.parent.mkdir(parents=True, exist_ok=True)
    line = ('            "ref_hidden_states": ref_hidden_states,  # (w4: no clone, 11 GB card)\n' if patched else
            '            "ref_hidden_states": {k: v.clone() for k, v in ref_hidden_states.items()},\n')
    with open(f, "w", newline="\n") as fh:
        fh.write("class P:\n    def x(self):\n        cross_attention_kwargs = {\n" + line + "        }\n")
    return d


def sparse(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(size)


def test_views_check(tmp):
    smi11 = fake_smi(tmp / "s11", ["NVIDIA GeForce RTX 2080 Ti, 11264, 11000, 550.1"])
    smi8 = fake_smi(tmp / "s8", ["NVIDIA GeForce RTX 3070, 8192, 7900, 550.1"])
    smi24 = fake_smi(tmp / "s24", ["NVIDIA RTX A5000, 24564, 23800, 550.1"])
    busy = fake_smi(tmp / "sbusy", ["NVIDIA RTX A5000, 24564, 6000, 550.1"])
    none = tmp / "snone" / ("nvidia-smi.cmd" if WIN else "nvidia-smi")
    pat = fake_clone(tmp / "mv_patched", True)
    unp = fake_clone(tmp / "mv_plain", False)
    ok(gpu_check.mv_patched(str(pat)) is True and gpu_check.mv_patched(str(unp)) is False
       and gpu_check.mv_patched(str(tmp / "nowhere")) is None, "mv_patched: patched / plain / missing clone")
    rc, why, notes, st = check_json(tmp, smi11, "views", "--mvadapter", str(pat))
    ok("GPU" not in why.split("torch")[0] and "patched" not in why and "clone not found" not in why,
       "views: 11 GB card + patched clone -> no GPU or clone objection", why)
    rc, why, notes, st = check_json(tmp, smi11, "views", "--mvadapter", str(unp))
    ok(rc == 2 and "not patched" in why and "mvadapter_11gb.patch" in why,
       "views: 11 GB card + plain clone -> apply the patch (names the command)", why)
    ok("14.0 GB" in why, "views: unpatched clone asks 14 GB", why)
    rc, why, notes, st = check_json(tmp, smi24, "views", "--mvadapter", str(unp))
    ok("not patched" not in why and "not patched" in notes, "views: 24 GB card + plain clone -> only a note", why + " | " + notes)
    rc, why, notes, st = check_json(tmp, smi11, "views", "--mvadapter", str(pat), "--views", "6")
    ok(rc == 2 and "6 views" in why and "14.0 GB" in why, "views: 6 views on 11 GB -> refused (14 GB)", why)
    rc, why, notes, st = check_json(tmp, smi8, "views", "--mvadapter", str(pat))
    ok(rc == 2 and "8.0 GB" in why and "10.5 GB" in why, "views: 8 GB card -> too small", why)
    rc, why, notes, st = check_json(tmp, busy, "views", "--mvadapter", str(pat))
    ok(rc == 2 and "free" in why and "stop other GPU work" in why, "views: busy card -> stop other GPU work", why)
    rc, why, notes, st = check_json(tmp, none, "views", "--mvadapter", str(pat))
    ok(rc == 2 and "no NVIDIA GPU" in why and bool(st.get("fallback")), "views: no GPU -> refused with a fallback", why)
    rc, why, notes, st = check_json(tmp, smi11, "views")
    ok("MV-Adapter clone not found" in why, "views: no clone -> named", why)
    ok("Apache-2.0" in notes and "RAIL++-M" in notes and "no region limit" in notes,
       "views: licences in the notes, no region gate", notes)
    ok("SDXL fp16 weights not cached" in notes + why, "views: SDXL weights not cached -> download note or disk reason",
       notes + " | " + why)
    hf = tmp / "hf" / "hub"
    sparse(hf / "models--stabilityai--stable-diffusion-xl-base-1.0" / "snapshots" / pins.hf("stabilityai/stable-diffusion-xl-base-1.0") / "unet"
           / "diffusion_pytorch_model.fp16.safetensors", 2_000_000_000)
    sparse(hf / "models--huanngzh--mv-adapter" / "snapshots" / pins.hf("huanngzh/mv-adapter") / "mvadapter_i2mv_sdxl.safetensors", 100)
    rc, why, notes, st = check_json(tmp, smi11, "views", "--mvadapter", str(pat))
    ok("SDXL fp16 weights cached" in notes and "MV-Adapter weights cached" not in notes,
       "views: SDXL found in HF_HOME, a 100-byte adapter file is not 'cached'", notes)
    shutil.rmtree(tmp / "hf")


def test_hy2_checks(tmp):
    smi11 = fake_smi(tmp / "s11b", ["NVIDIA GeForce RTX 2080 Ti, 11264, 11000, 550.1"])
    smi8 = fake_smi(tmp / "s8b", ["NVIDIA GeForce RTX 3070, 8192, 7900, 550.1"])
    hy2 = tmp / "hy2"
    (hy2 / "hy3dgen" / "shapegen").mkdir(parents=True, exist_ok=True)
    for cc in ("DE", "GB", "KR"):
        rc, why, notes, st = check_json(tmp, smi11, "shape_mv", "--region", cc, "--hy2-repo", str(hy2))
        ok(rc == 2 and "Hunyuan3D-2 licence excludes" in why, "shape_mv: region %s barred" % cc, why)
    rc, why, notes, st = check_json(tmp, smi11, "shape_mv", "--hy2-repo", str(hy2))
    ok(rc == 2 and "region unknown" in why, "shape_mv: no region -> ask the user", why)
    rc, why, notes, st = check_json(tmp, smi11, "shape_mv", "--region", "US", "--hy2-repo", str(hy2))
    ok("region" not in why and "GPU" not in why.split("torch")[0] and "clone not found" not in why,
       "shape_mv: 11 GB card + US + clone -> no GPU, region or clone objection", why)
    rc, why, notes, st = check_json(tmp, smi8, "shape_mv", "--region", "US", "--hy2-repo", str(hy2))
    ok(rc == 2 and "8.0 GB" in why, "shape_mv: 8 GB card -> too small", why)
    rc, why, notes, st = check_json(tmp, smi11, "shape_mv", "--region", "US")
    ok("Hunyuan3D-2 clone not found" in why, "shape_mv: no clone -> named", why)
    snap = tmp / "hf" / "hub" / "models--tencent--Hunyuan3D-2mv" / "snapshots" / pins.hf("tencent/Hunyuan3D-2mv") / "hunyuan3d-dit-v2-mv"
    snap.mkdir(parents=True, exist_ok=True)
    (snap / "config.yaml").write_text("model: x\n")
    rc, why, notes, st = check_json(tmp, smi11, "shape_mv", "--region", "US", "--hy2-repo", str(hy2))
    ok("weights cached" not in notes, "shape_mv: config without checkpoint is not 'cached'", notes)
    sparse(snap / "model.fp16.safetensors", 150_000_000)
    rc, why, notes, st = check_json(tmp, smi11, "shape_mv", "--region", "US", "--hy2-repo", str(hy2))
    ok("Hunyuan3D-2mv weights cached" in notes, "shape_mv: 2mv weights found in HF_HOME", notes)
    rc, why, notes, st = check_json(tmp, smi11, "paint", "--region", "US", "--hy2-repo", str(hy2))
    ok(rc == 2 and "custom_rasterizer" in why and "clone not found" in why,
       "paint: texture half not built / texgen missing -> named", why)
    rc, why, notes, st = check_json(tmp, smi11, "paint", "--region", "KR", "--hy2-repo", str(hy2))
    ok(rc == 2 and "excludes" in why, "paint: region KR barred", why)
    rc, why, notes, st = check_json(tmp, smi11, "concept")
    ok("RAIL++-M" in notes and "region" not in why, "concept: licence noted, no region gate", why + " | " + notes)
    shutil.rmtree(tmp / "hf")


def sculpt(*args, env_extra=None):
    env = dict(os.environ)
    env.pop("IAMAR_REGION", None)
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, str(GPU / "sculpt.py")] + list(args), capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def test_sculpt_args(tmp):
    for cc in ("DE", "GB", "KR"):
        rc, out = sculpt("shape", "--mv", str(tmp / "v" / "x"), str(tmp / "x.glb"), "--region", cc)
        ok(rc == 3 and "SCULPT_REFUSED" in out and "Tier 0" in out and "Hunyuan3D-2.1" not in out.split("FALLBACK")[1],
           "sculpt shape --mv: region %s refused, Tier 0 fallback (not 2.1, also barred)" % cc, out)
    rc, out = sculpt("paint", "a.glb", "v", "o.glb")
    ok(rc == 3 and "region unknown" in out, "sculpt paint: no region -> refused (exit 3)", out)
    base = ["run", "x.png", str(tmp / "o"), "--height", "1", "--budget", "100"]
    for extra, want in ((["--text", "a"], "--text only with --mv"),
                        (["--mv"], "--mv needs --text"),
                        (["--mv", "--text", "a", "--base", "#112233"], "--base only with --paint"),
                        (["--mv", "--text", "a", "--az", "90,180"], "including 0"),
                        (["--mv", "--text", "a", "--az", "0,x"], "--az: degrees"),
                        (["--recut"], "--recut only with --mv")):
        rc, out = sculpt(*(base + extra))
        ok(rc == 2 and want in out, "sculpt run %s -> %r" % (" ".join(extra), want), out)
    rc, out = sculpt(*(base + ["--mv", "--text", "a stone urn", "--region", "FR"]))
    ok(rc == 3 and "SCULPT_REFUSED" in out and not (tmp / "o" / "views").exists()
       and not (tmp / "o" / "x_rgba.png").exists(), "sculpt run --mv FR: refused before the cut-out (exit 3)", out)
    smi = fake_smi(tmp / "s11c", ["NVIDIA GeForce RTX 2080 Ti, 11264, 11000, 550.1"])
    rc, out = sculpt("views", "a.png", str(tmp / "v" / "x"), "--text", "x", "--az", "0", "90", "180", "270", "45", "315",
                     env_extra={"IAMAR_NVIDIA_SMI": str(smi), "MVADAPTER": str(fake_clone(tmp / "mv_p2", True))})
    ok(rc == 2 and "SCULPT_NOT_READY views" in out and "6 views" in out, "sculpt views: 6 --az values judged as 6 views", out)


def run_stage(script, *args):
    r = subprocess.run([sys.executable, str(GPU / "stages" / script)] + list(args), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def test_stage_refusals(tmp):
    good = shape_mv.parse_map("front=000,left=090,back=180,right=270")
    ok(good == {"front": 0, "left": 90, "back": 180, "right": 270}, "shape_mv: default map parsed", good)
    ok(shape_mv.parse_map("front=000") == {"front": 0}, "shape_mv: front alone allowed (city: bad side views)")
    for bad in ("left=090", "front=000,front=090", "front=400", "top=000,front=000", "front=x"):
        try:
            shape_mv.parse_map(bad)
            ok(False, "shape_mv: map %r refused" % bad, "accepted")
        except ValueError:
            ok(True, "shape_mv: map %r refused" % bad)
    ok(paint_mv.parse_views("000,090,270") == [0, 90, 270], "paint_mv: views parsed")
    for bad in ("0,0", "0,360", "a"):
        try:
            paint_mv.parse_views(bad)
            ok(False, "paint_mv: views %r refused" % bad, "accepted")
        except ValueError:
            ok(True, "paint_mv: views %r refused" % bad)
    rc, out = run_stage("shape_mv.py", str(tmp / "nov" / "x"), str(tmp / "x.glb"), "--repo", str(tmp))
    ok(rc == 1 and "missing views" in out and "x_az000_rgba.png" in out, "shape_mv: missing views named, no GPU import", out)
    (tmp / "vv").mkdir(exist_ok=True)
    for d in (0, 90, 180, 270):
        (tmp / "vv" / ("x_az%03d_rgba.png" % d)).write_bytes(b"x")
    rc, out = run_stage("shape_mv.py", str(tmp / "vv" / "x"), str(tmp / "x.glb"), "--repo", str(tmp))
    ok(rc == 1 and "Hunyuan3D-2 clone" in out, "shape_mv: wrong --repo refused", out)
    rc, out = run_stage("mv_views.py", "a.png", str(tmp / "v2" / "x"), "--mvadapter", str(tmp))
    ok(rc == 1 and "MV-Adapter clone" in out, "mv_views: wrong clone refused", out)
    rc, out = run_stage("mv_views.py", "a.png", str(tmp / "v2" / "x"), "--mvadapter",
                        str(fake_clone(tmp / "mv_p3", True)), "--az", "90", "180")
    ok(rc == 1 and "including 0" in out, "mv_views: --az without 0 refused", out)
    rc, out = run_stage("paint_mv.py", str(tmp / "nocage.glb"), str(tmp / "vv" / "x"), str(tmp / "p.glb"), "--repo", str(tmp))
    ok(rc == 1 and "nocage.glb" in out, "paint_mv: missing cage named", out)
    rc, out = run_stage("paint_mv.py", str(tmp / "nocage.glb"), str(tmp / "vv" / "x"), str(tmp / "p.glb"), "--base", "red")
    ok(rc == 1 and "#rrggbb" in out, "paint_mv: bad --base refused", out)


def test_patch(tmp):
    git = shutil.which("git")
    if not git:
        return skip("patch applies", "git not found")
    d = tmp / "mvrepo"
    fake = d / gpu_check.MV_PIPE
    fake.parent.mkdir(parents=True, exist_ok=True)
    src = ["x\n"] * 649 + ["\n", "        cross_attention_kwargs = {\n", '            "mv_scale": mv_scale,\n',
                           '            "ref_hidden_states": {k: v.clone() for k, v in ref_hidden_states.items()},\n',
                           '            "ref_scale": reference_conditioning_scale,\n',
                           '            "num_views": num_images_per_prompt,\n',
                           "            **(self.cross_attention_kwargs or {}),\n"] + ["y\n"] * 5
    with open(fake, "w", newline="\n") as fh:
        fh.write("".join(src))
    subprocess.run([git, "init", "-q", str(d)], check=True)
    ok(gpu_check.mv_patched(str(d)) is False, "patch: plain pipeline detected as unpatched")
    r = subprocess.run([git, "-C", str(d), "apply", str(GPU / "patches" / "mvadapter_11gb.patch")],
                       capture_output=True, text=True)
    ok(r.returncode == 0, "patch: git apply succeeds on the targeted lines", r.stderr)
    ok(gpu_check.mv_patched(str(d)) is True, "patch: detected as patched afterwards")


def test_cpu_stages(tmp):
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return skip("paint_fix / mv_recut / clean_concept", "numpy and Pillow not installed")
    # paint_fix: left half flat grey fill, right half saturated blue, an orange eye
    a = np.zeros((64, 64, 3), np.uint8)
    a[:, :32] = (150, 150, 150)
    a[:, 32:] = (40, 60, 160)
    a[28:36, 44:52] = (240, 160, 30)
    Image.fromarray(a).save(tmp / "alb.png")
    rc, out = run_stage("paint_fix.py", str(tmp / "alb.png"), "--base", "#355e4c", "--glow", str(tmp / "glow.png"),
                        "--out", str(tmp / "alb_fixed.png"))
    ok(rc == 0 and "PAINT_FIX_OK" in out, "paint_fix: runs", out)
    if rc == 0:
        f = np.asarray(Image.open(tmp / "alb_fixed.png")).astype(int)
        g = np.asarray(Image.open(tmp / "glow.png")).astype(int)
        grey_px, blue_px = f[32, 8], f[8, 56]
        ok(grey_px[1] > grey_px[0] and grey_px[1] > grey_px[2], "paint_fix: grey fill turned to the base green", grey_px)
        ok(abs(blue_px[2] - min(255, int(160 * 1.12))) <= 2, "paint_fix: painted colours lifted by --gain", blue_px)
        ok(g[32, 48] > 200 and g[8, 8] == 0 and g[8, 56] == 0, "paint_fix: glow mask on the orange eye only",
           (g[32, 48], g[8, 8], g[8, 56]))
    rc, out = run_stage("paint_fix.py", str(tmp / "alb.png"), "--base", "#12345")
    ok(rc == 2 and "#rrggbb" in out, "paint_fix: bad colour refused", out)
    try:
        import cv2  # noqa: F401
    except ImportError:
        return skip("mv_recut / clean_concept", "opencv-python not installed")
    # mv_recut: a clean cut-out (tall figure) and 4 grey views with a dark disc
    S = 256
    clean = np.zeros((200, 300, 4), np.uint8)
    clean[20:180, 120:180] = (200, 200, 200, 255)     # 60 x 160 figure off-centre
    Image.fromarray(clean, "RGBA").save(tmp / "clean.png")
    yy, xx = np.mgrid[:S, :S]
    for d in (0, 90, 180, 270):
        v = np.full((S, S, 3), 128, np.uint8)
        disc = (yy - 128) ** 2 + (xx - 128) ** 2 < 50 ** 2     # textured: flat panels are dropped
        v[disc] = np.dstack([60 + ((xx + yy) % 9) * 6, 70 + (xx % 5) * 5, 80 + (yy % 7) * 4])[disc]
        Image.fromarray(v).save(tmp / ("vw_az%03d.png" % d))
        Image.fromarray(np.dstack([v, np.zeros((S, S), np.uint8)]), "RGBA").save(tmp / ("vw_az%03d_rgba.png" % d))
    rc, out = run_stage("mv_recut.py", str(tmp / "vw"), str(tmp / "clean.png"), "--no-rembg")
    ok(rc == 0 and "RECUT_OK" in out, "mv_recut --no-rembg: runs", out)
    if rc == 0:
        a0 = np.asarray(Image.open(tmp / "vw_az000_rgba.png").getchannel("A")) > 127
        ys, xs = np.nonzero(a0)
        h = ys.max() - ys.min() + 1
        ok(abs(h - int(S * 0.9)) <= 6 and abs((ys.min() + ys.max()) / 2 - S / 2) <= 2 and abs((xs.min() + xs.max()) / 2 - S / 2) <= 2,
           "mv_recut: az 0 alpha framed like preprocess_image (longest side 0.9, centred)", (h, ys.min(), ys.max(), xs.min(), xs.max()))
        a90 = np.asarray(Image.open(tmp / "vw_az090_rgba.png").getchannel("A")) > 127
        share = a90.mean()
        ok(abs(share - np.pi * 50 ** 2 / S ** 2) < 0.01 and a90[128, 128] and not a90[5, 5],
           "mv_recut: az 90 cut from the flat grey (disc kept, grey dropped)", share)
        ok((tmp / "vw_az090_rgba_rembg.png").exists(), "mv_recut: rembg's original kept")
    # clean_concept: a picture with a figure, a frame and a plinth; the mask says all is subject
    pic = np.full((200, 200, 3), 230, np.uint8)
    pic[40:160, 80:120] = (90, 80, 70)       # figure
    pic[160:190, 60:140] = (120, 120, 120)   # plinth
    pic[0:10, :] = (10, 10, 10)              # frame
    Image.fromarray(pic).save(tmp / "busy.png")
    Image.fromarray(np.full((200, 200), 255, np.uint8)).save(tmp / "all.png")
    rc, out = run_stage("clean_concept.py", str(tmp / "busy.png"), str(tmp / "cc"), "--alpha", str(tmp / "all.png"),
                        "--poly", "70,30;130,30;130,195;70,195", "--cut-y", "160", "--margin", "0.1")
    ok(rc == 0 and "CLEAN_OK" in out, "clean_concept --alpha: runs", out)
    if rc == 0:
        c = Image.open(tmp / "cc_clean.png")
        al = np.asarray(c.getchannel("A")) > 16
        ys, xs = np.nonzero(al)
        ok(c.size[0] == c.size[1] and abs(c.size[0] - int(129 * 1.2)) <= 2,
           "clean_concept: square crop round the figure with the margin", c.size)
        ok(ys.max() - ys.min() + 1 <= 130 and xs.max() - xs.min() + 1 <= 61,
           "clean_concept: frame outside the outline and plinth below --cut-y dropped", (ys.min(), ys.max(), xs.min(), xs.max()))
        ok((tmp / "cc_clean_grey.jpg").exists(), "clean_concept: grey preview written")
    rc, out = run_stage("clean_concept.py", str(tmp / "busy.png"), str(tmp / "cc2"), "--grabcut")
    ok(rc == 2 and "--grabcut needs --poly" in out, "clean_concept: --grabcut without --poly refused", out)


def test_gpu_smoke(tmp):
    if os.environ.get("IAMAR_GPU_SMOKE_MV") != "1":
        return skip("multiview GPU smoke run", "opt-in: IAMAR_GPU_SMOKE_MV=1")
    import numpy as np
    from PIL import Image
    yy, xx = np.mgrid[:512, :512]
    al = (((xx - 256) / 120.0) ** 2 + ((yy - 280) / 200.0) ** 2 < 1).astype(np.uint8) * 255
    rgb = np.dstack([140 + (xx % 40), 110 + (yy % 30), np.full_like(xx, 90)]).astype(np.uint8)
    Image.fromarray(np.dstack([rgb, al]), "RGBA").save(tmp / "urn.png")
    region = os.environ.get("IAMAR_REGION", "")
    rc, out = sculpt("views", str(tmp / "urn.png"), str(tmp / "mv" / "urn"), "--text", "a clay urn, game asset",
                     "--size", "512", "--steps", "10")
    ok(rc == 0 and "VIEWS_OK" in out, "GPU smoke: views at 512 px / 10 steps", out)
    if rc:
        return
    rc, out = sculpt("shape", "--mv", str(tmp / "mv" / "urn"), str(tmp / "urn_high.glb"), "--region", region,
                     "--octree", "128", "--steps", "10")
    ok(rc == 0 and "SHAPE_OK" in out, "GPU smoke: Hunyuan3D-2mv shape at octree 128 / 10 steps", out)
    if rc:
        return
    if not gpu_check.find_blender()[0]:
        return skip("GPU smoke: cage + game", "Blender 4.2+ not found")
    rc, out = sculpt("cage", str(tmp / "urn_high.glb"), str(tmp / "game"), "--height", "1.0", "--tris", "1200", "--name", "urn")
    ok(rc == 0, "GPU smoke: cage", out)
    rc, out = sculpt("game", str(tmp / "game" / "urn_cage.glb"), str(tmp / "game" / "urn_high.glb"), str(tmp / "final"),
                     "--budget", "1200", "--name", "urn")
    ok(rc == 0, "GPU smoke: game", out)


def main():
    keep = None
    if "--keep" in sys.argv:
        keep = Path(sys.argv[sys.argv.index("--keep") + 1])
        keep.mkdir(parents=True, exist_ok=True)
    tmp = keep or Path(tempfile.mkdtemp(prefix="gpu_mv_test_"))
    try:
        for t in (test_views_check, test_hy2_checks, test_sculpt_args, test_stage_refusals, test_patch,
                  test_cpu_stages, test_gpu_smoke):
            try:
                t(tmp)
            except Exception as e:     # one broken test must not hide the others
                ok(False, t.__name__, "%s: %s" % (type(e).__name__, e))
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    print("%d passed, %d failed, %d skipped" % (len(PASSES), len(FAILS), len(SKIPS)))
    print("GPU_MV_TEST_OK" if not FAILS else "GPU_MV_TEST_FAILED")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
