#!/usr/bin/env python3
"""Style lint: check a world folder or .glb models against a style profile (style.json).

    iamar-world lint <world folder | model.glb ...> [--style PROFILE] [--class CLASS] [--json]
    python3 kit/lint/style_lint.py   (same arguments; iamar-world lint runs this)

PROFILE is a profile id under kit/style/<id>/ (default: the world's own style.json, else
"iamar") or a path to a style.json; "extends" is resolved like kit/style/check_style.py.
Every tolerance comes from the profile (lint, dimensions, budgets, palette, regions), so the
same lint judges the iamar look and any custom look (vision principle 4).

Checks, per model (LOD0 unless a rule says otherwise):
  budget      triangles at LOD0 <= profile budgets.triangles[class]; every LOD reported
  scale       a character model stands within 12 % of dimensions.person_m; a node named
              *door* (not a frame or arch) is dimensions.door_m (or a grand_door_m) tall
  roof        a node named *roof*: rise / half its short span within
              dimensions.roof_pitch_rise_per_run (15 % slack), or rise / model height within
              dimensions.roof_height_fraction when the profile gives no pitches
  arch        a node named *arch*: rise / half span within dimensions.arch_rise_half_span
  palette     each lit material's colour (texture mean x base colour factor x placement tint) is within
              lint.palette_max_delta_e of a profile colour (palette, regions, material tints,
              trim looks, each also weathered by every weathering role); drifted materials
              may cover at most lint.palette_max_off_share of the model's triangles
  colour      no material darker than lint.min_albedo_value, more saturated than
              lint.max_saturation, or within lint.forbidden_delta_e of a forbidden colour
              (pure black, missing-texture pink)
  texture     no texture that is mostly black or shows missing-texture pink; every
              texture reference resolves
and per world (scene.json):
  neighbours  two placements of the same building or landmark model at the same scale closer
              than lint.neighbour_m: the profile's neighbour rule (no two neighbours alike)
  primitives  primitive colours follow the colour rules above
  frame       summed placed triangles <= budgets.frame.visible_triangles_max

Model class: the object's "x-class" in scene.json, else --class, else the kit catalogue's
category for a catalogue copy (by sha256), else the file name
(house, inn ... -> building; elm, hedge ... -> tree; cathedral, castle ... -> landmark; horse, wolf -> creature;
person, npc -> character; statue -> hero_statue ...), else by size (largest side <= 3 m:
prop, else building). Exit 1 on any ERROR. Texture checks need Pillow (and numpy for
speed); without Pillow they are skipped with a WARN.
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import sys

LINT_DIR = Path(__file__).resolve().parent
KIT = LINT_DIR.parent
sys.path.insert(0, str(KIT / "style"))
import check_style  # noqa: E402  (profile loading and "extends" merge)

DEFAULT_LINT = {
    "palette_max_delta_e": 18.0,
    "palette_max_off_share": 0.2,
    "min_albedo_value": 0.08,
    "max_saturation": 0.8,
    "forbidden_colours": ["#000000", "#ff00ff"],
    "forbidden_delta_e": 12.0,
    "neighbour_m": 12.0,
    "pink_texture_share": 0.01,
    "person_tolerance": 0.12,
    "pitch_slack": 0.15,
    "vertex_bad_share": 0.1,
    "min_efficiency": 60.0,
    "max_metallic": 0.8,
}

# Model class from words in the file name; the first class in this list with a matching word wins
# ("boat_fish" is a boat, "dock_gull" a gull, "gate_guard" a guard), except that a person or
# animal named after a place (the head noun last) is that person or animal: "tavern_merchant" is
# a character, while "guard_house" stays a building and "fish_hall" a hall. Only a model the size
# of a person or animal (LIVING_MAX_M) is read that way: a 12 m "hall_of_heroes" or
# "tavern_of_the_fox" is named after its people or sign and stays a hall or a tavern.
CLASS_WORDS = [
    ("hero_statue", r"statue|bust"),
    ("hero_creature", r"dragon|griffin|gryphon|wyvern"),
    ("hair", r"hair|wig|braid"),
    ("face_head", r"head|face"),
    ("landmark", r"cathedral|castle|keep|palace|tower|temple|church|landmark|citadel|fortress|lighthouse|"
                 r"gatehouse|arena|hall|library|guildhall"),
    ("building", r"house|home|inn|tavern|shop|store|cottage|barn|smithy|blacksmith|alchemist|stable|chapel|"
                 r"building|bakery|mill|warehouse|workshop|hut|office"),
    # not buildings: no roof, walls or door to audit (iamar-world audit runs roof/edge/door on
    # building, landmark and interior only)
    ("vehicle", r"boat|ship|rowboat|sailboat|barge|raft|canoe|cart|wagon|carriage|sled|sleigh"),
    ("character", r"person|people|npc|villager|character|citizen|guard|knight|merchant|man|woman|child|hero"),
    ("creature", r"horse|pony|wolf|deer|stag|boar|sheep|goat|cow|pig|dog|cat|fox|rabbit|bird|crow|gull|duck|fish|"
                 r"bear|creature|animal|chicken|hen|owl|bat|insect|butterfly"),
    # trees and plants: no roof, walls or door either (gaps G11: an elm was audited as a building)
    ("tree", r"tree|oak|elm|pine|birch|beech|willow|fir|spruce|maple|cypress|palm|cedar|yew|bush|shrub|hedge|"
             r"plant|flower|fern|grass|reed|crop|sapling|vine|ivy|cactus|foliage"),
    ("structure", r"pier|dock|jetty|wharf|quay|bridge|boardwalk|mast|flagpole|pole|frame|scaffold|fence|"
                  r"railing|rail|wall|ground|terrain|platform|stair|stairs|steps|well|fountain|gate|arch|crane"),
    # furniture and small things: only read as the head noun of a small model ("hall_bench" is a
    # bench), never on their own over PROP_MAX_M (a 12 m "table_rock" stays sized)
    ("prop", r"bench|chair|stool|table|desk|bed|shelf|shelves|bookcase|cabinet|chest|crate|barrel|box|"
             r"basket|sack|bucket|lamp|lantern|candle|pot|jar|bottle|cup|bowl|plate|sign|signpost|rug"),
]
PLACE, LIVING = ("landmark", "building"), ("character", "creature")
LIVING_MAX_M = 4.0
PROP_MAX_M = 3.0

# A model copied from the kit's catalogue (kit/catalog/catalog.json, matched by the file's sha256)
# takes its class from the catalogue category, not from words in its file name: hall_bench.glb is
# furniture, not a hall (gaps G8). None: no class of its own (the name and size decide).
CATALOG = KIT / "catalog" / "catalog.json"
CATEGORY_CLASS = {
    "building": "building", "landmark": "landmark",
    "tree": "tree", "flower": "tree", "ground-flora": "tree", "crop": "tree",
    "prop": "prop", "furniture": "prop", "tool": "prop", "signage": "prop", "lamp": "prop",
    "building-part": "structure", "fence": "structure", "gate": "structure", "bridge": "structure",
    "road": "structure", "terrain": "structure", "rock": "structure",
    "vehicle": "vehicle", "statue": "hero_statue", "mythical": "hero_creature", "character": "character",
    "hair": "hair", "horse": "creature", "bird": "creature", "fish": "creature", "insect": "creature",
    "animal-small": "creature", "wildlife": "creature", "livestock": "creature",
}
_CATALOGUE: dict | None = None

SMALL_IS_PROP = ("vehicle", "structure")

LOD_RE = re.compile(r"(?i)(?:^|[_.\- ])lod[_\- ]?(\d+)$")


# ------------------------------------------------------------------ colour

def hex_rgb(h: str) -> tuple[float, float, float]:
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


def rgb_hex(c) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * 255))) for v in c[:3])


def srgb_to_linear(v: float) -> float:
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def linear_to_srgb(v: float) -> float:
    v = max(0.0, min(1.0, v))
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def lab(c) -> tuple[float, float, float]:
    r, g, b = (srgb_to_linear(v) for v in c[:3])
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a, b, kl: float = 1.0) -> float:
    """CIE76; kl=2 halves the weight of lightness (baked light changes brightness, not hue)."""
    la, lb = lab(a), lab(b)
    return math.sqrt(((la[0] - lb[0]) / kl) ** 2 + (la[1] - lb[1]) ** 2 + (la[2] - lb[2]) ** 2)


def profile_colours(prof: dict) -> dict[str, tuple]:
    """name -> sRGB colour for every colour the profile names, plus weathered variants."""
    out: dict[str, tuple] = {}

    def add(name, h):
        if isinstance(h, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", h):
            out[name] = hex_rgb(h)

    for n, s in (prof.get("palette") or {}).items():
        if isinstance(s, dict) and not s.get("glow"):  # glows are lights, not surface colours
            add("palette.%s" % n, s.get("hex"))
    for rn, r in (prof.get("regions") or {}).items():
        if not isinstance(r, dict):
            continue
        for k, v in r.items():
            if isinstance(v, list):
                for i, h in enumerate(v):
                    add("regions.%s.%s[%d]" % (rn, k, i), h)
            else:
                add("regions.%s.%s" % (rn, k), v)
    mats = prof.get("materials") or {}
    for n, m in (mats.get("layers") or {}).items():
        add("materials.%s" % n, m.get("tint") if isinstance(m, dict) else None)
    for n, h in ((mats.get("trim_sheet") or {}).get("looks") or {}).items():
        add("trim.%s" % n, h)
    roles = ((prof.get("weathering") or {}).get("roles") or {})
    base = dict(out)
    for role, w in roles.items():
        for n, c in base.items():
            h, s, v = colorsys.rgb_to_hsv(*c)
            out["%s~%s" % (n, role)] = colorsys.hsv_to_rgb(h, min(1.0, s * w.get("saturation_scale", 1.0)),
                                                         min(1.0, v * w.get("value_scale", 1.0)))
    return out


def nearest(c, colours: dict) -> tuple[str, float]:
    best = ("", float("inf"))
    for n, p in colours.items():
        d = delta_e(c, p, kl=2.0)
        if d < best[1]:
            best = (n, d)
    return best


class Palette:
    """A profile's colours and colour rules, with judgements cached per quantised colour."""

    def __init__(self, prof: dict):
        self.lint = dict(DEFAULT_LINT, **(prof.get("lint") or {}))
        self.colours = profile_colours(prof)
        self.forbidden = [hex_rgb(h) for h in self.lint["forbidden_colours"]]
        # swatches marked glow (lamps, embers: emissive in the world) or allow_dark (door
        # openings, chimney mouths) are deliberate: exempt from the darkness and saturation rules
        self.exempt = [hex_rgb(s["hex"]) for s in (prof.get("palette") or {}).values()
                       if isinstance(s, dict) and (s.get("glow") or s.get("allow_dark")) and "hex" in s]
        self._cache: dict[tuple, list] = {}

    def nearest(self, c):
        return nearest(c, self.colours) if self.colours else ("", 0.0)

    def judge(self, c) -> list[str]:
        key = tuple(round(v * 63) for v in c[:3])
        if key in self._cache:
            return self._cache[key]
        out = []
        if any(delta_e(c, e) < 4.0 for e in self.exempt):
            self._cache[key] = out
            return out
        if any(delta_e(c, f) < self.lint["forbidden_delta_e"] for f in self.forbidden):
            out.append("forbidden")
        h, s, v = colorsys.rgb_to_hsv(*c[:3])
        if v < self.lint["min_albedo_value"]:
            out.append("dark")
        if s > self.lint["max_saturation"] and v > 0.5:  # bright and saturated (neon); dark browns are not
            out.append("saturated")
        if self.colours and self.nearest(c)[1] > self.lint["palette_max_delta_e"]:
            out.append("off")
        self._cache[key] = out
        return out


