#!/usr/bin/env python3
"""Painted hair strand textures for alpha strand-card hair (mp-WOLF, the maintainer's art bar 2026-10-10).

  python3 kit/tools/painters/strand_paint.py [out_dir] [beard]   # writes T_HairCards.png + T_HairFill.png + T_BeardFill.png

T_HairCards.png (1024 x 1024): four card clumps side by side, each 256 px wide; V runs from
the root (v = 0, top) to the tip (v = 1). Every strand is painted as a soft line that is
darker at the root and lighter toward the end, the strands of a clump draw together toward
the tip and their tips fade out (transparent), so a card has no hard edge.
  col 0  dense lock (wide, few gaps)        col 1  medium lock, gaps between strands
  col 2  wisps and flyaways (thin, sparse)  col 3  short tuft (beards, crop: tapers early)
T_HairFill.png (256 x 256, tiles both ways): the dense under-layer painted on the scalp cap
and the beard base (strands along V, no alpha), so the skin never shows between cards.
Channels (linear data, not colour): R = value (root dark .. tip light, per strand),
G = per-strand random (shifts the anisotropic highlight, shaders/hair_cards.gdshader),
B = strand core (1 at a strand's centre line: a soft cylinder for the highlight), A = alpha.
Deterministic.
"""
import os
import numpy as np
from PIL import Image

OUT = os.environ.get("PAINT_OUT", "hair_cards")   # output dir: first argument, else $PAINT_OUT, else ./hair_cards
rng = np.random.default_rng(7)


def splat(acc, xs, ys, rad, val, rnd, alpha, wrap=False):
    val = np.broadcast_to(np.asarray(val, dtype=float), np.shape(xs))
    """Soft discs along a strand (xs, ys: points); keeps the topmost strand's channels."""
    h, w = acc["a"].shape
    rads = np.broadcast_to(np.asarray(rad, dtype=float), np.shape(xs))
    r = int(np.ceil(rads.max() * 1.2)) + 1
    oy, ox = np.mgrid[-r:r + 1, -r:r + 1]
    for x, y, v, a, rad in zip(xs, ys, val, alpha, rads):
        cx, cy = int(np.floor(x)), int(np.floor(y))
        px = cx + ox
        py = cy + oy
        d = np.sqrt((px + 0.5 - x) ** 2 + (py + 0.5 - y) ** 2) / rad
        cov = np.clip(1.0 - d, 0.0, 1.0) ** 0.8 * a
        if wrap:
            px %= w
            py %= h
        else:
            m = (px >= 0) & (px < w) & (py >= 0) & (py < h)
            px, py, cov, d = px[m], py[m], cov[m], d[m]
        core = np.clip(1.0 - d, 0.0, 1.0) ** 2
        old = acc["a"][py, px]
        new = cov + old * (1.0 - cov)
        k = np.where(new > 1e-6, cov / np.maximum(new, 1e-6), 0.0)
        acc["r"][py, px] = acc["r"][py, px] * (1 - k) + v * k
        acc["g"][py, px] = acc["g"][py, px] * (1 - k) + rnd * k
        acc["b"][py, px] = np.maximum(acc["b"][py, px] * (1 - k), core * k)
        acc["a"][py, px] = new


def clump(w, h, n, width, gather, thick, length, wave, fly=0.0, taper_start=0.55):
    """One card clump: n strands across `width` (0..1 of the column), drawn root to tip."""
    acc = {c: np.zeros((h, w)) for c in "rgba"}
    cx = w * 0.5
    order = rng.permutation(n)
    for i in order:
        x0 = cx + (rng.random() - 0.5) * width * w
        L = h * length * (0.75 + 0.25 * rng.random())
        y0 = h * 0.01 * rng.random()
        steps = int(L)
        t = np.linspace(0.0, 1.0, steps)
        # the lock draws together toward its tip, with a soft S and a little wave
        xg = x0 + (cx - x0) * gather * t ** 1.4
        ph = rng.random() * 6.28
        xs = xg + np.sin(t * wave * 6.28 + ph) * w * 0.012 + (rng.random() - 0.5) * w * 0.05 * t ** 2
        if fly > 0.0 and rng.random() < fly:   # a stray hair leaving the lock
            xs += (rng.random() - 0.5) * w * 0.35 * t ** 2
        ys = y0 + t * L
        base = 0.5 + 0.5 * rng.random() ** 0.7       # strands differ: separation at a glance
        val = base * (0.7 + 0.42 * t ** 0.8)             # a little darker at the root, light ends
        # (the dark root of the whole head is the cap's; a card's root fades into what lies under it)
        tip = 1.0 - np.clip((t - taper_start) / (1.0 - taper_start), 0.0, 1.0) ** 1.6
        root = np.clip(t / 0.1, 0.0, 1.0)
        alpha = np.clip(tip, 0.0, 1.0) * root * (0.75 + 0.25 * rng.random())
        rad = thick * (0.7 + 0.6 * rng.random()) * (1.0 - 0.5 * t)
        splat(acc, xs, ys, np.maximum(rad, 0.6), val, rng.random(), alpha)
    return acc


