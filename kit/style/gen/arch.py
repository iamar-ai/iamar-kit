"""Doors and round-arched stone door surrounds: a port of MpStyle.door_arch (the iamar browser source (not public)
scripts/world/masterplan/mp_style.gd) and the door frame it springs from (Buildings.door).

A ring of voussoirs with a keystone springs from the door frame's lintel and a timber
tympanum fills the arch. The rise is min(half span, room under the first floor's beam): a
semicircle at most, refused under 0.28 m (profile `dimensions.arch_rise_half_span`). The
ring's back lies on the wall and its feet on the lintel, so neither is emitted; every other
face is, so the surround is closed against the wall.
"""
from __future__ import annotations

import math

from meshkit import Mesh, UP, add, mul, basis_facing, at_basis

LINTEL = 0.24     # lintel height over the door (Buildings.door)
RING = 0.22       # voussoir depth across the ring
DEPTH = 0.17      # how far the ring stands out of the wall
SEGS = 9


def door(mesh: Mesh, pos, normal, width, door_h, mats, kind=0, details=True):
    """A door on a wall face: frame (two jambs and a lintel standing out of the wall), a leaf a
    little proud of the wall inside the frame, and iron straps (kind 0, 2) or panels (kind 1).
    `pos` is the door's foot on the wall face. Returns the lintel's top y."""
    b = basis_facing(normal)
    frame = mats["stone"]["name"] if kind == 2 else (mats["paint"]["name"] if kind == 1 else mats["trim"]["name"])
    leaf = mats["timber"]["name"] if kind == 2 else mats["paint"]["name"]
    fw = 0.16      # frame width
    fd = 0.12      # frame depth out of the wall
    P = lambda x, y, z: at_basis(b, pos, x, y, z)
    for sx in (-1.0, 1.0):
        mesh.box(frame, P(sx * (width * 0.5 + fw * 0.5), door_h * 0.5, fd * 0.5), (fw, door_h, fd), b,
                 back=False, bottom=False, top=False)
    # the lintel is as deep as the arch ring (DEPTH) and a little more, so the ring's feet stand on it
    lw, ld = width + 0.45, DEPTH + 0.02
    mesh.box(frame, P(0.0, door_h + LINTEL * 0.5, ld * 0.5), (lw, LINTEL, ld), b, back=False)
    # the leaf, 2.5 cm proud of the wall (frame sides seal its edges)
    hx, z = width * 0.5, 0.025
    mesh.quad(leaf, P(-hx, 0.0, z), P(hx, 0.0, z), P(hx, door_h, z), P(-hx, door_h, z), normal)
    if not details:
        pass
    elif kind in (0, 2):
        for y in (0.45, door_h - 0.5):
            mesh.box(mats["iron"]["name"], P(0.0, y, z + 0.012), (width - 0.12, 0.07, 0.024), b, back=False)
    else:
        for y in (door_h * 0.28, door_h * 0.7):
            mesh.box(leaf, P(0.0, y, z + 0.012), (width - 0.3, door_h * 0.3, 0.024), b, back=False)
    return pos[1] + door_h + LINTEL


def door_arch(mesh: Mesh, pos, normal, width, door_h, ceiling, stone, fill):
    """MpStyle.door_arch: True when built, False when there is no room under `ceiling`."""
    spring = pos[1] + door_h + LINTEL
    span = width * 0.5
    rise = min(span, ceiling - spring - RING - 0.08)
    if rise < 0.28:
        return False
    b = basis_facing(normal)
    along = b[0]

    def at(x, y, z):
        return add(add(add(pos, mul(along, x)), mul(UP, y - pos[1])), mul(normal, z))

    inner, outer = [], []
    for i in range(SEGS + 1):
        t = math.pi * i / SEGS
        inner.append((math.cos(t) * span, spring + math.sin(t) * rise))
        outer.append((math.cos(t) * (span + RING), spring + math.sin(t) * (rise + RING)))
    # tympanum: timber, just proud of the wall
    for i in range(SEGS):
        q0, q1 = inner[i], inner[i + 1]
        mesh.tri(fill, at(0.0, spring, 0.03), at(q0[0], q0[1], 0.03), at(q1[0], q1[1], 0.03), normal)
    c = (0.0, spring)
    for i in range(SEGS):
        i0, i1, e0, e1 = inner[i], inner[i + 1], outer[i], outer[i + 1]
        mesh.quad(stone, at(i0[0], i0[1], DEPTH), at(e0[0], e0[1], DEPTH), at(e1[0], e1[1], DEPTH),
                  at(i1[0], i1[1], DEPTH), normal)
        mid_i = ((i0[0] + i1[0]) * 0.5, (i0[1] + i1[1]) * 0.5)
        mid_e = ((e0[0] + e1[0]) * 0.5, (e0[1] + e1[1]) * 0.5)
        down = _unit((c[0] - mid_i[0], c[1] - mid_i[1]))
        mesh.quad(stone, at(i0[0], i0[1], 0.0), at(i1[0], i1[1], 0.0), at(i1[0], i1[1], DEPTH), at(i0[0], i0[1], DEPTH),
                  add(mul(along, down[0]), mul(UP, down[1])))
        up = _unit((mid_e[0] - c[0], mid_e[1] - c[1]))
        mesh.quad(stone, at(e0[0], e0[1], 0.0), at(e1[0], e1[1], 0.0), at(e1[0], e1[1], DEPTH), at(e0[0], e0[1], DEPTH),
                  add(mul(along, up[0]), mul(UP, up[1])))
    # keystone: a block whose back is on the wall
    ky = spring + rise + RING * 0.5
    kd = DEPTH + 0.07
    mesh.box(stone, add(at(0.0, ky, 0.0), mul(normal, kd * 0.5)), (0.3, RING + 0.2, kd), b, back=False)
    return True


def _unit(v):
    ln = math.hypot(v[0], v[1])
    return (v[0] / ln, v[1] / ln) if ln > 1e-12 else (0.0, 0.0)


def wall_panel(mesh: Mesh, width, height, depth, mat, cap_mat=None):
    """A free-standing wall block, front face at z=0 facing +z (for the arch sample)."""
    mesh.box(mat, (0.0, height * 0.5, -depth * 0.5), (width, height, depth), None, bottom=False)
