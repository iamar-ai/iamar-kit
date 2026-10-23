# Split-budget cage for a statue whose high mesh has "head" and "body" primitives (merge.py):
# the body, the head (hat, hair) and the face oval are each cut to their OWN triangle budget
# (only that group's faces are simplified in each pass, so no crack opens between groups),
# then one xatlas atlas where the face charts get `face_density` x the texel density.
#   python lowsplit.py hi.glb out_prefix body_tris head_tris face_tris  cx cy rx ry [face_density]
# (variant for facegraft2 output: cx unused, cy = collar height, rx/ry = head box x range)
import os, sys, numpy as np, trimesh, pymeshlab, xatlas
hi_p, out = sys.argv[1], sys.argv[2]
nb, nh, nf = map(int, sys.argv[3:6]); cx, cy, rx, ry = map(float, sys.argv[6:10])
dens = float(sys.argv[10]) if len(sys.argv) > 10 else 3.0
sc = trimesh.load(hi_p)
parts = {g.visual.material.name.split(".")[0]: g for g in sc.geometry.values()}
body, head = parts["body"], parts["head"]
# groups: 2 = the swapped face (material "head"), 1 = hat + hair (the body piece above the collar,
# inside the head box; the staff head beside it stays body), 0 = the rest of the body
c = body.triangles_center
hh = (c[:, 1] > cy) & (c[:, 0] > rx) & (c[:, 0] < ry)
grp = np.concatenate([np.where(hh, 1, 0), np.full(len(head.faces), 2)])
m = trimesh.util.concatenate([body, head])
m.visual = trimesh.visual.ColorVisuals(m)
m.merge_vertices(merge_tex=True, merge_norm=True)   # the glb splits every vertex per normal: weld, or every edge is a "boundary"
print("HI verts", len(m.vertices))
print("HI faces body %d head %d face %d" % ((grp == 0).sum(), (grp == 1).sum(), (grp == 2).sum()))
# each group is simplified as its own submesh with its boundary locked (VCG keeps boundary vertices
# fixed), so the face/head seam is the same edge chain on both sides and welds back exactly
target = {0: nb, 1: nh, 2: nf}
Vs, Fs, Qs, off = [], [], [], 0
if os.environ.get('SELDEC') == '1':
    # SELDEC=1 (an internal task): thin each group as a SELECTION of the one welded mesh. A selected-only collapse never moves a vertex
    # of an unselected triangle, so the borders between groups still weld exactly, but a group's own open edges (the elven
    # king's hair strands) thin like the rest; with every border locked the king's hair kept ~3.9k triangles on its strand
    # edges and its crown went flat at a 3.4k budget.
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(m.vertices, m.faces, f_scalar_array=grp.astype(float)))
    for g in (2, 1, 0):
        ms.compute_selection_by_condition_per_face(condselect="fq == %d" % g)
        ms.apply_filter("meshing_decimation_quadric_edge_collapse", targetfacenum=target[g], selected=True, preserveboundary=False,
            boundaryweight=float(os.environ.get('BW', '2.0')), preservenormal=True, preservetopology=True, optimalplacement=True,
            planarquadric=os.environ.get('PLANAR', '1') == '1', qualitythr=float(os.environ.get('QT', '0.4')), autoclean=True)
    ms.apply_filter("meshing_remove_unreferenced_vertices"); cm = ms.current_mesh()
    Vs, Fs, Qs = [cm.vertex_matrix()], [cm.face_matrix()], [np.rint(cm.face_scalar_array()).astype(int)]
for g in ((0, 1, 2) if os.environ.get('SELDEC') != '1' else ()):
    sub = m.submesh([np.where(grp == g)[0]], append=True)
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(sub.vertices, sub.faces))
    ms.apply_filter("meshing_decimation_quadric_edge_collapse", targetfacenum=target[g], preserveboundary=True,
        boundaryweight=float(os.environ.get('BW','2.0')), preservenormal=True, preservetopology=True, optimalplacement=True,
        planarquadric=os.environ.get('PLANAR','1')=='1', qualitythr=float(os.environ.get('QT','0.4')), autoclean=True)
    cm = ms.current_mesh(); Vs.append(cm.vertex_matrix()); Fs.append(cm.face_matrix() + off); off += cm.vertex_number()
    Qs.append(np.full(cm.face_number(), g))
