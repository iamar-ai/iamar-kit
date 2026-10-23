# Thin a prepped statue (prep_full.py output: primitives "head" = face oval, "body" = the rest) WITHOUT opening a crack
# along the face oval:  python predec_joint.py in.glb out.glb face_faces body_faces
# The old h21/predec.py decimated the two primitives separately with an unlocked rim, so their rims drifted apart and the
# game showed a dark jagged line round the face (elf archer v4, mp-RV 44fab600: 707 open edges at head height).
# Here the body and the face are thinned with the rim held still, then welded and thinned once more together (steps A-C).
# Every final triangle takes the label of the nearest original one, so the face oval keeps prep_full.py's shape for lowsplit3.py.
# (Tried and dropped: quality-weighted collapse (MeshLab normalises the weights, the body error went to ~0 and the
# decimation spun webs of huge triangles across the arrow and cloak), a selected-only FACE pass (it flattened the face into a
# wedge), a separately thinned rim band with both edges locked (17 cm slivers across the face), and locking every open edge in
# step A (the source's own open edges stayed dense: archer body 7.7k over its 6k budget, 5x the dark texels).)
import os, sys, numpy as np, trimesh, pymeshlab
from scipy.spatial import cKDTree
src, out, nf, nb = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
sc = trimesh.load(src); parts = {g.visual.material.name.split(".")[0]: g for g in sc.geometry.values()}
head, body = parts["head"], parts["body"]
m = trimesh.util.concatenate([body, head]); m.visual = trimesh.visual.ColorVisuals(m)
lab = np.concatenate([np.zeros(len(body.faces), np.int8), np.ones(len(head.faces), np.int8)])
cen0 = m.triangles_center
m.merge_vertices(merge_tex=True, merge_norm=True)
F0 = m.faces
# A. the BODY is thinned on the welded mesh as a selection: a selected-only collapse never moves a vertex of an unselected
#    (face) triangle, so the rim stays put, while the source's own open edges (cloak hems, bow ends) thin as usual
ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(m.vertices, F0, f_scalar_array=lab.astype(float)))
ms.compute_selection_by_condition_per_face(condselect="fq == 0")
ms.apply_filter("meshing_decimation_quadric_edge_collapse", targetfacenum=nb, selected=True,   # the target counts the selection
    preserveboundary=False, boundaryweight=6.0, preservenormal=True, preservetopology=True, optimalplacement=True, qualitythr=0.4, autoclean=True)
ms.apply_filter("meshing_remove_unreferenced_vertices"); c = ms.current_mesh()
VA, FA, qA = c.vertex_matrix().copy(), c.face_matrix().copy(), c.face_scalar_array().copy()
print("PREDEC body: %d -> %d faces" % ((lab == 0).sum(), (qA == 0).sum()))
# B. the FACE is thinned as its own submesh with its boundary (the rim) locked. (A selected-only face pass in the same MeshSet
#    wrecked the face into a wedge.)
sub = trimesh.Trimesh(VA, FA[qA == 1], process=False); sub.remove_unreferenced_vertices()
ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(sub.vertices, sub.faces))
ms.apply_filter("meshing_decimation_quadric_edge_collapse", targetfacenum=nf, preserveboundary=True, boundaryweight=6.0,
    preservenormal=True, preservetopology=True, optimalplacement=True, qualitythr=0.4, autoclean=True)
ms.apply_filter("meshing_remove_unreferenced_vertices"); c = ms.current_mesh(); vB, fB = c.vertex_matrix(), c.face_matrix()
print("PREDEC face: %d -> %d faces" % (len(sub.faces), len(fB)))
w = trimesh.Trimesh(np.concatenate([VA, vB]), np.concatenate([FA[qA == 0], fB + len(VA)]), process=False)
w.merge_vertices(); w.remove_unreferenced_vertices()
# C. one short joint pass over the welded mesh: the rim is still at full resolution and its tiny edges are by far the cheapest
#    collapses, so they go first; a welded rim cannot split
ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(w.vertices, w.faces))
ms.apply_filter("meshing_decimation_quadric_edge_collapse", targetfacenum=int((nf + nb) * float(os.environ.get("JOINT", "0.97"))),
    preserveboundary=False, boundaryweight=6.0, preservenormal=True, preservetopology=True, optimalplacement=True, qualitythr=0.4, autoclean=True)
ms.apply_filter("meshing_remove_unreferenced_vertices"); c = ms.current_mesh(); V, F = c.vertex_matrix(), c.face_matrix()
isf = lab[cKDTree(cen0).query(V[F].mean(1), workers=-1)[1]] == 1
sc2 = trimesh.Scene()
for name, sel in (("head", isf), ("body", ~isf)):
    f = F[sel]; u = np.unique(f); r = -np.ones(len(V), int); r[u] = np.arange(len(u))
    t = trimesh.Trimesh(V[u], r[f], process=False)
    t.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(name=name))
    sc2.add_geometry(t, geom_name=name, node_name=name)
    print("PREDEC", name, int(len(head.faces) if name == "head" else len(body.faces)), "->", len(t.faces))
sc2.export(out)
