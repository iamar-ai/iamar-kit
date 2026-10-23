Rendered by `iamar-world shots --tier low` (1280x720) in the iamar browser iamar.26 + kit pack, offscreen on a GPU render host, 2026-10-20 (an internal task). Sample world: the gate at [0, 0, 8] with a `visual: none` portal, the statue at the origin (kit/tests/recipes/statue_portal_test.py builds the same world).

```
SHOT statue_front         day    triangles=4596 draws=6 objects=6 fps=81.4 ok
SHOT statue_back          day    triangles=5340 draws=12 objects=12 fps=69.9 ok
SHOT portal_close         day    triangles=768 draws=8 objects=8 fps=78.8 ok
SHOT portal_through       day    triangles=5340 draws=12 objects=12 fps=68.4 ok
SHOT statue_front         dusk   triangles=4596 draws=6 objects=6 fps=77.1 ok
SHOT statue_back          dusk   triangles=5340 draws=12 objects=12 fps=74.5 ok
SHOT portal_close         dusk   triangles=768 draws=8 objects=8 fps=80.3 ok
SHOT portal_through       dusk   triangles=5340 draws=12 objects=12 fps=68.0 ok
```
