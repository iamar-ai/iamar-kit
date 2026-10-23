"""The Mission Hall: builds, lights, bakes and exports the hall of a world package.

Step 1 of the Mission Hall worked example (kit/examples/mission_hall/README.md). Blender
4.2+ with Cycles; a GPU for Cycles is strongly advised (the full bake is long on a CPU):

    blender -b --python kit/examples/mission_hall/mission_hall.py -- worlds/mission_hall         [samples] [--quick] [--preview] [--render] [--props DIR] [--textures DIR] [--work DIR]

  worlds/mission_hall   the package; writes assets/*.glb there
  samples               Cycles samples for the light bake (default 384)
  --quick               quarter-size lightmaps and few samples, for trying geometry
  --preview             also renders preview images of the baked hall into the work folder
  --render              renders the real lighting (no bake) into the work folder and stops
  --props DIR           folder of glTF props by file name (Table_Large.gltf, Chalice.gltf, ...:
                        the Quaternius Fantasy Props MegaKit, CC0, quaternius.com; the kit
                        catalogue lists each under its sha256). Without it every prop is a
                        plain box of the catalogue's size, so the booths keep their shape
  --textures DIR        folder of the five surface maps (default kit/style/materials/library:
                        ashlar, plaster, trim, timber, stone; original, CC0)
  --work DIR            bake scratch and previews (default <package>/../build/mission_hall_work,
                        outside the package so none of it ships)

How it is lit: everything static is modelled here with Blender's Python API (bmesh), dressed
with the kit's material library and catalogue props, lit by a sun through the oculus,
stained-glass windows, braziers and lanterns, and baked with Cycles: per atlas, the surface
colour, the light (direct + bounced, denoised), ambient occlusion and emission are baked
separately and combined here (colour x (light + a little occlusion-shaded fill) + emission,
with a soft shoulder for the sunlit pool). The result is one texture per atlas on unlit
(KHR_materials_unlit) glTF materials, so the browser draws the hall with its light already in
it, at the cost of one draw call per atlas, and people walking through it are lit by the
scene's live lights (scene.json, written by hall_scene.py) instead.

Outputs (in <package>/assets/):
  hall.glb            the baked hall (6 meshes, 6 unlit materials)
  hall_collision.glb  invisible walk/obstacle geometry (floors, ramps for the stairs and the dais)
  flame.glb           a flickering brazier flame (animation "flicker"), placed per brazier
  shaft.glb           the translucent shaft of light under the oculus
  veil.glb            the portal's glow and turning spiral (animation "swirl")
Also prints HALL_* lines: positions scene.json needs (braziers, booths, gallery spots).

Ported from the iamar browser source (not public) tools/blender/mission_hall.py (ca4acb3) for the kit (an internal task):
the city's assets/ folder is replaced by --props/--textures, and the work folder by --work.
"""
import bmesh
import bpy
import json
import math
import os
import struct
import sys
import time

import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
VALUE_OPTS = ("--props", "--textures", "--work")
opts, pos_args = {}, []
_i = 0
while _i < len(argv):
    if argv[_i] in VALUE_OPTS and _i + 1 < len(argv):
        opts[argv[_i]] = argv[_i + 1]
        _i += 2
        continue
    if not argv[_i].startswith("--"):
        pos_args.append(argv[_i])
    _i += 1
HERE = os.path.dirname(os.path.abspath(__file__))
KIT_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PKG = os.path.abspath(pos_args[0]) if pos_args else os.path.abspath("worlds/mission_hall")
SAMPLES = int(pos_args[1]) if len(pos_args) > 1 else 384
QUICK = "--quick" in argv
PREVIEW = "--preview" in argv
ASSETS = os.path.join(PKG, "assets")
WORK = os.path.abspath(opts.get("--work") or os.path.join(os.path.dirname(PKG), "build", "mission_hall_work"))
PREV = os.path.join(WORK, "preview")
TEXTURES = os.path.abspath(opts.get("--textures") or os.path.join(KIT_ROOT, "kit", "style", "materials", "library"))
PROPS = os.path.abspath(opts["--props"]) if opts.get("--props") else None
CATALOG = os.path.join(KIT_ROOT, "kit", "catalog", "catalog.json")
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(WORK, exist_ok=True)
T0 = time.time()


def log(*a):
    print("HALL", "%6.1fs" % (time.time() - T0), *a, flush=True)


# ---------------------------------------------------------------- dimensions (metres, game axes)
R = 34.0            # drum (inner face of the outer wall)
WALL_TOP = 18.0     # the dome springs here
GAL_Y = 8.0         # gallery floor
GAL_IN = 29.0       # gallery inner edge (the balustrade)
COL_R = 24.0        # colonnade radius
N_COL = 16
ALC_W = 3.5         # alcove half width
ALC_D = 38.0        # alcove back wall (distance from the centre along the booth axis)
ALC_SPRING = 2.6    # alcove arch springs here (a semicircle of radius ALC_W above)
DAIS = [(7.2, 0.3), (5.9, 0.6), (4.6, 0.9)]   # (radius, top height) of each step
DOME_TOP = 42.0
OCULUS = 4.0
Rs = (R * R + (DOME_TOP - WALL_TOP) ** 2) / (2.0 * (DOME_TOP - WALL_TOP))
DOME_CY = DOME_TOP - Rs
PHI0 = math.asin(R / Rs)            # polar angle of the springing
PHI1 = math.asin(OCULUS / Rs)       # polar angle of the oculus
OCULUS_Y = DOME_CY + Rs * math.cos(PHI1)
POOL = Vector((0.0, 0.9, 2.2))      # where the sun through the oculus lands (on the dais)
BRAZIER_R = 19.0
STAIR_ANGLES = [math.radians(112.5), math.radians(292.5)]

# the eight booths, k * 45 degrees round from +Z (straight ahead of the spawn)
GUILDS = [
    # id, sign, banner colour, emblem, trim
    ("guild", "ADVENTURERS' GUILD", "9e2a2a", "swords"),
    ("rangers", "RANGERS OF THE WEALD", "3a6a34", "arrow"),
    ("tamers", "BEAST TAMERS", "2e6e6a", "paw"),
    ("bounty", "BOUNTY OFFICE", "35353a", "skull"),
    ("arcane", "ARCANE CONCLAVE", "5d3a8e", "star"),
    ("maps", "CARTOGRAPHERS", "2d4e9c", "compass"),
    ("merchants", "MERCHANTS' EXCHANGE", "b8862a", "coin"),
    ("dawn", "ORDER OF THE DAWN", "d8ccb0", "sun"),
]
BOOTH_A = [math.radians(45.0 * k) for k in range(8)]

RES = {"floor": 2048, "walls": 2048, "upper": 2048, "dome": 1024, "columns": 1024, "props": 2048}
if QUICK:
    RES = {k: v // 4 for k, v in RES.items()}
    SAMPLES = min(SAMPLES, 48)


def V(x, y, z):
    return Vector((x, y, z))


def G(p):
    """Game (Y up, -Z forward: glTF) to Blender (Z up)."""
    return Vector((p[0], -p[2], p[1]))


GM = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
UP = V(0, 1, 0)


def dirv(a):
    return V(math.sin(a), 0.0, math.cos(a))


def tanv(a):
    """Right-hand direction for someone at the centre looking out along dirv(a)."""
    return dirv(a).cross(UP)


def on_drum(a, u, y, r=R):
    """A point on the drum: arc length u to the right of angle a, height y."""
    aa = a - u / r   # to the right of dirv(a) is decreasing angle (tanv = dirv x up)
    return dirv(aa) * r + UP * y


# ---------------------------------------------------------------- scene reset, render setup
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
SC.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for kind in ("OPTIX", "CUDA", "NONE"):
    try:
        prefs.compute_device_type = kind
        break
    except TypeError:
        continue
prefs.refresh_devices()
for d in prefs.devices:
    d.use = d.type != "CPU"
SC.cycles.device = "GPU" if prefs.compute_device_type != "NONE" else "CPU"
SC.cycles.max_bounces = 6
SC.cycles.diffuse_bounces = 4
SC.cycles.glossy_bounces = 0
SC.cycles.transmission_bounces = 0
SC.cycles.use_denoising = False
SC.view_settings.view_transform = "Standard"
SC.render.bake.margin = 8
SC.render.bake.margin_type = "EXTEND"
log("device", prefs.compute_device_type, SC.cycles.device, "samples", SAMPLES, "quick" if QUICK else "")

world = bpy.data.worlds.new("Sky")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.42, 0.58, 0.92, 1.0)
bg.inputs[1].default_value = 0.0   # the sky lights the hall only through the oculus (SKY_DISC): no leaks
world.light_settings.distance = 2.5   # AO reach
SC.world = world


# ---------------------------------------------------------------- images made here (numpy)
def np_image(name, arr, srgb=True):
    """arr: (h, w, 3|4) float 0..1, row 0 at the bottom (Blender's order)."""
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), np.float32)], axis=2)
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    img.pixels.foreach_set(arr.astype(np.float32).ravel())
    img.pack()
    return img


def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def _hash(a, b):
    """Stable pseudo-random 0..1 per integer cell."""
    x = (a.astype(np.int64) * 73856093) ^ (b.astype(np.int64) * 19349663)
    x = (x ^ (x >> 13)) * 1274126177
    return ((x & 0xFFFF).astype(np.float32)) / 65535.0


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


FLOOR_L = 39.0   # the floor image covers [-L, L] in x and z


def make_floor_image(n):
    """The mosaic floor, in game XZ: u = (x + L) / 2L, v = (z + L) / 2L."""
    xs = (np.arange(n, dtype=np.float32) + 0.5) / n * 2 * FLOOR_L - FLOOR_L
    x, z = np.meshgrid(xs, xs)          # rows = z
    r = np.sqrt(x * x + z * z)
    th = np.arctan2(x, z)               # 0 toward +Z, like dirv()
    cream = hexc("e9dcc0")
    col = np.zeros((n, n, 3), np.float32) + cream
    # tesserae: polar cells ~16 cm, a grout line round each, per-cell colour jitter
    s = 0.16
    ri = np.floor(r / s)
    circ = np.maximum(ri * s, s)
    ai = np.floor((th + math.pi) * circ / s)
    fr = r / s - ri
    fa = (th + math.pi) * circ / s - ai
    jit = _hash(ri, ai)
    grout = np.minimum(np.minimum(fr, 1 - fr), np.minimum(fa, 1 - fa))
    g = smooth(0.0, 0.12, grout)
    # --- inner medallion (the dais top): gold 8-point star on lapis, in an ivory ring
    lap = hexc("2d4e9c")
    gold = hexc("d0a040")
    ivory = hexc("efe6d0")
    dark = hexc("3a2e28")
    terra = hexc("b0583a")
    star_r = 3.2 * (0.55 + 0.45 * np.abs(np.cos(4 * th)) ** 6)
    m = r < 4.6
    col[m] = lap
    col[m & (r < star_r)] = gold
    col[m & (r < star_r * 0.55)] = ivory
    col[m & (r > 3.9)] = ivory
    col[m & (r > 4.25)] = dark
    # --- the field between the dais and the colonnade
    f = (r >= 7.0) & (r < 24.0)
    col[f] = cream
    # eight rays toward the booths, each in its guild's colour with a gold edge
    for k, gd in enumerate(GUILDS):
        a = BOOTH_A[k]
        d = np.angle(np.exp(1j * (th - a)))
        width = 0.16 * (1.0 - (r - 7.0) / 17.0) + 0.02
        ray = f & (np.abs(d) < width) & (r < 21.0)
        edge = f & (np.abs(d) < width + 0.018) & (r < 21.3) & ~ray
        col[edge] = gold
        c = hexc(gd[2]) if gd[0] != "dawn" else hexc("e6d8b8")
        col[ray] = c
    # between the rays: a lattice of lozenges in soft terracotta and sage
    rhomb = f & (np.abs(((r - 7.0) / 1.1) % 2 - 1) + np.abs(((th * r) / 1.1) % 2 - 1) < 0.55)
    base_ray = np.zeros_like(f)
    for k in range(8):
        d = np.angle(np.exp(1j * (th - BOOTH_A[k])))
        base_ray |= np.abs(d) < 0.21
    col[rhomb & ~base_ray & (r > 9.0) & (r < 20.5)] = hexc("c98d62")
    for rr, cc in ((7.3, dark), (7.7, gold), (12.0, terra), (16.0, terra), (21.5, dark), (21.9, gold), (22.4, dark)):
        col[f & (np.abs(r - rr) < 0.12)] = cc
    # a running wave (the "Vitruvian scroll") between 22.6 and 23.6
    wv = f & (r > 22.6) & (r < 23.6)
    wave = np.sin(th * 96.0) * 0.35 + 23.1
    col[wv & (r < wave)] = terra
    col[f & (np.abs(r - 23.8) < 0.18)] = dark
    # --- the ambulatory and the alcoves: big polished slabs, two tones, radial joints
    o = r >= 24.0
    slab_r = np.floor((r - 24.0) / 2.5)
    slab_a = np.floor((th + math.pi) / (2 * math.pi / 48))
    chk = (slab_r + slab_a) % 2
    tone = np.where(chk[..., None] > 0.5, hexc("d6c7a8"), hexc("c2ae8e"))
    col[o] = tone[o]
    fr2 = ((r - 24.0) / 2.5) % 1.0
    fa2 = ((th + math.pi) / (2 * math.pi / 48)) % 1.0
    joint = np.minimum(np.minimum(fr2, 1 - fr2) * 2.5, np.minimum(fa2, 1 - fa2) * (2 * math.pi / 48) * r)
    vein = 0.5 + 0.5 * np.sin(x * 1.7 + np.sin(z * 0.9) * 2.0 + z * 0.4)
    col[o] *= (0.93 + 0.07 * vein[o])[..., None]
    col[o] *= (0.6 + 0.4 * smooth(0.0, 0.03, joint[o]))[..., None]
    # tesserae grout and jitter (not on the slabs)
    t = r < 24.0
    col[t] *= (0.9 + 0.12 * jit[t])[..., None]
    col[t] *= (0.62 + 0.38 * g[t])[..., None]
    return np.clip(col, 0, 1)


