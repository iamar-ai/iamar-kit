#!/usr/bin/env python3
"""Tests of the statue v4 chain (kit/gpu/statue): refine check, licence gate, fp16 patch, and the chain end to end.

    python3 kit/tests/gpu_statue/statue_test.py [--keep DIR]

Runs on any computer:
  - statue.py check --stage refine against fake nvidia-smi programs (no GPU, a 16 GB card, a busy 24 GB card, a free
    24 GB card): refused with the fallback, or only the missing install is named
  - statue.py refine refuses without a region and in the EU, the UK and South Korea (exit 3)
  - the fp16 patch on a stand-in with the stock script's anchors (applied once, with the s.3b notice; refused when an
    anchor is missing); with ULTRASHAPE_REPO set, on the real stock script too
  - no hardcoded host paths in the shipped scripts
  - uv-search with a fake Python: FCYL* among the user's parameters, a failed radius skipped, all failed -> exit 1
  - the chain end to end on a generated 115k-triangle stand-in statue (robe, neck, head with a nose, staff, a ground
    puddle): prep (puddle cut, face oval tagged), joint thinning, split cage at its budgets, Cycles bake at 512 px,
    relight, dilate, seam blend, feet, qa_statue PASS; then a wrong face oval through --combo must FAIL the QA and
    stop (needs Blender 4.2+ and numpy scipy pillow trimesh pymeshlab xatlas in --python / IAMAR_STATUE_PYTHON;
    SKIPPED without them). About 70 s.
Opt-in GPU smoke run (NVIDIA 24 GB, the UltraShape install, a cut-out and a coarse mesh):
  IAMAR_STATUE_SMOKE=1 ULTRASHAPE_REPO=... ULTRASHAPE_CKPT=... IAMAR_STATUE_PYTHON=... IAMAR_REGION=US \\
  IAMAR_STATUE_IMAGE=x_rgba.png IAMAR_STATUE_COARSE=x_nobase.glb python3 kit/tests/gpu_statue/statue_test.py
Prints STATUE_TEST_OK and exits 0 when nothing failed.
"""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
ST = KIT / "gpu" / "statue"
sys.path.insert(0, str(ST))
sys.dont_write_bytecode = True
import statue  # noqa: E402
import gpu_check  # noqa: E402

FAILS, PASSES, SKIPS = [], [], []


def ok(cond, what, detail=""):
    (PASSES if cond else FAILS).append(what + ("" if cond else ": " + detail))
    print(("PASS " if cond else "FAIL ") + what + ("" if cond else "\n     " + detail[:1500]))


def skip(what, why):
    SKIPS.append(what)
    print("SKIPPED %s (%s)" % (what, why))


def fake_smi(d, line):
    """A directory holding an nvidia-smi that prints `line` (None: no nvidia-smi). Returns its path."""
    d.mkdir(parents=True, exist_ok=True)
    if line is None:
        return d / "nvidia-smi"
    if os.name == "nt":
        p = d / "nvidia-smi.cmd"
        p.write_text("@echo %s\r\n" % line)
    else:
        p = d / "nvidia-smi"
        p.write_text("#!/bin/sh\necho '%s'\n" % line)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def run_statue(args, env_add=None, drop=("IAMAR_REGION", "ULTRASHAPE_REPO", "ULTRASHAPE_CKPT", "CUDA_VISIBLE_DEVICES")):
    env = dict(os.environ)
    for k in drop:
        env.pop(k, None)
    env.update(env_add or {})
    return subprocess.run([sys.executable, str(ST / "statue.py")] + args, capture_output=True, text=True, env=env)


