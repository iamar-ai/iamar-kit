#!/usr/bin/env python3
"""iamar-world terrain: coast, island, lake and river heightmaps with matching water and a spawn on dry ground.

  iamar-world terrain coast|island|lake|river <world> [--size 256] [--beach-width 14] [--depth 4]
                                             [--water-level 0.2] [--resolution 97] [--seed 1] [--json]

Writes <world>/textures/height.png (resolution x resolution, one pixel per terrain vertex, so the
ground the browser builds is exactly the ground computed here) and sets "terrain", "water" and one
"default" spawn point in <world>/scene.json, keeping every other field. Water is swimmable and
sized to the real shoreline; the spawn stands on dry sand facing the water.
Layout (world centred on 0,0): coast has the sea on +Z; island sits in the middle of the sea;
lake is a basin in the middle of land; river runs along X. Pure standard library.
"""
import argparse, json, math, os, struct, sys, zlib

KINDS = ("coast", "island", "lake", "river")


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def wob(x, z, seed):
    """Deterministic gentle noise in [-1, 1] (a few sines, no random state)."""
    s = seed * 1.7
    return (math.sin(x * 0.045 + s) * math.cos(z * 0.037 - s) * 0.6
            + math.sin(x * 0.11 - z * 0.09 + s * 2) * 0.4)


def signed_distance(kind, x, z, size, seed):
    """Metres from the shoreline: positive in the water, negative on land."""
    w = wob(x, z, seed)
    if kind == "coast":
        return (z - size * 0.12) + w * size * 0.03
    if kind == "island":
        return math.hypot(x, z) - size * 0.22 + w * size * 0.02
    if kind == "lake":
        return size * 0.2 - math.hypot(x * 0.8, z) + w * size * 0.015
    return size * 0.04 - abs(z - math.sin(x * 2 * math.pi / size * 1.5 + seed) * size * 0.08) + w * size * 0.008


def height(d, water, depth, beach, hill):
    if d > 0:
        run = max(depth * 4.0, 8.0)
        return water - depth * smooth(d / run)
    t = -d
    h = water + 0.05 + 1.1 * smooth(t / beach)
    if t > beach:
        h += hill * (1 - math.exp(-(t - beach) / 45.0))
    return h


def png_gray8(path, rows):
    n = len(rows)
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 0, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def build(kind, size, beach, depth, water, res, seed):
    hill = 2.5
    step = size / (res - 1)
    hs, ds = [], []
    for i in range(res):
        z = -size / 2 + i * step
        hr, dr = [], []
        for j in range(res):
            x = -size / 2 + j * step
            d = signed_distance(kind, x, z, size, seed)
            hr.append(height(d, water, depth, beach, hill * (0.6 + 0.4 * wob(x * 0.5, z * 0.5, seed + 3))))
            dr.append(d)
        hs.append(hr)
        ds.append(dr)
    lo = min(min(r) for r in hs)
    hi = max(max(r) for r in hs)
    span = max(hi - lo, 0.001)
    pix = [[int(round((h - lo) / span * 255)) for h in r] for r in hs]
    # the heights the browser will see (quantised to 8 bits), for the spawn
    gh = [[lo + p / 255.0 * span for p in r] for r in pix]
    return pix, gh, ds, lo, hi, step


def pick_spawn(kind, size, beach, gh, ds, res, step, water):
    """Dry ground just inland of the sand, close to the middle of the map."""
    want = -(beach + 4.0)
    best = None
    for i in range(res):
        for j in range(res):
            if gh[i][j] <= water + 0.3:
                continue
            x = -size / 2 + j * step
            z = -size / 2 + i * step
            score = abs(ds[i][j] - want) + 0.01 * math.hypot(x, z)
            if best is None or score < best[0]:
                best = (score, x, z, gh[i][j])
    if best is None:
        raise SystemExit("terrain: no dry ground found; lower --water-level or --depth")
    return best[1], best[2], best[3]


def facing_yaw(kind, x, z, size, seed):
    """Yaw in degrees that looks toward the water: up the gradient of the signed distance at the spawn,
    so a meandering river or a wobbly shore never puts the water behind. Browser convention (player.gd,
    WorldPackage.yaw_basis): yaw 0 faces -Z, 180 faces +Z, forward = (-sin yaw, -cos yaw)."""
    h = 0.5
    dx = signed_distance(kind, x + h, z, size, seed) - signed_distance(kind, x - h, z, size, seed)
    dz = signed_distance(kind, x, z + h, size, seed) - signed_distance(kind, x, z - h, size, seed)
    return round(math.degrees(math.atan2(-dx, -dz)) % 360, 1)