# ------------------------------------------------------------------ glb

COMPONENTS = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
TYPE_N = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class Glb:
    def __init__(self, path: Path):
        self.path = path
        data = path.read_bytes()
        if len(data) < 20 or data[:4] != b"glTF":
            raise ValueError("not a binary glTF (.glb)")
        _, _, total = struct.unpack_from("<4sII", data, 0)
        off, self.json, self.bin = 12, None, b""
        while off + 8 <= min(total, len(data)):
            ln, kind = struct.unpack_from("<II", data, off)
            chunk = data[off + 8: off + 8 + ln]
            if kind == 0x4E4F534A:
                self.json = json.loads(chunk.decode("utf-8"))
            elif kind == 0x004E4942:
                self.bin = chunk
            off += 8 + ln
        if self.json is None:
            raise ValueError("no JSON chunk")
        self.g = self.json

    def view_bytes(self, i: int) -> bytes:
        v = self.g["bufferViews"][i]
        o = v.get("byteOffset", 0)
        return self.bin[o:o + v["byteLength"]]

    def accessor_values(self, i: int, limit: int | None = None) -> list[tuple]:
        a = self.g["accessors"][i]
        if "bufferView" not in a:
            return []
        fmt, size = COMPONENTS[a["componentType"]]
        n = TYPE_N[a["type"]]
        v = self.g["bufferViews"][a["bufferView"]]
        stride = v.get("byteStride") or size * n
        base = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        count = a["count"] if limit is None else min(a["count"], limit)
        step = max(1, a["count"] // count) if count else 1
        out = []
        for k in range(0, a["count"], step):
            vals = struct.unpack_from("<%d%s" % (n, fmt), self.bin, base + k * stride)
            if a.get("normalized"):
                mx = float((1 << (8 * size - (1 if fmt.islower() else 0))) - 1)
                vals = tuple(max(-1.0, x / mx) for x in vals)
            out.append(vals)
            if len(out) >= count:
                break
        return out

    def prim_triangles(self, p: dict) -> int:
        mode = p.get("mode", 4)
        n = (self.g["accessors"][p["indices"]]["count"] if "indices" in p
             else self.g["accessors"][p["attributes"]["POSITION"]]["count"])
        if mode == 4:
            return n // 3
        if mode in (5, 6):
            return max(0, n - 2)
        return 0

    def image_bytes(self, i: int) -> bytes | None:
        im = self.g.get("images", [])[i]
        if "bufferView" in im:
            return self.view_bytes(im["bufferView"])
        return None

    def instances(self):
        """(node index, node, world matrix) for every node with a mesh in the default scene."""
        nodes = self.g.get("nodes", [])
        scenes = self.g.get("scenes") or [{"nodes": list(range(len(nodes)))}]
        roots = scenes[self.g.get("scene", 0)].get("nodes", [])
        out, stack = [], [(r, IDENT) for r in roots]
        while stack:
            i, parent = stack.pop()
            n = nodes[i]
            m = mat_mul(parent, node_matrix(n))
            if "mesh" in n:
                out.append((i, n, m))
            stack.extend((c, m) for c in n.get("children", []))
        return out

    def part_roots(self) -> list[tuple[int, str, str]]:
        """(node index, name, class) for every root node of the default scene whose extras carry
        an "x-class": a file holding several models (`style-gen street`: one house per root node),
        each judged on its own. Empty for an ordinary model."""
        nodes = self.g.get("nodes", [])
        scenes = self.g.get("scenes") or [{"nodes": list(range(len(nodes)))}]
        out = []
        for r in scenes[self.g.get("scene", 0)].get("nodes", []):
            cls = (nodes[r].get("extras") or {}).get("x-class") if r < len(nodes) else None
            if isinstance(cls, str) and cls:
                out.append((r, nodes[r].get("name") or "node%d" % r, cls))
        return out

    def root_of(self) -> dict:
        """node index -> the root node of the default scene it hangs from."""
        nodes = self.g.get("nodes", [])
        scenes = self.g.get("scenes") or [{"nodes": list(range(len(nodes)))}]
        out, stack = {}, [(r, r) for r in scenes[self.g.get("scene", 0)].get("nodes", [])]
        while stack:
            i, r = stack.pop()
            out[i] = r
            stack.extend((c, r) for c in nodes[i].get("children", []))
        return out

    def node_names(self):
        """node index -> its name path from the root (for *door*, *roof*, LOD tests)."""
        nodes = self.g.get("nodes", [])
        parent = {}
        for i, n in enumerate(nodes):
            for c in n.get("children", []):
                parent[c] = i
        names = {}
        for i, n in enumerate(nodes):
            chain, j = [], i
            while j is not None:
                chain.append(nodes[j].get("name", "") or "")
                mesh = nodes[j].get("mesh")
                if mesh is not None:
                    chain.append(self.g["meshes"][mesh].get("name", "") or "")
                j = parent.get(j)
            names[i] = chain
        return names


IDENT = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]


