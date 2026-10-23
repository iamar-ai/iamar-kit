# The design interview: protocol

Written by swarm project `iamar-creator-knowledge` (an internal task, I1). Read this before you build
anything for a user. It is the first step of the playbook: **no world is built until the user has
approved a design brief.**

Files in this folder:

| File | What |
|---|---|
| `PROTOCOL.md` (this file) | How the interview runs: stages, rules, routers, the brief |
| `common.md` | The opening question set every interview starts with, setup detection, conflict flags, a worked dry run |
| `types/` | One question set per world type |
| `tracks/` | Track A / B / C process documents |
| `schema/` | `brief.json` schema and validator (`brief.py`) |

Run the common opening, pick the type and track with the routers below, ask the type's and
track's questions, and write the brief in both forms (section 6).

## 1. Why an interview

The user brings an idea; you bring the experience of building the iamar city. The interview
turns a vague idea into a brief you can build and check. It also stops the expensive mistakes:
a style chosen too late, a tier the user's computers cannot run, a scope that does not fit the
budget. Ask first, cheaply, so you do not rebuild later.

## 2. Rules for the agent

1. **Small batches.** Ask 2 to 4 questions at a time, never a long form.
2. **Defaults and examples on every question.** Offer a recommended answer and one or two
   examples, so a user with only a vague idea can answer "you choose".
3. **"You choose" is a valid answer.** Pick the default, record it as a default (see section 6),
   and tell the user in one line what you picked.
   The only questions without a default are the ones that define the world itself (common A1
   and B1, type `other` O1): there, "you choose" means ask again with the examples, or offer the
   listed words to pick from. Every other question, including the author name (A5), has a default.
4. **Show, do not describe, when you can.** For look and feel, show catalogue thumbnails or
   city screenshots and ask the user to point; do not ask abstract style questions.
   On a **text-only channel** (a chat or message relay that cannot carry images), send the
   picture paths anyway, one line each with a plain description of what it shows, and ask the
   user to open them (the contact sheet first: one file instead of six). Record whether the
   answer was given on the pictures or on the descriptions only (see
   `kit/recipes/greybox/README.md`, section 4).
5. **One question set at a time**, in the order of section 3. Do not jump ahead.
6. **Flag conflicts the moment you see them** (see `common.md`, section 4), with the cheapest fix.
7. **No build before approval.** Summarise the brief, ask "Shall I build this?", and wait for a
   clear yes. A change after approval re-opens only the affected section.
8. **Be honest about limits.** If the user's setup cannot reach the quality they want, say so
   and name the tier that can (see `common.md`, section 3).
9. **Never ask for secrets** (passwords, tokens, payment details). Hosting and publishing
   steps are described in `AGENT_KIT.md`; the user performs any step that needs a credential.
10. **Do not copy someone else's IP.** For a custom look, ask for the feeling and the rules of
    the world, not "like <named game or film>"; original concept images only.

## 3. Stages

| # | Stage | What you learn | File |
|---|---|---|---|
| 1 | Common opening | Purpose, audience, size of the visit, mood, the user's own setup | `common.md` |
| 2 | World-type router | Which question set follows | section 4 below |
| 3 | Track router | iamar-family, brand-new, or hybrid | section 5 below |
| 4 | Type-specific questions | The details of that kind of world | `types/<type>.md` |
| 5 | Reuse | Which catalogue objects to borrow, what to make new | section 7 below |
| 6 | Connections | Portals, address and name, hosting audience and limits | section 7 below |
| 7 | Constraints | Target tier, download size, quality bar | `common.md` |
| 8 | Brief and approval | The written brief; the user says yes or changes it | section 6 below |

Stages 1 to 3 always happen. Skip a later stage only if the user says it does not apply, and
record "not applicable" in the brief.

## 4. World-type router

Ask once, after the common opening: *"Which of these is closest to what you want to make?"*

| Type | Short description |
|---|---|
| `town` | A town, city or a district that extends an existing one |
| `nature` | A wilderness: biome, water, wildlife, paths |
| `interior` | A hall, dungeon, house or any enclosed space |
| `social` | A hub for meeting people, with events |
| `quest` | A game or adventure with goals, NPCs and quests |
| `shop` | A marketplace or shop |
| `education` | A learning world with activities and a teacher |
| `gallery` | A museum or showcase with exhibits and a route |
| `event` | A festival or one-off event |
| `other` | Anything else (sci-fi station, vehicle world, abstract space) |

A world can mix types (a town with a quest). Pick the **primary** type for the question set, and
list the others in the brief; ask only the extra questions the second type needs.

## 5. Track router

