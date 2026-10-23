# Question set: Town or district (`town`)

Written by swarm project `iamar-creator-knowledge` (an internal task, I3). A town, a village or a district; also an extension of the iamar city (a harbour quarter, a market street).

Run this after the common opening (`../common.md`) and the routers (`../PROTOCOL.md`, sections 4 and 5).
Same rules: 2 to 4 questions at a time, a default and examples on every question, "you choose" is valid, record each answer as `chosen` or `default`, no build before approval.

## 1. Questions

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| T1 | How big is it: a single street, a hamlet, a district, a whole town? | A hamlet of about 20 buildings | one street; 20 houses; four quarters |
| T2 | Where is it: next to an existing iamar quarter, on the coast, on a hill, on a river? | Beside the city, on flat ground with a river on one side | edge of the city by the sea; hill village |
| T3 | What buildings must it have (inn, market, chapel, harbour, houses, workshops)? | Houses, one inn, one market square, one landmark | an inn, 3 shops, a chapel |
| T4 | What is the one landmark visitors will remember from far away? | A tower or a harbour light | clock tower; lighthouse; a giant tree |
| T5 | Who lives here, and what do they do all day? | 6 villagers with simple daily routines | a fisher, a baker, a guard |
| T6 | How do visitors move in: walk only, ride, boat? | Walk | horses in the stable; a ferry |
| T7 | Does it connect to the city by a road, gate or portal? | A gate on the city side | portal in the market; road to the south gate |

Answer ids in the brief use these numbers (for example `T1`).

## 2. Traps and checks for this type

- Houses vary per street: never the same facade twice in a row (anti-repetition lint).
- Every building is closed (no gaps, no hidden faces built): run the closure audit before paint.
- The landmark is visible from the spawn point and from the main approach: check with a fixed eye-height shot.
- Villager count is capped by the tier: more than 20 animated characters breaks the low tier (flag F2).

## 3. Reuse

Search the catalogue for houses per quarter, trees, fences, lamps, bridges and boats before modelling.

## 4. What goes into the brief

- `type`: `town`. Typical `features` kinds: `npc`, `quest`, `script`.
- `checkpoints`: greybox, scale check, paint.
- Budgets come from the tier target (`../PROTOCOL.md`, section 6); do not raise them to fit the idea.

## 5. Worked example and dry run

Persona: Mira, a retired teacher, wants a place for her grandchildren; no Blender, no GPU.

The brief written from this interview is `examples/town/brief.json` (readable twin `examples/town/world.brief.md`).
It passes `python3 kit/interview/schema/brief.py check kit/interview/types/examples/town/brief.json --md kit/interview/types/examples/town/world.brief.md --approved`.
The dry run in `kit/tests/interview/types_test.py` loads it, checks that every answer id exists in the table above and validates it.