def mat_mul(a, b):
    """column-major 4x4."""
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def node_matrix(n: dict):
    if "matrix" in n:
        return list(map(float, n["matrix"]))
    tx, ty, tz = n.get("translation", [0, 0, 0])
    x, y, z, w = n.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = n.get("scale", [1, 1, 1])
    r = [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w),
         2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w),
         2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)]
    return [r[0] * sx, r[1] * sx, r[2] * sx, 0, r[3] * sy, r[4] * sy, r[5] * sy, 0,
            r[6] * sz, r[7] * sz, r[8] * sz, 0, tx, ty, tz, 1]


def transform_box(m, lo, hi):
    pts = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    out = [[m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12],
            m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
            m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]] for p in pts]
    return [min(p[i] for p in out) for i in range(3)], [max(p[i] for p in out) for i in range(3)]


def arch_ring(g: "Glb", mesh: dict, m) -> tuple[float, float] | None:
    """(rise, span) of an arch's opening, measured on its intrados (the soffit faces that look down
    and in towards the opening's middle), so a wall panel, door or jambs in the same node do not
    count (gaps G7: style-gen arch's sample wall made the node 2.18). None when the node has no
    such faces (a block or a flat lintel): the caller falls back to the node's bounding box."""
    pts = []
    for p in mesh.get("primitives", []):
        if p.get("mode", 4) != 4 or "POSITION" not in p.get("attributes", {}):
            continue
        pos = [(m[0] * v[0] + m[4] * v[1] + m[8] * v[2] + m[12], m[1] * v[0] + m[5] * v[1] + m[9] * v[2] + m[13],
                m[2] * v[0] + m[6] * v[1] + m[10] * v[2] + m[14]) for v in g.accessor_values(p["attributes"]["POSITION"])]
        idx = [i for t in g.accessor_values(p["indices"]) for i in t] if "indices" in p else list(range(len(pos)))
        for k in range(0, len(idx) - 2, 3):
            a, b, c = pos[idx[k]], pos[idx[k + 1]], pos[idx[k + 2]]
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            ln = math.sqrt(sum(x * x for x in n))
            if ln < 1e-12:
                continue
            if -0.98 < n[1] / ln < -0.05:   # looks down, but is not a flat underside
                pts.extend((a, b, c))
    if len(pts) < 6:
        return None
    lo = [min(q[i] for q in pts) for i in range(3)]
    hi = [max(q[i] for q in pts) for i in range(3)]
    ax = 0 if hi[0] - lo[0] >= hi[2] - lo[2] else 2
    half = (hi[ax] - lo[ax]) / 2.0
    if half <= 0:
        return None
    mid = (hi[ax] + lo[ax]) / 2.0
    # the crown vertex sits a little off the middle on an odd ring (9 voussoirs): on an elliptic or
    # round arch y = spring + rise * sqrt(1 - (x / half)^2), so read the rise back through that
    top = max(pts, key=lambda q: q[1])
    d = min(abs(top[ax] - mid) / half, 0.5)
    rise = (top[1] - lo[1]) / math.sqrt(1.0 - d * d)
    return rise, 2.0 * half


