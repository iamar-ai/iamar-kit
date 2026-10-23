"""Automatic QA before a statue is installed. Usage: qa_statue.py <low_low.glb> <albedo.png> [normal.png]
Env: FCX FCZ FRXL FRXR FRZ (face oval centre/radii as given to prep_full.py, Blender frame: x, z up) and FCY.
Checks (exit 1 on any FAIL, so chain.sh stops before installing):
  1 face-region SEAMS: UV seam edges inside the face oval whose two sides have a different colour (texture jump through
    nose/lip/cheek, the mage's cheek patches and the sorceress' lip seam),
  2 OVERLAPPING SHELLS: a second surface facing out within 1.2 cm behind the face/neck skin (old chin or jaw poking through a graft),
  3 black texels inside the used charts (unbaked, shows as dark dots),
  4 floating components (separate pieces not touching the main body, by distance),
  5 face chart count,
  6 CRACKS: open (one-sided) edges of the welded mesh round the face (oval grown 1.4x) and neck: a crack between the face and
    the head shows as a dark jagged line whatever the textures (elf archer v4: 707 open edges, h21/predec.py)."""
import sys, os, numpy as np, trimesh
from PIL import Image
from scipy.spatial import cKDTree
E = os.environ.get
glb, alb_p = sys.argv[1], sys.argv[2]
sc = trimesh.load(glb)
alb = np.asarray(Image.open(alb_p).convert("RGB")).astype(float)
H, W = alb.shape[:2]
CX, CY, CZ = float(E("FCX", "0")), float(E("FCY", "0")), float(E("FCZ", "0.6"))
RXL, RXR, RZ = float(E("FRXL", "0.08")), float(E("FRXR", "0.08")), float(E("FRZ", "0.09"))
fails = []

def tex(uv):
    u = np.clip((uv[:, 0] * W).astype(int), 0, W - 1); v = np.clip(((1 - uv[:, 1]) * H).astype(int), 0, H - 1)
    return alb[v, u]

head = sc.geometry["head"]; body = sc.geometry["body"]
V, F, UV = head.vertices, head.faces, head.visual.uv
# glb frame: x, y up, z = -blender y. face oval in glb: centre (CX, CZ up, -CY)
import math
YAW = math.radians(float(E("FYAW", "0")))
def inoval(P, grow=1.0):   # same face frame as prep_full.py / qa_uv.py: glb -> Blender (x, -z, y), rotated by FYAW
    bx, by, bz = P[:, 0], -P[:, 2], P[:, 1]
    dx, dy = bx - CX, by - CY; lx = dx * math.cos(YAW) - dy * math.sin(YAW); ly = dx * math.sin(YAW) + dy * math.cos(YAW)
    return (ly < 0) & (((lx / np.where(lx > 0, RXR, RXL)) / grow) ** 2 + ((bz - CZ) / RZ / grow) ** 2 < 1)
cen = V[F].mean(1)
face_t = inoval(cen, 0.8)
print("QA face triangles inside the oval:", int(face_t.sum()))
if face_t.sum() < 200: print("QA RESULT FAIL face oval holds only %d triangles: wrong FCX/FCY/FCZ/FYAW (the check would be vacuous)" % face_t.sum()); sys.exit(1)

# 1 seams: welded-position edges whose UVs differ between the two triangles
key = np.round(V * 1e5).astype(np.int64)
_, vid = np.unique(key, axis=0, return_inverse=True)
vid = vid.ravel()
edges = {}
for ti in np.where(face_t)[0]:
    for a, b in ((0, 1), (1, 2), (2, 0)):
        i, j = F[ti, a], F[ti, b]
        k = (min(vid[i], vid[j]), max(vid[i], vid[j]))
        edges.setdefault(k, []).append((ti, i, j))
bad, tot = [], 0
for k, l in edges.items():
    if len(l) != 2: continue
    (t1, i1, j1), (t2, i2, j2) = l
    u1a, u1b = UV[i1], UV[j1]
    if vid[i2] == vid[i1]: u2a, u2b = UV[i2], UV[j2]
    else: u2a, u2b = UV[j2], UV[i2]
    if np.abs(u1a - u2a).max() < 1e-4 and np.abs(u1b - u2b).max() < 1e-4: continue
    tot += 1
    s = np.linspace(0.1, 0.9, 5)[:, None]
    c1 = tex(u1a + (u1b - u1a) * s); c2 = tex(u2a + (u2b - u2a) * s)
    d = np.abs(c1 - c2).mean()
    if d > 10: bad.append((d, np.linalg.norm(V[i1] - V[j1])))
seam_len = sum(l for d, l in bad)
print("QA seam edges in face: %d, with a colour jump >10: %d (length %.3f)" % (tot, len(bad), seam_len))
if seam_len > 0.10: fails.append("face texture seams: %d edges, %.3f long" % (len(bad), seam_len))


