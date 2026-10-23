"""Where the statue stands and how tall it is, from the cut-down mesh: feet.py <low_low.glb>
Prints 'FEET {"feet_center": [x, z], "height": h, "min_y": y}' in the glb frame (y up, model units). Place a statue by
its feet, not its bounding box: a staff or a cloak that sticks out moves the box centre off the plinth (statue v4).
feet_center = midpoint of the lowest 6% of the vertices (the soles), as the city measured its gate statues."""
import json, sys, numpy as np, trimesh
sc = trimesh.load(sys.argv[1])
V = np.concatenate([g.vertices for g in sc.geometry.values()])
y0, y1 = V[:, 1].min(), V[:, 1].max()
low = V[V[:, 1] <= y0 + 0.06 * (y1 - y0)]
print("FEET " + json.dumps({"feet_center": [round(float(np.median(low[:, 0])), 4), round(float(np.median(low[:, 2])), 4)],
                            "height": round(float(y1 - y0), 4), "min_y": round(float(y0), 4)}))
