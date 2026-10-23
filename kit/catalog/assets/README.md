# The city's own objects (kit/catalog/assets)

glTF files of objects the iamar city builds in code, ready to drop into a world. Each one has
a catalogue entry (`iamar-world assets search <words>`; `source.origin` is `city`) whose `use`
line says how to place it:

```
copy kit/catalog/assets/props/well.glb to <world folder>/assets/well.glb, then
scene.json objects: {"asset": "assets/well.glb", "position": [x, 0, z], "collision": "mesh"}
```

| Folder | What | Built in the city by (the iamar browser source (not public)) |
|---|---|---|
| `props/` | 45 street, quarter and training-ground props: lamps, benches, stall, well, fountain, smithy kit, banners, signs, racks, tourney pieces; the city's painted look baked into a texture per file (below) | `MpProps.sample(kind)` (Dresser kinds; faces nobody sees removed); each file carries its own collision shape (OMI physics body) |
| `trees/` | oak, elm, pine | `TreeGen.mesh(kind, 0)` (welded trunk and leaf blobs, vertex colour) |
| `creatures/` | rabbit, rooster, hen, cow, deer, wolf, duck, duckling, fish, frog, turtle (parts in their standing rest pose, vertex-painted); young stable dragon and the guardian dragon (skinned, painted atlas) | `MpCreatures` (AnimalKit / WildlifeKit / PondKit), `MpDragonKit`, `DragonKit` v23 |
| `creatures/insects/` | six butterflies (small white, brimstone, small tortoiseshell, common blue, peacock, red admiral), bumblebee, dragonfly: wings on hinge nodes with their motion as clips (`flap`/`glide`/`rest`, `fly`/`rest`) | butterflies: the city's `Butterflies` + `butterfly_motion.gd` + `assets/butterflies/atlas.png`; bumblebee and dragonfly made for the kit in the same build (the city has them only as a sound and as motes) |
| `harbour/` | rowboat and fishing boat (clip `bob`, origin at the waterline), mooring bollard, harbour bell in its frame (clip `ring`), pile of fishing net, herring gull (clips `perch`, `fly`); `harbour/sounds/`: sea waves (16 s seamless ambient loop), harbour bell strike, gull calls, mono Ogg Vorbis | made for the kit: `export_harbour.gd` builds the models in the city's painted look (the city has no harbour), `harbour.py sounds` synthesises the sounds from fixed seeds (no recordings) |
| `furniture/` | armchair, oak chair, high chair, trestle table (with its benches), hall bench, cot bed, shop shelf, bookshelf, kitchen dresser, hearth, iron-bound chest; front toward +Z, faces against the wall or floor left unbuilt as in the city; painted look baked into a texture per file (below) | `MpInnWing`, `MpGuildhallInterior`, `MpInteriorKits`, `MpInteriors` room builders, one piece per empty room (`export_city_pieces.gd`) |
| `crops/` | cabbage, lettuce, leek, carrot, onion, squash, runner beans (vertex-painted, two-sided, 9-42 triangles) | `MpCropBeds` plant meshes (`export_city_pieces.gd`) |
| `flora/` | daisies, buttercups, pink campion, grass tuft, tall grass, reeds, lily pad (painted atlas cards, alpha-scissored, 2-6 triangles); pond stone | `MpFlora` cards and stone (`export_city_pieces.gd`) |
| `buildings/`, `landmarks/` | 35 houses and shops of the city's four quarters (civic heart, herbalists', mages', warriors': homes, bakeries, smithies, a forge, armourers, wandmakers, tailors, a bookshop, an arcaded shop row ...), re-centred, open party-wall sides recorded, each open-sided one also closed (`*_closed.glb`); two gatehouses, the South Gate causeway bridge, gazebo, temple, amphitheatre, horse stable, wall fountain, statue plinth, ten hero statues; and (batch 3) the cathedral, library, inn, mage school, castle, city hall, trading hall, giant-bird aerie, small-dragon stable, weapons hall, the aqueduct and its waterfall, a mage portal ring. Details: [buildings/README.md](buildings/README.md) | `MpBuildings`, `MpLandmarks`, `MpGrandGate`, `MpStatues` via iamar-models (`import_city_buildings.py`) |
| `interiors/` | 22 room interiors, one per building purpose: shops (bird supplies, smithy, forge, runes, curios, jousting, wands, healer, tools, herbs, books, bakery, saddlery, weapons hall), city hall, bank, trading hall, library (its nine parts in one file), inn and tavern, horse, giant-bird and small-dragon stables. Inner fittings only, moved by their building's offset: placed at the building's position they line up. Details: [interiors/README.md](interiors/README.md) | city room builders via iamar-models (`import_city_interiors.py`) |