def test_check(tmp):
    us = tmp / "us" / "repo"
    (us / "ultrashape").mkdir(parents=True)
    (us / "scripts").mkdir()
    cases = [("no GPU", None, "no NVIDIA GPU"),
             ("16 GB card", "NVIDIA RTX A4000, 16376, 16000, 550.1", "the refine used about 19 GB"),
             ("busy 24 GB card", "NVIDIA RTX A5000, 24564, 9000, 550.1", "GPU memory free"),
             ("free 24 GB card", "NVIDIA RTX A5000, 24564, 24000, 550.1", None)]
    for name, line, expect in cases:
        smi = fake_smi(tmp / ("smi_" + re.sub(r"\W", "_", name)), line)
        r = run_statue(["check", "--stage", "refine", "--json", "--python", sys.executable, "--us-repo", str(us),
                        "--region", "US"], {"IAMAR_NVIDIA_SMI": str(smi)})
        try:
            res = json.loads(r.stdout)
            s = res["steps"]["refine"]
        except (ValueError, KeyError):
            ok(False, "check refine (%s) prints JSON" % name, r.stdout + r.stderr)
            continue
        ok(r.returncode == 2 and not s["ready"] and s["fallback"], "check refine (%s): not ready, fallback named" % name,
           json.dumps(s))
        if expect:
            ok(expect in s["why"], "check refine (%s) says %r" % (name, expect), s["why"])
        else:
            gpu_said = any(w in s["why"] for w in ("GPU", "19 GB"))
            ok(not gpu_said and "fp16 script missing" in s["why"] and "checkpoint" in s["why"],
               "check refine (free 24 GB card): GPU accepted, the missing patch and checkpoint named", s["why"])
    # the patch and a checkpoint make those reasons go away
    (us / "scripts" / "infer_fp16.py").write_text("# stand-in\n")
    ck = tmp / "us" / "checkpoints"
    ck.mkdir()
    import pins   # the checkpoint must have the pinned size (kit/gpu/pins.json); truncate leaves it sparse
    with open(ck / "ultrashape_v1.pt", "wb") as f:
        f.truncate(pins.PINS["files"]["infinith/UltraShape/ultrashape_v1.pt"]["size"])
    smi = fake_smi(tmp / "smi_ok", "NVIDIA RTX A5000, 24564, 24000, 550.1")
    r = run_statue(["check", "--stage", "refine", "--json", "--python", sys.executable, "--us-repo", str(us),
                    "--region", "US"], {"IAMAR_NVIDIA_SMI": str(smi)})
    s = json.loads(r.stdout)["steps"]["refine"]
    ok("fp16" not in s["why"] and "checkpoint" not in s["why"] and any("checkpoint:" in n for n in s["notes"]),
       "check refine finds the patched script and the checkpoint next to the clone", json.dumps(s))


def test_region(tmp):
    for region in (None, "DE", "GB", "KR", "EU", "Germany"):
        args = ["refine", "in.png", "in.glb", str(tmp / "o")] + (["--region", region] if region else [])
        r = run_statue(args)
        ok(r.returncode == 3 and "STATUE_REFUSED" in r.stderr and "FALLBACK" in r.stderr,
           "refine refused for region %s (exit 3, fallback named)" % region, "%d %s" % (r.returncode, r.stderr))


def test_patch(tmp):
    stock = ("import torch\n\ndef load_models(config_path, ckpt_path, device='cuda'):\n"
             + "".join(old for old, _ in statue.PATCH[:2])
             + "    \n    vae.load_state_dict(weights['vae'], strict=True)\n" + statue.PATCH[2][0]
             + "    \n    vae.eval().to(device)\n")
    out = statue.patch_text(stock.replace("\n", "\r\n"))
    ok(out.startswith(statue.NOTICE) and "s.3b" in out, "patch: the modified file carries the licence notice")
    ok(out.count("torch.set_default_dtype(torch.float16)") == 1 and "map_location='cuda', mmap=False" in out
       and "del weights" in out and "map_location='cpu'" not in out, "patch: fp16 GPU build, GPU checkpoint load, freed")
    try:
        compile(out, "infer_fp16.py", "exec")
        ok(True, "patch: the result is valid Python")
    except SyntaxError as e:
        ok(False, "patch: the result is valid Python", str(e))
    try:
        statue.patch_text(stock.replace("map_location='cpu'", "map_location=device"))
        ok(False, "patch refuses a changed upstream script")
    except ValueError as e:
        ok("anchor" in str(e), "patch refuses a changed upstream script", str(e))
    repo = tmp / "fake_us"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "infer_dit_refine.py").write_text(stock)
    r = run_statue(["patch", "--us-repo", str(repo)])
    ok(r.returncode == 0 and "PATCH_OK" in r.stdout and (repo / "scripts" / "infer_fp16.py").is_file(),
       "statue.py patch writes scripts/infer_fp16.py into the clone", r.stdout + r.stderr)
    real = os.environ.get("ULTRASHAPE_REPO")
    if real and os.path.isfile(os.path.join(real, "scripts", "infer_dit_refine.py")):
        try:
            statue.patch_text(open(os.path.join(real, "scripts", "infer_dit_refine.py"), encoding="utf-8").read())
            ok(True, "patch applies to the real stock script in ULTRASHAPE_REPO")
        except ValueError as e:
            ok(False, "patch applies to the real stock script in ULTRASHAPE_REPO", str(e))
    else:
        skip("patch on the real UltraShape script", "ULTRASHAPE_REPO not set")


