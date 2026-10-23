# Question set: Social hub (`social`)

Written by swarm project `iamar-creator-knowledge` (an internal task, I3). A place for meeting people: a plaza, a lounge, a stage, with events.

Run this after the common opening (`../common.md`) and the routers (`../PROTOCOL.md`, sections 4 and 5).
Same rules: 2 to 4 questions at a time, a default and examples on every question, "you choose" is valid, record each answer as `chosen` or `default`, no build before approval.

## 1. Questions

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| S1 | What do people do together here: talk, play, watch, trade? | Talk and watch events | a lounge; a stage with a screen |
| S2 | How many at once, at the busiest? | 20 | 10; 50 |
| S3 | Where do they gather, and is there a stage or a screen? | A plaza with a stage | a campfire; a bar |
| S4 | Do they need chat, voice, emotes, name tags? | Chat and name tags | voice; emotes |
| S5 | Are there recurring events, and who runs them? | One host, one event a week | none |
| S6 | How do newcomers find their way? | A welcome board near the spawn | a guide NPC |
| S7 | Who moderates, and what are the rules? | The owner moderates; a rules sign at the entrance | none, friends only |

Answer ids in the brief use these numbers (for example `S1`).

## 2. Traps and checks for this type

- Concurrency decides hosting: a public hub of over 30 visitors needs stronger hosting than one's own computer (flag F1).
- Keep the plaza readable at distance: wayfinding signs and a clear focal point.
- Many avatars cost frames: use the crowd budget of the tier, not the maximum.
- Moderation and rules are written in the brief; the kit does not provide an automatic moderator.

## 3. Reuse

Reuse benches, lamps, stage props and signage from the catalogue.

## 4. What goes into the brief

- `type`: `social`. Typical `features` kinds: `ui`, `script`, `npc`.
- `checkpoints`: greybox, scale check, paint.
- Budgets come from the tier target (`../PROTOCOL.md`, section 6); do not raise them to fit the idea.

## 5. Worked example and dry run

Persona: Jonah, a streamer, wants a lounge for his community; iamar technology but his own look.

The brief written from this interview is `examples/social/brief.json` (readable twin `examples/social/world.brief.md`).
It passes `python3 kit/interview/schema/brief.py check kit/interview/types/examples/social/brief.json --md kit/interview/types/examples/social/world.brief.md --approved`.
The dry run in `kit/tests/interview/types_test.py` loads it, checks that every answer id exists in the table above and validates it.