The 61 in `props/`, `trees/` and `creatures/` come from `the iamar-models mesh archive (not public)` (exported there by the iamar browser source (not public)
`tools/masterplan_export_glb.gd` and `tools/masterplan_export_creatures.gd`), copied by
`import_city_models.py`, which measures every file itself (triangles, size, skeleton,
collision) and checks it against iamar-models' `models.json`. The record per file, with its
source commit, is `../sources/city_models.json`.

The props then get the city's painted look baked in (next section): `bake_painted.gd` rewrites
each copied file with a texture and records it in `../sources/painted_bake.json`;
`import_city_models.py --baked` folds that into the rows (the row keeps the iamar-models copy's
hash as `painted_bake.source_sha256`).

The 8 insects are made, not copied: `export_insects.gd` builds them (run from an the iamar browser source (not public)
checkout, it reads the city's butterfly atlas) and `insects.py record` measures them into
`../sources/insects.json`. Their `use` line includes `"animation"`, the clip the world loops.

The furniture, crops and flora are not in iamar-models: the city builds them only inside
whole rooms and as MultiMeshes of thousands of copies. `export_city_pieces.gd` calls the same
builder functions once per piece (read-only, against an the iamar browser source (not public) checkout) and writes
the files plus `../sources/pieces_export.json`; `import_city_models.py --pieces` measures them
into `../sources/city_pieces.json` (city_models.json's row format; furniture rows also list the
city's sit spots as `seats`). The flora cards keep their cell of the painted flora atlas
with the flora shader's tint and root shade baked in (256 px wide).

## The painted look, baked (an internal task)

The city draws every MeshKit object (props, furniture, buildings) with one shader,
`shaders/mp_painted.gdshaderinc` in the iamar browser source (not public): the vertex colour is only the look's base
colour, and the shader paints the pattern over it from the hand-painted library
`assets/masterplan/textures/mp_library.png` (13 layers, 4 m tiles at 256 px/m). A glTF cannot
carry that shader, so a file holding only the vertex colour shows one flat colour per face
(the art bar: "never flat untextured colour"). `painted_baker.gd` runs the shader's colour logic
on the CPU for each texel of a per-object atlas and writes it as the base-colour texture:

| Pattern (vertex alpha >> 3) | Baked as in the city |
|---|---|
| 2 timber | the timber layer, grain along each face's long axis (boards, legs, beams) |
| 1 stone, 11 ashlar/granite, 20 brick, 21-23 limewash, 4 plaster, 5 cobble, 3 roof, 6 thatch | their library layer on face-aligned planar coordinates (courses follow each face), brick and pencilled-ashlar joints |
| 8 iron, 19 strap trim | the iron layer / trim strip; their faces go to a surface of their own with the city's roughness 0.38-0.4 and metallic 0.4-0.45 |
| 12-18 trims | the trim-sheet strip along the face, its profile across it (cornice, frame, moulding, carved, dentil, rope, beam) |
| 9 cloth, 10 stripes, 0 plain | the shader's cloth mottling, awning stripes, painted value noise |
| 7 glass | leaded panes sized to the window, stained-glass quarries for glow 4 (roughness 0.18) |
| every painted face | broad value drift, grime, the worn-edge highlight on small faces, chipped stone arrises, rain streaks on outdoor walls, the quarter's colour grade, and MeshKit's contact shade (UV2) |
| glow 1-7 (lamp panes, embers, horn lanterns) | an emission texture at a dusk level (`night` 0.35: the city varies it with the hour, a glTF cannot) |

Each face is a chart at 128 px per metre (half the library's density; an atlas never exceeds
1024 px, a bigger object is baked coarser), with a 2 px gutter of the face's own edge colour;
JPEG at quality 0.85. Triangles, their corners and winding are unchanged (only TEXCOORD_0 is new;
COLOR_0 and UV2 are dropped, both are in the texture), so the files look the same in every glTF
viewer and on every browser, also older ones that ignore vertex colour. Not baked, because it
needs the city around the object: the light bake (sky-visibility stains, AO; a world's own
light and bake apply), the world maps (street ruts, grass edges, wall-foot grime, ivy, painted
half-timbering), the flagstone breakup of large paved floors, rain wetness and cloud shadow.
Furniture is baked as indoor (no rain streaks), props as outdoor, both quarter 0 (civic), variant 0.
Colour: the shader receives the vertex colour decoded from sRGB (the look's `#rrggbb` as
written); the baker does the same. Measured on the quench barrel, anvil and well, unshaded, the
bake is within 5-10 % of the live shader's output; baking the raw values instead came out 1.4-4x
too bright and washed out. Evidence (before = the old flat file as the browser draws it, after =
baked): `docs/evidence/job3129_furniture.jpg`, `job3129_props.jpg`, and
`job3129_city_vs_bake.jpg` (left the city's own `MpMaterials.live` shader on the unbaked copy,
right the bake). Test: `kit/tests/catalog/painted_bake_test.gd` (run from an the iamar browser source (not public)
checkout: triangles and winding kept, iron split out, glow, timber grain varies and its mean
is the shader's colour, every shipped prop and furniture file textured).
`import_city_models.py --check` fails when a prop or furniture file is still flat vertex colour.

## Commands

```
python3 kit/catalog/assets/import_city_models.py <iamar-models checkout>   # re-import (then bake, --baked, catalog.py build)
godot --headless --path <the iamar browser source (not public) checkout> -s <iamar-kit>/kit/catalog/assets/bake_painted.gd   # bake the props' painted look
python3 kit/catalog/assets/import_city_models.py --baked                   # fold the bake into city_models.json
godot --headless --path <the iamar browser source (not public) checkout> -s <iamar-kit>/kit/catalog/assets/export_city_pieces.gd
python3 kit/catalog/assets/import_city_models.py --pieces                  # measure the pieces (then catalog.py build)
python3 kit/catalog/assets/import_city_models.py --check                   # files match their records
godot --headless --path <the iamar browser source (not public) checkout> -s <iamar-kit>/kit/catalog/assets/export_insects.gd   # rewrite the insects
python3 kit/catalog/assets/insects.py record                               # then measure them (and catalog.py build)
python3 kit/catalog/assets/insects.py --check                              # insect files match their records, clips exist
godot --headless --path <the iamar browser source (not public) checkout> -s <iamar-kit>/kit/catalog/assets/export_harbour.gd  # rewrite the harbour models
python3 kit/catalog/assets/harbour.py sounds                               # synthesise the harbour sounds (ffmpeg with libvorbis)
python3 kit/catalog/assets/harbour.py record                               # measure models and sounds, draw the sounds' previews
python3 kit/catalog/assets/harbour.py --check                              # harbour files match their records
python3 kit/catalog/catalog.py check                                       # also fails on a .glb here with no entry
godot --headless --path <the iamar browser source (not public) checkout> -s <iamar-kit>/kit/tests/catalog/city_assets_test.gd
```

The last one builds a sample world with every model here plus the four creature kinds and
opens it through the browser's own `WorldPackage` / `WorldBuilder`: each model must load with
its recorded triangles and size, props keep their collision, dragons their skeleton, and cows,
horses, chickens and bunnies wander inside their radius, and every insect loops its clip with
its wings swinging (112 checks with the furniture, crops and flora, 2026-10-20 on Windows, Godot 4.7.2, the iamar browser source (not public) 6137fefa).

## What they keep, and what they do not (yet)

| Behaviour | State |
|---|---|
| Collision | Kept: props carry an OMI physics body; scene.json `"collision": "box"`/`"mesh"` for trees, cow and dragons |
| Wander, graze, peck, hop | Kept for cow, horse, chicken, bunny through `scene.json creatures` (`creature:<kind>` entries); the creature models here are static rest poses |
| Deer, wolf, ducks, fish, frogs: wander, flee, swim | Not in package worlds: the browser's `WorldCreatures` knows only cow, horse, chicken, bunny |
| Wind sway of trees | Kept when placed with `"sway": true` (the use line says so): the browser's `WindField.adopt_tree` puts every surface on its wind shader in tree mode, trunk rooted, canopy swaying (the iamar browser source (not public) d44444b2). The city's own `foliage.gdshader` cannot travel in a glTF. The test checks each tree (`BEHAVIOUR ... sways in the shared wind`) |
| Dragon flight, idle, breathing | Not kept: the files are skinned but carry no animation clips |
| Insect wings | Kept as clips: scene.json `"animation": "flap"` (butterflies) or `"fly"` (bumblebee, dragonfly) loops the wingbeat in place; `rest` is the perched pose. Flying about, landing on flowers and fleeing the hero (the city's `Butterflies` steering) are not in package worlds: a world script or a path moves them |
| Colours of vertex-painted models | Kept from browser the iamar browser source (not public) d7d034da on (an internal task): WorldPackage turns `vertex_color_use_as_albedo` on for every surface with `COLOR_0` and reads these Godot-made files as sRGB (swayed trees too); older browsers draw the trees, creatures and crops above white (recipe `gltf_texture_colours`). The props and furniture (painted bake, an internal task), the insects and the flora cards carry their colours in a texture and look the same on every browser |
| The city's painted patterns | Baked into a texture for the props and furniture (wood grain, stone courses, iron, trims, cloth, contact shade, glow; section above). Not for the trees, creatures and crops: the city draws those with their own vertex-colour shaders, not the painted library |
| LODs | One LOD each (the city's far detail is impostors and HLOD, not per-object LOD files) |

Placement scale: the young dragon is the great dragon's rig at 0.16 and the guardian is drawn
at 1.35; their `use` line includes that `"scale"`.

## Not imported (yet)

- City-wide batches in iamar-models `props/` (`Kerbs_*`, `Hedgerows`, `Horses`, `StoneWalls`,
  `Fields` ...): placed sets, not single objects.
- The iamar-models copies of the giant eagle, griffin LODs and dragon breeds (2.6-3 MB each,
  the same texture embedded in every file; the eagle and breeds wear a Hunyuan3D head whose
  licence is unconfirmed, `kit/inventory/licences.json` generated-head-glb). Instead
  `export_city_mounts.gd` rebuilds them with the city's code-built heads and per-LOD WebP
  textures (`creatures/mounts/`, `sources/city_mounts.json`): the griffin has one file per
  tier (LOD0-2, under 1 MB together), the breeds and the eagle one LOD each.
- Interiors (`interiors/`), the other 112 city buildings and the large landmarks (see
  buildings/README.md "Not imported"), horses and birds as models: follow-up jobs of C2. Herb-garden herbs (`MpHerbGarden`, their
  own atlas) are not exported yet.

Licence: iamar original work, licence not chosen yet (`kit/inventory/licences.json`
`original-procedural`); reusable in iamar worlds (the maintainer 2026-10-03), not shippable in the
public export until the licence is set.
