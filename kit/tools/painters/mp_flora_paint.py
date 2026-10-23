#!/usr/bin/env python3
"""Masterplan flora atlas (job 13 follow-up, K-FOR): hand-painted cards for the
meadow and pond edges, in the K-ART style (warm sunlit tips, cool shaded bases,
painted rim light; detail in the texture, the meshes are two crossed quads).

    python3 kit/tools/painters/mp_flora_paint.py [out=out/mp_flora_atlas.png] [--preview]

Atlas: 4 x 3 cells of CELL px (MpFlora.CELLS names them, same order):
  0 grass tuft   1 tall grass with seed heads   2 daisies   3 buttercups
  4 pink clover and foxglove   5 reeds with cattails   6 lily pads with a flower
  7 small lily pads (top-down, cells 6-7 lie flat on the water)
  8 flower carpet (top-down: daisies, buttercups, clover leaves)
  9 pink and violet flower carpet (top-down; cells 8-9 lie flat on the meadow)
 10 floating leaves (top-down, drawn as lily cards on the moat by the trees)
Upright cards stand on the bottom edge of their cell (the root line).
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CELL = 512
SS = 2                      # supersampling
C = CELL * SS


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def blade(d, x0, y0, h, lean, w, base, tip, rng, curl=0.35):
    """A tapered, curving blade from (x0, y0) up h px; colour base -> tip."""
    n = 14
    pts = []
    for i in range(n + 1):
        t = i / n
        x = x0 + lean * h * (t ** (1.0 + curl)) + math.sin(t * 2.0 + x0) * w * 0.3
        y = y0 - h * t + h * curl * 0.25 * t * t * abs(lean)
        pts.append((x, y, w * (1.0 - t) ** 0.8 + 0.6 * SS))
    lit = rng.random() < 0.6
    for i in range(n):
        (xa, ya, wa), (xb, yb, wb) = pts[i], pts[i + 1]
        t = (i + 0.5) / n
        col = lerp(base, tip, t ** 0.8)
        if lit and t > 0.45:
            col = lerp(col, (238, 236, 150), 0.25 * (t - 0.45) / 0.55)   # sunlit tip
        dx, dy = xb - xa, yb - ya
        L = math.hypot(dx, dy) + 1e-6
        nx, ny = -dy / L, dx / L
        poly = [(xa + nx * wa, ya + ny * wa), (xb + nx * wb, yb + ny * wb),
                (xb - nx * wb, yb - ny * wb), (xa - nx * wa, ya - ny * wa)]
        d.polygon(poly, fill=col + (255,))
        # painted rim light on one edge of the blade
        if lit:
            d.line([(xa + nx * wa * 0.7, ya + ny * wa * 0.7), (xb + nx * wb * 0.7, yb + ny * wb * 0.7)],
                   fill=lerp(col, (250, 248, 190), 0.35) + (255,), width=max(1, SS))
    return pts[-1][:2]


def tuft(d, rng, cx, n, hmin, hmax, spread, base=(38, 70, 30), tip=(150, 190, 70), wid=7):
    tops = []
    for _ in range(n):
        x0 = float(np.clip(cx + rng.normal(0, spread), C * 0.22, C * 0.78))
        h = rng.uniform(hmin, hmax)
        lean = float(np.clip((x0 - cx) / (spread * 3.0) + rng.normal(0, 0.18), -0.45, 0.45))
        b = tuple(int(c * rng.uniform(0.85, 1.1)) for c in base)
        t = tuple(min(255, int(c * rng.uniform(0.85, 1.12))) for c in tip)
        tops.append(blade(d, x0, C - 2, h, lean, wid * SS * rng.uniform(0.7, 1.2), b, t, rng))
    return tops


def flower(d, x, y, r, petals, col, centre, rng):
    for k in range(petals):
        a = k * 2 * math.pi / petals + rng.uniform(-0.2, 0.2)
        px, py = x + math.cos(a) * r * 0.9, y + math.sin(a) * r * 0.55
        shade = lerp(col, (255, 255, 255), 0.3) if math.sin(a) < 0 else lerp(col, (120, 110, 140), 0.18)
        d.ellipse([px - r * 0.55, py - r * 0.38, px + r * 0.55, py + r * 0.38], fill=shade + (255,))
    d.ellipse([x - r * 0.38, y - r * 0.3, x + r * 0.38, y + r * 0.3], fill=centre + (255,))
    d.ellipse([x - r * 0.18, y - r * 0.2, x + r * 0.05, y - r * 0.02], fill=lerp(centre, (255, 250, 210), 0.5) + (255,))


def stem(d, x0, top, rng, col=(60, 100, 40)):
    x1, y1 = top
    d.line([(x0, C - 2), ((x0 + x1) / 2 + rng.normal(0, 6 * SS), (C + y1) / 2), (x1, y1)], fill=col + (255,), width=3 * SS)


def cell_grass(rng):
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    tuft(d, rng, C / 2, 28, C * 0.18, C * 0.32, C * 0.07, base=(30, 58, 26), tip=(110, 150, 50))   # back, darker
    tuft(d, rng, C / 2, 34, C * 0.25, C * 0.55, C * 0.09)
    return im


def cell_tall(rng):
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    tuft(d, rng, C / 2, 26, C * 0.25, C * 0.5, C * 0.08, base=(40, 66, 30), tip=(150, 175, 70), wid=5)
    for _ in range(7):
        x0 = C / 2 + rng.normal(0, C * 0.08)
        top = blade(d, x0, C - 2, rng.uniform(C * 0.6, C * 0.9), rng.normal(0, 0.15), 2.2 * SS, (70, 90, 40), (180, 170, 90), rng, 0.1)
        # seed head: a soft oat-coloured spike of grains
        for k in range(14):
            gy = top[1] + k * 5 * SS
            gx = top[0] + math.sin(k * 1.7) * 6 * SS
            d.ellipse([gx - 4 * SS, gy - 6 * SS, gx + 4 * SS, gy + 6 * SS], fill=lerp((214, 196, 120), (150, 130, 70), k / 14) + (255,))
    return im


def cell_flowers(rng, col, centre, petals, size, n):
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    tuft(d, rng, C / 2, 22, C * 0.14, C * 0.32, C * 0.1)
    heads = []
    for _ in range(n):
        x0 = C / 2 + rng.normal(0, C * 0.12)
        top = (x0 + rng.normal(0, C * 0.04), C - rng.uniform(C * 0.3, C * 0.62))
        stem(d, x0, top, rng)
        heads.append(top)
    for x, y in sorted(heads, key=lambda p: p[1]):
        c = tuple(min(255, int(v * rng.uniform(0.9, 1.08))) for v in col)
        flower(d, x, y, size * SS * rng.uniform(0.8, 1.2), petals, c, centre, rng)
    return im


def cell_pink(rng):
    im = cell_flowers(rng, (226, 120, 170), (250, 210, 120), 6, 19, 7)
    d = ImageDraw.Draw(im)
    for _ in range(3):   # foxglove spikes: bells stacked up a stem
        x0 = C / 2 + rng.normal(0, C * 0.12)
        h = rng.uniform(C * 0.55, C * 0.85)
        stem(d, x0, (x0, C - h), rng)
        for k in range(9):
            y = C - h + k * h * 0.06
            r = (7 + k * 0.9) * SS
            col = lerp((190, 110, 210), (150, 70, 160), k / 9)
            d.ellipse([x0 - r, y - r * 0.6, x0 + r, y + r * 0.6], fill=col + (255,))
            d.ellipse([x0 - r * 0.4, y - r * 0.4, x0 + r * 0.1, y], fill=lerp(col, (255, 230, 250), 0.45) + (255,))
    return im


def cell_reeds(rng):
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for _ in range(24):
        x0 = C / 2 + rng.normal(0, C * 0.09)
        blade(d, x0, C - 2, rng.uniform(C * 0.5, C * 0.95), rng.normal(0, 0.12), 6 * SS, (36, 70, 44), (120, 160, 80), rng, 0.15)
    for _ in range(5):   # cattails
        x0 = C / 2 + rng.normal(0, C * 0.07)
        top = (x0 + rng.normal(0, 8 * SS), C * rng.uniform(0.03, 0.2))
        d.line([(x0, C - 2), top], fill=(70, 96, 50, 255), width=3 * SS)
        x, y = top
        d.rounded_rectangle([x - 9 * SS, y + 8 * SS, x + 9 * SS, y + 70 * SS], radius=9 * SS, fill=(112, 70, 40, 255))
        d.rounded_rectangle([x - 9 * SS, y + 8 * SS, x - 2 * SS, y + 66 * SS], radius=6 * SS, fill=(150, 100, 60, 255))
        d.line([(x, y + 8 * SS), (x, y - 14 * SS)], fill=(90, 80, 50, 255), width=2 * SS)
    return im


def pad(d, x, y, r, rot, rng):
    base = (58, 110, 50)
    a0 = rot
    pts = []
    for k in range(48):
        a = a0 + 0.28 + k * (2 * math.pi - 0.56) / 47
        rr = r * (1.0 + 0.03 * math.sin(a * 5))
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    pts.append((x, y))
    d.polygon(pts, fill=base + (255,))
    # painted volume: lit upper-left rim, darker lower-right, radial veins
    d.polygon([(x + (px - x) * 0.92, y + (py - y) * 0.92) for px, py in pts], fill=(76, 132, 58, 255))
    for k in range(9):
        a = a0 + 0.5 + k * (2 * math.pi - 1.0) / 8
        d.line([(x, y), (x + math.cos(a) * r * 0.85, y + math.sin(a) * r * 0.85)], fill=(96, 150, 70, 255), width=2 * SS)
    d.arc([x - r * 0.95, y - r * 0.95, x + r * 0.95, y + r * 0.95], 190, 300, fill=(170, 200, 110, 255), width=3 * SS)
    d.arc([x - r * 0.97, y - r * 0.97, x + r * 0.97, y + r * 0.97], 10, 120, fill=(34, 70, 36, 255), width=3 * SS)


def cell_lily(rng, flower_on):
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    spots = [(0.35, 0.4, 0.22), (0.68, 0.33, 0.16), (0.6, 0.7, 0.2), (0.27, 0.75, 0.12)] if flower_on else \
            [(0.3, 0.3, 0.13), (0.65, 0.35, 0.11), (0.45, 0.65, 0.15), (0.78, 0.72, 0.09), (0.2, 0.7, 0.08)]
    for sx, sy, sr in spots:
        pad(d, sx * C, sy * C, sr * C, rng.uniform(0, 2 * math.pi), rng)
    if flower_on:
        x, y = 0.5 * C, 0.48 * C
        for ring, (n, r, col) in enumerate([(10, 46, (250, 236, 240)), (8, 32, (246, 200, 214)), (6, 18, (255, 246, 200))]):
            for k in range(n):
                a = k * 2 * math.pi / n + ring * 0.3
                px, py = x + math.cos(a) * r * SS * 0.6, y + math.sin(a) * r * SS * 0.6
                d.ellipse([px - 13 * SS, py - 13 * SS, px + 13 * SS, py + 13 * SS], fill=col + (255,))
        d.ellipse([x - 9 * SS, y - 9 * SS, x + 9 * SS, y + 9 * SS], fill=(240, 196, 70, 255))
    return im


def cell_carpet(rng, palette):
    """Top-down scatter of tiny flowers and clover over a soft round patch."""
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = []
    while len(pts) < 70:
        x, y = rng.uniform(0.08, 0.92) * C, rng.uniform(0.08, 0.92) * C
        if math.hypot(x - C / 2, y - C / 2) < C * 0.44:
            pts.append((x, y))
    for x, y in pts[:30]:   # clover trefoils under the flowers
        g = lerp((70, 120, 40), (130, 170, 60), rng.uniform(0, 1))
        for k in range(3):
            a = k * 2 * math.pi / 3 + rng.uniform(0, 1)
            r = 9 * SS
            d.ellipse([x + math.cos(a) * r - r, y + math.sin(a) * r - r, x + math.cos(a) * r + r, y + math.sin(a) * r + r], fill=g + (255,))
    for x, y in pts[30:]:
        col, centre = palette[int(rng.integers(len(palette)))]
        flower(d, x, y, rng.uniform(9, 15) * SS, int(rng.integers(5, 9)), col, centre, rng)
    return im


def cell_leaves(rng):
    """Top-down: a few fallen leaves floating together, autumn and late-summer colours,
    a darker wet rim and a midrib on each (Z-FLORA water pass: leaves on the moat)."""
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cols = [(196, 150, 52), (170, 86, 38), (122, 84, 46), (138, 150, 60), (206, 120, 40)]
    for _ in range(11):
        r0 = rng.uniform(0.0, 0.33) * C
        a0 = rng.uniform(0, 2 * math.pi)
        x, y = C / 2 + math.cos(a0) * r0, C / 2 + math.sin(a0) * r0
        L = rng.uniform(60, 110) * SS
        w = L * rng.uniform(0.32, 0.45)
        ang = rng.uniform(0, 2 * math.pi)
        ca, sa = math.cos(ang), math.sin(ang)
        col = cols[int(rng.integers(len(cols)))]
        pts = []
        for k in range(17):
            t = k / 16
            r = w * math.sin(t * math.pi) ** 0.8
            pts.append((x + ca * (t - 0.5) * L - sa * r, y + sa * (t - 0.5) * L + ca * r))
        for k in range(15, 0, -1):
            t = k / 16
            r = w * math.sin(t * math.pi) ** 0.8
            pts.append((x + ca * (t - 0.5) * L + sa * r, y + sa * (t - 0.5) * L - ca * r))
        d.polygon(pts, fill=lerp(col, (40, 30, 20), 0.35) + (255,))
        inner = [(x + (px - x) * 0.86, y + (py - y) * 0.86) for px, py in pts]
        d.polygon(inner, fill=lerp(col, (255, 240, 200), rng.uniform(0.0, 0.18)) + (255,))
        d.line([(x - ca * L * 0.5, y - sa * L * 0.5), (x + ca * L * 0.45, y + sa * L * 0.45)], fill=lerp(col, (60, 40, 20), 0.5) + (255,), width=2 * SS)
        d.line([(x - ca * L * 0.5, y - sa * L * 0.5), (x - ca * L * 0.62, y - sa * L * 0.62)], fill=(90, 60, 30, 255), width=2 * SS)
    return im


def finish(im):
    im = im.resize((CELL, CELL), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    # bleed colour into transparent texels (mips keep the painted edge, no dark halo)
    rgb, al = a[..., :3], a[..., 3:] / 255.0
    acc, w = rgb * al, al
    for r in (2, 6, 16):
        acc = acc + np.asarray(Image.fromarray((rgb * al).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32)
        w = w + np.asarray(Image.fromarray((al[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32)[..., None] / 255.0
    fill = acc / np.maximum(w, 1e-3)
    out = np.where(al > 0.5, rgb, fill)
    return Image.fromarray(np.dstack([out, a[..., 3]]).clip(0, 255).astype(np.uint8))


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    out = args[0] if args else "out/mp_flora_atlas.png"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    rng = np.random.default_rng(1307)
    cells = [cell_grass(rng), cell_tall(rng),
             cell_flowers(rng, (246, 244, 236), (240, 190, 50), 11, 22, 11),
             cell_flowers(rng, (250, 214, 60), (220, 150, 40), 5, 19, 12),
             cell_pink(rng), cell_reeds(rng), cell_lily(rng, True), cell_lily(rng, False),
             cell_carpet(rng, [((248, 246, 238), (240, 190, 50)), ((250, 214, 60), (220, 150, 40))]),
             cell_carpet(rng, [((230, 130, 180), (250, 220, 130)), ((180, 140, 230), (250, 230, 140)), ((248, 246, 238), (240, 190, 50))]),
             cell_leaves(rng)]
    atlas = Image.new("RGBA", (CELL * 4, CELL * 3), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        atlas.paste(finish(c), ((i % 4) * CELL, (i // 4) * CELL))
    atlas.save(out)
    if "--preview" in sys.argv:
        bg = Image.new("RGBA", atlas.size, (52, 60, 74, 255))
        bg.alpha_composite(atlas)
        bg.convert("RGB").resize((1024, 768)).save(os.path.splitext(out)[0] + "_preview.jpg", quality=85)
    print("mp_flora_paint: wrote", out)


if __name__ == "__main__":
    main()
