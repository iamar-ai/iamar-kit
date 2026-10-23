#!/usr/bin/env python3
"""Several views -> high-poly shape with Tencent Hunyuan3D-2mv (GPU tier, multiview step 2).

    python kit/gpu/stages/shape_mv.py out/views/x out/x_high.glb --repo ~/mv/Hunyuan3D-2
        [--map front=000,left=090,back=180,right=270] [--octree 380] [--steps 50]
        [--seed 1234] [--chunks 20000] [--max-faces 0]

Reads P_az<deg>_rgba.png for the views prefix P (mv_views.py, then mv_recut.py for pale
figures). Hunyuan3D-2mv wants front, left, back, right = the picture, the picture turned 90
degrees clockwise seen from above (az 090), the back (180), az 270; --map picks which view is
which and may leave some out (`--map front=000` shapes from the picture alone, the city's
answer when the generated side views were wrong: wings turned into a cloak).

--repo is the git clone of Tencent-Hunyuan/Hunyuan3D-2 (its hy3dgen package; env HY3D2_REPO).
The weights (tencent/Hunyuan3D-2mv, folder hunyuan3d-dit-v2-mv, the fp16 checkpoint) load
from the Hugging Face cache (HF_HOME) and download there on first use; never copied into
the kit or a world. Floaters and degenerate faces are removed; --max-faces thins the
surface (the city used 80000 for heads). The output is the HIGH model for the normal bake,
never a game mesh: next step `sculpt.py cage`.

Measured in the iamar city (RTX 2080 Ti 11 GB, 2026-10-14, fp16): octree 380 / 50 steps
about 3 minutes, about 10 with the first load; it fits 11 GB.

LICENCE: Tencent Hunyuan 3D 2.0 Community License. Not licensed in the EU, the UK or South
Korea; above 1 million monthly active users a licence from Tencent is needed; outputs must
not be used to improve other AI models. `sculpt.py` asks for the region before this step.

Writes the .glb, <out>.json (seconds, faces, peak GPU) and <out>_front.png (the front view,
for the cage step's records). Prints SHAPE_OK.
Packaged from the iamar-models mesh archive (not public) tools/mesh3d/head_mv.py (iamar city, an internal task).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pins  # noqa: E402  (kit/gpu/pins.json: the pinned upstream revisions)

SLOTS = ("front", "left", "back", "right")


def parse_map(spec):
    """'front=000,left=090' -> {'front': 0, 'left': 90}; raises ValueError on a bad spec."""
    out = {}
    for kv in spec.split(","):
        k, _, v = kv.strip().partition("=")
        if k not in SLOTS or not v.strip().isdigit() or not 0 <= int(v) < 360 or k in out:
            raise ValueError("--map %r: use front=DEG,left=DEG,back=DEG,right=DEG (front required)" % spec)
        out[k] = int(v)
    if "front" not in out:
        raise ValueError("--map %r: the front view is required" % spec)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("views", help="views prefix (P_az<deg>_rgba.png)")
    ap.add_argument("out", help="output .glb")
    ap.add_argument("--repo", default=os.environ.get("HY3D2_REPO"), help="Hunyuan3D-2 clone (env HY3D2_REPO)")
    ap.add_argument("--map", default="front=000,left=090,back=180,right=270")
    ap.add_argument("--octree", type=int, default=380)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--chunks", type=int, default=20000)
    ap.add_argument("--max-faces", type=int, default=0, help="reduce the surface to this many faces")
    a = ap.parse_args(argv)
    try:
        slots = parse_map(a.map)
    except ValueError as e:
        print("SHAPE_FAIL %s" % e, file=sys.stderr)
        return 1
    files = {k: "%s_az%03d_rgba.png" % (a.views, v) for k, v in slots.items()}
    miss = [f for f in files.values() if not os.path.isfile(f)]
    if miss:
        print("SHAPE_FAIL missing views: %s (mv_views.py writes them)" % ", ".join(miss), file=sys.stderr)
        return 1
    if not a.repo or not os.path.isdir(os.path.join(a.repo, "hy3dgen", "shapegen")):
        print("SHAPE_FAIL --repo (or HY3D2_REPO) must be the Hunyuan3D-2 clone (has hy3dgen/shapegen)", file=sys.stderr)
        return 1
    sys.path.insert(0, os.path.abspath(a.repo))

    import torch
    from PIL import Image
    if not torch.cuda.is_available():
        print("SHAPE_FAIL no CUDA GPU visible to torch (see kit/gpu/gpu_check.py --stage shape_mv)", file=sys.stderr)
        return 1
    from hy3dgen.shapegen import (DegenerateFaceRemover, FaceReducer, FloaterRemover,
                                  Hunyuan3DDiTFlowMatchingPipeline)

    imgs = {k: Image.open(f).convert("RGBA") for k, f in files.items()}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    stem = os.path.splitext(a.out)[0]
    imgs["front"].save(stem + "_front.png")
    t0 = time.time()
    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        pins.snapshot("tencent/Hunyuan3D-2mv", ["hunyuan3d-dit-v2-mv/*"]), subfolder="hunyuan3d-dit-v2-mv", variant="fp16")
    load_s = time.time() - t0
    t1 = time.time()
    mesh = pipe(image=imgs, num_inference_steps=a.steps, octree_resolution=a.octree, num_chunks=a.chunks,
                generator=torch.manual_seed(a.seed), output_type="trimesh")[0]
    sample_s = time.time() - t1
    faces_raw = len(mesh.faces)
    mesh = FloaterRemover()(mesh)
    mesh = DegenerateFaceRemover()(mesh)
    if a.max_faces and len(mesh.faces) > a.max_faces:
        mesh = FaceReducer()(mesh, max_facenum=a.max_faces)
    mesh.export(a.out)
    try:
        import resource
        ram = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    except ImportError:          # Windows
        ram = None
    rep = {"tool": "hunyuan3d-2mv shape", "views": files, "out": a.out, "octree": a.octree,
           "steps": a.steps, "seed": a.seed, "faces_raw": faces_raw, "faces": len(mesh.faces),
           "vertices": len(mesh.vertices), "load_s": round(load_s, 1), "sample_s": round(sample_s, 1),
           "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
           "peak_ram_gb": round(ram, 2) if ram else None, "gpu": torch.cuda.get_device_name(0)}
    with open(stem + ".json", "w") as f:
        json.dump(rep, f, indent=1)
    print("SHAPE_OK %s faces %d from %d views, sample %.0fs load %.0fs peak GPU %.1f GB" % (
        a.out, rep["faces"], len(files), sample_s, load_s, rep["peak_gpu_gb"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
