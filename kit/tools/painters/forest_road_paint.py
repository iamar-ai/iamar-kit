#!/usr/bin/env python3
"""Painted surface of the forest road (K-FOR, forest road job, docs/MASTERPLAN_JOBS.md
f519ba8): one texture laid along the road as a ribbon (ForestRoad), u across the
road (0 = left verge, 1 = right verge), v along it (tiles every TILE_M metres).

    python3 kit/tools/painters/forest_road_paint.py [out=out/road_track.png] [--preview]

What it shows (K-ART style: painted value, warm lights, cool darks): a worn,
light dirt-and-gravel track that reads against the dark forest floor; two darker
wheel ruts with a lighter, grassy hump between them; pebbles and a few leaves; the
verges break up into grass with a noisy alpha so the ribbon melts into the
terrain instead of ending on a line. Seamless along v (all noise periodic in v).
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

W, H = 512, 1024              # across x along (TILE_M metres along)
TILE_M = 8.0
RUTS = (0.33, 0.67)           # rut centres across the road (u)


def pnoise(scale, seed):
    """Smooth noise periodic in v (rows) and clamped in u."""
    r = np.random.default_rng(seed).standard_normal((H, W))
    f = ndimage.gaussian_filter(r, scale, mode=("wrap", "reflect"))
    return f / (np.abs(f).max() + 1e-6)


def tile_noise(n, scale, seed, aniso=(1.0, 1.0)):
    r = np.random.default_rng(seed).standard_normal((n, n))
    f = ndimage.gaussian_filter(r, (scale * aniso[0], scale * aniso[1]), mode="wrap")
    return f / (np.abs(f).max() + 1e-6)


def paint_wood(out, n=512):
    """Weathered planks, grain along x: warm lit boards, dark seams, knots, grey wear."""
    grain = tile_noise(n, 1.5, 11, (0.4, 6.0)) * 0.6 + tile_noise(n, 3.0, 12, (0.6, 8.0)) * 0.4
    y = np.arange(n)[:, None].repeat(n, 1)
    board = (y // (n // 4)) % 2
    seam = np.clip(1.0 - np.abs((y % (n // 4)) - 1.5) / 3.0, 0, 1)
    col = np.array([0.56, 0.40, 0.25])[None, None, :] * (1.0 + 0.22 * grain[..., None] + 0.05 * board[..., None])
    lit = np.clip(1.0 - (y % (n // 4)) / 10.0, 0, 1)   # painted bevel: top edge of each board lit
    col = col * (1.0 + 0.18 * lit[..., None]) * (1.0 - 0.55 * seam[..., None])
    wear = np.clip(tile_noise(n, 20, 13) * 1.4 - 0.3, 0, 1)
    col = col * (1.0 - 0.35 * wear[..., None]) + np.array([0.5, 0.48, 0.44]) * 0.35 * wear[..., None]
    rng = np.random.default_rng(14)
    for _ in range(5):   # knots
        cy, cx = rng.integers(0, n, 2)
        yy, xx = np.ogrid[:n, :n]
        d = np.hypot(((xx - cx + n // 2) % n - n // 2) / 2.2, (yy - cy + n // 2) % n - n // 2)
        k = np.clip(1.0 - d / 9.0, 0, 1)
        col = col * (1.0 - 0.5 * k[..., None])
    Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).save(out)


def paint_stone(out, n=512):
    """Weathered dressed stone: soft value blotches, lit chips, lichen and moss."""
    b = tile_noise(n, 30, 21) * 0.6 + tile_noise(n, 6, 22) * 0.3 + tile_noise(n, 1.5, 23) * 0.1
    col = np.array([0.64, 0.61, 0.55])[None, None, :] * (1.0 + 0.2 * b[..., None])
    chips = tile_noise(n, 1.2, 24) > 0.6
    col[chips] = col[chips] * 1.18
    lich = np.clip(tile_noise(n, 8, 25) * 1.8 - 0.8, 0, 1)
    col = col * (1.0 - 0.4 * lich[..., None]) + np.array([0.70, 0.72, 0.52]) * 0.4 * lich[..., None]
    moss = np.clip(tile_noise(n, 14, 26) * 1.6 - 0.75, 0, 1)
    col = col * (1.0 - 0.6 * moss[..., None]) + np.array([0.30, 0.40, 0.16]) * 0.6 * moss[..., None]
    Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).save(out)


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    out = args[0] if args else "out/road_track.png"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    u = np.linspace(0.0, 1.0, W)[None, :].repeat(H, 0)
    n1, n2, n3 = pnoise(18, 1), pnoise(5, 2), pnoise(1.5, 3)
    # base: warm light dirt, mottled
    dirt = np.array([0.62, 0.50, 0.34])
    dirt_dark = np.array([0.40, 0.30, 0.20])
    col = dirt[None, None, :] * (1.0 + 0.10 * n1[..., None] + 0.06 * n2[..., None])
    # ruts: two darker, slightly cooler grooves with a lit edge on the left of each
    wob = 0.012 * pnoise(30, 4)
    for rc in RUTS:
        d = np.abs(u - rc - wob)
        rut = np.clip(1.0 - d / 0.07, 0.0, 1.0) ** 1.2
        col = col * (1.0 - 0.5 * rut[..., None]) + dirt_dark * 0.22 * rut[..., None]
        lip = np.clip(1.0 - np.abs(u - rc - wob - 0.065) / 0.02, 0.0, 1.0)
        col = col * (1.0 + 0.12 * lip[..., None])
    # centre hump: lighter, with grass creeping in
    cen = np.clip(1.0 - np.abs(u - 0.5 - wob) / 0.09, 0.0, 1.0)
    grass = np.array([0.42, 0.52, 0.22])
    gmask = np.clip(cen * (0.5 + 0.9 * pnoise(3, 5)) - 0.15, 0.0, 1.0)
    col = col * (1.0 + 0.10 * cen[..., None])
    col = col * (1.0 - gmask[..., None]) + grass * (0.85 + 0.3 * n2[..., None]) * gmask[..., None]
    # pebbles: small lit-top stones scattered, denser near the ruts' edges
    rng = np.random.default_rng(6)
    peb = np.zeros((H, W))
    for _ in range(320):
        y, x = rng.integers(0, H), rng.integers(8, W - 8)
        r = rng.uniform(2.5, 5.5)
        yy, xx = np.ogrid[-6:7, -6:7]
        m = (xx / r) ** 2 + (yy / (r * 0.8)) ** 2 <= 1.0
        ys = (np.arange(-6, 7) + y) % H
        sub = peb[ys][:, x - 6:x + 7]
        sub[m] = np.maximum(sub[m], rng.uniform(0.5, 1.0))
        peb[ys, x - 6:x + 7] = sub
    pcol = np.array([0.66, 0.62, 0.55])
    col = col * (1.0 - 0.6 * peb[..., None]) + pcol * peb[..., None] * 0.6 * (0.9 + 0.2 * n3[..., None])
    # fallen leaves: russet and gold flecks
    leaves = (pnoise(1.2, 7) > 0.55) & (rng.random((H, W)) < 0.5)
    col[leaves] = col[leaves] * 0.4 + np.array([0.55, 0.30, 0.12]) * 0.6
    # verges: grass grows in from both sides, alpha breaks up into tufts
    edge = np.minimum(u, 1.0 - u)
    ragged = edge + 0.05 * pnoise(4, 8) + 0.03 * pnoise(1.5, 9)
    verge = np.clip(1.0 - (ragged - 0.04) / 0.10, 0.0, 1.0)
    col = col * (1.0 - 0.6 * verge[..., None]) + grass * 0.9 * 0.6 * verge[..., None]
    alpha = np.clip((ragged - 0.015) / 0.07, 0.0, 1.0)
    img = np.dstack([np.clip(col, 0, 1), alpha])
    Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(out)
    if "--preview" in sys.argv:
        bg = Image.new("RGBA", (W * 2, H), (40, 52, 30, 255))
        t = Image.open(out)
        bg.alpha_composite(t, (0, 0))
        bg.alpha_composite(t, (W, 0))
        bg.convert("RGB").resize((512, 512)).save(os.path.splitext(out)[0] + "_preview.jpg", quality=85)
    d = os.path.dirname(out)
    paint_wood(os.path.join(d, "road_wood.png"))
    paint_stone(os.path.join(d, "road_stone.png"))
    print("forest_road_paint: wrote", out, "+ road_wood.png, road_stone.png")


if __name__ == "__main__":
    main()
