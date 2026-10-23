#!/usr/bin/env python3
"""Painted atlas of the roadside lantern (RoadLantern, scripts/world/road_lantern.gd;
the maintainer 2026-10-11 23:05, docs/masterplan_audit/f4_triage.md: the forest road lanterns
looked too modern). One 256 x 512 albedo + a matching normal map, shared by every
post on the forest road, the south approach and Thornbury:

    python3 kit/tools/painters/road_lantern_paint.py [out_dir=out] [--preview]

  u 0.00-0.50  weathered oak: grey-brown, silvered where the rain runs, dark
               splits along the grain, two knots, a little green lichen low down.
               Seamless along v (the post repeats it every 1.6 m).
  u 0.50-1.00  forged black iron: hammer dimples, warm rust in the hollows, worn
               edges a touch lighter.

The normal map (OpenGL / Godot convention, y up) comes from the same height field:
grain grooves and splits in the wood, hammer dimples in the iron.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

W, H = 256, 512
HALF = W // 2


def noise(shape, scale, seed, wrap=True):
    r = np.random.default_rng(seed).standard_normal(shape)
    f = ndimage.gaussian_filter(r, scale, mode="wrap" if wrap else "reflect")
    return f / (np.abs(f).max() + 1e-6)


def wood():
    h, w = H, HALF
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    # grain: long streaks along v (rows), wobbling a little across
    wob = noise((h, w), (40, 12), 1) * 6.0
    grain = np.sin((x + wob) * 0.55) * 0.5 + 0.5
    fine = noise((h, w), (18, 0.7), 2)
    streak = noise((h, w), (60, 3), 3)
    # splits: a few dark cracks along the grain, broken along their length
    split = np.zeros((h, w), np.float32)
    rng = np.random.default_rng(4)
    for cx in rng.uniform(4, w - 4, 7):
        on = noise((h,), 14, int(cx)) > -0.1
        d = np.abs(x - (cx + wob[:, :1] * 0.6))
        split += np.where(on[:, None], np.clip(1.0 - d / 1.3, 0, 1), 0)
    split = np.clip(split, 0, 1)
    # knots: dark rings, the grain bends round them
    knot = np.zeros((h, w), np.float32)
    for (kx, ky, kr) in [(0.3, 0.28, 7.0), (0.72, 0.71, 5.5)]:
        kx *= w
        ky *= h
        dd = np.hypot((x - kx) * 1.0, (y - ky) * 0.55)
        dd = np.minimum(dd, np.hypot((x - kx), (y - ky - h) * 0.55))
        dd = np.minimum(dd, np.hypot((x - kx), (y - ky + h) * 0.55))
        knot = np.maximum(knot, np.clip(1.0 - dd / kr, 0, 1))
    base = np.array([0.40, 0.31, 0.22])        # weathered oak
    silver = np.array([0.52, 0.49, 0.44])      # rain-silvered
    dark = np.array([0.16, 0.11, 0.08])
    lichen = np.array([0.40, 0.45, 0.30])
    t = np.clip(streak * 0.5 + 0.5, 0, 1)[..., None]
    col = base * (1 - t * 0.7) + silver * (t * 0.7)
    col = col * (0.82 + 0.18 * grain[..., None]) * (0.93 + 0.07 * fine[..., None])
    col = col * (1 - split[..., None] * 0.75) + dark * split[..., None] * 0.75
    ring = (np.sin(knot * 18.0) * 0.5 + 0.5) * (knot > 0.02)
    col = col * (1 - knot[..., None] * 0.55) + dark * (knot[..., None] * 0.55) * (0.6 + 0.4 * ring[..., None])
    lic = np.clip(noise((h, w), 5, 9) * 1.6 - 0.9, 0, 1)[..., None] * 0.45
    col = col * (1 - lic) + lichen * lic
    height = grain * 0.35 + fine * 0.15 - split * 0.9 - knot * 0.3 + ring * 0.15
    return col, height


def iron():
    h, w = H, W - HALF
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    # hammer dimples: soft round dents on a jittered grid
    dim = np.zeros((h, w), np.float32)
    rng = np.random.default_rng(11)
    for _ in range(300):
        cx, cy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(4.0, 9.0)
        dx = np.minimum(np.abs(x - cx), w - np.abs(x - cx))
        dy = np.minimum(np.abs(y - cy), h - np.abs(y - cy))
        d2 = (dx * dx + dy * dy) / (r * r)
        dim = np.minimum(dim, -np.clip(1.0 - d2, 0, 1) ** 2)
    rough = noise((h, w), 1.2, 12)
    blot = noise((h, w), 9, 13)
    base = np.array([0.13, 0.12, 0.12])
    worn = np.array([0.30, 0.29, 0.28])
    rust = np.array([0.36, 0.17, 0.08])
    rs = np.clip(blot * 1.4 - 0.25, 0, 1) * np.clip(-dim * 1.5 + 0.3, 0, 1)
    rs = np.clip(rs + np.clip(rough - 0.75, 0, 1) * 0.6, 0, 0.85)[..., None]
    hi = 0.25 + 0.2 * np.clip(dim + 1.0, 0, 1) + 0.25 * np.clip(blot, 0, 1)
    col = base * (1 - hi[..., None]) + worn * hi[..., None]
    col = col * (0.9 + 0.1 * rough[..., None])
    col = col * (1 - rs) + rust * rs
    height = dim * 0.8 + rough * 0.08
    return col, height


def normal_from(height, strength):
    gy, gx = np.gradient(ndimage.gaussian_filter(height, 0.8, mode="wrap"))
    nx, ny, nz = -gx * strength, gy * strength, np.ones_like(height)
    n = np.stack([nx, ny, nz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = args[0] if args else "out"
    os.makedirs(out, exist_ok=True)
    wc, wh = wood()
    ic, ih = iron()
    col = np.concatenate([wc, ic], 1)
    nrm = np.concatenate([normal_from(wh, 3.0), normal_from(ih, 4.0)], 1)
    srgb = np.clip(col, 0, 1)   # painted straight in sRGB
    Image.fromarray((srgb * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, "road_lantern.png"))
    Image.fromarray((np.clip(nrm, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, "road_lantern_n.png"))
    print("wrote", os.path.join(out, "road_lantern.png"), os.path.join(out, "road_lantern_n.png"))


if __name__ == "__main__":
    main()