def water_entries(kind, size, depth, water, color):
    def entry(i, pos, sz):
        return {"id": i, "position": pos, "size": sz, "depth": round(depth, 2), "color": color, "swimmable": True}
    if kind == "coast":
        z0 = size * 0.12 - size * 0.04  # covers the wobbling shoreline
        return [entry("sea", [0, water, round((z0 + size / 2) / 2, 2)], [size, round(size / 2 - z0, 2)])]
    if kind == "island":
        return [entry("sea", [0, water, 0], [size, size])]
    if kind == "lake":
        r = size * (0.2 + 0.015)          # the shore wobbles out to here (signed_distance), so scale with size
        return [entry("lake", [0, water, 0], [round(r * 2 / 0.8 + 4, 2), round(r * 2 + 4, 2)])]
    return [entry("river", [0, water, 0], [size, round(size * 0.27 + 4, 2)])]


def main(argv):
    ap = argparse.ArgumentParser(prog="iamar-world terrain", description=__doc__.split("\n\n")[0])
    ap.add_argument("kind", choices=KINDS)
    ap.add_argument("world")
    ap.add_argument("--size", type=float, default=256.0, help="terrain side in metres (default 256)")
    ap.add_argument("--beach-width", type=float, default=14.0, help="sand width in metres (default 14)")
    ap.add_argument("--depth", type=float, default=4.0, help="water depth in metres (default 4, swimmable)")
    ap.add_argument("--water-level", type=float, default=0.2, help="water surface height (default 0.2)")
    ap.add_argument("--resolution", type=int, default=97, help="vertices per side (default 97)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--color", default="#3aa6b8cc", help="water colour (default clear teal)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    scene_path = os.path.join(a.world, "scene.json")
    if not os.path.isfile(scene_path):
        print("iamar-world terrain: %s not found. Run: iamar-world new %s" % (scene_path, a.world), file=sys.stderr)
        return 2
    if not 17 <= a.resolution <= 1025 or a.size <= 0 or a.beach_width <= 0 or a.depth <= 0:
        print("iamar-world terrain: need 17 <= --resolution <= 1025 and positive --size/--beach-width/--depth", file=sys.stderr)
        return 2
    step = a.size / (a.resolution - 1)
    warns = []
    if a.beach_width < step * 2:
        warns.append("beach %.1f m is under 2 vertex spacings (%.1f m): the shore will look jagged; raise --resolution or --beach-width" % (a.beach_width, step))
    if a.depth < 2.0:
        warns.append("depth %.1f m is too shallow to dive; use --depth 2 or more for swimming" % a.depth)
    tris = 2 * (a.resolution - 1) ** 2
    pix, gh, ds, lo, hi, step = build(a.kind, a.size, a.beach_width, a.depth, a.water_level, a.resolution, a.seed)
    x, z, y = pick_spawn(a.kind, a.size, a.beach_width, gh, ds, a.resolution, step, a.water_level)
    yaw = facing_yaw(a.kind, x, z, a.size, a.seed)
    os.makedirs(os.path.join(a.world, "textures"), exist_ok=True)
    png_gray8(os.path.join(a.world, "textures", "height.png"), pix)
    with open(scene_path, encoding="utf-8") as f:
        scene = json.load(f)
    scene["terrain"] = {"type": "heightmap", "size": [a.size, a.size], "position": [0, 0, 0],
                        "heightmap": "textures/height.png", "min_height": round(lo, 4), "max_height": round(hi, 4),
                        "resolution": a.resolution,
                        "materials": [{"color": "#c9b98a", "min_height": -100},
                                      {"color": "#7a9a52", "min_height": round(a.water_level + 1.3, 2)}],
                        "collision": True}
    scene["water"] = water_entries(a.kind, a.size, a.depth, a.water_level, a.color)
    spawn = {"id": "default", "position": [round(x, 2), round(y + 0.05, 2), round(z, 2)], "yaw": yaw}
    scene["spawn_points"] = [spawn] + [s for s in scene.get("spawn_points", []) if s.get("id") != "default"]
    with open(scene_path, "w", encoding="utf-8") as f:
        json.dump(scene, f, indent=2)
        f.write("\n")
    nxt = "iamar-world validate %s" % a.world
    res = {"kind": a.kind, "world": a.world, "heightmap": "textures/height.png", "resolution": a.resolution,
           "triangles": tris, "min_height": round(lo, 3), "max_height": round(hi, 3), "water_level": a.water_level,
           "spawn": spawn, "water": scene["water"], "warnings": warns, "next": nxt}
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print("TERRAIN %s: %dx%d vertices (%d triangles), heights %.2f..%.2f m, water at %.2f m, %.1f m deep"
              % (a.kind, a.resolution, a.resolution, tris, lo, hi, a.water_level, a.depth))
        print("SPAWN default at %s yaw %s (dry ground, facing the water)" % (spawn["position"], yaw))
        for w in warns:
            print("WARN: " + w)
        print("NEXT: " + nxt)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
