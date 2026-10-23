# Recipe `portal_gate`: a dressed gate (stone or plaster) for every portal

The browser's own portal visual is a glowing ring or a plain grey frame. A world that promises
"a gate back to the city" needs a real one: the harbour blind test placed a flat slab with a ring
(review: FAIL row "portal gate", an internal task). This recipe builds a free-standing, walk-through stone
gate from the world's style profile, at a few hundred triangles, that passes `lint`, `audit` and
the texel rule.

Layer: engineering (any world) with the style's colours and painted maps. Tier 0: Python 3 only.
Status: WORKS (test below; shots in the real preview, iamar.26 day and dusk, in `docs/evidence/job3279/`).

## Steps

```
# 1. paint the profile's maps at 512 px (two used: dressed stone, wall)
python3 kit/style/check_style.py --paint /tmp/tex --profile <profile> --size 512 --only dressed_stone,wall_plaster
# 2. build the gate (512 maps tile every 2 m: 256 px per metre)
python3 kit/recipes/portal/portal_gate.py worlds/<world>/assets/portal_gate.glb --profile <profile> --textures /tmp/tex
#    GATE_OK ...: 344 triangles (budget 3000), opening 3.00 x 4.50 m, gate 5.10 x 5.68 x 1.40 m
```

The `--only` names are the iamar profile's layers; for another profile leave `--only` out (it
paints every layer) or name that profile's wall and stone layers.

3. Place the gate where the portal is, with the same yaw, and let the gate be the visual:

```json
"objects": [{"id": "portal_gate", "asset": "assets/portal_gate.glb", "position": [-40, 0, 2], "yaw": 90,
             "collision": "mesh"}],
"portals": [{"id": "home", "to": "oakhaven#default_arrival", "label": "To the iamar city",
             "position": [-40, 0, 2], "yaw": 90, "size": [2.4, 3.2, 0.8], "visual": "none"}]
```

`"visual": "ring"` also works: the glowing ring then stands inside the arch as the threshold.
Keep the portal `size` inside the opening (default opening 3.0 m wide, springing at 3.0 m: a
2.4 x 3.2 m entry fits with room).

4. Check: `iamar-world lint worlds/<world>` reports `arch 'portal_arch_LOD0' rise / half span 1.00`
and no error; `iamar-world materials texel worlds/<world>` passes; a `portal` camera in
`shots.json` at eye height, 4-6 m from the gate, shows the arch (see `docs/evidence/job3279/portal_*.jpg`).

## Options

| Option | Default | What |
|---|---|---|
| `--width` | 3.0 | opening width (m); at least 1.0 |
| `--spring` | 3.0 | height where the arch springs (m); the crown is `spring + width / 2` |
| `--pier` | 0.9 | each pier's width (m) |
| `--depth` | 0.9 | the gate's thickness (m) |
| `--variant` | auto | `stone` (dressed-stone body, voussoir ring, keystone, imposts) or `plaster` (one rounded adobe/plaster body from the wall layer, plinths and a slim coping). `auto` picks `stone` only when the profile paints an `ashlar`/`stone` layer, so a desert or other Track B profile gets `plaster` |
| `--profile`, `--region`, `--seed` | iamar | colours and weathering, as `style-gen` |
| `--textures DIR` | none | `DIR/<layer>.png` from `check_style.py --paint`; the UV scale follows the map's size (256 px/m) |
| `--world DIR [--check]` | | a preview world (ground, spawn, gate, a `visual: none` portal) and its closure/zfight/roof audits |

## What it builds

One node `portal_arch_LOD0` (lint classes a *gate* or *arch* as a structure, budget 3,000):

- the body (stone variant; the plaster variant skips the ring, keystone and imposts): the gate's outline (two piers and the head) cut around a semicircular opening, one
  closed solid; the body's top is left out because the coping covers it;
- on both faces: a voussoir ring standing 0.1 m proud, a keystone, impost blocks at the springing
  and pier plinths, all as wide as the pier so nothing overhangs the opening (an overhang shows
  its open back: the closure audit catches it);
- a coping slab overhanging every side.

Why not `style-gen arch`: that is a door surround on a wall, with a closed timber door and
tympanum. A portal needs an opening you walk through and a gate seen from both sides.

## Test

```
python3 kit/tests/recipes/statue_portal_test.py     # 18 checks with Blender, 12 without
```