def emblem_mask(kind, u, v):
    """u, v in -1..1 (v up). A simple heraldic device."""
    m = np.zeros_like(u, dtype=bool)
    if kind == "swords":
        for sgn in (-1, 1):
            c, s = math.cos(sgn * 0.7), math.sin(sgn * 0.7)
            a = c * u + s * v
            b = -s * u + c * v
            m |= (np.abs(a) < 0.07) & (b > -0.55) & (b < 0.8)
            m |= (np.abs(b + 0.45) < 0.06) & (np.abs(a) < 0.28)
            m |= (np.abs(a) < 0.05) & (b < -0.55) & (b > -0.8)
    elif kind == "arrow":
        m |= (np.abs(u) < 0.06) & (v > -0.8) & (v < 0.45)
        m |= (v > 0.35) & (v < 0.85) & (np.abs(u) < (0.85 - v) * 0.7)
        for k in range(3):
            y = -0.75 + k * 0.14
            m |= (np.abs(np.abs(u) - (v - y) * 0.9) < 0.05) & (v > y) & (v < y + 0.3) & (np.abs(u) < 0.3)
    elif kind == "paw":
        m |= ((u / 0.42) ** 2 + ((v + 0.3) / 0.34) ** 2) < 1
        for cx, cy in ((-0.5, 0.25), (-0.18, 0.55), (0.18, 0.55), (0.5, 0.25)):
            m |= ((u - cx) / 0.16) ** 2 + ((v - cy) / 0.21) ** 2 < 1
    elif kind == "skull":
        m |= (u / 0.55) ** 2 + ((v - 0.12) / 0.55) ** 2 < 1
        m |= (np.abs(u) < 0.32) & (v > -0.62) & (v < -0.2)
        for cx in (-0.22, 0.22):
            m &= ~(((u - cx) / 0.15) ** 2 + ((v - 0.05) / 0.17) ** 2 < 1)
        m &= ~((np.abs(u) < 0.05) & (v < -0.28) & (v > -0.62))
        m &= ~((np.abs(u - 0.16) < 0.03) & (v < -0.3)) & ~((np.abs(u + 0.16) < 0.03) & (v < -0.3))
    elif kind == "star":
        r = np.sqrt(u * u + v * v)
        a = np.arctan2(u, v)
        m |= r < 0.28 + 0.55 * np.abs(np.cos(4 * a)) ** 8
        m |= r < 0.3
    elif kind == "compass":
        r = np.sqrt(u * u + v * v)
        a = np.arctan2(u, v)
        m |= r < 0.12 + 0.72 * np.abs(np.cos(2 * a)) ** 14
        m |= (np.abs(r - 0.55) < 0.05)
    elif kind == "coin":
        r = np.sqrt(u * u + v * v)
        m |= (r < 0.7) & ~((r > 0.5) & (r < 0.58))
        m &= ~((np.abs(u) < 0.08) & (np.abs(v) < 0.3) & (r < 0.5))
    elif kind == "sun":
        r = np.sqrt(u * u + v * v)
        a = np.arctan2(u, v)
        m |= r < 0.34
        m |= (r < 0.82) & (np.cos(12 * a) > 0.72) & (r > 0.4)
    return m


def make_banner_image():
    """Eight banners side by side (each 256 x 1024): field, gold border, emblem."""
    w, h = 256, 1024
    out = np.zeros((h, 8 * w, 3), np.float32)
    uu, vv = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)
    gold = hexc("d4a640")
    for k, gd in enumerate(GUILDS):
        field = hexc(gd[2])
        c = np.zeros((h, w, 3), np.float32) + field
        # weave and a soft vertical sheen
        c *= (0.9 + 0.1 * np.sin(uu * 180) * np.sin(vv * 700))[..., None]
        border = (uu < 0.06) | (uu > 0.94) | (vv > 0.965) | ((vv < 0.2) & (np.abs(vv - 0.2 + np.abs(uu - 0.5) * 0.36) < 0.035))
        inner = (np.abs(uu - 0.5) < 0.40) & (vv > 0.3) & (vv < 0.93)
        c[border] = gold
        # emblem in a circle
        eu = (uu - 0.5) / 0.36
        ev = (vv - 0.62) / 0.18
        ring = np.abs(np.sqrt(eu ** 2 + (ev * 0.5) ** 2) - 1.0) < 0.05
        mk = emblem_mask(gd[3], eu * 1.15, ev * 0.58)
        ecol = gold if gd[0] not in ("merchants", "dawn") else hexc("7a1f1f")
        c[inner & mk] = ecol
        c[inner & ring] = ecol
        # a band under the emblem
        c[inner & (np.abs(vv - 0.38) < 0.012)] = gold
        out[:, k * w:(k + 1) * w] = c
    return np.clip(out, 0, 1)


def make_glass_image():
    """Stained glass (256 x 512): leaded cells of jewel colours round a golden rose."""
    w, h = 256, 512
    uu, vv = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)
    rng = np.random.default_rng(7)
    pts = rng.random((60, 2))
    pal = np.array([hexc(c) for c in ("2d5ab8", "3e8ed8", "b8322e", "e0a030", "3f9a52", "7a4ab0", "2d5ab8", "e8c860")])
    d = np.full(uu.shape, 9.0)
    d2 = np.full(uu.shape, 9.0)
    idx = np.zeros(uu.shape, np.int32)
    for i, (px, py) in enumerate(pts):
        dd = (uu - px) ** 2 + ((vv - py) * 2) ** 2
        closer = dd < d
        d2 = np.where(closer, d, np.minimum(d2, dd))
        idx = np.where(closer, i, idx)
        d = np.where(closer, dd, d)
    c = pal[idx % len(pal)]
    lead = (np.sqrt(d2) - np.sqrt(d)) < 0.012
    # the rose near the top
    ru, rv = uu - 0.5, (vv - 0.72) * 2
    rr = np.sqrt(ru ** 2 + rv ** 2)
    ra = np.arctan2(ru, rv)
    rose = rr < 0.2 + 0.08 * np.cos(8 * ra)
    c[rose] = hexc("f0c040")
    c[rr < 0.08] = hexc("c02828")
    lead |= np.abs(rr - (0.2 + 0.08 * np.cos(8 * ra))) < 0.012
    lead |= (uu < 0.03) | (uu > 0.97) | (np.abs(vv - 0.45) < 0.008)
    c[lead] = hexc("1a1512")
    return np.clip(c, 0, 1)


def make_notice_image():
    """Parchment notices (512 x 512, 2 x 2): scribbled lines, a red seal, a sketch."""
    n = 512
    uu, vv = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n)
    c = np.zeros((n, n, 3), np.float32) + hexc("eadbb4")
    c *= (0.92 + 0.08 * np.sin(uu * 37) * np.sin(vv * 23))[..., None]
    lu = (uu * 2) % 1
    lv = (vv * 2) % 1
    q = (np.floor(uu * 2) + 2 * np.floor(vv * 2)).astype(int)
    ink = hexc("3a2a1c")
    lines = (np.abs(((lv - 0.12) * 14) % 1 - 0.5) < 0.1) & (lv > 0.12) & (lv < 0.78) & (lu > 0.12) & (lu < 0.88)
    lines &= np.sin(lu * 220 + np.floor(lv * 14) * 3) > -0.6
    c[lines] = ink
    title = (lv > 0.82) & (lv < 0.9) & (lu > 0.22) & (lu < 0.78)
    c[title] = hexc("7a1f1f")
    seal = ((lu - 0.78) ** 2 + (lv - 0.12) ** 2) < 0.006
    c[seal & ((q == 0) | (q == 3))] = hexc("a82424")
    sketch = (q == 1) & (np.abs(np.sqrt((lu - 0.5) ** 2 + (lv - 0.45) ** 2) - 0.2) < 0.012)
    c[sketch] = ink
    c[(lu < 0.03) | (lu > 0.97) | (lv < 0.03) | (lv > 0.97)] *= 0.8
    return np.clip(c, 0, 1)


log("images")
IMG_FLOOR = np_image("floor_albedo", make_floor_image(1024 if QUICK else 4096))
IMG_BANNER = np_image("banners", make_banner_image())
IMG_GLASS = np_image("glass", make_glass_image())
IMG_NOTICE = np_image("notices", make_notice_image())


# ---------------------------------------------------------------- materials (for the bake only)
# the city's painted kit textures, mapped to the kit's material library (any folder of maps
# with these names works: --textures)
SURFACES = {"T_Brick_BaseColor": "ashlar", "T_Plaster_BaseColor": "plaster",
            "T_RockTrim_BaseColor": "trim", "T_WoodTrim_BaseColor": "timber",
            "T_UnevenBrick_BaseColor": "stone"}


def load_kit(name):
    base = SURFACES.get(name, name)
    for ext in (".jpg", ".png", ".webp"):
        p = os.path.join(TEXTURES, base + ext)
        if os.path.exists(p):
            return bpy.data.images.load(p, check_existing=True)
    raise SystemExit("HALL_ERROR no surface map %r in %s (--textures)" % (base, TEXTURES))


MATS = {}


def mat_base(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 1.0
    b.inputs["Specular IOR Level"].default_value = 0.0
    MATS[name] = m
    return m, nt, b


def mat_tex(name, image, tint="ffffff", tile=2.0, uvmap="uv0", offset=(0.0, 0.0)):
    """Kit texture repeated every `tile` metres over uv0 (metres), times a tint."""
    m, nt, b = mat_base(name)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = uvmap
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0 / tile, 1.0 / tile, 1.0)
    mp.inputs["Location"].default_value = (offset[0], offset[1], 0.0)
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = image
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    mix.inputs[7].default_value = tuple(hexc(tint)) + (1.0,)
    nt.links.new(uv.outputs[0], mp.inputs[0])
    nt.links.new(mp.outputs[0], tx.inputs[0])
    nt.links.new(tx.outputs[0], mix.inputs[6])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    return m


def mat_col(name, col, noise=0.0):
    m, nt, b = mat_base(name)
    c = tuple(hexc(col)) + (1.0,)
    if noise <= 0:
        b.inputs["Base Color"].default_value = c
        return m
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 6.0
    ramp = nt.nodes.new("ShaderNodeMix")
    ramp.data_type = "RGBA"
    ramp.inputs[6].default_value = tuple(hexc(col) * (1 - noise)) + (1.0,)
    ramp.inputs[7].default_value = c
    nt.links.new(nz.outputs[0], ramp.inputs["Factor"])
    nt.links.new(ramp.outputs[2], b.inputs["Base Color"])
    return m


def mat_img(name, image, emit=0.0):
    """An image over uv0 in 0..1 (banners, glass, notices, the floor)."""
    m, nt, b = mat_base(name)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "uv0"
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = image
    nt.links.new(uv.outputs[0], tx.inputs[0])
    if emit > 0:
        b.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
        nt.links.new(tx.outputs[0], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    else:
        nt.links.new(tx.outputs[0], b.inputs["Base Color"])
    return m


def mat_emit(name, col, strength):
    m, nt, b = mat_base(name)
    b.inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1)
    b.inputs["Emission Color"].default_value = tuple(hexc(col)) + (1.0,)
    b.inputs["Emission Strength"].default_value = strength
    return m


T_BRICK = load_kit("T_Brick_BaseColor")
T_PLASTER = load_kit("T_Plaster_BaseColor")
T_TRIM = load_kit("T_RockTrim_BaseColor")
T_WOOD = load_kit("T_WoodTrim_BaseColor")
T_UNEVEN = load_kit("T_UnevenBrick_BaseColor")
mat_tex("brick", T_BRICK, "f2dcb8", 2.6)
mat_tex("brick_low", T_BRICK, "d8c09c", 2.6)
mat_tex("trim", T_TRIM, "f0dcc0", 2.0)
mat_tex("plaster", T_PLASTER, "f6e8cc", 3.5)
mat_tex("plaster_warm", T_PLASTER, "eed4a8", 3.5)
mat_tex("coffer", T_PLASTER, "5a78b8", 2.0)
mat_tex("marble", T_PLASTER, "fbf6ee", 1.6)
mat_tex("wood", T_WOOD, "ffffff", 2.0)
mat_tex("stone", T_UNEVEN, "e0d4c0", 1.6)
mat_img("mosaic", IMG_FLOOR)
MATS["mosaic"].node_tree.nodes["UV Map"].uv_map = "uvf"
mat_img("banner", IMG_BANNER)
mat_img("glass", IMG_GLASS, emit=5.0)
mat_img("notice", IMG_NOTICE)
mat_col("gold", "d9ad4c", 0.25)
mat_col("iron", "2c2a2c", 0.3)
mat_col("dark_wood", "4a3020", 0.3)
mat_col("board", "6a4428", 0.3)
mat_emit("coals", "ff5a14", 2.2)
mat_emit("lamp", "ffb860", 2.6)
mat_emit("sky_hole", "9cc4ff", 1.0)


