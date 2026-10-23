#!/usr/bin/env python3
"""RGBA cut-out -> high-poly shape with Tencent Hunyuan3D-2.1 (GPU tier, step 2).

    python kit/gpu/stages/shape_hy21.py cutout.png out_high.glb --repo ~/Hunyuan3D-2.1
        [--octree 380] [--steps 50] [--seed 0] [--chunks 20000] [--max-faces N]

Needs an NVIDIA GPU (CUDA) and the Python environment of the Hunyuan3D-2.1 install
(kit/gpu/README.md "Install"). --repo is the git clone of Tencent-Hunyuan/Hunyuan3D-2.1 (its
hy3dshape package is used; env HY3D21_REPO also works). The weights (tencent/Hunyuan3D-2.1,
the dit and vae folders, 7.5 GB) load from the Hugging Face cache (HF_HOME) and download
there on first use. They are never copied into the kit or a world.

Octree 380 and 50 steps are the city's statue settings (shape in 1-3 minutes on an RTX
A5000); octree 256 and 30 steps give a quick draft. The output is the raw generator surface
(hundreds of thousands of faces): it is the HIGH model for the normal bake, never a game
mesh (next step: `sculpt.py cage`). --max-faces thins it first with the pipeline's own
face reducer when a later step runs short of memory.

LICENCE: Tencent Hunyuan 3D 2.1 Community License. Not licensed in the EU, the UK or South
Korea; a product above 1 million monthly active users needs a licence from Tencent;
outputs must not be used to improve other AI models. `sculpt.py` asks for the region before
it runs this step.

Writes out_high.glb and out_high.json (seconds, faces, peak GPU and RAM). Prints SHAPE_OK.
Packaged from the iamar-models mesh archive (not public) tools/mesh3d/statue_v3/gen21.py (iamar city statues).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pins  # noqa: E402  (kit/gpu/pins.json: the pinned upstream revisions)

try:
    import resource   # POSIX only; absent on Windows
except ImportError:
    resource = None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", help="RGBA cut-out (kit/gpu/stages/cutout.py)")
    ap.add_argument("out", help="output .glb")
    ap.add_argument("--repo", default=os.environ.get("HY3D21_REPO"), help="Hunyuan3D-2.1 clone")
    ap.add_argument("--octree", type=int, default=380)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--chunks", type=int, default=20000)
    ap.add_argument("--max-faces", type=int, default=0, help="reduce the raw surface to this many faces")
    a = ap.parse_args(argv)
    if not a.repo or not os.path.isdir(os.path.join(a.repo, "hy3dshape")):
        print("SHAPE_FAIL --repo (or HY3D21_REPO) must be the Hunyuan3D-2.1 clone (has hy3dshape/)", file=sys.stderr)
        return 1
    sys.path.insert(0, os.path.join(os.path.abspath(a.repo), "hy3dshape"))

    import torch
    from PIL import Image
    if not torch.cuda.is_available():
        print("SHAPE_FAIL no CUDA GPU visible to torch (see kit/gpu/gpu_check.py)", file=sys.stderr)
        return 1
    from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline

    t0 = time.time()
    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        pins.snapshot("tencent/Hunyuan3D-2.1", ["hunyuan3d-dit-v2-1/*", "hunyuan3d-vae-v2-1/*"]))
    load_s = time.time() - t0
    img = Image.open(a.src)
    if img.mode != "RGBA":
        from hy3dshape.rembg import BackgroundRemover
        img = BackgroundRemover()(img.convert("RGB"))
    t1 = time.time()
    mesh = pipe(image=img, num_inference_steps=a.steps, octree_resolution=a.octree,
                num_chunks=a.chunks, generator=torch.manual_seed(a.seed))[0]
    sample_s = time.time() - t1
    faces_raw = len(mesh.faces)
    if a.max_faces and faces_raw > a.max_faces:
        from hy3dshape.postprocessors import FaceReducer
        mesh = FaceReducer()(mesh, max_facenum=a.max_faces)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    mesh.export(a.out)
    rep = {
        "tool": "hunyuan3d-2.1 shape", "src": a.src, "out": a.out,
        "octree": a.octree, "steps": a.steps, "seed": a.seed,
        "faces_raw": faces_raw, "faces": len(mesh.faces), "vertices": len(mesh.vertices),
        "load_s": round(load_s, 1), "sample_s": round(sample_s, 1),
        "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
        "peak_ram_gb": (round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2)
                        if resource else None),
        "gpu": torch.cuda.get_device_name(0),
    }
    with open(os.path.splitext(a.out)[0] + ".json", "w") as f:
        json.dump(rep, f, indent=1)
    print("SHAPE_OK %s faces %d sample %.0fs load %.0fs peak GPU %.1f GB RAM %s GB" % (
        a.out, rep["faces"], sample_s, load_s, rep["peak_gpu_gb"],
        "%.1f" % rep["peak_ram_gb"] if rep["peak_ram_gb"] is not None else "n/a"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
