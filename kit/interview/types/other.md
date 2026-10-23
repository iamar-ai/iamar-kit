# Question set: Other (sci-fi, vehicle, abstract) (`other`)

Written by swarm project `iamar-creator-knowledge` (an internal task, I3). Anything that fits no other type: a space station, a ship interior, an abstract space.

Run this after the common opening (`../common.md`) and the routers (`../PROTOCOL.md`, sections 4 and 5).
Same rules: 2 to 4 questions at a time, a default and examples on every question, "you choose" is valid, record each answer as `chosen` or `default`, no build before approval.

## 1. Questions

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| O1 | In one sentence, what is it, and why does it not fit the other types? | (no default: ask again) | a space station; a living ship |
| O2 | What is the main way to move or feel in it? | Walk | float; ride; fly |
| O3 | Which rules differ from the iamar world (gravity, scale, time)? | None, ordinary walking | low gravity; tiny scale |
| O4 | What are the two or three things to see or do? | Two things to see, one thing to do | a viewing deck |
| O5 | Which existing type is closest, so I can borrow its questions? | The closest from the router | interior; nature |
| O6 | What look and sound? | A clean, original look; ask for the feeling and rules | neon; organic |
| O7 | What must the kit not be asked to do (limits)? | Nothing beyond the tier | no AI generation |

Answer ids in the brief use these numbers (for example `O1`).

## 2. Traps and checks for this type

- If the world needs a movement mode the kit lacks, record it as a limit in the brief; do not hack the engine silently.
- Borrow the question set of the closest type for the rest; state which one in the brief (extra_types).
- Custom look means Track B or C with a style.json; the engineering layer still applies in full.
- Check the greybox with the user before any paint: unusual worlds are easy to misread.

## 3. Reuse

Search the catalogue by description; reuse neutral props.

## 4. What goes into the brief

- `type`: `other`. Typical `features` kinds: `script`, `audio`.
- `checkpoints`: greybox, scale check, paint.
- Budgets come from the tier target (`../PROTOCOL.md`, section 6); do not raise them to fit the idea.

## 5. Worked example and dry run

Persona: Mei, a sci-fi author, wants a station to show her readers.

The brief written from this interview is `examples/other/brief.json` (readable twin `examples/other/world.brief.md`).
It passes `python3 kit/interview/schema/brief.py check kit/interview/types/examples/other/brief.json --md kit/interview/types/examples/other/world.brief.md --approved`.
The dry run in `kit/tests/interview/types_test.py` loads it, checks that every answer id exists in the table above and validates it.