# ---------------------------------------------------------------- mesh building
class MB:
    """Collects faces in game coordinates; becomes one Blender object."""

    def __init__(self, name, atlas, smooth=False):
        self.name, self.atlas, self.smooth = name, atlas, smooth
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("uv0")
        self.uvf = self.bm.loops.layers.uv.new("uvf")   # the floor image's planar map
        self.grp = self.bm.faces.layers.int.new("grp")  # lightmap island groups (see finish)
        self.cur_grp = -1
        self.n_grp = 0
        self.mats = []

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def face(self, pts, uvs, mat, hint=None):
        pts = [Vector(p) for p in pts]
        if hint is not None:
            n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
            if n.length < 1e-9 and len(pts) > 3:
                n = (pts[2] - pts[0]).cross(pts[3] - pts[0])
            if n.dot(Vector(hint)) < 0:
                pts = pts[::-1]
                uvs = uvs[::-1]
        vs = [self.bm.verts.new(G(p)) for p in pts]
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.mi(mat)
        f.smooth = self.smooth
        f[self.grp] = self.cur_grp
        for lp, uv, p in zip(f.loops, uvs, pts):
            lp[self.uv].uv = uv
            lp[self.uvf].uv = ((p.x + FLOOR_L) / (2 * FLOOR_L), (p.z + FLOOR_L) / (2 * FLOOR_L))
        return f

    def quad(self, a, b, c, d, mat, hint=None, uv=None):
        """a b c d round the quad; uv default: metres along ab and ad."""
        if uv is None:
            w = (Vector(b) - Vector(a)).length
            h = (Vector(d) - Vector(a)).length
            uv = [(0, 0), (w, 0), (w, h), (0, h)]
        return self.face([a, b, c, d], uv, mat, hint)

    def box(self, c, size, mat, yaw=0.0, skip=()):
        """Axis box of `size` centred on c (turned by yaw about Y), faces outward."""
        c = Vector(c)
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        cs, sn = math.cos(yaw), math.sin(yaw)

        def P(x, y, z):
            return c + V(x * cs + z * sn, y, -x * sn + z * cs)
        faces = {
            "top": ([P(-hx, hy, -hz), P(hx, hy, -hz), P(hx, hy, hz), P(-hx, hy, hz)], UP),
            "bottom": ([P(-hx, -hy, -hz), P(-hx, -hy, hz), P(hx, -hy, hz), P(hx, -hy, -hz)], -UP),
            "px": ([P(hx, -hy, -hz), P(hx, -hy, hz), P(hx, hy, hz), P(hx, hy, -hz)], P(1, 0, 0) - c),
            "nx": ([P(-hx, -hy, hz), P(-hx, -hy, -hz), P(-hx, hy, -hz), P(-hx, hy, hz)], P(-1, 0, 0) - c),
            "pz": ([P(hx, -hy, hz), P(-hx, -hy, hz), P(-hx, hy, hz), P(hx, hy, hz)], P(0, 0, 1) - c),
            "nz": ([P(-hx, -hy, -hz), P(hx, -hy, -hz), P(hx, hy, -hz), P(-hx, hy, -hz)], P(0, 0, -1) - c),
        }
        for k, (pts, n) in faces.items():
            if k in skip:
                continue
            self.quad(*pts, mat, hint=n)

    def obox(self, c, ax, ay, az, size, mat):
        """Box of `size` centred on c along the (orthonormal, game space) axes ax, ay, az."""
        c = Vector(c)
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        P = lambda x, y, z: c + ax * x + ay * y + az * z
        for sgn in (-1, 1):
            self.quad(P(sgn * hx, -hy, -hz), P(sgn * hx, hy, -hz), P(sgn * hx, hy, hz), P(sgn * hx, -hy, hz), mat, hint=ax * sgn)
            self.quad(P(-hx, sgn * hy, -hz), P(hx, sgn * hy, -hz), P(hx, sgn * hy, hz), P(-hx, sgn * hy, hz), mat, hint=ay * sgn)
            self.quad(P(-hx, -hy, sgn * hz), P(hx, -hy, sgn * hz), P(hx, hy, sgn * hz), P(-hx, hy, sgn * hz), mat, hint=az * sgn)

    def lathe(self, center, profile, n, mat, sign=1, a0=0.0, a1=2 * math.pi, mats=None, uv_h=None):
        """Revolves profile [(r, y), ...] round the Y axis through center. sign +1: normals
        point to the right of the profile's direction in the (r, y) plane (outward for a
        profile that climbs the outside and turns in over the top)."""
        center = Vector(center)
        self.n_grp += 1
        call = self.n_grp
        span = max(max(r for r, _ in profile) * abs(a1 - a0), 1e-3)
        sectors = max(1, min(n, int(span / 10.0)))   # lightmap islands about 10 m wide
        for i in range(len(profile) - 1):
            (r0, y0), (r1, y1) = profile[i], profile[i + 1]
            n2 = (y1 - y0, -(r1 - r0))
            m = mats[i] if mats else mat
            seg_len = math.hypot(r1 - r0, y1 - y0)
            vacc = sum(math.hypot(profile[k + 1][0] - profile[k][0], profile[k + 1][1] - profile[k][1]) for k in range(i))
            for j in range(n):
                self.cur_grp = call * 1000 + (j * sectors) // n
                t0 = a0 + (a1 - a0) * j / n
                t1 = a0 + (a1 - a0) * (j + 1) / n
                d0, d1 = dirv(t0), dirv(t1)
                pa = center + d0 * r0 + UP * y0
                pb = center + d1 * r0 + UP * y0
                pc = center + d1 * r1 + UP * y1
                pd = center + d0 * r1 + UP * y1
                dm = dirv((t0 + t1) / 2)
                hint = (dm * n2[0] + UP * n2[1]) * sign
                rr = max(r0, r1, 0.3)
                u0, u1 = t0 * rr, t1 * rr
                uvs = [(u0, vacc), (u1, vacc), (u1, vacc + seg_len), (u0, vacc + seg_len)]
                if r0 < 1e-6:
                    self.face([pa, pc, pd], [uvs[0], uvs[2], uvs[3]], m, hint)
                elif r1 < 1e-6:
                    self.face([pa, pb, pc], uvs[:3], m, hint)
                else:
                    self.face([pa, pb, pc, pd], uvs, m, hint)
        self.cur_grp = -1

    def finish(self):
        me = bpy.data.meshes.new(self.name)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.0004)
        # cut big rings (floors, the gallery) into sectors so their lightmap islands pack
        cut = [e for e in self.bm.edges if len(e.link_faces) == 2 and e.link_faces[0][self.grp] != e.link_faces[1][self.grp]
               and max(e.link_faces[0][self.grp], e.link_faces[1][self.grp]) >= 0]
        if cut:
            bmesh.ops.split_edges(self.bm, edges=cut)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(MATS[m])
        ob = bpy.data.objects.new(self.name, me)
        SC.collection.objects.link(ob)
        ob["atlas"] = self.atlas
        return ob


# ---------------------------------------------------------------- the floor and the dais
log("floor")
fl = MB("floor_inner", "floor")
fl.lathe(V(0, 0, 0), [(24.0, 0.0), (18.0, 0.0), (12.0, 0.0), (7.0, 0.0)], 128, "mosaic")
# the dais: marble treads, trim risers, the medallion on top
prof = [(7.2, 0.0), (7.2, 0.3), (5.9, 0.3), (5.9, 0.6), (4.6, 0.6), (4.6, 0.9)]
fl.lathe(V(0, 0, 0), prof, 96, None, mats=["trim", "marble", "trim", "marble", "trim"])
fl.lathe(V(0, 0, 0), [(4.6, 0.9), (2.4, 0.9), (0.0, 0.9)], 96, "mosaic")
fl.finish()

fo = MB("floor_outer", "walls")
fo.lathe(V(0, 0, 0), [(R + 0.01, 0.0), (29.0, 0.0), (24.0, 0.0)], 128, "mosaic")

# ---------------------------------------------------------------- the drum, the alcoves
log("walls")
wl = fo   # the lower drum shares the walls atlas
PANEL = 5.2          # half width of a booth panel (arc length)
LOW_TOP = GAL_Y - 0.5


def arch_curve(n_arc=16):
    """The alcove opening, as (u, v) from bottom left, up, over, down to bottom right."""
    pts = [(-ALC_W, 0.0), (-ALC_W, ALC_SPRING)]
    for i in range(1, n_arc):
        t = math.pi - math.pi * i / n_arc
        pts.append((ALC_W * math.cos(t), ALC_SPRING + ALC_W * math.sin(t)))
    pts += [(ALC_W, ALC_SPRING), (ALC_W, 0.0)]
    return pts


def panel_outline(pts, half, top):
    """Matching points round the panel border for each arch point (same parameter t)."""
    out = []
    for u, v in pts:
        if v <= ALC_SPRING + 1e-6 and abs(u) >= ALC_W - 1e-6:
            out.append((math.copysign(half, u), v))
        else:
            # project from the arch centre onto the rectangle
            du, dv = u, v - ALC_SPRING
            s = min(half / max(abs(du), 1e-6), (top - ALC_SPRING) / max(dv, 1e-6))
            out.append((du * s, ALC_SPRING + dv * s))
    return out


ARCH = arch_curve()
OUTL = panel_outline(ARCH, PANEL, LOW_TOP)
for k, a in enumerate(BOOTH_A):
    d, t = dirv(a), tanv(a)
    inward = -d
    # the panel round the arch, on the drum
    for i in range(len(ARCH) - 1):
        p0 = on_drum(a, ARCH[i][0], ARCH[i][1])
        p1 = on_drum(a, ARCH[i + 1][0], ARCH[i + 1][1])
        q1 = on_drum(a, OUTL[i + 1][0], OUTL[i + 1][1])
        q0 = on_drum(a, OUTL[i][0], OUTL[i][1])
        uvs = [(ARCH[i][0], ARCH[i][1]), (ARCH[i + 1][0], ARCH[i + 1][1]), (OUTL[i + 1][0], OUTL[i + 1][1]), (OUTL[i][0], OUTL[i][1])]
        wl.face([p0, p1, q1, q0], uvs, "brick", hint=inward)
    # the corners the strip skips where the outline turns from a side onto the top
    for i in range(len(OUTL) - 1):
        (u0, v0), (u1, v1) = OUTL[i], OUTL[i + 1]
        side0 = abs(abs(u0) - PANEL) < 1e-6 and v0 < LOW_TOP - 1e-6
        top1 = abs(v1 - LOW_TOP) < 1e-6
        top0 = abs(v0 - LOW_TOP) < 1e-6
        side1 = abs(abs(u1) - PANEL) < 1e-6 and v1 < LOW_TOP - 1e-6
        if (side0 and top1) or (top0 and side1):
            cu = math.copysign(PANEL, u0 if side0 else u1)
            wl.face([on_drum(a, u0, v0), on_drum(a, cu, LOW_TOP), on_drum(a, u1, v1)], [(u0, v0), (cu, LOW_TOP), (u1, v1)], "brick", hint=inward)
    # the alcove: jambs and vault (the arch pushed straight back), back wall, floor
    back = [d * ALC_D + t * u + UP * v for u, v in ARCH]
    front = [on_drum(a, u, v) for u, v in ARCH]
    acc = 0.0
    for i in range(len(ARCH) - 1):
        seg = math.hypot(ARCH[i + 1][0] - ARCH[i][0], ARCH[i + 1][1] - ARCH[i][1])
        mid = (front[i] + front[i + 1] + back[i] + back[i + 1]) * 0.25
        hint = d * mid.dot(d) + UP * ALC_SPRING - mid
        vault = ARCH[i][1] > ALC_SPRING + 0.01 or ARCH[i + 1][1] > ALC_SPRING + 0.01
        if not vault:
            hint.y = 0.0
        dep = (back[i] - front[i]).length
        wl.face([front[i], front[i + 1], back[i + 1], back[i]], [(acc, 0), (acc + seg, 0), (acc + seg, dep), (acc, dep)],
                "plaster_warm" if vault else "brick_low", hint=hint)
        acc += seg
    # back wall (a fan from the centre of its bottom)
    cb = d * ALC_D
    for i in range(len(ARCH) - 1):
        wl.face([cb, back[i], back[i + 1]], [(0, 0), ARCH[i], ARCH[i + 1]], "brick", hint=inward)
    # floor of the alcove (slabs, from the floor image)
    fa = [front[0] + UP * 0.005, front[-1] + UP * 0.005, back[-1] + UP * 0.005, back[0] + UP * 0.005]
    wl.face(fa, [(0, 0), (7, 0), (7, 4), (0, 4)], "mosaic", hint=UP)
    # pilasters and an archivolt round the opening
    for sgn in (-1, 1):
        c = on_drum(a, sgn * (ALC_W + 0.55), (LOW_TOP) / 2, R - 0.2)
        wl.box(c, (0.9, LOW_TOP, 0.4), "trim", yaw=a)
    # archivolt: a band 0.45 m wide round the arch, standing 0.14 m proud
    for i in range(1, len(ARCH) - 2):
        u0, v0 = ARCH[i]
        u1, v1 = ARCH[i + 1]
        if v0 < ALC_SPRING - 1e-3 or v1 < ALC_SPRING - 1e-3:
            continue
        def off(u, v, s):
            du, dv = u, v - ALC_SPRING
            L = math.hypot(du, dv)
            return (du * (L + s) / L, ALC_SPRING + dv * (L + s) / L)
        o0, o1 = off(u0, v0, 0.45), off(u1, v1, 0.45)
        rr = R - 0.14
        wl.face([on_drum(a, u0, v0, rr), on_drum(a, u1, v1, rr), on_drum(a, *o1, rr), on_drum(a, *o0, rr)],
                [(u0, v0), (u1, v1), o1, o0], "trim", hint=inward)
        wl.face([on_drum(a, u0, v0, rr), on_drum(a, u1, v1, rr), on_drum(a, u1, v1, R), on_drum(a, u0, v0, R)],
                [(0, 0), (0.3, 0), (0.3, 0.14), (0, 0.14)], "trim", hint=UP * ALC_SPRING - on_drum(a, u0, v0))

