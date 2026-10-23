#!/usr/bin/env python3
"""Painted textures for the forest's own trees (A16, Z-FOR; kit/tools/painters/make_forest_trees.gd
builds the models that use them), in the K-ART hand-painted style: painted bevels
lit from the top left, warm sunlit tips drifting to cool blue-green shade, brushy
value mottling, no photo noise.

    python3 kit/tools/painters/forest_tree_paint.py [out_dir=out] [--preview]

Writes (RGBA, 512 px):
  Leaves_Clump_Broad.png  a round clump of overlapping painted leaves with a ragged
                          leafy outline (oak / beech crowns: one card = one clump)
  Leaves_Clump_Small.png  a looser clump of small leaves with gaps (birch)
  Leaf_Bough_Pine.png     a drooping fir bough: a twig with needle sprays both sides,
                          tip at the top of the image, base at the bottom
  Bark_Oak.png            seamless deep-furrowed grey-brown bark with moss in the cracks
  Bark_Beech.png          seamless smooth grey bark with faint rings and lichen
  Bark_Birch.png          seamless white bark with black lenticel dashes and dark scars
The leaf textures are a mid-bright green so the model's material colour and its
vertex colour (per clump hue, inner-crown shade) tint them per species.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

N = 512
LIGHT = np.array([-0.6, -0.8])          # painted light from the top left (x right, y down)
WARM = np.array([1.10, 1.03, 0.72])
COOL = np.array([0.70, 0.88, 1.0])


def noise(shape, scale, seed, wrap=True, aniso=(1.0, 1.0)):
    """Smooth random field in [-1, 1]; `scale` = feature size in px (y, x stretch)."""
    r = np.random.default_rng(seed).standard_normal(shape)
    f = ndimage.gaussian_filter(r, (scale * aniso[0], scale * aniso[1]), mode="wrap" if wrap else "reflect")
    return f / (np.abs(f).max() + 1e-6)


def lum(c):
    return c[..., 0] * 0.3 + c[..., 1] * 0.59 + c[..., 2] * 0.11


def leaf_shape(yy, xx, cx, cy, ang, ln, wd, kind):
    """Signed inside-ness (>0 inside) of one leaf in local px coordinates."""
    ca, sa = np.cos(ang), np.sin(ang)
    u = (xx - cx) * ca + (yy - cy) * sa        # along the leaf, 0 at the stalk
    v = -(xx - cx) * sa + (yy - cy) * ca
    t = u / ln
    if kind == "broad":    # oval with a soft point
        half = wd * np.sqrt(np.clip(t * (1.0 - t), 0.0, None)) * 2.0 * (1.0 - 0.25 * np.clip(t - 0.6, 0.0, 1.0))
    else:                  # small, rounder (birch: little toothed diamonds)
        half = wd * np.clip(np.minimum(t * 1.6, (1.0 - t) * 1.3), 0.0, None)
    inside = half - np.abs(v)
    return inside, t, v / (np.maximum(half, 1e-3))


def paint_clump(name, out, kind, count, radius, leaf_len, seed, gaps=0.0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    col = np.zeros((N, N, 3), np.float32)
    alpha = np.zeros((N, N), np.float32)
    c0 = N * 0.5
    # leaves from the back (inner, darker, cooler) to the front (outer top, lit, warm):
    # sort by a depth that grows toward the top-left rim, like a lit ball of leaves
    pts = []
    # a lobed outline (5-7 rounded lobes, each its own size) instead of a disc, and
    # the leaves thinning out toward it, so the clump's edge reads as single leaves
    lobes = int(rng.integers(5, 8))
    lph = rng.uniform(0, 2 * np.pi)
    lamp = rng.uniform(0.7, 1.0, lobes)
    for i in range(count):
        a = rng.uniform(0, 2 * np.pi)
        k = (a + lph) / (2 * np.pi) * lobes
        j = int(k) % lobes
        bump = np.sin((k - int(k)) * np.pi) ** 0.8 * lamp[j]
        R = radius * (0.66 + 0.34 * bump)
        r = R * rng.uniform(0.0, 1.0) ** 0.62
        if rng.uniform() < 0.12:
            r = R * rng.uniform(0.95, 1.12)   # a few strays past the outline
        cx, cy = c0 + np.cos(a) * r, c0 + np.sin(a) * r * 0.92
        if gaps > 0.0 and noise_val(cx, cy, seed) < -gaps:
            continue
        rim = min(r / R, 1.0)
        light = (-(cx - c0) * LIGHT[0] - (cy - c0) * LIGHT[1]) / radius   # +1 toward the light
        depth = rim * 0.6 + rng.uniform(0, 0.5)
        pts.append((depth, cx, cy, a, rim, light))
    pts.sort()
    for depth, cx, cy, a, rim, light in pts:
        # leaves point outward from the clump's middle (a little random), stalk inward
        ang = a + rng.normal(0.0, 0.55) if rim > 0.25 else rng.uniform(0, 2 * np.pi)
        ln = leaf_len * rng.uniform(0.75, 1.25)
        wd = ln * (0.32 if kind == "broad" else 0.42) * rng.uniform(0.85, 1.15)
        sx, sy = cx - np.cos(ang) * ln * 0.45, cy - np.sin(ang) * ln * 0.45
        x0, x1 = int(max(0, sx - ln - 2)), int(min(N, sx + ln + 2))
        y0, y1 = int(max(0, sy - ln - 2)), int(min(N, sy + ln + 2))
        if x1 <= x0 or y1 <= y0:
            continue
        sub = (slice(y0, y1), slice(x0, x1))
        ins, t, vn = leaf_shape(yy[sub], xx[sub], sx, sy, ang, ln, wd, kind)
        m = np.clip(ins * 0.9, 0.0, 1.0)
        if m.max() <= 0.0:
            continue
        # this leaf's colour: lit or shaded by where it sits in the clump, + its own jitter
        lit = np.clip(0.5 + 0.45 * light + 0.25 * (depth - 0.5), 0.0, 1.0)
        base = np.array([0.36, 0.60, 0.17]) * rng.uniform(0.85, 1.12)
        base = base * (1.0 + (WARM - 1.0) * lit) * (1.0 + (COOL - 1.0) * (1.0 - lit))
        base[0] *= rng.uniform(0.9, 1.15)
        val = 0.62 + 0.5 * lit
        # painted bevel across the leaf (one half lit, the other shaded) + a midrib
        side = np.sign(np.sin(ang) * LIGHT[0] * -1 + np.cos(ang) * LIGHT[1] * 0.0 + 1e-3)
        bevel = 1.0 + 0.16 * vn * side * -1.0
        tipglow = 1.0 + 0.18 * np.clip(t - 0.55, 0.0, 1.0)
        rib = 1.0 - 0.14 * np.exp(-(vn * 6.0) ** 2) * (t > 0.08) * (t < 0.9)
        c = base[None, None, :] * (val * bevel * tipglow * rib)[..., None]
        # darker rim line where this leaf overlaps the ones behind (painted edge)
        edge = np.clip(ins * 0.35, 0.0, 1.0)
        c = c * (0.72 + 0.28 * edge)[..., None]
        a_old = alpha[sub]
        col[sub] = col[sub] * (1.0 - m[..., None]) + c * m[..., None]
        alpha[sub] = np.maximum(a_old, m)
    # brushy value mottling, soft inner shade toward the bottom right of the clump
    mott = 1.0 + 0.07 * noise((N, N), 6.0, seed + 1, wrap=False)
    d = np.hypot(xx - c0, yy - c0) / radius
    inner = 1.0 - 0.18 * np.clip(1.0 - d, 0.0, 1.0) * np.clip((yy - c0) / radius + 0.3, 0.0, 1.0)
    col = np.clip(col * (mott * inner)[..., None], 0.0, 1.0)
    a = (alpha > 0.5).astype(np.float32)
    # bleed colour into the cut-away pixels so mipmaps keep the leaf colours at the edge
    col = bleed(col, a)
    o = np.dstack([col, a])
    Image.fromarray((o * 255.0 + 0.5).astype(np.uint8)).save(f"{out}/{name}.png")


_gap_fields = {}


def noise_val(x, y, seed):
    if seed not in _gap_fields:
        _gap_fields[seed] = noise((N, N), 28.0, seed + 7, wrap=False)
    return _gap_fields[seed][int(np.clip(y, 0, N - 1)), int(np.clip(x, 0, N - 1))]


def bleed(col, a):
    inside = a > 0.5
    if inside.all():
        return col
    idx = ndimage.distance_transform_edt(~inside, return_distances=False, return_indices=True)
    out = col[idx[0], idx[1]]
    return np.where(inside[..., None], col, out * 0.9)


def paint_bough(name, out, seed):
    """A fir bough card: base at the bottom middle, tip at the top middle."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    col = np.zeros((N, N, 3), np.float32)
    alpha = np.zeros((N, N), np.float32)
    # the twig: from (0.5, 0.98) up to (0.5, 0.04), a gentle S
    ts = np.linspace(0.0, 1.0, 120)
    twig = np.stack([N * (0.5 + 0.03 * np.sin(ts * 3.0)), N * (0.98 - 0.94 * ts)], 1)
    # needle sprays: short strokes from the twig, angled toward the tip, longer in the middle
    for (px, py) in twig:
        x0, x1 = int(max(0, px - 5)), int(min(N, px + 5))
        y0, y1 = int(max(0, py - 5)), int(min(N, py + 5))
        sub = (slice(y0, y1), slice(x0, x1))
        m = np.clip(3.0 - np.hypot(xx[sub] - px, yy[sub] - py), 0.0, 1.0)
        col[sub] = col[sub] * (1.0 - m[..., None]) + np.array([0.22, 0.16, 0.10]) * m[..., None]
        alpha[sub] = np.maximum(alpha[sub], m)
    strokes = []
    for i, (px, py) in enumerate(twig[::2]):
        t = i / (len(twig) / 2)
        reach = N * 0.40 * np.sin(np.clip(t * 1.02, 0.0, 1.0) * np.pi) ** 0.6 + N * 0.04
        for sgn in (-1.0, 1.0):
            for k in range(5):
                ang = np.radians(-90 + sgn * rng.uniform(28, 70))
                ln = reach * rng.uniform(0.45, 1.0)
                strokes.append((rng.uniform(0, 1), px, py, ang, ln, t, sgn))
    strokes.sort()
    for depth, px, py, ang, ln, t, sgn in strokes:
        ex, ey = px + np.cos(ang) * ln, py + np.sin(ang) * ln
        x0, x1 = int(max(0, min(px, ex) - 8)), int(min(N, max(px, ex) + 8))
        y0, y1 = int(max(0, min(py, ey) - 8)), int(min(N, max(py, ey) + 8))
        if x1 <= x0 or y1 <= y0:
            continue
        sub = (slice(y0, y1), slice(x0, x1))
        dx, dy = ex - px, ey - py
        L2 = dx * dx + dy * dy + 1e-6
        u = np.clip(((xx[sub] - px) * dx + (yy[sub] - py) * dy) / L2, 0.0, 1.0)
        dist = np.hypot(xx[sub] - (px + u * dx), yy[sub] - (py + u * dy))
        w = 6.0 * (1.0 - 0.7 * u) + 1.0
        m = np.clip(w - dist, 0.0, 1.0)
        lit = np.clip(0.2 + 0.8 * depth, 0.0, 1.0)
        base = np.array([0.20, 0.44, 0.22]) * (1.0 + (WARM - 1.0) * lit * 0.7) * (1.0 + (COOL - 1.0) * (1.0 - lit))
        c = base[None, None, :] * (0.62 + 0.62 * lit) * (0.82 + 0.4 * u)[..., None] * (1.0 - 0.18 * np.clip(dist / w, 0, 1))[..., None]
        col[sub] = col[sub] * (1.0 - m[..., None]) + c * m[..., None]
        alpha[sub] = np.maximum(alpha[sub], m)
    col = np.clip(col * (1.0 + 0.06 * noise((N, N), 5.0, seed + 3, wrap=False))[..., None], 0.0, 1.0)
    a = (alpha > 0.5).astype(np.float32)
    col = bleed(col, a)
    Image.fromarray((np.dstack([col, a]) * 255.0 + 0.5).astype(np.uint8)).save(f"{out}/{name}.png")