def union(a, b):
    if a is None:
        return b
    return [min(a[0][i], b[0][i]) for i in range(3)], [max(a[1][i], b[1][i]) for i in range(3)]


def size_of(box):
    return [box[1][i] - box[0][i] for i in range(3)] if box else [0.0, 0.0, 0.0]


# ------------------------------------------------------------------ textures

def texture_image(raw: bytes):
    """The embedded image as a small RGB picture (sampled at the model's UVs), or None without Pillow."""
    try:
        from PIL import Image
    except ImportError:
        return None
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((256, 256))
    return im


def is_pink(c) -> bool:
    return c[0] > 0.9 and c[2] > 0.9 and c[1] < 0.15


# ------------------------------------------------------------------ lint

class Report:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, level, where, rule, msg):
        self.items.append({"level": level, "where": where, "rule": rule, "message": msg})

    def errors(self):
        return [i for i in self.items if i["level"] == "ERROR"]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def catalogue() -> dict:
    """The kit catalogue's entries by full sha256 ({} when it is missing or unreadable)."""
    global _CATALOGUE
    if _CATALOGUE is None:
        _CATALOGUE = {}
        try:
            for e in json.loads(CATALOG.read_text(encoding="utf-8")).get("entries") or []:
                sha = ((e.get("source") or {}).get("sha256") or "").lower()
                if sha:
                    _CATALOGUE[sha] = e
        except (OSError, ValueError, AttributeError):
            pass
    return _CATALOGUE


def catalogue_entry(path: Path | None = None, sha: str | None = None) -> dict | None:
    """The catalogue entry of a file (by its content) or of a sha256."""
    if sha is None and path is not None:
        try:
            sha = file_sha256(path)
        except OSError:
            return None
    return catalogue().get((sha or "").lower())


def catalogue_class(entry: dict | None, size) -> str | None:
    cls = CATEGORY_CLASS.get((entry or {}).get("category", ""))
    if cls in SMALL_IS_PROP and max(size) <= PROP_MAX_M:
        return "prop"
    return cls


def classify(name: str, size, given: str | None, budgets: dict, entry: dict | None = None) -> tuple[str, str]:
    """Model class: given (x-class / --class), else the catalogue entry's category, else words in
    the file name, else size."""
    if given:
        return given, "given"
    cat = catalogue_class(entry, size)
    if cat:
        return cat, "catalogue"
    stem = Path(name).stem.lower()
    found = []   # (class, end of its last matching word), in CLASS_WORDS order
    for cls, words in CLASS_WORDS:
        if cls == "prop" and max(size) > PROP_MAX_M:
            continue
        ends = [m.end(1) for m in re.finditer(r"(?:^|[^a-z])(%s)(?:s|es)?(?=$|[^a-z])" % words, stem)]
        if ends and cls in budgets:
            found.append((cls, max(ends)))
    if found:
        cls, end = found[0]
        if cls in PLACE and max(size) <= LIVING_MAX_M:
            # a person, animal or small thing named after a place: the head noun (last) wins
            later = [c for c, e in sorted(found, key=lambda f: -f[1]) if c in LIVING + ("prop",) and e > end]
            cls = later[0] if later else cls
        if cls in SMALL_IS_PROP and max(size) <= PROP_MAX_M:
            return "prop", "name+size"   # a small cart, gate or pole is a prop
        return cls, "name"
    return ("prop" if max(size) <= PROP_MAX_M else "building"), "size"


