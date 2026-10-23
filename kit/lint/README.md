# Style lint and screenshot comparison

Two checks that judge a world against its **style profile** (`style.json`, see
[`../style/README.md`](../style/README.md)) instead of against hard-coded iamar values, so the
same commands work for the iamar look (Track A) and for a brand-new look (Track B).

| Command | What it does |
|---|---|
| `iamar-world lint <world folder or .glb ...> [--style P] [--class C] [--json] [--quiet]` | Lints models and the scene (`style_lint.py`) |
| `iamar-world compare-shots <before> <after> [--style P] [--out DIR] [--max-change X] [--json]` | Compares two shots from the same camera, or two folders of them paired by file name (`compare_shots.py`) |
| `iamar-world compare-shots <shots> [--style P] [--ground-times T] [--json]` | One shot or folder, no before: the per-shot checks (missing-texture pink, ground colour by day) |

Both are plain Python 3 (`python3 kit/lint/style_lint.py ...` works the same; on Windows the
launcher takes `PYTHON` or `py -3`). Texture sampling and the screenshot comparison need numpy
and Pillow; without Pillow the lint skips texture checks with a WARN. Exit status 1 means at
least one ERROR. Neither needs the browser.

**Which profile:** `--style iamar` (any id under `kit/style/<id>/`) or `--style path/style.json`;
without `--style` a world folder's own `style.json` is used, else `iamar`. A profile with
`"extends"` is merged over its parent first, so a Track A world inherits every iamar rule and
changes only what it states.

## What the lint checks

Every tolerance is read from the profile (`lint`, `dimensions`, `budgets`, `palette`, `regions`,
`materials`, `weathering`). Per model (LOD0, node names decide parts):

| Rule | Check | Profile fields |
|---|---|---|
| budget | LOD0 triangles against the class budget; every LOD reported; each LOD must be lighter than the one before. In a world, an asset with LOD1+ nodes (`_LOD1`, `_LOD2` ...) is an ERROR [lod]: the browser draws every node of a package model (it has no LOD-node handling and makes its own LOD chain, recipe `lod_chain`), so ship LOD0 only (`style-gen --lods 1`); the frame total counts every node drawn. Over budget is a WARN that states Efficiency (100 x budget / triangles), an ERROR below `min_efficiency` | `budgets.triangles`, `lint.min_efficiency` |
| scale | a `character` stands at `person_m` (+- `person_tolerance`); a node named `*door*` (not frame, arch, step ...) is `door_m` tall, a landmark's door up to the largest `grand_door_m` (an object `{building kind: metres or [min, max]}`; `check_style.py` refuses other shapes), another building's up to the smallest | `dimensions.person_m`, `door_m`, `grand_door_m` |
| roof | a node named `*roof*`: rise over half its short span within the profile's pitches (+- `pitch_slack`); flat-roofed profiles give `roof_height_fraction` instead | `dimensions.roof_pitch_rise_per_run`, `roof_height_fraction` |
| arch | a node named `*arch*`: rise over half its span (1 = semicircular), measured on the ring's soffit (its faces that look down into the opening), so a wall, door or jambs in the same node do not count; a node with no such faces (a block) is measured by its bounding box | `dimensions.arch_rise_half_span` |
| colour | sampled surface colour (base colour x texture at the model's UVs x vertex colours x the placement's scene.json `tint`, so each tint is judged as its own entry, `file.glb tinted #rrggbb`): nothing near a forbidden colour (black, missing-texture pink), darker than `min_albedo_value`, or bright and more saturated than `max_saturation`, on more than `vertex_bad_share` of a material | `lint.*`; swatches marked `glow` or `allow_dark` are exempt. A baked-light material (`KHR_materials_unlit` with a texture, from `kit/blender/bake_unlit.py`) holds colour x light: its dark texels are shade and are judged by `iamar-world audit dark-bake`, which knows what a viewer can see (pink still fails) |
| palette | each sample within `palette_max_delta_e` (CIE76, lightness at half weight because baked light changes brightness, not hue) of a profile colour: palette, region colours, material tints, trim looks, each also weathered by every weathering role; at most `palette_max_off_share` of the triangles off-palette. The dark texels of a baked-light material (hidden faces, sub-texel triangles, undersides) are shade, not a colour choice: they are never counted off-palette and are left to `audit dark-bake`; its lit texels are judged as usual | `palette`, `regions`, `materials`, `weathering`, `lint` |
| metal | a material with `metallicFactor` at or above `lint.max_metallic` (0.8) and no metal texture: it reflects an environment the preview world lacks and renders near black at eye height. Reused built-in objects have no file in the kit: `kit/catalog/builtin_materials.json` (rebuilt by `python3 kit/catalog/builtin_materials.py <browser workspace>`) holds their materials, judged for metal, near-black and off-palette colour (WARN) | `lint.max_metallic` |
| texture | every texture reference resolves and is embedded; missing-texture pink on the surface | `lint.pink_texture_share` |

