#!/usr/bin/env python3
"""Tests for the timber frame of style-gen houses (kit/style/gen/frame.py, an internal task: the harbour
blind test a5 houses were plaster with quoins, review gap R3). Every pattern builds rails, posts
and braces as it says and passes the closure, roof and zfight audits on every LOD (so no timber
lies on a window, a quoin, the oriel or the tower); the iamar profile frames its town houses by
default and a Track B profile without weights stays plain; LOD1 drops the braces, LOD2 the frame.

    python3 kit/tests/style/gen/frame_test.py [--quick]

The audits need numpy (as `iamar-world audit` does). --quick skips the every-feature houses.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[3]
GEN = KIT / "style" / "gen" / "gen.py"
DESERT = KIT / "style" / "schema" / "examples" / "desert_trading_post.style.json"
HARBOUR = KIT / "style" / "schema" / "examples" / "harbour_quarter.style.json"
PATTERNS = ("plain", "post", "studs", "braced", "crossed")


def run(*args):
    p = subprocess.run([sys.executable, str(GEN), *map(str, args), "--json"], capture_output=True, text=True)
    try:
        rep = json.loads(p.stdout)
    except ValueError:
        rep = {}
    return p, rep


def main() -> int:
    quick = "--quick" in sys.argv
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (("  " + str(detail)[-700:]) if detail and not cond else ""), flush=True)

    try:
        import numpy  # noqa: F401
        have_np = True
    except ImportError:
        have_np = False
        print("SKIPPED audits (numpy not installed)")

    with tempfile.TemporaryDirectory(prefix="iamar-frame-") as raw:
        tmp = Path(raw)
        tris, pieces = {}, {}
        for t in PATTERNS:
            args = ["house", tmp / ("%s.glb" % t), "--region", "warriors", "--seed", 3, "--storeys", 3,
                    "--footprint", "9x7", "--no-tower", "--no-oriel", "--timber", t, "--budget", 9000]
            if have_np:
                args += ["--world", tmp / ("w_%s" % t), "--check"]
            p, rep = run(*args)
            tris[t] = rep.get("triangles_per_lod", [0, 0, 0])
            pieces[t] = rep.get("timber_pieces", {})
            # a high budget keeps every piece (fit() drops dressing to meet the building budget)
            check("%s: generated with every piece" % t,
                  p.returncode == 0 and rep.get("timber_frame") == t and rep.get("economy") == 0, p.stdout[-600:] + p.stderr)
            if have_np:
                check("%s: closure, roof and zfight audits pass on every LOD" % t, rep.get("audit_ok") is True,
                      rep.get("audit"))
        pc = lambda t, k: pieces[t].get(k, 0)
        check("plain: no timber on the walls", sum(pieces["plain"].values()) == 0, pieces["plain"])
        # one centre post per wall and storey (a window in the middle splits it into the pieces above and below)
        check("post: rails and a centre post per wall and storey, no braces",
              pc("post", "rails") >= 8 and 0 < pc("post", "posts") <= 16 and pc("post", "braces") == 0, pieces["post"])
        check("studs: studs on every bay line, no braces",
              pc("studs", "posts") > pc("post", "posts") and pc("studs", "braces") == 0, pieces["studs"])
        check("braced: corner braces", pc("braced", "braces") >= 4, pieces["braced"])
        check("crossed: crosses in pairs, more braces than braced",
              pc("crossed", "braces") > pc("braced", "braces") and pc("crossed", "braces") % 2 == 0, pieces["crossed"])
        check("LOD0 triangles grow plain < post < studs <= braced < crossed",
              tris["plain"][0] < tris["post"][0] < tris["studs"][0] <= tris["braced"][0] < tris["crossed"][0],
              {t: tris[t] for t in PATTERNS})
        check("LOD1 keeps rails and posts, drops the braces",
              tris["plain"][1] < tris["studs"][1] == tris["braced"][1] == tris["crossed"][1], {t: tris[t] for t in PATTERNS})
        check("LOD2 has no frame", len({tris[t][2] for t in PATTERNS}) == 1, {t: tris[t] for t in PATTERNS})

        # at the building budget fit() drops shutters, sills, side quoins, then braces, posts, the frame
        p, rep = run("house", tmp / "fit.glb", "--region", "warriors", "--seed", 3, "--storeys", 3, "--footprint", "9x7",
                     "--no-tower", "--no-oriel", "--timber", "crossed", "--lods", 1)
        tri0 = rep.get("triangles_per_lod", [99999])[0]
        check("crossed at the building budget: LOD0 fits, framing kept as far as it fits",
              p.returncode == 0 and tri0 <= 3000 and (rep.get("economy", 9) < 4 or rep["timber_pieces"]["braces"] == 0)
              and (rep.get("economy", 9) >= 6 or rep["timber_pieces"]["rails"] > 0), (tri0, rep.get("economy"), rep.get("timber_pieces")))

        # defaults: the iamar profile frames its town houses, its Mages' quarter stays mostly plain,
        # the harbour example (Track A) has the Warriors' weights, a Track B profile without weights is plain
        picks = {}
        for label, prof, region in (("iamar civic", "iamar", "civic"), ("harbour example", HARBOUR, "harbour"),
                                    ("desert", DESERT, "caravanserai"), ("iamar mages", "iamar", "mages")):
            got = []
            for seed in range(1, 9 if quick else 13):
                p, rep = run("house", tmp / "pick.glb", "--profile", prof, "--region", region, "--seed", seed,
                             "--storeys", 2, "--lods", 1)
                got.append(rep.get("timber_frame"))
            picks[label] = got
        check("iamar civic: every town house is timber-framed by default",
              all(g not in (None, "plain") for g in picks["iamar civic"]), picks["iamar civic"])
        check("harbour example: half-timbered by default (Warriors' weights)",
              sum(g in ("studs", "braced", "crossed") for g in picks["harbour example"]) >= len(picks["harbour example"]) // 2,
              picks["harbour example"])
        check("desert (no weights): plain walls", set(picks["desert"]) == {"plain"}, picks["desert"])
        check("iamar mages: mostly plain (the city's quarter weights)",
              picks["iamar mages"].count("plain") >= len(picks["iamar mages"]) // 4, picks["iamar mages"])

        # a one-storey house has no upper storey to frame
        p, rep = run("house", tmp / "one.glb", "--storeys", 1, "--timber", "crossed", "--lods", 1)
        check("one storey: no frame", p.returncode == 0 and not sum((rep.get("timber_pieces") or {}).values()), rep.get("timber_pieces"))
        p, _ = run("house", tmp / "bad.glb", "--timber", "lattice")
        check("an unknown pattern is refused", p.returncode != 0 and "timber" in (p.stdout + p.stderr), p.stdout + p.stderr)

        if not quick:
            # every feature on (jetty, oriel, tower, arch on a stone ground storey) with each braced pattern,
            # and a plaster house whose quoins run to the eaves
            for foot, seed, region, extra in (("L", 5, "warriors", ["--door-kind", 2]), ("U", 2, "civic", []),
                                              ("rect", 3, "herbalists", []), ("T", 6, "mages", [])):
                for t in ("braced", "crossed"):
                    args = ["house", tmp / "f.glb", "--footprint", foot, "--seed", seed, "--region", region,
                            "--storeys", 3, "--jetty", "--tower", "--oriel", "--timber", t, *extra]
                    if have_np:
                        args += ["--world", tmp / ("wf_%s_%s" % (foot, t)), "--check"]
                    p, rep = run(*args)
                    check("%s seed %d %s, every feature, %s: within budget%s" % (foot, seed, region, t,
                                                                                 " and audits pass" if have_np else ""),
                          p.returncode == 0 and rep.get("triangles_per_lod", [99999])[0] <= 3000
                          and (rep.get("audit_ok") is True or not have_np), p.stdout[-600:] + p.stderr)

    ok = all(checks)
    print("%s: %d/%d checks" % ("FRAME_TEST_OK" if ok else "FRAME_TEST_FAIL", sum(checks), len(checks)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
