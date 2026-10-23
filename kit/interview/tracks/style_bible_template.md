# Style bible: <world name>

Fill this in with the user (Track B and Track C, see `track_b.md`). Ask each section in a small
batch with a default and an example; mark each answer **chosen** (the user said it) or
**default** (you picked it). Keep it short: one page is enough. When it is approved it becomes
`worlds/<world>/style.json` (mapping table in `track_b.md`, step 3).

Never write "like <named game or film>". Write the feeling and the world's own rules.

## 1. The look in one sentence and three words

- Sentence: ______ (example: "Sun-baked adobe and indigo cloth under a hot white sky.")
- Three words: ______, ______, ______ (example: dry, crowded, warm)
- Answered by: chosen / default

## 2. The world's own rules

What is always true here? Three rules that every object obeys.
1. ______ (example: "Everything is built of mud brick and palm wood; no stone except gates and the well.")
2. ______
3. ______

## 3. Shape language

How do shapes feel? Pick one for buildings and one for props, or write your own.

| | Options | Chosen |
|---|---|---|
| Buildings | chunky and rounded / tall and thin / low and wide / angular / organic | |
| Props | chunky and exaggerated / delicate / blocky / worn and uneven | |
| Silhouette | the one feature that makes the skyline recognisable (a tower, a dome, a mast) | |

Rule of thumb for all looks: triangles go where the silhouette needs them; detail comes from
painted texture and baked light.

## 4. Palette

Four to eight named colours with hex values, what each is for, and (optional) which painted
material layer it uses. No pure black, no missing-texture pink.

| Name | Hex | Used for | Material layer |
|---|---|---|---|
| ______ | #______ | walls | plaster |
| ______ | #______ | beams, doors | timber |
| ______ | #______ | ground | cobble |
| ______ | #______ | accents (cloth, signs) | |

Accent colours (two or three, used sparingly): ______

## 5. Zones (optional)

Districts, biomes or areas that look different from each other. For each: a name, the mood, the
wall, timber and trim colours, and the light colour of windows and lamps.

| Zone | Mood | Wall | Timber | Trim | Window glow / lamp |
|---|---|---|---|---|---|

## 6. Weathering and variation

- How do surfaces age? (sun-bleached tops, sand-darkened bases; moss; salt; soot)
- Neighbour rule: "No two neighbouring buildings share ______" (tint, awning colour, roof shape)

## 7. Scale and proportion

| Rule | Value |
|---|---|
| A person | 1.8 m (fixed) |
| A door | ______ m |
| A grand door (`dimensions.grand_door_m`, optional) | an object `{building kind: metres or [min, max]}`, never a bare list |
| A storey | ______ m |
| Wall thickness | ______ m |
| Roof height as share of building height | ______ to ______ |
| Street / path widths | ______ |

## 8. Painted materials

For each surface family: the layer it is painted from, the tint, where it is used. (The kit
paints seamless tiles at 256 px per metre, 4 m per tile.)

| Material | Layer | Tint | Used for |
|---|---|---|---|

## 9. Light and atmosphere

- Usual time of day and weather: ______
- Sun: warm or cool? shadows soft or sharp? ______
- Sky (top, horizon, ground colours): ______
- Fog or haze: colour and strength ______ (keep fog light; warm fog can tint a whole scene)
- Night: what lights up (lamps, windows, glowing things)? ______

## 10. Budgets

Defaults come from the art bar and may only be tightened: ordinary building 1k to 3k triangles,
landmark 5k to 15k, prop about 300, creature 3k to 8k, hero statue about 8k, a visible frame well
under 1M. Write the ones you want tighter: ______

## 11. Reference images (original)

List the images in `worlds/<world>/style/refs/` and what each shows. Mark the ones the user chose.

| File | Shows | Chosen? |
|---|---|---|

## 12. Anchor assets (step 4 of `track_b.md`)

One building, one prop, one surface, built first to prove the look.

| Anchor | What | Screenshot (1.7 m and 15 m) | User said yes? |
|---|---|---|---|

## 13. Things to avoid

What must this world never look or feel like? ______ (example: no glossy plastic, nothing medieval)

## 14. Approval

The user's words and the date: ______