w = trimesh.Trimesh(np.concatenate(Vs), np.concatenate(Fs), process=False)
q = np.concatenate(Qs)
w.merge_vertices()   # exact positions: the locked seam welds
V, F = w.vertices, w.faces
print("LOW faces body %d head %d face %d total %d" % ((q == 0).sum(), (q == 1).sum(), (q == 2).sum(), len(F)))
def arap_uv(v, f, uv0, iters=int(os.environ.get('ARAP_IT', '40'))):
    """ARAP (local/global) unwrap of the face chart, started from its projection, free rim (an internal task: a single cylindrical
    projection squeezes every surface that faces up or down, the sorceress' brow and nose underside, into a thin band:
    qa_statue 'face UV crushed'). Each triangle keeps its 3D shape and size in UV as far as the disk allows."""
    import scipy.sparse as sp, scipy.sparse.linalg as sla
    n, m_ = len(v), len(f)
    p0, p1, p2 = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    e1 = p1 - p0; e2 = p2 - p0; l1 = np.linalg.norm(e1, axis=1); ok = l1 > 1e-12
    ax = e1 / np.maximum(l1, 1e-12)[:, None]; nrm = np.cross(e1, e2); ay = np.cross(nrm, e1)
    ay /= np.maximum(np.linalg.norm(ay, axis=1), 1e-12)[:, None]
    X = np.zeros((m_, 3, 2)); X[:, 1, 0] = l1; X[:, 2, 0] = (e2 * ax).sum(1); X[:, 2, 1] = (e2 * ay).sum(1)   # flat triangle
    rows, cols, vals, cots = [], [], [], np.zeros((m_, 3))
    for k_, (a_, b_, c_) in enumerate(((0, 1, 2), (1, 2, 0), (2, 0, 1))):
        u1 = v[f[:, a_]] - v[f[:, c_]]; u2 = v[f[:, b_]] - v[f[:, c_]]
        cot = (u1 * u2).sum(1) / np.maximum(np.linalg.norm(np.cross(u1, u2), axis=1), 1e-12)
        cot = np.clip(cot, 1e-4, 1e4) * 0.5; cots[:, k_] = cot   # weight of edge (a_, b_)
        rows += [f[:, a_], f[:, b_]]; cols += [f[:, b_], f[:, a_]]; vals += [cot, cot]
    Wm = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    L = (sp.diags(np.asarray(Wm.sum(1)).ravel()) - Wm).tolil(); L[0, :] = 0; L[0, 0] = 1; L = L.tocsc()   # pin vertex 0
    solve = sla.factorized(L)
    u = uv0.copy()
    for _ in range(iters):
        U = u[f]                                                     # local: best rotation per triangle
        S = np.zeros((m_, 2, 2))
        for k_, (a_, b_) in enumerate(((0, 1), (1, 2), (2, 0))):
            dx = (X[:, a_] - X[:, b_]); du = (U[:, a_] - U[:, b_])
            S += cots[:, k_, None, None] * du[:, :, None] * dx[:, None, :]
        Us, _, Vt = np.linalg.svd(S); R = Us @ Vt
        d = np.linalg.det(R) < 0
        if d.any(): Us[d, :, 1] *= -1; R = Us @ Vt
        b = np.zeros((n, 2))                                        # global: Poisson solve
        for k_, (a_, b_) in enumerate(((0, 1), (1, 2), (2, 0))):
            r = cots[:, k_, None] * np.einsum("tij,tj->ti", R, X[:, a_] - X[:, b_])
            np.add.at(b, f[:, a_], r); np.add.at(b, f[:, b_], -r)
        b[0] = u[0]
        u = np.stack([solve(b[:, 0]), solve(b[:, 1])], 1)
    U = u[f]; sa = (U[:, 1, 0] - U[:, 0, 0]) * (U[:, 2, 1] - U[:, 0, 1]) - (U[:, 2, 0] - U[:, 0, 0]) * (U[:, 1, 1] - U[:, 0, 1])
    print("FACEUV arap: %d verts, %d iterations, flipped triangles %d of %d" % (n, iters, int((sa < 0).sum() if (sa > 0).sum() > m_ / 2 else (sa > 0).sum()), m_))
    return u


