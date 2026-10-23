# City buildings and landmarks (kit/catalog/assets/buildings, landmarks)

Representative houses and shops of each iamar city quarter, and the city's reusable landmarks,
as glTF files ready to drop into a world. Each one has a catalogue entry
(`iamar-world assets search house`, `... gatehouse`; `source.origin` is `city`, `style` names the
quarter) whose `use` line says how to place it:

```
copy kit/catalog/assets/buildings/b124.glb to <world folder>/assets/b124.glb, then
scene.json objects: {"asset": "assets/b124.glb", "position": [x, 0, z], "collision": "mesh"}
```

## What is here

| File | Quarter (plan) | What | Triangles | Size (m) | Open side |
|---|---|---|---|---|---|
| `buildings/b124.glb` | civic heart | town house, L-shaped, half-timbered | 3,056 | 9.3 x 11.1 x 17.3 | none |
| `buildings/b055.glb` | civic heart | healer's shop | 2,436 | 9.7 x 9.4 x 7.6 | none |
| `buildings/b107.glb` | herbalists' quarter | house, steep gable, flower boxes | 2,986 | 7.9 x 9.7 x 8.7 | -z, 6.1 m |
| `buildings/b106.glb` | herbalists' quarter | healer's shop | 2,264 | 8.0 x 9.8 x 10.9 | -z, 7.3 m |
| `buildings/b053.glb` | mages' quarter | tall three-storey house | 3,877 | 17.7 x 18.4 x 8.8 | +x, 7.9 m |
| `buildings/b033.glb` | mages' quarter | narrow workshop (arcane smith) | 1,925 | 12.5 x 14.0 x 5.6 | +z, 10.8 m |
| `buildings/b105.glb` | warriors' quarter | house, stone and dark timber | 1,740 | 7.6 x 9.5 x 8.4 | +z, 6.5 m |
| `buildings/b069.glb` | warriors' quarter | cobbler's shop with bay corner | 2,013 | 7.7 x 8.6 x 8.9 | -z, 6.5 m |
| `buildings/b001.glb` | warriors' quarter | warriors' quarter bird supply shop | 4,565 | 19.49 x 10.14 x 28.98 | -z 1.2 m |
| `buildings/b005.glb` | mages' quarter | mages' quarter wandmaker | 2,066 | 14.72 x 14.16 x 14.04 | -x 4.1 m, +x 6.8 m, +z 6.6 m, +x 1.8 m, -x 8 m, -z 1.6 m |
| `buildings/b007.glb` | warriors' quarter | warriors' quarter smithy | 3,197 | 8.2 x 10.47 x 18.75 | +x 2.1 m, +x 6.4 m |
| `buildings/b008.glb` | mages' quarter | mages' quarter curio shop | 1,791 | 16.47 x 10.26 x 8.45 | -x 1.8 m, -z 7 m, -z 4.1 m, +x 6.8 m |
| `buildings/b021.glb` | warriors' quarter | warriors' quarter blacksmith forge | 1,076 | 15.3 x 8.67 x 8.24 | +z 1.2 m, -x 3 m, -z 8.9 m, -z 7.5 m, +x 6.4 m |
| `buildings/b023.glb` | warriors' quarter | warriors' quarter bakery | 3,441 | 11.45 x 12.86 x 9.37 | -x 4.7 m, -z 4.1 m |
| `buildings/b024.glb` | mages' quarter | mages' quarter tailor | 3,284 | 10.08 x 16.66 x 12.26 | +x 9.9 m, -z 1.8 m |
| `buildings/b028.glb` | herbalists' quarter | herbalists' quarter armourer | 5,530 | 11.07 x 12.27 x 14.26 | +x 4.6 m, +z 6.4 m |
| `buildings/b029.glb` | herbalists' quarter | herbalists' quarter bakery | 4,382 | 14.09 x 13.27 x 18.51 | -z 8.1 m, +x 1 m, -z 1 m, -z 2.2 m, +x 1.3 m, +x 2.3 m, +z 2.1 m, +x 3.4 m |
| `buildings/b036.glb` | mages' quarter | mages' quarter rune carver | 1,668 | 13.32 x 13.0 x 12.2 | +x 8.1 m, -z 4.7 m, -z 1.3 m |
| `buildings/b038.glb` | herbalists' quarter | herbalists' quarter bookshop | 1,124 | 6.78 x 6.23 x 6.52 | +x 4.6 m, -z 5.6 m |
| `buildings/b039.glb` | civic heart | civic heart jousting supplies | 5,189 | 12.68 x 11.04 x 26.08 | none |
| `buildings/b043.glb` | warriors' quarter | warriors' quarter wandmaker | 2,771 | 14.81 x 15.66 x 13.07 | -x 10.5 m, -z 2.5 m, -z 6.2 m |
| `buildings/b046.glb` | mages' quarter | mages' quarter armourer | 590 | 11.59 x 12.95 x 6.08 | +z 10.8 m, -z 10.8 m, +x 5.6 m |
| `buildings/b051.glb` | warriors' quarter | warriors' quarter weaponsmith | 914 | 11.45 x 6.15 x 3.72 | -z 10.1 m |
| `buildings/b052.glb` | warriors' quarter | warriors' quarter armourer | 3,589 | 20.45 x 14.49 x 3.98 | -z 11.9 m, -z 1.2 m |
| `buildings/b056.glb` | civic heart | civic heart town house | 947 | 12.85 x 9.4 x 12.85 | +x 8.9 m, -x 1.7 m, -x 10.3 m |
| `buildings/b067.glb` | warriors' quarter | warriors' quarter spice seller | 2,211 | 9.47 x 8.68 x 9.99 | -x 4.9 m |
| `buildings/b084.glb` | civic heart | civic heart tailor | 1,240 | 6.93 x 7.33 x 10.18 | +x 8.8 m |
| `buildings/b098.glb` | warriors' quarter | warriors' quarter chandler | 2,043 | 13.7 x 9.95 x 13.66 | +x 9.8 m, -x 1.3 m, -x 9.3 m |
| `buildings/b099.glb` | civic heart | civic heart toolmaker | 984 | 10.5 x 8.99 x 11.19 | +x 4.2 m, +x 5 m, -x 9.8 m |
| `buildings/b120.glb` | herbalists' quarter | herbalists' quarter herbalist | 1,346 | 15.31 x 12.64 x 8.73 | +z 8.1 m, -x 6.3 m, +x 2.8 m, -z 4.7 m, +x 3.8 m, +x 2.8 m |
| `buildings/b127.glb` | herbalists' quarter | herbalists' quarter toolmaker | 5,495 | 13.59 x 11.87 x 21.73 | -x 6.4 m, -z 7.3 m, +x 5 m, +x 5.2 m |
| `buildings/b132.glb` | civic heart | civic heart bakery | 890 | 9.66 x 11.02 x 11.6 | -x 10.7 m, -z 8.9 m |
| `buildings/b133.glb` | civic heart | civic heart rune carver | 4,048 | 17.89 x 14.61 x 16.95 | +z 5.9 m, -x 6.5 m, -z 4.2 m |
| `buildings/b137.glb` | herbalists' quarter | herbalists' quarter arcaded shop row | 5,470 | 12.39 x 11.27 x 13.4 | -x 6 m, +x 6.4 m |
| `buildings/b138.glb` | warriors' quarter | warriors' quarter cloth merchant | 2,578 | 7.49 x 9.36 x 8.52 | -z 6.5 m, +x 5.3 m, -z 2.6 m, -z 1.3 m |
| `landmarks/gatehouse_1.glb` | South Gate | grand gatehouse, twin spired towers | 7,766 | 22.4 x 51.3 x 16.5 | |
| `landmarks/gatehouse_2.glb` | city wall | side gatehouse | 1,899 | 18.6 x 37.6 x 23.2 | |
| `landmarks/bridge_1.glb` | South Gate | stone causeway bridge, 57 m | 6,346 | 31.0 x 5.0 x 57.2 | |
| `landmarks/gz01.glb` | civic heart | round community gazebo | 1,774 | 13.0 x 10.3 x 13.2 | |
| `landmarks/c05.glb` | | colonnaded temple | 8,746 | 32.7 x 7.5 x 30.2 | |
| `landmarks/amp01.glb` | | small amphitheatre with stage | 3,006 | 25.0 x 7.6 x 15.9 | |
| `landmarks/s01.glb` | civic heart | horse stable, row of stalls | 4,476 | 32.1 x 7.4 x 23.5 | |
| `landmarks/grand_mascherone.glb` | | grand wall fountain (carved face) | 2,090 | 6.4 x 6.2 x 8.0 | |
| `landmarks/statue_bridge_1.glb` | South Gate bridge | round statue plinth | 528 | 2.9 x 1.6 x 2.9 | |
| `landmarks/hero_e1.glb` | South Gate bridge | stone hero statue, spear and shield | 1,894 | 1.8 x 5.4 x 1.3 | |
| `landmarks/hero_w1.glb` | South Gate bridge | stone hero statue, knight with sword | 1,906 | 1.2 x 3.3 x 1.2 | |
| `landmarks/hero_e2.glb` | South Gate bridge | statue of a woman holding up an orb | 2,004 | 1.88 x 4.11 x 1.92 | |
| `landmarks/hero_e3.glb` | South Gate bridge | statue of a woman with a flower | 2,032 | 1.73 x 3.3 x 1.8 | |
| `landmarks/hero_e4.glb` | South Gate bridge | statue of a swordswoman | 1,996 | 1.17 x 3.28 x 1.22 | |
| `landmarks/hero_e5.glb` | South Gate bridge | statue of a scholar with a book | 1,956 | 1.81 x 3.61 x 1.84 | |
| `landmarks/hero_w2.glb` | South Gate bridge | statue of a mage with a book | 1,864 | 1.87 x 3.66 x 1.84 | |
| `landmarks/hero_w3.glb` | South Gate bridge | statue of a huntress with arrows | 2,010 | 1.66 x 3.66 x 1.69 | |
| `landmarks/hero_w4.glb` | South Gate bridge | statue of a man with a lantern | 1,920 | 1.63 x 3.48 x 1.5 | |
| `landmarks/hero_w5.glb` | South Gate bridge | statue of a spearman with shield | 1,984 | 1.54 x 5.32 x 1.31 | |