Ask once, in plain words: *"Should this world feel like iamar's city, build on iamar but look
different, or be completely its own?"* If the user is unsure, show three screenshots of the city
(`../gallery/city/`) and three contrasting styles and ask them to point. One file each:
`python3 kit/gallery/contact_sheet.py city OUT.png --quarter civic` and
`python3 kit/gallery/contact_sheet.py styles OUT.png` (palette cards of the city, harbour, desert and
station looks; ready-made: `kit/gallery/styles/style_cards.png`; say they are palettes, not renders).

| Answer | Track | What changes |
|---|---|---|
| Like the iamar city | **A** (iamar-family) | Load the iamar style profile and style kit; prefer catalogue objects; run the style lint and screenshot comparison; ask which quarter's palette and how the world connects to the city |
| Completely its own | **B** (brand-new) | Engineering practices apply in full; write a style bible and a `style.json` before building; ask open-ended questions about feeling and rules |
| iamar technology, different look | **C** (hybrid) | Treat as Track B for the look and take the engineering layer from the iamar kit (open: Track C may be folded into B) |

Engineering practices (budgets, visible-faces-only, closure, LODs, baked light, tiers,
packaging) apply to every track. Style practices (palettes, weathering, arches, roof
proportions, the material set) belong to the iamar look and apply to Track A only.

## 6. The design brief

The brief is the output of the interview and the contract for the build. It has two forms
that must agree: `world.brief.md` for the user to read and `brief.json` for tools
(schema and validator in `schema/`: `python3 kit/interview/schema/brief.py check brief.json --md world.brief.md`).

Fields (minimum):

| Field | Content |
|---|---|
| `vision` | One sentence |
| `audience` | Who visits, expected number at once, access (public, buddies, private) |
| `type`, `extra_types` | From the type router |
| `track` | A, B or C, with `style_profile`: `iamar` for Track A, the path of the world's own `style.json` for B and C. A Track A world that writes a `style.json` extending iamar (track_a.md step 1) keeps `style_profile: "iamar"` and names that file in `style_file` |
| `mood` | Feeling, time of day, weather |
| `characters` | `standard` (default: visitors bring their own iamar avatar), `restyled` or `custom` (then `custom_characters` lists the supplied models); from common B5 |
| `setup` | The user's computers: Blender?, GPU?, comfortable with scripts? and the resulting build tier |
| `tier_target` | The lowest hardware tier visitors must run (see `docs/WORLD_TIERS.md`) |
| `budgets` | Triangle, texture and download budgets taken from the tier and the art bar |
| `reuse` | Catalogue objects chosen, and what is new |
| `connections` | Portals, address and name, hosting choice |
| `features` | NPCs, quests, scripts, audio, UI pages |
| `checkpoints` | The stages where the user will see screenshots (greybox, scale check, paint) |
| `open_questions` | Anything not decided |
| `answers` | Every answer with `source`: `chosen` or `default` |
| `layout` | Optional: `{"zones": ["beach", "sea", {"kind": "house", "rooms": "bedroom:3,living,kitchen,bath:2"}]}`, the zones `iamar-world new --from-brief brief.json` blocks out (read from `vision` when absent; [docs/WORLD_FROM_BRIEF.md](../../docs/WORLD_FROM_BRIEF.md)) |

Mark every answer `chosen` (the user said it) or `default` (you picked it). The user reviews
the defaults first at approval time. After approval, store the brief in the world folder and
refer to it in the final report: the report states, for every budget and feature, whether the
build met it.

## 7. Reuse and connections (stages 5 and 6)

- **Reuse first.** Search the catalogue before modelling anything:
  `iamar-world assets search "<words>"` (see `AGENT_KIT.md`). Show thumbnails and let the user
  choose. Record chosen assets and what must be made new.
- **Connections.** Ask whether visitors should reach this world from the iamar city (portal),
  what it should be called, and who may visit. Hosting is the user's own computer; the kit
  commands and the user-performed steps are in `AGENT_KIT.md`. You never handle credentials.

## 8. Approval and changes

1. Present the brief in plain words: what will be built, what it will look like, what it will
   cost in download size and hardware, and the defaults you chose.
2. Ask: "Shall I build this?" Wait for a clear yes.
3. Record the approval (date, the user's words) in the brief.
   On Track B or C this one approval also covers the style bible's core (look sentence, three
   words, palette, light, three rules), which you interview before this step and put in the
   brief; the rest of the bible is written after it without a second approval
   (`tracks/track_b.md`).
4. Later changes: update the brief, say what moves (budget, schedule, tier), and ask again for
   the changed part only.

## 9. What counts as a successful interview

- The brief validates (`schema/brief.py check`) and contains no contradicting budgets.
- Every default is marked and was shown to the user.
- The tier the user's setup can build matches the quality they asked for, or the gap was
  stated and accepted.
- The user approved in their own words.
