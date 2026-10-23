#!/usr/bin/env python3
"""Checks the ground-colour rule of kit/lint/compare_shots.py (harbour a5 an internal task): a day shot whose
ground is lit orange or yellow fails against the world's style profile, the same ground under white
light passes, dusk and night shots are not judged, a view of mostly water is skipped, and in a pair
only an after shot that got worse fails. Real shots: the harbour a5 review's day frames (orange
cobbles, yellow grass) fail, the city's own day shots pass.

    python3 kit/tests/lint/compare_shots_test.py

Needs numpy and Pillow; without them it reports SKIPPED.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
SHOTS = KIT / "lint" / "compare_shots.py"
HARBOUR = KIT / "blindtest" / "harbour"
PROFILE = HARBOUR / "world" / "style.json"


def run(*args):
    return subprocess.run([sys.executable, str(SHOTS), *map(str, args)], capture_output=True, text=True)


def main() -> int:
    try:
        import numpy  # noqa: F401
        from PIL import Image
    except ImportError:
        print("SKIPPED compare_shots_test: needs numpy and Pillow")
        return 0
    checks = []

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (("  " + detail.strip()[-600:]) if detail and not cond else ""), flush=True)

    cobble = (0x93, 0x8e, 0x83)   # iamar palette cobble, the harbour's terrain cobble texture mean
    meadow = (0x6b, 0x8c, 0x40)

    def shot(path, ground, light=(1.0, 1.0, 1.0), ground2=None, sky=(70, 120, 210)):
        """A 320x180 frame: sky on top, ground (two halves when ground2) in the lower 45 %, lit by light."""
        im = Image.new("RGB", (320, 180), sky)
        lit = lambda c: tuple(min(255, int(v * k)) for v, k in zip(c, light))
        im.paste(lit(ground), (0, 99, 320 if ground2 is None else 160, 180))
        if ground2 is not None:
            im.paste(lit(ground2), (160, 99, 320, 180))
        im.save(path)

    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        white, orange = (1.0, 1.0, 1.0), (1.25, 1.0, 0.62)   # orange: the #ffb064 sun's tint
        shot(t / "lane_day.png", cobble, white, meadow)
        shot(t / "lane_orange_day.png", cobble, orange, meadow)
        shot(t / "lane_orange_dusk.png", cobble, orange, meadow)
        shot(t / "meadow_yellow_day.png", meadow, (1.35, 1.2, 0.7))
        shot(t / "quay_water_day.png", (40, 90, 150), orange)
        shot(t / "lane_shade_day.png", cobble, (0.5, 0.5, 0.5), meadow)

        def single(name):
            return run(t / name, "--style", PROFILE)

        r = single("lane_day.png")
        check("ground: grey cobbles and green grass under white light pass", r.returncode == 0 and "ground 0.0" in r.stdout, r.stdout)
        r = single("lane_shade_day.png")
        check("ground: the same ground in shade passes", r.returncode == 0, r.stdout)
        r = single("lane_orange_day.png")
        check("ground: orange-lit cobbles fail with the warm-light message",
              r.returncode == 1 and "day ground colour" in r.stdout and "warm day light" in r.stdout, r.stdout)
        r = single("meadow_yellow_day.png")
        check("ground: yellow-lit grass fails", r.returncode == 1 and "day ground colour" in r.stdout, r.stdout)
        r = single("lane_orange_dusk.png")
        check("ground: a dusk shot is not judged", r.returncode == 0 and "ground -" in r.stdout, r.stdout)
        r = run(t / "lane_orange_dusk.png", "--style", PROFILE, "--ground-times", "all")
        check("ground: --ground-times all judges it", r.returncode == 1, r.stdout)
        r = single("quay_water_day.png")
        check("ground: a view of mostly water is skipped", r.returncode == 0 and "ground -" in r.stdout, r.stdout)
        # profile driven: a desert profile's sand is its ground; the harbour's is cobble and grass
        sand = (0xd8, 0xb2, 0x7a)
        (t / "desert.json").write_text('{"schema": "iamar-style/1", "id": "desert_test", "palette": '
                                       '{"dune_sand": {"hex": "#d8b27a"}, "packed_path": {"hex": "#a08868"}}}',
                                       encoding="utf-8")
        shot(t / "dunes_day.png", sand, white)
        r = run(t / "dunes_day.png", "--style", t / "desert.json")
        check("ground: sand under white light passes a desert profile", r.returncode == 0 and "ground 0.0" in r.stdout, r.stdout)
        r = run(t / "dunes_day.png", "--style", PROFILE)
        check("ground: the same sand fails the harbour profile (not its ground)", r.returncode == 1, r.stdout)

        # pairs: only an after shot that got worse fails
        (t / "a").mkdir()
        (t / "b").mkdir()
        shot(t / "a" / "lane_day.png", cobble, white, meadow)
        shot(t / "b" / "lane_day.png", cobble, orange, meadow)
        r = run(t / "a", t / "b", "--style", PROFILE)
        check("pair: white -> orange day light fails", r.returncode == 1 and "day ground colour" in r.stdout, r.stdout)
        r = run(t / "b", t / "a", "--style", PROFILE)
        check("pair: orange -> white passes (the fix)", r.returncode == 0 and "ground " in r.stdout and "-> 0.0" in r.stdout, r.stdout)
        shot(t / "a" / "lane_day.png", cobble, orange, meadow)
        r = run(t / "b", t / "a", "--style", PROFILE)
        check("pair: orange before and after is a WARN, not an ERROR",
              r.returncode == 0 and "WARN" in r.stdout and "no worse than before" in r.stdout, r.stdout)

        # real shots: harbour a5 review day frames (an internal task) against the city's own
        sheet = HARBOUR / "review-a5" / "sheets" / "m_02_square_terrace_tavern.jpg"
        city = HARBOUR / "shots" / "city_warriors.jpg"
        if sheet.is_file() and city.is_file():
            (t / "real").mkdir()
            im = Image.open(sheet)
            w, h = im.size
            im.crop((0, 0, w // 3, h // 3)).save(t / "real" / "a5_square_day.png")
            im.crop((w // 3, 0, 2 * w // 3, h // 3)).save(t / "real" / "a5_square_dusk.png")
            Image.open(city).save(t / "real" / "city_warriors_day.png")
            r = run(t / "real", "--style", PROFILE)
            check("real: harbour a5 day square fails, its dusk and the city's day pass",
                  r.returncode == 1 and "FAIL  a5_square_day.png" in r.stdout and "OK    a5_square_dusk.png" in r.stdout
                  and "OK    city_warriors_day.png" in r.stdout, r.stdout)
        else:
            print("SKIPPED real shots (harbour a5 review sheets not in this kit)")

    ok = all(checks)
    print("%s compare_shots_test: %d/%d" % ("OK" if ok else "FAIL", sum(checks), len(checks)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