The first 8 houses (one house and one shop per quarter) came in 2026-10-20; the 26 shops and the
other houses after b069 and the 8 heroes after hero_w1 came with PUB6 batch 1 (an internal task), the rows
`kit/catalog/public_selection.json` picked: one per quarter and purpose the catalogue lacked.

Budgets (AGENTS.md 60/40 rule): ordinary building 3k, landmark 15k. Over the building budget
(efficiency 80): b053 (3,877), b124 (3,056) and from batch 1 b001, b007, b023, b024, b028, b029,
b039, b052, b127, b133, b137 (3.2k to 5.5k: large corner blocks and three-storey rows, as the city
builds them; the selection's cap is 25k); every landmark and statue is under 15k.

## How they were made

`import_city_buildings.py` copies the files from `the iamar-models mesh archive (not public)` (de6b2675; built by
the iamar browser source (not public) `tools/masterplan_export_glb.gd` from the masterplan builders `MpBuildings`,
`MpLandmarks`, `MpGrandGate`, `MpStatues`) and:

- **re-centres** each one: the city stores vertices in city coordinates, so the root node is
  moved to put the footprint centre at x = z = 0 and the ground at y = 0. The gatehouses and
  the bridge keep their foundations below y = 0 (they stand in the moat); their entry says so.
- **measures** triangles and size itself (`import_city_models.measure`) and keeps the source
  file's sha256 and the offset applied in `../../sources/city_buildings.json`.
- **finds open sides**: the city never builds a wall nobody sees, so a terraced house has no
  wall where it touched its neighbour. The script compares each footprint side of the plan
  (at the commit the model was built from) with the outward-facing wall area at ground-floor
  height and records sides with almost none, with the side's two footprint corners (`ends`, in
  the file's coordinates). The result was checked against renders of every house from four
  sides and `iamar-world audit edge` on each file standing alone. The measure misses a party wall
  the city built only in part (the share above a lower neighbour); `FORCE_OPEN` in the script
  names those sides (B084's rear, B132's -z). B003 (a mages' curio shop, the selection's first
  pick) is left out: a sliver of a terrace whose closed variant still shows open at eye height;
  B008 stands for the quarter's curio shops. Put a wall, a neighbour or a hedge on an open side,
  pick a house with none, or use its closed variant (below).

## Closed variants (`buildings/<id>_closed.glb`)

Each open-sided house also ships closed, as its own catalogue entry ("... (closed)", search
`detached house`); the open original's description names it. `close_open_sides.py` makes them
from the files above (standard library only; rerun after a re-import, `--check` verifies):

```
python3 kit/catalog/assets/close_open_sides.py            # writes buildings/*_closed.glb + sources/city_buildings_closed.json
python3 kit/catalog/assets/close_open_sides.py --check
python3 kit/tests/catalog/closed_variants_test.py         # audits them free-standing in a world
```

For each open side it finds the plane where the side's wall ends stand on the ground, cuts the
house 4 cm inside it and closes the outline from the ground to the roof (wall colour) and across
the roof's end (roof colour): an outward cap flush with the wall ends (tilted to meet both corner
walls) and an inward one 2.5 cm behind (seen through the windows). Each side is closed in its
own plane and along its own length (its recorded `ends`): a house with two open sides facing the
same way at different depths (a recessed bay, a stepped terrace) gets a cap in each, where the
first version put both in the house's outermost plane and left the recessed one open (an internal task:
b099, b127 and five more batch-1 houses). Spots the house already closes with a face that way, in
any of its materials, are left out (cap columns split where such a face starts or stops), so
nothing z-fights. The cap is one more primitive of the house's mesh with the same material and
vertex attributes, so it renders like the house.

