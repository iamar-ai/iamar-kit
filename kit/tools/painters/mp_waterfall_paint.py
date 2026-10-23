#!/usr/bin/env python3
"""Painted waterfall textures (K-FOR, waterfall job 2138f73): hand-painted in the
K-ART style, the motion comes from scrolling them in the shader (MpWaterfall).

    python3 kit/tools/painters/mp_waterfall_paint.py [out_dir=out] [--preview]

fall_flow.png  RGBA, tiles vertically: the falling sheet. Long vertical strands of
               pale cyan-white over translucent teal, thin bright white streaks,
               darker glassy gaps (alpha low, see-through to the sheet behind) so
               the layered sheets read as a body of water with depth (mp-WATER).
foam.png       RGBA: soft billowing white foam / mist clump (base cards), alpha
               falls off to the edges, painted lit top and cool blue-grey shadow.
foam_tile.png  RGBA, tiles both ways: churning foam for the mound at the foot and
               the drift on the pond: white billows, blue-grey pockets, holes.
rock.png       RGB, tiles both ways: mottled grey-brown stone with lichen and moss
               flecks and a few dark cracks, for the broad boulders round the plunge.
ring.png       RGBA, top-down: a broken ring of foam with ripples, clear middle.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage


def per_noise(shape, sig, seed, wrap=("wrap", "wrap")):
    r = np.random.default_rng(seed).standard_normal(shape)
    f = ndimage.gaussian_filter(r, sig, mode=wrap)
    return f / (np.abs(f).max() + 1e-6)


def save(a, path):
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def flow(out):
    H, W = 1024, 512
    # strands: noise stretched hard along v (rows), periodic both ways
    s1 = per_noise((H, W), (40, 2.0), 1)
    s2 = per_noise((H, W), (90, 5.0), 2)
    s3 = per_noise((H, W), (14, 1.0), 3)
    strand = 0.5 + 0.55 * s1 + 0.35 * s2 + 0.2 * s3
    # thin bright streaks: hard-stretched noise thresholded to lines a few px wide,
    # breaking up along their length (painted white strokes down the fall)
    s4 = per_noise((H, W), (70, 0.8), 9)
    s5 = per_noise((H, W), (25, 6.0), 10)
    streak = np.clip((s4 - 0.42) * 5.0, 0, 1) * np.clip(0.7 + 0.8 * s5, 0, 1)
    teal = np.array([0.14, 0.46, 0.57])
    pale = np.array([0.70, 0.91, 0.97])
    white = np.array([0.97, 0.99, 1.0])
    t = np.clip(strand, 0, 1)[..., None]
    col = teal * (1 - t) + pale * t
    foam = np.clip(np.clip((strand - 0.66) * 3.5, 0, 1) + streak, 0, 1)
    col = col * (1 - foam[..., None]) + white * foam[..., None]
    # glassy gaps go thin (0.18) so the sheet behind shows through; strands and
    # streaks are solid
    lo, hi = np.quantile(strand, [0.12, 0.88])
    alpha = np.clip(0.18 + (strand - lo) / (hi - lo) * 0.82, 0.18, 1.0)
    alpha = np.maximum(alpha, foam * 0.97)
    save(np.dstack([col, alpha]), out)


def foam(out):
    N = 512
    yy, xx = np.mgrid[0:N, 0:N] / (N - 1.0) * 2.0 - 1.0
    r = np.hypot(xx * 0.9, yy * 1.1)
    b = per_noise((N, N), 22, 4, ("reflect", "reflect")) * 0.6 + per_noise((N, N), 9, 5, ("reflect", "reflect")) * 0.3 \
        + per_noise((N, N), 3, 6, ("reflect", "reflect")) * 0.1
    body = np.clip(1.0 - r + 0.35 * b, 0, 1)
    alpha = np.clip(body * 2.6 - 0.85, 0, 1) ** 0.9
    lit = np.clip(0.5 - yy * 0.6 + 0.5 * b, 0, 1)   # painted light from above
    shadow = np.array([0.66, 0.76, 0.84])
    white = np.array([0.98, 0.99, 1.0])
    col = shadow * (1 - lit[..., None]) + white * lit[..., None]
    save(np.dstack([col, alpha]), out)


def foam_tile(out):
    N = 256
    b = per_noise((N, N), 18, 21) * 0.55 + per_noise((N, N), 7, 22) * 0.3 + per_noise((N, N), 2.5, 23) * 0.15
    churn = np.clip(0.62 + 0.9 * b, 0, 1)
    # lit billows: brighter where the noise rises, cool shadow in the pockets
    lit = np.clip(0.35 + 0.9 * b + 0.25 * per_noise((N, N), 4, 24), 0, 1)
    shadow = np.array([0.70, 0.79, 0.86])
    white = np.array([0.99, 1.0, 1.0])
    col = shadow * (1 - lit[..., None]) + white * lit[..., None]
    # holes where the pockets are deep, else dense foam
    alpha = np.clip((churn - 0.22) * 1.6, 0, 1) ** 0.8
    save(np.dstack([col, alpha]), out)


def rock(out):
    N = 256
    g = per_noise((N, N), 14, 31) * 0.5 + per_noise((N, N), 5, 32) * 0.3 + per_noise((N, N), 1.6, 33) * 0.2
    base_a = np.array([0.70, 0.65, 0.56])   # warm grey-brown (bright: it is
    base_b = np.array([0.40, 0.41, 0.40])   # multiplied by vertex colour) / cooler grey
    # (after4 shots: std 0.07 read as flat grey humps in the game; 2.4 x g and the
    # darker cool grey push the mottling to std ~0.11 so the stone shows at 3 m)
    t = np.clip(0.5 + 2.4 * g, 0, 1)[..., None]
    col = base_b * (1 - t) + base_a * t
    # lichen flecks (pale yellow-green) and moss (deeper green) in the hollows
    lich = np.clip((per_noise((N, N), 3, 34) - 0.45) * 4.0, 0, 1)
    moss = np.clip((per_noise((N, N), 9, 35) - 0.25) * 2.2, 0, 1) * np.clip(0.6 - g, 0, 1)
    col = col * (1 - lich[..., None]) + np.array([0.66, 0.64, 0.42]) * lich[..., None]
    col = col * (1 - moss[..., None]) + np.array([0.30, 0.42, 0.20]) * moss[..., None]
    # a few dark cracks: thin lines of stretched noise
    wander = per_noise((N, N), (1.5, 9), 36) + 0.5 * per_noise((N, N), (6, 1.5), 37)
    crack = np.clip((np.abs(wander) < 0.03) * 1.0, 0, 1) * np.clip((per_noise((N, N), 20, 38) + 0.1) * 3.0, 0, 1)
    col = col * (1 - 0.5 * crack[..., None])
    save(col, out)


def ring(out):
    N = 512
    yy, xx = np.mgrid[0:N, 0:N] / (N - 1.0) * 2.0 - 1.0
    r = np.hypot(xx, yy)
    a = np.arctan2(yy, xx)
    wob = per_noise((N, N), 10, 7, ("reflect", "reflect"))
    band = np.exp(-((r - 0.62 - 0.05 * wob) / 0.12) ** 2)
    inner = np.exp(-((r - 0.36 - 0.04 * wob) / 0.07) ** 2) * 0.6
    ripples = (0.5 + 0.5 * np.sin(r * 40.0 + wob * 2.0)) * np.clip(1.0 - r, 0, 1) * 0.25
    broken = np.clip(0.55 + 0.6 * per_noise((N, N), 5, 8, ("reflect", "reflect")) + 0.2 * np.sin(a * 7.0), 0, 1)
    alpha = np.clip((band + inner) * broken + ripples, 0, 1) * np.clip((0.98 - r) * 6.0, 0, 1)
    col = np.array([0.95, 0.98, 1.0])[None, None, :] * (0.85 + 0.15 * broken[..., None])
    save(np.dstack([col.repeat(N, 0) if col.shape[0] == 1 else col, alpha]), out)


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    d = args[0] if args else "out"
    os.makedirs(d, exist_ok=True)
    flow(os.path.join(d, "fall_flow.png"))
    foam(os.path.join(d, "foam.png"))
    foam_tile(os.path.join(d, "foam_tile.png"))
    rock(os.path.join(d, "rock.png"))
    ring(os.path.join(d, "ring.png"))
    if "--preview" in sys.argv:
        sheet = Image.new("RGBA", (2560, 512), (36, 60, 70, 255))
        for i, n in enumerate(["fall_flow", "foam", "foam_tile", "rock", "ring"]):
            t = Image.open(os.path.join(d, n + ".png")).convert("RGBA").resize((512, 512))
            sheet.alpha_composite(t, (i * 512, 0))
        sheet.convert("RGB").save(os.path.join(d, "preview.jpg"), quality=85)
    print("mp_waterfall_paint: wrote", d)


if __name__ == "__main__":
    main()
