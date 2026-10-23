#!/usr/bin/env python3
"""Painted crop fields for the countryside outside the walls (MpCountryside, K-FOR;
review r4 gap 4). One atlas of 4 x 2 tileable cells, each CELL px = TILE_M metres,
rows running along v (the shader turns each field's rows its own way):

  0 ripe wheat (gold rows)      1 green barley / young corn   2 ploughed furrows
  3 pasture with clover          4 cabbage / turnip rows        5 flax (blue flowers)
  6 rapeseed (yellow)            7 fallow / hay meadow (mown stripes)

    python3 kit/tools/painters/mp_fields_paint.py [out=out/fields_atlas.png] [--preview]

Painted value in the K-ART manner: warm light, cool shade, soft brushy mottling,
row ridges lit on one side; everything periodic so each cell tiles.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

CELL = 512
TILE_M = 8.0


def pn(sig, seed):
    r = np.random.default_rng(seed).standard_normal((CELL, CELL))
    f = ndimage.gaussian_filter(r, sig, mode="wrap")
    return f / (np.abs(f).max() + 1e-6)


def rows(n_rows, sharp=2.0):
    """Row ridges across u (period CELL / n_rows): 1 on the ridge, 0 in the furrow."""
    u = np.arange(CELL)[None, :].repeat(CELL, 0) / CELL
    s = 0.5 + 0.5 * np.cos(u * n_rows * 2 * np.pi)
    return s ** sharp, np.sin(u * n_rows * 2 * np.pi)   # ridge, side (lit/shade)


def mix(a, b, t):
    return a * (1 - t[..., None]) + b * t[..., None]


def cell(kind):
    m1, m2, m3 = pn(30, kind * 7 + 1), pn(6, kind * 7 + 2), pn(1.4, kind * 7 + 3)
    if kind == 0:   # ripe wheat
        r, side = rows(16, 1.2)
        c = mix(np.array([0.62, 0.45, 0.18]), np.array([0.93, 0.78, 0.38]), np.clip(r * 0.8 + 0.25 * m2 + 0.15 * m3, 0, 1))
        c *= (1 + 0.08 * side)[..., None] * (1 + 0.08 * m1)[..., None]
    elif kind == 1:   # green barley
        r, side = rows(18, 1.0)
        c = mix(np.array([0.30, 0.45, 0.16]), np.array([0.62, 0.74, 0.30]), np.clip(r * 0.7 + 0.3 * m2 + 0.1 * m3, 0, 1))
        c *= (1 + 0.1 * side)[..., None] * (1 + 0.08 * m1)[..., None]
    elif kind == 2:   # ploughed earth
        r, side = rows(12, 1.6)
        c = mix(np.array([0.30, 0.20, 0.12]), np.array([0.58, 0.42, 0.27]), np.clip(r * 0.85 + 0.2 * m2, 0, 1))
        c *= (1 + 0.15 * side)[..., None] * (1 + 0.1 * m1)[..., None]
        clods = m3 > 0.55
        c[clods] *= 1.15
    elif kind == 3:   # pasture with clover
        c = mix(np.array([0.32, 0.52, 0.20]), np.array([0.56, 0.72, 0.30]), np.clip(0.5 + 0.5 * m1 + 0.3 * m2, 0, 1))
        dots = (m3 > 0.62)
        c[dots] = c[dots] * 0.5 + np.array([0.95, 0.95, 0.88]) * 0.5
    elif kind == 4:   # cabbage rows
        r, side = rows(10, 3.0)
        soil = np.array([0.40, 0.29, 0.18]) * (1 + 0.1 * m2)[..., None]
        head = np.clip(r * (0.6 + 0.6 * (pn(3, 99) > 0.0)), 0, 1)
        leaf = mix(np.array([0.30, 0.50, 0.32]), np.array([0.62, 0.78, 0.55]), np.clip(0.5 + 0.6 * m3, 0, 1))
        c = mix(soil, leaf, head)
    elif kind == 5:   # flax in flower: green stems, a haze of small sky-blue flowers
        r, side = rows(20, 1.0)
        c = mix(np.array([0.30, 0.46, 0.18]), np.array([0.50, 0.66, 0.28]), np.clip(r * 0.6 + 0.3 * m2, 0, 1))
        fl = (m3 > 0.35) & (pn(2, 55) > 0.1)
        c[fl] = c[fl] * 0.35 + np.array([0.42, 0.62, 0.98]) * 0.65
    elif kind == 6:   # rapeseed
        r, side = rows(15, 1.0)
        c = mix(np.array([0.70, 0.66, 0.15]), np.array([0.98, 0.88, 0.26]), np.clip(0.55 + 0.5 * m2 + 0.3 * m3 + 0.2 * r, 0, 1))
        c *= (1 + 0.06 * m1)[..., None]
    else:   # hay meadow, mown in wide stripes
        u = np.arange(CELL)[None, :].repeat(CELL, 0) / CELL
        stripe = (np.floor(u * 4) % 2)
        c = mix(np.array([0.50, 0.62, 0.26]), np.array([0.70, 0.74, 0.36]), np.clip(0.4 + 0.35 * stripe + 0.3 * m2 + 0.15 * m3, 0, 1))
        c *= (1 + 0.08 * m1)[..., None]
    return np.clip(c, 0, 1)


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    out = args[0] if args else "out/fields_atlas.png"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    atlas = np.zeros((CELL * 2, CELL * 4, 3))
    for k in range(8):
        r, c = divmod(k, 4)
        atlas[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] = cell(k)
    Image.fromarray((atlas * 255 + 0.5).astype(np.uint8)).save(out)
    if "--preview" in sys.argv:
        Image.open(out).resize((1024, 512)).save(os.path.splitext(out)[0] + "_preview.jpg", quality=85)
    print("mp_fields_paint: wrote", out)


if __name__ == "__main__":
    main()
