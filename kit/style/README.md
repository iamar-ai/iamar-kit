# Style kit: style profiles (style.json)

A **style profile** is one world's look written down as data: palette, per-area palettes,
weathering, dimensions, painted material layers, glTF material recipes, atmosphere values,
triangle budgets and lint tolerances. The kit's style tools read it, so they work for the
iamar look and for any custom look alike (vision principle 4: engineering practices apply
to every world, style practices belong to a profile).

| Path | What it is |
|---|---|
| `schema/style.schema.json` | The format (JSON Schema, `"schema": "iamar-style/1"`) |
| `iamar/style.json` | The iamar profile, every value read from the city's code (cited per value, `the iamar browser source (not public)` 2116b91e) |
| `schema/examples/harbour_quarter.style.json` | Track A example: `"extends": "iamar"`, adds a harbour region, tightens the building budget |
| `schema/examples/desert_trading_post.style.json` | Track B example: a brand-new, non-medieval profile written from a style bible |
| `check_style.py` | Checks a profile; paints its materials into a world's `textures/` |
| `../tests/style/style_profile_test.py` | Tests (profiles pass, seeded mistakes fail, painting works) |
| `../lint/` | Style lint and screenshot comparison driven by a profile (`iamar-world lint`, `compare-shots`) |
| `gen/` | Style generators: masterplan house, convex-wing roof, door arch (`iamar-world style-gen`, an internal task) |
| `materials/`, `lighting/`, `variety/` | Other jobs: painted material library (A10, an internal task), tested lighting presets (A3, 2981), anti-repetition (A9, 2987) |

## Using a profile in a world

1. **Track A (iamar-family):** put a `style.json` in the world folder with
   `"extends": "iamar"` and only what differs (a new region, tighter budgets).
   **Track B (brand-new look):** write a whole profile from the style bible
   (`kit/interview/tracks/`), like the desert example.
2. Check it: `python3 kit/style/check_style.py worlds/my_world/style.json`.
   It refuses unknown material layers, scene fields that do not exist in
   `docs/WORLD_FORMAT.md` 4.1, budgets looser than the parent profile's, malformed
   colours, black or missing-texture pink in the palette, and (for a profile that
   declares `sources`) any colour without a source.
3. Paint its materials:
   `python3 kit/style/check_style.py --paint worlds/my_world/.build/painted --profile worlds/my_world/style.json [--size 512] [--only roof_slate,wall_plaster]`
   writes one seamless `<material>.png` per `materials.layers` entry (256 px per metre at
   1024 px, 4 m per tile: in Blender 1 UV unit = 4 m), tinted to the profile's colour, and
   `style_materials.json`. Use them as Base Color, then bake light (`kit/blender/`).
   Point `--paint` at the world's `.build/` folder, not at the world folder itself: painted
   maps are build inputs, not world content, and anything written into the world folder gets
   packed into the package download (the harbour blind test painted 18 PNGs, ~12 MB, into
   the world folder before moving them). Directories whose names start with `.` are not
   part of a package (`docs/WORLD_FORMAT.md` section 1).
4. Copy the profile's `atmosphere.presets.<name>.environment` into `scene.json`
   `environment`. The iamar values are the city's own (`tested: false`: the city uses a
   filmic tonemap, a package a linear one); tested package presets come from A3.
5. `material_recipes` restates the city's shader looks (stone, water, night glow) as what
   a glTF can carry, because a package cannot ship shaders.
6. Lint against it: `iamar-world lint worlds/my_world` (the world's own `style.json`, else
   `--style iamar`) and compare before/after shots with `iamar-world compare-shots`
   ([`../lint/README.md`](../lint/README.md)). `lint`, `dimensions` and `budgets` are their
   tolerances; the review gate scores 60/40 Beauty/Efficiency on top.

## Generators

`generators` in a profile says what can be built for that look and with which command.
For iamar: `iamar-world style-gen house|roof|arch` ([`gen/README.md`](gen/README.md): the
masterplan house with its dressing (quoins, jetties, oriels, corner towers), the convex-wing roof
and the round door arch, closed, culled and audited, from any profile and region),
`iamar-world assets building ... --style plaster|stone|brick` (the simpler Oakhaven town
builder) and `--paint` above.

Two look-level gaps every world must dress (AGENT_KIT step 6, with a shot CHECK for each): the
built-in portal visual is a plain grey frame, so place a `style-gen arch` at each portal; and
terrain beyond the playable area is a flat colour band, so give it a texture, a sea wall or
cliff at the edge, or a distant backdrop.

## Rules of thumb that are style, not engineering

From the iamar profile (see its `weathering`, `atmosphere.rules`, `materials.paint_rules`):
weather every base colour by role (walls 0.5 x saturation, 0.96 x value ...); give each object
a small shift and never repeat a neighbour's tint; keep the warmth in the sun and surfaces and
the fog cool and light (a warm fog tinted the valley yellow: FAILED, MASTERPLAN_TODO B15);
nothing pure black (iron is `#4d5157`).
