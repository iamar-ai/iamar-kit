#!/usr/bin/env python3
"""Herb cards for the library's herb garden HERB01 (18:40 gate, point 2: "the herbs are
uniform blue-green blobs in grid rows; give each herb its shape and colour"). Painted in
the K-ART style of kit/tools/painters/mp_flora_paint.py (warm sunlit tips, cool shaded bases, painted
rim light; detail in the texture, the meshes are two crossed quads) and drawn by
MpHerbGarden with the mp_flora shader.

    python3 kit/tools/painters/mp_herb_paint.py [out=out/mp_herb_atlas.png] [--preview]

Atlas: 4 x 3 cells like the flora atlas (the shader maps cell c to column c % 4, row c / 4);
eight herbs, same order as MpHerbGarden.CARD:
  0 lavender  grey-green mound, many violet spikes
  1 rosemary  upright woody stems of dark needles, pale blue flecks
  2 sage      mound of broad grey-green oval leaves, violet spike
  3 thyme     low wide mat of tiny leaves, pink flower clusters
  4 mint      bright green serrated leaves on upright stems, mauve tips
  5 chamomile feathery green with white daisies on thin stems
  6 fennel    tall feathery fronds with yellow umbels
  7 foxglove  one tall spike of pink bells over a leaf rosette
Top-down mats (Z-FLORA, the maintainer F4 20261011-205928 "more herbs ... instead of empty dirt":
from a raised camera the upright cards are edge-on and the beds read as bare soil). Cells
8-11 lie flat on the soil under the upright cards, an irregular leafy patch each:
  8 leafy mat  bright serrated leaves in rosettes, mauve tips (mint, foxglove rosettes)
  9 grey mat   grey-green ovals and needle sprigs, violet flecks (sage, lavender, rosemary)
 10 feathery   fine fronds with white daisies and yellow umbels (chamomile, fennel)
 11 thyme mat  tiny leaves packed tight, pink flower clusters (thyme)
Upright cards stand on the bottom edge of their cell (the root line).
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mp_flora_paint import C, CELL, SS, blade, finish, flower, lerp, stem, tuft  # noqa: E402


def new():
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def leaf(d, x, y, L, w, ang, col, rng, serrated=False):
    """An oval leaf with a lit half and a midrib."""
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    n = 16
    for i in range(n + 1):
        t = i / n
        r = w * math.sin(t * math.pi) * (1.0 + (0.12 * math.sin(t * 40) if serrated else 0.0))
        pts.append((x + ca * L * t - sa * r, y + sa * L * t + ca * r))
    for i in range(n, -1, -1):
        t = i / n
        r = w * math.sin(t * math.pi) * (1.0 + (0.12 * math.sin(t * 40 + 1) if serrated else 0.0))
        pts.append((x + ca * L * t + sa * r, y + sa * L * t - ca * r))
    lit = lerp(col, (236, 232, 150), 0.22)
    d.polygon(pts, fill=col + (255,))
    # sunlit upper half
    half = pts[: n + 1] + [pts[0]]
    d.polygon(half, fill=lit + (255,))
    d.line([(x, y), (x + ca * L, y + sa * L)], fill=lerp(col, (20, 40, 20), 0.35) + (255,), width=max(1, SS))


def mound(d, rng, cx, base_y, rx, ry, col, lit, n_leaves, leaf_len, leaf_w, serrated=False):
    """A rounded cushion of leaves: a dark body, then leaves fanned over it, lit on top."""
    d.ellipse([cx - rx, base_y - ry * 2, cx + rx, base_y], fill=lerp(col, (10, 25, 15), 0.45) + (255,))
    for _ in range(n_leaves):
        a = rng.uniform(0, math.pi)
        px = cx + math.cos(a) * rx * rng.uniform(0.0, 0.9)
        py = base_y - ry * 2 * math.sin(a) ** 0.6 * rng.uniform(0.2, 1.0) + ry * 0.1
        ang = -math.pi / 2 + (px - cx) / rx * 1.1 + rng.normal(0, 0.25)
        shade = lerp(col, lit, 0.55 * max(0.0, (base_y - py) / (ry * 2)))
        leaf(d, px, py, leaf_len * rng.uniform(0.8, 1.2), leaf_w * rng.uniform(0.8, 1.2), ang, shade, rng, serrated)


def spike(d, x, top_y, h, col, lit, rng, bells=12, bell_r=5.0, stalk=(96, 120, 70)):
    d.line([(x, C - 2), (x + rng.normal(0, 4 * SS), top_y + h * 0.5), (x, top_y)], fill=stalk + (255,), width=2 * SS)
    for k in range(bells):
        t = k / bells
        y = top_y + t * h
        r = bell_r * SS * (0.55 + 0.6 * t)
        c = lerp(lit, col, t)
        d.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], fill=c + (255,))
        d.ellipse([x - r * 0.5, y - r * 0.5, x, y - r * 0.05], fill=lerp(c, (255, 245, 250), 0.4) + (255,))


def cell_lavender(rng):
    im, d = new()
    mound(d, rng, C / 2, C - 2, C * 0.26, C * 0.14, (116, 138, 112), (190, 205, 160), 60, 42 * SS, 3.5 * SS)
    for _ in range(30):
        x = C / 2 + rng.normal(0, C * 0.16)
        h = rng.uniform(C * 0.12, C * 0.2)
        top = C - rng.uniform(C * 0.42, C * 0.62)
        spike(d, x, top, h, (108, 72, 190), (170, 140, 230), rng, 10, 3.6, (120, 140, 110))
    return im


def cell_rosemary(rng):
    im, d = new()
    for _ in range(11):
        x0 = C / 2 + rng.normal(0, C * 0.1)
        h = rng.uniform(C * 0.45, C * 0.8)
        lean = rng.normal(0, 0.14)
        d.line([(x0, C - 2), (x0 + lean * h, C - h)], fill=(96, 72, 48, 255), width=3 * SS)
        for k in range(int(h / (7 * SS))):
            t = k / max(1, h / (7 * SS))
            px, py = x0 + lean * h * t, C - h * t
            for s in (-1, 1):
                col = lerp((40, 78, 48), (110, 150, 90), t) if rng.random() < 0.7 else (60, 96, 62)
                d.line([(px, py), (px + s * rng.uniform(10, 18) * SS, py - rng.uniform(2, 8) * SS)], fill=col + (255,), width=2 * SS)
            if rng.random() < 0.12 and t > 0.4:
                d.ellipse([px - 4 * SS, py - 4 * SS, px + 4 * SS, py + 4 * SS], fill=(170, 190, 235, 255))
    return im


def cell_sage(rng):
    im, d = new()
    mound(d, rng, C / 2, C - 2, C * 0.3, C * 0.15, (138, 158, 132), (210, 220, 185), 34, 56 * SS, 13 * SS)
    for _ in range(4):
        x = C / 2 + rng.normal(0, C * 0.12)
        spike(d, x, C - rng.uniform(C * 0.5, C * 0.66), C * 0.16, (120, 90, 170), (175, 150, 215), rng, 9, 3.8, (130, 150, 120))
    return im


def cell_thyme(rng):
    im, d = new()
    # a low mat: a wide low body of tiny leaves, pink flower clusters on top
    mound(d, rng, C / 2, C - 2, C * 0.42, C * 0.075, (96, 128, 80), (190, 205, 140), 140, 12 * SS, 3 * SS)
    for _ in range(26):
        x = C / 2 + rng.normal(0, C * 0.2)
        y = C - rng.uniform(C * 0.08, C * 0.2)
        r = rng.uniform(6, 10) * SS
        d.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], fill=lerp((214, 140, 196), (240, 190, 225), rng.random()) + (255,))
    return im


def cell_mint(rng):
    im, d = new()
    for _ in range(9):
        x0 = C / 2 + rng.normal(0, C * 0.12)
        h = rng.uniform(C * 0.4, C * 0.7)
        lean = rng.normal(0, 0.12)
        d.line([(x0, C - 2), (x0 + lean * h, C - h)], fill=(70, 110, 60, 255), width=3 * SS)
        for k in range(1, int(h / (26 * SS))):
            t = k * 26 * SS / h
            px, py = x0 + lean * h * t, C - h * t
            for s in (-1, 1):
                leaf(d, px, py, 34 * SS, 11 * SS, (-0.55 if s > 0 else -2.6) + rng.normal(0, 0.2), lerp((62, 140, 60), (150, 200, 90), t), rng, True)
        d.ellipse([x0 + lean * h - 6 * SS, C - h - 10 * SS, x0 + lean * h + 6 * SS, C - h + 4 * SS], fill=(200, 180, 225, 255))
    return im


def cell_chamomile(rng):
    im, d = new()
    tuft(d, rng, C / 2, 40, C * 0.12, C * 0.3, C * 0.12, base=(60, 100, 44), tip=(150, 190, 90), wid=2.2)
    heads = []
    for _ in range(12):
        x0 = C / 2 + rng.normal(0, C * 0.14)
        top = (x0 + rng.normal(0, C * 0.05), C - rng.uniform(C * 0.32, C * 0.6))
        stem(d, x0, top, rng, (80, 120, 60))
        heads.append(top)
    for x, y in sorted(heads, key=lambda p: p[1]):
        flower(d, x, y, 13 * SS * rng.uniform(0.8, 1.15), 12, (248, 246, 236), (240, 196, 50), rng)
    return im


def cell_fennel(rng):
    im, d = new()
    for _ in range(14):
        x0 = C / 2 + rng.normal(0, C * 0.09)
        h = rng.uniform(C * 0.5, C * 0.92)
        lean = rng.normal(0, 0.1)
        top = blade(d, x0, C - 2, h, lean, 2.2 * SS, (90, 130, 60), (170, 200, 90), rng, 0.12)
        for k in range(int(h / (16 * SS))):   # feathery side fronds
            t = (k + 0.5) * 16 * SS / h
            px, py = x0 + lean * h * t, C - h * t
            for s in (-1, 1):
                blade(d, px, py, rng.uniform(16, 30) * SS, s * rng.uniform(0.9, 1.6), 1.2 * SS, (90, 130, 60), (190, 210, 110), rng, 0.1)
        if rng.random() < 0.5:   # yellow umbel
            for k in range(10):
                a = k * 2 * math.pi / 10
                fx, fy = top[0] + math.cos(a) * 11 * SS, top[1] + math.sin(a) * 6 * SS
                d.ellipse([fx - 3 * SS, fy - 3 * SS, fx + 3 * SS, fy + 3 * SS], fill=(236, 206, 70, 255))
    return im


def cell_foxglove(rng):
    im, d = new()
    mound(d, rng, C / 2, C - 2, C * 0.26, C * 0.1, (82, 122, 70), (170, 200, 110), 22, 50 * SS, 14 * SS)
    for x_off in (-C * 0.1, C * 0.08):
        x = C / 2 + x_off + rng.normal(0, C * 0.03)
        h = rng.uniform(C * 0.5, C * 0.62)
        spike(d, x, C - h - C * 0.22, h, (196, 96, 150), (240, 170, 200), rng, 12, 11.0, (90, 120, 70))
    return im


def blob(rng, n=7):
    """An irregular patch: a union of offset circles round the cell centre."""
    cs = []
    for k in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(0.0, 0.2) * C
        cs.append((C / 2 + math.cos(a) * r0, C / 2 + math.sin(a) * r0, rng.uniform(0.17, 0.27) * C))
    return (lambda x, y: any(math.hypot(x - cx, y - cy) < r for cx, cy, r in cs)), cs


def mat_base(d, cs, col):
    for cx, cy, r in cs:   # a shaded under-layer so the patch has no holes in its middle
        r2 = r * 0.82
        d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=col + (255,))


def rosette(d, rng, x, y, n, L, w, col, lit, serrated=False):
    a0 = rng.uniform(0, 2 * math.pi)
    for k in range(n):
        a = a0 + k * 2 * math.pi / n + rng.normal(0, 0.2)
        leaf(d, x, y, L * rng.uniform(0.75, 1.15), w * rng.uniform(0.8, 1.2), a,
             lerp(col, lit, rng.uniform(0.0, 0.6)), rng, serrated)


def cell_mat_leafy(rng):
    im, d = new()
    inside, cs = blob(rng)
    mat_base(d, cs, (38, 74, 34))
    for _ in range(170):
        x, y = rng.uniform(0.05, 0.95) * C, rng.uniform(0.05, 0.95) * C
        if inside(x, y):
            rosette(d, rng, x, y, int(rng.integers(4, 7)), 40 * SS, 12 * SS, (58, 128, 52), (160, 206, 96), True)
            if rng.random() < 0.25:
                d.ellipse([x - 7 * SS, y - 7 * SS, x + 7 * SS, y + 7 * SS], fill=(196, 170, 222, 255))
    return im


def cell_mat_grey(rng):
    im, d = new()
    inside, cs = blob(rng)
    mat_base(d, cs, (66, 84, 64))
    for _ in range(160):
        x, y = rng.uniform(0.05, 0.95) * C, rng.uniform(0.05, 0.95) * C
        if not inside(x, y):
            continue
        if rng.random() < 0.55:
            rosette(d, rng, x, y, int(rng.integers(4, 6)), 46 * SS, 13 * SS, (122, 144, 118), (212, 222, 186))
        else:   # a needle sprig seen from above
            a = rng.uniform(0, 2 * math.pi)
            L = rng.uniform(40, 70) * SS
            for k in range(9):
                t = k / 8
                px, py = x + math.cos(a) * L * t, y + math.sin(a) * L * t
                for sgn in (-1, 1):
                    b = a + sgn * 1.1
                    d.line([(px, py), (px + math.cos(b) * 12 * SS, py + math.sin(b) * 12 * SS)],
                           fill=lerp((52, 88, 60), (130, 160, 110), t) + (255,), width=2 * SS)
        for _ in range(int(rng.integers(0, 4))):
            fx, fy = x + rng.normal(0, 20 * SS), y + rng.normal(0, 20 * SS)
            if inside(fx, fy):
                r = rng.uniform(4, 7) * SS
                d.ellipse([fx - r, fy - r, fx + r, fy + r], fill=lerp((120, 84, 196), (186, 160, 236), rng.random()) + (255,))
    return im


def cell_mat_feathery(rng):
    im, d = new()
    inside, cs = blob(rng)
    mat_base(d, cs, (52, 86, 38))
    for _ in range(420):
        x, y = rng.uniform(0.05, 0.95) * C, rng.uniform(0.05, 0.95) * C
        if inside(x, y):
            a = rng.uniform(0, 2 * math.pi)
            blade(d, x, y, rng.uniform(28, 50) * SS, math.cos(a) * 1.4, 1.6 * SS, (80, 124, 54), (176, 206, 104), rng, 0.2)
    for _ in range(70):
        x, y = rng.uniform(0.1, 0.9) * C, rng.uniform(0.1, 0.9) * C
        if not inside(x, y):
            continue
        if rng.random() < 0.65:
            flower(d, x, y, 12 * SS * rng.uniform(0.8, 1.2), 12, (248, 246, 236), (240, 196, 50), rng)
        else:
            for k in range(8):
                b = k * 2 * math.pi / 8
                fx, fy = x + math.cos(b) * 10 * SS, y + math.sin(b) * 10 * SS
                d.ellipse([fx - 3 * SS, fy - 3 * SS, fx + 3 * SS, fy + 3 * SS], fill=(236, 206, 70, 255))
    return im


def cell_mat_thyme(rng):
    im, d = new()
    inside, cs = blob(rng, 9)
    mat_base(d, cs, (64, 90, 52))
    for _ in range(900):
        x, y = rng.uniform(0.04, 0.96) * C, rng.uniform(0.04, 0.96) * C
        if inside(x, y):
            leaf(d, x, y, rng.uniform(10, 16) * SS, 3.5 * SS, rng.uniform(0, 2 * math.pi),
                 lerp((84, 118, 70), (178, 198, 132), rng.random()), rng)
    for _ in range(60):
        x, y = rng.uniform(0.08, 0.92) * C, rng.uniform(0.08, 0.92) * C
        if inside(x, y):
            for _k in range(5):
                fx, fy = x + rng.normal(0, 6 * SS), y + rng.normal(0, 6 * SS)
                r = rng.uniform(4, 7) * SS
                d.ellipse([fx - r, fy - r, fx + r, fy + r], fill=lerp((206, 128, 188), (246, 196, 230), rng.random()) + (255,))
    return im


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    out = args[0] if args else "out/mp_herb_atlas.png"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    rng = np.random.default_rng(2211)
    cells = [cell_lavender(rng), cell_rosemary(rng), cell_sage(rng), cell_thyme(rng),
             cell_mint(rng), cell_chamomile(rng), cell_fennel(rng), cell_foxglove(rng),
             cell_mat_leafy(rng), cell_mat_grey(rng), cell_mat_feathery(rng), cell_mat_thyme(rng)]
    atlas = Image.new("RGBA", (CELL * 4, CELL * 3), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        atlas.paste(finish(c), ((i % 4) * CELL, (i // 4) * CELL))
    atlas.save(out)
    if "--preview" in sys.argv:
        bg = Image.new("RGBA", atlas.size, (52, 60, 74, 255))
        bg.alpha_composite(atlas)
        bg.convert("RGB").resize((1024, 768)).save(os.path.splitext(out)[0] + "_preview.jpg", quality=85)
    print("mp_herb_paint: wrote", out)


if __name__ == "__main__":
    main()
