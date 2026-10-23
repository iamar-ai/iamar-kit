# Track B: a brand-new world with its own look

For a world that is its own: a desert trading post, a space station, an underwater town, an
abstract gallery. The iamar **engineering** practices apply in full; the iamar **style** does
not, so before you build anything you and the user write down the look as a **style bible**,
turn it into a machine-readable `style.json`, and prove it on a few anchor assets. Use this
after the interview has chosen Track B or Track C (`README.md`, section 3).

**One approval, not two.** Interview the bible's core *before* the brief approval and put it in
the brief: the one-sentence look, the three words, the palette, the light and the three rules.
The user approves brief and core together (`../PROTOCOL.md`, section 8). The rest of the bible
(steps 1 to 4 below) is filled in after that approval and needs no second "yes"; only a change
to the approved core re-opens approval, for that part only.

Each step ends with a **check**.

## Step 1: write the style bible with the user

Fill in `style_bible_template.md` with the user, in small batches (the template's sections are
the batches). Ask about the feeling and the world's own rules, never "like <named game or
film>". Offer defaults and options, show candidate images, and record each answer as chosen or
default (as in the brief).

**Check:** every section of the bible is filled in or marked "not applicable", and it agrees
with the core the user approved with the brief (the one-sentence look, the palette, the three
words). If it does not, ask again for the changed part only.

## Step 2: reference images (original)

Make original concept images for the look: three to six pictures covering a street or open
space, a building, a prop, and a lighting mood. Sources, in order of preference: the user's own
sketches or photos; images you generate with an image model the user gives you a key for; or
rough Blender block-out renders. Do not trace or copy someone else's artwork.

Save them under `worlds/my_world/style/refs/` and list them in the bible.

**Check:** the user has pointed at the pictures that feel right and rejected the ones that do
not; the chosen ones are named in the bible.

## Step 3: turn the bible into `style.json`

Use the mapping below. Start from the Track B example
(`kit/style/schema/examples/desert_trading_post.style.json`) and keep only what your bible
states; leave a section out if the bible has nothing to say about it (the profile format
`iamar-style/1` has only `schema`, `id`, `name`, `description` as required fields).

| Style bible section | `style.json` field |
|---|---|
| One-sentence look, three words | `name`, `description` |
| Palette (named colours with hex, what each is for) | `palette` (each: `hex`, optional `pattern` = the material layer it is painted with) |
| Districts, biomes or zones with their own colours | `regions` (per zone: `mood`, `wall`, `timber`, `trim`, `paints`, `window_glow`, `lamp`, `fog_tint`, ...) |
| How surfaces age and vary | `weathering` (`roles` with saturation and value scales and jitter, and a `neighbour_rule`) |
| Scale and proportion rules | `dimensions` (person 1.8 m, doors, storeys, wall thickness, roof share, street widths) |
| Painted surfaces | `materials` (`layers`: layer, tint, where it is used; 256 px per metre, 4 m tiles) |
| Light and atmosphere | `atmosphere` (`presets` with `environment`, and `rules`) |
| Budgets | `budgets` (per asset class, at LOD0; you may only tighten the engineering budgets) |
| Tolerances you want the lint to enforce | `lint` (palette delta E, forbidden colours, saturation) |
| What can be generated for this look | `generators` |

Rules: no pure black and no missing-texture pink in the palette; use `"extends": "iamar"` only
if the user wants part of the iamar rules (Track C); give each colour a source (the bible
section or the reference image it came from) so it can be re-checked.

**Check:** `python3 kit/style/check_style.py worlds/my_world/style.json` passes.

## Step 4: anchor assets (prove the bible)

Build three small things before anything else, from the bible alone, at the target tier: **one
building (or the nearest equivalent), one prop, and one ground or wall surface**. Paint with
`python3 kit/style/check_style.py --paint worlds/my_world/textures --profile
worlds/my_world/style.json`, apply the lighting preset, and take shots at eye height (1.7 m)
and at 15 m (`iamar-world preview ... --view "x,y,z>lx,ly,lz"`).

If the anchors do not look like the reference images, **change the bible or the profile now**,
not after 200 objects exist.

**Check:** `iamar-world lint worlds/my_world` passes on the anchors; the user has seen the
anchor shots and said "yes, that is the world".

## Step 5: build the world

From here the process is Track A steps 2 to 7 (`track_a.md`), with these differences:
- the profile is your own, so `iamar-world lint` and `compare-shots` judge against **your**
  bible and anchors, not the city;
- reuse: search the catalogue and take **neutral** objects (rocks, trees, animals, simple props)
  and style-compatible ones; do not borrow city buildings, which carry the iamar look;
- a long flat wall, an arch or a medieval roof rule is not required: your bible's rules decide
  (the desert example has roofs at 0 to 10 percent of the building height on purpose);
- the engineering rules stay: every visible face closed, nothing unseen has polygons, openings
  are openings, detail from paint and baked light, budgets met per tier.

**Check:** as in Track A step 7: the review gate by a different agent, score at or above the
brief's threshold, no FAIL row, every budget met.

## Track B mistakes to avoid

- Building before the anchors are right: the whole world then repeats the mistake.
- A palette with too many colours: most good looks have four to eight named colours and a few
  accents.
- Copying a named game or film's look: ask for the feeling and the world's own rules.
- Borrowing medieval city buildings into a non-medieval world.
- Skipping the lint because "there is no iamar rule for this": the lint reads *your* profile.
