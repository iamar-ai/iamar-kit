# Greybox first, with the user's approval at each stage

Written by swarm project `iamar-creator-knowledge` (an internal task, A7). The cheapest time to change a
world is before it is painted. This recipe turns that into a process with three checkpoints where
the **user** sees pictures and says yes, plus a checker.

Status: **engineering practice, layer = every world, every track.** The pieces come from the city
build (layout fixed in the plan before painting, fixed eye-height cameras, scale checked in
review); the whole ladder has not yet been run end to end on a kit world: that is the blind test
(job T1). The checker below is tested (`kit/tests/greybox/greybox_test.py`).

Run the check on any world's sidecar file:

```
python3 kit/recipes/greybox/check_greybox.py <world>/greybox.json     # GREYBOX_OK or FAIL lines
python3 kit/recipes/greybox/check_greybox.py <world>/greybox.json --brief brief.json   # approvals per the brief's checkpoints
python3 kit/tests/greybox/greybox_test.py                              # the checker's own test
```

## 1. The ladder

| Stage | You do | Checkpoint (the user sees pictures) | Cost of changing the layout afterwards |
|---|---|---|---|
| 0 Brief | Interview, approved brief (`kit/interview/PROTOCOL.md`) | the brief itself | nothing built yet |
| 1 Greybox | Block out streets, plots, landmarks, openings with plain grey shapes at real size | **Checkpoint 1: layout.** Is this the place? | minutes: move a box |
| 2 Scale | Walk it at 1.7 m, fix proportions, add the portal arrival and wayfinding points | **Checkpoint 2: scale.** Does it feel the right size? | an hour: resize and re-place |
| 3 Paint | Materials, baked light and AO, catalogue objects replace the placeholders, lighting preset | **Checkpoint 3: look.** Is this the world? | hours to days: re-paint and re-bake |
| 4 Review | The independent gate (`kit/review/REVIEWER.md`) | the review report | as stage 3 |

The brief's `checkpoints` field (see `kit/interview/schema/`, interview question D4) names which of
these the user asked to see; the interview's default is all three (`kit/interview/common.md` D4),
and a user may drop the scale check (the worked dry run there keeps greybox and paint). Never skip a checkpoint the brief names. The layout (greybox)
checkpoint is never skipped, whatever the brief says: it is the point of this recipe. When the brief
has no scale checkpoint, still walk the block-out at 1.7 m (stage 2), and show the scale pictures at
the next checkpoint the brief names. Copy the brief's `checkpoints` into `greybox.json` (or pass
`--brief`) so the checker asks only for the approvals the user agreed to give.

## 2. What a greybox is

- **Plain neutral materials** (one flat grey, or one grey per class); no textures, no painted
  palette, no baked light, no lighting preset. Painting before checkpoint 1 hides layout mistakes
  behind pretty colour and makes the user judge the paint instead of the plan.
- **Real dimensions.** A person marker 1.8 m, doors 2.0 to 2.4 m (the iamar city uses about 2.1 to
  2.2 m), storeys about 3.2 m, streets at their real widths (the city: lanes 5 m, alleys 3 m,
  main streets 10 m). Track B worlds use the numbers of their own `style.json`
  (`dimensions`).
- **Openings are openings.** Every door, gate, arch and path is a real open gap with a frame, not a
  painted square. A greybox with a closed wall where a door will be hides the most common closure
  mistake until it is expensive.
- **Placeholders for catalogue objects.** Use a box of the object's real size (from
  `iamar-world assets show`) where a borrowed object will go, so the layout already counts it.
- **Triangles already at budget.** A block-out is the cheapest version of the final shape; if a
  greybox box is over the class budget, the final one will be worse. Budgets per class: building
  3,000, prop 300, character 12,000, creature 6,000, landmark 15,000 at LOD0 (a profile may tighten).

## 3. Commands

```bash
iamar-world new worlds/my_world --id my_world --title "My World" --author "<user's name>"
iamar-world validate worlds/my_world                                   # no ERROR before showing the user anything
iamar-world preview  worlds/my_world /tmp/greybox                      # spawn view, four around, one from above, NPCs
iamar-world preview  worlds/my_world /tmp/greybox --view "x,y,z>lx,ly,lz"   # a camera of your choice (position > look-at)
```

Put the cameras at **1.7 m**, outside every footprint and off tree trunks (a camera inside a
building gave two identical "before and after" shots in the city). The fixed-camera `iamar-world
shots` command is a separate job (A1); until it exists, place cameras by hand as above.

## 4. Checkpoint protocol (what to show, what to ask, what to record)

**Show** (five to six pictures, named in `greybox.json` `shots`):
1. the **spawn view** (the first thing a visitor sees);
2. a **street** at eye height, and a second street or the main route;
3. a **landmark** close up and its silhouette from the far end of the main route;
4. the **portal arrival** if the brief has a portal;
5. an **aerial or map** overview (the only shot that is not at eye height).

**Ask** exactly three things, in plain words, and wait for answers:
1. "Is this the right place and layout?" (checkpoint 1) / "Does it feel the right size?" (checkpoint 2) /
   "Is this the look you want?" (checkpoint 3);