Per world (`scene.json`): the same building or landmark model at the same scale closer than
`neighbour_m` to another copy (the profile's neighbour rule: vary the model, tint or scale; a `tint`
counts when a channel differs by at least 0.05, about 13/255, and `#ffffff` is no tint);
missing assets (an asset listed in `manifest.json` `reused`, from `iamar-world assets use <hash> --as`, is not missing: the lint resolves its hash in the kit catalogue and lints the kit's copy, or, for an object built into the browser, reports the catalogue's triangles and class); primitive colours under the colour rules (a fully transparent `"color"`, alpha
`00`, is an invisible collision proxy and is skipped); summed placed triangles against
`budgets.frame.visible_triangles_max`. Objects with a tiny `visible_range` (collision-only meshes)
are skipped.

**Several models in one file:** a .glb whose root nodes carry extras `{"x-class": C}` (`iamar-world style-gen street`: one house per root node) is linted root node by root node, each as class C (reported as `file.glb#node`), plus one `[parts]` INFO line; the scene object needs no `x-class`. In such a file every root node needs its own x-class: an untagged root node is still drawn, so it is linted and counted too, and fails `[parts]` (an internal task). A row merged into one mesh has no such nodes and is judged as one model (harbour a4 G11).

**Model class:** `"x-class"` on the scene object, else `--class`, else the kit catalogue's category when the file is a catalogue copy (matched by sha256: `hall_bench.glb` is furniture, a prop; an elm is a tree), else words in the file name
(`house`, `inn`, `office` ... building; `cathedral`, `castle`, `hall` ... landmark; `boat`,
`ship`, `cart` ... vehicle; `pier`, `quay`, `mast`, `frame`, `fence`, `wall`, `ground`, `bridge`
... structure; `horse`, `wolf` ... creature; `dragon`, `griffin` hero_creature; `statue`
hero_statue; `npc`, `person` character; `hair`; `head`, `face`), else by size (largest side up
to 3 m: prop, else building). The first class in that order with a word in the name wins
(`fish_hall` is a hall, `boat_fish` a boat); a vehicle or structure up to 3 m is a prop. Trees and plants
(`tree`, `elm`, `oak`, `pine`, `hedge`, `bush`, `flower`, `crop` ...) are class `tree`. A model up to 4 m named
after a place keeps its head noun when that is a person, animal or furniture word (`tavern_merchant` a
character, `hall_bench` and `tavern_table` props; furniture words `bench`, `table`, `chair`, `crate`, `lamp`
... only count up to 3 m). The iamar profile budgets structure, vehicle and tree at 3000 triangles; `iamar-world audit` runs its
building audits (roof, edge, door) only on building, landmark and interior.

## What compare-shots checks

For each pair: the two really are the same camera (same aspect ratio and correlated edges,
`--min-edge-corr`, default 0.5; a moved or zoomed camera is refused because the comparison
would be meaningless); mean colour change and the share of visibly changed pixels
(`--max-change` fails a pair over the limit); the share of pixels within
`lint.shot_palette_delta_e` of a profile colour, including its sky, fog, sun and ambient
colours, at several light levels (an ERROR when it falls by more than `shot_palette_drop`); new
missing-texture pink; black rising by more than `shot_black_rise`. `--out DIR` writes
`<name>_compare.png`: before | after | change heat map. Feed it the fixed cameras of
`iamar-world shots` (its `shots/` folder; `kit/shots/README.md`) or `iamar-world preview --view`, before and after a change.

### Ground colour by day

