# Question set: Education world (`education`)

Written by swarm project `iamar-creator-knowledge` (an internal task, I3). A learning world with activities, a teacher and things to look at or do.

Run this after the common opening (`../common.md`) and the routers (`../PROTOCOL.md`, sections 4 and 5).
Same rules: 2 to 4 questions at a time, a default and examples on every question, "you choose" is valid, record each answer as `chosen` or `default`, no build before approval.

## 1. Questions

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| E1 | What is the subject, and the learning goal in one sentence? | Learners can name the parts of a cell | history of a harbour; physics lab |
| E2 | Who are the learners (age, level), and how many? | A class of 30 teenagers | adults; 10 children |
| E3 | What activities: explore, collect, quiz, build, discuss? | Explore and a short quiz | a lab experiment |
| E4 | Who is the teacher: an NPC, a live person, both? | A live teacher guided by signs | NPC guide |
| E5 | How is progress shown and by whom? | A checklist the teacher sees | no tracking |
| E6 | Do learners need accounts or names, and are children involved? | Names only, no personal data | anonymous |
| E7 | How long is one session? | 45 minutes | a single 10-minute visit |

Answer ids in the brief use these numbers (for example `E1`).

## 2. Traps and checks for this type

- Class size sets hosting: 30 learners need a hosting plan, not the teacher's laptop alone (flag F1).
- No personal data of learners in the world, the brief or the logs; the user decides on accounts outside the kit.
- Content must be correct: the user supplies or verifies the facts; never invent facts for a lesson.
- Keep text short and big: UI pages follow the UI recipe; check readability at the lowest tier.

## 3. Reuse

Reuse props, signs and NPC bodies; label objects in the world with the sign recipe.

## 4. What goes into the brief

- `type`: `education`. Typical `features` kinds: `ui`, `npc`, `script`, `quest`.
- `checkpoints`: greybox, scale check, paint.
- Budgets come from the tier target (`../PROTOCOL.md`, section 6); do not raise them to fit the idea.

## 5. Worked example and dry run

Persona: Dr. Ruiz, a biology teacher, brings a class of 30.

The brief written from this interview is `examples/education/brief.json` (readable twin `examples/education/world.brief.md`).
It passes `python3 kit/interview/schema/brief.py check kit/interview/types/examples/education/brief.json --md kit/interview/types/examples/education/world.brief.md --approved`.
The dry run in `kit/tests/interview/types_test.py` loads it, checks that every answer id exists in the table above and validates it.
