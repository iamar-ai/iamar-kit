# Tracks: iamar-family, brand-new, hybrid

Written by swarm project `iamar-creator-knowledge` (an internal task, I4). The track router is stage 3
of the design interview (`../PROTOCOL.md`, section 5). This folder holds what you do after the
user answers.

| File | What |
|---|---|
| `README.md` (this file) | The router question, the decision table, the Track C decision |
| `track_a.md` | Track A: an iamar-family world, step by step, with a check at every step |
| `track_b.md` | Track B: a brand-new world: write a style bible, turn it into `style.json`, then build |
| `style_bible_template.md` | The style bible to fill in with the user (Track B, and Track C) |

## 1. Two layers (why there are tracks)

**Engineering practices apply to every world, every track:** triangle and texture budgets,
visible-faces-only, closure, LODs, baked light and AO, hardware tiers, packaging and signing,
performance checks, the independent review gate.

**Style practices belong to a look.** For the iamar look they are the palettes, weathering,
stone ground floors, jetties, roof proportions, arches and the 13 painted materials, all written
down as data in `kit/style/iamar/style.json`. A track decides **which style profile the world is
checked against**:

| Track | The world is checked against | Where the profile comes from |
|---|---|---|
| A (iamar-family) | the `iamar` profile, or a profile that `extends` it | `kit/style/iamar/style.json`; a world adds only what differs |
| B (brand-new) | the world's own `style.json` | written with the user from a style bible |
| C (hybrid) | the world's own `style.json` | see section 3 |

`iamar-world lint` and `iamar-world compare-shots` read the profile, so the same two commands
serve every track (`kit/lint/README.md`); `kit/style/check_style.py` checks the profile itself.

## 2. The router question

Ask once, in plain words (it is also question B3 of `../common.md`):

> Should this world feel like iamar's city, build on iamar but look different, or be
> completely its own?

If the user is unsure, **show, do not describe**: three screenshots of the city (a street, a
landmark, the skyline: `../../gallery/city/`, one set per quarter) and three contrasting looks (any three from the style examples or the
user's own references; `python3 kit/gallery/contact_sheet.py styles OUT.png` makes the palette-card sheet, ready-made in `kit/gallery/styles/style_cards.png`), and ask them to point. Never ask them to name a game or film to copy; ask
for the feeling and the world's own rules (`../PROTOCOL.md`, rule 10).

| The user says | Track | Open |
|---|---|---|
| "like the city", "same style", "an extension of the city" | **A** | `track_a.md` |
| "completely different", "my own", "a sci-fi station", "a desert town" | **B** | `track_b.md` |
| "your engine and quality, but a different look", "the city's feel in another setting" | **B** (see section 3) | `track_b.md` |

Signs that the answer is wrong, check before you commit to a track:
- Track A but the theme is not medieval (a space station, a desert market): conflict flag F5 in
  `../common.md`. Offer Track B and say why: the iamar kit's looks are medieval and will not match.
- Track B but the user wants visitors to walk between the iamar city and the world and feel no
  seam: ask whether the portal arrival area should be Track A (a small matching threshold) while
  the rest is Track B. The two can coexist: one profile per world, so the threshold is a
  separate small world or a region of a Track A profile.

## 3. Track C (hybrid): decision

**Track C is folded into Track B.** "iamar technology with a different look" needs exactly
Track B's work (a style bible and its own `style.json`) and exactly Track A's engineering
practices, which apply to both anyway. A separate track would have no steps of its own.

What Track C users get inside Track B:
- the engineering layer of the kit is unchanged: `../common.md` budgets and conflict flags,
  Blender tools, the catalogue (objects tagged for the user's style, or neutral), the review gate;
- the user may borrow **neutral** catalogue objects (rocks, trees, animals, simple props) and
  re-tint them through the profile's palette (scene.json objects `"tint": "#rrggbb"` — browser
  03032d78 and later; refused by the pinned kit runtime 0bef8c6d, see `kit/runtime.lock` — a multiply:
  light and grey objects take any palette colour, dark ones only get darker; for those export the
  model and recolour the copy), but not city buildings, which carry the iamar look;
- an `extends` of `iamar` is allowed in the profile if the user wants to keep part of it (for
  example the `dimensions` and `lint` values) and replace the rest; everything not restated is
  inherited, and budgets may only be tightened, never loosened (`kit/style/README.md`).

the maintainer decides whether Track C stays folded; this is the swarm's default (swarm vision, job I4).

## 4. What every track produces

By the end of a track the world folder contains: `scene.json` and assets, `style.json` (Track
B, and Track A when the world adds a region or tightens a budget), `world.brief.md` and
`brief.json` (the approved brief), the screenshots taken at each checkpoint, the lint output, and
the review report (`../../review/REVIEWER.md`).
