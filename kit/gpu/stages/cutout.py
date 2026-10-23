#!/usr/bin/env python3
"""Concept picture -> RGBA cut-out for an image-to-3D generator (GPU tier, step 1).

    python kit/gpu/stages/cutout.py concept.png out_rgba.png [--plinth-row N]
        [--size 1024] [--fill 0.8] [--model isnet-general-use] [--alpha-min 20]

Removes the background with rembg (isnet-general-use by default; CPU is enough), makes
every pixel row from --plinth-row down transparent (rows of the ORIGINAL picture: drop a
drawn plinth or ground, or the generator invents a floating disc under the feet), crops to
the subject and centres it on a square transparent canvas, the subject's longest side at
--fill of the canvas (0.8: the generators want a margin). A picture that already has an
alpha channel with transparent pixels keeps its own alpha (--rembg forces rembg).

Run it with the Python of your GPU environment (it needs rembg, onnxruntime, numpy and
Pillow). rembg downloads its model once (~170 MB) to U2NET_HOME (default ~/.u2net).
Packaged from the iamar-models mesh archive (not public) tools/mesh3d/statue_v4/cutout.py (iamar city, 2026-10-19).
Prints CUTOUT_OK <out> <subject w>x<h> on success, exits 1 on failure.
"""
import argparse
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--plinth-row", type=int, default=None,
                    help="first pixel row (original picture) made transparent")
    ap.add_argument("--size", type=int, default=1024, help="square canvas side (default 1024)")
    ap.add_argument("--fill", type=float, default=0.8, help="subject's longest side / canvas (default 0.8)")
    ap.add_argument("--model", default="isnet-general-use", help="rembg model (default isnet-general-use)")
    ap.add_argument("--alpha-min", type=int, default=20, help="alpha above this counts as subject")
    ap.add_argument("--rembg", action="store_true", help="run rembg even when the picture has alpha")
    a = ap.parse_args(argv)
    if not 0.1 <= a.fill <= 1.0:
        sys.exit("cutout: --fill must be between 0.1 and 1.0")

    import numpy as np
    from PIL import Image

    im = Image.open(a.src)
    has_alpha = im.mode in ("RGBA", "LA") and np.array(im.convert("RGBA"))[..., 3].min() < 250
    if has_alpha and not a.rembg:
        arr = np.array(im.convert("RGBA"))
        how = "own alpha"
    else:
        from rembg import new_session, remove
        arr = np.array(remove(im.convert("RGB"), session=new_session(a.model)).convert("RGBA"))
        how = "rembg " + a.model
    if a.plinth_row is not None:
        arr[max(0, a.plinth_row):, :, 3] = 0
    ys, xs = np.where(arr[..., 3] > a.alpha_min)
    if len(xs) == 0:
        print("CUTOUT_FAIL nothing left after background removal", file=sys.stderr)
        return 1
    crop = Image.fromarray(arr).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    sc = a.fill * a.size / max(crop.size)
    crop = crop.resize((max(1, int(crop.size[0] * sc)), max(1, int(crop.size[1] * sc))), Image.LANCZOS)
    canvas = Image.new("RGBA", (a.size, a.size), (0, 0, 0, 0))
    canvas.paste(crop, ((a.size - crop.size[0]) // 2, (a.size - crop.size[1]) // 2), crop)
    canvas.save(a.out)
    print("CUTOUT_OK %s %dx%d (%s)" % (a.out, crop.size[0], crop.size[1], how))
    return 0


if __name__ == "__main__":
    sys.exit(main())
