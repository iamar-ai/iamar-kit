"""Blend the albedo across UV seams so the two charts that meet at an edge show the same colour there.
Usage: seam_blend.py <low_low.glb> <albedo.png> [radius_px]
Each chart is baked on its own, so where two charts meet on the mesh (face chart / hair chart on the sorceress' forehead, 2026-10-20)
their border texels can differ (qa_statue.py check 1: 'face texture seams'). For every seam edge (welded positions, different UVs)
the colour of both sides is sampled every texel along the edge; each side is pulled to the mean of the two, and the correction
fades out over radius_px (default 6) texels INSIDE the same chart only (a chart-id raster keeps it out of neighbouring charts)."""
import sys, numpy as np, trimesh
from PIL import Image, ImageDraw
from scipy import ndimage
import scipy.sparse as sp
low, alb_p = sys.argv[1], sys.argv[2]
R = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0
sc = trimesh.load(low)
alb = np.asarray(Image.open(alb_p).convert("RGB")).astype(np.float64)
H, W = alb.shape[:2]
acc = np.zeros((H, W, 3)); wsum = np.zeros((H, W)); wmax = np.zeros((H, W))
lab_img = Image.new("I", (W, H), 0); dr = ImageDraw.Draw(lab_img)
geos = []
nlab = 0
for g in sc.geometry.values():
    V, F, UV = g.vertices, g.faces, g.visual.uv
    # charts = triangles connected through shared UV vertices (same vertex index = same UV)
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    t = np.tile(np.arange(len(F)), 3)
    m = sp.coo_matrix((np.ones(len(e)), (t, e[:, 0])), shape=(len(F), len(V))).tocsr()
    ft = (m @ m.T).tocoo()
    _, lab = sp.csgraph.connected_components(sp.coo_matrix((np.ones(len(ft.row)), (ft.row, ft.col)), shape=(len(F), len(F))), directed=False)
    lab = lab + nlab + 1; nlab = lab.max()
    px = np.stack([UV[:, 0] * W, (1 - UV[:, 1]) * H], 1)
    for fi, f in enumerate(F):
        dr.polygon([tuple(px[i]) for i in f], fill=int(lab[fi]))
    geos.append((V, F, UV, lab))
lab_img = np.asarray(lab_img).astype(np.int64)
# grow each chart's label 3 px into the background (bake margin) so border texels belong to their chart
grow = ndimage.distance_transform_edt(lab_img == 0, return_distances=True, return_indices=True)
d, (iy, ix) = grow
lab_full = np.where(d <= 3, lab_img[iy, ix], 0)

def samp(uv):
    x = np.clip(uv[:, 0] * W - 0.5, 0, W - 1.001); y = np.clip((1 - uv[:, 1]) * H - 0.5, 0, H - 1.001)
    x0, y0 = x.astype(int), y.astype(int); fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return (alb[y0, x0] * (1 - fx) * (1 - fy) + alb[y0, x0 + 1] * fx * (1 - fy) + alb[y0 + 1, x0] * (1 - fx) * fy + alb[y0 + 1, x0 + 1] * fx * fy)

r = int(np.ceil(R * 2)); oy, ox = np.mgrid[-r:r + 1, -r:r + 1]; ker = np.exp(-(ox ** 2 + oy ** 2) / (2 * (R / 2) ** 2))
def splat(uv, delta, chart):
    for (u, v), dl in zip(uv, delta):
        cx, cy = int(u * W), int((1 - v) * H)
        y0, y1, x0, x1 = max(cy - r, 0), min(cy + r + 1, H), max(cx - r, 0), min(cx + r + 1, W)
        if y0 >= y1 or x0 >= x1: continue
        k = ker[y0 - cy + r:y1 - cy + r, x0 - cx + r:x1 - cx + r] * (lab_full[y0:y1, x0:x1] == chart)
        acc[y0:y1, x0:x1] += k[..., None] * dl; wsum[y0:y1, x0:x1] += k
        np.maximum(wmax[y0:y1, x0:x1], k, out=wmax[y0:y1, x0:x1])

nseam = 0
for V, F, UV, lab in geos:
    key = np.round(V * 1e5).astype(np.int64)
    _, vid = np.unique(key, axis=0, return_inverse=True); vid = vid.ravel()
    edges = {}
    for ti in range(len(F)):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            i, j = F[ti, a], F[ti, b]
            edges.setdefault((min(vid[i], vid[j]), max(vid[i], vid[j])), []).append((ti, i, j))
    for l in edges.values():
        if len(l) != 2: continue
        (t1, i1, j1), (t2, i2, j2) = l
        u1a, u1b = UV[i1], UV[j1]
        u2a, u2b = (UV[i2], UV[j2]) if vid[i2] == vid[i1] else (UV[j2], UV[i2])
        if np.abs(u1a - u2a).max() < 1e-4 and np.abs(u1b - u2b).max() < 1e-4: continue
        if lab[t1] == lab[t2]: continue
        nseam += 1
        n = int(max(np.linalg.norm((u1b - u1a) * [W, H]), np.linalg.norm((u2b - u2a) * [W, H]))) + 2
        s = np.linspace(0, 1, n)[:, None]
        p1 = u1a + (u1b - u1a) * s; p2 = u2a + (u2b - u2a) * s
        c1, c2 = samp(p1), samp(p2); mean = 0.5 * (c1 + c2)
        splat(p1, mean - c1, lab[t1]); splat(p2, mean - c2, lab[t2])
corr = np.where(wsum[..., None] > 0, acc / np.maximum(wsum, 1e-9)[..., None], 0) * wmax[..., None]
out = np.clip(alb + corr, 0, 255).astype(np.uint8)
Image.fromarray(out).save(alb_p)
print("SEAM_BLEND %s: %d seam edges between charts, %d texels changed, mean |correction| %.1f" % (alb_p, nseam, int((wmax > 0.05).sum()), float(np.abs(corr[wmax > 0.05]).mean()) if (wmax > 0.05).any() else 0.0))
