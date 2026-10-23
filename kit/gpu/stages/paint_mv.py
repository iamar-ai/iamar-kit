#!/usr/bin/env python3
"""Paint a game cage from the generated views with Hunyuan3D-2 paint (GPU tier, multiview, optional).

    python kit/gpu/stages/paint_mv.py game/x_cage.glb out/views/x game/x_painted.glb
        --repo ~/mv/Hunyuan3D-2 [--paint 000,090,270] [--size 2048] [--rewrap]
        [--base "#355e4c" --gain 1.12] [--glow game/x_glow.png]

Paints the cage (`sculpt.py cage`, or any low mesh with UVs) from several views so the far
side is painted from its own view instead of guessed (the city's dragon heads: no mirror
step). The cage keeps its own UVs (--rewrap: Hunyuan3D-2's own xatlas unwrap instead). The
city's lesson: leave the back view out (`--paint 000,090,270`, the default); it is the
weakest of the generated views. Faces no view saw come out flat grey: --base recolours that
fill and lifts the colours (stages/paint_fix.py), --glow writes an emission mask of the hot
colours. Next: `sculpt.py game x_painted.glb x_high.glb final` (the normal bake keeps the
painted texture and adds the normal map).

--repo is the Hunyuan3D-2 clone with its texture half built (hy3dgen/texgen: the
custom_rasterizer and differentiable_renderer extensions; kit/gpu/README.md 'Install').
Weights tencent/Hunyuan3D-2 (hunyuan3d-paint-v2-0 and hunyuan3d-delight-v2-0) load from
HF_HOME and are never copied into the kit or a world. The pipeline runs with model CPU
offload (the city painted on an 11 GB RTX 2080 Ti, about 1 minute at 2048 px).

LICENCE: Tencent Hunyuan 3D 2.0 Community License (EU, UK, South Korea excluded; see
shape_mv.py). `sculpt.py paint` asks for the region first.
Prints PAINT_OK. Packaged from the iamar-models mesh archive (not public) tools/mesh3d/head_mv.py (paint stage) and
head_tex.py (iamar city, an internal task).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pins  # noqa: E402  (kit/gpu/pins.json: the pinned upstream revisions)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True


def parse_views(spec):
    out = []
    for v in spec.split(","):
        v = v.strip()
        if not v.isdigit() or not 0 <= int(v) < 360 or int(v) in out:
            raise ValueError("--paint %r: distinct degrees, comma separated (000,090,270)" % spec)
        out.append(int(v))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cage", help="low mesh with UVs (.glb/.obj)")
    ap.add_argument("views", help="views prefix (P_az<deg>_rgba.png)")
    ap.add_argument("out", help="painted .glb")
    ap.add_argument("--repo", default=os.environ.get("HY3D2_REPO"), help="Hunyuan3D-2 clone (env HY3D2_REPO)")
    ap.add_argument("--paint", default="000,090,270", help="views to paint from (degrees)")
    ap.add_argument("--size", type=int, default=2048, help="texture and render size")
    ap.add_argument("--rewrap", action="store_true", help="new UVs by Hunyuan3D-2 instead of the cage's own")
    ap.add_argument("--base", default="", help="recolour the unseen grey fill to this #rrggbb")
    ap.add_argument("--gain", type=float, default=1.12)
    ap.add_argument("--glow", default="", help="write the hot-colour emission mask here")
    a = ap.parse_args(argv)
    import paint_fix
    try:
        az = parse_views(a.paint)
        base = paint_fix.hex_rgb(a.base) if a.base else None
    except ValueError as e:
        print("PAINT_FAIL %s" % e, file=sys.stderr)
        return 1
    files = ["%s_az%03d_rgba.png" % (a.views, v) for v in az]
    miss = [f for f in files + [a.cage] if not os.path.isfile(f)]
    if miss:
        print("PAINT_FAIL missing: %s" % ", ".join(miss), file=sys.stderr)
        return 1
    if not a.repo or not os.path.isdir(os.path.join(a.repo, "hy3dgen", "texgen")):
        print("PAINT_FAIL --repo (or HY3D2_REPO) must be the Hunyuan3D-2 clone (has hy3dgen/texgen)", file=sys.stderr)
        return 1
    sys.path.insert(0, os.path.abspath(a.repo))

    import torch
    import trimesh
    from PIL import Image
    if not torch.cuda.is_available():
        print("PAINT_FAIL no CUDA GPU visible to torch (see kit/gpu/gpu_check.py --stage paint)", file=sys.stderr)
        return 1
    import hy3dgen.texgen.pipelines as P
    if not a.rewrap:
        P.mesh_uv_wrap = lambda m: m   # keep the cage's own UVs
    from hy3dgen.texgen import Hunyuan3DPaintPipeline

    low = trimesh.load(a.cage, force="mesh", process=False)
    if not a.rewrap and getattr(low.visual, "uv", None) is None:
        print("PAINT_FAIL %s has no UVs: unwrap it (sculpt.py cage does) or pass --rewrap" % a.cage, file=sys.stderr)
        return 1
    refs = [Image.open(f).convert("RGBA") for f in files]
    t0 = time.time()
    paint = Hunyuan3DPaintPipeline.from_pretrained(
        pins.snapshot("tencent/Hunyuan3D-2", ["hunyuan3d-delight-v2-0/*", "hunyuan3d-paint-v2-0-turbo/*"]))
    paint.config.texture_size = a.size
    paint.config.render_size = a.size
    paint.enable_model_cpu_offload()
    load_s = time.time() - t0
    t1 = time.time()
    m = paint(low, image=refs)
    paint_s = time.time() - t1
    # the paint renderer may hand back its own centred, normalised frame: put the mesh back
    # where the cage was (uniform scale + offset; a turned or squashed result is refused)
    restored = False
    lo, hi = low.bounds
    plo, phi = m.bounds
    ext, pext = hi - lo, phi - plo
    if pext.max() <= 0:
        print("PAINT_FAIL the painted mesh is empty", file=sys.stderr)
        return 1
    k = ext.max() / pext.max()
    if abs(k - 1) > 1e-3 or abs((lo + hi - plo - phi)).max() > 1e-3 * ext.max():
        ratio = (ext + 1e-9) / (pext * k + 1e-9)
        if abs(ratio - 1).max() > 0.02:
            print("PAINT_FAIL the painted mesh's proportions %s differ from the cage's %s (turned?)"
                  % (list(pext.round(3)), list(ext.round(3))), file=sys.stderr)
            return 1
        m.apply_scale(k)
        m.apply_translation((lo + hi) / 2 - (m.bounds[0] + m.bounds[1]) / 2)
        restored = True
    grey = None
    mat = getattr(m.visual, "material", None)
    attr = next((k for k in ("baseColorTexture", "image") if getattr(mat, k, None) is not None), None)
    if (base or a.glow) and attr is None:
        print("PAINT_FAIL the painted mesh has no texture image to fix", file=sys.stderr)
        return 1
    if a.glow:
        mask, _ = paint_fix.glow_mask(getattr(mat, attr))
        mask.save(a.glow)
    if base:
        fixed, grey = paint_fix.fix_albedo(getattr(mat, attr), base, a.gain)
        setattr(mat, attr, fixed)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    m.export(a.out)
    rep = {"tool": "hunyuan3d-2 paint", "cage": a.cage, "views": files, "out": a.out, "size": a.size,
           "faces": len(m.faces), "size_restored": restored, "load_s": round(load_s, 1), "paint_s": round(paint_s, 1),
           "grey_fill_recoloured": None if grey is None else round(grey, 4),
           "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2), "gpu": torch.cuda.get_device_name(0)}
    with open(os.path.splitext(a.out)[0] + ".json", "w") as f:
        json.dump(rep, f, indent=1)
    print("PAINT_OK %s from %d views at %d px, paint %.0fs, peak GPU %.1f GB" % (
        a.out, len(files), a.size, paint_s, rep["peak_gpu_gb"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
