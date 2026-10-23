# The independent review gate

Written by swarm project `iamar-creator-knowledge` (an internal task, A2). Read this if you are the
**reviewer** of an iamar world (or of a change to one). The author of the work never passes
their own work. You are a second agent in a **fresh context**: you know the brief and the
rules below, not the author's reasoning.

Why this exists (lessons from building the iamar city): a stream that looked terrible passed
a quality check because the author judged their own shots; designed creatures and gate guards
passed their own tests while **missing from the game**, because the tests called the module
directly. A review that looks at the real world, with numbers, by someone else, is what caught
them.

## 1. Rules of the gate

1. **Independence.** You did not write or edit what you review. Do not take the author's word,
   summary or screenshots as evidence; produce your own.
2. **Judge the real world.** Open the world the way a visitor does (`iamar-world preview`, the
   browser with the packed world, or the hosted address) and look at **that**. A shot from the
   author's test script, or a tool that calls a module directly, is not proof the thing is in
   the game. For every object, creature, NPC, sign or effect the brief promises: find it in the
   real world, or fail it.
3. **Numbers and pictures together.** Every verdict cites a triangle count or measurement and a
   screenshot name. No "looks fine".
4. **Say what kind of picture it is.** State whether an image is the full-detail source or the
   game mesh at its tier, and the time of day and tier it was taken at.
5. **Do not fix.** Report. The author fixes and asks again. (If you also write fixes you become
   the author and lose independence for those fixes.)
6. **Never pass what you could not see.** "Not verified" is a valid, honest result; it is not a
   PASS.
7. **Software rendering is slow.** Frame rates from a software renderer or an emulated GPU are
   not comparable to a real GPU; triangle and draw counts are.

## 2. What you are given and what you must ask for

Given: the world folder (or packed world), the approved design brief (`world.brief.md` /
`brief.json`, see `kit/interview/`), and the style profile (`iamar` for Track A, the world's own
`style.json` for Track B).

Ask for nothing from the author except missing files. If the brief is absent, stop: there is
nothing to judge against.

## 3. Procedure

### 3.1 Numbers (before you look)

Run these and keep the output:

```bash
iamar-world validate worlds/my_world                  # every ERROR and WARN
iamar-world techniques worlds/my_world                # what the browser applies by itself, and its ADVICE lines
iamar-world perf worlds/my_world /tmp/review          # preview run that also checks the hard targets
iamar-world lint worlds/my_world --style <profile>    # style lint (palette, scale, budgets, repetition)
```