In a world, free-standing on a ground (`kit/tests/catalog/closed_variants_test.py`, all 32):
edge passes on every closed side, the cap adds at most 0.5 m2 of coplanar area over its original
(zfight), and closure is 0 m (b021 keeps 0.6 m where its 1.2 m +z stub meets the forge arcade).
Left as they are: b053's -x and -z (deep doorways, a jog the ray test reads as open) and b137's
-z (a slit where its two blocks meet), on sides that were never open.

| Variant | Cap triangles | Total |
|---|---|---|
| `b001_closed` | 282 | 4,847 |
| `b005_closed` | 1268 | 3,334 |
| `b007_closed` | 324 | 3,523 |
| `b008_closed` | 658 | 2,449 |
| `b021_closed` | 617 | 1,705 |
| `b023_closed` | 338 | 3,789 |
| `b024_closed` | 271 | 3,577 |
| `b028_closed` | 519 | 6,049 |
| `b029_closed` | 1015 | 5,407 |
| `b033_closed` | 255 | 2,189 |
| `b036_closed` | 552 | 2,220 |
| `b038_closed` | 356 | 1,487 |
| `b043_closed` | 381 | 3,155 |
| `b046_closed` | 806 | 1,401 |
| `b051_closed` | 339 | 1,253 |
| `b052_closed` | 470 | 4,061 |
| `b053_closed` | 148 | 4,029 |
| `b056_closed` | 326 | 1,273 |
| `b067_closed` | 201 | 2,418 |
| `b069_closed` | 215 | 2,234 |
| `b084_closed` | 174 | 1,414 |
| `b098_closed` | 768 | 2,820 |
| `b099_closed` | 555 | 1,539 |
| `b105_closed` | 220 | 1,960 |
| `b106_closed` | 199 | 2,466 |
| `b107_closed` | 148 | 3,134 |
| `b120_closed` | 902 | 2,248 |
| `b127_closed` | 687 | 6,196 |
| `b132_closed` | 347 | 1,242 |
| `b133_closed` | 287 | 4,343 |
| `b137_closed` | 740 | 6,238 |
| `b138_closed` | 974 | 3,602 |

