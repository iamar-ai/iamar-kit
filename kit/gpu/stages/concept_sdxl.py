#!/usr/bin/env python3
"""Text -> original concept pictures with SDXL base 1.0 (GPU tier, step 0; optional).

    python kit/gpu/stages/concept_sdxl.py out/concepts --prompt "..." [--count 4]
        [--seed 100] [--neg "..."] [--steps 40] [--cfg 7.0] [--size 1024] [--low-vram]

For when the user has no picture: SDXL base 1.0 (stabilityai/stable-diffusion-xl-base-1.0,
CreativeML Open RAIL++-M: outputs are the user's, the licence's use restrictions apply)
paints --count candidates, one per seed, from text only. Never feed commercial art in as a
reference: the city's first eagle head came from a commercial game picture and had to be
redone from an original (iamar-models tools/mesh3d/README.md). Pick one with the user, then
`sculpt.py cutout` (plain background) or stages/clean_concept.py (busy picture).

Prompt the way the city did: the subject, the view ("three-quarter side view facing
right"), "stylized hand-painted fantasy game art, clean silhouette, soft even studio light,
isolated on a plain light grey background, centered", and in --neg what must not appear
(text, watermark, frame, extra heads, scenery, cropped parts).

Loads only the fp16 weights (variant fp16; about 7 GB in HF_HOME). Model CPU offload by
default; --low-vram offloads layer by layer (the city ran it in about 1.5 GB of GPU memory
next to another service on an 11 GB card, slower). Writes concept_<seed>.png and
concepts.json, prints CONCEPT_OK.
Packaged from the iamar-models mesh archive (not public) tools/mesh3d/refimg.py (iamar city, eagle head v2).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pins  # noqa: E402  (kit/gpu/pins.json: the pinned upstream revisions)

NEG = ("text, watermark, logo, frame, border, multiple heads, background scenery, "
       "blurry, lowres, photo noise, cropped, cut off")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out_dir")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--neg", default=NEG)
    ap.add_argument("--count", type=int, default=4)
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--low-vram", action="store_true", help="sequential CPU offload (slow, about 1.5 GB)")
    a = ap.parse_args(argv)
    if not 1 <= a.count <= 32:
        ap.error("--count must be 1 to 32")
    if a.size % 64 or not 512 <= a.size <= 1536:
        ap.error("--size must be a multiple of 64 in [512, 1536]")
    import torch
    from diffusers import StableDiffusionXLPipeline
    if not torch.cuda.is_available():
        print("CONCEPT_FAIL no CUDA GPU visible to torch; use a picture the user has rights to instead",
              file=sys.stderr)
        return 1
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.time()
    pipe = StableDiffusionXLPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0",
                                                     revision=pins.hf("stabilityai/stable-diffusion-xl-base-1.0"),
                                                     torch_dtype=torch.float16, variant="fp16",
                                                     use_safetensors=True)
    if a.low_vram:
        pipe.enable_sequential_cpu_offload()
    else:
        pipe.enable_model_cpu_offload()
    done = []
    for i in range(a.count):
        s = a.seed + i
        img = pipe(prompt=a.prompt, negative_prompt=a.neg, num_inference_steps=a.steps, guidance_scale=a.cfg,
                   width=a.size, height=a.size, generator=torch.manual_seed(s)).images[0]
        p = os.path.join(a.out_dir, "concept_%d.png" % s)
        img.save(p)
        done.append(p)
        print("saved", p, flush=True)
    rep = {"tool": "sdxl base 1.0", "prompt": a.prompt, "neg": a.neg, "seeds": [a.seed + i for i in range(a.count)],
           "steps": a.steps, "cfg": a.cfg, "size": a.size, "files": done, "seconds": round(time.time() - t0, 1),
           "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
           "licence": "CreativeML Open RAIL++-M (output)"}
    with open(os.path.join(a.out_dir, "concepts.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print("CONCEPT_OK %s %d pictures" % (a.out_dir, len(done)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
