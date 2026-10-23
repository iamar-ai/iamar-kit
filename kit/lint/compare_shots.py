#!/usr/bin/env python3
"""Same-camera screenshot comparison, judged against a style profile.

    iamar-world compare-shots BEFORE AFTER [--style PROFILE] [--out DIR] [--json]
    iamar-world compare-shots SHOTS [--style PROFILE] [--json]     (one shot or folder: per-shot checks)
    python3 kit/lint/compare_shots.py   (same arguments; iamar-world compare-shots runs this)

BEFORE and AFTER are two PNG/JPEG shots from the same camera, or two folders of shots:
files with the same name are paired (the camera names `iamar-world shots` and
`iamar-world view --view` write). For every pair it reports

  camera      the two shots really are the same view: same aspect ratio and correlated
              edges (an edge correlation under --min-edge-corr means the camera moved,
              so the comparison would be meaningless: ERROR)
  change      mean colour difference (CIE76) and the share of pixels that changed visibly
              (delta E > 10); --max-change fails a pair that changed more than allowed
  on-palette  share of pixels within lint.shot_palette_delta_e (default 8) of a profile colour (its
              palette, regions, material tints, sky and fog colours, each weathered and at
              several light levels): a drop of more than lint.shot_palette_drop is an ERROR
  black/pink  share of pure-black and missing-texture-pink pixels: new pink is an ERROR,
              black growing by more than lint.shot_black_rise is an ERROR
  ground      day shots only (file name ends in _day, as `iamar-world shots` names them;
              --ground-times): the mean colour of the lower 40 % of the frame (blue water and sky
              left out) must lie among the profile's ground colours (palette entries named or
              patterned cobble, path, grass, meadow, sand ...; the ground_stone of the profile's
              own regions; lint.shot_ground_colours) mixed in any share and lit by white light.
              A warm day light moves it off them: the orange cobbles and yellow grass of harbour
              a5 (an internal task) are 10-25 delta E away, the city and the lighting presets 0-6. Further
              than lint.shot_ground_cast (default 9) is an ERROR; in a pair only when the after
              shot is also worse than the before shot, else a WARN

With only one argument (a shot or a folder) it runs the per-shot checks (pink, ground) alone,
and, with --out, writes <name>_compare.png per pair: before | after | change heat map.
Exit 1 on any ERROR. Needs numpy and Pillow.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

LINT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(LINT_DIR))
sys.path.insert(0, str(LINT_DIR.parent / "style"))
import check_style  # noqa: E402
import style_lint  # noqa: E402

SHOT_LINT = {"shot_palette_delta_e": 8.0, "shot_palette_drop": 0.10, "shot_black_rise": 0.10,
             "shot_ground_cast": 9.0}
GROUND_WORDS = ("cobble", "flag", "pav", "path", "street", "road", "ground", "grass", "meadow", "lawn",
                "moss", "sand", "dirt", "soil", "earth", "gravel", "dune", "turf", "mud")
GROUND_BAND = 0.4        # lower share of the frame read as ground
GROUND_MIN_SHARE = 0.25  # of that band, once blue (water, sky) and black pixels are left out
WIDTH = 320


def need():
    try:
        import numpy as np
        from PIL import Image
        return np, Image
    except ImportError as e:
        print("ERROR compare-shots needs numpy and Pillow (%s)" % e)
        sys.exit(2)


def to_lab(np, rgb):
    """rgb: (..., 3) sRGB 0-1 -> Lab (D65)."""
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def shot_colours(np, prof):
    """Profile colours a screenshot may legitimately show: the lint's set, the atmosphere's sky,
    fog, sun and ambient colours, each also at 0.45, 0.7 and 1.2 x brightness (shade and sun)."""
    cols = list(style_lint.profile_colours(prof).values())
    for preset in ((prof.get("atmosphere") or {}).get("presets") or {}).values():
        env = preset.get("environment", {}) if isinstance(preset, dict) else {}
        for sec, keys in (("sky", ("top_color", "horizon_color", "ground_color", "color")), ("fog", ("color",)),
                          ("sun", ("color",)), ("ambient", ("color",))):
            for k in keys:
                h = (env.get(sec) or {}).get(k)
                if isinstance(h, str) and len(h) >= 7 and h.startswith("#"):
                    cols.append(style_lint.hex_rgb(h[:7]))
    base = np.array(cols, dtype=np.float64).reshape(-1, 3)
    if not len(base):
        return None
    lit = np.concatenate([np.clip(base * k, 0, 1) for k in (0.45, 0.7, 1.0, 1.2)])
    return to_lab(np, lit)


def ground_colours(prof, parent=None) -> dict:
    """name -> sRGB of every colour the profile paints its ground with: palette entries named or
    patterned after ground (cobble, path, grass, meadow, sand ...), the ground_stone of the
    profile's own regions (a profile that extends iamar is judged by its own regions, not by every
    quarter of the parent) and lint.shot_ground_colours."""
    out = {}
    for n, sw in (prof.get("palette") or {}).items():
        if isinstance(sw, dict) and not sw.get("glow") and isinstance(sw.get("hex"), str) \
                and any(w in ("%s %s" % (n, sw.get("pattern", ""))).lower() for w in GROUND_WORDS):
            out["palette.%s" % n] = style_lint.hex_rgb(sw["hex"][:7])
    regions = prof.get("regions") or {}
    inherited = set((parent or {}).get("regions") or {})
    for r in [r for r in regions if r not in inherited] or list(regions):
        h = regions[r].get("ground_stone") if isinstance(regions[r], dict) else None
        if isinstance(h, str) and len(h) >= 7:
            out["regions.%s.ground_stone" % r] = style_lint.hex_rgb(h[:7])
    for i, h in enumerate((prof.get("lint") or {}).get("shot_ground_colours") or []):
        if isinstance(h, str) and len(h) >= 7:
            out["lint.shot_ground_colours[%d]" % i] = style_lint.hex_rgb(h[:7])
    return out


def hull2d(pts):
    """Convex hull (counter-clockwise) of 2-D points."""
    p = sorted(set((round(float(x), 4), round(float(y), 4)) for x, y in pts))
    if len(p) < 3:
        return p
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for q in p:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0:
            lo.pop()
        lo.append(q)
    for q in reversed(p):
        while len(up) >= 2 and cross(up[-2], up[-1], q) <= 0:
            up.pop()
        up.append(q)
    return lo[:-1] + up[:-1]


def ground_hull(np, cols: dict):
    """The (a*, b*) area every mix of the ground colours fills under white light from shade to sun
    (0.45-1.2 x, as shot_colours; black included): white light keeps a mix inside, coloured moves it out."""
    if not cols:
        return None
    base = np.array(list(cols.values()), dtype=np.float64).reshape(-1, 3)
    lit = np.concatenate([np.clip(base * k, 0, 1) for k in (0.45, 0.7, 1.0, 1.2)] + [np.zeros((1, 3))])
    return hull2d(to_lab(np, lit)[:, 1:])


def hull_distance(h, x: float, y: float) -> float:
    """Distance from (x, y) to the convex polygon h (0 inside)."""
    if len(h) == 1:
        return ((x - h[0][0]) ** 2 + (y - h[0][1]) ** 2) ** 0.5
    inside, best = len(h) >= 3, float("inf")
    for i in range(len(h)):
        (ax, ay), (bx, by) = h[i], h[(i + 1) % len(h)]
        ex, ey, wx, wy = bx - ax, by - ay, x - ax, y - ay
        if ex * wy - ey * wx < 0:
            inside = False
        t = max(0.0, min(1.0, (wx * ex + wy * ey) / max(ex * ex + ey * ey, 1e-12)))
        best = min(best, ((wx - t * ex) ** 2 + (wy - t * ey) ** 2) ** 0.5)
    return 0.0 if inside else best


def ground_cast(np, lab, hull):
    """Mean ground colour of a shot's lower band -> {off, hue, chroma, share} (off: delta E in a*b*
    from the ground colours' hull), or None when the band is mostly water, sky or black."""
    band = lab[int(lab.shape[0] * (1 - GROUND_BAND)):].reshape(-1, 3)
    keep = (band[:, 2] >= -4.0) & (band[:, 0] >= 8.0)
    share = float(keep.mean()) if len(keep) else 0.0
    if hull is None or share < GROUND_MIN_SHARE:
        return None
    m = band[keep].mean(axis=0)
    return {"off": round(hull_distance(hull, float(m[1]), float(m[2])), 1),
            "hue": round(float(np.degrees(np.arctan2(m[2], m[1]))), 1),
            "chroma": round(float(np.hypot(m[1], m[2])), 1), "share": round(share, 2)}


