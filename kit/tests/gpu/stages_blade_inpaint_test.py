#!/usr/bin/env python3
"""Tests of the GPU tier's two repair stages: inpaint (redraw one part of a concept) and blade
(give a sculpt back a thin blade it lost).

    python3 kit/tests/gpu/stages_blade_inpaint_test.py [--keep DIR]

Runs on any computer, no GPU needed, a few seconds:
  - stages/inpaint_part.py refuses bad numbers, missing files, a picture SDXL cannot take and an
    all-black mask, before any torch import (needs Pillow for the last two; SKIPPED without it)
  - sculpt.py inpaint checks the computer first (gpu_check --stage concept): no NVIDIA GPU -> exit 2
    with SCULPT_NOT_READY and a fallback, nothing generated
  - stages/add_blade.py refuses bad points and sizes before importing Blender's modules, and
    sizes the blade (no Blender): at least 2.5 % of the source's triangles, so the cage step's
    --min-part 0.02 never drops it; past MAX_SEGMENTS it refuses
  - with Blender 4.2+ (BLENDER=path or the usual places; else SKIPPED): sculpt.py blade on a
    generated cube adds the blade's triangles and writes a glb that Blender reads back
Prints BLADE_INPAINT_TEST_OK and exits 0 when nothing failed.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
GPU = KIT / "gpu"
sys.path.insert(0, str(GPU))
sys.dont_write_bytecode = True
import gpu_check  # noqa: E402

FAILS, PASSES, SKIPS = [], [], []


def ok(cond, what, detail=""):
    (PASSES if cond else FAILS).append(what + ("" if cond else ": " + detail))
    print(("PASS " if cond else "FAIL ") + what + ("" if cond else "\n     " + str(detail)[:1500]))


def skip(what, why):
    SKIPS.append(what)
    print("SKIPPED %s (%s)" % (what, why))


def run(args, env=None):
    r = subprocess.run([sys.executable] + [str(a) for a in args], capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_inpaint_args(tmp):
    st = GPU / "stages" / "inpaint_part.py"
    base = [st, tmp / "nope.png", tmp / "nope_mask.png", tmp / "out", "--prompt", "a staff"]
    rc, out = run(base + ["--count", "0"])
    ok(rc == 2 and "--count" in out, "inpaint: --count 0 refused", out)
    rc, out = run(base + ["--strength", "1.5"])
    ok(rc == 2 and "--strength" in out, "inpaint: --strength 1.5 refused", out)
    rc, out = run(base[:-2])
    ok(rc == 2 and "--prompt" in out, "inpaint: --prompt is required", out)
    rc, out = run(base)
    ok(rc == 1 and "INPAINT_FAIL no such file" in out, "inpaint: missing picture named", out)
    try:
        from PIL import Image
    except ImportError:
        return skip("inpaint picture and mask checks", "Pillow not installed")
    Image.new("RGB", (1001, 1001), (128, 128, 128)).save(tmp / "odd.png")
    Image.new("RGB", (512, 512), (128, 128, 128)).save(tmp / "c.png")
    Image.new("L", (64, 64), 0).save(tmp / "black.png")
    Image.new("L", (64, 64), 255).save(tmp / "white.png")
    rc, out = run([st, tmp / "odd.png", tmp / "white.png", tmp / "out", "--prompt", "x"])
    ok(rc == 1 and "multiple of 8" in out, "inpaint: 1001 px picture refused (SDXL needs multiples of 8)", out)
    rc, out = run([st, tmp / "c.png", tmp / "black.png", tmp / "out", "--prompt", "x"])
    ok(rc == 1 and "no white area" in out, "inpaint: all-black mask refused", out)
    ok(not (tmp / "out").exists(), "inpaint: nothing written by a refused run")


def test_inpaint_gate(tmp):
    env = dict(os.environ)
    env["IAMAR_NVIDIA_SMI"] = str(tmp / "nosmi" / ("nvidia-smi.cmd" if os.name == "nt" else "nvidia-smi"))
    env.pop("CUDA_VISIBLE_DEVICES", None)
    rc, out = run([GPU / "sculpt.py", "inpaint", tmp / "c.png", tmp / "white.png", tmp / "gated",
                   "--prompt", "x", "--python", sys.executable, "--hf-home", tmp / "hf"], env=env)
    ok(rc == 2 and "SCULPT_NOT_READY concept" in out and "FALLBACK" in out,
       "sculpt.py inpaint: no GPU -> gpu_check concept refuses with a fallback (exit 2)", out)
    ok(not (tmp / "gated").exists(), "sculpt.py inpaint: nothing generated when refused")


def test_blade_args(tmp):
    st = GPU / "stages" / "add_blade.py"
    rc, out = run([st, "a.glb", "b.glb", "--root=-0.1,0", "--tip=0,0,1"])
    ok(rc == 2 and "three numbers" in out, "blade: a two-number point refused", out)
    rc, out = run([st, "a.glb", "b.glb", "--root=0,0,1", "--tip=0,0,1"])
    ok(rc == 2 and "same point" in out, "blade: root == tip refused", out)
    rc, out = run([st, "a.glb", "b.glb", "--root=0,0,0", "--tip=0,0,1", "--width", "0"])
    ok(rc == 2 and "--width" in out, "blade: zero width refused", out)
    rc, out = run([st, "a.glb", "b.glb", "--root=0,0,0", "--tip=0,0,1", "--segments", "0"])
    ok(rc == 2 and "--segments" in out, "blade: zero segments refused", out)
    rc, out = run([st, "a.glb", "b.glb", "--tip=0,0,1"])
    ok(rc == 2 and "--root" in out, "blade: --root is required", out)


def test_blade_sizing():
    sys.path.insert(0, str(GPU / "stages"))
    import add_blade as B
    ok(B.blade_segments(240, 12) == 240, "blade sizing: a small mesh keeps --segments")
    ok(B.blade_tris(240) == 1922, "blade sizing: 240 segments are 1922 triangles")
    for src in (96_000, 100_000, 400_000, 1_500_000):
        n = B.blade_segments(240, src)
        ok(n is not None and n >= 240 and B.blade_tris(n) >= 0.025 * src
           and (n == 240 or B.blade_tris(n - 1) < 0.025 * src),
           "blade sizing: %d-triangle source -> %s segments, >= 2.5 %% and the fewest that reach it" % (src, n),
           (n, B.blade_tris(n or 0)))
    ok(B.blade_segments(240, 100_000) > 240, "blade sizing: a 100k raw Hunyuan mesh raises --segments")
    big = int((B.blade_tris(B.MAX_SEGMENTS) + 1) / 0.025) + 100
    ok(B.blade_segments(240, big) is None, "blade sizing: %d triangles is past MAX_SEGMENTS -> refused" % big)


def test_blade_blender(tmp):
    path, ver = gpu_check.find_blender()
    if not path or ver[:2] < gpu_check.BLENDER_MIN:
        return skip("blade on a generated cube", "Blender 4.2+ not found")
    src, dst = tmp / "cube.glb", tmp / "cube_blade.glb"
    mk = ("import bpy,sys; bpy.ops.wm.read_factory_settings(use_empty=True); "
          "bpy.ops.mesh.primitive_cube_add(size=1); "
          "bpy.ops.export_scene.gltf(filepath=sys.argv[-1], export_format='GLB')")
    r = subprocess.run([path, "-b", "--factory-startup", "--python-expr", mk, "--", str(src)],
                       capture_output=True, text=True)
    if not src.exists():
        return ok(False, "blade: Blender writes the test cube", r.stdout + r.stderr)
    env = dict(os.environ, BLENDER=path)
    segs = 40
    rc, out = run([GPU / "sculpt.py", "blade", src, dst, "--root=0,0,0.5", "--tip=-0.2,0,2.0",
                   "--segments", segs], env=env)
    ok(rc == 0 and "BLADE_OK" in out and dst.exists(), "sculpt.py blade: BLADE_OK and the glb written", out)
    # the cube is 12 triangles; the blade adds 4 sides x 2 triangles per segment and a 2-triangle cap
    want = 12 + segs * 8 + 2
    ok(("BLADE_OK %s %d" % (dst, want)) in out, "blade: %d triangles (cube 12 + blade %d)" % (want, want - 12), out)
    rd = ("import bpy,sys; bpy.ops.wm.read_factory_settings(use_empty=True); "
          "bpy.ops.import_scene.gltf(filepath=sys.argv[-1]); "
          "m=[o for o in bpy.data.objects if o.type=='MESH']; "
          "print('READ', len(m), sum(len(o.data.polygons) for o in m), "
          "round(max((o.matrix_world @ v.co).z for o in m for v in o.data.vertices), 3))")
    r = subprocess.run([path, "-b", "--factory-startup", "--python-expr", rd, "--", str(dst)],
                       capture_output=True, text=True)
    line = [l for l in r.stdout.splitlines() if l.startswith("READ ")]
    ok(line == ["READ 1 %d 2.0" % want], "blade: one mesh read back, reaching the tip (z 2.0)", r.stdout[-800:])


def main():
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    tmp = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="blade_inpaint_"))
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        test_inpaint_args(tmp)
        if (tmp / "c.png").exists():
            test_inpaint_gate(tmp)
        else:
            skip("sculpt.py inpaint gate", "Pillow not installed")
        test_blade_args(tmp)
        test_blade_sizing()
        test_blade_blender(tmp)
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    print("%d passed, %d failed, %d skipped" % (len(PASSES), len(FAILS), len(SKIPS)))
    if FAILS:
        return 1
    print("BLADE_INPAINT_TEST_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
