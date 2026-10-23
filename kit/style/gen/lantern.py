"""Street and wall lanterns whose glass reads as lit at dusk and night (an internal task).

The harbour blind test built its lantern as glowing glass inside a closed iron lathe: the glass
was emissive but nobody could see it, so the lanterns read as dark grey boxes at night. Here the
iron is an open frame: a base plate, four corner bars and a pyramid cap, with the glass box
between them visible from every side. The glass is emissive (the profile's `lamp_glow`, strength
`--glow`), so it glows whatever the scene light; a point light at the glass centre (the report's
`light`, to copy into scene.json `lights`) is what lights the street around it.

    post: a stone foot, a timber post and the lantern on top (2.6 m to the cap by default)
    wall: an iron wall plate and arm with the lantern hanging from it; the wall is the z = 0
          plane and the lantern stands out along +z (place it with the object's rotation)

Hidden faces are not built: the glass's top and bottom sit on the plates, the bars' ends in
them, the post's top under the base plate and its foot under the post.
"""
from __future__ import annotations

from meshkit import Mesh, UP

GLASS = 0.19        # glass box side (m)
GLASS_H = 0.26      # glass height
PLATE = 0.27        # base and cap plate side
PLATE_H = 0.035
BAR = 0.03          # corner bar thickness
CAP_H = 0.17        # pyramid cap height


def glow_colour(st) -> str:
    return st.palette.get("lamp_glow") or st.palette.get("candle") or "#ffc060"


def materials(st, glow: float) -> dict:
    g = glow_colour(st)
    return {
        "iron": {"name": "iron", "color": st.colour("iron", "lantern"), "roughness": 0.6},
        "timber": {"name": st.layer("timber") or "timber", "color": st.colour("timber", "lantern"),
                   "layer": st.layer("timber"), "roughness": 0.9},
        "stone": {"name": (st.layer("stone") or "stone"), "color": st.colour("stone", "lantern"),
                  "layer": st.layer("stone"), "roughness": 0.9},
        "glass": {"name": "lamp_glass", "color": g, "emissive": g, "emissive_strength": glow, "roughness": 0.3},
    }


def head(m: Mesh, M: dict, x: float, y0: float, z: float, lod: int):
    """The lantern from the bottom of its base plate (y0) up; returns the glass centre."""
    iron, glass = M["iron"]["name"], M["glass"]["name"]
    gy0 = y0 + PLATE_H
    gy1 = gy0 + GLASS_H
    m.box(iron, (x, y0 + PLATE_H / 2, z), (PLATE, PLATE_H, PLATE))
    m.box(glass, (x, (gy0 + gy1) / 2, z), (GLASS, GLASS_H, GLASS), top=False, bottom=False)
    if lod <= 1:
        h = GLASS / 2
        for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            m.beam(iron, (x + sx * h, gy0, z + sz * h), (x + sx * h, gy1, z + sz * h), BAR, ends=False)
    # cap plate (its top is under the pyramid) and pyramid roof
    m.box(iron, (x, gy1 + PLATE_H / 2, z), (PLATE, PLATE_H, PLATE), top=False)
    ty = gy1 + PLATE_H
    p = PLATE / 2
    corners = [(x - p, ty, z - p), (x + p, ty, z - p), (x + p, ty, z + p), (x - p, ty, z + p)]
    apex = (x, ty + CAP_H, z)
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        out = ((a[0] + b[0]) / 2 - x, CAP_H * 0.5, (a[2] + b[2]) / 2 - z)
        m.tri(iron, a, b, apex, out)
    if lod == 0:
        m.prism(iron, (x, ty + CAP_H - 0.02, z), 0.025, 0.09, 6)   # finial / hanging ring
    return (x, (gy0 + gy1) / 2, z), ty + CAP_H


class Lantern:
    def __init__(self, st, mount: str = "post", height: float = 2.6, glow: float = 1.3):
        if mount not in ("post", "wall"):
            raise ValueError("lantern --mount must be post or wall, not %r" % mount)
        self.st, self.mount, self.height, self.glow = st, mount, height, glow
        self.mats = materials(st, glow)
        self.report = {}

    def build(self, lod: int) -> Mesh:
        m = Mesh(self.st.tile_m)
        M = self.mats
        if self.mount == "post":
            # cap top at `height`: post up to the base plate
            y0 = self.height - (2 * PLATE_H + GLASS_H + CAP_H)
            foot_h = 0.32
            if lod <= 1:
                m.box(M["stone"]["name"], (0, foot_h / 2, 0), (0.34, foot_h, 0.34), bottom=False)
                m.box(M["timber"]["name"], (0, (foot_h + y0) / 2, 0), (0.15, y0 - foot_h, 0.15), top=False, bottom=False)
            else:
                m.box(M["timber"]["name"], (0, y0 / 2, 0), (0.15, y0, 0.15), top=False, bottom=False)
            centre, top = head(m, M, 0.0, y0, 0.0, lod)
        else:
            # wall plate on the z = 0 wall, an arm out to the lantern, which hangs below the arm
            arm_y, reach = self.height, 0.42
            m.box(M["iron"]["name"], (0, arm_y - 0.12, 0.01), (0.12, 0.36, 0.02), back=False)
            m.beam(M["iron"]["name"], (0, arm_y, 0.02), (0, arm_y, reach + 0.03), 0.04)
            if lod <= 1:   # brace from the plate's foot up to the arm
                m.beam(M["iron"]["name"], (0, arm_y - 0.28, 0.02), (0, arm_y - 0.02, reach * 0.6), 0.025)
            y0 = arm_y - 0.06 - (2 * PLATE_H + GLASS_H + CAP_H)
            centre, top = head(m, M, 0.0, y0, reach, lod)
            if lod <= 1:   # the hanger from the cap to the arm
                m.beam(M["iron"]["name"], (0, top - 0.02, reach), (0, arm_y - 0.02, reach), 0.02, ends=False)
        self.report.update({"mount": self.mount, "height": round(self.height, 3), "glow": self.glow,
                            "glass_centre": [round(c, 3) for c in centre],
                            "light": self.light(centre)})
        return m

    def light(self, centre) -> dict:
        """The scene.json `lights` entry to pair with this lantern (position relative to the
        object's origin: add the object's position, rotated by its yaw)."""
        return {"type": "point", "position": [round(c, 3) for c in centre], "color": glow_colour(self.st),
                "energy": 1.4, "range": 9, "attenuation": 1, "shadows": False}
