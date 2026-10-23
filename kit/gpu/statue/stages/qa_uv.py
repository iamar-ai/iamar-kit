"""Fast face-UV quality (no bake needed): qa_uv.py <low_low.glb>  -> prints 'UVQ <score> fold <f> crushed <c>' (lower = better).
Env: FCX FCY FCZ FRXL FRXR FRZ as for qa_statue.py. Used by auto_uv.sh to search the face-only UV axis."""
import sys, os, numpy as np, trimesh
E = os.environ.get
sc = trimesh.load(sys.argv[1]); head = sc.geometry["head"]
V, F, UV = head.vertices, head.faces, head.visual.uv
CX, CY, CZ = float(E("FCX", "0")), float(E("FCY", "0")), float(E("FCZ", "0.6"))
RXL, RXR, RZ = float(E("FRXL", "0.08")), float(E("FRXR", "0.08")), float(E("FRZ", "0.09"))
import math
YAW = math.radians(float(E("FYAW", "0")))
cen = V[F].mean(1); bx, by, bz = cen[:, 0], -cen[:, 2], cen[:, 1]          # glb -> Blender frame (as prep_full.py)
dx, dy = bx - CX, by - CY; lx = dx * math.cos(YAW) - dy * math.sin(YAW); ly = dx * math.sin(YAW) + dy * math.cos(YAW)
t = (ly < 0) & (((lx / np.where(lx > 0, RXR, RXL)) * 0.85) ** 2 + ((bz - CZ) / RZ * 0.85) ** 2 < 1)
fu = UV[F[t]]; fp = V[F[t]]
uva = 0.5 * ((fu[:, 1, 0] - fu[:, 0, 0]) * (fu[:, 2, 1] - fu[:, 0, 1]) - (fu[:, 2, 0] - fu[:, 0, 0]) * (fu[:, 1, 1] - fu[:, 0, 1]))
a3 = 0.5 * np.linalg.norm(np.cross(fp[:, 1] - fp[:, 0], fp[:, 2] - fp[:, 0]), axis=1); ok = a3 > 1e-9
dens = np.abs(uva[ok]) * 2048 * 2048 / a3[ok]; w = a3[ok] / a3[ok].sum(); sg = np.sign(uva[ok])
fold = float(w[sg != (1 if (w * sg).sum() > 0 else -1)].sum()); crushed = float(w[dens < 0.25 * np.median(dens)].sum())
print("UVQ %.4f fold %.4f crushed %.4f" % (fold + crushed, fold, crushed))