(`lint` and `compare-shots` are described in `kit/lint/README.md`; they work for Track A and
Track B alike because they read the world's style profile.) Record: triangles per distinct model
and per LOD, texture sizes, the visible-frame triangle and draw totals, each tier's budgets
(`docs/WORLD_TIERS.md`), and any ERROR or WARN.

Setup the commands need (found in the dry run of 2026-10-20, `docs/reviews/2026-10-20-an agent-reviewer-gate-dry-run.md`):
- `validate`, `techniques` and `lint` need the developer kit, and the kit needs an iamar browser
  that has the kit commands: set `IAMAR_BROWSER` to that build (an older one starts the game
  instead) and `IAMAR_KIT_PACK` to a kit pack (`tools/build_pack.sh` in iamar-kit, headless Godot).
- `preview`, `perf` and `shots` open the browser: run them under `offscreen`, never on `:0`.
- A software renderer (offscreen) gives frame times that are not comparable: record the frame
  row as "not verified" there, and take frame time on a real GPU host.
- No brief, no verdict: a world without `world.brief.md` / `brief.json` gets numbers and pictures
  only, and no score.

### 3.2 Pictures (then look)

Take, in the real world, at each tier the brief targets (`--tier low|medium|high|ultra`):

- the **spawn view** and the **eye-height views** around the world: use
  `iamar-world preview <world> <out> --view "x,y,z>lx,ly,lz"` with the camera at about 1.7 m,
  at a street, at a landmark, at the portal and along the main route;
- a **close-up** (about 1.7 m, the object fills the frame) and a **mid-distance** shot (about
  15 m) for every distinct model class: house type, prop family, creature, statue, tree;
- a **far** view that shows the skyline and the edges of the world;
- **day, dusk and night** if the brief has a time of day or lights: `iamar-world shots <world>
  <out>` renders the world's fixed cameras (`shots.json`, or your own with `--cameras FILE`) at
  all three and writes a review sheet per camera and time with triangles and draw calls
  (`kit/shots/README.md`).

- **play** every quest and scripted interaction the brief promises: `iamar-world playtest
  <world> <out> --steps steps.json` enters the real world as a visitor, plays the steps (talk,
  choose, pick up, use a script entity, go to a trigger) and prints each quest's state, what the
  world's scripts changed (moved, light, sound, note) and a shot per step
  (`kit/playtest/README.md`). Write the steps yourself from the brief, not from the author's
  files. A quest that does not reach `done`, or a promised effect with no `EFFECT` line, is a
  FAIL of "present in the real world".

Look at **every** picture. Then compare against the references: for Track A the city's own
shots at the same camera and time (`iamar-world compare-shots <before> <after>` pairs two shots
from the same camera); for Track B the style bible's concept images.

### 3.3 Per-mesh table

For each distinct mesh or model class fill one row (this is the format the city's own review
used):

| Mesh | Tris (per LOD) | What carries the detail | Close / mid shot | Verdict | Why / what to change |
|---|---|---|---|---|---|

Detail key: **S** silhouette from geometry, **P** a shared tiled pattern or vertex colour,
**T** a painted texture of its own, **N** a normal map, **Sh** a dedicated shader.
Verdict: **PASS**, **PASS (minor)** (list the minor items) or **FAIL**. A FAIL blocks "done".

### 3.4 Checklist (answer every line, yes / no / not verified)

Visibility and closure:
- Everything a visitor can see is closed: no missing side, crack, gap at a join, open underside,
  paper-thin geometry?
- Nothing a visitor can never see has polygons (hidden backs, undersides below eye height,
  insides of solid stands)?
- Holes are openings, not gaps: every door, gate, arch, window, stair and path is open, framed
  and leads somewhere, and no closure fix blocked a planned path?
- No flickering overlap or z-fighting visible from any review camera?

Look:
- Scale is right (a person about 1.8 m, a door about 2.1 to 2.2 m)?
- Detail comes from painted texture, baked light and normal maps, not from extra triangles;
  triangles sit where the silhouette needs them?
- No flat untextured colour, plastic or chrome materials, black or pink surfaces?
- Shapes are chunky and readable at distance; the skyline is not flat; there is a clear focal
  landmark and the first ten seconds after arrival are inviting?
- No two neighbours look alike (window rhythm, roof pitch, tint), and scattered props are not
  copy-pasted?
- Light is believable: warm and cool contrast, baked shadow without seams, and every time of day
  you shot is readable (no near-black areas)?
- The lowest declared tier still looks complete and not broken?

Fit to the brief:
- Every feature, NPC, quest, sign and effect the brief promises is **present in the real
  world** (state where you found it)?
- Every budget in the brief is met (triangles, textures, download size), per tier?
- Every default the author chose is one the user was shown and accepted (see the brief's
  `answers`)?

Track A only (the iamar look): palettes, weathering, stone ground floors, jetties, roof
proportions (a roof is one third to one half of a building's height), arches, and the quarter
atmosphere match the style profile and the references. A long flat wall with no arch is a FAIL
in this track.

## 4. Scoring

Two scores, each 0 to 100, combined with fixed weights (the maintainer, 2026-10-10):

**Score = 0.6 x Beauty + 0.4 x Efficiency**

**Beauty** is your judgement against the art bar: look clearly better than a well-known
stylised fantasy MMO and leave visitors impressed, with a very low polygon count. Anchors:

| Beauty | Reads as |
|---|---|
| 90 to 100 | Clearly beyond the bar: rich painted detail, strong silhouettes, coherent colour and light; players would stop to look |
| 70 to 89 | At the bar in places; a few plain or thin objects; light and colour mostly convincing |
| 50 to 69 | Clean and correct but plain: flat colour, thin shapes, little painted detail |
| 30 to 49 | Visible defects: gaps, flat walls, plastic look, repetition |
| 0 to 29 | Broken or unreadable |

**Efficiency** is 100 at or under the asset's triangle budget (LOD0); above it,
100 x budget / triangles (25 % over budget gives 80). Budgets to use (from the city's art bar;
the brief may state its own, which then win): playable character with head, hair and outfit 12k;
face and head 2.5k; hair 1.5k; ordinary building 3k (a house 1k to 3k); landmark 15k; prop 300;
creature 6k and a hero creature 10k; hero statue about 8k; a visible frame well under 1M
triangles including shadows. Score each distinct asset class, then give the weighted average
over what is visible in the real world.

**Decision rules.**
- A **change** to an existing world is accepted only if it **raises** the weighted score. Report
  Beauty, Efficiency and the weighted score before and after, and the triangles per LOD for what
  changed. An improvement that costs many triangles is not done until texture carries it.
- A **new world** (for example a blind test) passes at a weighted score of **70** or more on
  every track, with no FAIL row, every budget met and every promised feature found in the real
  world. The threshold is the maintainer's proposal and may be changed by him; read the swarm vision for
  the current value.

## 5. The report

Write the report to `docs/reviews/<date>-<your-agent>-<slug>.md` (the ledger described in
`kit/inventory/LAYOUT.md`) and give the author a copy. Use this shape:

```markdown
# Review: <world or change>, <date>, reviewer <agent>

Reviewed: <world folder / address / commit>, tier(s) <...>, track <A|B|C>, brief <path>
Pictures: <list of file names; for each: full-detail or game mesh, tier, time of day>

## Verdict: PASS | PASS (minor) | FAIL
Beauty <n>, Efficiency <n>, weighted <n> (before: <n> if a change)

## Numbers
<triangles per class and LOD, texture sizes, visible-frame totals, validate/lint/perf output summary>

## Per-mesh table
<table from section 3.3>

## Checklist
<every line from 3.4: yes / no / not verified, with where you looked>

## Not verified
<what you could not see or measure, and why>

## Next gaps (ranked)
1. <the biggest gap, with the place and picture>
2. ...
3. ...
```

The **ranked list of next gaps** is mandatory even on a PASS: a review that passes everything
and names nothing teaches the author nothing, and the art work must never run dry while the bar
is not met.

## 6. A prompt you can give the reviewer agent

```text
You are the independent reviewer of an iamar world. You did not build it. Read
kit/review/REVIEWER.md and follow it exactly. You have: the world folder <path>, the approved
brief <path>, and the style profile <id or path>. Run the numbers (validate, techniques, perf,
lint), look at the real world at the tiers the brief targets (eye-height views, close-ups,
mid-distance, far; day, dusk and night where the brief has them), and look at every picture.
Fill the per-mesh table and the checklist, score Beauty and Efficiency (60/40), and write the
report to docs/reviews/. Do not fix anything. Do not accept the author's screenshots or summary
as evidence. Say "not verified" rather than guessing. End with a ranked list of the next three
gaps.
```

## 7. Status

Written from the city's own review practice (the per-mesh review, the standing art review gate
and the art bar). The kit commands named above exist at the time of writing (`validate`,
`techniques`, `perf`, `preview`, `lint`, `compare-shots`, and the fixed-camera `shots`, job A1).
A dry run of the commands on the kit starter (2026-10-20, an agent) checked the tool path; it had no
brief, so it gave no verdict. A real verdict on a briefed sample world is still owed to the blind tests (job T1).
