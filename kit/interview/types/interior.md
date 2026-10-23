# Question set: Interior, hall or dungeon (`interior`)

Written by swarm project `iamar-creator-knowledge` (an internal task, I3). A hall, a house, a tavern, a dungeon or any enclosed space.

Run this after the common opening (`../common.md`) and the routers (`../PROTOCOL.md`, sections 4 and 5).
Same rules: 2 to 4 questions at a time, a default and examples on every question, "you choose" is valid, record each answer as `chosen` or `default`, no build before approval.

## 1. Questions

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| I1 | What is the room for, and how many rooms? | One main room plus one side room | a tavern hall; a three-level dungeon |
| I2 | How big is the main room in steps (so a visitor feels it)? | About 12 by 8 metres | a narrow corridor; a large hall |
| I3 | Where does light come from: windows, fire, lamps, magic? | Windows by day and a hearth | candles only; torches |
| I4 | What furniture and props, and which is the focus? | Tables, chairs, a hearth as the focus | a throne; a bar counter |
| I5 | How do visitors enter and leave? | One door to the outside | a trapdoor; a portal |
| I6 | Who is inside? | One innkeeper | two guards; nobody |
| I7 | Is it standalone or the inside of a building outside? | Inside of an outside building (shared door) | a separate world |

Answer ids in the brief use these numbers (for example `I1`).

## 2. Traps and checks for this type

- Interiors are baked: light comes from baked AO and a few real lights, never many dynamic lights.
- Walls get no hidden faces and doors are real openings: run the door and closure audits.
- Keep walls, ceilings and floors thick enough to show no light leaks: check the dark-bake audit.
- Furniture comes from the catalogue as single objects, not from a combined room mesh.

## 3. Reuse

Search the catalogue for furniture, lamps, doors and hearths.

## 4. What goes into the brief

- `type`: `interior`. Typical `features` kinds: `npc`, `script`, `audio`.
- `checkpoints`: greybox, scale check, paint.
- Budgets come from the tier target (`../PROTOCOL.md`, section 6); do not raise them to fit the idea.

## 5. Worked example and dry run

Persona: Priya, a game master, needs a tavern for her table-top group.

The brief written from this interview is `examples/interior/brief.json` (readable twin `examples/interior/world.brief.md`).
It passes `python3 kit/interview/schema/brief.py check kit/interview/types/examples/interior/brief.json --md kit/interview/types/examples/interior/world.brief.md --approved`.
The dry run in `kit/tests/interview/types_test.py` loads it, checks that every answer id exists in the table above and validates it.