def bark_shade(hgt, base, crack_col, moss_amt, seed):
    gy, gx = np.gradient(hgt)
    bevel = np.clip(-(gx * LIGHT[0] + gy * LIGHT[1]) * 2.5, -1.0, 1.0)
    ridge = np.clip(hgt * 0.5 + 0.5, 0.0, 1.0)
    col = base[None, None, :] * (0.78 + 0.22 * bevel + 0.35 * (ridge - 0.5))[..., None]
    col = col * (1.0 + (np.array([1.08, 1.03, 0.9]) - 1.0) * ridge[..., None])
    crack = np.clip(0.42 - ridge, 0.0, 1.0)[..., None] * 2.2
    col = col * (1.0 - 0.55 * crack) + crack * crack_col * 0.5
    moss = np.clip(noise(hgt.shape, 26.0, seed + 3) * 1.6 - 0.45, 0.0, 1.0) * (0.3 + 0.7 * (1.0 - ridge)) * moss_amt
    col = col * (1.0 - 0.6 * moss[..., None]) + moss[..., None] * np.array([0.30, 0.40, 0.12]) * 0.6
    col *= 1.0 + 0.06 * noise(hgt.shape, 10.0, seed + 5)[..., None]
    return np.clip(col, 0.0, 1.0)


def paint_bark_oak(name, out, seed):
    # long vertical plates (stretched noise) split by deep furrows and broken by
    # short cross cracks: thresholded and sharpened into chunky painted plates
    plates = noise((N, N), 5.0, seed, aniso=(7.0, 1.0)) * 0.8 + noise((N, N), 2.5, seed + 1, aniso=(4.0, 1.0)) * 0.3
    plates = (plates - plates.mean()) / (plates.std() + 1e-6)
    breaks = noise((N, N), 3.0, seed + 2, aniso=(0.35, 2.2))
    hgt = np.tanh(plates * 1.8) - 0.9 * np.clip((breaks - 0.55) * 4.0, 0.0, 1.0)
    hgt = ndimage.gaussian_filter(hgt, 0.8, mode="wrap")
    col = bark_shade(hgt, np.array([0.50, 0.45, 0.40]), np.array([0.04, 0.03, 0.05]), 0.9, seed)
    Image.fromarray((np.dstack([col, np.ones((N, N))]) * 255.0 + 0.5).astype(np.uint8)).save(f"{out}/{name}.png")


