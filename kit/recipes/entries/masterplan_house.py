"""Recipe masterplan_house (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 640
LAYER = "style"
r("masterplan_house", "Masterplan houses, convex-wing roofs and door arches from a style profile", "geometry",
  "A finished-looking town house in under 3000 triangles: the city's own house builder (stone or limewash ground storey, quoins and timber corner posts, half-timbered upper storeys, a jettied front on carved brackets, an oriel, a round corner tower, a framed door under a round stone arch, windows with shutters) under a hipped roof that covers any L-, T- or U-shaped footprint, closed and culled, with LODs.",
  "Every iamar-family building that is not a landmark; a custom look reuses it with its own style profile (colours, dimensions, painted layers).",
  ["`iamar-world style-gen house out.glb --profile <profile> --region <region> --seed N --footprint rect|narrow|L|T|U|WxD|points.json --world preview --check`: writes LOD0-2, fits LOD0 to the profile's building budget (drops shutters, sills, side quoins, then timber braces, posts and rails) and runs the closure, roof and zfight audits on every LOD.",
   "Timber frame on the upper storeys: `--timber plain|post|studs|braced|crossed` or, by default, picked by seed from the region's (else the profile's) `timber_frame_weights`; the iamar profile frames town houses ([0, 1, 3, 3, 2]) and keeps the city's quarter weights (mages mostly plain). Rails and posts stand 6 cm proud, braces 3 cm, all clear of windows, shutters, quoins, oriel and tower; a Track B profile without weights stays plain. Never leave an iamar town house a plaster box between quoins: the harbour blind test a5 did (review gap R3).",
   "Roof alone over any footprint: `iamar-world style-gen roof out.glb --footprint L --eaves 6`; a door surround: `iamar-world style-gen arch out.glb --width 1.3 --ceiling 3.6`.",
   "Paint the profile's layers (`check_style.py --paint textures --profile <profile>`) and pass `--textures textures`: each part takes its layer's painted texture (1 UV unit = 4 m), a paint colour on a shared layer stays in the base colour factor.",
   "Tall houses: the roof stays a third to a half of the height when the profile gives `roof_height_fraction` (iamar does); style-gen prints `WARN roof` when a narrow wing (an L or U arm, a 6 m deep house of 3+ storeys) cannot reach it under the pitch ceiling: make it deeper or lower.",
   "Vary houses by seed and region; never place one seed twice side by side (the variety rules, kit/style/variety).",
   "Then bake light (kit/blender bake_unlit.py) and run the review gate."],
  {"budget_lod0": 3000, "lods": 3, "quoin_course_m": 0.36, "eave_overhang_m": [0.42, 0.66], "cap_w_m": 0.17},
  "kit/tests/style/gen/style_gen_test.py (audits on every LOD, budget, plan area of the roof = footprint, determinism), kit/tests/style/gen/frame_test.py (each timber pattern's pieces, audits, profile defaults); `--check` per build.",
  "None at run time; one generator run per house.",
  "the iamar browser source (not public) scripts/world/masterplan/mp_roof.gd (A20 convex wings, the maintainer 2026-10-09 'see the roofs rather than mesh openings'), mp_style.gd (dress_corners, jetty_brackets, door_arch, corner_tower), mp_buildings.gd (_emit_oriel; _base_style and _emit_facade_varied timber-frame language and quarter weights); ported in iamar-kit kit/style/gen (an internal task; timber frame an internal task, harbour a5 review docs/reviews/2026-10-22-an agent-blindtest-harbour-a5.md gap 3)",
  "automatic", "kit/style/gen/gen.py")
