#!/usr/bin/env python3
"""Clean a busy concept down to the free-standing figure (GPU tier, before the views; CPU only).

    python kit/gpu/stages/clean_concept.py concept.png out/x [--poly "x,y;x,y;..."]
        [--grabcut [--bg "poly|poly"] [--fg "poly|poly"]] [--cut-y ROW] [--margin 0.08]

For concepts where the plain cut-out (stages/cutout.py) fails: a figure drawn in front of
architecture, frames, medallions or effects. rembg cuts first; --poly (the figure's outline
in picture pixels) drops everything outside it; --grabcut refines inside the outline with
OpenCV GrabCut (rembg's sure pixels as foreground), with --bg polygons pinned as background
(the arch seen between a wing and the body) and --fg polygons pinned as figure. The city's
lesson (an internal task): rembg drops pale wings in front of pale marble pillars; draw the polygons
on a 64 px grid over the concept and check the hands are not inside a --bg one. --cut-y
drops every row from there down (the drawn plinth). The result is cropped square round the
figure with --margin on each side.

Writes P_clean.png (RGBA, alpha = the figure: the input of mv_views.py or sculpt.py shape)
and P_clean_grey.jpg (512 px on grey, to look at). Prints CLEAN_OK.
Needs numpy, Pillow, opencv-python and rembg.
Packaged from the iamar-models mesh archive (not public) tools/mesh3d/clean_concept.py (iamar city, an internal task).
"""
import argparse
import sys


def polys(spec, size):
    """A boolean mask of the polygons in `spec` ('x,y;x,y;...|x,y;...')."""
    import numpy as np
    from PIL import Image, ImageDraw
    pm = Image.new("L", size, 0)
    for one in spec.split("|"):
        pts = [tuple(float(v) for v in p.split(",")) for p in one.split(";") if p.strip()]
        if len(pts) < 3:
            raise ValueError("polygon %r: at least 3 points x,y;x,y;x,y" % one)
        ImageDraw.Draw(pm).polygon(pts, fill=255)
    return np.asarray(pm) > 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("image")
    ap.add_argument("out", help="output prefix")
    ap.add_argument("--poly", default="", help="outline of the figure, x,y;x,y;... (picture pixels)")
    ap.add_argument("--cut-y", type=int, default=0, help="drop every row from here down (the plinth)")
    ap.add_argument("--grabcut", action="store_true", help="refine with GrabCut inside the outline")
    ap.add_argument("--bg", default="", help="GrabCut: sure background inside the outline, polygons split by |")
    ap.add_argument("--fg", default="", help="GrabCut: sure figure, polygons split by |")
    ap.add_argument("--margin", type=float, default=0.08)
    ap.add_argument("--alpha", default="", help="use this mask (white = figure) instead of rembg")
    a = ap.parse_args(argv)
    if a.grabcut and not a.poly:
        ap.error("--grabcut needs --poly (the outline it refines inside)")
    if not 0 <= a.margin <= 0.5:
        ap.error("--margin must be in [0, 0.5]")
    import cv2
    import numpy as np
    from PIL import Image
    im = Image.open(a.image).convert("RGB")
    W, H = im.size
    if a.alpha:
        al = np.asarray(Image.open(a.alpha).convert("L").resize(im.size)).astype(np.uint8)
    else:
        from rembg import new_session, remove
        al = np.asarray(remove(im, session=new_session()).getchannel("A")).astype(np.uint8)
    try:
        poly = polys(a.poly, im.size) if a.poly else None
        bgp = polys(a.bg, im.size) if a.bg else None
        fgp = polys(a.fg, im.size) if a.fg else None
    except ValueError as e:
        ap.error(str(e))
    if a.grabcut:
        mask = np.full((H, W), cv2.GC_BGD, np.uint8)
        mask[poly] = cv2.GC_PR_FGD
        inner = cv2.erode((poly & (al > 220)).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        mask[inner] = cv2.GC_FGD
        if bgp is not None:
            mask[bgp] = cv2.GC_BGD
        if fgp is not None:
            mask[fgp] = cv2.GC_FGD
        bgm, fgm = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR), mask, None, bgm, fgm, 8, cv2.GC_INIT_WITH_MASK)
        keep = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
        # the largest piece plus anything big, holes under 0.2 % filled, a soft 1 px edge
        n, lab, st, _ = cv2.connectedComponentsWithStats(keep, 8)
        big = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 0.004 * keep.sum()]
        keep = np.isin(lab, big).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(1 - keep, 8)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] < 0.002 * H * W and st[i, cv2.CC_STAT_LEFT] > 0 and st[i, cv2.CC_STAT_TOP] > 0:
                keep[lab == i] = 1
        al = cv2.GaussianBlur((keep * 255).astype(np.uint8), (3, 3), 0)
    elif poly is not None:
        al = (al * poly).astype(np.uint8)
    if a.cut_y:
        al = al.copy()
        al[a.cut_y:] = 0
    ys, xs = np.nonzero(al > 16)
    if len(xs) == 0:
        print("CLEAN_FAIL nothing of the figure left (check --poly, --cut-y)", file=sys.stderr)
        return 1
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    side = max(1, int(max(x1 - x0, y1 - y0) * (1 + 2 * a.margin)))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    rgba = np.dstack([np.asarray(im), al])
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(Image.fromarray(rgba, "RGBA"), (side // 2 - int(cx), side // 2 - int(cy)))
    out.save(a.out + "_clean.png")
    g = Image.new("RGB", out.size, (128, 128, 128))
    g.paste(out, mask=out.getchannel("A"))
    g.resize((512, 512)).save(a.out + "_clean_grey.jpg", quality=88)
    print("CLEAN_OK %s_clean.png box %d,%d,%d,%d side %d" % (a.out, x0, y0, x1, y1, side))
    return 0


if __name__ == "__main__":
    sys.exit(main())
