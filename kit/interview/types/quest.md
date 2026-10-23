# Question set: Quest or game (`quest`)

Written by swarm project `iamar-creator-knowledge` (an internal task, I3). An adventure with goals, NPCs, quests, rewards and a way to win or finish.

Run this after the common opening (`../common.md`) and the routers (`../PROTOCOL.md`, sections 4 and 5).
Same rules: 2 to 4 questions at a time, a default and examples on every question, "you choose" is valid, record each answer as `chosen` or `default`, no build before approval.

## 1. Questions

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| Q1 | What is the goal, in one sentence, and how does a visitor know they won? | Find three lost items and return them | defeat the dragon; escape the maze |
| Q2 | How long does one run take? | 20 minutes | 5 minutes; an evening |
| Q3 | Which NPCs give or take part in quests? | One quest giver and one helper | a merchant; a rival |
| Q4 | What can the visitor do: talk, pick up, use, fight, solve? | Talk, pick up, use | fight; puzzles |
| Q5 | What is the danger or friction, and how forgiving is it? | Gentle: no death, only retry | hard mode; timer |
| Q6 | Is progress saved, and for whom? | Saved per visitor | no save |
| Q7 | Single player or together? | Together, up to 4 | solo |

Answer ids in the brief use these numbers (for example `Q1`).

## 2. Traps and checks for this type

- Every quest step is a script with a test: write the quest as data, then run the quest check headless.
- The player must always know the next step: an in-world hint or a journal entry for every state.
- Do not hide required items behind a missed trigger: test the path from fresh start to the end.
- Combat or danger raises the animation budget: cap animated actors by tier (flag F2).

## 3. Reuse

Reuse NPC bodies, hair, clothing and prop pickups from the catalogue.

## 4. What goes into the brief

- `type`: `quest`. Typical `features` kinds: `npc`, `quest`, `script`, `ui`.
- `checkpoints`: greybox, quest walkthrough, paint.
- Budgets come from the tier target (`../PROTOCOL.md`, section 6); do not raise them to fit the idea.

## 5. Worked example and dry run

Persona: Dana, a game designer, wants a short desert quest to test.

The brief written from this interview is `examples/quest/brief.json` (readable twin `examples/quest/world.brief.md`).
It passes `python3 kit/interview/schema/brief.py check kit/interview/types/examples/quest/brief.json --md kit/interview/types/examples/quest/world.brief.md --approved`.
The dry run in `kit/tests/interview/types_test.py` loads it, checks that every answer id exists in the table above and validates it.
