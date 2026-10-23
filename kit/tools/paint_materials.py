#!/usr/bin/env python3
"""Paint seamless, hand-painted-style material textures for an iamar world.

    python3 kit/tools/paint_materials.py <out_dir> [options]

Writes <out_dir>/<material>.png for each material (square, tiling exactly in both
directions) and <out_dir>/materials.json (size, metres per tile, texels per metre,
mean colour of each texture). Needs only Python 3.8+, numpy and Pillow; no
Blender, no GPU, no network. A few seconds per material.

Materials (the painted look: each stone, slate, plank or tile is its own painted
shape, with a lit top-left rim and a darker lower-right rim, soft value gradients,
warm highlights and cool shadows, brushy mottling, dirt in the joints, chipped
edges):

  stone       small coursed stone       ashlar      big dressed pale ashlar
  granite     rough dark granite        plaster     lime plaster with stains
  timber      oak planks, grain along u slate       blue slate roof
  slate_dark  heavy dark slate roof     glazed      glazed barrel roof tiles
  shingle     mossy wooden shingles     thatch      thatch
  cobble      cobbled street            iron        hammered iron plate, rivets
  grass       painted meadow turf       sand        rippled sand and dust
  trim        trim sheet: 8 horizontal strips, top to bottom cornice, frame,
              moulding, carved, dentil, rope, beam, strap (each 1/8 of the height,
              tiling along u): map a moulding's UVs onto one strip

Every texture covers TILE_M = 4 m of surface per repeat (256 texels per metre at
1024 px): UV-map your models at that scale (in Blender: 1 UV unit = 4 m) so every
material shares one texel density. Roofs: v runs down the slope (image top = ridge).

Options:
  --materials LIST  comma-separated names, or "all" (default all)
  --size N          output size in px: 256, 512, 1024 (default) or 2048. Painted at
                    1024 and resampled seamlessly, so every size shows the same design
  --tint NAME=#RRGGBB  colour a material (repeatable): its mean colour becomes this
                    colour. Untinted textures are painted around a warm neutral grey
                    (mean ~0.6) so a tint can be applied later in a shader instead
  --preview         also write <material>_tiled.png, a 2x2 repeat (seams would show
                    as lines through the middle)
  --list            print the material names and exit

Example: python3 kit/tools/paint_materials.py worlds/my_world/textures \
             --materials stone,timber,slate --size 512 --tint slate=#56637a

The textures are plain colour (albedo) maps: use them as a material's Base Color
in Blender, then bake light with kit/blender/bake_unlit.py or leave them live-lit.

All noise is periodic (band-limited random fields made in the Fourier domain) and
every block layout wraps around the tile, so nothing shows a seam. Deterministic:
the same arguments always paint the same pixels.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

# The painters below draw at this fixed size (their block layouts are in pixels);
# --size resamples the result.
SIZE = 1024
TILE_M = 4.0                 # metres per tile for every surface material
TEXELS = SIZE / TILE_M       # 256 px per metre at SIZE
MEAN = 0.6                   # every material is normalised to this mean value
WARM = (1.06, 1.0, 0.88)     # painted warm balance applied to every material

LAYERS = [
    "stone", "ashlar", "granite", "plaster", "timber", "slate", "slate_dark",
    "glazed", "shingle", "thatch", "cobble", "iron", "trim",
    "grass", "sand",
]
# Trim-sheet strips, top to bottom, each SIZE/8 px high and TILE_M metres long.
TRIMS = ["cornice", "frame", "moulding", "carved", "dentil", "rope", "beam", "strap"]


# ------------------------------------------------------------------ helpers

def rng(seed):
    return np.random.default_rng(seed)


def pnoise(shape, cycles, seed, octaves=1, gain=0.5):
    """Periodic band-limited noise in [-1, 1]: `cycles` features across the tile
    (a scalar or (cy, cx)). Tiles exactly because it is built in the Fourier
    domain from integer frequencies."""
    h, w = shape
    cy, cx = (cycles, cycles) if np.isscalar(cycles) else cycles
    fy = np.fft.fftfreq(h) * h
    fx = np.fft.fftfreq(w) * w
    out = np.zeros(shape)
    amp = 1.0
    r = rng(seed)
    for _ in range(octaves):
        d = np.sqrt((fy[:, None] / max(cy, 1e-3)) ** 2 + (fx[None, :] / max(cx, 1e-3)) ** 2)
        filt = np.exp(-0.5 * (d / 1.0) ** 2) * (d > 0)
        spec = np.fft.fft2(r.standard_normal(shape)) * filt
        n = np.real(np.fft.ifft2(spec))
        n /= (np.abs(n).max() + 1e-9)
        out += n * amp
        amp *= gain
        cy, cx = cy * 2.0, cx * 2.0
    return out / (np.abs(out).max() + 1e-9)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def grid(h=SIZE, w=SIZE):
    y, x = np.mgrid[0:h, 0:w].astype(np.float64)
    return y, x


def cyclic_cuts(r, length, mean, jitter):
    """Cut positions partitioning a cyclic span [0, length) into pieces of about
    `mean` (+- jitter); returns sorted starts with the first at a random phase."""
    n = max(1, int(round(length / mean)))
    w = np.clip(r.normal(1.0, jitter, n), 0.55, 1.6)
    w = w / w.sum() * length
    starts = np.concatenate([[0.0], np.cumsum(w)[:-1]])
    phase = r.uniform(0, length)
    return np.sort((starts + phase) % length)


def blocks(rows, length, mean, jitter, seed):
    """Running-bond block layout for a SIZE x SIZE tile. rows: list of row heights
    in px summing to SIZE. Returns per-pixel (block id, local x, local y, block w,
    block h) with local coords in px, wrapping across the tile edges."""
    r = rng(seed)
    y, x = grid()
    bid = np.zeros((SIZE, SIZE), np.int64)
    lx = np.zeros((SIZE, SIZE))
    ly = np.zeros((SIZE, SIZE))
    bw = np.ones((SIZE, SIZE))
    bh = np.ones((SIZE, SIZE))
    top = 0
    nid = 0
    for i, rh in enumerate(rows):
        cuts = cyclic_cuts(r, length, mean, jitter)
        ys = slice(top, top + rh)
        xs = x[ys]
        # piece index: last cut <= x (cyclic: before the first cut is the last piece)
        k = np.searchsorted(cuts, xs, side="right") - 1
        start = cuts[k % len(cuts)]
        widths = np.diff(np.concatenate([cuts, [cuts[0] + length]]))
        local = (xs - start) % length
        bid[ys] = nid + (k % len(cuts))
        lx[ys] = local
        bw[ys] = widths[k % len(cuts)]
        ly[ys] = y[ys] - top
        bh[ys] = rh
        nid += len(cuts)
        top += rh
    return bid, lx, ly, bw, bh


def per_block(bid, seed, n=None):
    """A random value per block id, gathered per pixel ([0,1))."""
    r = rng(seed)
    m = int(bid.max()) + 1
    return r.random(m)[bid]


def hue(rgb, warm):
    """Painted hue drift: warm (+) toward ochre, cool (-) toward blue-grey."""
    w = warm[..., None]
    return rgb * (1 + w * np.array([0.10, 0.03, -0.09]))


def finish(rgb, name):
    """Normalise to MEAN so the shader's palette tint lands on the right colour,
    keep a little of the painted contrast, clip, to 8-bit."""
    # warm-neutral balance (sunlit limestone, not grey card), then the mean value
    rgb = rgb * np.array(WARM)
    lum = rgb.mean()
    rgb = rgb * (MEAN / max(lum, 1e-6))
    return (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)


def gray3(v):
    return np.repeat(v[..., None], 3, axis=2)


def bevel_shade(lx, ly, bw, bh, gap, rim, chip):
    """Painted bevel on a block: distance to its edges (px) perturbed by `chip`
    noise. Returns (inside mask 0..1, shade multiplier)."""
    dl = lx - gap * 0.5
    dr = bw - lx - gap * 0.5
    dt = ly - gap * 0.5
    db = bh - ly - gap * 0.5
    d = np.minimum(np.minimum(dl, dr), np.minimum(dt, db)) + chip
    inside = smooth(0.0, 1.6, d)
    # top and left rims catch the light, bottom and right fall into shade
    lit = smooth(rim, 0.0, np.minimum(dt, dl) + chip * 0.5)
    shad = smooth(rim * 1.3, 0.0, np.minimum(db, dr) + chip * 0.5)
    shade = 1.0 + 0.30 * lit - 0.36 * shad
    # soft dome: centre a little brighter than the rim
    u = np.clip(lx / bw, 0, 1)
    v = np.clip(ly / bh, 0, 1)
    dome = 1.0 + 0.07 * (1 - (2 * u - 1) ** 2) * (1 - (2 * v - 1) ** 2) - 0.08 * v
    return inside, shade * dome


# ------------------------------------------------------------------ stone

def masonry(seed, rows, mean_len, jitter, gap, rim, rough, val_jit, mortar, dirt):
    r = rng(seed)
    bid, lx, ly, bw, bh = blocks(rows, SIZE, mean_len, jitter, seed)
    chip = pnoise((SIZE, SIZE), 40, seed + 1, 2) * rough
    inside, shade = bevel_shade(lx, ly, bw, bh, gap, rim, chip)
    bval = 1.0 + (per_block(bid, seed + 2) - 0.5) * val_jit
    # warm and cool blocks side by side (honey, buff, grey-blue), like a wall
    # built from more than one quarry
    bwarm = (per_block(bid, seed + 3) - 0.5) * 2.6
    surf = 1.0 + 0.09 * pnoise((SIZE, SIZE), 14, seed + 4, 3) + 0.03 * pnoise((SIZE, SIZE), 90, seed + 5, 2)
    # chisel strokes: fine diagonal streaks
    y, x = grid()
    strokes = 1.0 + 0.02 * np.sin((x + y * 0.6) * 0.9 + pnoise((SIZE, SIZE), 30, seed + 6) * 6)
    big = 1.0 + 0.10 * pnoise((SIZE, SIZE), 3, seed + 7, 2)
    # worn arrises: broken, lighter rims where the edges have weathered
    rim_d = np.minimum(np.minimum(lx, bw - lx), np.minimum(ly, bh - ly))
    wear = smooth(9, 2, rim_d) * smooth(0.1, 0.6, pnoise((SIZE, SIZE), 60, seed + 10, 2) * 0.5 + 0.5)
    v = bval * shade * surf * strokes * big * (1 + 0.16 * wear)
    warm = bwarm * 0.5 + 0.4 * (shade - 1.0) * 2.5   # warm highlights, cool shade
    stone = hue(gray3(v * 0.62), warm)
    # dirt in the joints and in lower corners
    grime = smooth(0.0, 0.7, pnoise((SIZE, SIZE), 6, seed + 8, 3) * 0.5 + 0.5 - 0.35)
    jointdirt = (1 - inside)
    mort = gray3(np.full((SIZE, SIZE), mortar) * (0.9 + 0.1 * pnoise((SIZE, SIZE), 80, seed + 9)))
    mort = hue(mort, np.full((SIZE, SIZE), -0.5))
    rgb = stone * inside[..., None] + mort * (1 - inside[..., None])
    near_joint = smooth(10, 0, np.minimum(np.minimum(lx, bw - lx), np.minimum(ly, bh - ly)))
    rgb *= (1 - dirt * (0.5 * jointdirt + 0.25 * near_joint * grime))[..., None]
    return rgb


def stone():
    # 0.5 m courses of varied height, blocks ~0.9 m
    r = rng(11)
    rows = []
    left = SIZE
    while left > 0:
        h = int(r.choice([112, 128, 144, 160]))
        h = min(h, left) if left - h >= 90 or left - h == 0 else left
        rows.append(h)
        left -= h
    return masonry(11, rows, 1.05 * TEXELS, 0.28, gap=8, rim=13, rough=4.5, val_jit=0.34, mortar=0.24, dirt=0.4)


def ashlar():
    # dressed pale ashlar: regular 0.64 m courses, long 1.3 m blocks, tight joints
    rows = [128, 128, 128, 128, 128, 128, 128, 128]   # 0.5 m
    return masonry(21, rows, 1.25 * TEXELS, 0.18, gap=6, rim=14, rough=3.0, val_jit=0.28, mortar=0.28, dirt=0.35)


def granite():
    # rough dark granite: tall uneven courses, heavy chipped edges, speckles
    rows = [176, 144, 160, 192, 176, 176]
    rgb = masonry(31, rows, 1.0 * TEXELS, 0.3, gap=9, rim=14, rough=9.0, val_jit=0.34, mortar=0.18, dirt=0.5)
    r = rng(32)
    speck = r.random((SIZE, SIZE))
    rgb *= (1 - 0.25 * (speck > 0.985) + 0.18 * (speck < 0.012))[..., None]
    return rgb


# ------------------------------------------------------------------ plaster

def plaster():
    y, x = grid()
    n1 = pnoise((SIZE, SIZE), 5, 41, 3)
    n2 = pnoise((SIZE, SIZE), 22, 42, 2)
    # trowel strokes: broad arcs as anisotropic noise
    tr = pnoise((SIZE, SIZE), (10, 3), 43, 2)
    v = 0.64 * (1 + 0.06 * n1 + 0.04 * n2 + 0.05 * tr)
    warm = 0.6 * n1 + 0.3
    rgb = hue(gray3(v), warm)
    # stains and damp patches, darker toward the lower part of each stain
    st = smooth(0.25, 0.75, pnoise((SIZE, SIZE), 3, 44, 3))
    rgb *= (1 - 0.08 * st)[..., None]
    rgb = hue(rgb, 0.5 * st)
    # a few hairline cracks
    cr = np.abs(pnoise((SIZE, SIZE), 8, 45, 3))
    crack = smooth(0.025, 0.0, cr) * smooth(0.55, 0.8, pnoise((SIZE, SIZE), 4, 46) * 0.5 + 0.5)
    rgb *= (1 - 0.0 * crack)[..., None]       # hairline cracks read as scribbles: off
    # odd chips showing stone beneath
    chip = smooth(0.9, 0.93, pnoise((SIZE, SIZE), 14, 47, 2) * 0.5 + 0.5)
    rgb = rgb * (1 - chip[..., None]) + hue(gray3(np.full((SIZE, SIZE), 0.45)), np.full((SIZE, SIZE), 0.6)) * chip[..., None]
    return rgb


# ------------------------------------------------------------------ wood

def timber():
    """Oak planks with the grain along +u (x): 0.67 m boards (6 per tile, so a
    beam or frame shows one board, not stripes),
    painted grain lines, knots, lighter top rim, darker gaps."""
    y, x = grid()
    nb = 6
    board = SIZE / nb
    b = np.floor(y / board).astype(int)
    fy = (y % board) / board
    r = rng(51)
    bval = (r.random(nb + 1) - 0.5)[b] * 0.25 + 1.0
    boff = (r.random(nb + 1) * 7)[b]
    warp = pnoise((SIZE, SIZE), (6, 2), 52, 2) * 0.12
    # broad painted grain: a few soft bands per board, not fine hatching
    grain = np.sin((fy + warp + boff) * np.pi * 2 * 3 + pnoise((SIZE, SIZE), (8, 1.0), 53, 2) * 2.5)
    g = 1 + 0.12 * grain + 0.04 * pnoise((SIZE, SIZE), (24, 2), 54, 2)
    # board ends staggered along x
    ends = np.zeros((SIZE, SIZE))
    for i in range(nb + 1):
        e = r.uniform(0, SIZE)
        rows = b == i
        dx = np.abs(((x - e + SIZE / 2) % SIZE) - SIZE / 2)
        ends[rows] = smooth(4, 0, dx[rows])
    # knots
    knots = np.zeros((SIZE, SIZE))
    for _ in range(14):
        kx, ky = r.uniform(0, SIZE, 2)
        dx = ((x - kx + SIZE / 2) % SIZE) - SIZE / 2
        dy = ((y - ky + SIZE / 2) % SIZE) - SIZE / 2
        d = np.sqrt(dx * dx / 2.2 + dy * dy)
        knots = np.maximum(knots, smooth(9, 2, d))
    edge = np.minimum(fy, 1 - fy) * board
    gap = smooth(0, 3, edge)
    rim = 1 + 0.18 * smooth(9, 0, fy * board) - 0.22 * smooth(10, 0, (1 - fy) * board)
    v = 0.62 * bval * g * rim * (1 - 0.35 * knots) * (1 - 0.6 * ends)
    v = v * gap + 0.18 * (1 - gap)
    warm = 0.5 + 0.8 * (rim - 1) + 0.3 * grain * 0.3
    return hue(gray3(v), warm)


# ------------------------------------------------------------------ roofs

def roof_tiles(seed, rows_n, len_m, jitter, gap, rim, val_jit, rough, moss=0.0, round_tile=False):
    """Overlapping roof units: v runs down the slope (top of the image = ridge
    side), each course's lower edge is lit, the course above casts a shadow
    band onto it."""
    rows = [SIZE // rows_n + (1 if k < SIZE % rows_n else 0) for k in range(rows_n)]
    bid, lx, ly, bw, bh = blocks(rows, SIZE, len_m * TEXELS, jitter, seed)
    chip = pnoise((SIZE, SIZE), 50, seed + 1, 2) * rough
    # slates hang: their lower edge is ragged and lit, shadow under the course above
    u = lx / bw
    v = ly / bh
    side = np.minimum(lx, bw - lx) + chip
    inside = smooth(0, 1.5, side - gap * 0.5)
    shade = 0.78 + 0.34 * v          # darker at the top (under the course above)
    shade *= 1 + 0.22 * smooth(rim, 0, (bh - ly) + chip)      # lit lower edge
    shade *= 1 - 0.25 * smooth(rim, 0, ly)                     # course shadow line
    if round_tile:
        # barrel tiles: cylindrical highlight across u plus a glaze streak
        cyl = np.sin(np.clip(u, 0, 1) * np.pi)
        shade *= 0.62 + 0.5 * cyl
        shade += 0.35 * smooth(0.12, 0.0, np.abs(u - 0.32)) * (0.4 + 0.6 * v)
    bval = 1 + (per_block(bid, seed + 2) - 0.5) * val_jit
    surf = 1 + 0.07 * pnoise((SIZE, SIZE), 30, seed + 3, 3)
    big = 1 + 0.08 * pnoise((SIZE, SIZE), 3, seed + 4, 2)
    val = 0.6 * bval * shade * surf * big
    warm = (per_block(bid, seed + 5) - 0.5) * 1.2 + (shade - 1) * 1.5
    rgb = hue(gray3(val), warm)
    rgb = rgb * inside[..., None] + gray3(np.full((SIZE, SIZE), 0.12)) * (1 - inside[..., None])
    if moss > 0:
        m = smooth(0.35, 0.8, pnoise((SIZE, SIZE), 5, seed + 6, 4) * 0.5 + 0.5) * smooth(0.3, 1.0, v)
        mossc = np.array([0.42, 0.5, 0.22]) * (0.8 + 0.3 * pnoise((SIZE, SIZE), 60, seed + 7)[..., None])
        rgb = rgb * (1 - moss * m[..., None]) + mossc * (moss * m[..., None])
    return rgb


def slate():
    return roof_tiles(61, 11, 0.62, 0.22, gap=5, rim=9, val_jit=0.32, rough=3.5)


def slate_dark():
    return roof_tiles(71, 9, 0.75, 0.32, gap=7, rim=11, val_jit=0.4, rough=8.0, moss=0.12)


def glazed():
    return roof_tiles(81, 10, 0.40, 0.04, gap=3, rim=8, val_jit=0.18, rough=1.0, round_tile=True)


def shingle():
    return roof_tiles(91, 13, 0.36, 0.4, gap=4, rim=7, val_jit=0.45, rough=4.0, moss=0.4) * \
        (1 + 0.08 * np.sin(grid()[1] * 0.9 + pnoise((SIZE, SIZE), (2, 30), 92) * 4))[..., None]


def thatch():
    """Thatch: overlapping courses whose butt ends wander (noise-shifted course
    lines), straw clumps of their own value, combed straw along the slope."""
    y, x = grid()
    straw = pnoise((SIZE, SIZE), (3, 70), 102, 3)
    straw2 = pnoise((SIZE, SIZE), (5, 160), 103, 2)
    course = SIZE / 8
    wander = pnoise((SIZE, SIZE), (1, 6), 105, 2) * course * 0.35
    fy = ((y + wander) % course) / course
    shade = 0.68 + 0.42 * fy ** 0.8           # butt ends lit at each course's foot
    shade *= 1 - 0.28 * smooth(0.1, 0.0, fy)
    clump = 1 + 0.12 * pnoise((SIZE, SIZE), (8, 14), 106, 2)
    v = 0.6 * shade * clump * (1 + 0.15 * straw + 0.08 * straw2)
    warm = 0.6 + 0.6 * straw + (shade - 1) * 1.2
    rgb = hue(gray3(v), warm)
    dark = smooth(0.4, 0.9, pnoise((SIZE, SIZE), 4, 104, 3) * 0.5 + 0.5)
    rgb *= (1 - 0.22 * dark)[..., None]
    moss = smooth(0.55, 0.85, pnoise((SIZE, SIZE), 5, 107, 3) * 0.5 + 0.5) * (1 - fy)
    rgb = rgb * (1 - 0.3 * moss[..., None]) + np.array([0.4, 0.46, 0.22]) * 0.3 * moss[..., None]
    return rgb


# ------------------------------------------------------------------ ground, metal

def cobble():
    """Rounded setts in loose rows, each a painted dome with a lit top-left."""
    y, x = grid()
    r = rng(111)
    n = 18                     # setts per row (0.22 m)
    rows = 26
    rh = SIZE / rows
    pts = []
    for j in range(rows):
        off = r.uniform(0, 1)
        for i in range(n):
            pts.append(((i + off + r.normal(0, 0.12)) * SIZE / n, (j + 0.5 + r.normal(0, 0.1)) * rh))
    pts = np.array(pts)
    d1 = np.full((SIZE, SIZE), 1e9)
    d2 = np.full((SIZE, SIZE), 1e9)
    cid = np.zeros((SIZE, SIZE), np.int64)
    off_x = np.zeros((SIZE, SIZE))
    off_y = np.zeros((SIZE, SIZE))
    for k, (px, py) in enumerate(pts):
        dx = ((x - px + SIZE / 2) % SIZE) - SIZE / 2
        dy = ((y - py + SIZE / 2) % SIZE) - SIZE / 2
        d = np.sqrt((dx / 1.25) ** 2 + dy ** 2)
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        d1 = np.where(closer, d, d1)
        cid = np.where(closer, k, cid)
        off_x = np.where(closer, dx, off_x)
        off_y = np.where(closer, dy, off_y)
    edge = d2 - d1
    inside = smooth(1.5, 6.0, edge)
    dome = smooth(18, 0, edge)
    light = 1 + 0.25 * np.clip(-(off_x + off_y) / 25, -1, 1) * (1 - dome * 0.3)
    bval = 1 + (r.random(len(pts)) - 0.5)[cid] * 0.35
    bwarm = (r.random(len(pts)) - 0.5)[cid] * 1.2
    v = 0.62 * bval * light * (1 - 0.18 * dome) * (1 + 0.06 * pnoise((SIZE, SIZE), 60, 112, 2))
    rgb = hue(gray3(v), bwarm + (light - 1) * 2)
    dirt = hue(gray3(np.full((SIZE, SIZE), 0.2) * (1 + 0.3 * pnoise((SIZE, SIZE), 40, 113))), np.full((SIZE, SIZE), 0.8))
    return rgb * inside[..., None] + dirt * (1 - inside[..., None])


def grass():
    """Meadow turf: painted blade clumps (fine strokes along v), value patches of
    sun and shade, a few clover and dry-straw flecks. Ground, so it has no lit rim."""
    y, x = grid()
    blade = pnoise((SIZE, SIZE), (90, 24), 121, 3)       # strokes stretched along v
    clump = pnoise((SIZE, SIZE), 22, 122, 3)
    patch = pnoise((SIZE, SIZE), 5, 123, 3)
    v = 0.6 * (1 + 0.20 * blade + 0.16 * clump + 0.22 * patch)
    warm = -0.2 + 0.9 * patch + 0.5 * clump                 # green, sun-warmed patches
    rgb = hue(gray3(v), warm) * np.array([0.82, 1.0, 0.62])
    dry = smooth(0.55, 0.85, pnoise((SIZE, SIZE), 12, 124, 3) * 0.5 + 0.5)
    rgb = rgb * (1 - 0.25 * dry[..., None]) + np.array([0.52, 0.46, 0.26]) * 0.25 * dry[..., None]
    fleck = smooth(0.72, 0.9, pnoise((SIZE, SIZE), 70, 125, 2) * 0.5 + 0.5)
    rgb = rgb * (1 - 0.35 * fleck[..., None]) + np.array([0.42, 0.62, 0.30]) * 0.35 * fleck[..., None]
    return rgb


def sand():
    """Sand and dust: wind ripples (long soft ridges lit from the top-left), fine grain,
    darker damp patches and a few pebbles."""
    y, x = grid()
    warp = pnoise((SIZE, SIZE), 3, 131, 1) * 0.035
    ph = (y / SIZE * 14 + x / SIZE * 5 + warp * 14) * 2 * np.pi
    ripple = np.sin(ph) * 0.5 + 0.5
    lit = 0.5 * np.sin(ph + 0.9) + 0.5
    grain = pnoise((SIZE, SIZE), 240, 132, 1)
    patch = pnoise((SIZE, SIZE), 4, 133, 3)
    v = 0.6 * (1 + 0.12 * (lit - 0.5) + 0.04 * ripple + 0.07 * grain + 0.10 * patch)
    rgb = hue(gray3(v), 0.9 + 0.6 * patch + 0.3 * (lit - 0.5))
    damp = smooth(0.6, 0.9, pnoise((SIZE, SIZE), 6, 134, 3) * 0.5 + 0.5)
    rgb *= (1 - 0.18 * damp)[..., None]
    pebble = smooth(0.8, 0.92, pnoise((SIZE, SIZE), 55, 135, 2) * 0.5 + 0.5)
    rgb = rgb * (1 - 0.4 * pebble[..., None]) + np.array([0.34, 0.31, 0.28]) * 0.4 * pebble[..., None]
    return rgb


def iron():
    y, x = grid()
    hammer = pnoise((SIZE, SIZE), 60, 121, 2)
    v = 0.6 * (1 + 0.1 * hammer + 0.1 * pnoise((SIZE, SIZE), 4, 122, 2))
    rgb = hue(gray3(v), -0.4 + 0.3 * pnoise((SIZE, SIZE), 6, 123))
    # plate seams every 1 m and rivets along them
    p = TEXELS
    fx = (x % p)
    fy = (y % p)
    seam = smooth(3, 0, np.minimum(fx, p - fx)) + smooth(3, 0, np.minimum(fy, p - fy))
    rgb *= (1 - 0.45 * np.clip(seam, 0, 1))[..., None]
    rx = ((x + p / 8) % (p / 4)) - p / 8
    ry = np.minimum(fy, p - fy) - 12
    rd = np.sqrt(rx ** 2 + ry ** 2)
    rv = smooth(9, 5, rd)
    rl = smooth(5, 0, np.sqrt((rx + 2.5) ** 2 + (ry + 2.5) ** 2))
    rgb = rgb * (1 - 0.4 * rv)[..., None] + (0.35 * rv + 0.6 * rl)[..., None]
    rust = smooth(0.5, 0.9, pnoise((SIZE, SIZE), 8, 124, 3) * 0.5 + 0.5)
    rgb = rgb * (1 - 0.3 * rust[..., None]) + np.array([0.45, 0.26, 0.14]) * 0.3 * rust[..., None]
    return rgb


# ------------------------------------------------------------------ trim sheet

def trim():
    """Eight strips, each SIZE/8 px high (v across the trim, top = upper edge)
    and tiling along u: profiles painted as light/shade bands (the moulding
    reads carved without a single extra polygon)."""
    sh = SIZE // 8
    out = np.zeros((SIZE, SIZE, 3))
    y, x = np.mgrid[0:sh, 0:SIZE].astype(np.float64)
    v = y / sh
    grainn = pnoise((sh, SIZE), (1, 40), 131, 2)
    stn = 1 + 0.08 * pnoise((sh, SIZE), (3, 60), 132, 3)

    def profile(bands):
        # bands: list of (v0, v1, value at v0, value at v1)
        p = np.zeros_like(v)
        for v0, v1, a, b in bands:
            t = np.clip((v - v0) / max(v1 - v0, 1e-6), 0, 1)
            m = (v >= v0) & (v < v1)
            p = np.where(m, a + (b - a) * t, p)
        return p

    strips = []
    # cornice: fillet, big ovolo, cavetto, bead
    strips.append(profile([(0, .1, 1.15, 1.05), (.1, .14, .55, .6), (.14, .5, 1.25, .7), (.5, .56, .5, .55),
                           (.56, .8, .7, 1.1), (.8, .84, .55, .6), (.84, .95, 1.2, .8), (.95, 1, .5, .5)]) * stn)
    # window/door frame: chamfered stone surround with a lit outer arris
    strips.append(profile([(0, .08, .5, .6), (.08, .22, 1.25, 1.0), (.22, .78, .95, .9), (.78, .92, .8, .62),
                           (.92, 1, .45, .45)]) * stn)
    # moulding: torus + scotia string course
    strips.append(profile([(0, .15, 1.05, 1.0), (.15, .45, 1.3, .65), (.45, .55, .5, .55), (.55, .75, .7, 1.15),
                           (.75, 1, 1.0, .85)]) * stn)
    # carved band: leaf-and-dart rhythm along u, 0.33 m repeat
    rep = SIZE / 12
    fx = (x % rep) / rep
    leaf = np.sqrt(((fx - 0.5) * 2.2) ** 2 + ((v - 0.55) * 1.6) ** 2)
    leafm = smooth(1.0, 0.85, leaf)
    lit = np.clip(1.0 - (fx - 0.3) * 0.8 - (v - 0.3) * 0.8, 0.5, 1.4)
    dart = smooth(0.06, 0.0, np.abs(fx - 0.0) + np.abs(fx - 1.0) * 0 ) * (v > 0.25) * (v < 0.85)
    carved = (0.55 + 0.75 * leafm * lit) * (1 - 0.4 * dart)
    carved = np.where(v < 0.12, 1.1, np.where(v > 0.9, 0.85, carved))
    rib = smooth(0.04, 0.0, np.abs(fx - 0.5)) * leafm * (v > 0.3)
    strips.append((carved - 0.25 * rib) * stn)
    # dentils: square teeth under a fillet
    rep = SIZE / 24
    fx = (x % rep) / rep
    tooth = (fx > 0.12) & (fx < 0.72) & (v > 0.3)
    den = np.where(v < 0.25, profile([(0, .25, 1.15, .9)]), np.where(tooth, 1.05 - 0.35 * fx - 0.25 * (v - 0.3), 0.35))
    strips.append(den * stn)
    # rope moulding
    rep = SIZE / 20
    tw = ((x + v * rep * 1.2) % rep) / rep
    rope = 0.55 + 0.7 * np.sin(np.clip(tw, 0, 1) * np.pi) * np.sin(np.clip(v, 0, 1) * np.pi)
    strips.append(rope * stn)
    # timber beam: grain along u, chamfered arrises
    g = 1 + 0.12 * np.sin((v * 7 + grainn * 0.8) * np.pi) + 0.05 * pnoise((sh, SIZE), (2, 80), 133)
    beam = profile([(0, .1, 1.2, 1.0), (.1, .9, 1.0, .9), (.9, 1, .65, .55)]) * g
    strips.append(beam)
    # iron strap with rivets
    rep = SIZE / 8
    rx = (x % rep) - rep / 2
    ry = (v - 0.5) * sh
    rd = np.sqrt(rx ** 2 + ry ** 2)
    strap = profile([(0, .15, .5, .8), (.15, .85, 1.0, .85), (.85, 1, .6, .4)]) * (1 + 0.08 * pnoise((sh, SIZE), (2, 50), 134))
    strap = strap * (1 - 0.35 * smooth(10, 6, rd)) + 0.5 * smooth(6, 0, np.sqrt((rx + 2) ** 2 + (ry + 2) ** 2))
    strips.append(strap)
    warmth = [0.3, 0.3, 0.3, 0.3, 0.3, 0.4, 0.8, -0.5]
    for i, s in enumerate(strips):
        val = 0.6 * s
        warm = np.full_like(val, warmth[i]) + (s - 1) * 1.5
        out[i * sh:(i + 1) * sh] = hue(gray3(val), warm)
    return out


PAINTERS = {
    "stone": stone, "ashlar": ashlar, "granite": granite, "plaster": plaster,
    "timber": timber, "slate": slate, "slate_dark": slate_dark, "glazed": glazed,
    "shingle": shingle, "thatch": thatch, "cobble": cobble, "iron": iron, "trim": trim,
    "grass": grass, "sand": sand,
}




# ------------------------------------------------------------------ command line

def resample_seamless(rgb, size):
    """Resizes a tiling image and keeps it tiling: wrap-pad, resize, crop."""
    h = rgb.shape[0]
    if size == h:
        return rgb
    pad = max(8, h // 32)
    big = np.pad(rgb, ((pad, pad), (pad, pad), (0, 0)), mode="wrap")
    k = size / h
    out_pad = int(round(pad * k))
    full = size + 2 * out_pad
    im = Image.fromarray(big).resize((full, full), Image.LANCZOS)
    return np.asarray(im)[out_pad:out_pad + size, out_pad:out_pad + size]


def parse_tint(s):
    name, _, col = s.partition("=")
    col = col.strip().lstrip("#")
    if name not in PAINTERS or len(col) != 6:
        raise argparse.ArgumentTypeError("--tint wants NAME=#RRGGBB with a known material name, got %r" % s)
    return name, tuple(int(col[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def main(argv=None):
    p = argparse.ArgumentParser(prog="paint_materials.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("out_dir", nargs="?")
    p.add_argument("--materials", default="all")
    p.add_argument("--size", type=int, default=1024, choices=(256, 512, 1024, 2048))
    p.add_argument("--tint", type=parse_tint, action="append", default=[])
    p.add_argument("--preview", action="store_true")
    p.add_argument("--list", action="store_true")
    a = p.parse_args(argv)
    if a.list:
        print("\n".join(LAYERS))
        return 0
    if not a.out_dir:
        p.error("out_dir is required")
    names = LAYERS if a.materials == "all" else [n.strip() for n in a.materials.split(",") if n.strip()]
    bad = [n for n in names if n not in PAINTERS]
    if bad:
        p.error("unknown material(s) %s; known: %s" % (", ".join(bad), ", ".join(LAYERS)))
    tints = dict(a.tint)
    os.makedirs(a.out_dir, exist_ok=True)
    meta = {"size": a.size, "tile_m": TILE_M, "texels_per_m": a.size / TILE_M, "materials": {}}
    for name in names:
        rgb = finish(PAINTERS[name](), name)
        if name in tints:
            f = rgb.astype(np.float64) / 255.0
            f = f / np.maximum(f.reshape(-1, 3).mean(axis=0), 1e-6) * np.array(tints[name])
            rgb = (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)
        rgb = resample_seamless(rgb, a.size)
        path = os.path.join(a.out_dir, name + ".png")
        Image.fromarray(rgb).save(path, optimize=True)
        mean = [round(float(v) / 255.0, 3) for v in rgb.reshape(-1, 3).mean(axis=0)]
        entry = {"file": name + ".png", "mean_rgb": mean}
        if name in tints:
            entry["tint"] = "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in tints[name])
        if name == "trim":
            entry["strips"] = TRIMS
        meta["materials"][name] = entry
        if a.preview:
            sheet = np.tile(rgb, (2, 2, 1))
            Image.fromarray(sheet).save(os.path.join(a.out_dir, name + "_tiled.png"), optimize=True)
        print("PAINTED %s %dpx mean=%.3f" % (name, a.size, rgb.mean() / 255), flush=True)
    with open(os.path.join(a.out_dir, "materials.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print("WROTE %s (%d materials)" % (a.out_dir, len(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