# 1b UV quality of the face: folds (flipped UV orientation) and crushed texel density (a chart squeezed into a thin band bakes smeared)
fu = UV[F[face_t]]
uva = 0.5 * ((fu[:, 1, 0] - fu[:, 0, 0]) * (fu[:, 2, 1] - fu[:, 0, 1]) - (fu[:, 2, 0] - fu[:, 0, 0]) * (fu[:, 1, 1] - fu[:, 0, 1]))
fp = V[F[face_t]]; a3 = 0.5 * np.linalg.norm(np.cross(fp[:, 1] - fp[:, 0], fp[:, 2] - fp[:, 0]), axis=1)
ok = a3 > 1e-9
dens = np.abs(uva[ok]) * W * H / a3[ok]
med = np.median(dens)
w = a3[ok] / a3[ok].sum()
crushed = float(w[dens < 0.25 * med].sum())            # share of the face AREA with under a quarter of the median texel density
sgn = np.sign(uva[ok]); flip = float(w[sgn != (1 if (w * sgn).sum() > 0 else -1)].sum())
print("QA face UV: median density %.0f texel/m2, crushed area share %.3f, folded area share %.3f" % (med, crushed, flip))
if crushed > 0.06: fails.append("face UV crushed: %.1f%% of the face has <1/4 texel density" % (100 * crushed))
if flip > 0.15: fails.append("face UV folded: %.1f%% flipped" % (100 * flip))

# 2 overlapping shells behind the face/neck skin (rays along the inverse normal)
mesh = trimesh.Trimesh(np.vstack([head.vertices, body.vertices]), np.vstack([head.faces, body.faces + len(head.vertices)]), process=False)
fn = head.face_normals[face_t]; pts = cen[face_t]
sel = np.random.default_rng(0).choice(len(pts), min(1500, len(pts)), replace=False)
mv, mf = mesh.vertices, mesh.faces
mc = mv[mf].mean(1); mtree = cKDTree(mc)
dist = []
for p, n in zip(pts[sel], fn[sel]):
    o = p - n * 1e-4; d = -n
    # triangles whose centre lies near the ray's first 3 cm
    cand = set()
    for t in (0.006, 0.015, 0.025):
        cand.update(mtree.query_ball_point(o + d * t, 0.012))
    best = 9.0
    for c in cand:
        a, b2, c2 = mv[mf[c]]
        e1, e2 = b2 - a, c2 - a; h = np.cross(d, e2); det = e1 @ h
        if abs(det) < 1e-12: continue
        f = 1.0 / det; s_ = o - a; u = f * (s_ @ h)
        if u < 0 or u > 1: continue
        q = np.cross(s_, e1); v = f * (d @ q)
        if v < 0 or u + v > 1: continue
        tt = f * (e2 @ q)
        # only a surface that faces the ray (entering a second shell) counts: the ray leaving a thin feature through its own
        # back (nose, circlet, ear) is not an overlap (elven king v5: 113 of 1500 hits, 76 of them exits; an internal task)
        if tt > 1e-4 and np.cross(e1, e2) @ d < 0: best = min(best, tt)
    dist.append(best)
dist = np.array(dist)
over = int((dist < 0.012).sum())
print("QA face points with another surface < 1.2 cm behind:", over, "of", len(sel))
if over > 0.04 * len(sel): fails.append("overlapping shells behind the face: %d of %d" % (over, len(sel)))

# 3 black texels inside the used charts
uvall = np.concatenate([g.visual.uv[g.faces].reshape(-1, 2) for g in (head, body)])
mask = np.zeros((H, W), bool)
from PIL import ImageDraw
im = Image.new("L", (W, H), 0); dr = ImageDraw.Draw(im)
for g in (head, body):
    for t in g.visual.uv[g.faces]:
        dr.polygon([(x * W, (1 - y) * H) for x, y in t], fill=255)
mask = np.asarray(im) > 0
dark = (alb.sum(2) < 60) & mask
print("QA black texels inside charts:", int(dark.sum()), "of", int(mask.sum()))
if dark.sum() > 0.002 * mask.sum(): fails.append("black texels in charts: %d" % dark.sum())

# 4 floating components by distance
vm = trimesh.Trimesh(mesh.vertices, mesh.faces, process=False)
tree = cKDTree(vm.vertices)
import scipy.sparse as sp, scipy.sparse.csgraph as cg
pairs = tree.query_pairs(2e-4, output_type="ndarray")
n = len(vm.vertices)
A = sp.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
e = vm.edges_unique
B = sp.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n))
nc, lab = cg.connected_components(A + B + A.T + B.T)
sizes = np.bincount(lab[mesh.faces[:, 0]])
big = sizes.max()
small = [(int(s)) for s in sizes if 0 < s < 0.02 * big]
print("QA components: %d, small floating ones (<2%% of the largest): %d" % (nc, len(small)))
if len(small) > 8: fails.append("floating components: %d" % len(small))
# 6 cracks round the face: open edges of the whole welded cut-down mesh inside the grown oval
wm = trimesh.Trimesh(mesh.vertices, mesh.faces, process=False); wm.merge_vertices()
eu, ec = np.unique(wm.edges_sorted, axis=0, return_counts=True); op = eu[ec == 1]
om = wm.vertices[op].mean(1); near = inoval(om, 1.4) & (cKDTree(V[F[face_t]].reshape(-1, 3)).query(om)[0] < 0.03)   # at the face skin, not a bow end in front of it
crack = float(np.linalg.norm(wm.vertices[op[near, 0]] - wm.vertices[op[near, 1]], axis=1).sum())
print("QA open edges round the face: %d (length %.3f)" % (near.sum(), crack))
if crack > 0.02: fails.append("cracks round the face: %d open edges, %.3f long" % (near.sum(), crack))
print("QA RESULT", "FAIL " + "; ".join(fails) if fails else "ok")
sys.exit(1 if fails else 0)
