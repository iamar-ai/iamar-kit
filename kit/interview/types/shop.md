# Question set: Shop or marketplace (`shop`)

Written by swarm project `iamar-creator-knowledge` (an internal task, I3). One shop or a whole market where goods are shown and visitors browse or buy.

Run this after the common opening (`../common.md`) and the routers (`../PROTOCOL.md`, sections 4 and 5).
Same rules: 2 to 4 questions at a time, a default and examples on every question, "you choose" is valid, record each answer as `chosen` or `default`, no build before approval.

## 1. Questions

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| H1 | What is sold, and how many different goods? | 12 goods in one shop | art prints; spices; furniture |
| H2 | Is anything really bought in the world, or is it a showcase? | Showcase only; link out to the real shop | real checkout |
| H3 | How are goods shown: shelves, stalls, a counter, a catalogue wall? | Shelves and a counter | stalls on a street |
| H4 | Who runs the shop, and what do they say? | One shopkeeper NPC | none |
| H5 | How do visitors learn a price or a detail? | An info board per good | hover label |
| H6 | How many shops, and how do they connect? | One shop | a market street |
| H7 | What is the brand look: colours, logo, tone? | The iamar look with a shop sign | brand palette |

Answer ids in the brief use these numbers (for example `H1`).

## 2. Traps and checks for this type

- Payments and credentials stay outside the world: link out, never collect card data in the kit.
- Each good is a catalogue entry (single object with a thumbnail): reuse before modelling.
- Signs and prices must be legible at eye height: use the sign recipe and a screenshot at 5 m.
- A market of many stalls repeats: apply the anti-repetition rules to stall roofs and goods.

## 3. Reuse

Search the catalogue for shelves, crates, baskets, signs and market props.

## 4. What goes into the brief

- `type`: `shop`. Typical `features` kinds: `npc`, `ui`, `script`.
- `checkpoints`: greybox, scale check, paint.
- Budgets come from the tier target (`../PROTOCOL.md`, section 6); do not raise them to fit the idea.

## 5. Worked example and dry run

Persona: Leila, who sells spices online, wants a showcase for her goods.

The brief written from this interview is `examples/shop/brief.json` (readable twin `examples/shop/world.brief.md`).
It passes `python3 kit/interview/schema/brief.py check kit/interview/types/examples/shop/brief.json --md kit/interview/types/examples/shop/world.brief.md --approved`.
The dry run in `kit/tests/interview/types_test.py` loads it, checks that every answer id exists in the table above and validates it.
