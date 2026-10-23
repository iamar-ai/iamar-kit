# Composition, first impression and wayfinding recipes

How to make a world read well from the player's eye: what they see in the first ten seconds, what
draws them on, how they find places. Each recipe has a status (WORKS / PARTIAL / FAILED), evidence
from the city build, its layer (engineering = every world, style = the iamar look only) and a
command that passes or fails. Evidence ids (`TDnnn`) are rows of `kit/inventory/techniques_from_docs.json`;
commit hashes are in `the iamar browser source (not public)`.

Run the check on any world's sidecar file:

```
python3 kit/recipes/composition/check_composition.py <world>/composition.json   # COMPOSITION_OK or FAIL lines
python3 kit/tests/composition/composition_test.py                                # the checker's own test
```

`composition.json` (a kit file, not an engine or manifest field; all coordinates are metres on the
ground plane `[x, z]`, bearings clockwise from +z):

| Key | Content |
|---|---|
| `signs[]` | `id, kind, letter_m, read_distance_m, mount_m, mirrored, lit, blocks_opening` |
| `vistas[]` | `id, eye_xz, targets[{name, xz, allowed[]}]` (what one reveal point must show) |
| `obstacles[]` | `id, rect [x0, z0, x1, z1]` footprints that may block a sightline |
| `roofs[]` | `id, rise_m` eaves-to-ridge for ordinary houses |
| `first_view` | `spawn_xz, heading_deg, focals[{name, xz}]` |

Worked example: `examples/harbour_quarter.composition.json` (a harbour-quarter extension; the end-to-end
statue and prop example, job I5, should reuse it), which passes. `kit/tests/composition/composition_test.py` seeds one fault
per rule and requires the matching FAIL.

## 1. Eye height first (engineering, WORKS)

Judge every view from 1.7 m, never from a flying camera. Review cameras must stand outside every
footprint and off tree trunks: fixed-offset cameras ended up inside two buildings and gave shots
pixel-identical before and after (TD431, an internal task: take the first clear candidate from a frontal fan
then the approach path, 2.5 m outside every footprint, and keep already-clear eyes so sheets stay
comparable). Check: `iamar-world shots` eye placement (planned, job A1; until then place cameras by hand); the vista check below uses the same eye.

## 2. Axis ends on a landmark; focal piece on each entry sightline (style, WORKS)

A main street ends on a landmark (King's Way on the keep). Where streets enter a square, put a focal
piece (fountain, statue) at the point nearest every entry street's line of sight (least squares over
the last 15 m of each street), and keep stalls out of the view cones (TD132; `tools/city_map/square_focals.py`).
Gate Square keeps its focal off-axis because its axis is the view to the castle. Trap: the cone
polygons are runtime data; a plan-grow tool that skipped them left them behind while the city moved
(TD427: 56 failures unfixed, 0 fixed, tests/citygrow_focals_test.gd). Check: `vistas[].targets` with
`obstacles[]`: `check_composition.py` fails when a footprint blocks a sightline.

## 3. Skyline variation (style for the numbers, engineering for the rule; WORKS)

A uniform roof rise reads as "a low pale band" from the approach (mp-RV review round 6). The city
varies rise per quarter (4.2-6.2 m steep tall quarter, 2.3-3.2 m low cottages) with a deterministic
per-building spread, and lets landmarks (spire 84 m, tower 47 m) break the line (TD020, TD006;
`tools/city_map/skyline_heights.py`). Your numbers differ; the rule does not: spread, not one height.
Check: `roofs[]` standard deviation must be at least 0.6 m (`skyline flat` otherwise).

## 4. Wayfinding signs that can be read (engineering, WORKS)

Letters 0.25 m on fingerposts (read at 15 m), 0.5-0.8 m on landmark and quarter boards (30-40 m),
that is letter height at least read distance / 60; high contrast, never thin lettering; mounted
2.5-4 m so crowds and stalls cannot hide them; one single-sided face per reading direction, never
mirrored; a lantern on the post so it reads at night; freestanding boards stand about 3 m off the
facade so they never cover a door or window (TD140, TD182; `mp_wayfinding.gd`: 19 fingerposts, 4
quarter boards, 12 landmark boards, about 10.8k triangles in total, 0.1 s to build). Derive sites from
the street graph at build time (crossings, T-joins, squares, shortest routes) so they follow every
plan edit. Trap: a freestanding name board duplicated the facade sign at the cathedral and was
removed (`NO_BOARD`, the maintainer F4 report 20261013-163441): one name per entrance. Check: `signs[]`.

## 5. First ten seconds (engineering rule, style choices; WORKS)

The spawn must face something worth walking to: a focal target within 30 degrees of the heading.
The city reveals South Gate, guardian dragon and cathedral spire together at one point after a last
bend that keeps the city hidden, then runs the road straight to the bridge (TD132,
`tools/city_map/vista_approach.py`). Its own checks, reused here: the targets fit a 44 degree
picture, sit at least 8 degrees apart, the spire clears the wall by 15 m. Check: `first_view` and
`vistas[]` (fails on `one picture`, `merge`, `first view`).

## 6. Make the road read at a glance (style, WORKS)

Worn surface with ruts and a lighter centre strip 4-6 m wide, trees kept back 2-3 m, shafts of light
on the road, fingerposts at forks (TD147, the maintainer 2026-10-07 21:40: "the road in the woods is not very
obvious"). Check: screenshot at 1.7 m, then run the reviewer gate (`kit/review/REVIEWER.md`).

## 7. Failed or open (documented, not hidden)

- FAILED: fixed-offset review cameras inside buildings (recipe 1).
- FAILED: one flat roof rise for every house (recipe 3).
- FAILED: freestanding board duplicating a facade sign (recipe 4).
- OPEN: larger cities must be rebaked and measured before skyline claims (TD701); scale is not free.
- OPEN: the SVG plan map does not show wayfinding signs.

Order in the playbook: interview brief -> greybox (A7) -> recipes 1, 2, 5 on the greybox -> signs (4)
-> skyline (3) after the paint -> `check_composition.py` -> reviewer gate.
