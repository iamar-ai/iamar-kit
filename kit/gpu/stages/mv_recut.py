#!/usr/bin/env python3
"""Better cut-outs of generated views for pale figures (GPU tier, multiview; CPU only).

    python kit/gpu/stages/mv_recut.py out/views/x clean_rgba.png [--az 0 90 180 270]
        [--thr 9] [--flat 1.2] [--no-rembg]

rembg alone drops pale parts in front of pale backgrounds (the city's stone dragonbinder
lost both wings in the az 0 view). MV-Adapter paints every view on a flat 0.5 grey, so:
  az 0    takes the alpha of the clean cut-out itself (the picture you gave mv_views.py),
          framed exactly as MV-Adapter's preprocess_image frames it (bounding box, longest
          side 0.9 of the view, centred)
  others  rembg OR "differs from the flat grey" (blurred colour distance over --thr),
          closed, specks under 0.3 % dropped, holes under 0.15 % of the view filled (the
          gaps between a wing and the body stay open), and flat painted panels (local
          brightness spread under --flat over a large area) removed
Rewrites P_az<deg>_rgba.png for the views prefix P and keeps rembg's original as
P_az<deg>_rgba_rembg.png. --no-rembg uses the colour distance alone (no rembg install).
Prints RECUT_OK and one line per view with the share of the view kept.
Needs numpy, Pillow and opencv-python (and rembg unless --no-rembg).
Packaged from the iamar-models mesh archive (not public) tools/mesh3d/mv_recut.py (iamar city, an internal task).
"""
import argparse
import os
import sys


def framed_alpha(clean_alpha, S, np, Image):
    """The clean cut-out's alpha placed as MV-Adapter's preprocess_image places the picture."""
    ys, xs = np.where(clean_alpha > 0)
    H, W = clean_alpha.shape
    y0, y1 = max(ys.min() - 1, 0), min(ys.max() + 1, H)
    x0, x1 = max(xs.min() - 1, 0), min(xs.max() + 1, W)
    c = clean_alpha[y0:y1, x0:x1]
    h, w = c.shape
    if h > w:
        w, h = int(w * (S * 0.9) / h), int(S * 0.9)
    else:
        h, w = int(h * (S * 0.9) / w), int(S * 0.9)
    c = np.asarray(Image.fromarray(c).resize((max(w, 1), max(h, 1))))
    out = np.zeros((S, S), np.uint8)
    out[(S - h) // 2:(S - h) // 2 + h, (S - w) // 2:(S - w) // 2 + w] = c
    return out


def grey_alpha(rgb, thr, np, cv2):
    f = cv2.GaussianBlur(rgb.astype(np.float32), (5, 5), 0)
    rim = np.concatenate([f[:6].reshape(-1, 3), f[-6:].reshape(-1, 3), f[:, :6].reshape(-1, 3), f[:, -6:].reshape(-1, 3)])
    bg = np.median(rim, axis=0)
    m = (np.linalg.norm(f - bg, axis=2) > thr).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prefix", help="the views prefix given to mv_views.py")
    ap.add_argument("clean", help="the clean RGBA cut-out the views were made from")
    ap.add_argument("--az", type=int, nargs="+", default=[0, 90, 180, 270])
    ap.add_argument("--thr", type=float, default=9.0, help="colour distance from the grey that counts as subject")
    ap.add_argument("--flat", type=float, default=1.2, help="local brightness spread below this is a flat panel")
    ap.add_argument("--no-rembg", action="store_true", help="colour distance only")
    a = ap.parse_args(argv)
    import cv2
    import numpy as np
    from PIL import Image
    sess = remove = None
    if not a.no_rembg:
        from rembg import new_session, remove
        sess = new_session()
    clean = np.asarray(Image.open(a.clean).convert("RGBA").getchannel("A"))
    if not (clean > 0).any():
        print("RECUT_FAIL %s has no opaque pixels" % a.clean, file=sys.stderr)
        return 1
    for az in a.az:
        p = "%s_az%03d" % (a.prefix, az)
        if not os.path.isfile(p + ".png"):
            print("RECUT_FAIL missing view %s.png (mv_views.py writes it)" % p, file=sys.stderr)
            return 1
        rgb = np.asarray(Image.open(p + ".png").convert("RGB"))
        S = rgb.shape[0]
        if os.path.exists(p + "_rgba.png") and not os.path.exists(p + "_rgba_rembg.png"):
            os.replace(p + "_rgba.png", p + "_rgba_rembg.png")
        if az == 0:
            al = framed_alpha(clean, S, np, Image)
        else:
            keep = grey_alpha(rgb, a.thr, np, cv2)
            if remove is not None:
                keep = keep | (np.asarray(remove(Image.fromarray(rgb), session=sess).getchannel("A")) > 127)
            keep = keep.astype(np.uint8)
            n, lab, st, _ = cv2.connectedComponentsWithStats(keep, 8)
            big = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 0.003 * keep.sum()]
            keep = np.isin(lab, big).astype(np.uint8)
            n, lab, st, _ = cv2.connectedComponentsWithStats(1 - keep, 4)
            for i in range(1, n):
                if st[i, cv2.CC_STAT_AREA] < 0.0015 * S * S:
                    keep[lab == i] = 1
            lum = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
            mu = cv2.blur(lum, (15, 15))
            sd = np.sqrt(np.maximum(cv2.blur(lum * lum, (15, 15)) - mu * mu, 0))
            flat = cv2.morphologyEx((sd < a.flat).astype(np.uint8), cv2.MORPH_OPEN, np.ones((15, 15), np.uint8))
            n, lab, st, _ = cv2.connectedComponentsWithStats(flat, 8)
            for i in range(1, n):
                if st[i, cv2.CC_STAT_AREA] > 0.004 * S * S:
                    keep[lab == i] = 0
            al = cv2.GaussianBlur(keep * 255, (3, 3), 0)
        Image.fromarray(np.dstack([rgb, al]), "RGBA").save(p + "_rgba.png")
        print("recut %s kept %.3f" % (p, float((al > 127).mean())), flush=True)
    print("RECUT_OK %s %d views" % (a.prefix, len(a.az)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
