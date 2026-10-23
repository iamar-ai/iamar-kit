# bake_vertex_light houses in the real preview (an internal task)

`contact_day_dusk.png`: five painted-plaster houses baked with `kit/blender/bake_vertex_light.py`
(from `kit/tests/blender/vertex_light_test.py --keep DIR`), rendered by `iamar-world shots DIR/world OUT
--times day,dusk` in the real browser (iamar.26, kit pack of b5aa604, a render host offscreen, A5000 not
needed: Mesa software render under `offscreen`).

What the pictures show: the painted wall map is kept; the sunward wall is brighter than the shaded
one and a cast shadow falls on the plinth side; the roof keeps its slate map. At dusk the baked walls
do not change (the bake is fixed to the day sun, material is unshaded), so there is no double lighting
(live light on top of baked light); the sky and cobble ground, which are live, do change.
The edge_* cameras look at the world boundary and are not part of the check.
