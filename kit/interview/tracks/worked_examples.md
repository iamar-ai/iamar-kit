# Worked examples: one per track

Both examples exist as real profiles and pass `python3 kit/style/check_style.py <file>` (checked
2026-10-20). They show what the track documents produce.

**Honest note:** the example files hold only the profile (the output). The user requests and the
"decided" and "answer" columns below are **reconstructed for illustration** from what the profile
contains; rows marked (illustrative) are not in the profile file at all (greybox, reuse and
landmark choices). A real run records them in the brief and the style bible.

## Track A: the harbour quarter

File: `kit/style/schema/examples/harbour_quarter.style.json`. Persona request (invented for illustration): "Like the iamar
city, but by the sea" (interview persona Mira, `../common.md`, section 6).

| Step in `track_a.md` | What was decided | Where it shows |
|---|---|---|
| 1 Profile | `"extends": "iamar"`; one new region `harbour`: tarred timber `#3b3026`, weathered grey stone `#9a958c` on 70 percent of ground floors, teal trim `#2f6464`, boat paints (teal, blue, red, ochre, green, cream), cool fog `#b8c8d4` | `regions.harbour` |
| 1 Profile | Tighter budget: building at LOD0 2,800 triangles instead of the city's 3,000 | `budgets.triangles.building` |
| 2 Greybox (illustrative) | Streets on the city's grid (lanes 5 m), a quay, a lighthouse as the landmark | brief `checkpoints` |
| 3 Reuse (illustrative) | Boats, barrels, nets, benches from the catalogue; houses from `assets building house --style plaster` | brief `reuse` |
| 5 Light | The iamar golden-hour preset with the cool harbour fog tint | `atmosphere` inherited, `regions.harbour.fog_tint` |

What was **not** restated: palettes of the other quarters, weathering rules, dimensions, material
layers, lint tolerances. They come from the parent profile.

## Track B: the desert trading post

File: `kit/style/schema/examples/desert_trading_post.style.json`. Persona request (invented for illustration): "A dusty trading
post where caravans stop; it should feel hot, crowded and bright" (a brand-new, non-medieval look).

Style bible (the answers that became the profile):

| Bible section | Answer | Became |
|---|---|---|
| 1 Look | "Sun-baked adobe and indigo cloth under a hot white sky." Dry, crowded, warm | `name`, `description` |
| 2 Rules | Everything is mud brick and palm wood; stone only for gates and the well; cloth overhead everywhere | `materials.layers` uses: adobe walls, sandstone gates and well, palm wood beams |
| 3 Shape | Low, wide, rounded buildings; beams that stick out of the walls; silhouette: the caravanserai gate | `dimensions` (roof share 0 to 10 percent), anchor choice |
| 4 Palette | adobe `#d6b48a`, adobe dark `#a9835c`, sandstone `#c99d6a`, palm wood `#6b4a2e`, indigo `#2f3f78`, saffron `#d9962c`, sand `#e0c79a`, brass `#a8843e` | `palette` |
| 5 Zones | souk (shaded, awnings), caravanserai (open courtyard, cool well) | `regions` |
| 6 Weathering | Sun-bleached tops, sand-darkened bases; no neighbours share a wall tint or awning colour | `weathering` |
| 7 Scale | Person 1.8 m, door 2.0 to 2.4 m, storey 3.0 m, thick walls 0.45 m, alleys 2.5 m, souk lane 4 m, caravan road 9 m | `dimensions` |
| 9 Light | Noon heat: hot white horizon, blue-violet shadows so the sand does not go flat | `atmosphere.presets.noon_heat` (`tested: false`, see below) |
| 10 Budgets | Building 2,500, prop 300, character 12,000, creature 6,000 | `budgets.triangles` |

Notes from the example:
- The atmosphere preset is marked `tested: false`: its values come from the bible and have not
  been through the tested presets of job A3; check them with screenshots before relying on them.
- The profile has no `extends`: Track B uses the engineering rules of the kit, but judges
  style against itself. `iamar-world lint worlds/<world>` reads the world's own `style.json`.

## What these examples do not show

- A run of the full process on a real world: that is the blind tests (job T1) and the review dry
  run (job A2b), which produce the proof that a fresh agent can follow these documents.
- Track C: it is folded into Track B (`README.md`, section 3).