def lint_model(path: Path, prof: dict, rep: Report, cls_given: str | None = None, label: str | None = None,
               collect: list | None = None, root: int | None = None, in_world: bool = False,
               tint: str | None = None) -> dict:
    """Lints one .glb; returns {triangles (LOD0), drawn, lods, size, class}. `collect`, when given, receives one
    {name, share, metallic, colour} per opaque material (builtin_materials.py stores them for reused objects).
    A file whose root nodes carry extras {"x-class": C} (`style-gen street`) is linted part by part
    (`root`: only that root node's subtree), each as class C, reported as <file>#<node>.
    `in_world`: the model is a world package's asset, which the browser draws node by node (no LOD nodes).
    `tint`: the placement's scene.json "tint" ("#rrggbb"); the browser multiplies every colour by it, so
    the colours are judged after the multiply."""
    where = label or str(path)
    if root is None:
        try:
            roots = Glb(path).part_roots()
        except (OSError, ValueError, KeyError, struct.error):
            roots = []
        if roots:
            # a root without x-class in such a file is still drawn: lint it on its own too, and fail it
            g = Glb(path)
            nodes, tagged = g.g.get("nodes", []), {ri for ri, _, _ in roots}
            meshy = {r for i, r in g.root_of().items() if "mesh" in nodes[i]}
            untagged = [(r, nodes[r].get("name") or "node%d" % r, cls_given) for r in sorted(meshy - tagged)]
            for ri, name, _ in untagged:
                rep.add("ERROR", "%s#%s" % (where, name), "parts",
                        "root node without extras x-class in a file whose other root nodes have one: "
                        "give every root node its own {\"x-class\": ...}")
            tot, drawn, lods_all, box_all = 0, 0, {}, None
            for ri, name, cls in roots + untagged:
                info = lint_model(path, prof, rep, cls, "%s#%s" % (where, name), collect, ri, in_world, tint)
                tot += info["triangles"]
                drawn += info.get("drawn", info["triangles"])
                for k, v in info["lods"].items():
                    lods_all[k] = lods_all.get(k, 0) + v
            rep.add("INFO", where, "parts", "%d models in one file (root nodes with extras x-class), each linted on its own: "
                    "%d triangles at LOD0 together" % (len(roots), tot))
            return {"triangles": tot, "drawn": drawn, "lods": lods_all, "size": [0, 0, 0], "class": "parts"}
    lint = dict(DEFAULT_LINT, **(prof.get("lint") or {}))
    dims = prof.get("dimensions") or {}
    budgets = (prof.get("budgets") or {}).get("triangles") or {}
    try:
        g = Glb(path)
    except (OSError, ValueError, KeyError, struct.error) as e:
        rep.add("ERROR", where, "file", "cannot read: %s" % e)
        return {"triangles": 0, "lods": {}, "size": [0, 0, 0], "class": "?"}
    gj = g.g
    names = g.node_names()
    tint_lin = [srgb_to_linear(v) for v in hex_rgb(tint)] if tint else [1.0, 1.0, 1.0]
    lods: dict[int, int] = {}
    box0 = None
    mat_prims: dict[int, list] = {}
    parts: dict[str, list] = {"door": [], "roof": [], "arch": []}
    root_of = g.root_of() if root is not None else {}
    for i, node, m in g.instances():
        if root is not None and root_of.get(i) != root:
            continue
        chain = names[i]
        lod = 0
        for nm in chain:
            mm = LOD_RE.search(nm)
            if mm:
                lod = int(mm.group(1))
                break
        mesh = gj["meshes"][node["mesh"]]
        tris = 0
        nbox = None
        for p in mesh.get("primitives", []):
            t = g.prim_triangles(p)
            tris += t
            acc = gj["accessors"][p["attributes"]["POSITION"]]
            if lod == 0 and "min" in acc and "max" in acc:
                nbox = union(nbox, transform_box(m, acc["min"], acc["max"]))
            if lod == 0:
                mat_prims.setdefault(p.get("material", -1), []).append((t, p["attributes"]))
        lods[lod] = lods.get(lod, 0) + tris
        if lod == 0 and nbox:
            box0 = union(box0, nbox)
            own = (chain[0] + " " + (chain[1] if len(chain) > 1 and "mesh" in node else "")).lower()
            for part in parts:
                if part in own and not (part == "door" and re.search(r"frame|arch|step|knob|handle|bell|sign", own)) \
                        and not (part == "roof" and re.search(r"window|dormer|chimney|vent|cap|ridge_tile", own)):
                    parts[part].append((chain[0] or chain[-1], nbox if part != "arch" else (nbox, arch_ring(g, mesh, m))))
    size = size_of(box0)
    cls, how = classify(path.name if root is None else where, size, cls_given, budgets,
                        None if cls_given else catalogue_entry(path))
    tri0 = lods.get(0, 0)
    lod_txt = ", ".join("LOD%d %d" % (k, v) for k, v in sorted(lods.items()))
    budget = budgets.get(cls)
    if budget is None:
        rep.add("WARN", where, "budget", "class %s has no triangle budget in the profile (%s)" % (cls, lod_txt))
    elif tri0 > budget:
        eff = 100.0 * budget / tri0
        lvl = "ERROR" if eff < float(lint["min_efficiency"]) else "WARN"
        rep.add(lvl, where, "budget", "%d triangles at LOD0 > %s budget %d: efficiency %.0f (%s at %.0f; %s; class by %s)"
                % (tri0, cls, budget, eff, "fails" if lvl == "ERROR" else "lint passes", float(lint["min_efficiency"]), lod_txt, how))
    else:
        rep.add("INFO", where, "budget", "%d / %d triangles (%s, class %s by %s)" % (tri0, budget, lod_txt, cls, how))
    if len(lods) > 1:
        prev = None
        for k in sorted(lods):
            if prev is not None and lods[k] >= prev:
                rep.add("ERROR", where, "lod", "LOD%d has %d triangles, not fewer than the LOD before (%d)" % (k, lods[k], prev))
            prev = lods[k]
        if in_world:
            # the browser has no _LOD<n> node handling for package models: every node is drawn,
            # on top of LOD0 (harbour attempt 4, gaps G10/G14: 13 lanterns 58 draws, 23 with LOD0 only)
            rep.add("ERROR", where, "lod", "LOD nodes in a world asset (%s): the browser draws every node of the file, "
                    "so it pays %d triangles and their draw calls, not %d. Ship LOD0 only (style-gen --lods 1, or "
                    "export only the LOD0 nodes); the browser makes its own LOD chain (recipe lod_chain)"
                    % (lod_txt, sum(lods.values()), tri0))

    # scale
    person = float(dims.get("person_m", 0) or 0)
    if cls == "character" and person:
        tol = float(lint["person_tolerance"])
        if not (person * (1 - tol) <= size[1] <= person * (1 + tol)):
            rep.add("ERROR", where, "scale", "character is %.2f m tall; the profile's person is %.2f m (+-%d %%)"
                    % (size[1], person, round(tol * 100)))
    door = dims.get("door_m")
    if door and parts["door"]:
        grand = []
        gd = dims.get("grand_door_m")
        for v in (gd.values() if isinstance(gd, dict) else []):
            grand.extend(v if isinstance(v, list) else [v])
        lo, hi = float(door[0]), float(door[1])
        # grand doors: a landmark's may reach the largest, any other building's the smallest (an inn's)
        top = (max(grand) if cls == "landmark" else min(grand)) if grand else hi
        for name, b in parts["door"]:
            h = size_of(b)[1]
            ok = lo - 0.05 <= h <= max(hi, top) + 0.05
            if not ok:
                rep.add("ERROR", where, "scale", "door %r is %.2f m tall; the profile wants %.2f-%.2f m%s"
                        % (name, h, lo, hi, " (a %s's grand door up to %.1f m)" % (cls, top) if top > hi else ""))
            else:
                rep.add("INFO", where, "scale", "door %r %.2f m" % (name, h))

    # roofs and arches
    pitches = dims.get("roof_pitch_rise_per_run")
    frac = dims.get("roof_height_fraction")
    slack = float(lint["pitch_slack"])
    for name, b in parts["roof"]:
        s = size_of(b)
        run = min(s[0], s[2]) / 2.0
        if pitches and run > 0:
            pitch = s[1] / run
            lo, hi = min(pitches) * (1 - slack), max(pitches) * (1 + slack)
            if not lo <= pitch <= hi:
                rep.add("ERROR", where, "roof", "roof %r pitch %.2f (rise %.2f m over %.2f m) is outside the profile's %.2f-%.2f"
                        % (name, pitch, s[1], run, min(pitches), max(pitches)))
            else:
                rep.add("INFO", where, "roof", "roof %r pitch %.2f" % (name, pitch))
        elif frac and size[1] > 0:
            f = s[1] / size[1]
            if not float(frac[0]) - 0.05 <= f <= float(frac[1]) + 0.05:
                rep.add("ERROR", where, "roof", "roof %r is %.0f %% of the model's height; the profile wants %.0f-%.0f %%"
                        % (name, f * 100, frac[0] * 100, frac[1] * 100))
            else:
                rep.add("INFO", where, "roof", "roof %r is %.0f %% of the model's height" % (name, f * 100))
    arch = dims.get("arch_rise_half_span")
    for name, (b, ring) in parts["arch"]:
        s = size_of(b)
        rise, span = ring if ring else (s[1], max(s[0], s[2]))
        if arch and span > 0:
            r = rise / (span / 2.0)
            if not float(arch[0]) <= r <= float(arch[1]):
                rep.add("ERROR", where, "arch", "arch %r rise / half span %.2f is outside the profile's %.2f-%.2f"
                        % (name, r, arch[0], arch[1]))
            else:
                rep.add("INFO", where, "arch", "arch %r rise / half span %.2f" % (name, r))

    # materials, vertex colours and textures
    pal = Palette(prof)
    total = float(sum(t for prims in mat_prims.values() for t, _ in prims) or 1)
    tex = None
    off_share = 0.0
    tex_seen: dict[int, tuple] = {}
    materials = gj.get("materials", [])
    textures = gj.get("textures", [])
    for mi, prims in sorted(mat_prims.items()):
        mat = materials[mi] if 0 <= mi < len(materials) else {}
        mname = mat.get("name") or ("material %d" % mi if mi >= 0 else "default material")
        if mat.get("alphaMode") == "BLEND":
            continue  # glass, water and veils are judged by the review, not the palette
        pbr = mat.get("pbrMetallicRoughness", {})
        factor = list(pbr.get("baseColorFactor", [1, 1, 1, 1]))[:3]  # linear
        emissive = max(mat.get("emissiveFactor", [0, 0, 0])) > 0.2 or "KHR_materials_emissive_strength" in mat.get("extensions", {})
        ti = (pbr.get("baseColorTexture") or {}).get("index")
        tex, uv_name = None, "TEXCOORD_0"
        if ti is not None:
            src = textures[ti].get("source") if 0 <= ti < len(textures) else None
            if src is None or src >= len(gj.get("images", [])):
                rep.add("ERROR", where, "texture", "%s: base colour texture %s does not resolve" % (mname, ti))
                continue
            if src not in tex_seen:
                raw = g.image_bytes(src)
                if raw is None:
                    rep.add("ERROR", where, "texture", "%s: image %d is not embedded" % (mname, src))
                    continue
                try:
                    tex_seen[src] = texture_image(raw)
                except Exception as e:  # noqa: BLE001 (any decode error is a broken texture)
                    rep.add("ERROR", where, "texture", "%s: image %d does not decode: %s" % (mname, src, e))
                    continue
            tex = tex_seen[src]
            if tex is None:
                continue
            uv_name = "TEXCOORD_%d" % int((pbr.get("baseColorTexture") or {}).get("texCoord", 0))
        if emissive:
            continue
        # a baked-light material (KHR_materials_unlit with a texture, kit/blender/bake_unlit.py)
        # holds colour x light: its dark texels are shade, judged by `iamar-world audit dark-bake`
        # (which knows what a viewer can see), not by the albedo rules here
        baked = "KHR_materials_unlit" in (mat.get("extensions") or {}) and tex is not None
        # samples: (sRGB colour, weight); vertex colours multiply the base colour (glTF)
        samples: list[tuple] = []
        for t, attrs in prims:
            col = g.accessor_values(attrs["COLOR_0"], limit=4000) if "COLOR_0" in attrs else None
            uvs = g.accessor_values(attrs[uv_name], limit=4000) if tex is not None and uv_name in attrs else None
            n = max(len(col or []), len(uvs or []), 1)
            w = float(t) / n
            for i in range(n):
                c = list(factor)
                if uvs is not None:
                    u, v = uvs[min(i, len(uvs) - 1)][:2]
                    px = tex.getpixel((int((u % 1.0) * tex.width) % tex.width, int((v % 1.0) * tex.height) % tex.height))
                    c = [srgb_to_linear(px[k] / 255.0) * c[k] for k in range(3)]
                elif tex is not None:
                    mean = tex.resize((1, 1)).getpixel((0, 0))
                    c = [srgb_to_linear(mean[k] / 255.0) * c[k] for k in range(3)]
                if col is not None:
                    vc = col[min(i, len(col) - 1)]
                    c = [c[k] * vc[k] for k in range(3)]
                c = [c[k] * tint_lin[k] for k in range(3)]
                samples.append((tuple(linear_to_srgb(v) for v in c), w))
        mw = sum(w for _, w in samples) or 1.0
        share = sum(t for t, _ in prims) / total
        metallic = float(pbr.get("metallicFactor", 1.0)) if "metallicRoughnessTexture" not in pbr else 0.0
        mean = tuple(sum(c[k] * w for c, w in samples) / mw for k in range(3))
        if collect is not None:
            collect.append({"name": mname, "share": round(share, 4), "metallic": round(metallic, 2),
                            "colour": rgb_hex(mean), "baked": baked})
        if metallic >= lint["max_metallic"] and not baked:
            rep.add("WARN", where, "metal", "%s: metallicFactor %.2f with no metal texture: a metal surface reflects its "
                    "environment and the preview world has none, so it renders near black at eye height "
                    "(set metallicFactor to 0 or give it a metal texture)" % (mname, metallic))
        pink = sum(w for c, w in samples if is_pink(c)) / (sum(w for _, w in samples) or 1.0)
        if pink > lint["pink_texture_share"]:
            rep.add("ERROR", where, "texture", "%s: %.1f %% of its surface is missing-texture pink" % (mname, pink * 100))
        bad = {"forbidden": 0.0, "dark": 0.0, "saturated": 0.0, "off": 0.0}
        worst = {}
        # the palette share of a baked material counts only its lit texels: shade (hidden faces,
        # sub-texel triangles, undersides) is no colour choice and is left to audit dark-bake too
        for c, w in samples:
            kinds = pal.judge(c)
            shade = baked and "dark" in kinds and not is_pink(c)
            for kind in kinds:
                if baked and (kind == "dark" or (kind == "forbidden" and not is_pink(c))):
                    continue
                if shade and kind == "off":
                    continue
                bad[kind] += w / mw
                worst.setdefault(kind, c)
        if baked:
            rep.add("INFO", where, "colour", "%s: baked light (unlit): dark texels are checked by iamar-world audit dark-bake" % mname)
        single = len(samples) == 1
        limit = 0.0 if single else float(lint["vertex_bad_share"])
        if bad["forbidden"] > limit:
            rep.add("ERROR", where, "colour", "%s: %s%s is too close to a forbidden colour (black, missing-texture pink)"
                    % (mname, rgb_hex(worst["forbidden"]), "" if single else " (on %.0f %% of its surface)" % (bad["forbidden"] * 100)))
        if bad["dark"] > limit:
            rep.add("ERROR", where, "colour", "%s: %s%s is darker than min_albedo_value %.2f (no black surfaces)"
                    % (mname, rgb_hex(worst["dark"]), "" if single else " (on %.0f %% of its surface)" % (bad["dark"] * 100),
                       lint["min_albedo_value"]))
        if bad["saturated"] > limit and share > 0.01:
            rep.add("ERROR", where, "colour", "%s: %s%s is more saturated than max_saturation %.2f"
                    % (mname, rgb_hex(worst["saturated"]), "" if single else " (on %.0f %% of its surface)" % (bad["saturated"] * 100),
                       lint["max_saturation"]))
        if bad["off"] > 0:
            off_share += share * bad["off"]
            if bad["off"] * share > 0.005:
                c = worst["off"]
                near, d = pal.nearest(c)
                rep.add("WARN", where, "palette", "%s: %s is %.1f from the palette (nearest %s); off-palette colour on %.1f %% of triangles"
                        % (mname, rgb_hex(c), d, near, share * bad["off"] * 100))
    if off_share > lint["palette_max_off_share"]:
        rep.add("ERROR", where, "palette", "%.0f %% of the triangles use colours off the %s palette (max %.0f %%)"
                % (off_share * 100, prof.get("id"), lint["palette_max_off_share"] * 100))
    else:
        rep.add("INFO", where, "palette", "%.1f %% of the triangles off the %s palette" % (off_share * 100, prof.get("id")))
    return {"triangles": tri0, "drawn": sum(lods.values()), "lods": lods, "size": size, "class": cls}


