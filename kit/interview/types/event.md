# Question set: Festival or event (`event`)

Written by swarm project `iamar-creator-knowledge` (an internal task, I3). A one-off or recurring event: a festival, a wedding, a concert, a launch.

Run this after the common opening (`../common.md`) and the routers (`../PROTOCOL.md`, sections 4 and 5).
Same rules: 2 to 4 questions at a time, a default and examples on every question, "you choose" is valid, record each answer as `chosen` or `default`, no build before approval.

## 1. Questions

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| V1 | What is the event, when, and for how long? | One evening, 2 hours | a wedding; a harvest fair |
| V2 | How many guests, and do they come at once? | 40 guests, all at once | 10; 100 |
| V3 | What happens, in order (a running order)? | Welcome, show, dance | speech; fireworks |
| V4 | What decorations, lights and sounds does it need? | Lanterns and music | fireworks; banners |
| V5 | Is it live-hosted, or self-running? | Live host | self-running |
| V6 | Is the world kept afterwards or taken down? | Kept for a week | one night only |
| V7 | What souvenir or memory do guests keep? | A screenshot spot | a guest book |

Answer ids in the brief use these numbers (for example `V1`).

## 2. Traps and checks for this type

- A crowd at one time is the worst case: size the world and hosting for the peak, not the average (flag F1).
- Fireworks and particles cost frames: cap particle counts for the lowest tier and test it.
- Time-limited events need a schedule in the brief: the date, the start and the end.
- Music and voice are the host's: the kit does not supply licensed music.

## 3. Reuse

Reuse lanterns, banners, tables and the plaza pieces from the catalogue.

## 4. What goes into the brief

- `type`: `event`. Typical `features` kinds: `script`, `audio`, `ui`.
- `checkpoints`: greybox, scale check, paint.
- Budgets come from the tier target (`../PROTOCOL.md`, section 6); do not raise them to fit the idea.

## 5. Worked example and dry run

Persona: Kenji, who organises a neighbourhood party, wants an online lantern night.

The brief written from this interview is `examples/event/brief.json` (readable twin `examples/event/world.brief.md`).
It passes `python3 kit/interview/schema/brief.py check kit/interview/types/examples/event/brief.json --md kit/interview/types/examples/event/world.brief.md --approved`.
The dry run in `kit/tests/interview/types_test.py` loads it, checks that every answer id exists in the table above and validates it.
