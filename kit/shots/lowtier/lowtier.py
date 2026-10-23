#!/usr/bin/env python3
"""Low-tier visual check: render a world at the lowest hardware tier and fail when it looks broken.

    iamar-world lowtier <world> <out> [--cameras FILE] [--times day,night] [--tier low]
                        [--no-high] [--npcs all|models|none] [--size WxH] [--json]
    python3 kit/shots/lowtier/lowtier.py ...   (same arguments)

It runs `iamar-world shots` at the low tier (default times day and night), then reads every
raw shot and checks, per shot:

    blank        the picture is (nearly) one flat colour: the scene did not draw
    magenta      more than 2% of pixels are missing-texture pink
    crushed      90% or more of the pixels are black: shadows or ambient light are broken
                 (night is exempt, it is allowed to be dark but not blank)
    blown        90% or more of the pixels are white: exposure or sun is broken
    triangles    the shot has none, or is over the world's triangle budget
    impostors    unless --no-high: the low tier draws no more triangles than the high tier
                 for the same camera and time (distant LODs and impostors are doing their job),
                 give or take 1% (--impostor-slack) for script entities that moved between runs;
                 wandering creatures worth more than that (ducks, 2000 triangles each) need
                 --npcs none, which leaves them out of both runs

Output: <out>/low/ (the shots run), <out>/high/ (the comparison run), <out>/LOWTIER.md and
<out>/lowtier.json. Exit 0 when every check passes, 1 when a shot fails or a render fails,
2 on bad input. Needs Pillow for the pixel checks (without it only the numbers are checked
and the report says so).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import shots  # noqa: E402

MAGENTA_MAX = 0.02
DARK_MAX = 0.90
BRIGHT_MAX = 0.90
FLAT_STD = 2.0
# Script entities (gulls, a sailing boat, walkers) are somewhere else in the low and high
# runs, so the two counts differ by a few hundred triangles even when the tiers load the same
# files; the impostor check allows this share before it fails (--impostor-slack).
IMPOSTOR_SLACK = 0.01


def pixel_stats(path):
    """-> dict of mean, std, magenta, dark, bright fractions, or None without Pillow."""
    try:
        from PIL import Image
    except ImportError:
        return None
    im = Image.open(path).convert("RGB")
    im.thumbnail((160, 160))
    raw = im.tobytes()
    px = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw) - 2, 3)]
    n = max(1, len(px))
    lum = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in px]
    mean = sum(lum) / n
    std = (sum((v - mean) ** 2 for v in lum) / n) ** 0.5
    return {"mean": round(mean, 1), "std": round(std, 1),
            "magenta": sum(1 for r, g, b in px if r > 200 and b > 200 and g < 80) / n,
            "dark": sum(1 for v in lum if v < 12) / n,
            "bright": sum(1 for v in lum if v > 245) / n}


def judge(shot, stats, high=None, slack=IMPOSTOR_SLACK):
    """-> list of failure names for one shot result (see the module doc)."""
    bad = []
    if not shot.get("triangles"):
        bad.append("triangles")
    elif shot.get("budget", {}).get("triangles") is not None and shot["triangles"] > shot["budget"]["triangles"]:
        bad.append("triangles")
    if stats:
        if stats["std"] < FLAT_STD:
            bad.append("blank")
        if stats["magenta"] > MAGENTA_MAX:
            bad.append("magenta")
        if shot["time"] != "night" and stats["dark"] >= DARK_MAX:
            bad.append("crushed")
        if stats["bright"] >= BRIGHT_MAX:
            bad.append("blown")
    if high is not None and shot.get("triangles", 0) > high.get("triangles", 0) * (1.0 + slack):
        bad.append("impostors")
    return bad


def run_shots(a, tier, out):
    argv = [a.world, str(out), "--tier", tier, "--times", a.times, "--size", a.size]
    if a.cameras:
        argv += ["--cameras", a.cameras]
    if a.runner:
        argv += ["--runner", a.runner]
    if a.tmp:
        argv += ["--tmp", a.tmp]
    if a.frames:
        argv += ["--frames", str(a.frames)]
    if a.npcs != "all":
        argv += ["--npcs", a.npcs]
    code = shots.main(argv)
    f = out / "shots.json"
    return code, (json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {})


def main(argv=None):
    ap = argparse.ArgumentParser(prog="iamar-world lowtier", description=__doc__.split("\n")[0])
    ap.add_argument("world")
    ap.add_argument("out")
    ap.add_argument("--cameras")
    ap.add_argument("--times", default="day,night")
    ap.add_argument("--tier", default="low", help="the tier to check (default low)")
    ap.add_argument("--no-high", action="store_true", help="skip the high-tier comparison run (no impostor check)")
    ap.add_argument("--impostor-slack", type=float, default=IMPOSTOR_SLACK,
                    help="share of the high tier's triangles the low tier may exceed it by (default 0.01: moving script entities)")
    ap.add_argument("--npcs", default="all", choices=["all", "models", "none"],
                    help="which NPCs and creatures both runs draw (default all); 'none' makes the impostor check exact when wandering creatures (ducks) differ between runs")
    ap.add_argument("--size", default="640x360")
    ap.add_argument("--frames", type=int, default=0)
    ap.add_argument("--runner", help=argparse.SUPPRESS)
    ap.add_argument("--tmp", help="folder for the per-render world copies (default TMPDIR)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not (0.0 <= a.impostor_slack <= 1.0):
        print("ERROR lowtier: --impostor-slack must be 0..1", file=sys.stderr)
        return 2
    out = Path(a.out).resolve()
    code, low = run_shots(a, a.tier, out / "low")
    if code == 2:
        return 2
    high = {}
    if not a.no_high and code == 0:
        hcode, hrep = run_shots(a, "high", out / "high")
        if hcode == 2:
            return 2
        high = {(s["camera"], s["time"]): s for s in hrep.get("shots", [])}
    rows, failed = [], 0
    have_pil = True
    for s in low.get("shots", []):
        stats = pixel_stats(s["shot"])
        have_pil = have_pil and stats is not None
        bad = judge(s, stats, high.get((s["camera"], s["time"])) if high else None, a.impostor_slack)
        failed += bool(bad)
        rows.append({"camera": s["camera"], "time": s["time"], "triangles": s["triangles"],
                     "high_triangles": high.get((s["camera"], s["time"]), {}).get("triangles"),
                     "stats": stats, "failed": bad})
    expected = len(low.get("cameras", [])) * len(low.get("times", []))
    render_fail = code != 0 or len(rows) != expected or not rows
    report = {"world": low.get("world"), "tier": a.tier, "shots": rows, "failed": failed,
              "render_ok": not render_fail, "pixel_checks": have_pil}
    out.mkdir(parents=True, exist_ok=True)
    (out / "lowtier.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    lines = ["# Low-tier check: %s (tier %s)" % (report["world"], a.tier), "",
             "| camera | time | triangles | high tier | result |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %s | %d | %s | %s |" % (r["camera"], r["time"], r["triangles"],
                     r["high_triangles"] if r["high_triangles"] is not None else "-",
                     "ok" if not r["failed"] else "FAIL " + ",".join(r["failed"])))
    if not have_pil:
        lines += ["", "Pillow is missing: only the triangle numbers were checked (pip install Pillow)."]
    (out / "LOWTIER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if a.json:
        print(json.dumps(report, indent=1))
    else:
        for r in rows:
            print("LOWTIER %-20s %-6s triangles=%d %s" % (r["camera"], r["time"], r["triangles"],
                  "ok" if not r["failed"] else "FAIL " + ",".join(r["failed"])))
        print("lowtier: %d shot(s), %d failed%s -> %s" % (len(rows), failed, ", render failed" if render_fail else "", out))
    return 1 if failed or render_fail else 0


if __name__ == "__main__":
    sys.exit(main())