2. "Is anything missing or in the wrong place?";
3. "May I go on to the next stage?"

**Text-only channel.** Some sessions cannot show images (a terminal, a message relay, a voice
assistant). The pictures are still the checkpoint, so do not drop them:
1. make one contact sheet of the checkpoint shots (`iamar-world shots` writes
   `<out>/contact_sheet.png`; with hand-placed cameras, list the five or six files);
2. send the paths, contact sheet first, each with one line saying what it shows (place, camera
   height, what the user should look at, e.g. "spawn view at 1.7 m: quay on the left, lighthouse
   at the end of the street");
3. ask the user to open the contact sheet before answering, then ask the three questions above;
4. if they say they cannot open it, go on with the descriptions, and say so in the record.

**Record**: the user's words and the date, in the brief's approval notes and in `greybox.json`
`approvals` (`checkpoint`: `greybox`, `scale` or `paint`). Add `(on description only)` to the
recorded words when the user approved without opening the pictures; ask for a picture look again
at the next checkpoint, because layout and size are exactly what a description hides. A change after a checkpoint re-opens that
checkpoint only for what changed (`kit/interview/PROTOCOL.md`, section 8).

## 5. `greybox.json` (a kit sidecar file, not an engine or manifest field)

| Key | Content |
|---|---|
| `stage` | `greybox`, `scale` or `paint` |
| `measurements` | `person_m`, `door_m`, `storey_m` as **measured in the block-out**, and `street_widths_m` |
| `objects[]` | `id`, `class` (`building`, `landmark`, `prop`, `character`, `ground`), `triangles`, `painted`, `baked`, `openings[]`, `enterable` |
| `shots[]` | `file`, `eye_m`, `kind` (`spawn`, `street`, `landmark`, `portal` at eye height; `aerial`, `map` overview) |
| `approvals[]` | `checkpoint`, `date`, `words` (the user's own words) |
| `checkpoints` | the brief's `checkpoints`, copied as they are (for example `["greybox", "paint"]`); without it (and without `--brief`) all three approvals are required |
| `limits` | optional overrides of the defaults (from a world's style profile) |

Worked example: `examples/harbour_quarter.greybox.json` (a harbour quarter at the `scale` stage with
the greybox approved; it passes, and its approval is an example entry, not a real user's words).

## 6. Rules the checker enforces (each fails with its own message)

| Rule | Fails when |
|---|---|
| G1 painted too early | an object is painted or baked at stage `greybox` |
| G2 scale | `person_m`, `door_m` or `storey_m` is missing or outside the limits (person 1.6 to 2.0, door 2.0 to 2.4, storey 2.6 to 3.6 m) |
| G3 openings | a building or landmark has no named opening |
| G4 eye-height pictures | fewer than four eye-height shots, an eye height outside 1.5 to 1.9 m, or no aerial/map overview |
| G5 approval | a later stage lacks the approval of an earlier checkpoint the brief names (greybox always; scale only when the brief names a scale check), or an approval lacks a date or the user's own words (three words or more) |
| G6 budget | a block-out object is over the class triangle budget |

## 7. Mistakes seen when this is skipped

- Painting and baking first, then moving a street: the bakes are thrown away (the city matches
  bakes by shape and offset for exactly this reason).
- Layout changes made by repainting instead of changing the plan (the city's concept-target rule:
  match the look with the painting, change the layout through the plan).
- Judging from a flying camera: every size looks right from above and wrong at 1.7 m.
- A "door" that is a texture on a closed wall; found only at the review gate.
- Asking the user "do you like it?" after painting: they judge colour, not layout, and their
  layout complaint then costs a re-bake.
- A footbridge built flat and level with the quay: the blind-test harbour (attempt 5, gap R6) had a
  stone footbridge that read as a paved terrace, because the deck had no rise and the inlet water
  could not be seen from the approach (`kit/blindtest/harbour/review-a5/sheets/m_06_pier_lighthouse_footbridge.jpg`,
  third frame, `rv_footbridge`).

## 8. Water crossings (bridges, fords, stepping stones)

A bridge is recognised by the water under it, not by its parapets. Check at the greybox stage,
from the approach at 1.7 m (one of the checkpoint 1 street shots):

1. **Visible rise or arch.** The deck is raised above the banks (about 0.5 m at the crown for a
   footbridge, more for a road bridge), or the span is an arch whose soffit is visible from the
   approach. A deck level with the quay reads as paving.
2. **Open water under it.** The channel is lower than both banks and open under the span: the
   greybox shows a gap (a cut in the ground, a dark or blue placeholder) at least as wide as the
   deck, not a flat slab covering it. The water surface must be visible from the approach camera,
   so do not hide the inlet behind parapets taller than 1 m, and put the camera where the
   approach slopes up to the crown.
3. **Banks read.** The ground drops at the banks (a wall or slope), so the crossing is a
   decision of the layout and is approved at checkpoint 1, not discovered at paint.
4. **Example shot.** Add one named shot to `greybox.json` `shots` taken at 1.7 m, 6 to 10 m from
   the bridge end, looking along the deck; it must show the rise and the water together. If the
   shot cannot show both, change the layout, not the paint.