def test_no_host_paths():
    bad = []
    for p in sorted(ST.rglob("*.py")):
        for i, l in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"/home/|mp_run|claude-citymap|code/oakhaven|C:\\\\Users|~/", l):
                bad.append("%s:%d %s" % (p.name, i, l.strip()[:100]))
    ok(not bad, "no hardcoded host paths or city install steps in kit/gpu/statue", "\n".join(bad))


def chain_python():
    py = os.environ.get("IAMAR_STATUE_PYTHON") or os.environ.get("IAMAR_GPU_PYTHON") or sys.executable
    mods, err = gpu_check.env_modules(py, list(statue.CHAIN_MODULES))
    if mods is None:
        return None, err
    miss = [m for m in statue.CHAIN_MODULES if not mods.get(m)]
    return (py, None) if not miss else (None, "missing " + ", ".join(miss) + " in " + py)


def test_chain(tmp):
    bl, ver = gpu_check.find_blender()
    if not bl or ver[:2] < gpu_check.BLENDER_MIN:
        return skip("chain end to end", "Blender 4.2+ not found (BLENDER=)")
    py, why = chain_python()
    if not py:
        return skip("chain end to end", why)
    sample = tmp / "sample.glb"
    r = subprocess.run([bl, "-b", "--factory-startup", "--python", str(HERE / "make_sample.py"), "--", str(sample)],
                       capture_output=True, text=True)
    ok(sample.is_file(), "stand-in statue generated", (r.stdout + r.stderr)[-800:])
    if not sample.is_file():
        return
    face = ["FCX=0.03", "FCZ=0.66", "FRXL=0.07", "FRXR=0.07", "FRZ=0.08", "CYLX=0.03", "CYLZ=0", "NECKX=0.03"]
    budgets = {"body": 1500, "hat_hair": 900, "face": 1200}
    common = ["--python", py, "--size", "512", "--nb", "1500", "--nh", "900", "--nf", "1200",
              "--nf-pre", "5000", "--nb-pre", "30000"]
    w = tmp / "w"
    r = run_statue(["chain", str(w), str(sample), "--name", "sample"] + common + face)
    out = r.stdout + r.stderr
    ok(r.returncode == 0 and "STATUE_OK" in out, "chain runs to STATUE_OK", out[-2500:])
    rep = json.loads((w / "run.json").read_text()) if (w / "run.json").is_file() else {}
    ok(rep.get("qa") == "ok", "qa_statue passes on the stand-in", json.dumps(rep.get("steps", []))[-1500:])
    prep = " ".join(sum((s["lines"] for s in rep.get("steps", []) if s["step"] == "prep"), []))
    m = re.search(r"removed (\d+) faces; head-material faces (\d+)", prep)
    ok(bool(m) and int(m.group(1)) > 5000 and int(m.group(2)) > 500,
       "prep cut the ground puddle and tagged the face oval", prep)
    tri = rep.get("triangles", {})
    total = tri.get("total", 0)
    ok(0 < total <= sum(budgets.values()) * 1.02, "game statue at its budget (%d tris <= %d)" % (total, sum(budgets.values())),
       json.dumps(tri))
    files = ["sample.gltf", "sample.bin", "sample_albedo.png", "sample_normal.png"]
    ok(all((w / "out" / f).is_file() for f in files), "out/ holds the glTF, its buffer, albedo and normal map",
       str(list((w / "out").iterdir()) if (w / "out").is_dir() else "no out/"))
    pl = rep.get("placement", {})
    ok(1.6 < pl.get("height", 0) < 1.8 and abs(pl.get("min_y", 9) + 0.93) < 0.02,
       "feet: figure height and sole level measured (the puddle gone)", json.dumps(pl))
    # a wrong face oval: QA must fail and the chain stop, reusing the prep (--combo, KEY=VAL right after the workdir)
    w2 = tmp / "w2"
    bad = [x for x in face if not x.startswith("FCZ=")] + ["FCZ=0.0"]
    r = run_statue(["chain", str(w2), "--combo", str(w / "combo.glb"), "--name", "sample"] + bad + common)
    out = r.stdout + r.stderr
    ok(r.returncode == 1 and "QA FAILED" in out and "STATUE_OK" not in out and "STEP prep" not in out,
       "a wrong face oval fails the QA and stops the chain (exit 1, prep reused)", out[-1500:])