# the plain drum between the booth panels, floor to gallery
for k in range(8):
    a0 = BOOTH_A[k] + PANEL / R
    a1 = BOOTH_A[(k + 1) % 8] - PANEL / R + (2 * math.pi if k == 7 else 0.0)
    n = 10
    for j in range(n):
        t0 = a0 + (a1 - a0) * j / n
        t1 = a0 + (a1 - a0) * (j + 1) / n
        p = [dirv(t0) * R, dirv(t1) * R, dirv(t1) * R + UP * LOW_TOP, dirv(t0) * R + UP * LOW_TOP]
        u0, u1 = t0 * R, t1 * R
        wl.face(p, [(u0, 0), (u1, 0), (u1, LOW_TOP), (u0, LOW_TOP)], "brick", hint=-dirv((t0 + t1) / 2))
# a skirting band round the whole foot of the wall
for k in range(8):
    s0 = BOOTH_A[k] + ALC_W / R
    s1 = BOOTH_A[(k + 1) % 8] - ALC_W / R + (2 * math.pi if k == 7 else 0.0)
    wl.lathe(V(0, 0, 0), [(R - 0.25, 0.0), (R - 0.25, 0.6), (R, 0.6)], 14, "trim", sign=-1, a0=s0, a1=s1)
wl.finish()

# ---------------------------------------------------------------- the upper drum, windows, gallery, stairs
log("upper")
up = MB("upper", "upper")
N_UP = 128
WIN_A = [math.radians(22.5 + 45.0 * k) for k in range(8)]
WIN_W, WIN_Y0, WIN_SPRING = 1.4, 10.0, 14.0
# the upper drum (the windows are panes laid on it, lit from within)
for j in range(N_UP):
    up.cur_grp = 7000 + j // 8
    t0, t1 = 2 * math.pi * j / N_UP, 2 * math.pi * (j + 1) / N_UP
    p = [dirv(t0) * R + UP * LOW_TOP, dirv(t1) * R + UP * LOW_TOP, dirv(t1) * R + UP * WALL_TOP, dirv(t0) * R + UP * WALL_TOP]
    up.face(p, [(t0 * R, LOW_TOP), (t1 * R, LOW_TOP), (t1 * R, WALL_TOP), (t0 * R, WALL_TOP)], "brick", hint=-dirv((t0 + t1) / 2))
up.cur_grp = -1
# a cornice where the dome springs and a band at the gallery rail
up.lathe(V(0, 0, 0), [(R, WALL_TOP - 0.9), (R - 0.35, WALL_TOP - 0.7), (R - 0.35, WALL_TOP - 0.3), (R - 0.6, WALL_TOP)], N_UP, "trim", sign=-1)
for a in WIN_A:
    # the pane: an arched shape, stained glass, just proud of the wall
    rr = R - 0.03
    pts = [(-WIN_W, WIN_Y0), (WIN_W, WIN_Y0), (WIN_W, WIN_SPRING)]
    for i in range(1, 12):
        tt = math.pi * i / 12
        pts.append((WIN_W * math.cos(tt), WIN_SPRING + WIN_W * math.sin(tt)))
    pts.append((-WIN_W, WIN_SPRING))
    cu, cv = 0.0, (WIN_Y0 + WIN_SPRING) / 2
    H = WIN_SPRING + WIN_W - WIN_Y0
    def wuv(u, v):
        return ((u + WIN_W) / (2 * WIN_W), (v - WIN_Y0) / H)
    for i in range(len(pts)):
        u0, v0 = pts[i]
        u1, v1 = pts[(i + 1) % len(pts)]
        up.face([on_drum(a, cu, cv, rr), on_drum(a, u0, v0, rr), on_drum(a, u1, v1, rr)],
                [wuv(cu, cv), wuv(u0, v0), wuv(u1, v1)], "glass", hint=-dirv(a))
    # a stone frame round it
    frame = [(-WIN_W, WIN_Y0)] + [(-WIN_W, WIN_SPRING)] + [(WIN_W * math.cos(math.pi - math.pi * i / 12), WIN_SPRING + WIN_W * math.sin(math.pi - math.pi * i / 12)) for i in range(1, 12)] + [(WIN_W, WIN_SPRING), (WIN_W, WIN_Y0)]
    for i in range(len(frame) - 1):
        (u0, v0), (u1, v1) = frame[i], frame[i + 1]
        def grow(u, v, s):
            if v <= WIN_SPRING:
                return (u + math.copysign(s, u), v)
            du, dv = u, v - WIN_SPRING
            L = math.hypot(du, dv)
            return (du * (L + s) / L, WIN_SPRING + dv * (L + s) / L)
        o0, o1 = grow(u0, v0, 0.35), grow(u1, v1, 0.35)
        r2 = R - 0.12
        up.face([on_drum(a, u0, v0, r2), on_drum(a, u1, v1, r2), on_drum(a, *o1, r2), on_drum(a, *o0, r2)],
                [(u0, v0), (u1, v1), o1, o0], "trim", hint=-dirv(a))
    up.box(on_drum(a, 0, WIN_Y0 - 0.2, R - 0.25), (2 * WIN_W + 1.0, 0.4, 0.5), "trim", yaw=a)

# gallery: slab (planks on top, plaster under), its edge, corbels, the balustrade
gal_top = [(R, GAL_Y), (GAL_IN, GAL_Y)]
up.lathe(V(0, 0, 0), gal_top, N_UP, "wood")
up.lathe(V(0, 0, 0), [(GAL_IN, GAL_Y), (GAL_IN, GAL_Y - 0.5), (R, GAL_Y - 0.5)], N_UP, None, mats=["trim", "plaster"])
for j in range(48):
    a = 2 * math.pi * (j + 0.5) / 48
    if min(abs(math.remainder(a - b, 2 * math.pi)) for b in BOOTH_A) < math.radians(4.5):
        continue
    up.box(dirv(a) * (GAL_IN + 0.45) + UP * (GAL_Y - 0.85), (0.4, 0.7, 0.9), "trim", yaw=a)
# balustrade: plinth, balusters, rail; open where the stairs arrive
STAIR_TOP_A = [sa + math.atan2(7.4 + 0.9, 27.0 + 0.9) for sa in STAIR_ANGLES]


def in_gap(a, half=math.radians(2.6)):
    return any(abs(math.remainder(a - g, 2 * math.pi)) < half for g in STAIR_TOP_A)


NB = 200
for j in range(NB):
    t0, t1 = 2 * math.pi * j / NB, 2 * math.pi * (j + 1) / NB
    if in_gap((t0 + t1) / 2):
        continue
    up.cur_grp = 8000 + j // 12
    for (ra, rb, y0, y1, m) in ((GAL_IN - 0.02, GAL_IN + 0.3, GAL_Y, GAL_Y + 0.18, "trim"), (GAL_IN - 0.05, GAL_IN + 0.33, GAL_Y + 1.0, GAL_Y + 1.12, "trim")):
        d0, d1 = dirv(t0), dirv(t1)
        up.face([d0 * ra + UP * y1, d1 * ra + UP * y1, d1 * rb + UP * y1, d0 * rb + UP * y1], [(t0 * ra, 0), (t1 * ra, 0), (t1 * ra, 0.3), (t0 * ra, 0.3)], m, hint=UP)
        up.face([d0 * ra + UP * y0, d1 * ra + UP * y0, d1 * ra + UP * y1, d0 * ra + UP * y1], [(t0 * ra, y0), (t1 * ra, y0), (t1 * ra, y1), (t0 * ra, y1)], m, hint=-d0)
        up.face([d0 * rb + UP * y0, d1 * rb + UP * y0, d1 * rb + UP * y1, d0 * rb + UP * y1], [(t0 * rb, y0), (t1 * rb, y0), (t1 * rb, y1), (t0 * rb, y1)], m, hint=d0)
        if m == "trim" and y0 > GAL_Y:
            up.face([d0 * ra + UP * y0, d1 * ra + UP * y0, d1 * rb + UP * y0, d0 * rb + UP * y0], [(0, 0), (1, 0), (1, 1), (0, 1)], m, hint=-UP)
    am = (t0 + t1) / 2
    up.cur_grp = -1
    up.lathe(dirv(am) * (GAL_IN + 0.14) + UP * (GAL_Y + 0.18), [(0.07, 0.0), (0.1, 0.12), (0.05, 0.35), (0.09, 0.6), (0.05, 0.82)], 4, "marble", a0=am + math.pi / 4, a1=am + math.pi / 4 + 2 * math.pi)

# stairs: straight flights in the ambulatory, rising clockwise to a landing at the gallery
STAIR_D, STAIR_HALF, STAIR_W, N_STEP = 27.0, 7.4, 1.9, 32
STAIRS = []
for sa in STAIR_ANGLES:
    d, t = dirv(sa), tanv(sa)
    # runs along -t (toward larger angle) from the bottom at +t*HALF to the top at -t*HALF
    start = d * STAIR_D + t * STAIR_HALF
    run = -t
    tread = 2 * STAIR_HALF / N_STEP
    rise = GAL_Y / N_STEP
    for i in range(N_STEP):
        c = start + run * (tread * (i + 0.5)) + UP * (rise * (i + 1) / 2)
        yaw = math.atan2(run.x, run.z)
        up.box(c, (STAIR_W, rise * (i + 1), tread), "stone", yaw=yaw, skip=("bottom",))
    top = start + run * (2 * STAIR_HALF)
    # landing from the last step to the gallery edge
    land_c = top + run * 0.9 + d * 0.9 + UP * (GAL_Y - 0.25)
    up.box(land_c, (STAIR_W + 1.8, 0.5, 1.8), "wood", yaw=math.atan2(run.x, run.z))
    STAIRS.append((start, top, run, d))
up.finish()

# ---------------------------------------------------------------- the colonnade and entablature
log("columns")
co = MB("columns", "columns", smooth=True)
COL_A = [math.radians(11.25 + 22.5 * k) for k in range(N_COL)]
for a in COL_A:
    c = dirv(a) * COL_R
    co.box(c + UP * 0.25, (1.7, 0.5, 1.7), "trim", yaw=a)
    co.lathe(c + UP * 0.5, [(0.82, 0.0), (0.86, 0.12), (0.8, 0.26), (0.72, 0.34), (0.7, 0.4)], 16, "marble")
    shaft = [(0.7, 0.4)]
    for i in range(1, 7):
        y = 0.4 + 10.0 * i / 6
        shaft.append((0.7 - 0.08 * (i / 6) ** 1.5, y))
    co.lathe(c + UP * 0.5, shaft, 16, "marble")
    co.lathe(c + UP * 10.9, [(0.62, 0.0), (0.66, 0.1), (0.68, 0.2), (0.9, 0.7), (1.0, 0.95)], 16, "marble")
    co.box(c + UP * 12.0, (2.1, 0.3, 2.1), "trim", yaw=a)
# entablature: soffit, faces, a cornice lip
ENT0, ENT1 = 12.15, 13.6
co.lathe(V(0, 0, 0), [(COL_R + 1.1, ENT0), (COL_R - 1.1, ENT0)], 96, "plaster", sign=-1)
co.lathe(V(0, 0, 0), [(COL_R - 1.1, ENT0), (COL_R - 1.1, ENT1 - 0.4), (COL_R - 1.35, ENT1 - 0.2), (COL_R - 1.35, ENT1), (COL_R, ENT1)], 96, None, sign=-1, mats=["trim", "gold", "trim", "trim"])
co.lathe(V(0, 0, 0), [(COL_R + 1.1, ENT0), (COL_R + 1.1, ENT1 - 0.4), (COL_R + 1.35, ENT1 - 0.2), (COL_R + 1.35, ENT1), (COL_R, ENT1)], 96, None, sign=1, mats=["trim", "gold", "trim", "trim"])
# hanging lanterns on chains from the entablature, over the path to each booth
LANTERNS = []
for a in BOOTH_A:
    c = dirv(a) * COL_R
    co.box(c + UP * ((ENT0 + 9.6) / 2), (0.06, ENT0 - 9.6, 0.06), "iron")
    co.lathe(c + UP * 8.6, [(0.0, 1.35), (0.34, 1.05), (0.38, 0.95), (0.28, 0.9)], 8, "iron", sign=-1)
    co.lathe(c + UP * 8.6, [(0.28, 0.9), (0.3, 0.3), (0.28, 0.25)], 8, "lamp", sign=-1)
    co.lathe(c + UP * 8.6, [(0.28, 0.25), (0.34, 0.15), (0.2, 0.0), (0.0, -0.15)], 8, "iron", sign=-1)
    LANTERNS.append(c + UP * 9.2)
co.finish()

# ---------------------------------------------------------------- the dome
log("dome")
dm = MB("dome", "dome", smooth=True)
N_DOME = 32
ROWS = 5
PHI_A, PHI_B = math.radians(16.0), math.radians(63.0)


def sph(phi, th, rad=Rs):
    return V(0, DOME_CY, 0) + dirv(th) * (rad * math.sin(phi)) + UP * (rad * math.cos(phi))


