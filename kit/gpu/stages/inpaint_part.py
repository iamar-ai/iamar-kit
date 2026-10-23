#!/usr/bin/env python3
"""Repaint one part of a concept picture and keep the rest, with SDXL base 1.0 (GPU tier, step 0b; optional).

    python kit/gpu/stages/inpaint_part.py concept.png mask.png out/parts --prompt "..."
        [--count 4] [--seed 100] [--neg "..."] [--steps 40] [--cfg 8.0] [--strength 0.99] [--low-vram]

For a concept that is right except one part (the city's South Gate mage, 2026-10-13: concept
#7 kept, the staff redrawn). SDXL base 1.0 inpaints directly; no separate inpainting model.
The mask is a grey picture (resized to the concept): white is repainted, black kept. Draw it
over the part with a margin (the staff head, the shaft), paint black over what must not change
(the hand holding it), and feather it a few pixels so the seam blends. --strength 0.99 draws
the masked area new, guided by its surroundings; describe the part in the figure's own
material ("carved pale grey stone staff with a crystal head").

Weights: stabilityai/stable-diffusion-xl-base-1.0 (CreativeML Open RAIL++-M, not shipped
with the kit: the user downloads them into HF_HOME and accepts the licence; outputs are the
user's, the licence's use restrictions apply). Same weights and GPU need as concept_sdxl.py:
`sculpt.py inpaint` checks the computer first (gpu_check --stage concept). Model CPU offload
by default, --low-vram layer by layer (slow, about 1.5 GB of GPU memory).
Writes part_<seed>.png and parts.json, prints INPAINT_OK.
Packaged from the iamar-models mesh archive (not public) tools/mesh3d/inpaint_part.py (iamar city, South Gate mage).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pins  # noqa: E402  (kit/gpu/pins.json: the pinned upstream revisions)

NEG = "text, watermark, extra hands, extra arms, blurry, lowres"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("image")
    ap.add_argument("mask", help="white = repaint, black = keep (resized to the image)")
    ap.add_argument("out_dir")
    ap.add_argument("--prompt", required=True, help="the new part, in the figure's material")
    ap.add_argument("--neg", default=NEG)
    ap.add_argument("--count", type=int, default=4)
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--cfg", type=float, default=8.0)
    ap.add_argument("--strength", type=float, default=0.99)
    ap.add_argument("--low-vram", action="store_true", help="sequential CPU offload (slow, about 1.5 GB)")
    a = ap.parse_args(argv)
    if not 1 <= a.count <= 32:
        ap.error("--count must be 1 to 32")
    if not 1 <= a.steps <= 200:
        ap.error("--steps must be 1 to 200")
    if not 0 < a.strength <= 1:
        ap.error("--strength must be in (0, 1]")
    for p in (a.image, a.mask):
        if not os.path.isfile(p):
            print("INPAINT_FAIL no such file: %s" % p, file=sys.stderr)
            return 1
    from PIL import Image
    img = Image.open(a.image).convert("RGB")
    W, H = img.size
    if W % 8 or H % 8 or not (256 <= W <= 2048 and 256 <= H <= 2048):
        print("INPAINT_FAIL %s is %dx%d: SDXL needs each side a multiple of 8 in [256, 2048] "
              "(1024x1024 is what it was trained on)" % (a.image, W, H), file=sys.stderr)
        return 1
    m = Image.open(a.mask).convert("L").resize(img.size)
    lo, hi = m.getextrema()
    if hi < 128:
        print("INPAINT_FAIL the mask has no white area: nothing would be repainted", file=sys.stderr)
        return 1
    import torch
    from diffusers import StableDiffusionXLInpaintPipeline
    if not torch.cuda.is_available():
        print("INPAINT_FAIL no CUDA GPU visible to torch; edit the picture by hand instead", file=sys.stderr)
        return 1
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.time()
    pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0", revision=pins.hf("stabilityai/stable-diffusion-xl-base-1.0"),
        torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
    if a.low_vram:
        pipe.enable_sequential_cpu_offload()
    else:
        pipe.enable_model_cpu_offload()
    done = []
    for i in range(a.count):
        s = a.seed + i
        r = pipe(prompt=a.prompt, negative_prompt=a.neg, image=img, mask_image=m, strength=a.strength,
                 num_inference_steps=a.steps, guidance_scale=a.cfg, width=W, height=H,
                 generator=torch.manual_seed(s)).images[0]
        p = os.path.join(a.out_dir, "part_%d.png" % s)
        r.save(p)
        done.append(p)
        print("saved", p, flush=True)
    rep = {"tool": "sdxl base 1.0 inpaint", "image": os.path.basename(a.image), "mask": os.path.basename(a.mask),
           "prompt": a.prompt, "neg": a.neg, "seeds": [a.seed + i for i in range(a.count)], "steps": a.steps,
           "cfg": a.cfg, "strength": a.strength, "files": done, "seconds": round(time.time() - t0, 1),
           "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
           "licence": "CreativeML Open RAIL++-M (output)"}
    with open(os.path.join(a.out_dir, "parts.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print("INPAINT_OK %s %d pictures" % (a.out_dir, len(done)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