Day shots (file names ending in `_day`, as `iamar-world shots` writes them; `--ground-times
dusk,day` or `all` to change that) are also judged on their ground: the mean colour of the lower
40 % of the frame, leaving out blue pixels (water, sky) and black, must lie among the profile's
ground colours mixed in any share and lit by white light, from shade to sun. The ground colours
are the palette entries named or patterned after ground (`cobble`, `path`, `street`, `grass`,
`meadow`, `moss`, `sand`, `dirt`, `gravel` ...), the `ground_stone` of the profile's own regions (a
profile that `extends` iamar is judged by its own regions, not every city quarter) and any
`lint.shot_ground_colours` (a list of `#rrggbb`). The distance (delta E in a* b*) above
`lint.shot_ground_cast` (default 9) is an ERROR alone, and in a pair when the after shot is also
more than 1 worse than the before shot (else a WARN). A view that is mostly water or sky is
skipped. Calibration: the harbour a5 review's day frames, lit by the golden-hour sun on a moving
clock (orange cobbles, yellow grass; an internal task), are 10-25 off; the city's own day shots and the
lighting presets 0-6; the same harbour world after `lighting.py apply day` 0.0
(`kit/style/lighting/README.md`, "A running clock"). Fix a failure in the light, not the
textures: `lighting.py check <world>` names a warm moving sun.

## Samples and calibration

| Sample | What it shows |
|---|---|
| `samples/iamar_city/` | The city's own masterplan houses B002, B003, B005 as exported to `the iamar-models mesh archive (not public)` (56aa77ee): vertex-coloured, baked by the city builder. Passes the iamar profile; B002 is over the 3000-triangle building budget (efficiency 83: WARN, not a failure). |
| `samples/desert_post/` | A Track B world with its own `style.json` (the desert trading post example): flat-roofed adobe houses. Passes its own profile and fails the iamar one (its roofs are too flat for iamar pitches). |

`samples/make_samples.py` rebuilds the scene files and the desert models.

The iamar tolerances (`kit/style/iamar/style.json` `lint`) were calibrated in an internal task on the
city's own output, 2026-10-19:

| Measurement | Result | Tolerance chosen |
|---|---|---|
| masterplan houses B001-B005, vertex colours vs the iamar palette | all within delta E 8.8 | `palette_max_delta_e` 15 |
| the city's brightest surface colours (`cloth_red`, `gold`, `awning_red`) | saturation 0.72-0.75 | `max_saturation` 0.8 (only for value above 0.5) |
| masterplan houses' triangles | B001 4312 (efficiency 70), B002 3635 (83), B003 1386, B005 1934 | `min_efficiency` 60 |
| 16 real city screenshots (`docs/masterplan_shots`, `masterplan_layout`, `masterplan_creatures` in the iamar browser source (not public)) | median 97 % of pixels within delta E 8 of the palette, lowest 46 % (close-ups of costumes and meadow); pure neon 0 % | `shot_palette_delta_e` 8; the rule is the fall between before and after (`shot_palette_drop` 0.1), not a level |
| a city before/after pair at a different zoom (`masterplan_shots/f4_156`) | edge correlation 0.39 | refused (default 0.5) |

The lint also caught real problems while calibrating, kept here as evidence:

- The old-town builder (`iamar-world assets building`) makes houses of 3893-5221 triangles and an
  inn of 20152 with its furniture: over the 3000 building budget (house with `--style stone`:
  efficiency 57, an ERROR).
- The iamar profile from an internal task lacked 33 of the city's own `mats.gd` LOOKS colours (cloth,
  awnings, glows, the `dark` of openings); they are in the profile now, glows and openings marked, plus bark, meadow and leaf greens.
- `worlds/mission_hall` (the iamar browser source (not public)) fails: a 88406-triangle hall (landmark budget 15000) with
  pure-black wall and floor vertex colours on 12-16 % of their surface.

## Tests

`python3 kit/tests/lint/style_lint_test.py` (in `tools/run_tests.sh` as `kit_style_lint`): the
city sample passes; the custom world passes its own profile, fails the iamar profile, and its own
budgets and tolerances apply; 15 seeded violations fail (budget, black, too dark, neon,
off-palette, short, giant and landmark-size doors, steep and flat roofs, flattened arch, giant
person, heavier LOD1, textured pink, textured off-palette); unused black atlas space and the
profile's glow and opening colours do not; repeated neighbours, missing assets and black
primitives fail; compare-shots passes a small light change and refuses a moved camera, new pink,
rising black and palette drift. `python3 kit/tests/lint/compare_shots_test.py` (`kit_compare_shots`): the
ground colour by day: white light on cobbles and grass passes, orange and yellow light fail, dusk is
not judged, water is skipped, a desert profile's sand passes its own profile and fails the harbour's,
pairs fail only when worse, and the real harbour a5 day square fails where its dusk and the city pass.
The models come from `kit/tests/lint/glb_fixture.py`, a small
dependency-free glTF writer.
