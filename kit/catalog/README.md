# Object catalogue (kit/catalog)

Every reusable object a world can use, described in plain words so an agent can find it by
what it is, not by its file name: `iamar-world assets search horse`, `... small animal`,
`... chair`, `... tavern`. Reuse before modelling (AGENT_KIT.md "Reuse first").

| Path | What it is |
|---|---|
| `schema.json` | The entry format (`iamar-catalog/1`): id, name, kind, category, description + synonyms, tags, thumbnail, style and style compatibility, size, pivot, triangles per LOD, textures, collision, tier variants, animations and behaviours, placement hints, pairings, source, licence, attribution, reuse, use |
| `catalog.json` | The catalogue, generated (one entry per line). Never edit by hand |
| `CATALOG.md` | The same as a readable list, with a coverage table that shows the gaps (generated) |
| `catalog.py` | `build`, `check`, `search` (Python 3.8+, standard library only) |
| `vocabulary.json` | Categories (the vision's coverage list), the words that find each one, the rules that file a built-in model under one, placement hints |
| `overrides.json` | Hand-written fields per id; a `description` here marks the entry `written` |
| `sources/builtin_assets.json` | The browser's built-in CC0 models (copy of `the iamar browser source (not public)` `scripts/worlds/builtin_assets.json`, commit in `catalog.py` `BUILTIN_COMMIT`) |
| `sources/city_models.json` | The city's own props, trees and creatures (61 glTF files in `assets/`, measured and cited; `assets/README.md` says what each keeps) |
| `assets/` | Those files plus `import_city_models.py` (copies them from `the iamar-models mesh archive (not public)`, `--check` verifies them) |
| `sources/city_mounts.json` | The griffin (LOD0-2, one file per tier: `tier_variants`), the three stabled dragon breeds and the giant eagle, rebuilt with the city's code-built heads and per-LOD WebP textures by `assets/export_city_mounts.gd`, measured by `import_city_models.py --mounts` |
| `sources/harbour.json` | The harbour set in `assets/harbour/`: rowboat, fishing boat, mooring bollard, harbour bell, net pile, herring gull and the fish hall's slab, crates and drying net (`assets/export_harbour.gd`), and the sea, bell and gull sounds (`assets/harbour.py sounds`, Ogg Vorbis entries of kind `audio`); see "Harbour set" below |
| `sources/coastal.json` | The coastal and home set in `assets/coastal/` for beach and modern-house worlds: palm tree, dock, beach umbrella, sun lounger, beach towel, sea shells, coral, kelp (clip `sway`), sofa, kitchen counter, bathtub, wardrobe, rug (`assets/export_coastal.gd`, measured by `assets/coastal.py record`); see "Coastal and home set" below |
| `sources/procedural.json` | Objects without a file: creatures built by kind (`scene.creatures`) and the town's procedural buildings (`iamar-world assets building`) |
| `../tests/catalog/city_assets_test.gd` | Headless Godot test: every city model loads in a sample world with its triangles, size, collision and skeleton; the creature kinds wander; the harbour models play their clips and the harbour sounds load and play |
| `../tests/catalog_test.py` | Tests: fresh and valid, the horse / small animal / chair sample, seeded mistakes fail, the launcher |

## Getting the catalogue (public repository)

The catalogue, its search and its meshes are published at
**https://github.com/iamar-ai/iamar-kit** (`kit/catalog/`): clone it and run
`python3 kit/catalog/catalog.py search <words>`, or fetch a release pack by its sha256 from the
Releases page. When a world reuses an object, record its source and hash in the world's
`manifest.json` (`reused` or `credits`; AGENT_KIT.md "Reuse first"). Licences: code MIT,
catalogue data and original assets CC0-1.0, third-party objects as their entry says
(`THIRD_PARTY_NOTICES.md`). The repository is a one-way export; do not edit it by hand.

## Searching

```
iamar-world assets search <words...> [--category tree] [--style iamar-medieval] [--limit 0] [--json]
iamar-world assets search --worlds <words>     # objects inside downloaded worlds (the browser's search)
python3 kit/catalog/catalog.py search <words>  # the same without the launcher
```

Every word must match the entry's name, synonyms, category (label and synonyms), tags,
behaviours, description or file; name matches rank first. Plurals match singulars. A
query that is a category's label or synonym ("small animal", "farm animal") returns that
category. Each hit prints its id, triangles, size, licence, description and the `use` line
that puts it in a world (`iamar-world assets use <world> <id>`, a `scene.json creatures`
snippet, or `iamar-world assets building <kind>`).

Search never dead-ends (an internal task). Everyday words that are not in an entry are tried as
catalogue words from `vocabulary.json` `aliases` (ship -> boat, pier -> dock, tavern -> inn,
fir -> pine). A building word (house, home, cottage, inn) lists its generator first, which
builds one to any size (`iamar-world assets building house <out.glb> --rooms ...`). When
nothing matches, the search still ends `COUNT 0`, then prints `DID-YOU-MEAN <words>` for a
misspelling (sofaa -> sofa), up to five `NEAREST` entries (the corrected query, or the
entries matching the most of your words), and `MAKE` lines from `vocabulary.json` `make`:
the building generator for building words, and always the Blender starter
(`kit/blender/starter_build.py`). `--json` output stays a plain list of hits.

## Harbour set (sounds and a flying gull)

`assets search boat|bollard|bell|net|gull|sea|sound` finds the harbour set: two boats that bob
at their mooring (origin = the waterline, so place them at the water's height), a bollard, a
bell in its frame (clip `ring`), a net pile, a herring gull (clip `perch`; `fly` beats the
wings) and three sounds. A sound's entry has kind and category `audio`, 0 triangles, and a
`use` line that is its `scene.json sounds` entry: copy the `.ogg` to `<world>/audio/`, add the
entry, and set `position` for a positional sound (the bell, the gulls) or leave it out for the
ambient bed (the sea loop, seamless at 16 s). Its thumbnail is the waveform and its turntable
the waveform in eight slices of time, drawn by `assets/harbour.py record`.

Ringing the bell from a script (TypeScript `iamar.<name>`, docs/WORLD_API.md): play the clip on
the bell entity and the sound at the bell, `entity_play_anim(bell, "ring")` and
`sound_play("asset:audio/harbour_bell.ogg", x, 2.4, z)`; or, without a script, a quest's
`"on_complete": {"play": ["bell"]}` plays the bell's scene sound (its use line already sets
`"autoplay": false, "loop": false`).

A gull in flight is not a creature kind; script it: `entity_spawn("asset:assets/gull.glb", x, y, z, 0)`,
`entity_play_anim(g, "fly")`, then `entity_move_to(g, x2, y2, z2, 6)` to each point of a loop
over the water (it turns to face the way it goes), checking `entity_pos` each second for
arrival. To land it, move it onto a bollard top (0.66 m) and `entity_play_anim(g, "perch")`.
Gulls that only stand need no script: place the model with `"animation": "perch"`.

### Dressing a fish hall (an internal task)

`assets search fish hall` finds the interior set: `fish_stall` (a fishmonger's slab on trestles,
herring on ice, fish hung from a rail; front -Z is the buyer's side, 246 triangles),
`fish_crates` (three open crates of herring, 174) and `hanging_net` (a net drying over an
A-frame rack 2.6 m long, 262), with `net_pile` for the floor. All are props within the 300
triangle budget. An empty hall reads as a shed: the harbour a4 review found two crates in a
13 x 17 m hall. Worked example, a hall 13 m wide (x) and 17 m deep (z) with its centre at the
origin and the entrance on -Z. Add the hall's own position and turn to every entry:

```json
{"id": "slab_w1", "asset": "assets/fish_stall.glb", "position": [-4.6, 0, -2.5], "rotation": [0, -90, 0], "collision": "box"},
{"id": "slab_w2", "asset": "assets/fish_stall.glb", "position": [-4.6, 0, 1.5], "rotation": [0, -90, 0], "collision": "box"},
{"id": "slab_e1", "asset": "assets/fish_stall.glb", "position": [4.6, 0, -2.0], "rotation": [0, 90, 0], "collision": "box"},
{"id": "crates_w", "asset": "assets/fish_crates.glb", "position": [-5.6, 0, 4.2], "rotation": [0, 12, 0], "collision": "box"},
{"id": "crates_e", "asset": "assets/fish_crates.glb", "position": [5.4, 0, 1.4], "rotation": [0, -74, 0], "collision": "box", "scale": 0.95},
{"id": "net_rack", "asset": "assets/hanging_net.glb", "position": [0, 0, 6.6], "collision": "box"},
{"id": "net_floor", "asset": "assets/net_pile.glb", "position": [3.6, 0, 6.2], "rotation": [0, 30, 0], "collision": "none"}
```

The slabs stand 1.9 m out from the side walls with their backs to them (a slab's rail is at
+Z, so -90 turns the west row's rail to the wall); the middle 5 m stays clear from the
entrance to the net rack at the back, so the player walks straight in and sees the rack. Put a
quest item (the harbour brief's lost net) on the floor beside the rack, not on it, and turn
the crates differently so the stacks never repeat (`variety.py check`).

## Coastal and home set (an internal task)

`assets search palm|dock|pier|umbrella|lounger|towel|shells|coral|kelp|seaweed|sofa|kitchen|bathtub|wardrobe|rug`
finds the set made for the beach-house brief (the rowboat is the harbour set's). Every model is under
3000 triangles (`coastal.py --check` fails above it), one palette texture, colours below the linear
tonemap's white, style `iamar coastal and modern home` and `style_compat` neutral, so `--style`
offers them to any world. Origins: the dock's is the water's surface at its shore end (the deck,
0.6 m above, runs out along -Z: place it at the water's height and walk on it with
`"collision": "mesh"`); the coral's and kelp's are the sea floor; the rest stand on the ground.
The sofa, wardrobe and kitchen counter face +Z like the city's furniture (their backs, -Z, go to a wall).
Kelp waves with `"animation": "sway"`; the palm sways in the shared wind with `"sway": true`.
`docs/evidence/job3800/make_world.py <folder>` builds a test world with all of them on a beach,
under clear water and in an open living room, for `iamar-world preview`.

## Adding or changing entries

1. A new built-in model in the browser: `python3 kit/catalog/catalog.py build --builtin <iamar checkout>/scripts/worlds/builtin_assets.json`
   and update `BUILTIN_COMMIT`. New categories or filing words go in `vocabulary.json`.
2. A better description, synonyms, tags, behaviours, LODs or style tags for one object (`style_compat`: `iamar-medieval`, `neutral` or `other`; the default comes from `vocabulary.json` `style_rules`, and `check` fails on an untagged entry):
   add them under its id in `overrides.json`, then `build`.
3. Objects without a file (creatures, generators): `sources/procedural.json`.
4. A city object: add it to `PICK` in `assets/import_city_models.py`, rerun the import, then `build`.
   A coastal or home object: add it to `export_coastal.gd` and `MODELS` in `assets/coastal.py`, run the
   exporter and `coastal.py record`, then `build`.
   A harbour object or sound: add it to `export_harbour.gd` (models) or `SYNTH`/`SOUND_SET` in
   `assets/harbour.py`, run the exporter and `harbour.py sounds`, then `harbour.py record` and `build`.
5. `python3 kit/catalog/catalog.py check` fails when catalog.json or CATALOG.md is stale,
   an entry breaks the schema, a built-in model has no entry, or a `.glb` or `.ogg` in `assets/` has none. Run it and
   `python3 kit/tests/catalog_test.py` before pushing.
6. Provenance (an internal task): after adding or re-rendering any model, texture, image, sound or font, run
   `python3 kit/catalog/provenance_build.py`. It rewrites `provenance.json`: one row per shipped binary,
   `made_by` (`hand`, `procedural`, `blender`, `third-party:<row>` or `generative:<row>`, rows of
   `kit/inventory/licences.json`) plus the commit or file that shows it. Catalogue files and previews get
   their row from the entry; anything else needs a line in `RULES` in that script, and `check` fails until
   it has one. Anything made with, or showing the output of, Hunyuan3D, UltraShape, SDXL images,
   MV-Adapter or gpt-image is `generative:<row>`, and the public export withholds it.

Follow-up jobs build on this: C2 exports the city's own animals, trees, furniture and
buildings into the catalogue; C3a wrote a description, synonyms and tags for every
entry (`description_source: written`; `check` fails on a generated one); C3b (done) gives every entry a thumbnail and an 8-view turntable strip (`render_previews.gd`, `compact_previews.py`; `check` fails on a missing file); C4 tests each behaviour; C5 (done) tags `style_compat` from `style_rules`.