def test_uv_search(tmp):
    """uv-search with a fake Python (no trimesh needed): FCYL* among the user's params must not crash, the try's own
    axis reaches the stages, a failed radius is skipped (not scored from the last cage), and all-failed writes nothing."""
    w = tmp / "uvs"
    w.mkdir(parents=True, exist_ok=True)
    (w / "pre.glb").write_bytes(b"")
    fake = tmp / "fakepy.py"
    # lowsplit3: fails for FCYLR 0.6, else writes uvtry_low.glb; qa_uv: score = |FCYLR - 0.9| (+ FCX check)
    fake.write_text(
        "import os, sys\n"
        "E = os.environ\n"
        "if sys.argv[1].endswith('lowsplit3.py'):\n"
        "    if E.get('ALLFAIL') == '1' or abs(float(E['FCYLR']) - 0.6) < 1e-9: sys.exit(1)\n"
        "    open('uvtry_low.glb', 'w').write(E['FCYLR'])\n"
        "else:\n"
        "    if not os.path.exists('uvtry_low.glb'): sys.exit(1)\n"
        "    print('UVQ %.4f fold 0 crushed 0' % (abs(float(open('uvtry_low.glb').read()) - 0.9) + (0 if E.get('FCX') == '0.1' else 5)))\n")
    wrap = tmp / ("fakepy.cmd" if os.name == "nt" else "fakepy.sh")
    if os.name == "nt":
        wrap.write_text('@"%s" "%s" %%*\r\n' % (sys.executable, fake))
    else:
        wrap.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, fake))
        wrap.chmod(wrap.stat().st_mode | stat.S_IEXEC)
    args = ["uv-search", str(w), "--python", str(wrap), "--radii", "0.3,0.6,0.9,1.5", "FCX=0.1", "FCYLX=7", "FCYLR=7"]
    r = run_statue(args)
    out = r.stdout + r.stderr
    best = (w / "best_axis.env").read_text() if (w / "best_axis.env").exists() else ""
    ok(r.returncode == 0 and "FCYLR=0.9" in best and "BEST 0.0000" in out,
       "uv-search: user FCYL* params do not crash, best radius 0.9 chosen, failed radius 0.6 skipped", out[-1500:])
    ok("FCYLR=0.600 UVQ failed" in out, "uv-search: a failed radius is reported, not scored from the previous cage", out[-1500:])
    (w / "best_axis.env").unlink(missing_ok=True)
    r = run_statue(args, {"ALLFAIL": "1"})
    ok(r.returncode == 1 and not (w / "best_axis.env").exists() and "no axis scored" in r.stderr,
       "uv-search: every radius failed -> exit 1, no best_axis.env", (r.stdout + r.stderr)[-1500:])


def test_smoke(tmp):
    if os.environ.get("IAMAR_STATUE_SMOKE") != "1":
        return skip("GPU smoke refine", "IAMAR_STATUE_SMOKE=1 not set")
    img, mesh = os.environ.get("IAMAR_STATUE_IMAGE"), os.environ.get("IAMAR_STATUE_COARSE")
    r = subprocess.run([sys.executable, str(ST / "statue.py"), "refine", img, mesh, str(tmp / "refine"), "--steps", "10"],
                       capture_output=True, text=True)
    ok(r.returncode == 0 and "REFINE_OK" in r.stdout, "GPU smoke: UltraShape refine", (r.stdout + r.stderr)[-2000:])


def main():
    keep = None
    if "--keep" in sys.argv:
        keep = Path(sys.argv[sys.argv.index("--keep") + 1])
        keep.mkdir(parents=True, exist_ok=True)
    tmp = keep or Path(tempfile.mkdtemp(prefix="statue_test_"))
    try:
        test_check(tmp)
        test_region(tmp)
        test_patch(tmp)
        test_no_host_paths()
        test_chain(tmp)
        test_uv_search(tmp)
        test_smoke(tmp)
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    print("%d passed, %d failed, %d skipped" % (len(PASSES), len(FAILS), len(SKIPS)))
    if FAILS:
        print("STATUE_TEST_FAILED")
        return 1
    print("STATUE_TEST_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