Totals include the trim backs below.
The capped side is a plain plastered wall, as a party wall is.

## Sealed trim (`seal_trim_edges.py`)

The city builds trim as single sheets (window-sill fronts, plinth faces that stop above the
ground, dormer cheeks, chimneys with no top). In a row the street hides their edges; a house
standing alone shows them edge-on from eye height, with the sheet's culled back behind, and
`iamar-world audit closure` failed on every house here (b124 8.4 m, b055 6.8 m, the variants
3.8 to 12.3 m). `seal_trim_edges.py` (standard library only) finds the edges the audit would
(used by one triangle, 12 cm or longer, no other face within 3 cm) and appends a back to the
sheet each belongs to: its coplanar triangles copied with the winding and normal turned round,
same material, vertex colours and UVs. Sheets the model already backs with a face turned the
other way get no copy (it would z-fight), and edges on a recorded open side stay as they are.
That costs 47 to 140 triangles a house. Every closed house (b124, b055, the six variants) now
passes closure 0 free-standing on a ground; an open original shows open edge only on its open
side. The backs share the front's lightmap UVs (TEXCOORD_1), so a bake writes both sides of a
sill into the same texels; they are thin trim, so that is not visible.

The import and `close_open_sides.py` call it on every house they write; to reseal in place:

```
python3 kit/catalog/assets/seal_trim_edges.py             # reseal buildings/*.glb, update sources/city_buildings.json
python3 kit/catalog/assets/close_open_sides.py            # rebuild the variants from the sealed originals
python3 kit/catalog/assets/seal_trim_edges.py --check     # no sheet left without its back
```

