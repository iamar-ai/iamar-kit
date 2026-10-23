# Job 3800 evidence: coastal and home catalogue set (eva, software GL)

`make_world.py <folder>` builds a test world that places all 13 models as their catalogue `use`
lines say (beach, clear water with coral and kelp on the floor, an open living room slab).
`iamar-world validate` passes (only WARN: unsigned) and `iamar-world preview` rendered 6 views,
19 objects, 6759 triangles, 35-43 fps on llvmpipe. `preview_sheet.jpg`: spawn, around0,
around2 and above. `thumbnails_before_turn.png` is the first render of all 13 thumbnails; the sofa,
kitchen counter and wardrobe then showed their backs, so they were turned to face +Z like the
city's furniture (`thumbnails_turned.png`). Colours and lighting here are software GL: judge them
on a GPU host.
