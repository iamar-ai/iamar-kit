Job 3362 (harbour a4 review gap R4): the hero_statue recipe's coat is a closed 4 cm slab and the
figure is weathered stone. Rendered by `iamar-world shots --tier low --times day,dusk` in the iamar
browser iamar.26 + kit pack (f903990), offscreen on a GPU render host, 2026-10-21; world built by
`kit/tests/recipes/statue_portal_test.py --keep` (statue at the origin, gate at [0, 0, 8]).

`before_after.jpg`: pairs, before (left, kit f903990) and after (right): side close day, back day,
side close dusk. Coat edges now have thickness; darker folds, grime rising from the feet, rain
streaks and a faint lichen green on the shoulders. Single shots: `statue_side_close_day.jpg`,
`statue_side_close_dusk.jpg`, `statue_front_day.jpg` (camera behind the figure, gate beyond).

Closure (`closure_audit.py --ground 0.02`): before 0 open, 7 non-manifold, 20 inside-out parts
(CLOSURE_FAIL); after CLOSURE_OK, 0 / 0 / 0. Triangles 2,550 -> 2,320 (slab rims +246; hair parts sunk inside the head, which were inside out, dropped -476; shots were taken before that drop, which removes only hidden faces).