# xatlas: the face charts are added with positions scaled by `dens`, so they get dens x the texel density
atlas = xatlas.Atlas()
subs = []
# the neck (body-group triangles under the chin) is a cylinder too: its own single chart, so the shading does not split down
# the middle of it where xatlas cut it into pieces
Cc = V[F].mean(1)
NX, NY0, NY1, NZ = float(os.environ.get('NECKX', '0.059')), float(os.environ.get('NECKY0', '0.49')), float(os.environ.get('NECKY1', '0.575')), float(os.environ.get('NECKR', '0.075'))
neck = (q != 2) & (np.abs(Cc[:, 0] - NX) < NZ) & (Cc[:, 1] > NY0) & (Cc[:, 1] < NY1) & (np.abs(Cc[:, 2] - float(os.environ.get('NECKZC', '0'))) < float(os.environ.get('NECKZR', '0.09'))) if os.environ.get('NECKCYL', '1') == '1' else np.zeros(len(F), bool)
print("neck triangles", int(neck.sum()))
for sel, k, cyl in (((q != 2) & ~neck, 1.0, False), (neck, dens, True), (q == 2, dens, True)):
    if not sel.any(): continue
    f = F[sel]; used = np.unique(f); remap = -np.ones(len(V), int); remap[used] = np.arange(len(used))
    v = V[used]; ctr = v.mean(0)
    if cyl and os.environ.get('CYL', '1') == '1':
        # ONE chart: a cylindrical parametrisation around the head's vertical axis (a face and a neck are nearly cylinder
        # pieces), so there are no scattered fragments whose edges show as patches
        CXf, CZf, Rf = float(os.environ.get('CYLX', '0.059')), float(os.environ.get('CYLZ', '-0.02')), float(os.environ.get('CYLR', '0.075'))
        if sel is not None and (q[sel] == 2).all():   # the face chart may use its own axis (FCYLX/FCYLZ/FCYLR): a protruding nose is crushed into a thin band when the axis is far behind it
            CXf, CZf, Rf = float(os.environ.get('FCYLX', CXf)), float(os.environ.get('FCYLZ', CZf)), float(os.environ.get('FCYLR', Rf))
        ang = np.arctan2(v[:, 0] - CXf, v[:, 2] - CZf)
        fuv = np.stack([ang * Rf, v[:, 1]], 1) * k
        if (q[sel] == 2).all() and os.environ.get('FACEUV', '') == 'arap':
            fuv = arap_uv(v, remap[f], fuv / k) * k
        atlas.add_mesh(v.astype(np.float32), remap[f].astype(np.uint32), uvs=fuv.astype(np.float32))
    else:
        atlas.add_mesh(((v - ctr) * k + ctr).astype(np.float32), remap[f].astype(np.uint32))
    subs.append((used, q[sel]))
co = xatlas.ChartOptions(); co.max_cost = float(__import__("os").environ.get("MAXCOST","16")); co.normal_deviation_weight = float(__import__("os").environ.get("NDW","0.5")); co.roundness_weight = 0.02
co.use_input_mesh_uvs = os.environ.get('CYL', '1') == '1'; co.straightness_weight = 2.0; co.max_iterations = 4
po = xatlas.PackOptions(); po.resolution = 2048; po.padding = 6; po.bilinear = True; po.blockAlign = True
atlas.generate(co, po)
print("ATLAS charts", atlas.chart_count, atlas.width, "x", atlas.height)
outs = {"head": [], "body": []}
for i, (used, qs) in enumerate(subs):
    vm, idx, uv = atlas[i]
    vv = V[used][vm]
    for name, gs in (("body", (0,)), ("head", (1, 2))):
        sel = np.isin(qs, gs)
        if sel.any(): outs[name].append((vv, idx[sel], uv))
sc2 = trimesh.Scene()
for name, chunks in outs.items():
    vs, fs, us, off = [], [], [], 0
    for vv, ii, uv in chunks:
        u = np.unique(ii); r = -np.ones(len(vv), int); r[u] = np.arange(len(u))
        vs.append(vv[u]); us.append(uv[u]); fs.append(r[ii] + off); off += len(u)
    t = trimesh.Trimesh(np.concatenate(vs), np.concatenate(fs), process=False)
    t.visual = trimesh.visual.TextureVisuals(uv=np.concatenate(us), material=trimesh.visual.material.PBRMaterial(name=name))
    sc2.add_geometry(t, geom_name=name, node_name=name)
    print("PRIM", name, len(t.faces), "tris", len(t.vertices), "verts")
sc2.export(out + "_low.glb")
