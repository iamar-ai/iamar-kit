# Market stall dressing: goods and back walls that read as a shop

A stall with an empty counter and a blank back wall reads as a prop, not a shop.
Each recipe here has a status (WORKS / PARTIAL / FAILED), evidence from a real
build, its layer (engineering = every world, style = the iamar look only) and a
check a builder or reviewer can run by eye on the shots.

Status: **WORKS** (the evidence is the fix for a measured failure, below).
Layer: style for the numbers, engineering for the rules. Kit: manual
(`stall_dressing` in `kit/recipes/techniques.json`).

## The failure this fixes (before)

Desert blind-test, attempt 2 (`docs/reviews/2026-10-21-an agent-blindtest-desert-a2.md`,
ranked gap 2, an internal task). The four market stalls in the brief (salt and spices, cloth,
brass and tools, water and gourds) read near-empty at the place visitors spend their
time:

- `rv_saffa_goods`, `rv_cloth_stall`, `rv_brass_stall`
  (`kit/blindtest/desert/review/sheets/m_day_0.jpg` bottom-right,
  `m_day_1.jpg` bottom-left and bottom-right): plain plaster back walls with flat
  dark grey panels (the panels read as holes), and two or three goods per counter
  in a single row on one plane — spice mounds, two cloth rolls, two brass bowls.
- Measured cost: stalls_west (Saffa's + water, two stalls) 3,310 triangles;
  stalls_east (cloth + brass, two stalls) 2,432 triangles — about 1,200-1,650
  triangles per stall, almost all of it spent on the counter/canopy/post shell,
  with nothing left for goods.
- The reused goods that were there cost too much each: catalogue vases at 598
  triangles against a small-prop budget of 35-50 (built-in sack 35, vase_tall /
  vase_wide 50).

The keepers, name plates and striped canopies were fine (review PASS) — keep them.
What was missing was stock.

## The recipe: five moves (engineering, WORKS)

Apply in this order. Every stall the visitor can see gets all five.

1. **Stock the back wall, don't panel it.** Replace flat dark panels with two
   shelf rows on the back wall (planks on brackets, or a side-post rack when there
   is no wall): jars, folded cloth, bowls, sacks. Two planks and 6-8 goods cost
   about 300-450 triangles. A dark flat panel reads as a hole; a stocked shelf
   reads as a shop.

2. **Lay the counter in three depths.** Front edge: low goods the visitor could
   almost touch (small bowls, mounds). Middle: taller goods (stacks, jars).
   Back: the tallest (or the shelf base from move 1). Never a single row of
   goods on one plane — that is the blank-counter look.

3. **Hang goods in the air.** From the canopy edge or a side post: strings of
   pots or gourds, cloth strips, a lantern. 3-5 hanging strands fill the empty
   air above the counter for about 250-350 triangles (a strand is ~8 triangles
   plus the item).

4. **Pile and bolt the goods; no singletons.** Spices: mounds in shallow bowls,
   3 mounds per bowl, never one mound on a bare counter. Cloth: bolts (rolled
   cylinders) stacked 3-2-1 with one bolt unrolled and draped over the counter
   edge. Brass: clusters of 3-5 vessels in mixed heights. Water: jars and gourds
   grouped, some on the ground beside the stall.

5. **The keeper works, with goods in front of them.** The desert build's keepers
   and name plates already pass (review PASS line) — keep the keeper behind the
   counter facing the visitor path, with a good in hand or the freshest goods
   directly in front of them.

### Counts and budget (the check)

- **At least 15 goods per stall:** 8+ on the counter (across the three depths),
  4+ on the back shelves, 3+ hanging. Count before the art pass moves on; a
  reviewer counts from the stall shots.
- **Triangle budget per stall, about 2,000-2,600 total:**
  - Shell (counter, posts, canopy, back wall, sign): ~800-1,000 — measured:
    desert stalls cost 1,216-1,655 each with 2-3 goods.
  - Dressing add-on: ~1,000-1,600 — back-wall shelves and stock ~350-450,
    counter goods ~900-1,100, hanging goods ~250-350.
  - That is about 2-3% of a 100,000-triangle world budget per stall
    (`budgets.triangles` in the desert brief): affordable where the brief puts
    stalls at the centre of the visit. Keep each dressed stall model under the
    profile's per-class triangle budget — the desert stalls passed lint with
    0 errors.
- **Reuse catalogue / built-in props first** (AGENT_KIT step 3), counted at
  their real lod0 triangles (`iamar-world assets show <name>`): sack 35,
  vase_tall / vase_wide 50, pot small 72, pot large 68, basket 176, coal sacks
  150, prop crate 230, potion 1/2/4 440-536, vase 2/4 598. A 598-triangle vase
  is a showpiece, not shelf stock — the desert review flagged exactly that
  (over the 35-50 small-prop budget).
- **Trap:** baked vertex-colour goods that render near-black (attempt 1's black
  pots on Saffa's counter). Check every reused good in a close eye-height shot
  before keeping it — the same check AGENT_KIT step 3 already requires.
- **Trap:** goods that block the keeper or the sightline. Keep the counter's
  middle low in front of the keeper's face, and keep stalls out of the square's
  view cones (recipe 2 in `kit/recipes/composition/README.md`).

### The four Brightsalt stalls, dressed (style)

How the five moves land on the brief's stalls:

| Stall | Back shelves | Counter (3 depths) | Hanging |
|---|---|---|---|
| Salt and spices (Saffa's, the big one) | 2 rows: salt sacks and small jars | front: 3 shallow bowls x 3 spice mounds; mid: 2 tall spice jars; back: stacked salt blocks | 4 strings of dried gourds |
| Cloth | 2 rows: folded cloth bolts | front: 1 bolt unrolled and draped over the edge; mid: bolts stacked 3-2-1; back: rolled rugs standing | cloth strips from the canopy edge |
| Brass and tools | 2 rows: small brass bowls and cups | front: 2 low bowls; mid: 3 vessels; back: 1 tall ewer | 3 strings of small pots, 1 lantern |
| Water and gourds | 1 row + ground: jars | front: 2 cups; mid: 2 jugs; back: tall jar; ground: 3 large gourds beside the stall | 2 strings of small gourds |

## After: the worked example

`examples/dressed_salt_stall.scene.json` dresses Saffa's salt-and-spice stall
(the `rv_saffa_goods` before) with the recipe: shell reused as built, 2
back-shelf rows with 6 goods, 9 spice mounds in 3 bowls plus 2 jars and 2 salt
blocks across three counter depths, 4 hanging gourd strings — 30 goods in about
1,600 triangles of dressing on a ~800-1,000-triangle shell. Compare the before
(`kit/blindtest/desert/review/sheets/m_day_0.jpg`, `rv_saffa_goods`) with the
goods list in the example: same stall, same camera, stocked.

### Check

1. The stall shots at eye height (`iamar-world shots`) show stocked shelves, a
   three-deep counter and hanging goods — not a single row of two or three.
2. `iamar-world lint` passes on the dressed stall models; the goods pass the
   small-prop triangle check from step 3 (`lint` WARNs `[metal]`/`[colour]`/
   `[palette]` on the built-in ones it knows).
3. The keeper still faces the visitor path and the goods do not block their
   face or the square's view cones.
