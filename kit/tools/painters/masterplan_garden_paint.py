"""Paints the library front-court garden textures (MpLibGarden, design review: "real
flowering plants", "clipped box hedges need a leafy texture", "soil and mulch texture").

    python kit/tools/painters/masterplan_garden_paint.py [out_dir]

out/
  plants.png   4 x 3 atlas of alpha cards (MpFlora's card layout and shader): one plant
               per cell, rooted at the cell's bottom edge
               0 lavender   1 rose shrub, pink   2 rose shrub, crimson   3 shasta daisies
               4 tulips, red and yellow   5 tulips, pink and white   6 delphiniums, blue
               7 leafy cushion with white flowers   8 catmint, violet   9 marigolds
  hedge.png    tileable clipped-box leaves (small-leaf noise, value variation)
  hedge_n.png  its normal map
  mulch.png    tileable bark mulch over dark soil
  mulch_n.png  its normal map
Seeded, so the output is the same every run.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
CELL = 512          # painted at 2x, saved at 256 a cell
rng = np.random.default_rng(4407)


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def jitter(c, k=18):
    return tuple(int(np.clip(v + rng.integers(-k, k + 1), 0, 255)) for v in c)


def shade(c, f):
    return tuple(int(np.clip(v * f, 0, 255)) for v in c)


def leaf(d, x, y, length, width, ang, col):
    """A pointed leaf (lens shape) from its base at (x, y)."""
    pts = []
    for i in range(13):
        t = i / 12.0
        w = math.sin(t * math.pi) * width * (1.0 - 0.3 * t)
        pts.append((t * length, w))
    for i in range(12, -1, -1):
        t = i / 12.0
        w = math.sin(t * math.pi) * width * (1.0 - 0.3 * t)
        pts.append((t * length, -w))
    ca, sa = math.cos(ang), math.sin(ang)
    poly = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]
    d.polygon(poly, fill=col + (255,))
    # midrib, a touch lighter
    d.line([(x, y), (x + length * 0.85 * ca, y + length * 0.85 * sa)], fill=shade(col, 1.25) + (255,), width=max(1, int(width * 0.18)))


def stem(d, x0, y0, x1, y1, col, w=3):
    mx = (x0 + x1) / 2 + rng.uniform(-8, 8)
    pts = []
    for i in range(9):
        t = i / 8.0
        x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1
        y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * ((y0 + y1) / 2) + t * t * y1
        pts.append((x, y))
    d.line(pts, fill=col + (255,), width=w)


def foliage(d, cx, base, spread, height, cols, n, lw=(40, 70), ww=(10, 18), up=True):
    """A clump of leaves rising from the base line, darker inside, lighter outside."""
    for i in range(n):
        t = i / max(1, n - 1)
        x = cx + rng.uniform(-spread, spread) * (0.4 + 0.6 * t)
        y = base - rng.uniform(0, height * 0.35) * t
        ang = -math.pi / 2 + rng.uniform(-1.2, 1.2) * (0.5 + 0.5 * t) if up else rng.uniform(0, math.tau)
        col = jitter(cols[min(len(cols) - 1, int(t * len(cols)))], 10)
        leaf(d, x, y, rng.uniform(*lw), rng.uniform(*ww), ang, col)


def bloom_round(d, x, y, r, col, centre=None):
    """A rose-like round bloom: dark outer cup, lighter swirled centre."""
    d.ellipse([x - r, y - r * 0.85, x + r, y + r * 0.85], fill=shade(col, 0.72) + (255,))
    d.ellipse([x - r * 0.8, y - r * 0.75, x + r * 0.8, y + r * 0.6], fill=col + (255,))
    for k in range(3):
        rr = r * (0.55 - 0.15 * k)
        d.arc([x - rr, y - rr * 0.8 - k * 2, x + rr, y + rr * 0.8 - k * 2], 200, 520, fill=shade(col, 1.25 + 0.1 * k) + (255,), width=3)
    if centre:
        d.ellipse([x - r * 0.18, y - r * 0.2, x + r * 0.18, y + r * 0.1], fill=centre + (255,))


def daisy(d, x, y, r, petal, eye):
    for k in range(12):
        a = k * math.tau / 12 + rng.uniform(-0.1, 0.1)
        px, py = x + math.cos(a) * r * 0.55, y + math.sin(a) * r * 0.45
        d.ellipse([px - r * 0.32, py - r * 0.16, px + r * 0.32, py + r * 0.16], fill=jitter(petal, 8) + (255,))
    d.ellipse([x - r * 0.28, y - r * 0.24, x + r * 0.28, y + r * 0.24], fill=eye + (255,))


def tulip(d, x, y, r, col):
    d.ellipse([x - r * 0.62, y - r * 0.4, x + r * 0.62, y + r * 0.9], fill=shade(col, 0.82) + (255,))
    for k in (-1, 0, 1):
        d.polygon([(x + k * r * 0.42 - r * 0.32, y + r * 0.3), (x + k * r * 0.42, y - r * 0.85 + abs(k) * r * 0.25), (x + k * r * 0.42 + r * 0.32, y + r * 0.3)],
                  fill=shade(col, 1.0 + 0.12 * (k == 0)) + (255,))


def spike(d, x, base, h, col, w=10):
    """A flower spike (lavender, delphinium): florets stacked up a stem, tapering."""
    stem(d, x, base, x + rng.uniform(-6, 6), base - h, hexc("#5b7a46"), 3)
    n = int(h / (w * 0.7))
    for i in range(n):
        t = i / max(1, n - 1)
        yy = base - h * (0.35 + 0.65 * t)
        ww = w * (1.0 - 0.6 * t)
        for s in (-1, 1):
            c = jitter(shade(col, 0.85 + 0.3 * rng.random()), 10)
            d.ellipse([x + s * ww * 0.45 - ww * 0.5, yy - ww * 0.45, x + s * ww * 0.45 + ww * 0.5, yy + ww * 0.45], fill=c + (255,))


def cell_img():
    return Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))


LEAVES = [hexc("#2f5228"), hexc("#3f6a32"), hexc("#55843e"), hexc("#6b9a4a")]
GREY = [hexc("#4c6650"), hexc("#647e66"), hexc("#7f9a80")]


def p_lavender():
    im = cell_img(); d = ImageDraw.Draw(im)
    foliage(d, 256, 505, 150, 140, GREY, 60, lw=(50, 90), ww=(5, 8))
    for i in range(26):
        x = 256 + rng.normal(0, 70)
        spike(d, x, 470 - rng.uniform(0, 40), rng.uniform(220, 330), hexc("#7a5cc4"), 13)
    return im


def p_rose(col):
    im = cell_img(); d = ImageDraw.Draw(im)
    foliage(d, 256, 508, 190, 260, LEAVES, 150, lw=(30, 52), ww=(12, 20), up=True)
    # a full leafy dome down to the base clump (no gap under it)
    for i in range(190):
        a = rng.uniform(0, math.tau)
        rr = rng.uniform(0, 1) ** 0.5
        x = 256 + math.cos(a) * 200 * rr
        y = 350 + math.sin(a) * 150 * rr
        leaf(d, x, y, rng.uniform(26, 42), rng.uniform(10, 16), rng.uniform(0, math.tau), jitter(LEAVES[rng.integers(1, 4)], 10))
    for i in range(16):
        a = rng.uniform(math.pi * 1.05, math.pi * 1.95)
        rr = rng.uniform(0.35, 1.0)
        bloom_round(d, 256 + math.cos(a) * 180 * rr, 340 + math.sin(a) * 150 * rr, rng.uniform(26, 36), jitter(col, 12))
    return im


def p_daisies():
    im = cell_img(); d = ImageDraw.Draw(im)
    foliage(d, 256, 508, 170, 120, LEAVES[1:], 70, lw=(40, 80), ww=(7, 11))
    for i in range(30):
        x = 256 + rng.normal(0, 75)
        top = rng.uniform(150, 290)
        stem(d, x + rng.uniform(-10, 10), 500, x, 500 - top, hexc("#5f8a44"), 4)
        daisy(d, x, 500 - top, rng.uniform(34, 46), hexc("#f6f3ea"), hexc("#e8b830"))
    return im


def p_tulips(cols):
    im = cell_img(); d = ImageDraw.Draw(im)
    for i in range(14):
        x = 256 + rng.normal(0, 70)
        leaf(d, x, 508, rng.uniform(120, 170), rng.uniform(18, 26), -math.pi / 2 + rng.uniform(-0.5, 0.5), jitter(hexc("#5b8a4a"), 10))
    for i in range(15):
        x = 256 + rng.normal(0, 80)
        top = rng.uniform(230, 340)
        stem(d, x, 505, x + rng.uniform(-12, 12), 505 - top, hexc("#5f8a44"), 5)
        tulip(d, x, 505 - top, rng.uniform(26, 32), jitter(cols[i % len(cols)], 10))
    return im


def p_delphinium():
    im = cell_img(); d = ImageDraw.Draw(im)
    foliage(d, 256, 508, 150, 160, LEAVES, 80, lw=(40, 70), ww=(14, 22))
    for i in range(7):
        x = 256 + rng.normal(0, 60)
        spike(d, x, 430, rng.uniform(300, 400), hexc("#4f6ed8") if i % 3 else hexc("#7a62d0"), 26)
    return im


def p_cushion():
    im = cell_img(); d = ImageDraw.Draw(im)
    for i in range(170):
        a = rng.uniform(math.pi, math.tau)
        rr = rng.uniform(0, 1) ** 0.6
        x = 256 + math.cos(a) * 230 * rr
        y = 500 + math.sin(a) * 210 * rr
        leaf(d, x, y, rng.uniform(26, 44), rng.uniform(11, 17), rng.uniform(0, math.tau), jitter(LEAVES[rng.integers(0, 4)], 12))
    for i in range(34):
        a = rng.uniform(math.pi * 1.05, math.pi * 1.95)
        rr = rng.uniform(0.2, 1.0)
        daisy(d, 256 + math.cos(a) * 210 * rr, 500 + math.sin(a) * 190 * rr, rng.uniform(12, 17), hexc("#fbfaf4"), hexc("#f0d050"))
    return im


def p_catmint():
    im = cell_img(); d = ImageDraw.Draw(im)
    foliage(d, 256, 508, 210, 150, GREY, 120, lw=(30, 50), ww=(10, 15))
    for i in range(40):
        x = 256 + rng.normal(0, 95)
        spike(d, x, 480, rng.uniform(140, 230), hexc("#8a7ad8"), 9)
    return im


def p_marigold():
    im = cell_img(); d = ImageDraw.Draw(im)
    foliage(d, 256, 508, 200, 130, LEAVES, 110, lw=(26, 44), ww=(9, 14))
    for i in range(140):
        a = rng.uniform(0, math.tau)
        rr = rng.uniform(0, 1) ** 0.5
        leaf(d, 256 + math.cos(a) * 200 * rr, 440 + math.sin(a) * 70 * rr, rng.uniform(24, 38), rng.uniform(9, 13), rng.uniform(0, math.tau), jitter(LEAVES[rng.integers(0, 4)], 10))
    for i in range(22):
        a = rng.uniform(math.pi * 1.05, math.pi * 1.95)
        rr = rng.uniform(0.2, 1.0)
        x, y = 256 + math.cos(a) * 190 * rr, 440 + math.sin(a) * 90 * rr
        col = jitter(hexc("#f0a020") if i % 2 else hexc("#e86a1a"), 12)
        bloom_round(d, x, y, rng.uniform(20, 28), col, hexc("#9a4a10"))
    return im


def tile_noise(size, cells, seed):
    g = np.random.default_rng(seed)
    base = g.random((cells, cells))
    img = Image.fromarray((base * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
    return np.asarray(img, np.float32) / 255.0


def normal_from(hgt, k=3.0):
    gx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * k
    gy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * k
    n = np.dstack([-gx, -gy, np.ones_like(hgt)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB")


def tileable_leaves(size, cols, n, lw, ww, dark_bg):
    """Leaves scattered over a torus (drawn 3x3 and cropped) so the tile repeats."""
    big = Image.new("RGB", (size * 3, size * 3), dark_bg)
    hgt = Image.new("L", (size * 3, size * 3), 40)
    d = ImageDraw.Draw(big)
    dh = ImageDraw.Draw(hgt)
    pts = [(rng.uniform(0, size), rng.uniform(0, size), rng.uniform(0, math.tau), rng.uniform(*lw), rng.uniform(*ww), rng.integers(0, len(cols)), rng.uniform(0.75, 1.2)) for _ in range(n)]
    for ox in (0, size, size * 2):
        for oy in (0, size, size * 2):
            for (x, y, a, l, w, ci, v) in pts:
                c = shade(cols[ci], v)
                leaf(d, ox + x, oy + y, l, w, a, c)
                g = int(80 + 150 * (v - 0.75) / 0.45)
                ca, sa = math.cos(a), math.sin(a)
                dh.ellipse([ox + x + l * 0.5 * ca - w, oy + y + l * 0.5 * sa - w, ox + x + l * 0.5 * ca + w, oy + y + l * 0.5 * sa + w], fill=g)
    big = big.crop((size, size, size * 2, size * 2))
    hgt = hgt.crop((size, size, size * 2, size * 2)).filter(ImageFilter.GaussianBlur(1.2))
    return big, np.asarray(hgt, np.float32) / 255.0


def main():
    os.makedirs(OUT, exist_ok=True)
    cells = [p_lavender(), p_rose(hexc("#e0708a")), p_rose(hexc("#a8182c")), p_daisies(),
             p_tulips([hexc("#d82828"), hexc("#f0c020")]), p_tulips([hexc("#f088a8"), hexc("#f6f2e8")]),
             p_delphinium(), p_cushion(), p_catmint(), p_marigold()]
    atlas = Image.new("RGBA", (CELL * 4, CELL * 3), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        # soften the alpha edge a touch, then bleed colour under transparent pixels so
        # the mipmaps do not fringe black
        atlas.paste(c, ((i % 4) * CELL, (i // 4) * CELL))
    arr = np.asarray(atlas, np.float32)
    a = arr[..., 3:4] / 255.0
    rgb = Image.fromarray(arr[..., :3].astype(np.uint8))
    blur = np.asarray(rgb.filter(ImageFilter.GaussianBlur(6)), np.float32)
    cov = np.asarray(Image.fromarray((a[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)[..., None] / 255.0
    bleed = np.where(cov > 0.01, blur / np.maximum(cov, 0.01), 0.0)
    out = arr[..., :3] * a + np.clip(bleed, 0, 255) * (1 - a)
    rgba = np.dstack([out, arr[..., 3]]).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").resize((CELL * 2, CELL * 3 // 2), Image.LANCZOS).save(os.path.join(OUT, "plants.png"), optimize=True)
    hedge, hh = tileable_leaves(256, [hexc("#2c4f26"), hexc("#3b6430"), hexc("#4c7a3a"), hexc("#5f8c44")], 900, (9, 15), (4, 6), hexc("#1c3218"))
    hedge.save(os.path.join(OUT, "hedge.png"), optimize=True)
    normal_from(hh, 4.0).save(os.path.join(OUT, "hedge_n.png"), optimize=True)
    # mulch: bark chips (warm browns) over dark soil, a few pale wood flecks
    mulch, mh = tileable_leaves(256, [hexc("#5a3e26"), hexc("#6e4c2e"), hexc("#4a3220"), hexc("#7e5a36"), hexc("#3a281a")], 700, (8, 16), (3, 6), hexc("#2a1e14"))
    m = np.asarray(mulch, np.float32)
    m *= (0.85 + 0.3 * tile_noise(256, 8, 11))[..., None]
    Image.fromarray(np.clip(m, 0, 255).astype(np.uint8)).save(os.path.join(OUT, "mulch.png"), optimize=True)
    normal_from(mh, 3.0).save(os.path.join(OUT, "mulch_n.png"), optimize=True)
    print("painted", OUT)


main()
