#!/usr/bin/env python3
"""Tests of the GPU tier (kit/gpu): hardware check, licence gate, cut-out, cage and game steps.

    python3 kit/tests/gpu/gpu_tier_test.py [--keep DIR]

Runs on any computer:
  - gpu_check.py against fake nvidia-smi programs (no GPU, an 8 GB card, a 24 GB card) and
    regions (none, DE, GB, KR, US): the shape step is refused or offered with its fallback
  - sculpt.py shape refuses without a region and in barred regions (exit 3)
  - stages/cutout.py on a small picture with its own alpha (needs numpy + Pillow; SKIPPED
    without them)
  - sculpt.py cage + game on a small generated "high" surface (a bumpy 20k-triangle
    sphere with a floating crumb and a base slab): crumb dropped, slab cut, real height,
    standing on 0, cage at the budget, then weld, closure, normal bake, AO and LODs
    (needs Blender 4.2+; SKIPPED without it). About 30 s on a laptop CPU.
Opt-in GPU smoke run (an NVIDIA GPU with 17+ GB and the Hunyuan3D-2.1 install):
  IAMAR_GPU_SMOKE=1 IAMAR_GPU_PYTHON=... HY3D21_REPO=... HF_HOME=... IAMAR_REGION=US \\
      python3 kit/tests/gpu/gpu_tier_test.py
  runs `sculpt.py run` on a generated picture at octree 128 / 10 steps (about 2 minutes,
  most of it loading the weights).
Prints GPU_TIER_TEST_OK and exits 0 when nothing failed.
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
sys.dont_write_bytecode = True
import gpu_check  # noqa: E402
import pins  # noqa: E402

FAILS, PASSES, SKIPS = [], [], []


def ok(cond, what, detail=""):
    (PASSES if cond else FAILS).append(what + ("" if cond else ": " + detail))
    print(("PASS " if cond else "FAIL ") + what + ("" if cond else "\n     " + detail[:1500]))


def skip(what, why):
    SKIPS.append(what)
    print("SKIPPED %s (%s)" % (what, why))


SMI_NAME = "nvidia-smi.cmd" if os.name == "nt" else "nvidia-smi"   # a .cmd runs without a /bin/sh


def fake_smi(d, line):
    """A directory holding an nvidia-smi that prints `line` (None: a directory without one)."""
    d.mkdir(parents=True, exist_ok=True)
    if line is not None:
        p = d / SMI_NAME
        p.write_text(("@echo %s\r\n" % line) if os.name == "nt" else "#!/bin/sh\necho '%s'\n" % line)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return d


def check_json(tmp, smi_dir, *args, cvd=None):
    env = dict(os.environ)
    env.pop("CUDA_VISIBLE_DEVICES", None)
    if cvd is not None:
        env["CUDA_VISIBLE_DEVICES"] = cvd
    env["IAMAR_NVIDIA_SMI"] = str(smi_dir / SMI_NAME)   # missing file = no GPU
    env.pop("IAMAR_REGION", None)
    r = subprocess.run([sys.executable, str(GPU / "gpu_check.py"), "--stage", "shape", "--json",
                        "--python", sys.executable, "--hf-home", str(tmp / "hf")] + list(args),
                       capture_output=True, text=True, env=env)
    try:
        return r.returncode, json.loads(r.stdout)
    except ValueError:
        return r.returncode, {"_raw": r.stdout + r.stderr}


def test_check(tmp):
    none = fake_smi(tmp / "smi_none", None)
    small = fake_smi(tmp / "smi_8", "NVIDIA GeForce RTX 3070, 8192, 7900, 550.1")
    big = fake_smi(tmp / "smi_24", "NVIDIA RTX A5000, 24564, 23800, 550.1")
    mid = fake_smi(tmp / "smi_18", "NVIDIA Test 18G, 18432, 18000, 550.1")
    busy = fake_smi(tmp / "smi_busy", "NVIDIA RTX A5000, 24564, 9000, 550.1")
    two = fake_smi(tmp / "smi_two", "NVIDIA GeForce RTX 3060, 12288, 12000, 550.1\nNVIDIA RTX A5000, 24564, 23800, 550.1")
    rc, j = check_json(tmp, none, "--region", "US")
    why = j.get("steps", {}).get("shape", {}).get("why", "")
    ok(rc == 2 and "no NVIDIA GPU" in why, "check: no GPU -> shape NOT_READY", json.dumps(j)[:600])
    ok(bool(j.get("steps", {}).get("shape", {}).get("fallback")), "check: NOT_READY names a fallback")
    rc, j = check_json(tmp, small, "--region", "US")
    why = j.get("steps", {}).get("shape", {}).get("why", "")
    ok(rc == 2 and "17.0 GB" in why and "8.0 GB" in why, "check: 8 GB card -> too small (17.0 GB measured)", why)
    rc, j = check_json(tmp, big, "--region", "US")
    why = j.get("steps", {}).get("shape", {}).get("why", "")
    ok("GPU" not in why.split("torch")[0] and "region" not in why, "check: 24 GB card + US -> no GPU or region objection", why)
    rc, j = check_json(tmp, mid, "--region", "US")
    notes = " ".join(j.get("steps", {}).get("shape", {}).get("notes", []))
    ok("untested" in notes, "check: 18 GB card -> fits but flagged untested", notes)
    rc, j = check_json(tmp, busy, "--region", "US")
    why = j.get("steps", {}).get("shape", {}).get("why", "")
    ok(rc == 2 and "free" in why, "check: 24 GB card with 8.8 GB free -> NOT_READY (stop other GPU work)", why)
    rc, j = check_json(tmp, two, "--region", "US")
    why = j.get("steps", {}).get("shape", {}).get("why", "")
    ok("RTX 3060" in why and "12.0 GB" in why, "check: judges cuda:0 (the 12 GB card), not the largest", why)
    rc, j = check_json(tmp, two, "--region", "US", cvd="1")
    why = j.get("steps", {}).get("shape", {}).get("why", "")
    ok("GB" not in why.split("torch")[0], "check: CUDA_VISIBLE_DEVICES=1 picks the A5000", why)
    rc, j = check_json(tmp, two, "--region", "US", cvd="")
    why = j.get("steps", {}).get("shape", {}).get("why", "")
    ok("hides every GPU" in why, "check: CUDA_VISIBLE_DEVICES empty -> no GPU", why)
    for cc in ("EU", "DEU", "Germany", "U5"):
        rc, j = check_json(tmp, big, "--region", cc)
        why = j.get("steps", {}).get("shape", {}).get("why", "")
        ok(rc == 2 and ("not a two-letter" in why or "excludes" in why), "check: region %r refused" % cc, why)
    for cc in ("DE", "GB", "KR", "fr"):
        rc, j = check_json(tmp, big, "--region", cc)
        why = j.get("steps", {}).get("shape", {}).get("why", "")
        ok(rc == 2 and "excludes the EU, the UK and South Korea" in why, "check: region %s barred" % cc, why)
    rc, j = check_json(tmp, big)
    why = j.get("steps", {}).get("shape", {}).get("why", "")
    ok(rc == 2 and "region unknown" in why, "check: no region -> ask the user", why)
    rc, j = check_json(tmp, big, "--region", "US")
    sh = j.get("steps", {}).get("shape", {})
    notes = " ".join(sh.get("notes", [])) + " " + sh.get("why", "")
    # a roomy disk gets a download note, a small /tmp a "not cached and only N GB free" reason
    ok("downloads 7.5 GB" in notes or "weights not cached and only" in notes,
       "check: weights not cached -> download note or disk reason", notes)
    snap = tmp / "hf" / "hub" / "models--tencent--Hunyuan3D-2.1" / "snapshots" / pins.hf("tencent/Hunyuan3D-2.1")
    for d in ("hunyuan3d-dit-v2-1", "hunyuan3d-vae-v2-1"):
        (snap / d).mkdir(parents=True, exist_ok=True)
    rc, j = check_json(tmp, big, "--region", "US")
    notes = " ".join(j.get("steps", {}).get("shape", {}).get("notes", []))
    ok("weights cached" not in notes, "check: empty weight folders are not 'cached'", notes)
    for d in ("hunyuan3d-dit-v2-1", "hunyuan3d-vae-v2-1"):
        (snap / d / "config.yaml").write_text("model: x\n")
        with open(snap / d / "model.fp16.ckpt", "wb") as f:   # sparse 120 MB
            f.truncate(120_000_000)
    rc, j = check_json(tmp, big, "--region", "US")
    notes = " ".join(j.get("steps", {}).get("shape", {}).get("notes", []))
    ok("weights cached" in notes, "check: cached weights found in HF_HOME", notes)
    shutil.rmtree(tmp / "hf")


def test_gate(tmp):
    for args, what in (([], "no region"), (["--region", "KR"], "KR"), (["--region", "it"], "IT")):
        env = dict(os.environ)
        env.pop("IAMAR_REGION", None)
        r = subprocess.run([sys.executable, str(GPU / "sculpt.py"), "shape", "in.png", str(tmp / "o.glb")] + args,
                           capture_output=True, text=True, env=env)
        ok(r.returncode == 3 and "SCULPT_REFUSED" in r.stderr, "sculpt shape refused: " + what, r.stdout + r.stderr)
    ok(not (tmp / "o.glb").exists(), "sculpt shape: nothing written when refused")
    r = subprocess.run([sys.executable, str(GPU / "sculpt.py"), "run", "in.png", str(tmp / "r"), "--height", "1",
                        "--budget", "100", "--region", "US", "--cpuu"], capture_output=True, text=True)
    ok(r.returncode == 2 and "unknown options" in r.stderr, "sculpt run: unknown option rejected", r.stderr)
    for bad, what in ((["--name", "../x"], "path name"), (["--height", "0"], "zero height"),
                      (["--height", "nan"], "nan height"), (["--budget", "0"], "zero budget"),
                      (["--cut-below", "1"], "cut-below 1")):
        args = {"--height": "1", "--budget": "100"}
        r = subprocess.run([sys.executable, str(GPU / "sculpt.py"), "run", "in.png", str(tmp / "r"), "--region", "US"]
                           + [x for k, v in args.items() if k not in bad for x in (k, v)] + bad,
                           capture_output=True, text=True)
        ok(r.returncode == 2 and not (tmp / "r").exists(), "sculpt run: %s rejected before any step" % what, r.stdout + r.stderr)


def test_cutout(tmp):
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        skip("cutout own alpha", "numpy/Pillow not in this Python")
        return
    a = np.zeros((300, 200, 4), np.uint8)
    a[50:250, 60:140] = (150, 140, 130, 255)     # subject
    a[230:300, 20:180] = (90, 90, 90, 255)       # a plinth from row 230
    Image.fromarray(a).save(tmp / "c.png")
    r = subprocess.run([sys.executable, str(GPU / "stages" / "cutout.py"), str(tmp / "c.png"), str(tmp / "c_rgba.png"),
                        "--plinth-row", "230", "--size", "256", "--fill", "0.8"], capture_output=True, text=True)
    ok(r.returncode == 0 and "CUTOUT_OK" in r.stdout and "own alpha" in r.stdout, "cutout: own alpha kept, ok line", r.stdout + r.stderr)
    if r.returncode:
        return
    o = np.array(Image.open(tmp / "c_rgba.png"))
    ys, xs = np.where(o[..., 3] > 20)
    ok(o.shape[:2] == (256, 256), "cutout: square canvas of --size", str(o.shape))
    ok(abs((ys.max() - ys.min() + 1) - 0.8 * 256) <= 2, "cutout: subject's long side at --fill", str(ys.max() - ys.min() + 1))
    ok(abs((ys.min() + ys.max()) / 2 - 128) <= 2 and abs((xs.min() + xs.max()) / 2 - 128) <= 2, "cutout: subject centred")
    w = xs.max() - xs.min() + 1
    ok(w < 0.5 * 256, "cutout: plinth below --plinth-row removed (subject stays narrow)", "width %d" % w)


GEN_HIGH = r'''
import bpy, bmesh, sys, random
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
random.seed(1)
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, radius=0.5, ring_count=80, location=(0, 0, 0.15))
s = bpy.context.active_object
s.scale = (0.6, 0.6, 1.0)
for v in s.data.vertices:
    v.co *= 1.0 + 0.03 * random.random()
bpy.ops.object.transform_apply(scale=True)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.45))     # base slab, bottom 10 %
b = bpy.context.active_object
b.scale = (0.9, 0.9, 0.1)
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.subdivide(number_cuts=20); bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.02, location=(0.7, 0, 0.3))  # crumb
for o in bpy.data.objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = s
bpy.ops.object.join()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_yup=True)
print("GEN_OK", sum(len(p.vertices) - 2 for p in s.data.polygons))
'''


def test_cage_game(tmp):
    path, ver = gpu_check.find_blender()
    if not path or ver[:2] < gpu_check.BLENDER_MIN:
        skip("cage + game", "Blender 4.2+ not found")
        return
    (tmp / "gen.py").write_text(GEN_HIGH)
    r = subprocess.run([path, "-b", "--factory-startup", "--python", str(tmp / "gen.py"), "--", str(tmp / "t_high.glb")],
                       capture_output=True, text=True)
    ok(r.returncode == 0 and "GEN_OK" in r.stdout, "generated test high surface", r.stdout[-800:] + r.stderr[-800:])
    if r.returncode:
        return
    r = subprocess.run([sys.executable, str(GPU / "sculpt.py"), "cage", str(tmp / "t_high.glb"), str(tmp / "game"),
                        "--height", "2.0", "--tris", "2000", "--cut-below", "0.12", "--name", "t"],
                       capture_output=True, text=True)
    ok(r.returncode == 0 and "CAGE_OK" in r.stdout, "sculpt cage: ok line", r.stdout + r.stderr)
    if r.returncode:
        return
    j = json.loads((tmp / "game" / "t_cage.json").read_text())
    ok(j["parts"] >= 3 and j["faces_dropped"] > 0, "cage: floating crumb dropped", json.dumps(j))
    ok(1900 <= j["tris_cage"] <= 2000, "cage: cage at the --tris budget", str(j["tris_cage"]))
    ok(abs(j["size_m"][1] - 2.0) < 0.01, "cage: scaled to --height", str(j["size_m"]))
    ok(j["size_m"][0] < 1.3, "cage: base slab below --cut-below removed (width of the body, not the slab)",
       str(j["size_m"]))
    import struct

    def bounds(p):
        d = p.read_bytes()
        n = struct.unpack("<I", d[12:16])[0]
        g = json.loads(d[20:20 + n])
        acc = g["accessors"][g["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
        return acc["min"], acc["max"], g
    mn, mx, g = bounds(tmp / "game" / "t_cage.glb")
    ok(abs(mn[1]) < 0.01, "cage: stands on y=0", str(mn))
    ok(abs(mn[0] + mx[0]) < 0.1 and abs(mn[2] + mx[2]) < 0.1, "cage: footprint centred on x/z", "%s %s" % (mn, mx))
    ok("TEXCOORD_0" in g["meshes"][0]["primitives"][0]["attributes"], "cage: has UVs for the bake")
    hm, hx, _ = bounds(tmp / "game" / "t_high.glb")
    ok(all(abs(a - b) < 0.05 for a, b in zip(hm + hx, mn + mx)), "cage: high and cage share place and scale",
       "%s %s / %s %s" % (hm, hx, mn, mx))
    r = subprocess.run([sys.executable, str(GPU / "sculpt.py"), "game", str(tmp / "game" / "t_cage.glb"),
                        str(tmp / "game" / "t_high.glb"), str(tmp / "final"), "--budget", "2000", "--name", "t",
                        "--normal-size", "256", "--cpu"], capture_output=True, text=True)
    ok(r.returncode == 0 and "PIPELINE_OK" in r.stdout, "sculpt game: asset pipeline ok", r.stdout + r.stderr)
    if r.returncode:
        return
    pj = json.loads((tmp / "final" / "pipeline.json").read_text())
    steps = {s["step"]: s["ok"] for s in pj["steps"]}
    ok(steps.get("normals") and steps.get("closure") and steps.get("light"), "game: closure, normal bake and AO ran", json.dumps(steps))
    ok(pj["triangles_per_lod"][0] <= 2000 and len(pj["triangles_per_lod"]) >= 3, "game: LOD0 within budget plus LODs",
       str(pj["triangles_per_lod"]))
    _, _, g = bounds(tmp / "final" / "t.glb")
    ok("normalTexture" in g["materials"][0], "game: normal map wired into the material")


GEN_PIC = r'''
from PIL import Image, ImageDraw
import sys
im = Image.new("RGB", (512, 512), (235, 235, 232)); d = ImageDraw.Draw(im)
d.rectangle((206, 420, 306, 450), fill=(120, 118, 112))
d.polygon([(236, 420), (276, 420), (300, 380), (330, 300), (320, 230), (286, 200), (226, 200), (192, 230), (182, 300), (212, 380)], fill=(150, 146, 138))
d.rectangle((232, 170, 280, 200), fill=(140, 136, 128))
im.save(sys.argv[1])
'''


def test_pins(tmp):
    """Job 3914: every upstream clone and model the GPU tier uses is pinned, and a drifted one is refused."""
    import re
    bad = []
    for f in GPU.rglob("*.py"):
        if f.name == "pins.py":
            continue
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r"(from_pretrained|snapshot_download|load_custom_adapter)\(((?:[^()]|\([^()]*\))*)\)", src):
            if "pins." not in m.group(2) and "revision" not in m.group(2):
                bad.append("%s: %s(%s" % (f.name, m.group(1), m.group(2)[:50]))
    ok(not bad, "every from_pretrained / snapshot_download / load_custom_adapter in kit/gpu passes a pinned revision", "; ".join(bad))
    readme = (GPU / "README.md").read_text(encoding="utf-8") + (GPU / "statue" / "README.md").read_text(encoding="utf-8")
    for name, g in pins.PINS["git"].items():
        ok(g["sha"] in readme, "README install steps check out the pinned %s commit" % name, g["sha"])
    for repo in ("tencent/Hunyuan3D-2.1", "infinith/UltraShape"):
        ok(pins.hf(repo) in readme, "README downloads the pinned %s revision" % repo, pins.hf(repo))
    ok("weights_only=True" in (GPU / "statue" / "statue.py").read_text(encoding="utf-8"),
       "the UltraShape patch loads the checkpoint with weights_only=True")
    clone = tmp / "pin_clone"
    (clone / ".git").mkdir(parents=True, exist_ok=True)
    want = pins.git_sha("Hunyuan3D-2.1")
    (clone / ".git" / "HEAD").write_text("0" * 40 + "\n")
    ok("pinned" in (pins.clone_problem(str(clone), "Hunyuan3D-2.1") or ""), "a clone at another commit is refused")
    (clone / ".git" / "HEAD").write_text(want + "\n")
    ok(pins.clone_problem(str(clone), "Hunyuan3D-2.1") is None, "a clone at the pinned commit passes")
    (clone / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (clone / ".git" / "refs" / "heads").mkdir(parents=True, exist_ok=True)
    (clone / ".git" / "refs" / "heads" / "main").write_text(want + "\n")
    ok(pins.clone_problem(str(clone), "Hunyuan3D-2.1") is None, "a branch ref at the pinned commit passes")
    home = tmp / "hf_pin"
    snaps = {}
    for rev in ("f" * 40, pins.hf("tencent/Hunyuan3D-2mv")):
        d = home / "hub" / "models--tencent--Hunyuan3D-2mv" / "snapshots" / rev / "hunyuan3d-dit-v2-mv"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.yaml").write_text("x")
        with open(d / "model.safetensors", "wb") as fh:
            fh.truncate(100_000_000)
        snaps[rev] = gpu_check.weights_cached(str(home), "tencent/Hunyuan3D-2mv", ["hunyuan3d-dit-v2-mv"])
    ok(snaps["f" * 40] is None, "weights cached only at another revision do not count")
    ok((snaps[pins.hf("tencent/Hunyuan3D-2mv")] or "").endswith(pins.hf("tencent/Hunyuan3D-2mv")),
       "weights cached at the pinned revision count")
    ck = tmp / "ckpt.pt"
    ck.write_bytes(b"x" * 10)
    ok("pinned" in (pins.file_problem(str(ck), "infinith/UltraShape/ultrashape_v1.pt") or ""),
       "a checkpoint of the wrong size is refused")


def test_smoke(tmp):
    if os.environ.get("IAMAR_GPU_SMOKE") != "1":
        skip("GPU smoke run", "opt-in: IAMAR_GPU_SMOKE=1")
        return
    py = os.environ.get("IAMAR_GPU_PYTHON") or sys.executable
    (tmp / "pic.py").write_text(GEN_PIC)
    subprocess.run([py, str(tmp / "pic.py"), str(tmp / "urn.png")], check=True)
    r = subprocess.run([sys.executable, str(GPU / "sculpt.py"), "run", str(tmp / "urn.png"), str(tmp / "smoke"),
                        "--height", "1.2", "--budget", "1200", "--plinth-row", "421", "--octree", "128", "--steps", "10"]
                       + (["--mem-cap", os.environ["IAMAR_GPU_MEMCAP"]] if os.environ.get("IAMAR_GPU_MEMCAP") else []),
                       capture_output=True, text=True)
    ok(r.returncode == 0 and "SCULPT_OK" in r.stdout, "GPU smoke: sculpt run end to end", r.stdout[-2000:] + r.stderr[-2000:])
    if r.returncode == 0:
        rep = json.loads((tmp / "smoke" / "run.json").read_text())
        print("     " + " | ".join("%s %ss" % (s["step"], s["seconds"]) for s in rep["steps"]),
              "LODs", rep.get("triangles_per_lod"))


def main():
    keep = None
    if "--keep" in sys.argv:
        keep = Path(sys.argv[sys.argv.index("--keep") + 1]).resolve()
        keep.mkdir(parents=True, exist_ok=True)
    tmp = keep or Path(tempfile.mkdtemp(prefix="gpu_tier_test_"))
    try:
        test_check(tmp)
        test_gate(tmp)
        test_cutout(tmp)
        test_cage_game(tmp)
        test_pins(tmp)
        test_smoke(tmp)
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    print("%d passed, %d failed, %d skipped" % (len(PASSES), len(FAILS), len(SKIPS)))
    if FAILS:
        print("GPU_TIER_TEST_FAILED")
        return 1
    print("GPU_TIER_TEST_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
