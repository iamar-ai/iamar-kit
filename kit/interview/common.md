# The common opening: questions every interview starts with

Written by swarm project `iamar-creator-knowledge` (an internal task, I1). Read `PROTOCOL.md` first
(the rules: small batches, defaults and examples, "you choose" allowed, no build before
approval). This file is stage 1 and stage 7 of the interview.

Ask in the four batches below. Offer the **default** with every question and record each
answer as `chosen` or `default` (see `PROTOCOL.md`, section 6).

## 1. Batch A: purpose and audience

| # | Question | Default if the user says "you choose" | Examples |
|---|---|---|---|
| A1 | In one sentence, what is this world for? | (no default: ask again with examples) | "A harbour village where my friends meet on weekends"; "A gallery for my paintings"; "A classroom for my biology course" |
| A2 | Who will visit, and how many at once? | A handful of friends, up to 10 at once | Just me; friends; a class of 30; anyone |
| A3 | Who may enter? | Friends only (buddies) | Private (me only); friends; public |
| A4 | How long will a typical visit last? | 15 to 30 minutes | A quick look; an evening; a whole lesson |
| A5 | Whose name goes on the world, and which hub account will host it? | Name: "<world title> makers" (built from the world's title, e.g. "Brightsalt Post makers"; say it in one line, the user can change it any time before publishing); account: none yet, the address stays `iamar://<owner>/<world>` until they sign in | "Maya Chen" on account `maya`; "Brightsalt game group" |

What the answers decide: A2 sets the load you plan for (see conflict flag F4); A3 sets the
hosting audience asked about later; A4 tells you how much there must be to do and see; A5 is
the `--author` of `iamar-world new` and the owner part of the world's address.

## 2. Batch B: mood and feel

| # | Question | Default | Examples |
|---|---|---|---|
| B1 | Which three words should visitors use to describe it? | (no default; offer six words to pick from) | cosy, mysterious, grand, playful, calm, eerie |
| B2 | What time of day and weather is it usually? | Golden hour, clear | Dawn mist; noon sun; dusk with lanterns; night with stars; rain |
| B3 | Should it feel like the iamar city, build on iamar but look different, or be completely its own? | Like the iamar city (Track A) | Show three screenshots of the city (`../gallery/city/`: a street, a landmark and the skyline per quarter) and three different styles and ask the user to point; this answer is the **track router** (`PROTOCOL.md`, section 5) |
| B4 | Is there anything it must not have or must not feel like? | Nothing special | No violence; nothing scary; no modern buildings |
| B5 | Who walks in your world: the standard iamar characters (visitors keep the avatar from their own iamar account), the same characters restyled by your world (costumes, palette), or characters you supply? | Standard iamar characters (visitors bring their own avatar; you build nothing for them) | Standard (human, elf, dwarf, gnome); restyled (everyone in lantern-festival robes); custom (you supply models: advanced, needs a 3D model of your own) |

B5 sets `characters` in the brief (`standard`, `restyled` or `custom`; `standard` if it is not asked).
Beginners should be offered only `standard` unless they ask for more; do not volunteer custom characters.
If B3 routed to Track B or C and B5 is `standard`, say in one line that the standard characters will
look different from the world and offer `restyled` or `custom`. This is advice only: it never blocks the build.

B3 is a routing question: after it, load the matching track document (`tracks/`). Never ask
the user to name a game or film to copy; ask for the feeling and the world's own rules.

## 3. Batch C: the user's own setup (decides the build tier)

Ask in plain words. Do not assume.

| # | Question | Default | Why it matters |
|---|---|---|---|
| C1 | Is Blender installed on the computer I build on? | Unknown: check with the kit (`iamar-world blender` reports what the kit finds) | Blender-tier tools (LODs, baking) need it |
| C2 | Does the computer have a strong graphics card (11 GB of video memory or more; the heaviest steps need about 19 GB), or can you run heavy AI generation at all? | No | Decides whether the optional GPU pipeline can run (statues and creatures from concept images). It is optional: without it you build with the Blender tier and the catalogue |
| C3 | Are you comfortable with scripts, or should I handle everything? | I handle everything | Decides how much you explain and how much you show the user |
| C4 | Which computers will visitors use? | A mix, including older laptops | Sets the lowest hardware tier to support (see section 4) |

### What the setup decides: build tiers

| Tier | You have | What you can reach |
|---|---|---|
| Tier 0 | Blender (or only the kit's built-in tools) | Clean, stylised worlds from the catalogue and the kit's tools. Props, houses, terrain. Plainer hero assets |
| Tier 1 | Tier 0 plus an image or 3D generation service the user pays for or supplies a key for | Better hero assets (statues, creatures) from original concept images |
| Tier 2 | Tier 1 plus a local GPU able to run the concept-to-mesh pipeline | The city's full pipeline; statue and creature quality closest to the city |

Tell the user which tier their answers put them in, and what it means for the result, **before**
you move on. If they want more than their tier reaches, say so and name the cheapest way up.

Do not confuse these **build tiers** (what the builder can make) with the **hardware tiers**
`low`, `medium`, `high`, `ultra` (what visitors' computers can run); the hardware tiers are
defined in `docs/WORLD_TIERS.md` and are chosen in stage 7 below.

## 4. Batch D: constraints (stage 7, ask after the type-specific questions)

| # | Question | Default | Notes |
|---|---|---|---|
| D1 | What is the lowest visitor computer this must run well on? | `low` (an older GPU at 30 fps, as in `docs/WORLD_TIERS.md`) | The package's own files are the `low` tier; richer tiers only add variants |
| D2 | How big may the download be? | About 100 MB in total (a rule of thumb you record as a number, not a platform limit) | No fixed package limit is documented in this kit; the host chooses the audience and upload limit when it starts hosting (`docs/SELF_HOSTING.md`). Visitors only fetch the files for their own tier (`docs/WORLD_TIERS.md`), so a rich `high` tier does not enlarge a `low` visitor's download |
| D3 | How good must it look? | As good as the iamar city at the same tier | State the art bar: detail from painted textures and baked light, not triangles |
| D4 | How much will you check along the way? | Screenshots after greybox, scale check and paint | These become the `checkpoints` in the brief |

## 5. Conflict flags: say it the moment you see it

When an answer collides with another, stop and name the conflict with the cheapest fix. Do not
quietly drop either side.

| Flag | Pattern | Say | Cheapest fix |
|---|---|---|---|
| F1 | Public audience and a tiny hosting setup | "Many visitors at once need your computer and connection to carry them" | Lower the expected number, or limit visitors, or host differently (see `docs/SELF_HOSTING.md`) |
| F2 | `low` tier target and very large scenes or many animated characters | "A low-tier computer cannot draw this many triangles or characters at once" | Reduce count in the low tier; keep the richer version for `medium` and above using `min_tier` clutter |
| F3 | Wants statue/creature quality of the city and is Tier 0 | "Hero assets of that quality need the concept-to-mesh pipeline" | Use catalogue objects, simplify, or add a generation service (Tier 1) |
| F4 | Classroom or event of 30+ visitors and an older host computer | "Thirty avatars and voices will strain this computer" | Split into sessions, lower the visual tier, or use a stronger host |
| F5 | Wants the iamar look (Track A) and a non-medieval theme | "The iamar style kit is medieval; a space station will not match it" | Switch to Track B or C and write a style bible |
| F6 | Wants huge outdoor scale and a small download | "Large terrain and big textures add up" | Reuse catalogue assets (referenced, not copied); lower texture sizes in `low` |
| F7 | Wants quests or scripts and the user is not comfortable with scripts | "Scripts are code that runs in a sandbox" | Keep it data-only (NPCs and quests are package data); add scripts only if needed |

Triangle and texture budgets are set per hardware tier in `manifest.json` (`budgets`:
`triangles`, `texture_size`, `texture_bytes`); the examples in `docs/WORLD_TIERS.md` (400,000
and 900,000 triangles for `medium` and `high`) are examples, not defaults. Per-asset targets
from the art bar: ordinary house 1k to 3k triangles, landmark 5k to 15k, creature 3k to 8k,
hero statue about 8k, a visible frame well under 1M triangles including shadows.

## 6. Worked dry run: a persona

Persona: "Mira", a retired teacher. She wants a small harbour village for her grandchildren and
friends. She has a laptop, no Blender, no GPU card, and knows nothing about scripts.

Condensed transcript (the agent's questions in bold, `[d]` marks a default):

1. **Batch A.** A1: "A harbour village where my grandchildren can explore and fish." A2: "Up to
   eight of us at once." (chosen) A3: "Just friends and family." (chosen: `buddies`) A4: "An
   afternoon." (chosen)
2. **Batch B.** B1: "cosy, colourful, calm" (chosen). B2: "Golden hour, clear" `[d]`. B3: Mira
   is shown three city screenshots and three other styles and points at the city's Herbalists'
   quarter: "Like that, but by the sea." (chosen: Track A, warm palette). B4: "Nothing scary."
   (chosen)
3. **Batch C.** C1: "No." (chosen: Blender will need installing, which the agent offers to
   guide). C2: "No." (chosen) C3: "You handle everything." `[d]` C4: "Probably old laptops."
   (chosen).
4. **Tier statement.** "You are Tier 0: I can build a cosy harbour village from the iamar
   catalogue and the kit's tools. Boats, houses and docks will be good; a hero statue like the
   city's gate statues would need an extra generation service."
5. **Routers.** Type: `town` primary, with a small `quest` element (fishing). Track: A.
6. **Batch D.** D1: `low` `[d]` (chosen because of old laptops). D2: about 100 MB `[d]`. D3: "As good as
   the city" `[d]`. D4: screenshots after greybox and paint (chosen: the
   user drops the scale check; the default is all three).
7. **Conflicts.** F1 not triggered (eight visitors). F2 not triggered. F3 does not apply (no
   hero statue). F5 not triggered (the theme fits Track A).
8. **Start of the brief** (written to `world.brief.md`):

```
vision:     A cosy harbour village for the family to explore and fish in.
audience:   family and friends, up to 8 at once, access: buddies
type:       town (primary), quest (fishing)
track:      A (iamar style profile, Herbalists palette by the sea)
mood:       cosy, colourful, calm; golden hour, clear [default]
setup:      laptop, no Blender yet, no GPU card; build tier 0
tier_target: low [chosen]; download budget about 100 MB [default]
checkpoints: screenshots after greybox and after paint [chosen]
open_questions: reuse choices (stage 5), portal and name (stage 6), fishing quest details (types/quest.md)
answers:    every line above marked chosen or default as in the transcript
```

Dry-run check for this job: the common opening ran to the tier statement and produced the
start of a brief without needing any file outside this folder.
