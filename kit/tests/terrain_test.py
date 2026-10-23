#!/usr/bin/env python3
"""iamar-world terrain: every kind writes a valid heightmap, water that matches, and a dry spawn."""
import importlib.util, json, math, os, struct, subprocess, sys, tempfile, zlib

TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "terrain", "terrain.py")


def read_png(path):
    d = open(path, "rb").read()
    assert d[:8] == b"\x89PNG\r\n\x1a\n"
    n = struct.unpack(">I", d[16:20])[0]
    assert d[24] == 8 and d[25] == 0, "8-bit greyscale"
    i, idat = 8, b""
    while i < len(d):
        ln = struct.unpack(">I", d[i:i + 4])[0]
        if d[i + 4:i + 8] == b"IDAT":
            idat += d[i + 8:i + 8 + ln]
        i += 12 + ln
    raw = zlib.decompress(idat)
    return n, [list(raw[r * (n + 1) + 1:(r + 1) * (n + 1)]) for r in range(n)]


def run(*args):
    return subprocess.run([sys.executable, "-I", TOOL, *args], capture_output=True, text=True)


for kind in ("coast", "island", "lake", "river"):
    with tempfile.TemporaryDirectory() as w:
        r = run(kind, w)
        assert r.returncode == 2 and "iamar-world new" in r.stderr, r.stderr
        json.dump({"environment": {"sky": "x"}, "objects": [{"id": "keep"}]}, open(os.path.join(w, "scene.json"), "w"))
        r = run(kind, w, "--resolution", "65", "--json")
        assert r.returncode == 0, r.stderr
        out = json.loads(r.stdout)
        sc = json.load(open(os.path.join(w, "scene.json")))
        assert sc["objects"] == [{"id": "keep"}] and sc["environment"] == {"sky": "x"}
        t = sc["terrain"]
        n, rows = read_png(os.path.join(w, "textures", "height.png"))
        assert n == t["resolution"] == 65
        flat = [p for row in rows for p in row]
        assert min(flat) == 0 and max(flat) == 255
        lo, hi = t["min_height"], t["max_height"]
        water = sc["water"][0]
        assert water["swimmable"] and water["depth"] >= 2
        wl = water["position"][1]
        assert lo < wl - 2 and hi > wl + 1, (kind, lo, hi, wl)
        # the spawn stands on the ground the browser builds, above the water
        sp = sc["spawn_points"][0]
        assert sp["id"] == "default"
        x, y, z = sp["position"]
        step = t["size"][0] / (n - 1)
        j = round((x + t["size"][0] / 2) / step)
        i = round((z + t["size"][1] / 2) / step)
        ground = lo + rows[i][j] / 255.0 * (hi - lo)
        assert abs(y - ground - 0.05) < 0.02, (kind, y, ground)
        assert y > wl + 0.3, (kind, y, wl)
        # water extent covers the wet vertices: no vertex below the surface lies outside it
        wx, wz = water["position"][0], water["position"][2]
        sx, sz = water["size"]
        for ii in range(n):
            for jj in range(n):
                g = lo + rows[ii][jj] / 255.0 * (hi - lo)
                if g < wl - 0.3:
                    px = -t["size"][0] / 2 + jj * step
                    pz = -t["size"][1] / 2 + ii * step
                    assert abs(px - wx) <= sx / 2 + 0.01 and abs(pz - wz) <= sz / 2 + 0.01, (kind, px, pz)
        assert out["next"].startswith("iamar-world validate")
        h = run(kind, w, "--resolution", "65", "--beach-width", "1")
        assert "WARN: beach" in h.stdout and "NEXT:" in h.stdout, h.stdout
# the spawn faces the water: 5 m ahead is closer to it, for every kind, size and seed (an internal task)
spec = importlib.util.spec_from_file_location("terrain_tool", TOOL)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
for kind in ("coast", "island", "lake", "river"):
    for size in ("256", "1024"):
        for seed in range(1, 9):
            with tempfile.TemporaryDirectory() as w:
                json.dump({}, open(os.path.join(w, "scene.json"), "w"))
                r = run(kind, w, "--resolution", "65", "--size", size, "--seed", str(seed))
                assert r.returncode == 0, r.stderr
                sp = json.load(open(os.path.join(w, "scene.json")))["spawn_points"][0]
                x, _, z = sp["position"]
                yaw = math.radians(sp["yaw"])
                here = tool.signed_distance(kind, x, z, float(size), seed)
                # the browser walks forward along (-sin yaw, -cos yaw) (player.gd, WorldPackage.yaw_basis)
                ahead = tool.signed_distance(kind, x - 5 * math.sin(yaw), z - 5 * math.cos(yaw), float(size), seed)
                assert ahead > here, (kind, size, seed, sp, here, ahead)
# no dry pit: at every size, a vertex below the surface lies inside the water (an internal task: the lake's
# fixed margin left pits up to 1.2 m deep outside the water at size 1024)
for kind in ("coast", "island", "lake", "river"):
    for size in (64.0, 256.0, 512.0, 1024.0):
        for seed in range(1, 9):
            pix, gh, ds, lo, hi, step = tool.build(kind, size, 14.0, 4.0, 0.2, 49, seed)
            wx, _, wz = tool.water_entries(kind, size, 4.0, 0.2, "#fff")[0]["position"]
            sx, sz = tool.water_entries(kind, size, 4.0, 0.2, "#fff")[0]["size"]
            for ii in range(49):
                for jj in range(49):
                    if gh[ii][jj] < 0.2 - 0.05:
                        px, pz = -size / 2 + jj * step, -size / 2 + ii * step
                        assert abs(px - wx) <= sx / 2 + 0.01 and abs(pz - wz) <= sz / 2 + 0.01, (kind, size, seed, px, pz)
print("terrain_test PASS")