def paint_bark_beech(name, out, seed):
    hgt = noise((N, N), 18.0, seed, aniso=(0.6, 1.6)) * 0.5 + noise((N, N), 4.0, seed + 2) * 0.12
    hgt = (hgt - hgt.mean()) / (hgt.std() + 1e-6) * 0.5
    col = bark_shade(hgt, np.array([0.47, 0.45, 0.42]), np.array([0.10, 0.09, 0.10]), 0.45, seed)
    # pale lichen blotches
    lich = np.clip(noise((N, N), 9.0, seed + 9) * 2.0 - 1.0, 0.0, 1.0)
    col = col * (1.0 - 0.4 * lich[..., None]) + lich[..., None] * np.array([0.62, 0.68, 0.55]) * 0.4
    Image.fromarray((np.dstack([np.clip(col, 0, 1), np.ones((N, N))]) * 255.0 + 0.5).astype(np.uint8)).save(f"{out}/{name}.png")


def paint_bark_birch(name, out, seed):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    base = np.array([0.74, 0.73, 0.69])
    col = np.broadcast_to(base, (N, N, 3)).copy()
    col *= (1.0 + 0.05 * noise((N, N), 14.0, seed, aniso=(0.4, 2.0)))[..., None]
    col *= (1.0 - 0.06 * np.clip(noise((N, N), 3.0, seed + 1, aniso=(0.3, 3.0)), 0, 1))[..., None]
    # horizontal lenticel dashes (wrapping in x) and a few dark diamond scars
    for i in range(240):
        cx, cy = rng.uniform(0, N), rng.uniform(0, N)
        ln, th = rng.uniform(10, 46), rng.uniform(1.2, 3.2)
        for ox in (-N, 0, N):
            for oy in (-N, 0, N):
                dx = np.abs(xx - cx - ox) / ln
                dy = np.abs(yy - cy - oy) / th
                m = np.clip(1.0 - (dx ** 2 + dy ** 2), 0.0, 1.0)
                if m.max() > 0:
                    col *= (1.0 - 0.75 * m)[..., None]
    warp = noise((N, N), 6.0, seed + 8) * 0.35
    for i in range(6):
        cx, cy = rng.uniform(0, N), rng.uniform(0, N)
        w, h = rng.uniform(22, 44), rng.uniform(14, 30)
        for ox in (-N, 0, N):
            for oy in (-N, 0, N):
                d = ((xx - cx - ox) / w) ** 2 + ((yy - cy - oy) / h) ** 2 + warp
                m = np.clip((1.0 - d) * 2.5, 0.0, 1.0) * 0.85
                col = col * (1.0 - m[..., None]) + m[..., None] * np.array([0.13, 0.11, 0.10])
    col *= (1.0 + 0.05 * noise((N, N), 4.0, seed + 4))[..., None]
    Image.fromarray((np.dstack([np.clip(col, 0, 1), np.ones((N, N))]) * 255.0 + 0.5).astype(np.uint8)).save(f"{out}/{name}.png")