def fill(w=512, h=1024, locks=12):
    """Tiling scalp / beard fill: locks side by side (darker grooves between them), each
    lock a bundle of strands with its own value and a gentle sway; tiles both ways."""
    acc = {c: np.zeros((h, w)) for c in "rgba"}
    acc["r"][:] = 0.18
    acc["g"][:] = 0.5
    acc["a"][:] = 1.0
    lw = w / locks
    for k in range(locks):
        cx = (k + 0.5 + (rng.random() - 0.5) * 0.4) * lw
        lv = 0.65 + 0.35 * rng.random()
        ph = rng.random() * 6.28
        for i in range(int(lw * 2.2)):
            x0 = cx + (rng.random() - 0.5) * lw * 1.05
            y0 = rng.random() * h
            t = np.linspace(0.0, 1.0, h)
            xs = x0 + np.sin(t * 6.28 + ph) * lw * 0.18 + np.sin(t * 6.28 * 3 + rng.random() * 6.28) * 1.5
            ys = y0 + t * h
            # a strand is lighter along its middle (the lock's crown) than at the lock's edge
            edge = abs(x0 - cx) / (lw * 0.55)
            v = lv * (0.55 + 0.45 * rng.random()) * (1.0 - 0.45 * min(edge, 1.0) ** 2)
            splat(acc, xs[::2], ys[::2], 1.1 + 0.7 * rng.random(), v, rng.random(), np.full(len(t[::2]), 0.85), wrap=True)
    acc["a"][:] = 1.0
    return acc


def beard_fill(w=512, h=512):
    """Z-FIX r15 (A30 gate: the beard read as woodgrain): a tiling beard fill of short
    clumped tufts, not long parallel grain. Staggered rows of tufts, each a bundle of
    strands of varied thickness that leave the skin dark at the root, curl a little and
    gather toward a lighter tip; between tufts the dark shadow of the skin under the
    beard. Tiles both ways; same channels as the fill (R value, G strand random, B core)."""
    r2 = np.random.default_rng(23)
    acc = {c: np.zeros((h, w)) for c in "rgba"}
    acc["r"][:] = 0.2           # the shadow under the beard (0.06 read as a near-black mass)
    acc["g"][:] = 0.5
    acc["a"][:] = 1.0
    rows, per = 9, 11
    for row in range(rows):
        for k in range(per):
            cx = (k + 0.5 + (r2.random() - 0.5) * 0.7 + (0.5 if row % 2 else 0.0)) * w / per
            cy = (row + (r2.random() - 0.5) * 0.6) * h / rows
            L = h * (0.2 + 0.18 * r2.random())          # a tuft spans 20-38 % of the tile
            lw = w / per * (0.55 + 0.4 * r2.random())
            curl = (r2.random() - 0.5) * lw * 0.9
            tv = 0.7 + 0.3 * r2.random()
            for i in range(int(14 + 16 * r2.random())):
                x0 = cx + (r2.random() - 0.5) * lw
                t = np.linspace(0.0, 1.0, int(L))
                xs = x0 + (cx + curl - x0) * 0.55 * t ** 1.3 + curl * 0.4 * t * t + np.sin(t * 9.0 + r2.random() * 6.28) * 0.8
                ys = cy + r2.random() * L * 0.15 + t * L
                val = tv * (0.45 + 0.6 * t ** 0.7) * (0.8 + 0.2 * r2.random())
                rad = (0.8 + 1.4 * r2.random() ** 2) * (1.0 - 0.45 * t)
                a = np.clip(t / 0.08, 0.0, 1.0) * (1.0 - np.clip((t - 0.75) / 0.25, 0.0, 1.0) ** 1.5) * 0.95
                splat(acc, xs[::2], ys[::2], np.maximum(rad[::2], 0.6), val[::2], r2.random(), a[::2], wrap=True)
    acc["a"][:] = 1.0
    return acc


def to_img(acc):
    rgba = np.stack([acc[c] for c in "rgba"], -1)
    return Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")


def main():
    global OUT
    import sys
    args = sys.argv[1:]
    if args and args[0] != "beard":
        OUT = args.pop(0)
    os.makedirs(OUT, exist_ok=True)
    if args == ["beard"]:   # (only the beard fill: the atlas and fill stay as committed)
        to_img(beard_fill()).save(os.path.join(OUT, "T_BeardFill.png"))
        print("wrote T_BeardFill.png")
        return
    W, H = 256, 1024
    cols = [
        clump(W, H, 260, 0.86, 0.35, 2.2, 0.98, 1.2, fly=0.04, taper_start=0.6),   # dense lock
        clump(W, H, 150, 0.78, 0.55, 2.0, 0.96, 1.6, fly=0.08, taper_start=0.5),   # medium lock
        clump(W, H, 55, 0.7, 0.2, 1.4, 0.95, 2.2, fly=0.3, taper_start=0.35),      # wisps
        clump(W, H, 220, 0.9, 0.5, 2.4, 0.92, 0.8, fly=0.05, taper_start=0.3),     # short tuft
    ]
    atlas = Image.new("RGBA", (W * 4, H))
    for i, c in enumerate(cols):
        atlas.paste(to_img(c), (i * W, 0))
    atlas.save(os.path.join(OUT, "T_HairCards.png"))
    to_img(fill()).save(os.path.join(OUT, "T_HairFill.png"))
    to_img(beard_fill()).save(os.path.join(OUT, "T_BeardFill.png"))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
