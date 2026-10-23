# iamar world recipes

How to engineer an iamar world that looks good and runs smoothly on every visitor's GPU.
Each recipe says what it is for, when to use it, the steps, the defaults, how the
kit checks it and where it comes from. `techniques.json` beside this file is the
source of truth (this page is generated from it). The browser applies recipes
marked *automatic*. Builders can apply *manual* recipes with today's format/tools.
A *planned* recipe has no supported package field or tool yet: skip it, report it
as unavailable when relevant, and never invent a field. Planned recipes do not
block validation, signing, or completion.

## Geometry

### Distance LOD chain  (`lod_chain`, kit: automatic)

Far objects use much lower-poly versions, so the triangle budget goes to what is near.

**When:** Every model larger than a crate, and every merged area mesh.

1. Model the full-detail version in Blender.
2. Make LODs at about 50% and 20% of the triangles (Decimate, planar for buildings, collapse for organic shapes).
3. Far away, swap to an impostor card (see impostor).
4. Let the engine pick by screen size.

**Defaults:** `lod_ratios` = [1.0, 0.5, 0.2], `lod_threshold_pixels` = 4.0

**Check:** perf: triangles per view in the busiest and the widest views.

**Cost:** More disk and memory per model; none at run time.

**From:** oakhaven b22d441 (distance LODs for merged props), project.godot mesh_lod threshold_pixels=4 (higher visibly breaks baked buildings); the browser applies it to every world (scripts/kit/world_techniques.gd, off with manifest techniques: {"lod_chain": false})

### Impostor cards far away  (`impostor`, kit: manual)

Distant trees, buildings and mountains become a flat textured card: a few triangles instead of thousands.

**When:** Anything regularly seen beyond about 80-150 m.

1. Give the far object "impostor": <metres> in scene.json (about 80-150).
2. Run `iamar-world impostors <folder>` (renders 8 views of the model into a small atlas; needs a display), then `iamar-world tiers` so lower tiers get smaller atlases. Objects reused by hash (assets use) are skipped: they are not in the folder, so model your own copy if it needs a card.
3. The browser swaps model and card at that distance; many cards of one model are drawn together.

**Defaults:** `start_m` = 120

**Check:** preview the widest view; perf triangles drop.

**Cost:** A texture per model.

**From:** docs/WORLD_TIERS.md (impostor cards), oakhaven 802210a/906af53

### Merge static meshes per area  (`merge_static`, kit: automatic)

Many small props become one mesh per area and material: far fewer draw calls.

**When:** Props that never move: fences, crates, barrels, shelves, small furniture.

1. Nothing to do in a world package: the browser merges static pieces that look the same (same material colour, texture and settings) per 96 m area into one mesh with its own LOD chain (scripts/kit/world_techniques.gd, off with manifest techniques: {"merge_static": false}).
2. Help it: give props that belong together the same material (one shared colour atlas) instead of a material per model.
3. Impostor cards and custom shaders keep their own draw.
4. Know where the areas are: they are 96 m squares in x and z. From browser 446b4862 they start at the smallest x and z of the pieces that can merge, so a town up to 96 m across is one area wherever it sits. Older browsers (including the pinned kit runtime, kit/runtime.lock, until it moves past 446b4862) start them at the world origin, with edges at x = 0 and z = 0: a town laid out around (0, 0) is cut into four areas and every shared look draws four times (harbour blind test a5: 187 draws for one view, 126 after moving the whole town by (+67, 0, +45) into one area). For those, keep the town inside one square from 0 to 96 (spawn near (48, 0, 48)) or move everything by one offset when you write scene.json.

**Defaults:** `cell_m` = 96

**Check:** perf: draw calls per view under budget.

**Cost:** One bigger mesh per area; culling is coarser.

**From:** oakhaven scripts/world/prop_batch.gd (PropBatch, keeps per-instance transforms for the bake export), 'Fewer prop draw calls'; world packages: oakhaven lakeside village 446 -> 126 draw calls

### Instance repeated props  (`instancing`, kit: automatic)

One mesh drawn many times in a single call (MultiMesh): grass, flowers, rocks, trees.

**When:** The same model placed more than about 10 times.

1. Place one model many times with an instance list instead of copies.

**Check:** perf: draw calls.

**Cost:** Instances share one LOD choice per batch.

**From:** oakhaven scripts/world/prop_batch.gd MultiMesh; the browser applies it to every world (scripts/kit/world_techniques.gd, off with manifest techniques: {"instancing": false})

### Thin far foliage  (`foliage_thinning`, kit: automatic)

Grass and flowers fade out with distance; trees are split into cells so culling works.

**When:** Any ground cover or forest.

1. Split foliage into cells (e.g. 30-45 m).
2. Reduce density with distance and stop at a visibility range.

**Defaults:** `visibility_end_m` = 90, `margin_m` = 8

**Check:** perf in open views.

**Cost:** Far ground looks a little barer.

**From:** oakhaven b22d441 (thinned far foliage, split tree cells), prop_batch.gd visibility_range_end; the browser applies it to every world (scripts/kit/world_techniques.gd, off with manifest techniques: {"foliage_thinning": false})

### Simple collision shapes  (`collision_proxy`, kit: manual)

Physics uses boxes and capsules, not the visual triangles.

**When:** Everything except floors and stairs people walk on.

1. Use collision: box for houses you do not enter, rocks, crates.
2. Use mesh only where people walk.
3. Props are obstacles, not ground.

**Check:** validate warns about mesh collision on big decorative models.

**Cost:** None.

**From:** docs/WORLD_FORMAT.md 4.4 collision; oakhaven 'props are obstacles, not ground'

### Weld identical vertices  (`weld_vertices`, kit: manual)

A mesh built as separate triangles (3 vertices per triangle, nothing shared) is indexed: corners that are equal in every attribute become one vertex. Same picture, far fewer vertices to build, upload and hold.

**When:** Any mesh you assemble in code or export as a triangle soup; check with vertices per triangle (about 3.0 = soup, 0.6-2.2 = indexed).

1. Merge only vertices equal in EVERY attribute (position, normal, tangent, colour, UV, lightmap UV, bones); keep hard edges and UV/lightmap seams split.
2. Keep the triangle order, so anything that hashes or bakes the mesh sees the same corners.
3. Weld before generating LODs; never weld across a lightmap seam or the bake shifts.

**Check:** vertex counts before/after per mesh; the same views shot before and after with the clock frozen are pixel-identical.

**Cost:** A little build time.

**From:** iamar-fps F11 1ebfb903 (city vertices 3.40M -> 3.12M, far prop copies -81 %, lamp glows -82 %; docs/perf/fps_f11_index_soup.md)

### Masterplan houses, convex-wing roofs and door arches from a style profile  (`masterplan_house`, kit: automatic)

A finished-looking town house in under 3000 triangles: the city's own house builder (stone or limewash ground storey, quoins and timber corner posts, half-timbered upper storeys, a jettied front on carved brackets, an oriel, a round corner tower, a framed door under a round stone arch, windows with shutters) under a hipped roof that covers any L-, T- or U-shaped footprint, closed and culled, with LODs.

**When:** Every iamar-family building that is not a landmark; a custom look reuses it with its own style profile (colours, dimensions, painted layers).

1. `iamar-world style-gen house out.glb --profile <profile> --region <region> --seed N --footprint rect|narrow|L|T|U|WxD|points.json --world preview --check`: writes LOD0-2, fits LOD0 to the profile's building budget (drops shutters, sills, side quoins, then timber braces, posts and rails) and runs the closure, roof and zfight audits on every LOD.
2. Timber frame on the upper storeys: `--timber plain|post|studs|braced|crossed` or, by default, picked by seed from the region's (else the profile's) `timber_frame_weights`; the iamar profile frames town houses ([0, 1, 3, 3, 2]) and keeps the city's quarter weights (mages mostly plain). Rails and posts stand 6 cm proud, braces 3 cm, all clear of windows, shutters, quoins, oriel and tower; a Track B profile without weights stays plain. Never leave an iamar town house a plaster box between quoins: the harbour blind test a5 did (review gap R3).
3. Roof alone over any footprint: `iamar-world style-gen roof out.glb --footprint L --eaves 6`; a door surround: `iamar-world style-gen arch out.glb --width 1.3 --ceiling 3.6`.
4. Paint the profile's layers (`check_style.py --paint textures --profile <profile>`) and pass `--textures textures`: each part takes its layer's painted texture (1 UV unit = 4 m), a paint colour on a shared layer stays in the base colour factor.
5. Tall houses: the roof stays a third to a half of the height when the profile gives `roof_height_fraction` (iamar does); style-gen prints `WARN roof` when a narrow wing (an L or U arm, a 6 m deep house of 3+ storeys) cannot reach it under the pitch ceiling: make it deeper or lower.
6. Vary houses by seed and region; never place one seed twice side by side (the variety rules, kit/style/variety).
7. Then bake light (kit/blender bake_unlit.py) and run the review gate.

