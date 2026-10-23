# Question set: Gallery or museum (`gallery`)

Written by swarm project `iamar-creator-knowledge` (an internal task, I3). A place that shows exhibits along a route: art, objects, photos, text.

Run this after the common opening (`../common.md`) and the routers (`../PROTOCOL.md`, sections 4 and 5).
Same rules: 2 to 4 questions at a time, a default and examples on every question, "you choose" is valid, record each answer as `chosen` or `default`, no build before approval.

## 1. Questions

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| G1 | What is on show, and how many pieces? | 12 paintings | sculptures; photographs; timelines |
| G2 | Where do the pieces come from (files the user supplies), and is rights clearance done? | User-supplied images, rights are the user's | scans; renders |
| G3 | What route do visitors take: free, guided, one-way? | A guided one-way loop | free walk |
| G4 | How is each piece lit and labelled? | Wall light and a plaque | spotlights; audio guide |
| G5 | What building holds it: a hall, a courtyard, open air? | A hall with two wings | a courtyard |
| G6 | Is there a focal piece or a finale? | One centrepiece | none |
| G7 | Is there audio or narration? | Optional short audio | none |

Answer ids in the brief use these numbers (for example `G1`).

## 2. Traps and checks for this type

- Exhibit images are textures: budget their sizes (texture_bytes) and share an atlas where possible.
- Rights of the exhibits are the user's: record the source for each piece in the brief; never import unknown images.
- Plaque text is legible at 2 m: take an eye-height shot per room.
- Lighting is baked: place baked wall lights and check the dark-bake audit.

## 3. Reuse

Reuse frames, plinths, benches and lamps; model only the hall.

## 4. What goes into the brief

- `type`: `gallery`. Typical `features` kinds: `ui`, `script`, `audio`.
- `checkpoints`: greybox, scale check, paint.
- Budgets come from the tier target (`../PROTOCOL.md`, section 6); do not raise them to fit the idea.

## 5. Worked example and dry run

Persona: Ana, a painter, wants a gallery for her watercolours.

The brief written from this interview is `examples/gallery/brief.json` (readable twin `examples/gallery/world.brief.md`).
It passes `python3 kit/interview/schema/brief.py check kit/interview/types/examples/gallery/brief.json --md kit/interview/types/examples/gallery/world.brief.md --approved`.
The dry run in `kit/tests/interview/types_test.py` loads it, checks that every answer id exists in the table above and validates it.