def reused_file(rec: dict) -> tuple[Path | None, dict | None]:
    """A manifest.reused record (`iamar-world assets use <hash> --as <path>`, AGENT_KIT step 3):
    the kit's own copy of the object when the catalogue has it as a kit file whose bytes still match
    the hash, and its catalogue entry."""
    sha = str(rec.get("sha256", "")).lower()
    entry = catalogue_entry(sha=sha)
    rel = str(((entry or {}).get("source") or {}).get("file") or "")
    f = KIT.parent / rel
    if rel.startswith("kit/") and ".." not in Path(rel).parts and f.is_file():
        try:
            if file_sha256(f) == sha:
                return f, entry
        except OSError:
            pass
    return None, entry


def lint_builtin_materials(rec: dict, prof: dict, rep: Report, label: str, what: str, tint: str | None = None) -> None:
    """A built-in object has no file in the kit; kit/catalog/builtin_materials.json (built by
    builtin_materials.py from the browser's files) holds its materials, judged here like a model of
    the world's own: near-black or off-palette colours and bare metal (a reused object is only
    kept after a close eye-height shot, AGENT_KIT step 3). `tint` is the placement's scene.json
    "tint": the browser multiplies albedo by it, so the mean colour is judged after the multiply."""
    try:
        mats = json.loads((KIT / "catalog" / "builtin_materials.json").read_text(encoding="utf-8")).get(
            str(rec.get("sha256", "")).lower())
    except (OSError, ValueError):
        mats = None
    if not mats:
        return
    lint = dict(DEFAULT_LINT, **(prof.get("lint") or {}))
    pal = Palette(prof)
    for m in mats:
        if m.get("baked"):
            continue
        c = hex_rgb(m["colour"])
        if tint:
            t = hex_rgb(tint)
            c = tuple(linear_to_srgb(srgb_to_linear(c[k]) * srgb_to_linear(t[k])) for k in range(3))
        shown = rgb_hex(c) if tint else m["colour"]
        kinds = pal.judge(c)
        if m.get("metallic", 0) >= lint["max_metallic"]:
            rep.add("WARN", label, "metal", "%s: material %s has metallicFactor %.2f and no metal texture: browsers from "
                    "iamar ae33b8aa draw it matte, as the city does, but older ones render it near black at eye height; "
                    "look at it in a close eye-height shot before keeping it" % (what, m["name"], m["metallic"]))
        for k in ("forbidden", "dark"):
            if k in kinds:
                rep.add("WARN", label, "colour", "%s: material %s mean colour %s is %s for the style (no black surfaces)"
                        % (what, m["name"], shown, "darker than min_albedo_value %.2f" % lint["min_albedo_value"] if k == "dark" else "near a forbidden colour"))
        if "off" in kinds and m.get("share", 0) > 0.1:
            near, d = pal.nearest(c)
            rep.add("WARN", label, "palette", "%s: material %s mean colour %s is %.1f from the palette (nearest %s) on %.0f %% of its triangles"
                    % (what, m["name"], shown, d, near, m["share"] * 100))