def dome_band(p0, p1, n, mat, sub=1):
    for j in range(n):
        for s in range(sub):
            t0 = 2 * math.pi * (j + s / sub) / n
            t1 = 2 * math.pi * (j + (s + 1) / sub) / n
            a, b, c, d = sph(p0, t0), sph(p0, t1), sph(p1, t1), sph(p1, t0)
            L0 = Rs * p0
            L1 = Rs * p1
            dm.face([a, b, c, d], [(t0 * Rs * math.sin(p0), L0), (t1 * Rs * math.sin(p0), L0), (t1 * Rs * math.sin(p1), L1), (t0 * Rs * math.sin(p1), L1)], mat, hint=V(0, DOME_CY, 0) - (a + c) * 0.5)


dome_band(PHI1, PHI_A, N_DOME, "plaster", sub=2)
dome_band(PHI_B, PHI0, N_DOME, "plaster", sub=2)
dph = (PHI_B - PHI_A) / ROWS
for row in range(ROWS):
    p0 = PHI_A + dph * row
    p1 = p0 + dph
    for j in range(N_DOME):
        t0 = 2 * math.pi * j / N_DOME
        t1 = 2 * math.pi * (j + 1) / N_DOME
        # frame fraction: the rib between coffers
        fp, ft = 0.16, 0.16
        P = [p0, p0 + dph * fp, p1 - dph * fp, p1]
        T = [t0, t0 + (t1 - t0) * ft, t1 - (t1 - t0) * ft, t1]
        cen = V(0, DOME_CY, 0)
        # ribs: the ring of 8 quads round the coffer
        for (i0, j0) in ((0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)):
            a, b = sph(P[i0], T[j0]), sph(P[i0], T[j0 + 1])
            c, d = sph(P[i0 + 1], T[j0 + 1]), sph(P[i0 + 1], T[j0])
            dm.face([a, b, c, d], [(0, 0), (1, 0), (1, 1), (0, 1)], "plaster", hint=cen - a)
        # the sunk panel, and its four sloping sides (stepped twice)
        depth = 0.55
        inner = [(P[1], T[1]), (P[1], T[2]), (P[2], T[2]), (P[2], T[1])]
        shrink = 0.25
        pm, tm = (P[1] + P[2]) / 2, (T[1] + T[2]) / 2
        deep = [(pm + (p - pm) * (1 - shrink), tm + (t - tm) * (1 - shrink)) for p, t in inner]
        A = [sph(p, t) for p, t in inner]
        B = [sph(p, t, Rs + depth) for p, t in deep]
        for i in range(4):
            dm.face([A[i], A[(i + 1) % 4], B[(i + 1) % 4], B[i]], [(0, 0), (1, 0), (1, 0.3), (0, 0.3)], "plaster_warm", hint=cen - (A[i] + A[(i + 1) % 4]) * 0.5)
        dm.face(B, [(0, 0), (1, 0), (1, 1), (0, 1)], "coffer", hint=cen - B[0])
        # a gilt rosette in the middle of each coffer
        rc = sph(pm, tm, Rs + depth - 0.03)
        nrm = (cen - rc).normalized()
        ax1 = (sph(pm, tm + 0.01) - sph(pm, tm)).normalized()
        ax2 = nrm.cross(ax1)
        rs = 0.35 * (0.6 + 0.4 * math.sin(pm))
        ring = [rc + (ax1 * math.cos(q) + ax2 * math.sin(q)) * rs * (1.0 if i % 2 == 0 else 0.55) for i, q in enumerate([math.pi * 2 * i / 16 for i in range(16)])]
        for i in range(16):
            dm.face([rc, ring[i], ring[(i + 1) % 16]], [(0.5, 0.5), (0, 0), (1, 0)], "gold", hint=nrm)
# the oculus: a stone lip, and the sky beyond it (a disc far above, so the bake sees sky)
dm.lathe(V(0, 0, 0), [(OCULUS, OCULUS_Y - 0.05), (OCULUS, OCULUS_Y + 1.0), (OCULUS + 0.8, OCULUS_Y + 1.0)], 32, "trim", sign=-1)
dm.finish()

# ---------------------------------------------------------------- dressing: braziers, banners, signs, boards, props
log("props")
pr = MB("props_mb", "props", smooth=True)
BRAZIERS = []
for k in range(8):
    a = math.radians(22.5 + 45.0 * k)
    c = dirv(a) * BRAZIER_R
    pr.lathe(c, [(0.55, 0.0), (0.5, 0.1), (0.18, 0.2), (0.12, 0.8), (0.16, 0.9)], 12, "iron")
    pr.lathe(c + UP * 0.9, [(0.1, 0.0), (0.62, 0.22), (0.72, 0.42), (0.66, 0.45)], 16, "iron")
    pr.lathe(c + UP * 1.3, [(0.64, 0.0), (0.3, 0.06), (0.0, 0.08)], 12, "coals")
    BRAZIERS.append(c + UP * 1.32)

# the return portal: a ring of stones standing in the dais, sunk into it so one walks
# through; the veil inside it is veil.glb (animated), the entry volume is scene.json's
PORTAL_Z = -1.5
PORTAL_R, PORTAL_T = 2.05, 0.5
PORTAL_CY = DAIS[-1][1] + PORTAL_R - 0.35
NV = 20
for i in range(NV):
    a0, a1 = 2 * math.pi * i / NV, 2 * math.pi * (i + 1) / NV
    am = (a0 + a1) / 2
    rad = V(math.sin(am), math.cos(am), 0)
    tng = V(math.cos(am), -math.sin(am), 0)
    c = V(0, PORTAL_CY, PORTAL_Z) + rad * PORTAL_R
    ln = 2 * PORTAL_R * math.sin((a1 - a0) / 2) * 0.97
    key = i == 0
    pr.obox(c, tng, rad, V(0, 0, 1), (ln, PORTAL_T * (1.25 if key else 1.0), 0.85 if key else 0.7), "gold" if key else ("trim" if i % 2 else "marble"))
for i in range(NV * 2):
    a0, a1 = 2 * math.pi * i / (NV * 2), 2 * math.pi * (i + 1) / (NV * 2)
    p0 = V(0, PORTAL_CY, PORTAL_Z) + V(math.sin(a0), math.cos(a0), 0) * (PORTAL_R - PORTAL_T / 2)
    p1 = V(0, PORTAL_CY, PORTAL_Z) + V(math.sin(a1), math.cos(a1), 0) * (PORTAL_R - PORTAL_T / 2)
    ax = (p1 - p0).normalized()
    ay = V(0, 0, 1).cross(ax)
    pr.obox((p0 + p1) / 2, ax, ay, V(0, 0, 1), ((p1 - p0).length, 0.08, 0.76), "gold")
for sgn in (-1, 1):
    pr.box(V(sgn * (PORTAL_R + 0.05), DAIS[-1][1] + 0.35, PORTAL_Z), (1.0, 0.7, 1.0), "trim")

# upper banners: long, swallow-tailed, above each booth, hung from an iron pole
banner_mb = MB("banners", "props")
for k, a in enumerate(BOOTH_A):
    d, t = dirv(a), tanv(a)
    W, TOPY, BOTY = 1.3, 16.8, 9.0
    base = d * (R - 0.35)
    nv, nu = 14, 4
    grid = []
    for iv in range(nv + 1):
        fv = iv / nv
        row = []
        for iu in range(nu + 1):
            fu = iu / nu
            u = -W + 2 * W * fu
            y = BOTY + (TOPY - BOTY) * fv
            # swallow tail: the bottom edge dips at the middle
            if iv == 0:
                y = BOTY + 0.9 * (1 - abs(fu - 0.5) * 2)
            fold = 0.08 * math.sin(fu * math.pi * 3) * (1 - fv) ** 0.5
            row.append((base + t * u - d * fold + UP * y, ((k + fu) / 8.0, (y - BOTY) / (TOPY - BOTY))))
        grid.append(row)
    for iv in range(nv):
        for iu in range(nu):
            p = [grid[iv][iu], grid[iv][iu + 1], grid[iv + 1][iu + 1], grid[iv + 1][iu]]
            banner_mb.face([q[0] for q in p], [q[1] for q in p], "banner", hint=-d)
    banner_mb.box(base + UP * (TOPY + 0.08) - d * 0.05, (2 * W + 0.5, 0.1, 0.1), "iron", yaw=a)
    for sgn in (-1, 1):
        banner_mb.box(base + t * (sgn * (W + 0.25)) + UP * (TOPY + 0.08) - d * 0.05, (0.2, 0.2, 0.2), "gold", yaw=a)
banner_mb.finish()

