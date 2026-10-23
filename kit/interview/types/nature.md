# Question set: Nature or wilderness (`nature`)

Written by swarm project `iamar-creator-knowledge` (an internal task, I3). A forest, a meadow, a coast, a mountain or a lake with wildlife and paths.

Run this after the common opening (`../common.md`) and the routers (`../PROTOCOL.md`, sections 4 and 5).
Same rules: 2 to 4 questions at a time, a default and examples on every question, "you choose" is valid, record each answer as `chosen` or `default`, no build before approval.

## 1. Questions

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| N1 | Which biome: forest, meadow, desert, coast, mountain, wetland? | Temperate forest with a clearing | pine forest; mountain lake |
| N2 | What water is there: river, lake, sea, waterfall, none? | One river and a pond | a stream; a waterfall |
| N3 | Which animals live here, and which should flee the visitor? | Deer and birds that flee, fish that stay | deer; ducks; butterflies |
| N4 | Is there a path, and what is at its end? | One path to a viewpoint | a trail to a lake; no path |
| N5 | What does the season and light look like? | Late summer, golden hour | autumn; winter dusk |
| N6 | How far can visitors see: open vista or closed in by trees? | Closed forest with one vista | a valley view from the ridge |
| N7 | Is anything built here: a hut, a bridge, ruins? | A bridge and a hut | a stone bridge; none |

Answer ids in the brief use these numbers (for example `N1`).

## 2. Traps and checks for this type

- Trees come as batches or instances: never one mesh per tree; budget the instance count, not the tree.
- Ground cover and trees sway only if the cost fits the tier: check the wind recipe before promising it.
- Fog and far impostors hide the world edge: show a shot from the farthest walkable point.
- Terrain chunks load on a worker thread: avoid single-frame spikes (see the terrain recipe).

## 3. Reuse

Reuse the catalogue trees, flowers, rocks and creatures (deer, birds, fish, butterflies) first.

## 4. What goes into the brief

- `type`: `nature`. Typical `features` kinds: `npc`, `script`, `audio`.
- `checkpoints`: greybox, scale check, paint.
- Budgets come from the tier target (`../PROTOCOL.md`, section 6); do not raise them to fit the idea.

## 5. Worked example and dry run

Persona: Tomas, a hobby hiker, wants a calm place to relax; own style, 6-year-old laptop.

The brief written from this interview is `examples/nature/brief.json` (readable twin `examples/nature/world.brief.md`).
It passes `python3 kit/interview/schema/brief.py check kit/interview/types/examples/nature/brief.json --md kit/interview/types/examples/nature/world.brief.md --approved`.
The dry run in `kit/tests/interview/types_test.py` loads it, checks that every answer id exists in the table above and validates it.
