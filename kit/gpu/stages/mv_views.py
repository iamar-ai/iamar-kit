#!/usr/bin/env python3
"""One picture -> consistent views from other sides with MV-Adapter on SDXL (GPU tier, multiview).

    python kit/gpu/stages/mv_views.py pic.png out/views/x --mvadapter ~/mv/MV-Adapter
        --text "carved grey stone dragon head, game asset" [--az 0 90 180 270]
        [--size 768] [--steps 40] [--cfg 3.0] [--seed 7] [--neg "..."]
        [--mask keep.png] [--rembg] [--model u2net]

The picture becomes the azimuth-0 view and MV-Adapter (github huanngzh/MV-Adapter,
Apache-2.0; weights huanngzh/mv-adapter) paints the others around it on SDXL base 1.0
(CreativeML Open RAIL++-M) with the madebyollin/sdxl-vae-fp16-fix VAE: orthographic,
elevation 0. A picture with its own transparency (a kit cut-out) keeps its alpha; otherwise
rembg cuts it out first (--mask: white = keep, multiplied into rembg's alpha, e.g. a head
without its neck). --text says what the subject is: the views follow it.

Writes, for the prefix P:
  P_cut.png              the conditioning cut-out
  P_ref.png              the same framed the way MV-Adapter sees it (az 0)
  P_az<deg>.png          every view, RGB on flat grey
  P_az<deg>_rgba.png     every view cut out by rembg (pale parts: run mv_recut.py next)
  P_grid.png             all views side by side, to look at before the shape step
  P_views.json           settings, seconds, peak GPU memory
Prints VIEWS_OK. Exits 1 on failure.

Memory (measured in the iamar city on an RTX 2080 Ti 11 GB, 2026-10-14): 768 px, 40 steps,
4 views: 9.7 GB peak, about 90 s. Needs kit/gpu/patches/mvadapter_11gb.patch in the clone
on cards under 14 GB (unpatched, the reference cache is cloned every step and 4 views do not
fit 11 GB); 6 views did not fit 11 GB even patched. The prompt is encoded first and both
text encoders leave the GPU before the UNet runs. diffusers' enable_model_cpu_offload does
NOT work with this pipeline (accelerate copies the cross-attention kwargs, the reference
pass's hidden-state cache comes back empty: KeyError on the first step).

SDXL must load with variant="fp16" (only the fp16 files are needed: without it diffusers
starts a 13 GB download). Weights load from the Hugging Face cache (HF_HOME) and are never
copied into the kit or a world.
Packaged from the iamar-models mesh archive (not public) tools/mesh3d/mv_views.py (iamar city, an internal task).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pins  # noqa: E402  (kit/gpu/pins.json: the pinned upstream revisions)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", help="the concept picture (a kit cut-out keeps its alpha)")
    ap.add_argument("out", help="output prefix (folder/name)")
    ap.add_argument("--mvadapter", default=os.environ.get("MVADAPTER"),
                    help="the MV-Adapter git clone (env MVADAPTER)")
    ap.add_argument("--text", default="high quality, detailed, game asset",
                    help="what the subject is (the views follow it)")
    ap.add_argument("--neg", default="", help="more negative prompt, appended to the default")
    ap.add_argument("--az", type=int, nargs="+", default=[0, 90, 180, 270])
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--cfg", type=float, default=3.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--mask", default=None, help="white = keep, multiplied into rembg's alpha")
    ap.add_argument("--rembg", action="store_true", help="run rembg even when the picture has alpha")
    ap.add_argument("--model", default="u2net", help="rembg model for the cut-outs (default u2net)")
    a = ap.parse_args(argv)
    if not a.mvadapter or not os.path.isfile(
            os.path.join(a.mvadapter, "mvadapter", "pipelines", "pipeline_mvadapter_i2mv_sdxl.py")):
        print("VIEWS_FAIL --mvadapter (or MVADAPTER) must be the MV-Adapter clone "
              "(has mvadapter/pipelines/; kit/gpu/README.md 'Install')", file=sys.stderr)
        return 1
    if 0 not in a.az or len(set(a.az)) != len(a.az) or any(not 0 <= x < 360 for x in a.az):
        print("VIEWS_FAIL --az: distinct degrees in [0, 360) including 0 (the picture itself)", file=sys.stderr)
        return 1
    if a.size % 64 or not 256 <= a.size <= 1024:
        print("VIEWS_FAIL --size must be a multiple of 64 in [256, 1024]", file=sys.stderr)
        return 1
    sys.path.insert(0, os.path.abspath(a.mvadapter))
    t0 = time.time()
    log = lambda *x: print("[%ds]" % round(time.time() - t0), *x, flush=True)

    import numpy as np
    import torch
    from PIL import Image
    from rembg import new_session, remove
    if not torch.cuda.is_available():
        print("VIEWS_FAIL no CUDA GPU visible to torch (see kit/gpu/gpu_check.py --stage views)", file=sys.stderr)
        return 1
    sess = new_session(a.model)

    def cutout(img, mask=None):
        rgba = remove(img.convert("RGB"), session=sess, bgcolor=[255, 255, 255, 0])
        if mask is not None:
            al = np.asarray(rgba.getchannel("A")).astype(np.float32)
            al *= np.asarray(mask.convert("L").resize(rgba.size)) / 255.0
            rgba.putalpha(Image.fromarray(al.astype(np.uint8)))
        return rgba

    src = Image.open(a.src)
    own = src.mode in ("RGBA", "LA") and np.asarray(src.convert("RGBA"))[..., 3].min() < 250
    if own and not a.rembg:
        ref = src.convert("RGBA")
        if a.mask:
            al = np.asarray(ref.getchannel("A")).astype(np.float32)
            al *= np.asarray(Image.open(a.mask).convert("L").resize(ref.size)) / 255.0
            ref.putalpha(Image.fromarray(al.astype(np.uint8)))
    else:
        ref = cutout(src, Image.open(a.mask) if a.mask else None)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    ref.save(a.out + "_cut.png")

    from diffusers import AutoencoderKL
    from mvadapter.pipelines.pipeline_mvadapter_i2mv_sdxl import MVAdapterI2MVSDXLPipeline
    from mvadapter.schedulers.scheduling_shift_snr import ShiftSNRScheduler
    from mvadapter.utils import make_image_grid
    from mvadapter.utils.geometry import get_plucker_embeds_from_cameras_ortho
    from mvadapter.utils.mesh_utils import get_orthogonal_camera
    from scripts.inference_i2mv_sdxl import preprocess_image

    dev = "cuda"
    pipe = MVAdapterI2MVSDXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0", revision=pins.hf("stabilityai/stable-diffusion-xl-base-1.0"),
        vae=AutoencoderKL.from_pretrained("madebyollin/sdxl-vae-fp16-fix", revision=pins.hf("madebyollin/sdxl-vae-fp16-fix")),
        torch_dtype=torch.float16, variant="fp16")
    # the UNet and VAE go to the GPU at once: the CPU copy of the whole pipeline peaked at 15-17 GB of
    # RAM, and a host watchdog that kills a process over 40% of RAM (the GPU host, 31 GB) ended the run
    pipe.unet.to(dev)
    pipe.vae.to(dev)
    import gc
    gc.collect()
    pipe.scheduler = ShiftSNRScheduler.from_scheduler(pipe.scheduler, shift_mode="interpolated", shift_scale=8.0)
    n = len(a.az)
    pipe.init_custom_adapter(num_views=n)
    pipe.load_custom_adapter("huanngzh/mv-adapter", weight_name="mvadapter_i2mv_sdxl.safetensors",
                             revision=pins.hf("huanngzh/mv-adapter"))
    pipe.to(dtype=torch.float16)
    neg = "watermark, text, ugly, deformed, noisy, blurry, low contrast, extra heads" + (", " + a.neg if a.neg else "")
    load_s = time.time() - t0
    # encode the prompt, then move both text encoders off the GPU before the UNet runs
    pipe.text_encoder.to(dev)
    pipe.text_encoder_2.to(dev)
    with torch.no_grad():
        pe, npe, ppe, nppe = pipe.encode_prompt(prompt=a.text, device=dev, num_images_per_prompt=1,
                                                do_classifier_free_guidance=True, negative_prompt=neg)
    pipe.text_encoder.to("cpu")
    pipe.text_encoder_2.to("cpu")
    torch.cuda.empty_cache()
    pipe.unet.to(dev)
    pipe.vae.to(dev)
    pipe.cond_encoder.to(device=dev, dtype=torch.float16)
    pipe.enable_vae_slicing()
    # the text encoders sit on the CPU now: the pipeline would take that as its device
    type(pipe)._execution_device = property(lambda self: torch.device(dev))
    log("pipeline ready, GB", round(torch.cuda.memory_allocated() / 2**30, 2))

    S = a.size
    cams = get_orthogonal_camera(elevation_deg=[0] * n, distance=[1.8] * n, left=-0.55, right=0.55,
                                 bottom=-0.55, top=0.55, azimuth_deg=[x - 90 for x in a.az], device=dev)
    ctrl = ((get_plucker_embeds_from_cameras_ortho(cams.c2w, [1.1] * n, S) + 1.0) / 2.0).clamp(0, 1)
    cond = preprocess_image(ref, S, S)
    cond.save(a.out + "_ref.png")
    t1 = time.time()
    imgs = pipe(prompt_embeds=pe, negative_prompt_embeds=npe, pooled_prompt_embeds=ppe,
                negative_pooled_prompt_embeds=nppe, height=S, width=S, num_inference_steps=a.steps,
                guidance_scale=a.cfg, num_images_per_prompt=n, control_image=ctrl,
                control_conditioning_scale=1.0, reference_image=cond, reference_conditioning_scale=1.0,
                cross_attention_kwargs={"scale": 1.0},
                generator=torch.Generator(device=dev).manual_seed(a.seed)).images
    sample_s = time.time() - t1
    peak = torch.cuda.max_memory_allocated() / 2**30
    for az, im in zip(a.az, imgs):
        im.save("%s_az%03d.png" % (a.out, az))
        cutout(im).save("%s_az%03d_rgba.png" % (a.out, az))
    make_image_grid([cond] + imgs, rows=1).save(a.out + "_grid.png")
    try:
        import resource
        ram = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    except ImportError:          # Windows
        ram = None
    rep = {"tool": "mv-adapter i2mv sdxl", "src": a.src, "prefix": a.out, "az": a.az, "size": S,
           "steps": a.steps, "cfg": a.cfg, "seed": a.seed, "text": a.text,
           "load_s": round(load_s, 1), "sample_s": round(sample_s, 1), "peak_gpu_gib": round(peak, 2),
           "peak_ram_gb": round(ram, 2) if ram else None, "gpu": torch.cuda.get_device_name(0)}
    with open(a.out + "_views.json", "w") as f:
        json.dump(rep, f, indent=1)
    print("VIEWS_OK %s_az*.png %d views at %d px, sample %.0fs, peak GPU %.1f GiB" % (a.out, n, S, sample_s, peak))
    return 0


if __name__ == "__main__":
    sys.exit(main())