# the sign over each arch (a board; the letters are text objects added below), and the
# mission board with its notices on the alcove's back wall
for k, a in enumerate(BOOTH_A):
    d, t = dirv(a), tanv(a)
    sign_c = d * (R - 0.32) + UP * 6.95
    pr.box(sign_c, (7.0, 0.8, 0.12), "dark_wood", yaw=a)
    pr.box(sign_c + UP * 0.43, (7.2, 0.08, 0.16), "gold", yaw=a)
    pr.box(sign_c - UP * 0.43, (7.2, 0.08, 0.16), "gold", yaw=a)
    bc = d * (ALC_D - 0.08) + UP * 2.75
    pr.box(bc, (3.0, 1.7, 0.1), "board", yaw=a)
    pr.box(bc - d * 0.05 + UP * 0.9, (3.2, 0.12, 0.14), "dark_wood", yaw=a)
    pr.box(bc - d * 0.05 - UP * 0.9, (3.2, 0.12, 0.14), "dark_wood", yaw=a)
    # notices: pinned at small angles
    rng = np.random.default_rng(k + 3)
    for i in range(7):
        nu = -1.2 + (i % 4) * 0.8 + rng.uniform(-0.1, 0.1)
        nvv = 0.35 if i < 4 else -0.4
        nu += 0.4 if i >= 4 else 0.0
        wq, hq = 0.3 + rng.uniform(0, 0.08), 0.4 + rng.uniform(0, 0.08)
        rot = rng.uniform(-0.12, 0.12)
        cq = bc - d * 0.06 + t * nu + UP * nvv
        pts = []
        for (du, dv) in ((-wq, -hq), (wq, -hq), (wq, hq), (-wq, hq)):
            ru = du * math.cos(rot) - dv * math.sin(rot)
            rv = du * math.sin(rot) + dv * math.cos(rot)
            pts.append(cq + t * ru + UP * rv)
        qx, qy = (i % 2) * 0.5, ((i // 2) % 2) * 0.5
        pr.face(pts, [(qx, qy), (qx + 0.5, qy), (qx + 0.5, qy + 0.5), (qx, qy + 0.5)], "notice", hint=-d)
    # two wall lanterns flanking the arch, under the gallery
    for sgn in (-1, 1):
        lc = on_drum(a, sgn * (ALC_W + 0.55), 4.6, R - 0.55)
        pr.box(lc + UP * 0.3, (0.34, 0.1, 0.34), "iron", yaw=a)
        pr.box(lc, (0.26, 0.42, 0.26), "lamp", yaw=a)
        pr.box(lc - UP * 0.26, (0.3, 0.08, 0.3), "iron", yaw=a)
pr_ob = pr.finish()


def text_object(body, size, loc, a, depth=0.02):
    cu = bpy.data.curves.new("txt", type="FONT")
    cu.body = body
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.0
    cu.resolution_u = 3
    ob = bpy.data.objects.new("txt", cu)
    SC.collection.objects.link(ob)
    d, t = dirv(a), tanv(a)
    M = Matrix.Identity(4)
    cols = [G(t), G(UP), G(-d)]
    for i in range(3):
        for j in range(3):
            M[j][i] = cols[i][j]
    M.translation = G(loc)
    ob.matrix_world = M
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    me.transform(M)
    bpy.data.objects.remove(ob)
    tob = bpy.data.objects.new("sign_text", me)
    SC.collection.objects.link(tob)
    me.materials.clear()
    me.materials.append(MATS["gold"])
    me.uv_layers.new(name="uv0")
    me.uv_layers.new(name="uvf")
    tob["atlas"] = "props"
    return tob


for k, a in enumerate(BOOTH_A):
    d = dirv(a)
    text_object(GUILDS[k][1], 0.46, d * (R - 0.4) + UP * 6.93, a)

# kit props, dressed per booth: (name, u across, w into the alcove from the drum, turn, scale)
BOOTH_PROPS = {
    "guild": [("Table_Large", 0, 0.9, 0, 1), ("WeaponStand", -2.3, 3.2, 0, 1), ("Shield_Wooden", 2.2, 3.5, 0, 1.3), ("Chest_Wood", 2.5, 2.4, -1.2, 0.5)],
    "rangers": [("Table_Large", 0, 0.9, 0, 1), ("Crate_Wooden", -2.5, 3.2, 0.3, 1), ("Barrel", 2.6, 3.2, 0, 1), ("Bag", -2.4, 2.1, 0.8, 1), ("Torch_Metal", 1.5, 3.8, 0, 1.4)],
    "tamers": [("Table_Large", 0, 0.9, 0, 1), ("Barrel_Apples", -2.5, 3.1, 0, 1), ("Bucket_Wooden_1", 2.3, 2.2, 0, 1.2), ("Crate_Wooden", 2.5, 3.3, -0.2, 0.9), ("Stool", -2.2, 1.9, 0, 1)],
    "bounty": [("Workbench", 0, 1.0, 0, 1.2), ("Barrel", -2.6, 3.2, 0, 1), ("Axe_Bronze", 2.3, 3.7, 0.3, 1.3), ("Chair_1", 2.4, 2.4, 2.6, 1)],
    "arcane": [("Table_Large", 0, 0.9, 0, 1), ("Bookcase_2", -2.2, 3.7, 0, 1), ("Cauldron", 2.3, 2.9, 0, 1), ("CandleStick_Triple", 0.9, 0.9, 0, 1, 0.81), ("BookStand", 2.6, 1.6, -0.6, 1)],
    "maps": [("Table_Large", 0, 0.9, 0, 1), ("Bookcase_2", 2.2, 3.7, 0, 1), ("Scroll_1", -0.6, 0.9, 0.4, 1.6, 0.81), ("Scroll_2", 0.5, 0.95, -0.3, 1.6, 0.81), ("Book_Stack_1", -1.1, 0.8, 0.2, 1.3, 0.81), ("Crate_Wooden", -2.5, 3.2, 0.2, 0.9)],
    "merchants": [("Table_Large", 0, 0.9, 0, 1), ("Coin_Pile", -0.6, 0.85, 0, 2.0, 0.81), ("Coin_Pile_2", 0.7, 0.9, 0.5, 2.0, 0.81), ("Chest_Wood", -2.5, 2.6, 1.2, 0.5), ("Barrel", 2.6, 3.2, 0, 1)],
    "dawn": [("Table_Large", 0, 0.9, 0, 1), ("Chalice", 0.4, 0.9, 0, 1.6, 0.81), ("Book_5", -0.5, 0.9, 0.3, 1.5, 0.81), ("Shield_Wooden", -2.3, 3.5, 0, 1.3), ("Barrel", 2.5, 3.2, 0, 1)],
}
_kit_cache = {}
_sizes = None


def catalogue_size(name):
    """[x, y (up), z] in metres of a built-in prop, by its file name, from kit/catalog."""
    global _sizes
    if _sizes is None:
        _sizes = {}
        try:
            with open(CATALOG, encoding="utf-8") as f:
                for e in json.load(f).get("entries", []):
                    fn = e.get("source", {}).get("file", "")
                    if fn.startswith("assets/props/") and e.get("size"):
                        _sizes[os.path.splitext(fn[len("assets/props/"):])[0]] = e["size"]
        except (OSError, ValueError):
            pass
    return _sizes.get(name, [0.5, 0.5, 0.5])


def standin_meshes(name):
    """Without --props: a box of the prop's catalogue size, standing on its base, so the
    booths keep their layout and the bake its shadows. Same shape as kit_meshes' result."""
    sx, sy, sz = catalogue_size(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:   # glTF +Y up is Blender +Z; glTF +Z (the front) is Blender -Y
        v.co = Vector((v.co.x * sx, v.co.y * sz, (v.co.z + 0.5) * sy))
    me = bpy.data.meshes.new("standin_" + name)
    bm.to_mesh(me)
    bm.free()
    uv = me.uv_layers.new(name="uv0")
    me.uv_layers.new(name="uvf")
    for poly in me.polygons:
        for k, li in enumerate(poly.loop_indices):
            uv.data[li].uv = ((0, 0), (1, 0), (1, 1), (0, 1))[k % 4]
    me.materials.append(MATS["dark_wood"])
    log("prop %s: stand-in box %.2f x %.2f x %.2f m (no --props file)" % (name, sx, sy, sz))
    return [(me, Matrix.Identity(4))]


def kit_meshes(name):
    """Imports a kit prop once: [(mesh, matrix in Blender space)] with uv0 as the UV name."""
    if name in _kit_cache:
        return _kit_cache[name]
    path = None
    if PROPS:
        for ext in (".gltf", ".glb"):
            if os.path.exists(os.path.join(PROPS, name + ext)):
                path = os.path.join(PROPS, name + ext)
                break
    if path is None:
        _kit_cache[name] = standin_meshes(name)
        return _kit_cache[name]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    out = []
    for o in new:
        if o.type == "MESH" and any(m is not None for m in o.data.materials):   # (helper shapes have none)
            me = o.data
            if me.uv_layers:
                me.uv_layers[0].name = "uv0"
            else:
                me.uv_layers.new(name="uv0")
            if "uvf" not in me.uv_layers:
                me.uv_layers.new(name="uvf")
            out.append((me, o.matrix_world.copy()))
    for o in new:
        bpy.data.objects.remove(o)
    for me, _ in out:
        for m in me.materials:
            if m and m.use_nodes:
                for n in m.node_tree.nodes:
                    if n.type == "UVMAP":
                        n.uv_map = "uv0"
                # as tools/bake_light.py does: kit surfaces count as opaque, matte, unlit
                b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if b is not None:
                    for lk in list(m.node_tree.links):
                        if lk.to_socket in (b.inputs["Alpha"], b.inputs["Metallic"]):
                            m.node_tree.links.remove(lk)
                    b.inputs["Alpha"].default_value = 1.0
                    b.inputs["Metallic"].default_value = 0.0
                    b.inputs["Specular IOR Level"].default_value = 0.2
                    if "Emission Strength" in b.inputs:
                        b.inputs["Emission Strength"].default_value = 0.0
    _kit_cache[name] = out
    return out


def place_kit(name, pos, a, turn=0.0, scale=1.0):
    d, t = dirv(a - turn), tanv(a - turn)
    R3 = Matrix.Identity(3)
    cols = [t, UP, -d]           # prop +X across, +Y up, front (glTF +Z) toward the hall
    for i in range(3):
        for j in range(3):
            R3[j][i] = cols[i][j]
    Mb = (GM @ R3 @ GM.transposed()).to_4x4() @ Matrix.Scale(scale, 4)
    Mb.translation = G(pos)
    obs = []
    for me, mw in kit_meshes(name):
        ob = bpy.data.objects.new("kit_" + name, me.copy())
        SC.collection.objects.link(ob)
        ob.data.transform(Mb @ mw)
        ob["atlas"] = "props"
        obs.append(ob)
    return obs


for k, a in enumerate(BOOTH_A):
    d, t = dirv(a), tanv(a)
    for e in BOOTH_PROPS[GUILDS[k][0]]:
        name, u, w, turn, sc = e[:5]
        y = e[5] if len(e) > 5 else 0.0
        place_kit(name, d * (R + w) + t * u + UP * y, a, turn, sc)

# ---------------------------------------------------------------- lights (bake only)
log("lights")


def point(name, p, col, power, radius=0.2):
    li = bpy.data.lights.new(name, "POINT")
    li.color = tuple(hexc(col))
    li.energy = power
    li.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, li)
    ob.location = G(p)
    SC.collection.objects.link(ob)
    return ob


sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 8.5
sun.data.angle = math.radians(1.2)
sun.data.color = tuple(hexc("fff0d8"))
SC.collection.objects.link(sun)
sdir = (POOL - V(0, OCULUS_Y, 0)).normalized()
sun.rotation_euler = Vector((0, 0, -1)).rotation_difference(G(sdir)).to_euler()
for i, b in enumerate(BRAZIERS):
    point("brazier%d" % i, b + UP * 0.35, "ff9a48", 650.0, 0.35)
for i, l in enumerate(LANTERNS):
    point("lantern%d" % i, l, "ffc070", 320.0, 0.3)
for k, a in enumerate(BOOTH_A):
    d = dirv(a)
    point("alcove%d" % k, d * (R + 1.8) + UP * 4.6, "ffb870", 480.0, 0.6)
    point("board%d" % k, d * (ALC_D - 1.6) + UP * 3.9, "ffd8a0", 60.0, 0.3)
point("portal", V(0, 2.4, 0), "7fd6ff", 420.0, 0.8)
for a in WIN_A:
    point("win_%d" % int(math.degrees(a)), dirv(a) * (R - 2.0) + UP * 12.5, "c8d8ff", 300.0, 1.5)

# the sky beyond the oculus, as a bright disc (bake only: the browser draws its own sky)
sky = MB("sky_disc", "bake_only")
sky.lathe(V(0, OCULUS_Y + 4.0, 0), [(0.0, 0.0), (14.0, 0.0)], 24, "sky_hole", sign=-1)
sky_ob = sky.finish()
sky_ob.visible_shadow = False   # the sun shines through it
MATS["sky_hole"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 2.2

# ---------------------------------------------------------------- collision (invisible)
log("collision")
cl = MB("collision", "collision")
cl.lathe(V(0, 0, 0), [(ALC_D + 1.0, 0.0), (7.4, 0.0)], 48, "plaster")
for (dr, dy) in DAIS:
    cl.lathe(V(0, 0, 0), [(dr, dy - 0.3), (dr, dy), (0.0, dy)], 48, "plaster", sign=1)
for i in range(NV):
    am = 2 * math.pi * (i + 0.5) / NV
    if math.cos(am) < -0.6:
        continue   # the sunk bottom stones: walked over
    rad = V(math.sin(am), math.cos(am), 0)
    tng = V(math.cos(am), -math.sin(am), 0)
    cl.obox(V(0, PORTAL_CY, PORTAL_Z) + rad * PORTAL_R, tng, rad, V(0, 0, 1), (0.7, PORTAL_T, 0.7), "plaster")
for sgn in (-1, 1):
    cl.box(V(sgn * (PORTAL_R + 0.05), DAIS[-1][1] + 0.35, PORTAL_Z), (1.0, 0.7, 1.0), "plaster")
for k, a in enumerate(BOOTH_A):
    d, t = dirv(a), tanv(a)
    # wall with a rectangular opening, alcove sides and back
    for sgn in (-1, 1):
        p0, p1 = on_drum(a, sgn * ALC_W, 0.0), on_drum(a, sgn * PANEL, 0.0)
        cl.quad(p0, p1, p1 + UP * WALL_TOP, p0 + UP * WALL_TOP, "plaster", hint=-d)
        f0 = on_drum(a, sgn * ALC_W, 0.0)
        b0 = d * ALC_D + t * (sgn * ALC_W)
        cl.quad(f0, b0, b0 + UP * 6.5, f0 + UP * 6.5, "plaster", hint=-t * sgn)
    cl.quad(on_drum(a, -ALC_W, 6.5), on_drum(a, ALC_W, 6.5), on_drum(a, ALC_W, WALL_TOP), on_drum(a, -ALC_W, WALL_TOP), "plaster", hint=-d)
    b0, b1 = d * ALC_D - t * ALC_W, d * ALC_D + t * ALC_W
    cl.quad(b0, b1, b1 + UP * 6.5, b0 + UP * 6.5, "plaster", hint=-d)
    # the counter
    cl.box(d * (R + 0.9) + UP * 0.5, (3.0, 1.0, 1.2), "plaster", yaw=a)
for k in range(8):
    a0 = BOOTH_A[k] + PANEL / R
    a1 = BOOTH_A[(k + 1) % 8] - PANEL / R + (2 * math.pi if k == 7 else 0.0)
    for j in range(4):
        t0 = a0 + (a1 - a0) * j / 4
        t1 = a0 + (a1 - a0) * (j + 1) / 4
        cl.quad(dirv(t0) * R, dirv(t1) * R, dirv(t1) * R + UP * WALL_TOP, dirv(t0) * R + UP * WALL_TOP, "plaster", hint=-dirv(t0))
for a in COL_A:
    cl.lathe(dirv(a) * COL_R, [(0.95, 0.0), (0.95, 13.0)], 8, "plaster")
for b in BRAZIERS:
    cl.lathe(b - UP * 1.32, [(0.72, 0.0), (0.72, 1.4)], 8, "plaster")
# gallery: floor, the underside, the balustrade (both faces), gaps at the stairs
cl.lathe(V(0, 0, 0), [(R, GAL_Y), (GAL_IN, GAL_Y)], 64, "plaster")
cl.lathe(V(0, 0, 0), [(GAL_IN, GAL_Y - 0.5), (R, GAL_Y - 0.5)], 64, "plaster")
NBc = 96
for j in range(NBc):
    t0, t1 = 2 * math.pi * j / NBc, 2 * math.pi * (j + 1) / NBc
    if in_gap((t0 + t1) / 2, math.radians(3.2)):
        continue
    d0, d1 = dirv(t0), dirv(t1)
    for rr, s in ((GAL_IN, -1), (GAL_IN + 0.3, 1)):
        cl.quad(d0 * rr + UP * GAL_Y, d1 * rr + UP * GAL_Y, d1 * rr + UP * (GAL_Y + 1.15), d0 * rr + UP * (GAL_Y + 1.15), "plaster", hint=d0 * s)
    cl.quad(d0 * GAL_IN + UP * (GAL_Y - 0.5), d1 * GAL_IN + UP * (GAL_Y - 0.5), d1 * GAL_IN + UP * GAL_Y, d0 * GAL_IN + UP * GAL_Y, "plaster", hint=-d0)
# stairs as ramps, with the landing
for (start, top, run, d) in STAIRS:
    w = STAIR_W / 2
    a0, a1 = start - d * w, start + d * w
    b0, b1 = top - d * w + UP * GAL_Y, top + d * w + UP * GAL_Y
    cl.quad(a0, a1, b1, b0, "plaster", hint=UP)
    lc = top + run * 0.9 + d * 0.9 + UP * GAL_Y
    cl.box(lc - UP * 0.25, (STAIR_W + 1.8, 0.5, 1.8), "plaster", yaw=math.atan2(run.x, run.z))
    # side walls of the flight so nobody walks under it
    for s in (-1, 1):
        e0, e1 = start + d * (s * w), top + d * (s * w)
        cl.quad(e0, e1, e1 + UP * GAL_Y, e0 + UP * 0.25, "plaster", hint=d * s)
    cl.quad(top - d * w, top + d * w, top + d * w + UP * GAL_Y, top - d * w + UP * GAL_Y, "plaster", hint=run)
col_ob = cl.finish()
col_ob.hide_render = True    # never lit, never casts: it only has to be walked on

# ---------------------------------------------------------------- positions for scene.json
info = {
    "braziers": [[round(b.x, 3), round(b.y, 3), round(b.z, 3)] for b in BRAZIERS],
    "lanterns": [[round(p.x, 3), round(p.y, 3), round(p.z, 3)] for p in LANTERNS],
    "booths": [{"guild": GUILDS[k][0], "angle": 45.0 * k, "npc": [round(v, 3) for v in (dirv(a) * (R + 2.3))], "front": [round(v, 3) for v in (dirv(a) * (R - 1.0))]} for k, a in enumerate(BOOTH_A)],
    "stairs": [{"bottom": [round(v, 3) for v in s[0]], "top": [round(v, 3) for v in (s[1] + UP * GAL_Y)]} for s in STAIRS],
    "gallery_y": GAL_Y, "gallery_mid_r": (GAL_IN + R) / 2,
    "oculus_y": OCULUS_Y, "pool": list(POOL),
    "sun_dir": [round(v, 4) for v in sdir],
    "windows": [45.0 * k + 22.5 for k in range(8)],
    "portal": {"position": [0.0, DAIS[-1][1], PORTAL_Z], "veil_center": [0.0, round(PORTAL_CY, 3), PORTAL_Z], "inner_radius": PORTAL_R - PORTAL_T / 2},
}
with open(os.path.join(WORK, "hall_info.json"), "w") as f:
    json.dump(info, f, indent=1)
log("info", json.dumps(info)[:400])


# ---------------------------------------------------------------- camera views (previews)
VIEWS = {
    "spawn": (V(0, 2.6, 3.8), V(0, 5.0, 30), 78),
    "back": (V(0, 2.6, -3.0), V(0, 8.0, -30), 78),
    "up": (V(0, 1.8, 10), V(0, 40, -2), 90),
    "gallery": (V(22.0, GAL_Y + 1.7, -20.0), V(-12, 4.0, 14), 75),
    "booth": (V(0, 1.7, 28), V(0, 2.5, 37), 70),
    "wide": (V(-18, 5.0, -18), V(14, 6.0, 16), 90),
    "dais": (V(-9, 3.0, 9), V(0, 0.9, 1), 70),
}


def render_views(prefix, samples, denoise_on):
    os.makedirs(PREV, exist_ok=True)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    SC.collection.objects.link(cam)
    SC.camera = cam
    SC.cycles.samples = samples
    SC.cycles.use_denoising = denoise_on
    SC.render.resolution_x, SC.render.resolution_y = 1280, 720
    SC.render.resolution_percentage = 100
    SC.render.image_settings.file_format = "PNG"
    for vn, (eye, look, fov) in VIEWS.items():
        cam.data.angle = math.radians(fov)
        cam.location = G(eye)
        cam.rotation_euler = (G(look) - G(eye)).to_track_quat("-Z", "Y").to_euler()
        SC.render.filepath = os.path.join(PREV, "%s_%s.png" % (prefix, vn))
        bpy.ops.render.render(write_still=True)
        log("render", prefix, vn)
    bpy.data.objects.remove(cam)


if "--render" in argv:
    # the real lighting, rendered (no bake): for tuning lights quickly
    SC.view_settings.view_transform = "Standard"
    render_views("real", 48, True)
    sys.exit(0)


# ---------------------------------------------------------------- join per atlas, lightmap UVs
def select_only(obs, active):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


ATLASES = {}
PIECES = {}
for ob in list(SC.objects):
    if ob.type == "MESH" and "atlas" in ob:
        ATLASES.setdefault(ob["atlas"], []).append(ob)
        key = ob.name.split(".")[0]
        PIECES[key] = PIECES.get(key, 0) + sum(len(p.vertices) - 2 for p in ob.data.polygons)
log("pieces", sorted(PIECES.items(), key=lambda kv: -kv[1])[:24])
JOINED = {}
ATLASES.pop("bake_only", None)
for name, obs in ATLASES.items():
    # joining fills a colour attribute with black where a mesh lacks it, and the kit's
    # materials multiply by it: give every mesh every attribute, white
    cnames = {}
    for o in obs:
        for ca in o.data.color_attributes:
            cnames[ca.name] = (ca.domain, ca.data_type)
    for o in obs:
        for cn, (dom, dt) in cnames.items():
            if cn not in o.data.color_attributes:
                ca = o.data.color_attributes.new(cn, dt, dom)
                ca.data.foreach_set("color", [1.0] * (4 * len(ca.data)))
    select_only(obs, obs[0])
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = "atlas_" + name
    JOINED[name] = ob
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    log("atlas", name, "tris", tris, "materials", len(ob.data.materials))

for name, ob in JOINED.items():
    if name == "collision":
        continue
    me = ob.data
    lm = me.uv_layers.new(name="lm")
    me.uv_layers.active = lm
    for l in me.uv_layers:
        if l.name == "uv0":
            l.active_render = True
    select_only([ob], ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=5.0 / RES[name], shape_method="CONCAVE")
    except TypeError:
        bpy.ops.uv.pack_islands(margin=5.0 / RES[name])
    bpy.ops.object.mode_set(mode="OBJECT")
    uvd = me.uv_layers["lm"].data
    rs = []
    for pl in me.polygons:
        us = [uvd[i].uv for i in pl.loop_indices]
        a2 = sum(abs((us[k].x - us[0].x) * (us[k + 1].y - us[0].y) - (us[k + 1].x - us[0].x) * (us[k].y - us[0].y)) / 2 for k in range(1, len(us) - 1))
        if pl.area > 1e-6:
            rs.append(a2 / pl.area)
    rs = np.array(rs)
    med = max(np.median(rs), 1e-12)
    log("unwrapped", name, "density p5 %.2f p50 %.3g p95 %.2f zero %d of %d" % (np.percentile(rs, 5) / med, med, np.percentile(rs, 95) / med, int((rs < med * 1e-3).sum()), len(rs)))


if "--uvcheck" in argv:
    sys.exit(0)


# ---------------------------------------------------------------- bake
def bake(ob, kind, res, samples, pass_filter=None):
    img = bpy.data.images.new("%s_%s" % (ob.name, kind), res, res, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    added = []
    for slot in ob.material_slots:
        m = slot.material
        if m is None or not m.use_nodes:
            continue
        nt = m.node_tree
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img
        nt.nodes.active = n
        added.append((nt, n))
    select_only([ob], ob)
    SC.cycles.samples = samples
    t = time.time()
    if kind == "ao":
        bpy.ops.object.bake(type="AO", margin=8, use_clear=True)
    elif kind == "emit":
        bpy.ops.object.bake(type="EMIT", margin=8, use_clear=True)
    else:
        bpy.ops.object.bake(type="DIFFUSE", pass_filter=pass_filter, margin=8, use_clear=True)
    for nt, n in added:
        nt.nodes.remove(n)
    log("baked", ob.name, kind, res, "%.1fs" % (time.time() - t))
    return img


def pixels(img):
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


dn_scene = bpy.data.scenes.new("denoise")
dn_scene.render.engine = "CYCLES"
dn_scene.cycles.samples = 1
dn_scene.view_settings.view_transform = "Standard"
dn_cam = bpy.data.objects.new("dn_cam", bpy.data.cameras.new("dn_cam"))
dn_scene.collection.objects.link(dn_cam)
dn_scene.camera = dn_cam
dn_scene.use_nodes = True


def denoise(img):
    nt = dn_scene.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    a = nt.nodes.new("CompositorNodeImage")
    a.image = img
    d = nt.nodes.new("CompositorNodeDenoise")
    c = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(a.outputs[0], d.inputs[0])
    nt.links.new(d.outputs[0], c.inputs[0])
    w, h = img.size
    dn_scene.render.resolution_x, dn_scene.render.resolution_y = w, h
    dn_scene.render.resolution_percentage = 100
    dn_scene.render.image_settings.file_format = "OPEN_EXR"
    dn_scene.render.image_settings.color_depth = "32"
    path = os.path.join(WORK, img.name + "_dn.exr")
    dn_scene.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=dn_scene.name)
    out = bpy.data.images.load(path)
    p = pixels(out)
    bpy.data.images.remove(out)
    return p


EXPOSURE = 1.0
FILL = np.array([0.16, 0.14, 0.11], np.float32)   # occlusion-shaded warm fill (the hall's soft ambience)
EMIT_K = 0.55


def shoulder(x, knee=0.72):
    """Linear below the knee, then a soft roll-off toward 1 (the sunlit pool, flames)."""
    y = np.where(x < knee, x, knee + (1 - knee) * (1 - np.exp(-(x - knee) / (1 - knee))))
    return np.clip(y, 0, 1)


def lin2srgb(x):
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(np.maximum(x, 0), 1 / 2.4) - 0.055)


FINAL = {}
for name, ob in JOINED.items():
    if name == "collision":
        continue
    res = RES[name]
    alb = pixels(bake(ob, "albedo", res, 8 if not QUICK else 2, {"COLOR"}))[..., :3]
    irr_img = bake(ob, "irr", res, SAMPLES, {"DIRECT", "INDIRECT"})
    raw = pixels(irr_img)[..., :3]
    irr = denoise(irr_img)[..., :3]
    log("irr", name, "raw max %.2f p99.9 %.2f  denoised max %.2f p99.9 %.2f" % (raw.max(), np.percentile(raw, 99.9), irr.max(), np.percentile(irr, 99.9)))
    ao = pixels(bake(ob, "ao", res, 64 if not QUICK else 8))[..., :1]
    emit = pixels(bake(ob, "emit", res, 1))[..., :3]
    lin = alb * (irr * EXPOSURE + FILL * ao) + emit * EMIT_K
    lum = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    log("light", name, "lum p10 %.3f p50 %.3f p90 %.3f p99 %.3f" % tuple(np.percentile(lum, [10, 50, 90, 99])))
    out = lin2srgb(shoulder(lin))
    h, w = out.shape[:2]
    img = bpy.data.images.new("hall_" + name, w, h, alpha=False)
    img.colorspace_settings.name = "sRGB"
    img.pixels.foreach_set(np.concatenate([out, np.ones((h, w, 1), np.float32)], axis=2).astype(np.float32).ravel())
    path = os.path.join(WORK, "hall_%s.jpg" % name)
    SC.render.image_settings.file_format = "JPEG"
    SC.render.image_settings.quality = 90
    SC.render.image_settings.color_mode = "RGB"
    img.save_render(path, scene=SC)
    bpy.data.images.remove(img)
    FINAL[name] = bpy.data.images.load(path)
    FINAL[name].colorspace_settings.name = "sRGB"


bpy.data.scenes.remove(dn_scene)


# ---------------------------------------------------------------- export
def unlit_material(name, img, double=False, alpha=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    if img is not None:
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = img
        nt.links.new(tx.outputs[0], b.inputs["Base Color"])
        if alpha == "texture":
            nt.links.new(tx.outputs[1], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = 1.0
    b.inputs["Metallic"].default_value = 0.0
    m.use_backface_culling = not double
    return m


def patch_unlit(path, blend_names=()):
    """Marks every material of a .glb unlit (KHR_materials_unlit)."""
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, total = struct.unpack("<III", data[:12])
    jlen, jtype = struct.unpack("<II", data[12:20])
    js = json.loads(data[20:20 + jlen].decode("utf-8"))
    rest = data[20 + jlen:]
    for m in js.get("materials", []):
        m.setdefault("extensions", {})["KHR_materials_unlit"] = {}
        pbr = m.setdefault("pbrMetallicRoughness", {})
        pbr["metallicFactor"] = 0.0
        pbr["roughnessFactor"] = 1.0
        m.pop("normalTexture", None)
        m.pop("occlusionTexture", None)
    used = js.setdefault("extensionsUsed", [])
    if "KHR_materials_unlit" not in used:
        used.append("KHR_materials_unlit")
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    out = struct.pack("<II", len(jb), 0x4E4F534A) + jb + rest
    with open(path, "wb") as f:
        f.write(struct.pack("<III", magic, ver, 12 + len(out)) + out)


def export(obs, path, animations=False, colors=False):
    select_only(obs, obs[0])
    kw = dict(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
              export_texcoords=True, export_normals=False, export_materials="EXPORT", export_image_format="AUTO",
              export_animations=animations, export_extras=False, export_cameras=False, export_lights=False)
    try:
        bpy.ops.export_scene.gltf(export_vertex_color="ACTIVE" if colors else "NONE", **kw)
    except TypeError:
        bpy.ops.export_scene.gltf(export_colors=colors, **kw)
    log("exported", os.path.basename(path), os.path.getsize(path), "bytes")


# the hall: each atlas keeps only its lightmap UVs and one unlit material
export_obs = []
for name, ob in JOINED.items():
    if name == "collision":
        continue
    me = ob.data
    # (fetch each layer afresh: removing one invalidates Python references to the others)
    for nm in [l.name for l in me.uv_layers if l.name != "lm"]:
        me.uv_layers.remove(me.uv_layers[nm])
    me.materials.clear()
    me.materials.append(unlit_material("hall_" + name, FINAL[name], double=(name == "props")))
    for p in me.polygons:
        p.material_index = 0
    ob.name = "hall_" + name
    export_obs.append(ob)

if PREVIEW:
    os.makedirs(PREV, exist_ok=True)
    # emission-only view of the baked result
    for ob in export_obs:
        m = ob.data.materials[0]
        nt = m.node_tree
        b = nt.nodes["Principled BSDF"]
        tx = next(n for n in nt.nodes if n.type == "TEX_IMAGE")
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(tx.outputs[0], em.inputs[0])
        out = nt.nodes["Material Output"]
        m["_prev_link"] = True
        nt.links.new(em.outputs[0], out.inputs[0])
    for o in [o for o in SC.objects if o.type == "LIGHT"]:
        o.hide_render = True
    col_ob.hide_render = True
    bg.inputs[1].default_value = 0.0
    SC.cycles.max_bounces = 0
    render_views("prev", 8, False)
    for ob in export_obs:
        m = ob.data.materials[0]
        nt = m.node_tree
        nt.links.new(nt.nodes["Principled BSDF"].outputs[0], nt.nodes["Material Output"].inputs[0])

p = os.path.join(ASSETS, "hall.glb")
export(export_obs, p)
patch_unlit(p)

# collision: one invisible material (alpha 0, masked away)
me = col_ob.data
while len(me.uv_layers):
    me.uv_layers.remove(me.uv_layers[0])
me.materials.clear()
cm = unlit_material("collision_invisible", None)
b = cm.node_tree.nodes["Principled BSDF"]
b.inputs["Alpha"].default_value = 0.0
try:
    cm.blend_method = "CLIP"
except Exception:
    pass
try:
    cm.surface_render_method = "DITHERED"
except Exception:
    pass
me.materials.append(cm)
col_ob.name = "hall_collision"
p = os.path.join(ASSETS, "hall_collision.glb")
export([col_ob], p)
patch_unlit(p)
# make sure the collision material is masked out in every reader
with open(p, "rb") as f:
    data = f.read()
jlen = struct.unpack("<I", data[12:16])[0]
js = json.loads(data[20:20 + jlen])
for m in js.get("materials", []):
    m["alphaMode"] = "MASK"
    m["alphaCutoff"] = 0.5
    m.setdefault("pbrMetallicRoughness", {})["baseColorFactor"] = [1, 1, 1, 0]
jb = json.dumps(js, separators=(",", ":")).encode()
jb += b" " * ((4 - len(jb) % 4) % 4)
rest = data[20 + jlen:]
out = struct.pack("<II", len(jb), 0x4E4F534A) + jb + rest
with open(p, "wb") as f:
    f.write(struct.pack("<III", 0x46546C67, 2, 12 + len(out)) + out)


# ---------------------------------------------------------------- dynamic pieces: flame, shaft
def vcol_mesh(name, faces_cols):
    """faces_cols: [(pts game, [colours])] -> object with a colour attribute."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("uv0")
    for pts, cols in faces_cols:
        vs = [bm.verts.new(G(p)) for p in pts]
        f = bm.faces.new(vs)
        for lp, c in zip(f.loops, cols):
            # the colour becomes a place on a gradient texture (vertex colours do not
            # survive every glTF reader: two COLOR_n sets came out, the first white)
            lp[uvl].uv = (0.5, 1.0 - (c[1] - 0.06) / 0.66)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    SC.collection.objects.link(ob)
    return ob


def flame_faces():
    out = []
    tongues = [(V(0, 0, 0), 0.34, 0.95), (V(0.14, 0, 0.05), 0.2, 0.62), (V(-0.12, 0, -0.08), 0.22, 0.7), (V(0.02, 0, -0.16), 0.18, 0.55)]
    for c0, rad, h in tongues:
        prof = [(rad * 0.7, 0.0), (rad, h * 0.18), (rad * 0.8, h * 0.45), (rad * 0.35, h * 0.78), (0.0, h)]
        cols = [(1.0, 0.72, 0.22, 1), (1.0, 0.5, 0.08, 1), (0.95, 0.3, 0.03, 1), (0.8, 0.16, 0.02, 1), (0.5, 0.06, 0.01, 1)]
        n = 8
        for i in range(len(prof) - 1):
            for j in range(n):
                t0, t1 = 2 * math.pi * j / n, 2 * math.pi * (j + 1) / n
                (r0, y0), (r1, y1) = prof[i], prof[i + 1]
                pa = c0 + dirv(t0) * r0 + UP * y0
                pb = c0 + dirv(t1) * r0 + UP * y0
                pc = c0 + dirv(t1) * r1 + UP * y1
                pd = c0 + dirv(t0) * r1 + UP * y1
                if r1 < 1e-6:
                    out.append(([pa, pb, pc], [cols[i], cols[i], cols[i + 1]]))
                else:
                    out.append(([pa, pb, pc, pd], [cols[i], cols[i], cols[i + 1], cols[i + 1]]))
    return out


fl_ob = vcol_mesh("flame", flame_faces())
grad = np.zeros((64, 4, 3), np.float32)
stops = [(1.0, 0.72, 0.22), (1.0, 0.5, 0.08), (0.95, 0.3, 0.03), (0.8, 0.16, 0.02), (0.5, 0.06, 0.01)]
for i in range(64):
    f = i / 63 * 4
    k = min(int(f), 3)
    t = f - k
    grad[i, :, :] = np.array(stops[k]) * (1 - t) + np.array(stops[k + 1]) * t
fl_ob.data.materials.append(unlit_material("flame", np_image("flame_grad", np.clip(grad, 0, 1) ** (1 / 2.2)), double=True))
fl_ob.animation_data_create()
act = bpy.data.actions.new("flicker")
fl_ob.animation_data.action = act
keys = [(1, (1.0, 1.0, 1.0), 0.0), (5, (1.08, 1.06, 1.18), 0.08), (9, (0.94, 0.95, 0.9), -0.05), (13, (1.05, 1.1, 1.1), 0.1),
        (17, (0.97, 0.94, 0.95), -0.08), (21, (1.06, 1.03, 1.14), 0.04), (25, (1.0, 1.0, 1.0), 0.0)]
for fr, s, rz in keys:
    fl_ob.scale = s
    fl_ob.rotation_euler = (0, 0, rz)
    fl_ob.keyframe_insert("scale", frame=fr)
    fl_ob.keyframe_insert("rotation_euler", frame=fr)
SC.frame_start, SC.frame_end = 1, 25
SC.render.fps = 24
p = os.path.join(ASSETS, "flame.glb")
export([fl_ob], p, animations=True)
patch_unlit(p)

# the shaft: two nested open cones from the oculus to the pool, faint and warm
sh_img = np.zeros((128, 4, 4), np.float32)
vv = (np.arange(128) + 0.5) / 128
alpha = 0.055 * smooth(0.0, 0.25, vv) * (1.0 - 0.5 * vv)
sh_img[..., 0], sh_img[..., 1], sh_img[..., 2] = 1.0, 0.94, 0.78
sh_img[..., 3] = alpha[:, None]
img_sh = np_image("shaft_grad", sh_img)
bm = bmesh.new()
uvl = bm.loops.layers.uv.new("uv0")
top_c = V(0, OCULUS_Y + 0.4, 0)
for rad_t, rad_b in ((3.9, 4.1), (3.2, 3.4), (2.3, 2.5)):
    n = 24
    for j in range(n):
        t0, t1 = 2 * math.pi * j / n, 2 * math.pi * (j + 1) / n
        pts = [POOL + dirv(t0) * rad_b + UP * 0.02, POOL + dirv(t1) * rad_b + UP * 0.02, top_c + dirv(t1) * rad_t, top_c + dirv(t0) * rad_t]
        f = bm.faces.new([bm.verts.new(G(p)) for p in pts])
        for lp, uv in zip(f.loops, [(0.2, 0.0), (0.8, 0.0), (0.8, 1.0), (0.2, 1.0)]):
            lp[uvl].uv = uv
me = bpy.data.meshes.new("shaft")
bm.to_mesh(me)
bm.free()
sh_ob = bpy.data.objects.new("shaft", me)
SC.collection.objects.link(sh_ob)
sm = unlit_material("shaft", img_sh, double=True, alpha="texture")
try:
    sm.blend_method = "BLEND"
except Exception:
    pass
try:
    sm.surface_render_method = "BLENDED"
except Exception:
    pass
me.materials.append(sm)
p = os.path.join(ASSETS, "shaft.glb")
export([sh_ob], p)
patch_unlit(p)
with open(p, "rb") as f:
    data = f.read()
jlen = struct.unpack("<I", data[12:16])[0]
js = json.loads(data[20:20 + jlen])
for m in js.get("materials", []):
    m["alphaMode"] = "BLEND"
    m["doubleSided"] = True
jb = json.dumps(js, separators=(",", ":")).encode()
jb += b" " * ((4 - len(jb) % 4) % 4)
rest = data[20 + jlen:]
out = struct.pack("<II", len(jb), 0x4E4F534A) + jb + rest
with open(p, "wb") as f:
    f.write(struct.pack("<III", 0x46546C67, 2, 12 + len(out)) + out)

# the portal veil: a spiral of light turning in the ring (animation "swirl"), over a still glow
def spiral_image(n=512):
    xs = (np.arange(n) + 0.5) / n * 2 - 1
    x, y = np.meshgrid(xs, xs)
    r = np.sqrt(x * x + y * y)
    a = np.arctan2(y, x)
    tw = a + 3.2 * np.log(r + 0.08)
    arms = (0.5 + 0.5 * np.sin(tw * 5.0)) ** 3
    rng = np.random.default_rng(3)
    noise = 0.5 + 0.5 * np.sin(tw * 13.0 + np.sin(r * 17.0) * 2.0) * np.sin(r * 23.0 + a * 3.0)
    body = arms * (0.5 + 0.7 * noise)
    rim = hexc("7fd6ff")
    mid = hexc("9d6bff")
    heart = hexc("ffd27a")
    c = heart[None, None] * (1 - smooth(0.0, 0.55, r))[..., None] + mid[None, None] * smooth(0.0, 0.55, r)[..., None]
    c = c * (1 - smooth(0.45, 0.95, r))[..., None] + rim[None, None] * smooth(0.45, 0.95, r)[..., None]
    alpha = np.clip(body * 0.85 + 0.12 + np.exp(-r * r * 9.0) * 0.8, 0, 1) * (1 - smooth(0.9, 1.0, r))
    out = np.concatenate([np.clip(c * (0.6 + 0.6 * body[..., None]), 0, 1), alpha[..., None]], axis=2)
    return out.astype(np.float32)


def glow_image(n=128):
    xs = (np.arange(n) + 0.5) / n * 2 - 1
    x, y = np.meshgrid(xs, xs)
    r = np.sqrt(x * x + y * y)
    c = np.zeros((n, n, 4), np.float32)
    c[..., :3] = hexc("8fd8ff")
    c[..., 3] = np.clip(0.55 * (1 - smooth(0.2, 1.0, r)) + 0.35 * np.exp(-((r - 0.9) / 0.06) ** 2), 0, 1) * (r < 1)
    return c


def disc_object(name, radius, img, z):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("uv0")
    n = 32
    ctr = bm.verts.new(G(V(0, 0, z)))
    ring = [bm.verts.new(G(V(math.cos(2 * math.pi * i / n) * radius, math.sin(2 * math.pi * i / n) * radius, z))) for i in range(n)]
    for i in range(n):
        f = bm.faces.new([ctr, ring[i], ring[(i + 1) % n]])
        for lp, v in zip(f.loops, [ctr, ring[i], ring[(i + 1) % n]]):
            gx, gz = v.co.x, v.co.z
            lp[uvl].uv = (0.5 + 0.5 * gx / radius, 0.5 + 0.5 * gz / radius)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    SC.collection.objects.link(ob)
    m = unlit_material(name, np_image(name + "_img", img), double=True, alpha="texture")
    try:
        m.blend_method = "BLEND"
    except Exception:
        pass
    me.materials.append(m)
    return ob


veil_r = PORTAL_R - PORTAL_T / 2 - 0.02
glow_ob = disc_object("veil_glow", veil_r, glow_image(), -0.02)
spin_ob = disc_object("veil_spiral", veil_r, spiral_image(256 if QUICK else 512), 0.02)
spin_ob.animation_data_create()
spin_ob.animation_data.action = bpy.data.actions.new("swirl")
spin_ob.rotation_mode = "XYZ"
for fr, ang in ((1, 0.0), (49, -math.pi), (97, -2 * math.pi)):
    spin_ob.rotation_euler = (0, ang, 0) if False else (0.0, 0.0, 0.0)
    # the disc faces game Z = Blender -Y: turn about Blender Y
    spin_ob.rotation_euler = (0.0, ang, 0.0)
    spin_ob.keyframe_insert("rotation_euler", frame=fr)
if spin_ob.animation_data.action.fcurves if hasattr(spin_ob.animation_data.action, "fcurves") else False:
    for fc in spin_ob.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
SC.frame_start, SC.frame_end = 1, 97
p = os.path.join(ASSETS, "veil.glb")
export([glow_ob, spin_ob], p, animations=True)
patch_unlit(p)
with open(p, "rb") as f:
    data = f.read()
jlen = struct.unpack("<I", data[12:16])[0]
js = json.loads(data[20:20 + jlen])
for m in js.get("materials", []):
    m["alphaMode"] = "BLEND"
    m["doubleSided"] = True
jb = json.dumps(js, separators=(",", ":")).encode()
jb += b" " * ((4 - len(jb) % 4) % 4)
rest = data[20 + jlen:]
out = struct.pack("<II", len(jb), 0x4E4F534A) + jb + rest
with open(p, "wb") as f:
    f.write(struct.pack("<III", 0x46546C67, 2, 12 + len(out)) + out)

log("done")
