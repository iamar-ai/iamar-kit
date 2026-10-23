#!/usr/bin/env python3
"""Finish a generated albedo for the game (GPU tier, after paint_mv.py; CPU only).

    python kit/gpu/stages/paint_fix.py albedo.png --base "#355e4c" [--gain 1.12]
        [--glow glow_mask.png] [--out fixed.png]

Hunyuan3D-2's paint leaves faces no view saw as a flat grey and its delighting leaves the
colours a little dark. This recolours the grey fill to --base (keeping the fill's own light
and dark, soft-edged so the patches do not outline), lifts the whole map by --gain, and with
--glow writes an emission mask of the hot colours (saturated yellow-orange: glowing eyes and
mouths). Without --out the albedo is rewritten in place.
Prints PAINT_FIX_OK with the share of the map recoloured. Needs numpy and Pillow.
Packaged from the iamar-models mesh archive (not public) tools/mesh3d/head_tex.py (iamar city, an internal task).
"""
import argparse
import re
import sys


def hex_rgb(s):
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", s or ""):
        raise ValueError("colour %r: use #rrggbb" % s)
    return [int(s[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]


def fix_albedo(im, base, gain=1.12):
    """(fixed RGB image, share of the map that was grey fill)."""
    import numpy as np
    from PIL import Image, ImageFilter
    rgb = np.asarray(im.convert("RGB")).astype(np.float32) / 255.0
    mx, mn = rgb.max(2), rgb.min(2)
    sat = np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0.0)
    grey = (sat < 0.12) & (mx > 0.3) & (mx < 0.82)
    g = Image.fromarray((grey * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    w = np.asarray(g).astype(np.float32)[..., None] / 255.0
    fill = np.array(base, np.float32) * (0.6 + 0.8 * rgb.mean(2, keepdims=True))
    out = np.clip((rgb * (1 - w) + fill * w) * gain, 0, 1)
    return Image.fromarray((out * 255).astype(np.uint8)), float(grey.mean())


def glow_mask(im):
    """(mask image, share of the map that is hot colour)."""
    import numpy as np
    from PIL import Image, ImageFilter
    rgb = np.asarray(im.convert("RGB")).astype(np.float32) / 255.0
    mx, mn = rgb.max(2), rgb.min(2)
    sat = np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0.0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hot = (r > 0.7) & (g > 0.45) & (b < 0.35) & (sat > 0.5) & (r >= g)
    m = Image.fromarray((hot * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.5))
    return m, float(hot.mean())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("albedo")
    ap.add_argument("--base", required=True, help="the subject's base colour, #rrggbb")
    ap.add_argument("--gain", type=float, default=1.12)
    ap.add_argument("--glow", default="", help="also write the hot-colour emission mask here")
    ap.add_argument("--out", default="", help="write here instead of in place")
    a = ap.parse_args(argv)
    try:
        base = hex_rgb(a.base)
    except ValueError as e:
        ap.error(str(e))
    if not 0.5 <= a.gain <= 2.0:
        ap.error("--gain must be in [0.5, 2.0]")
    from PIL import Image
    src = Image.open(a.albedo)
    if a.glow:
        m, hot = glow_mask(src)       # from the paint's own colours, before the lift
        m.save(a.glow)
        print("glow %.2f %% of the map -> %s" % (hot * 100, a.glow))
    out, grey = fix_albedo(src, base, a.gain)
    out.save(a.out or a.albedo)
    print("PAINT_FIX_OK %s grey fill %.1f %% recoloured to %s" % (a.out or a.albedo, grey * 100, a.base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