**Defaults:** `budget_lod0` = 3000, `lods` = 3, `quoin_course_m` = 0.36, `eave_overhang_m` = [0.42, 0.66], `cap_w_m` = 0.17

**Check:** kit/tests/style/gen/style_gen_test.py (audits on every LOD, budget, plan area of the roof = footprint, determinism), kit/tests/style/gen/frame_test.py (each timber pattern's pieces, audits, profile defaults); `--check` per build.

**Cost:** None at run time; one generator run per house.

**Kit tool:** `kit/style/gen/gen.py`

**From:** the iamar browser source (not public) scripts/world/masterplan/mp_roof.gd (A20 convex wings, the maintainer 2026-10-09 'see the roofs rather than mesh openings'), mp_style.gd (dress_corners, jetty_brackets, door_arch, corner_tower), mp_buildings.gd (_emit_oriel; _base_style and _emit_facade_varied timber-frame language and quarter weights); ported in iamar-kit kit/style/gen (an internal task; timber frame an internal task, harbour a5 review docs/reviews/2026-10-22-an agent-blindtest-harbour-a5.md gap 3)

## Visibility

### Occluders on big walls and buildings  (`occluders`, kit: planned)

Things hidden behind a castle wall or a hall are not drawn at all.

**When:** Large solid walls, buildings and hills between areas.

1. Add simple occluder boxes inside big solid shapes.
2. Turn occlusion culling on.

**Check:** perf: draw calls behind walls drop.

**Cost:** A little CPU per frame.

**From:** oakhaven b22d441 (castle and garden occluders), project use_occlusion_culling=true

### No live shadows on tiny props  (`tiny_no_shadow`, kit: automatic)

Small props do not cast real-time shadows (the bake already darkens under them).

**When:** Props smaller than about 1 m.

1. Set cast_shadow false on small props.

**Defaults:** `max_size_m` = 1.0

**Check:** perf: shadow draw calls.

**Cost:** None visible.

**From:** oakhaven b22d441; the browser applies it to every world (scripts/kit/world_techniques.gd, off with manifest techniques: {"tiny_no_shadow": false})

### A pool of real lights  (`light_pool`, kit: automatic)

Only the few lamps nearest the camera get a real light; the rest glow through their material.

**When:** Towns and halls with many lamps.

1. Register every lamp with its position.
2. Each moment, give the nearest few a real light.
3. Place each light from its fixture's transform (never a separately typed position).

**Defaults:** `real_lights` = 6

**Check:** night screenshots: glows sit in the fixtures.

**Cost:** Far lamps light nothing around them (until night lamps are baked).

**From:** oakhaven scripts/world/light_pool.gd (POOL=6), d5a0e98 Buildings.light_at; the browser applies it to every world (scripts/kit/world_techniques.gd, off with manifest techniques: {"light_pool": false})

## Lighting

### Blender Cycles light bake (sky and sun)  (`bake_sky_sun`, kit: manual)

Sky light and sunlight with soft shadows are baked into a texture, so static glTF scenery is lit for free without double-lighting.

**When:** Static architecture and big props that you author in Blender; primitives and reused assets stay live-lit.

1. Export the static model or area from Blender as a .glb with its ordinary materials (and any lamps as Blender lights).
2. Run `iamar-world blender-run kit/blender/bake_unlit.py -- in.glb assets/out.glb [samples]` (options: --sun x,y,z towards the sun in glTF axes, --sky-strength, --no-sun for interiors, --texel, --max-size, --per-object). It adds a non-overlapping lightmap UV set, sizes the texture from the surface area, bakes colour x (sky + sun + bounce + lamps) + glow with Cycles (GPU when found) and exports one texture per mesh with KHR_materials_unlit, so the browser shows the bake once instead of lighting it twice.
3. Skinned, animated and alpha (foliage, invisible collision) meshes stay live-lit with their own materials; keep moving characters, creatures, doors and flames out of baked files.
4. Look at the result (`iamar-world blender-run kit/blender/look.py -- /tmp/look assets/out.glb --shading flat`), then in `iamar-world preview`.
5. Bake interiors separately from shells, and rebake after any geometry change.

**Defaults:** `texel_m` = 0.1, `max_size` = 4096, `samples` = 128

**Check:** preview the static model from lit and shadowed sides; confirm the bake is visible once and no surface is black.

**Cost:** Bake time and one lightmap texture per object.

**Kit tool:** `kit/blender/bake_unlit.py`

**From:** kit/AGENT_KIT.md baked-lighting gotcha and Blender glTF KHR_materials_unlit; oakhaven tools/blender/mission_hall.py bake, tools/bake_light.py GPU selection

### Baked ambient occlusion in vertex colours (the time-independent bake)  (`bake_ao_vertex`, kit: manual)

Characters, animals and props get soft contact darkness baked in, so they sit in the world; in a world whose clock runs, the static models get it instead of a time-of-day bake, so it holds at every hour and on the low tier (no shadows).

**When:** Anything that moves (so it cannot use a lightmap), small props, and low-poly buildings with the soft --max-edge settings. Every static model you authored when `day_length_minutes` > 0: a time-of-day bake (bake_sky_sun, bake_vertex_light) is right at one hour only.

1. Run `iamar-world blender-run kit/blender/bake_vertex_ao.py -- in.glb assets/out.glb --distance <about a tenth of the model's size>` (--local when parts move apart). It bakes AO with Cycles and multiplies it into COLOR_0 (existing vertex colours are kept); skins and animations are exported unchanged.
2. The browser multiplies vertex colours into the base colour, so materials stay ordinary lit materials: the live sun, clock and shadows still light the model.
3. Neighbours: `python3 kit/style/lighting/lighting.py ao-args --world W --object ID [--reach 3]` prints `--occluder` options for the world's other placed .glb models near the object (in its frame; swaying and animated ones left out). Add them to the bake so the street or quay a house stands on gets the dark band round its foot, and a house the darkness of its neighbour. Terrain and primitives cannot be baked or occlude: make a ground that should take contact darkness a .glb.
4. AO is only as fine as the mesh: add a few edge loops where contact shadows should fall (a 0.5 m grid on a street or yard .glb).
5. Low-poly buildings: corner darkness spreads over whole wall faces (plaster 0.85 became 0.59). Add `--max-edge 2 --floor 0.6 --strength 0.7` (splits long edges first, about twice the triangles; check the tier budget), or give buildings no AO at all and rely on live sun and shadows.
6. The output's asset.extras.iamar_bake.kind is `sky_ao`; `iamar-world audit dark-bake` lists those objects (`sky_ao_objects`) and warns on a running clock when nothing is baked or an unlit time-of-day bake is used. FAILED: harbour blind test a5 kept every model live-lit because the lighting README said a running clock rules out baking, so the low tier had no contact shadows anywhere.

**Defaults:** `distance_m` = 0.5, `floor` = 0.25, `samples` = 64

**Check:** `python3 kit/tests/blender/sky_ao_bake_test.py`: a ground baked with its neighbour is dark only under and beside the turned house, white elsewhere, lit materials, sky_ao marker reported by audit dark-bake. Preview: no floating look.

**Cost:** A short bake at build time; nothing at run time.

**Kit tool:** `kit/blender/bake_vertex_ao.py`

**From:** oakhaven AnimalKit (hemisphere-ray AO), tools/bake_chicken_ao.py; running clock: docs/reviews/2026-10-22-an agent-blindtest-harbour-a5.md gap 1, an internal task

### Painted maps + baked light (light in vertex colours)  (`bake_vertex_light`, kit: manual)

Painted architecture keeps its shared 256 px/m library maps and still gets baked sky, sun and bounce light: the light is stored per vertex, not in a texture.

**When:** Static houses, walls and big props that use painted maps (`materials use`) and must pass `materials texel`. A glTF material has one colour texture and the browser reads no lightmap slot, so bake_sky_sun would replace the painted map by a 10-40 px/m bake.

1. UV-map the model to the painted maps at 256 px/m (a 1024 map per 4 m, or a 512 map per 2 m: `materials use --size 512` keeps five textured houses inside the 64 MiB budget, because every .glb pays for its own embedded maps).
2. Run `iamar-world blender-run kit/blender/bake_vertex_light.py -- in.glb assets/out.glb [samples] [--grid 1.0]` (the same --sun, --sky-strength, --no-sun and --lamp options as bake_unlit.py). It cuts the static meshes on a --grid lattice, splits hard edges, bakes light with Cycles into COLOR_0 and exports the original materials unlit.
3. Skinned, animated, alpha and emissive meshes stay live-lit with their own materials.
4. LODs: decimate the unbaked model (`lods.py`), then bake each level (LOD1 --grid 2, LOD2 --grid 0). FAILED: decimating the baked model removes the grid and the light with it (1,400 triangles fell to 44, lit only at the corners).
5. Open sheets (cloaks, banners, generated meshes with flipped triangles): Cycles bakes the side a normal points to, and a double-sided face shows one COLOR_0 from both sides. The bake turns double-sided faces whose normal side is enclosed and whose back is open to the open side (--no-orient keeps the normals). FAILED before that: about 400 cloak faces of the catalogue hero_w1 baked black and the browser showed a black cloak from behind. A sheet whose two sides must differ needs thickness or a flipped single-sided copy (kit/recipes/statue/statue.py).
6. Check with `iamar-world materials texel`, `materials budget`, `lint` and `audit all` on the world.

**Defaults:** `grid_m` = 1.0, `samples` = 64

**Check:** `python3 kit/tests/blender/vertex_light_test.py`: five baked houses pass texel, budget, lint and audit; sun side brighter than shade side. `python3 kit/tests/blender/bake_vertex_light_sheet_test.py`: a cloak facing the body, hero_w1 and the statue recipe bake with no visible face under 0.05.

**Cost:** Triangles grow with the grid (a 6 x 5 m house: about 1,000 at 1 m, 3,000 at 0.5 m); shadows are only as sharp as the grid.

**Kit tool:** `kit/blender/bake_vertex_light.py`

**From:** kit/blindtest/harbour/attempt-3/gaps.md G5, G6 (harbour blind test attempt 3, 071465c); browser the iamar browser source (not public) scripts/worlds/world_package.gd _glb_vertex_colours (COLOR_0 multiplies albedo) and Godot GLTFDocument KHR_materials_unlit -> unshaded (checked headless, an internal task); open sheets: an internal task (iamar.26 black cloak), an internal task

### Keep lightmaps lossless  (`lightmaps_lossless`, kit: planned)

Lightmaps are not VRAM-compressed: compression pads them to a multiple of 4 and shifts the light.

**When:** Every lightmap, unless the bake writes block-aligned sizes.

1. Import lightmap PNGs with lossless compression.
2. Know the cost: Godot keeps them RGB8 (lossless and VRAM-uncompressed both; channel_pack does not apply), and GPUs store RGB8 padded to 4 bytes a texel, so a 2-channel sky/sun map costs as much as RGBA.
3. To compress (BC5/RGTC, a quarter of the memory): make the bake write sizes that are a multiple of 4 (with the lightmap UVs scaled to match) and rebake; then check the hard-shadow views, where BC5 errs most (up to ~31/255 before filtering).

**Check:** screenshot diff after import changes.

**Cost:** More VRAM than compressed: iamar city 198 maps, 90 Mpx, ~458 MB lossless vs ~115 MB BC5.

**From:** oakhaven 00b844a perf pass; iamar-fps F3a 0f1c6e94 (docs/perf/fps_f3a_lightmap_vram.md: BC5 error, RG8 PortableCompressedTexture2D identical but 7-8x slower to load, RG8 DDS reads back as LA8)

### Live light only for what moves  (`live_only_moving`, kit: planned)

Characters get live shadows only where the bake has sun; lamps stay live via the light pool.

**When:** Always.

1. Use the bake for static things; live light and shadow only for characters and moving objects.

**Check:** perf: shadow cost.

**Cost:** None.

**From:** oakhaven bake.gd notes

### Bevel and normal maps from high-poly  (`bevel_normals`, kit: manual)

Bevels and fine detail are baked from a high-poly version into normal maps, so low-poly meshes read as carved.

**When:** Buildings, furniture, weapons.

1. Model or bevel a high-poly version in the same place and scale as the game mesh; export both as .glb.
2. Run `iamar-world blender-run kit/blender/bake_normals.py -- high.glb low.glb assets/out.glb --size 1024`. The low mesh needs non-overlapping UVs (or --unwrap). It wires the tangent-space map into every material of the low mesh, exports tangents (--save-map also keeps the PNG; keep it outside assets/).
3. Do not combine with bake_sky_sun on the same model: unlit materials ignore normal maps (bake the light from the high-poly instead).

**Defaults:** `size` = 2048, `cage` = 0.02, `distance` = 0.04

**Check:** preview close-ups.

**Cost:** A normal map per material.

**Kit tool:** `kit/blender/bake_normals.py`

**From:** Graphics list item 3; iamar-models tools/mesh3d/bake_v2.py; kit/blender/starter_build.py uses real bevels

### Lanterns that read as lit at dusk and night  (`lit_lantern`, kit: manual)

Street and wall lanterns whose glass glows warm from every side, paired with a point light that lights the street around them.

**When:** Every lamp a brief promises at dusk or night (quays, doors, lanes, bridge ends).

1. `iamar-world style-gen lantern assets/lantern.glb [--mount post|wall] [--height 2.6] [--glow 1.3] --json`: an open iron frame (base plate, four corner bars, pyramid cap) around emissive glass in the profile's `lamp_glow`, LOD0-2 within the prop budget; `--world preview --check` shows it at night with its light.
2. Copy the report's `light` into scene.json `lights` once per lantern, adding the object's position (rotated by its yaw): a point light at the glass centre, energy 1.4, range 9, no shadows. Keep to the manifest's `lights` budget (under 8 in a small world; the browser gives the nearest few a real light, light_pool).
3. Never put the glass inside a closed shell: the harbour blind test hid emissive glass inside a solid iron lathe and its lanterns read as dark grey boxes at night.
4. Keep `--glow` at 1-2: higher clips the glass to white in the browser's linear tonemap and loses the warm colour.
5. Lanterns are props: keep them live-lit (pipeline --light ao, not a light bake), and bake their light into the walls with bake_night when the world is seen at night.

**Defaults:** `glow` = 1.3, `light_energy` = 1.4, `light_range_m` = 9, `post_height_m` = 2.6, `budget_lod0` = 300

**Check:** kit/tests/style/gen/style_gen_test.py (glass visible: no iron face in front of it, emissive strength set, audits on every LOD, light at the glass centre); night shots: the glass is warm, not white, and a pool of light lies on the ground; kit/style/lighting/gallery/night_bake.

**Cost:** ~100 triangles per lantern; one real light each (the nearest few are live).

**Kit tool:** `kit/style/gen/gen.py`

**From:** harbour blind-test review (docs/reviews/2026-10-20-an agent-blindtest-harbour.md gap 3, sheet_n); iamar-kit kit/style/gen/lantern.py (an internal task)

### Bake the time of day the world is seen at  (`bake_night`, kit: manual)

A light bake is one time of day: walls baked in daylight stay day-bright under a black night sky. Baking the night (moonlight, a dim blue sky and the lanterns as lamps) gives dark walls with warm pools by each lamp.

**When:** A world that sits at dusk or night, or whose brief promises lamps at night, with light-baked (unlit) architecture.

1. Choose the world's lighting preset (kit/style/lighting presets; a world with running time keeps its walls live-lit instead: one bake cannot show both day and night).
2. Place the lanterns and their point lights in scene.json first (lit_lantern).
3. Per baked object: `python3 kit/style/lighting/lighting.py bake-args <preset> --world <world> --object <id>` prints bake_unlit options: the preset's sun or moon (direction, colour, energy x pi), its ambient as the sky, and every point light within its range + 12 m as `--lamp x,y,z,r,g,b,watts` in the object's own frame (45 W per unit of energy).
4. `iamar-world blender-run kit/blender/bake_unlit.py -- in.glb assets/out.glb 64 --texel 0.03 <those options>`.
5. Shoot the world at the time it is set to and at night (`iamar-world shots --times dusk,night`) and compare with the daylight bake (kit/style/lighting/night_bake_demo.py does both on a sample house).

**Defaults:** `watts_per_energy` = 45, `reach_m` = 12, `samples` = 64

**Check:** kit/tests/style/lighting_test.py (bake-args: preset sun, sky and lamps in the object's frame); kit/style/lighting/gallery/night_bake/night_bake_pair.jpg (before: daylight bake at night; after: night bake).

**Cost:** One extra bake per object for each look you ship; the bake shows one time of day only.

**Kit tool:** `kit/style/lighting/lighting.py`

**From:** harbour blind-test review gap 3 (sheet_n: walls stay bright at night); iamar-kit kit/style/lighting/lighting.py bake-args, kit/blender/bake_unlit.py --lamp (an internal task)

### Sky ambient only with a still sun  (`sky_ambient_still_sun`, kit: manual)

Ambient light taken from the sky makes the renderer rebuild the sky's light every time the sun moves; with a still sun it is built once and costs nothing after.

**When:** Any world that sets environment.ambient.source to "sky".

1. Keep `ambient.source: "color"` (the default) unless the sky's tint on shadowed sides really matters; pick the colour from the sky's horizon, darker.
2. Use `ambient.source: "sky"` only with a fixed `time_of_day` or `sun.direction` (today's format has no moving sun).
3. A sky that is only the background, with colour ambient, never builds sky light at all.

**Defaults:** `ambient_source` = "color"

**Check:** compare a shot with colour and sky ambient; keep sky only if the difference is visible.

**Cost:** Sky ambient + a moving sun: +10 ms CPU / +9 ms GPU per frame on software GL (iamar tools/k5_5_sky_probe.gd); a still sun: one rebuild at load.

**From:** iamar docs/perf/K5_5_ENVIRONMENT_RULES.md (an internal task): Godot GLES3 rebuilds sky radiance on any sky-visible light change when the sky feeds ambient/reflections; stepping the sun 0.05 deg/0.5 s only recovers ~2.5 ms

## Materials

### One shared wind  (`shared_wind`, kit: planned)

Grass, flowers, trees and flags all sway from one wind value: one uniform, no per-object scripts.

**When:** Any vegetation or cloth.

1. Drive vertex-shader sway from one global wind value.

**Check:** perf: no per-frame scripts for sway.

**Cost:** None.

**From:** oakhaven 'One shared wind for grass, flowers, trees and flags'

### Time-of-day palettes, haze and weather  (`atmosphere`, kit: manual)

Sky, fog, haze and glow follow the time of day; rain and storms; wetness as one shader parameter.

**When:** Outdoor worlds.

1. Use the browser's environment settings (scene.environment) rather than custom per-object effects.

**Check:** preview at several hours.

**Cost:** Small.

**From:** oakhaven 'Atmosphere and weather', Mats.set_wetness

## Textures

### VRAM texture compression and mipmaps  (`texture_compression`, kit: planned)

Textures are BC7 (desktop) and ETC2/ASTC (Apple Silicon) with mipmaps: about half the video memory.

**When:** Every texture except lightmaps.

1. Import with VRAM compression (high quality) and mipmaps on; enable ETC2/ASTC import for macOS.

**Check:** perf: VRAM in the busiest view.

**Cost:** More disk than lossless.

**From:** oakhaven 00b844a (457 -> 250 MB on Amber), 887bd83 (ETC2/ASTC)

### Right-sized textures and atlases  (`texture_sizes`, kit: manual)

Small textures for small or far things, atlases to share one material across many props.

**When:** Every material.

1. Pick the smallest size that looks right at the closest normal view.
2. Share atlases between props in one area.

**Check:** validate: texture budget.

**Cost:** Authoring time.

**From:** WORLD_FORMAT budgets

### Seamless hand-painted material textures  (`painted_materials`, kit: manual)

Stone, ashlar, granite, plaster, timber, slate, glazed tiles, shingles, thatch, cobbles, iron and a trim sheet, painted procedurally so every texture tiles exactly and shares one texel density.

**When:** Buildings, roofs and streets that need a coherent painted look without photo textures or downloads.

1. Run `python3 kit/tools/paint_materials.py <world>/textures --materials stone,timber,slate --size 512` (numpy and Pillow only; --tint NAME=#RRGGBB colours one; --list names them).
2. UV-map models at 4 m per texture repeat (one UV unit = 4 m) so every material keeps the same texel density; roof UVs run down the slope; trim mouldings map onto one of the trim sheet's 8 strips.
3. Use the PNG as the material's Base Color in Blender, then bake light (bake_sky_sun) or leave it live-lit.

**Defaults:** `tile_m` = 4.0, `size` = 1024

**Check:** preview: no visible seams or stretching; texel density alike on neighbouring surfaces.

**Cost:** One texture per material, shared between models.

**Kit tool:** `kit/tools/paint_materials.py`

**From:** oakhaven tools/mp_textures/paint_library.py (the masterplan city's painted library)

### Texel density and texture budget  (`texel_budget`, kit: manual)

Near surfaces stay as sharp as the city's (256 px per metre) and the world's texture memory stays inside its budget, checked by a command instead of by eye.

**When:** Every world that uses painted materials, before the independent review gate.

1. Write the profile's tints into the world: `iamar-world materials use <world> --profile <world>/style.json` (13 library maps tinted per layer; `--size 512` or `256` for a low tier).
2. UV-map at 1 UV unit = 4 m, then run `iamar-world materials texel <glb|world> ...`: it fails any surface below the rule.
3. Run `iamar-world materials budget <world> --profile <profile>`: it sums texture memory against the budget; drop sizes (texture_sizes) until it passes.
4. `iamar-world materials list|check|sample` show the library, verify its hashes and build the sample world.

**Defaults:** `tile_m` = 4.0, `px_per_m` = 256

**Check:** `materials texel` and `materials budget` exit 0 before review.

**Cost:** None at run time.

**Kit tool:** `kit/style/materials/materials.py`

**From:** iamar-kit b073489 kit/style/materials/materials.py (an internal task)

### Converted-model cache  (`gltf_cache`, kit: automatic)

Converted glTF scenes are cached, so a second visit opens faster.

**When:** Automatic in the browser.

1. Nothing to do as a builder.

**Cost:** Disk cache.

**From:** oakhaven scripts/worlds/world_cache.gd

### Store every texture once  (`textures_once`, kit: manual)

A model whose maps are embedded in a .glb gets them extracted again by Godot's import, so the repository and the build carry each texture twice. Ship the model as glTF with separate files instead.

**When:** Every textured model you add (sculpted statues, baked props).

1. Export glTF separate: `name.gltf` + `name.bin` + `name_albedo.png` + `name_normal.png`, one folder per model (Blender: export_format GLTF_SEPARATE; `iamar-models tools/mesh3d/bake_stone.py ... out.gltf` does it).
2. Name the images after the model so two models never share a texture file name.
3. Point the game at the .gltf; shoot the same views before and after: only animated things may differ.

**Check:** repository size of the asset folder; before/after shots.

**Cost:** None.

**From:** iamar gate statues 0e042740 (four statues 57 MB -> 29 MB, no visible change)

## Loading

### Stream terrain in chunks  (`streaming`, kit: planned)

Only the terrain near the player is built and refined.

**When:** Worlds larger than a few hundred metres.

1. Split terrain into chunks and build near ones first.

**Defaults:** `chunk_m` = 90

**Check:** frame-time metrics while walking.

**Cost:** Code complexity.

**From:** oakhaven scripts/world/terrain.gd CHUNK=90

### Build progressively, in time slices  (`progressive_build`, kit: planned)

Heavy building work runs in small slices across frames (and on worker threads) so the game never freezes.

**When:** Big worlds and any build step over a few milliseconds.

1. Split work into slices of about 10 ms per frame.
2. Commit meshes on worker threads.
3. Hide the first heavy frames behind the world-switch fade and progress bar.

**Defaults:** `slice_ms` = 10

**Check:** perf: no frame over 50 ms after load.

**Cost:** Things appear over a few seconds.

**From:** oakhaven town.gd slice_usec=10000, 'take the load stutters off the main thread', 00b844a progress bar

### Physics interpolation  (`physics_interp`, kit: automatic)

Movement is smooth at any frame rate.

**When:** Always.

1. Keep physics interpolation on (project setting).

**Cost:** None.

**From:** oakhaven project.godot physics_interpolation=true

## Quality

### Quality presets and auto-tune  (`quality_presets`, kit: manual)

Fast / Balanced / higher presets with a first-run auto-tune; worlds must look pleasant on the lowest.

**When:** Every world.

1. Design for the low tier first, then add detail that lights up on better GPUs.

**Check:** perf on Amber-class hardware (HD 5750, 1 GB) at 30 fps.

**Cost:** Testing several tiers.

**From:** oakhaven presets and _auto_tune; GPU tiers item (planned)

### Native OpenGL on Windows  (`native_gl_windows`, kit: manual)

On Windows x86 the GL Compatibility renderer runs straight on the driver's OpenGL; ANGLE (OpenGL over Direct3D) is only for devices known to need it. Faster and it draws correctly.

**When:** Every project on the Compatibility renderer that ships for Windows.

1. project.godot: `rendering/gl_compatibility/driver.windows="opengl3"`.
2. `force_angle_on_devices`: Godot's default list (old Radeon HD/R, Intel HD, old Iris) plus `{vendor: Microsoft, name: *}` (OpenGL-on-D3D12, the only GL on Windows ARM64/Snapdragon) and `{vendor: Qualcomm, name: *}`; setting the key replaces the defaults, so write them out.
3. Leave `fallback_to_angle` on: a PC whose native GL fails to start gets ANGLE.
4. Do not use a two-feature key such as `driver.windows.arm64`: Godot 4.7 ignores it silently.

**Check:** frame time A/B with `--rendering-driver opengl3` vs `opengl3_angle` at fixed views (tests/masterplan_city/render_time_probe.gd); shots compared.

**Cost:** None.

**From:** iamar-fps F5 ef84861d (Intel Arc 140V: mean frame -26 %, p95 -40 %, render CPU -25 %; ANGLE drew torn cloud bands and wall dither; docs/perf/fps_f5_windows_driver.md)

## Feel

### Responsive movement  (`movement_feel`, kit: automatic)

Jump grace (coyote time and a jump buffer), step-up only on steep collisions, floor snap, an eased camera that never clips into walls and fits rooms indoors.

**When:** Built into the browser; keep walkable slopes and doorways reasonable.

1. Keep doorways at least 2.2 m high, stairs shallow, walkable slopes under 40 degrees.

**Defaults:** `jump_grace_s` = 0.15, `floor_snap_m` = 0.9

**Check:** walk every path and portal.

**Cost:** None.

**From:** oakhaven player.gd JUMP_GRACE, floor_snap_length, c17e70d

## Network

### Lean networking  (`network`, kit: automatic)

Fast unreliable 15 Hz state, reliable events, Opus voice by distance, rarest-first parallel piece download, peers sharing pieces, per-peer rate limits.

**When:** Built into the browser.

1. Keep packages small so first visits are fast; nothing to do in world data.

**Cost:** None.

**From:** oakhaven scripts/net/*, scripts/shell/world_fetcher.gd, world_swarm.gd

## Interface

### Build a page once, then patch it  (`ui_pages`, kit: manual)

Shops, journals, notice boards and menus as world UI pages: JSON the browser builds from its own controls, kept cheap by building once and changing single nodes.

**When:** Any world UI beyond a line of text or one button (ui_text / ui_button / ui_bar stay for those).

1. Describe the page as data with the typed builders in api/typescript/iamar-world.d.ts (UiPage, UiNode): column/row/grid/panel for layout, text/heading/image, button/link/input/textarea/checkbox/slider/select for input, list for long lists. No HTML, no URLs.
2. Give every node the script will patch, read or hear from its own `id` (1-65535, unique in the page).
3. Call `ui_page_set` for every page in on_init (they start hidden), then `ui_page_show` when needed. After that send only `ui_page_patch(page, node, {...})` for what changed; never re-set a page to change one label.
4. Handle `on_ui_event(page, node, kind)`: 1 click, 2 change, 3 submit, 4 link, 5 the player closed a modal. Read an input with `ui_value` when you need it.
5. Style with a page `theme` (bg, fg, accent, border, font) and per-node `style`; colours are #rrggbb[aa], sizes px or "50%".
6. Lower the manifest UI budgets to what the world uses (max_pages, max_page_nodes, page_nodes_total, max_surfaces, max_page_images) and declare api_version 0.4.

**Defaults:** `max_pages` = 8, `max_page_nodes` = 512, `page_nodes_total` = 2000, `page_bytes` = 65536, `patch_bytes` = 8192, `patches_per_s` = 60

**Check:** `iamar-world validate` checks the manifest budgets; tests/typescript-world/ui_shop_sandbox.gd shows the pattern under test.

**Cost:** A built page costs nothing while idle; a full re-set rebuilds every control (sliced over frames for big pages).

**From:** iamar-ui-pages U1-U4 (docs/WORLD_UI_PAGES_DRAFT.md, api/ui_page.schema.json); example examples/typescript-ui-shop/

### Overlay, modal or surface  (`ui_page_modes`, kit: manual)

Pick where a page appears: a corner panel, a centred dialog that takes the keys, or a sign drawn on an object in the world.

**When:** Overlay (mode 1) for small always-on panels (coins, objectives); modal (2) for things the player reads or fills in (journal, dialogue choices, a form); surface (3) for things that belong to a place (shop counter, notice board, a screen).

1. Overlay: keep it small; overlays share one column drawn under the browser's own UI, so they never cover it.
2. Modal: open it on a key (`input_bind`) or a button. Esc and the frame's close button always close it and send kind 5: save what the player typed then. For 1.5 s after the player closes a modal, a new one is refused (E_LIMIT); do not retry in a loop.
3. Surface: spawn a box (the page fills its +Z face) or a plane (its top), `ui_page_surface(page, w, h)` with the face's aspect (128-1024 px a side), then `ui_page_show(page, 3, entity)`. At most 4 surfaces; past 40 m they stop updating, the player clicks them within 15 m.
4. Game keys are muted while the player types in a page field; do not bind letters you need while a modal is open.

**Defaults:** `max_surfaces` = 4, `surface_px` = [512, 512], `surface_update_m` = 40, `surface_click_m` = 15, `modal_reopen_s` = 1.5

**Check:** Walk up to every surface and open every modal in the preview; Esc closes each modal.

**Cost:** A surface renders only after a change (patch, input); idle surfaces cost no GPU time.

**From:** iamar-ui-pages U4/U5 (scripts/sandbox/world_ui/ui_page_host.gd, ui_page_surface.gd); example examples/typescript-ui-shop/

### Long lists and pictures in pages  (`ui_page_lists`, kit: manual)

Inventories, logs and notice boards with hundreds of rows stay smooth, and pages can show the world's own pictures.

**When:** Any list longer than about 20 rows; any icon or picture in a page.

1. Use a `list` node (items + max_height): only the rows in view are built, up to 1000 items. Replace its rows with one patch of `items`; do not patch rows one by one.
2. Keep rows simple and alike (a panel with a text and a button); give rows ids only when the script needs their events.
3. Images are `asset:<path>.png|jpg|webp` inside the signed package, decoded off the main thread: at most 32 per script, 2048 px a side, 16 MiB decoded in all. Use small icons (64-256 px), not photos.

**Defaults:** `list_items` = 1000, `max_page_images` = 32, `image_px` = 2048

**Check:** Scroll the longest list in the preview; images that break a limit show an empty frame and one log line.

**Cost:** Rows outside the view cost nothing; each image costs its decoded size in memory.

**From:** iamar-ui-pages U6 (scripts/sandbox/world_ui/ui_page_list.gd, ui_page_images.gd)

### Pages every visitor sees the same  (`ui_shared_pages`, kit: manual)

Scoreboards, shared notice boards and votes that show the same thing to everyone in the room, although every visitor's browser builds its own copy of the page.

**When:** Any page whose content belongs to the room rather than to one visitor; a visitor's own coins, journal or settings stay local (kv).

1. Every visitor runs their own copy of the script and builds the pages once in on_init, as usual. Only the content is shared, never the page itself.
2. One copy keeps the truth: the one where `is_authority()` is 1 (the visitor with the smallest player key). It alone changes the shared state.
3. Other copies send requests, not results: `message_to(authority, {"t":"ring"})`, where the authority's id is the player with the smallest `player_key` (the same rule). The authority applies its own requests directly.
4. The authority judges a request by its sender (the player id on_message_from gives it), never by a name or key inside the bytes; rate-limits each sender and cleans text (control and bidi characters out, length capped).
5. After a change the authority broadcasts the whole state with `world_message`, at most every 0.25 s (a burst costs one message), kept under 1 KiB (drop the oldest rows to fit). Every copy patches it into its pages (`ui_page_patch` of the list `items` and the texts that changed).
6. A copy accepts a state only from the player it counts as the authority, and from the same authority only a newer revision. A newcomer gets the state because the authority marks it dirty in on_enter.
7. Every copy keeps the last state, so when the authority leaves, the next one (its own is_authority turns 1 in on_tick) bumps the revision and carries on. is_authority is coordination, not security: a hostile visitor can arrange to be it.

**Defaults:** `messages_per_s` = 20, `message_bytes` = 1024, `state_every_s` = 0.25

**Check:** tests/typescript-world/ui_shared_sandbox.gd runs four visitors' copies wired like the net bridge: same pages everywhere, forged states and keys ignored, a late visitor and an authority handover.

**Cost:** One message per change burst to each visitor; pages are only patched, never rebuilt.

**From:** iamar-ui-pages U16; example examples/typescript-ui-shared/

## Measurement

### Drop triangles nobody can see  (`hidden_triangle_cull`, kit: planned)

Faces buried inside other geometry or never visible from any walkable place are removed before export: fewer triangles for free.

**When:** Merged areas and big buildings assembled from overlapping parts.

1. A kit command will find faces never seen from the walkable area and strip them; until then delete hidden faces by hand in Blender.

**Check:** perf: triangles per view drop, preview unchanged.

**Cost:** Build time.

**From:** oakhaven tools/city_vis, landmark far-LOD bake

### Rank models by cost  (`perf_rank`, kit: planned)

perf will list which models and shaders cost the most triangles and draw calls in each view, so you fix the worst first.

**When:** Whenever a view is over budget.

1. A `perf --rank` option will list the top models per view; until then compare perf numbers with models hidden.

**Check:** perf.

**Cost:** None.

**From:** oakhaven tri_rank and shader_census tools

### Find holes and open edges  (`open_edge_check`, kit: planned)

validate will report models with open edges or gaps between parts, where light leaks through a bake or the sky shows through a wall.

**When:** Every baked or enclosed model.

1. Until the check exists, look for gaps in Blender (Select > Select All by Trait > Non Manifold) before baking.

**Check:** validate.

**Cost:** None.

**From:** oakhaven masterplan_closure_audit

### Measure on the low-end machine  (`measure`, kit: manual)

Every change is measured before and after on Amber-class hardware, with fixed-view screenshots compared.

**When:** Always.

1. Run perf in the busiest view and the widest view.
2. Compare fixed-view screenshots before and after.
3. Report the numbers.

**Check:** perf, preview.

**Cost:** Time.

**From:** oakhaven tools/perf_probe.gd, autotest frame-time metrics

### Check the display before blaming vsync  (`display_refresh`, kit: manual)

A game pinned at exactly 30 fps with an idle GPU is often the monitor: vsync can only show as many frames as the display refreshes.

**When:** Whenever frame time sits at exactly 33.3 ms (or 16.7 ms) while the GPU and script times are far below it.

1. Read the display mode first (Linux: `xrandr`; Windows: display settings / DisplayServer.screen_get_refresh_rate()).
2. 4K offered only at 30/25/24 Hz with a 297 MHz pixel clock means an HDMI 1.4 link (TV input, cable or DP-to-HDMI adapter): fix it in hardware or run a 60 Hz mode.
3. On the Compatibility renderer, adaptive vsync acts as plain vsync on OpenGL, so changing it buys nothing.

**Check:** display mode listed in the perf report.

**Cost:** None.

**From:** iamar-fps F1 (the GPU host 3840x2160 at 29.97 Hz; 2560x1440@60 and 1080p@120 available)

## Art

### Cloud shadows  (`cloud_shadows`, kit: planned)

Slow-scrolling cloud shadows drift over the land: one texture sample in the terrain and baked shaders, big sense of life.

**When:** Outdoor worlds.

1. Enable the browser's cloud-shadow layer in scene.environment (density, speed, scale).

**Defaults:** `density` = 0.4, `speed_m_s` = 3.0

**Check:** preview over 10 s.

**Cost:** One texture sample.

**From:** Graphics ideas 2026-10-01 #1

### Terrain texture blending by slope and height  (`terrain_blend`, kit: planned)

Grass, dirt, rock and gravel chosen by slope and height with soft height-blended edges; triplanar rock on cliffs so nothing stretches.

**When:** Any terrain.

1. Assign terrain layers with slope and height ranges.
2. Use triplanar mapping on steep faces.

**Check:** preview cliffs and hills.

**Cost:** A few texture samples.

**From:** Graphics ideas #2

### Ground clutter  (`ground_clutter`, kit: planned)

Pebbles, fallen leaves, clover and mushrooms near paths and trees, instanced with LODs.

**When:** Wherever people walk outdoors.

1. Scatter small instanced props by rules (near paths, under trees, by water).
2. Thin them with distance.

**Defaults:** `visibility_end_m` = 40

**Check:** perf: draw calls stay in budget.

**Cost:** Instanced; small.

**From:** Graphics ideas #3

### Worn paths  (`path_wear`, kit: planned)

Darker trampled edges, cart ruts and puddle hollows along roads, painted into vertex colour or a terrain mask.

**When:** Roads and busy paths.

1. Paint wear along path splines into the terrain mask.

**Check:** preview roads.

**Cost:** Nearly free.

**From:** Graphics ideas #4

### Anisotropic filtering  (`anisotropic`, kit: automatic)

Ground textures stay sharp at grazing angles instead of blurring toward the horizon.

**When:** Ground, roads, floors.

1. Import ground textures with anisotropic filtering (4x-8x).

**Defaults:** `level` = 8

**Check:** preview long roads.

**Cost:** Nearly free.

**From:** Graphics ideas #5

### Per-instance colour variation  (`instance_tint`, kit: planned)

Every tree, bush, rock, roof and wall gets a slight random tint and brightness shift so copies stop looking copied.

**When:** Every repeated model.

1. Give each placement a small random tint (hue +-4%, value +-8%) through instance colour.

**Defaults:** `hue` = 0.04, `value` = 0.08

**Check:** preview a forest and a street.

**Cost:** Free.

**From:** Graphics ideas #6

### Smooth LOD transitions  (`lod_crossfade`, kit: planned)

A dithered crossfade between LOD levels, so trees and buildings stop visibly popping.

**When:** Every LOD chain.

1. Enable dithered LOD fade on LOD meshes.

**Defaults:** `fade_m` = 4.0

**Check:** walk toward a forest.

**Cost:** A little fill rate during the fade.

**From:** Graphics ideas #7

### Backlit leaves  (`leaf_translucency`, kit: planned)

Leaves and grass glow softly when the sun is behind them (wrap and transmission light in the foliage shader).

**When:** All foliage.

1. Use the foliage material with translucency on.

**Defaults:** `translucency` = 0.35

**Check:** preview against the low sun.

**Cost:** A few shader instructions.

**From:** Graphics ideas #8

### Grass that parts  (`grass_interaction`, kit: automatic)

Grass and flowers bend away from the player, townsfolk and horses as they walk through.

**When:** Grassy areas.

1. Nothing to do as a builder once the browser feature exists; use the standard grass material.

**Check:** walk through grass.

**Cost:** Small.

**From:** Graphics ideas #9

### Feet that follow the ground  (`foot_ik`, kit: automatic)

Foot IK plants feet on slopes and stairs instead of floating or sinking.

**When:** All characters (browser feature).

1. Keep stairs and slopes as real collision so feet can find them.

**Check:** walk up stairs and hills.

**Cost:** Small CPU per nearby character.

**From:** Graphics ideas #10

### Characters look at each other  (`look_at`, kit: automatic)

Heads turn toward nearby players and whoever they are talking to.

**When:** NPCs and players (browser feature).

1. Give NPCs a look_at radius if they should notice visitors.

**Defaults:** `radius_m` = 6

**Check:** talk to an NPC.

**Cost:** Tiny.

**From:** Graphics ideas #11

### Lively faces  (`faces`, kit: manual)

Eye highlights, blinking and varied idle animations so crowds do not move in sync.

**When:** All characters.

1. Use the built-in bodies, or give custom characters eye highlights and several idles.

**Check:** preview NPC close-ups.

**Cost:** Tiny.

**From:** Graphics ideas #12

### Soft ground shadows at distance  (`blob_shadows`, kit: automatic)

A simple soft shadow under every character and animal far away, where live shadows are off.

**When:** All characters and animals (browser feature).

1. Nothing to do for built-in characters; custom creatures declare a shadow radius.

**Check:** preview a crowd at distance.

**Cost:** One decal-like quad each.

**From:** Graphics ideas #13

### Lit windows at night  (`lit_windows`, kit: planned)

Windows glow warmly from inside, some flicker like candlelight, turning on and off through the evening (emissive only, no real lights).

**When:** Every building with windows.

1. Give window panes the window-glow material (it follows the time of day).

**Check:** night preview.

**Cost:** Free (emissive).

**From:** Graphics ideas #14

### Lived-in interiors  (`interior_dressing`, kit: manual)

Clutter, rugs, shelves, hanging herbs and dust motes in sunbeams, so insides feel lived in.

**When:** Every interior people can enter.

1. Dress each room with merged clutter props and a few motes in light shafts.

**Check:** preview every room.

**Cost:** Merged props; small.

**From:** Graphics ideas #15

### Market stall dressing  (`stall_dressing`, kit: manual)

Shelves, hanging goods, cloth bolts and piles on every market stall, so a stall reads as a shop and not a blank counter.

**When:** Every world with market stalls or shop counters the visitor can see.

1. Stock the back wall: two shelf rows with jars, folded cloth or bowls; never flat dark panels (they read as holes).
2. Lay the counter in three depths: low goods at the front edge, taller in the middle, tallest at the back.
3. Hang goods from the canopy edge or a side post: strings of pots or gourds, cloth strips, a lantern.
4. Pile and bolt the goods: spice mounds in shallow bowls, cloth bolts stacked 3-2-1 with one drape over the edge, brass in clusters of mixed heights.
5. At least 15 goods per stall (8+ on the counter, 4+ on shelves, 3+ hanging); count reused catalogue props at their real lod0 triangles (full recipe: kit/recipes/market/README.md).

**Defaults:** `triangles_per_stall` = 2600, `min_goods_per_stall` = 15

**Check:** stall shots at eye height show stocked shelves, a three-deep counter and hanging goods; the dressed models pass lint.

**Cost:** About 1,000-1,600 triangles of dressing per stall on top of the ~800-1,000-triangle shell.

**From:** desert blind-test review gap 2 (docs/reviews/2026-10-21-an agent-blindtest-desert-a2.md; rv_saffa_goods, rv_cloth_stall, rv_brass_stall; an internal task); full recipe and before/after example: kit/recipes/market/README.md

### Ambient creatures  (`ambient_creatures`, kit: planned)

Flocks of birds crossing the sky, crows on roofs, fish jumping, a few cats and dogs, laundry blowing in the wind.

**When:** Outdoor and town worlds.

1. Declare ambient life in scene.json (birds, fish, pets) with counts per area.

**Check:** preview over a minute.

**Cost:** A few cheap animated meshes.

**From:** Graphics ideas #16

### Sculpt a hero statue from an image  (`sculpt_from_image`, kit: manual)

A statue or hero prop is generated from a picture (image-to-3D), cut to a game budget and given the sculpt's detail as baked maps: it reads as carved stone at a fraction of the triangles.

**When:** Statues, figureheads, gate guardians: one-off showpieces seen up close.

1. Make an ORIGINAL concept (`iamar-models tools/mesh3d/refimg.py`, SDXL text-only, about 8-10 options; or the client's own AI-generated image). Never feed commercial art or someone else's sculpt.
2. Change one part without redrawing the figure: paint a mask (white = redraw, black = keep, feathered) and run `python kit/gpu/sculpt.py inpaint concept.png mask.png out/parts --prompt "the part, in the figure's material"` (SDXL inpainting, `kit/gpu/stages/inpaint_part.py`; the South Gate mage got a new staff this way).
3. Shape: `gen3d_v2.py img prefix 20000 0.0 shape` (Hunyuan3D-2, about 80k faces, ~2-3 min on an 11 GB GPU), then `... 8000 0.0 low` (decimate + xatlas UVs). 8k triangles is the sweet spot for a 3-4 m statue: 12k looks no better, 5k and below facet faces and cloaks.
4. A thin straight part the generator lost (a sword blade): `python kit/gpu/sculpt.py blade x_high.glb x_high_blade.glb --root=x,y,z --tip=x,y,z` (`kit/gpu/stages/add_blade.py`) on the high mesh, then redo the low mesh so the blade is in its UVs and the bake.
5. Bake: `blender -b --python <iamar-models>/tools/mesh3d/bake_stone.py -- hi.glb low.glb out.gltf 2048` (tangent normal map + sky occlusion times a pale stone colour, glTF separate).
6. Look from 4 sides (`kit/blender/look.py`), place it, and turn it so it faces the way the scene needs (find the front from a landmark of the pose: the drawn bow, not the elbow).
7. Shoot it in the world by day and night from both sides and commit the shots.

**Defaults:** `triangles` = 8000, `map_size` = 2048

**Check:** shots by day and night; LOD levels exist (8000/2000/1000/500).

**Cost:** Two 2048 maps per statue (~6-8 MB); GPU minutes per statue.

**From:** iamar gate statues 2026-10-13 (2d2f7ad9, af5a8efa, 40a3b0c1, ac36f688, 0e042740; docs/masterplan_audit/gate_statues/). Licence: Hunyuan3D-2 output may not be used in the EU, the UK or South Korea.

### Sculpt from several generated views  (`multiview_sculpt`, kit: manual)

One concept picture becomes a set of consistent views (front, sides, back) with a multi-view diffusion model, and the image-to-3D step builds the mesh from all of them: the far side is modelled and painted from its own view instead of guessed, so no mirror step and no blurred back.

**When:** Any sculpted part seen from all round (a creature head on a skeleton, a statue in a square); worth it when a single-view sculpt shows a soft or wrong back.

1. Crop the part from the concept and cut away what is not it (a polygon mask times background removal; `iamar-models tools/mesh3d/mv_views.py --mask`).
2. Views: `mv_views.py <img> <prefix> --mask poly.png --az 0 90 180 270 --text "..."` (MV-Adapter on SDXL, 768 px, ~90 s on an 11 GB GPU; four views fit, six do not). Make a contact sheet of the concept and the views and look at it: the back view is the weakest.
3. Shape: `head_mv.py <prefix> <out> 4000 0.0 shape` (Hunyuan3D-2mv from front/left/back/right, about 80k faces), then `... low` (cut, decimate keeping topology, large-chart UVs) and `... paint --paint 000,090,270` (Hunyuan3D-2 paint from several views onto the cage's own UVs).
4. Levels and bake: `blender -b --python <iamar-models>/tools/mesh3d/head_lods.py -- <out> <dir> <name> 2500,1500,700 --rot 0,0,180` (normal map from the high shape, coarser levels by collapse on the same UVs, glTF separate with one mesh per level), then `head_tex.py` (recolour the paint's grey fill, optional glow mask).
5. Test 1500 / 2500 / 4000 triangles at the distance it is seen and keep the lowest that holds the silhouette landmarks (horns, jaw, brow); pay for it by coarsening what the player sees less.

**Defaults:** `views` = 4, `view_size` = 768, `triangles` = 2500, `map_size` = 1024

**Check:** contact sheet of the views; triangles per level within the asset's old budget (dragon_lod_parts_test breeds); shots by day and night.

**Cost:** GPU minutes per part; two 1024 maps per part.

**From:** iamar stable dragon breeds 2026-10-14 (an internal task; docs/masterplan_audit/stable_dragons/). MV-Adapter (huanngzh, Apache-2.0); Hunyuan3D-2mv / -2 output may not be used in the EU, the UK or South Korea.

### Painted concept targets from fixed cameras  (`concept_targets`, kit: manual)

Before polishing a view, paint what it SHOULD look like from the same camera, so every later pass (textures, light, layout) is judged against a picture instead of a feeling.

**When:** Every world, before the art passes: 2-15 views a visitor really sees (arrival, main street, landmark, each quarter); after the greybox is approved.

1. Write a concept set (`kit/concept/README.md`): the size, one STYLE block from the world's style profile or style bible, and per camera eye, at and a SCENE text.
2. `python kit/concept/concept.py cams SET WORLD OUT --run` shoots each camera with `iamar-world preview` (OUT/<camera>_now.png).
3. `concept.py paint SET OUT` stretches each frame to the image API size, repaints it (SCENE + STYLE + LAYOUT + AVOID, the user's own key from the environment) and stretches it back so pixels line up; no key: `--provider manual` and `concept.py import`.
4. `concept.py compare SET OUT` writes now | target | blend | edges sheets; look at every one and reject paintings that moved the layout (no automatic score does this reliably).
5. Match the look with paint, light and texture; layout changes go through the plan, not the painting.

**Defaults:** `size` = [1536, 864], `api_size` = "1536x1024", `model` = "gpt-image-1.5", `quality` = "high", `input_fidelity` = "low"

**Check:** kit/tests/concept/concept_test.py (mocked image API); compare sheets reviewed by a different agent.

**Cost:** About 70-130 s and one paid image call per view; nothing at run time.

**Kit tool:** `kit/concept/concept.py`

**From:** the iamar browser source (not public) c2ec3b5e (P0 visual targets: docs/masterplan_targets cameras.json, prompts.json, tests/masterplan_city/concept_cam_shots.gd), docs/MASTERPLAN_ART_TECHNIQUES.md 'Painted concept targets' (10/10 kept first try); automatic layout score FAILED (kit/concept/README.md)

## Packaging

### Vertex colours in package worlds: which browser draws them, and in which colour space  (`gltf_texture_colours`, kit: manual)

glTF COLOR_0 multiplies the base colour, but Godot's runtime glTF import leaves vertex_color_use_as_albedo off. Browsers before the iamar browser source (not public) d7d034da (an internal task-10-20) therefore draw a model painted only with vertex colours white in a world package; from d7d034da on, WorldPackage turns the flag on for every surface with COLOR_0 and picks the colour space.

**When:** Every .glb a world package ships that carries COLOR_0 (status: FAILED on browsers before d7d034da, WORKS from d7d034da on; Godot 4.7.2).

1. Colour space: a .glb exported by Godot (asset.generator 'Godot Engine ...', as the catalogue's city exports are) is read as sRGB, because Godot writes its colours as they are; any other file is read as linear (the glTF spec: Blender writes linear). To say it outright, set asset.extras.iamar_vertex_colour to "srgb" or "linear".
2. For worlds that must also look right on older browsers, put the colours in a texture: a small palette image (one 8 px block per colour, so far mip levels keep them) with each face's UV on its block, or bake vertex colours to a texture in Blender; then leave COLOR_0 out or white, since it multiplies the texture.
3. Swayed trees (scene.json "sway": true) keep the colours and the colour space in the wind material (wind_plant use_vcol, vcol_srgb).
4. Look at the model through the browser's own path (a sample world, or WorldPackage._glb_decode) before shipping; the editor's import shows the colours whatever the runtime does.

**Defaults:** `palette_block_px` = 8, `vertex_colour_extras_key` = "iamar_vertex_colour"

**Check:** the iamar browser source (not public) tests/package_vertex_colour/vcol_test.gd (colours on, sRGB/linear choice, textured models untouched, swayed trees); kit/tests/catalog/city_assets_test.gd (every vertex-painted catalogue model draws its colours).

**Cost:** None with a browser from d7d034da; one small texture per model for older browsers.

**From:** the iamar browser source (not public) d7d034da scripts/worlds/world_package.gd _glb_decode (_glb_vertex_colours, _glb_vcol_srgb), shaders/wind_plant.gdshaderinc vcol_srgb; iamar-kit kit/catalog/assets/export_insects.gd (_pal_material, the texture route); before the fix the city's vertex-painted exports in kit/catalog/assets (C2a) loaded white

### Animation clips that survive the 30 fps import  (`gltf_clip_fps`, kit: manual)

Godot's glTF import resamples every clip at 30 frames a second, so a stroke faster than 15 Hz aliases away (a 15 Hz sine sampled at 30 fps is all zeros: a dragonfly's wings stood still).

**When:** Any looping clip in a .glb a world plays with scene.json objects "animation": wings, flags, wheels, flickers.

1. Keep motion at or under 15 Hz; for a buzz, flick between two poses on every 30 fps frame (cos at 15 Hz).
2. Make clip lengths whole 30 fps frames (0.4 s = 12 frames) so the loop has no seam.
3. Test the imported clip, not the one you wrote: advance the AnimationPlayer in small steps and measure the motion.

**Defaults:** `clip_fps` = 30, `max_stroke_hz` = 15

**Check:** kit/tests/catalog/city_assets_test.gd (insect wings swing > 0.3 rad over a clip).

**Cost:** None.

**From:** iamar-kit kit/catalog/assets/export_insects.gd (CLIP_FPS, BUZZ_HZ); the iamar browser source (not public) scripts/worlds/world_builder.gd _play loops the clip

### Bake a shader-painted look into a texture before exporting an object as glTF  (`painted_look_bake`, kit: manual)

A look a shader makes (the city's mp_painted: wood grain, stone courses, iron, trims, contact shade, glow, all from per-vertex look codes) cannot travel in a glTF; exported with only its vertex colour the object is one flat colour per face. Run the shader's colour logic into a per-object atlas instead and keep the mesh.

**When:** Every MeshKit object (props, furniture) a world package or the catalogue ships, and any object whose look comes from a custom shader (status: WORKS, an internal task: 45 props and 11 furniture pieces; a first bake from the raw vertex colours FAILED, see steps).

1. One chart per face (a MeshKit quad = two triangles sharing an edge and its UVs; other triangles alone) at 128 px/m with a 2 px gutter of the face's own edge colour, shelf-packed into the smallest power-of-two atlas; a bigger object is baked coarser to stay within 1024 px.
2. Per texel interpolate position, normal, face UV and contact shade and evaluate the shader's colour code (kit/catalog/assets/painted_baker.gd ports mp_painted.gdshaderinc 1:1, noise included).
3. Decode the vertex colour from sRGB first: Godot hands a spatial shader COLOR decoded, and raw values baked 1.4-4x too bright and washed out (measured against the live shader, unshaded).
4. Keep triangles and winding, replace TEXCOORD_0, drop COLOR_0 and UV2 (the file then looks the same in every viewer and browser); iron, strap trim and glass go to their own surface for roughness and metallic; glow becomes an emission texture at a fixed dusk level.
5. Leave out what needs the world (light bake and sky stains, street and ivy maps, rain): the world's own light and bake apply.
6. Catalogue props: import_city_models.py, bake_painted.gd, import_city_models.py --baked; furniture: export_city_pieces.gd bakes itself.

**Defaults:** `px_per_m` = 128, `max_atlas_px` = 1024, `gutter_px` = 2, `image` = "JPEG q0.85", `glow_night_level` = 0.35

**Check:** godot --headless --path <the iamar browser source (not public) checkout> -s kit/tests/catalog/painted_bake_test.gd (mesh kept, iron split, glow, grain varies, mean = the shader's colour, every shipped prop and furniture file textured); python3 kit/catalog/assets/import_city_models.py --check fails on a flat prop or furniture file.

**Cost:** A 256-1024 px JPEG per object (3.4 MB for the 45 catalogue props); 15-60 s of one CPU core per object.

**Kit tool:** `kit/catalog/assets/painted_baker.gd`

**From:** iamar-kit 1374cbc kit/catalog/assets/painted_baker.gd, bake_painted.gd, assets/README.md 'The painted look, baked', docs/evidence/job3129_city_vs_bake.jpg; the iamar browser source (not public) shaders/mp_painted.gdshaderinc