NAMES = ["Leaves_Clump_Broad", "Leaves_Clump_Small", "Leaf_Bough_Pine", "Bark_Oak", "Bark_Beech", "Bark_Birch"]


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    out = args[0] if args else "out"
    os.makedirs(out, exist_ok=True)
    paint_clump("Leaves_Clump_Broad", out, "broad", 460, N * 0.42, N * 0.08, 11)
    paint_clump("Leaves_Clump_Small", out, "small", 900, N * 0.42, N * 0.066, 23, gaps=0.85)
    paint_bough("Leaf_Bough_Pine", out, 31)
    paint_bark_oak("Bark_Oak", out, 41)
    paint_bark_beech("Bark_Beech", out, 53)
    paint_bark_birch("Bark_Birch", out, 67)
    if "--preview" in sys.argv:
        tiles = []
        for n in NAMES:
            t = Image.open(f"{out}/{n}.png").convert("RGBA").resize((320, 320))
            bg = Image.new("RGBA", t.size, (40, 44, 52, 255))
            bg.alpha_composite(t)
            tiles.append(bg.convert("RGB"))
        sheet = Image.new("RGB", (320 * 3, 320 * 2))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % 3) * 320, (i // 3) * 320))
        sheet.save(sys.argv[sys.argv.index("--preview") + 1] if len(sys.argv) > sys.argv.index("--preview") + 1 else f"{out}/tree_preview.jpg", quality=88)
    print("forest_tree_paint: wrote", out)


if __name__ == "__main__":
    main()