def judged_time(path: Path, times) -> bool:
    return "all" in times or any(path.stem.lower().endswith("_" + t) for t in times)


def ground_message(g, lim) -> str:
    return ("day ground colour %.1f delta E off the profile's ground colours (> %.0f; mean hue %.0f deg, "
            "chroma %.0f): a %s day light; keep a moving sun near white (lighting.py check, preset day; "
            "harbour a5 an internal task)" % (g["off"], lim, g["hue"], g["chroma"], "warm" if 20 <= g["hue"] <= 95 else "tinted"))


def ground_text(g) -> str:
    return "-" if not g else "%.1f" % g["off"]


def load(np, Image, path: Path, size=None):
    im = Image.open(path).convert("RGB")
    if size is None:
        size = (WIDTH, max(1, round(WIDTH * im.height / im.width)))
    return np.asarray(im.resize(size, Image.BILINEAR), dtype=np.float64) / 255.0, im.size


def stats(np, rgb, lab, pal_lab, tol):
    flat = rgb.reshape(-1, 3)
    black = float((flat.max(axis=1) < 0.03).mean())
    pink = float(((flat[:, 0] > 0.9) & (flat[:, 2] > 0.9) & (flat[:, 1] < 0.15)).mean())
    on = None
    if pal_lab is not None:
        L = lab.reshape(-1, 3)
        best = np.full(len(L), np.inf)
        for chunk in np.array_split(pal_lab, max(1, len(pal_lab) // 256)):
            d = np.sqrt(((L[:, None, 0] - chunk[None, :, 0]) / 2.0) ** 2 + (L[:, None, 1] - chunk[None, :, 1]) ** 2
                        + (L[:, None, 2] - chunk[None, :, 2]) ** 2)
            best = np.minimum(best, d.min(axis=1))
        on = float((best <= tol).mean())
    return {"black": black, "pink": pink, "on_palette": on}


def edges(np, rgb):
    g = rgb.mean(axis=2)
    gx = np.abs(np.diff(g, axis=1))[:-1, :]
    gy = np.abs(np.diff(g, axis=0))[:, :-1]
    return gx + gy


def compare(np, Image, a: Path, b: Path, prof, args, out_dir):
    lint = {**style_lint.DEFAULT_LINT, **SHOT_LINT, **(prof.get("lint") or {})}
    res = {"before": str(a), "after": str(b), "errors": [], "warnings": []}
    ra, sa = load(np, Image, a)
    with Image.open(b) as im_b:
        sb = im_b.size
    if abs(sa[0] / sa[1] - sb[0] / sb[1]) > 0.01:
        res["errors"].append("aspect ratio differs (%dx%d vs %dx%d): not the same camera" % (*sa, *sb))
        return res
    if sa != sb:
        res["warnings"].append("sizes differ (%dx%d vs %dx%d): compared at %d px wide" % (*sa, *sb, WIDTH))
    rb, _ = load(np, Image, b, (ra.shape[1], ra.shape[0]))
    ea, eb = edges(np, ra).ravel(), edges(np, rb).ravel()
    corr = float(np.corrcoef(ea, eb)[0, 1]) if ea.std() > 1e-6 and eb.std() > 1e-6 else 1.0
    res["edge_corr"] = round(corr, 3)
    if corr < args.min_edge_corr:
        res["errors"].append("edge correlation %.2f < %.2f: the camera moved, shots are not comparable" % (corr, args.min_edge_corr))
    la, lb = to_lab(np, ra), to_lab(np, rb)
    de = np.sqrt(((la - lb) ** 2).sum(axis=2))
    res["mean_delta_e"] = round(float(de.mean()), 2)
    res["changed_share"] = round(float((de > 10).mean()), 4)
    if args.max_change is not None and res["changed_share"] > args.max_change:
        res["errors"].append("%.0f %% of pixels changed (> --max-change %.0f %%)" % (res["changed_share"] * 100, args.max_change * 100))
    pal = shot_colours(np, prof)
    tol = float(lint["shot_palette_delta_e"])
    sa_, sb_ = stats(np, ra, la, pal, tol), stats(np, rb, lb, pal, tol)
    res["before_stats"], res["after_stats"] = sa_, sb_
    if sb_["pink"] > max(lint["pink_texture_share"], sa_["pink"] + 0.001):
        res["errors"].append("missing-texture pink on %.1f %% of the after shot" % (sb_["pink"] * 100))
    if sb_["black"] - sa_["black"] > lint["shot_black_rise"]:
        res["errors"].append("black pixels rose from %.0f %% to %.0f %%" % (sa_["black"] * 100, sb_["black"] * 100))
    if args.ground_hull is not None and judged_time(b, args.ground_times):
        ga, gb = ground_cast(np, la, args.ground_hull), ground_cast(np, lb, args.ground_hull)
        sa_["ground"], sb_["ground"] = ga, gb
        lim = float(lint["shot_ground_cast"])
        if gb and gb["off"] > lim:
            if ga is None or gb["off"] > ga["off"] + 1.0:
                res["errors"].append(ground_message(gb, lim) + ("" if ga is None else " (before %.1f)" % ga["off"]))
            else:
                res["warnings"].append(ground_message(gb, lim) + "; no worse than before (%.1f)" % ga["off"])
    if sa_["on_palette"] is not None and sa_["on_palette"] - sb_["on_palette"] > lint["shot_palette_drop"]:
        res["errors"].append("on-palette share fell from %.0f %% to %.0f %% (%s profile; max drop %.0f %%)"
                             % (sa_["on_palette"] * 100, sb_["on_palette"] * 100, prof.get("id"), lint["shot_palette_drop"] * 100))
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        heat = np.clip(de / 30.0, 0, 1)
        hm = np.stack([heat, heat * 0.35, 1 - heat], axis=-1) * 0.6 + rb.mean(axis=2, keepdims=True) * 0.4
        sheet = np.concatenate([ra, rb, hm], axis=1)
        p = out_dir / ("%s_compare.png" % b.stem)
        Image.fromarray((sheet * 255).astype("uint8")).save(p)
        res["sheet"] = str(p)
    return res


def single(np, Image, path: Path, prof, args):
    """Per-shot checks of one shot (no before): missing-texture pink and, for day shots, the ground colour."""
    lint = {**style_lint.DEFAULT_LINT, **SHOT_LINT, **(prof.get("lint") or {})}
    res = {"shot": str(path), "errors": [], "warnings": []}
    rgb, _ = load(np, Image, path)
    lab = to_lab(np, rgb)
    st = stats(np, rgb, lab, None, 0)
    res["stats"] = st
    if st["pink"] > lint["pink_texture_share"]:
        res["errors"].append("missing-texture pink on %.1f %% of the shot" % (st["pink"] * 100))
    if args.ground_hull is not None and judged_time(path, args.ground_times):
        g = ground_cast(np, lab, args.ground_hull)
        st["ground"] = g
        if g and g["off"] > float(lint["shot_ground_cast"]):
            res["errors"].append(ground_message(g, float(lint["shot_ground_cast"])))
    return res


def shot_files(p: Path):
    exts = {".png", ".jpg", ".jpeg"}
    return sorted(q for q in p.iterdir() if q.suffix.lower() in exts) if p.is_dir() else [p]


def pairs(a: Path, b: Path):
    if a.is_dir() and b.is_dir():
        exts = {".png", ".jpg", ".jpeg"}
        names = sorted(p.name for p in a.iterdir() if p.suffix.lower() in exts)
        out = [(a / n, b / n) for n in names if (b / n).is_file()]
        missing = [n for n in names if not (b / n).is_file()]
        return out, missing
    return [(a, b)], []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("before")
    ap.add_argument("after", nargs="?", help="omit to run only the per-shot checks on BEFORE")
    ap.add_argument("--style", default="iamar", help="profile id or style.json (default iamar)")
    ap.add_argument("--out", help="folder for before | after | heat-map sheets")
    ap.add_argument("--max-change", type=float, help="fail a pair whose changed-pixel share exceeds this (0-1)")
    ap.add_argument("--min-edge-corr", type=float, default=0.5, help="same-camera test (default 0.5)")
    ap.add_argument("--ground-times", default="day",
                    help="time suffixes whose ground colour is judged (default day; 'all' judges every shot)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    np, Image = need()
    try:
        prof, parent = check_style.load(a.style)
    except (OSError, ValueError) as e:
        print("ERROR cannot load style profile %s: %s" % (a.style, e))
        return 2
    a.ground_times = [t.strip().lower() for t in a.ground_times.split(",") if t.strip()]
    a.ground_hull = ground_hull(np, ground_colours(prof, parent))
    if a.after is None:
        files = shot_files(Path(a.before))
        if not files:
            print("ERROR no shots in %s" % a.before)
            return 2
        results = [single(np, Image, f, prof, a) for f in files]
        bad = sum(bool(r["errors"]) for r in results)
        if a.json:
            print(json.dumps({"profile": prof.get("id"), "ok": not bad, "shots": results}, indent=1))
        else:
            for r in results:
                print("%-5s %s: ground %s" % ("FAIL" if r["errors"] else "OK", Path(r["shot"]).name,
                                              ground_text(r["stats"].get("ground"))))
                for e in r["errors"]:
                    print("ERROR   " + e)
            print("%s compare-shots (%s): %d shot(s), %d failed" % ("FAIL" if bad else "OK", prof.get("id"), len(results), bad))
        return 1 if bad else 0
    ps, missing = pairs(Path(a.before), Path(a.after))
    if not ps:
        print("ERROR no shot pairs (same file names in both folders)")
        return 2
    results = [compare(np, Image, x, y, prof, a, Path(a.out) if a.out else None) for x, y in ps]
    bad = sum(bool(r["errors"]) for r in results)
    if a.json:
        print(json.dumps({"profile": prof.get("id"), "ok": not bad, "missing_after": missing, "pairs": results}, indent=1))
    else:
        for n in missing:
            print("WARN  %s: no shot of the same name in %s" % (n, a.after))
        for r in results:
            s0, s1 = r.get("before_stats") or {}, r.get("after_stats") or {}
            onp = lambda s: "-" if s.get("on_palette") is None else "%.0f%%" % (s["on_palette"] * 100)
            gnd = "" if "ground" not in s1 else ", ground %s -> %s" % (ground_text(s0.get("ground")), ground_text(s1.get("ground")))
            print("%-5s %s: edge-corr %s, mean dE %s, changed %s, on-palette %s -> %s, black %s -> %s%s%s"
                  % ("FAIL" if r["errors"] else "OK", Path(r["after"]).name, r.get("edge_corr", "-"), r.get("mean_delta_e", "-"),
                     "%.0f%%" % (r["changed_share"] * 100) if "changed_share" in r else "-", onp(s0), onp(s1),
                     "%.0f%%" % (s0.get("black", 0) * 100), "%.0f%%" % (s1.get("black", 0) * 100), gnd,
                     ("  " + r["sheet"]) if r.get("sheet") else ""))
            for e in r["errors"]:
                print("ERROR   " + e)
            for w in r["warnings"]:
                print("WARN    " + w)
        print("%s compare-shots (%s): %d pair(s), %d failed" % ("FAIL" if bad else "OK", prof.get("id"), len(results), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