def lint_reused(rec: dict, prof: dict, rep: Report, cls_given: str | None, label: str, tint: str | None = None) -> dict | None:
    """Lints a reused object as validate resolves it (the file is not in the world folder): the
    kit's copy when there is one, else the catalogue's numbers (a built-in object of the browser)."""
    src = rec.get("source") or {}
    what = "reused %s (%s %s)" % (str(rec.get("sha256", "?"))[:16], src.get("world", "?"), src.get("file", "?"))
    f, entry = reused_file(rec)
    if f:
        rep.add("INFO", label, "file", "%s: linting the kit's copy %s" % (what, f.relative_to(KIT.parent).as_posix()))
        return lint_model(f, prof, rep, cls_given, label + (" tinted %s" % tint if tint else ""), in_world=True, tint=tint)
    if entry is None:
        rep.add("WARN", label, "file", "%s is not in this kit's catalogue: not styled here (validate checks it)" % what)
        return None
    lint_builtin_materials(rec, prof, rep, label, what + (" tinted %s" % tint if tint else ""), tint)
    budgets = (prof.get("budgets") or {}).get("triangles") or {}
    size = [float(x) for x in (entry.get("size") or [0, 0, 0])]
    cls, how = classify(str(rec.get("path", "")), size, cls_given, budgets, entry)
    tri0 = int((entry.get("triangles") or {}).get("lod0", 0) or 0)
    budget = budgets.get(cls)
    lvl = "WARN" if budget and tri0 > budget else "INFO"
    rep.add(lvl, label, "budget", "%s: catalogue %r, %d triangles at LOD0%s (class %s by %s); built into the browser, "
            "not linted here" % (what, entry.get("name"), tri0, " / %d" % budget if budget else "", cls, how))
    return {"triangles": tri0, "lods": {0: tri0}, "size": size, "class": cls}


def obj_scale(o) -> float:
    s = o.get("scale", 1)
    return float(max(s)) if isinstance(s, list) else float(s)


TINT_APART = 0.05   # two placements' tints differ visibly when a channel differs by this much (sRGB 0-1)


def placement_tint(o: dict) -> str | None:
    """A scene.json object's "tint" when it is a valid "#rrggbb" (WORLD_FORMAT 4.4), lower-cased; else None
    (white multiplies by 1: no tint)."""
    t = str(o.get("tint", "")).lower()
    return t if re.fullmatch(r"#[0-9a-f]{6}", t) and t != "#ffffff" else None