```
python3 kit/catalog/assets/import_city_buildings.py <iamar-models> <plan.json>...   # re-import
python3 kit/catalog/assets/import_city_buildings.py --check                          # files match records, centred
```

## Known gaps

| Gap | State |
|---|---|
| Colour in package worlds | The files are vertex-coloured (the exporter turns the city's shaders into a vertex-colour material). The browser's run-time glTF loader does not switch vertex colour on, so a package world draws them white, like the other city models here. Job C2h (iamar-creator-knowledge #3131; also needs vertex_color_is_srgb) |
| Painted textures and baked light | Not in the files: the city's painted surfaces and lightmaps stay in the city. The models read as flat colour up close, below the art bar; a textured export is a follow-up |
| Interiors | The houses are shells; the city's rooms are separate files, in `../interiors/` (an internal task), moved by their building's offset so they fit inside it |
| LODs | One LOD each; the city's far detail is impostors and HLOD |
| Signs | Shop signs (painted board and lettering) are part of the file where the city built them |

## Not imported, and why

- Bank (B081, 29k triangles), guildhall (B044), Processional: over the selection's 25k-triangle
  bar or not picked (`kit/catalog/public_selection.json`). The cathedral, library, inn, mage school,
  castle, city hall and the other big landmarks came in with PUB6 batch 3 (an internal task): 0.6 to 4.1 MB
  each; packs (PUB7) keep them out of the plain git download, and `assets search` warns above 1 MB.
- The four gate figures (`FIGURE_STATUE_BRIDGE_1-4`) and the South Gate statues `HERO_3`..`HERO_8`:
  made with Hunyuan3D-2, whose licence for outputs is unconfirmed (`kit/inventory/licences.json`
  hunyuan3d-2). `HERO_E*`/`HERO_W*` are the game's own posed CC0 body, baked to stone, and ship.
- City-wide pieces (wall, moat, ground tiles, kerbs): placed sets, not objects. The aqueduct's
  arcade (AQUEDUCT01) and its waterfall came in with batch 3 as objects.
- The other city buildings: the selection (`kit/catalog/public_selection.json`, an internal task) keeps
  one per quarter and purpose; more can be added to `PICK` the same way.
- B003 (left out) and why B084 came back: see "How they were made".

Licence: CC0-1.0 (iamar original procedural work, an internal task; the heroes are posed from the CC0
Quaternius Universal Base Characters body).
