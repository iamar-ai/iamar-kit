#!/usr/bin/env python3
"""Job 3800 evidence: a small beach-house test world that places every coastal and home catalogue
object as its `use` line says, for `iamar-world preview`.

  python3 docs/evidence/job3800/make_world.py <out folder>
  iamar-world validate <out folder> && iamar-world preview <out folder> /tmp/coastal
"""
import json
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3] / "kit"
cat = json.loads((KIT / "catalog" / "catalog.json").read_text(encoding="utf-8"))
by_name = {e["source"]["file"].split("/")[-1][:-4]: e for e in cat["entries"]
           if e.get("source", {}).get("file", "").startswith("kit/catalog/assets/coastal/")}
out = Path(sys.argv[1])
(out / "assets").mkdir(parents=True, exist_ok=True)

# stem -> position, yaw. Beach for z > 0 at y 0, sea for z < 0 (surface y -0.3, floor y -2.6),
# an open living room slab at z 16..24.
PLACE = {
    "palm_tree": [([-9, 0, 4], 0), ([-12, 0, 8], 140), ([9, 0, 6], 70)],
    "beach_umbrella": [([-2, 0, 5], 0)],
    "sun_lounger": [([-3, 0, 5.2], 10), ([-1, 0, 5.4], -8)],
    "beach_towel": [([1.5, 0, 4.5], 30)],
    "sea_shells": [([0, 0, 1.5], 0), ([-6, 0, 1.2], 120)],
    "dock": [([6, -0.3, 1.0], 0)],
    "coral": [([-4, -2.6, -8], 0), ([0, -2.6, -11], 70)],
    "kelp": [([3, -2.6, -9], 0), ([-7, -2.6, -12], 40)],
    "rug": [([0, 0.32, 20], 0)],
    "sofa": [([0, 0.3, 21.5], 180)],
    "kitchen_counter": [([-5, 0.3, 23.3], 180)],
    "bathtub": [([5, 0.3, 23], 0)],
    "wardrobe": [([7.5, 0.3, 18], -90)],
}
objects = []
tris = 0
for stem, spots in PLACE.items():
    e = by_name[stem]
    src = KIT.parent / e["source"]["file"]
    shutil.copy(src, out / "assets" / src.name)
    for k, (pos, yaw) in enumerate(spots):
        o = {"id": "%s_%d" % (stem, k), "asset": "assets/" + src.name, "position": pos, "rotation": [0, yaw, 0]}
        if e.get("collision") not in (None, "none"):
            o["collision"] = e["collision"]
        if e.get("animations") and stem == "kelp":
            o["animation"] = "sway"
        if e["category"] == "tree":
            o["sway"] = True
        objects.append(o)
        tris += e["triangles"]["lod0"]
prims = [
    {"id": "sand", "shape": "box", "size": [60, 1, 30], "position": [0, -0.5, 15], "color": "#c8b48c", "collision": "box"},
    {"id": "seabed", "shape": "box", "size": [60, 1, 30], "position": [0, -3.1, -15], "color": "#a89a78", "collision": "box"},
    {"id": "room_floor", "shape": "box", "size": [18, 0.3, 9], "position": [0, 0.15, 20.5], "color": "#9c8a72", "collision": "box"},
]
scene = {"format": "iamar-scene", "format_version": 0,
         "environment": {"time_of_day": 11},
         "terrain": {"type": "none"}, "primitives": prims, "objects": objects,
         "water": [{"id": "sea", "position": [0, -0.3, -15], "size": [60, 30], "depth": 2.3, "color": "#2f7f8caa", "swimmable": True}],
         "spawn_points": [{"id": "default", "position": [0, 0.2, 12], "yaw": 0}]}
man = {"format": "iamar-world", "format_version": 0, "id": "coastal_set_test", "name": "Coastal and home set",
       "author": {"name": "an internal task"}, "version": "1.0.0", "api_version": "0.1",
       "features": ["objects", "primitives", "water"],
       "budgets": {"triangles": tris + 2000, "objects": len(objects) + len(prims) + 4, "texture_size": 1024,
                   "texture_bytes": 64 << 20, "package_bytes": 64 << 20}}
(out / "scene.json").write_text(json.dumps(scene, indent=1), encoding="utf-8")
(out / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
print("wrote %s: %d objects, %d triangles" % (out, len(objects), tris))