def lint_world(world: Path, prof: dict, rep: Report) -> None:
    lint = dict(DEFAULT_LINT, **(prof.get("lint") or {}))
    try:
        scene = json.loads((world / "scene.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        rep.add("ERROR", str(world), "scene", "cannot read scene.json: %s" % e)
        return
    try:
        manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    reused = {str(r.get("path", "")): r for r in (manifest.get("reused") or []) if isinstance(r, dict)}
    cache: dict[tuple, dict] = {}
    placed = 0
    objs = scene.get("objects") or []
    info_by_obj = []
    for o in objs:
        asset = o.get("asset", "")
        p = world / asset
        vr = o.get("visible_range", 0)
        if isinstance(vr, (int, float)) and 0 < vr < 0.5:
            rep.add("INFO", "%s:objects.%s" % (world.name, o.get("id")), "skip", "collision-only (visible_range %.2f): not styled" % vr)
            info_by_obj.append(None)
            continue
        tint = placement_tint(o)
        key = (asset, o.get("x-class"), tint)
        if key not in cache:
            if not p.is_file() and asset in reused:
                cache[key] = lint_reused(reused[asset], prof, rep, o.get("x-class"), "%s/%s" % (world.name, asset), tint)
            elif not p.is_file():
                rep.add("ERROR", "%s:objects.%s" % (world.name, o.get("id")), "file", "asset %s is missing" % asset)
                cache[key] = None
            else:
                cache[key] = lint_model(p, prof, rep, o.get("x-class"), "%s/%s%s" % (world.name, asset, " tinted %s" % tint if tint else ""),
                                        in_world=True, tint=tint)
        info = cache[key]
        info_by_obj.append(info)
        if info:
            placed += info.get("drawn", info["triangles"])   # every node is drawn, LOD nodes too
    # neighbours: the same building or landmark at the same scale, close together
    near = float(lint["neighbour_m"])
    for i, a in enumerate(objs):
        ia = info_by_obj[i]
        if not ia or ia["class"] not in ("building", "landmark"):
            continue
        for j in range(i + 1, len(objs)):
            b = objs[j]
            if b.get("asset") != a.get("asset") or abs(obj_scale(a) - obj_scale(b)) > 0.05 * obj_scale(a):
                continue
            ta, tb = hex_rgb(placement_tint(a) or "#ffffff"), hex_rgb(placement_tint(b) or "#ffffff")
            if max(abs(ta[k] - tb[k]) for k in range(3)) >= TINT_APART:
                continue   # a visibly different tint makes them different neighbours
            pa, pb = a.get("position", [0, 0, 0]), b.get("position", [0, 0, 0])
            d = math.dist(pa, pb)
            if d < near:
                rep.add("ERROR", "%s:objects.%s" % (world.name, b.get("id")), "neighbours",
                        "same %s %s as neighbour %s %.1f m away (closer than %.0f m): vary the model, tint or scale (%s)"
                        % (ia["class"], a.get("asset"), a.get("id"), d, near,
                           (prof.get("weathering") or {}).get("neighbour_rule", "no two neighbours alike")[:80]))
    # primitives
    colours = profile_colours(prof)
    forbidden = [hex_rgb(h) for h in lint["forbidden_colours"]]
    for pr in scene.get("primitives") or []:
        h = pr.get("color")
        if not (isinstance(h, str) and re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", h)) or pr.get("unlit"):
            continue
        c = hex_rgb(h[:7])
        where = "%s:primitives.%s" % (world.name, pr.get("id", pr.get("shape")))
        if len(h) == 9 and int(h[7:], 16) == 0:
            rep.add("INFO", where, "colour", "%s: fully transparent (invisible collision proxy), no colour rules" % h)
            continue
        if any(delta_e(c, f) < lint["forbidden_delta_e"] for f in forbidden):
            rep.add("ERROR", where, "colour", "%s is a forbidden colour" % h)
        hh, ss, vv = colorsys.rgb_to_hsv(*c)
        if vv < lint["min_albedo_value"]:
            rep.add("ERROR", where, "colour", "%s darker than min_albedo_value" % h)
        n, d = nearest(c, colours) if colours else ("", 0.0)
        if d > lint["palette_max_delta_e"]:
            rep.add("WARN", where, "palette", "%s is %.1f from the palette (nearest %s)" % (h, d, n))
    frame = ((prof.get("budgets") or {}).get("frame") or {}).get("visible_triangles_max")
    if frame and placed > frame:
        rep.add("ERROR", world.name, "frame", "%d placed triangles > frame budget %d" % (placed, frame))
    else:
        rep.add("INFO", world.name, "frame", "%d placed triangles%s" % (placed, " of %d" % frame if frame else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("targets", nargs="+", help="world folder(s) or .glb file(s)")
    ap.add_argument("--style", help="profile id or style.json (default: the world's style.json, else iamar)")
    ap.add_argument("--class", dest="cls", help="asset class for .glb targets (building, prop, character ...)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--quiet", action="store_true", help="only WARN and ERROR lines")
    a = ap.parse_args(argv)
    rep = Report()
    profiles = set()
    for t in a.targets:
        p = Path(t)
        ref = a.style or (str(p / "style.json") if p.is_dir() and (p / "style.json").is_file() else "iamar")
        try:
            prof, _ = check_style.load(ref)
        except (OSError, ValueError) as e:
            print("ERROR cannot load style profile %s: %s" % (ref, e))
            return 2
        profiles.add(prof.get("id", ref))
        if p.is_dir():
            lint_world(p, prof, rep)
        elif p.suffix.lower() == ".glb":
            lint_model(p, prof, rep, a.cls)
        else:
            rep.add("ERROR", t, "file", "not a world folder or .glb")
    if not any(i["rule"] == "texture" for i in rep.items):
        try:
            import PIL  # noqa: F401
        except ImportError:
            rep.add("WARN", "-", "texture", "Pillow not installed: texture checks skipped")
    errs = rep.errors()
    if a.json:
        print(json.dumps({"profiles": sorted(profiles), "ok": not errs, "items": rep.items}, indent=1))
    else:
        for i in rep.items:
            if a.quiet and i["level"] == "INFO":
                continue
            print("%-5s %s [%s] %s" % (i["level"], i["where"], i["rule"], i["message"]))
        print("%s style lint (%s): %d error(s), %d warning(s)" % ("FAIL" if errs else "OK", ", ".join(sorted(profiles)),
              len(errs), sum(1 for i in rep.items if i["level"] == "WARN")))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
