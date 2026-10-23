# iamar recipes by layer and build tier

Generated from `techniques.json` (`layer`, `tier`). **Engineering** recipes apply to every world
whatever its look; **style** recipes depend on the art direction (see `kit/style`). Tier is the
lowest build tier that can apply the recipe (0 Blender and kit tools, 1 plus a generation
service, 2 plus a local GPU).

## Engineering (apply to every world)

| Recipe | Id | Area | Kit | Tier |
|---|---|---|---|---|
| Distance LOD chain | `lod_chain` | geometry | automatic | 0 |
| Impostor cards far away | `impostor` | geometry | manual | 0 |
| Merge static meshes per area | `merge_static` | geometry | automatic | 0 |
| Instance repeated props | `instancing` | geometry | automatic | 0 |
| Thin far foliage | `foliage_thinning` | geometry | automatic | 0 |
| Simple collision shapes | `collision_proxy` | geometry | manual | 0 |
| Weld identical vertices | `weld_vertices` | geometry | manual | 0 |
| Occluders on big walls and buildings | `occluders` | visibility | planned | 0 |
| No live shadows on tiny props | `tiny_no_shadow` | visibility | automatic | 0 |
| A pool of real lights | `light_pool` | visibility | automatic | 0 |
| Blender Cycles light bake (sky and sun) | `bake_sky_sun` | lighting | manual | 0 |
| Baked ambient occlusion in vertex colours (the time-independent bake) | `bake_ao_vertex` | lighting | manual | 0 |
| Painted maps + baked light (light in vertex colours) | `bake_vertex_light` | lighting | manual | 0 |
| Keep lightmaps lossless | `lightmaps_lossless` | lighting | planned | 0 |
| Live light only for what moves | `live_only_moving` | lighting | planned | 0 |
| One shared wind | `shared_wind` | materials | planned | 0 |
| VRAM texture compression and mipmaps | `texture_compression` | textures | planned | 0 |
| Right-sized textures and atlases | `texture_sizes` | textures | manual | 0 |
| Converted-model cache | `gltf_cache` | textures | automatic | 0 |
| Store every texture once | `textures_once` | textures | manual | 0 |
| Stream terrain in chunks | `streaming` | loading | planned | 0 |
| Build progressively, in time slices | `progressive_build` | loading | planned | 0 |
| Physics interpolation | `physics_interp` | loading | automatic | 0 |
| Quality presets and auto-tune | `quality_presets` | quality | manual | 0 |
| Native OpenGL on Windows | `native_gl_windows` | quality | manual | 0 |
| Responsive movement | `movement_feel` | feel | automatic | 0 |
| Lean networking | `network` | network | automatic | 0 |
| Build a page once, then patch it | `ui_pages` | interface | manual | 0 |
| Overlay, modal or surface | `ui_page_modes` | interface | manual | 0 |
| Long lists and pictures in pages | `ui_page_lists` | interface | manual | 0 |
| Pages every visitor sees the same | `ui_shared_pages` | interface | manual | 0 |
| Drop triangles nobody can see | `hidden_triangle_cull` | measurement | planned | 0 |
| Rank models by cost | `perf_rank` | measurement | planned | 0 |
| Find holes and open edges | `open_edge_check` | measurement | planned | 0 |
| Measure on the low-end machine | `measure` | measurement | manual | 0 |
| Check the display before blaming vsync | `display_refresh` | measurement | manual | 0 |
| Anisotropic filtering | `anisotropic` | art | automatic | 0 |
| Smooth LOD transitions | `lod_crossfade` | art | planned | 0 |
| Feet that follow the ground | `foot_ik` | art | automatic | 0 |
| Characters look at each other | `look_at` | art | automatic | 0 |
| Soft ground shadows at distance | `blob_shadows` | art | automatic | 0 |
| Painted concept targets from fixed cameras | `concept_targets` | art | manual | 1 |
| Vertex colours in package worlds: which browser draws them, and in which colour space | `gltf_texture_colours` | packaging | manual | 0 |
| Animation clips that survive the 30 fps import | `gltf_clip_fps` | packaging | manual | 0 |
| Bake a shader-painted look into a texture before exporting an object as glTF | `painted_look_bake` | packaging | manual | 0 |
| Bake the time of day the world is seen at | `bake_night` | lighting | manual | 0 |
| Sky ambient only with a still sun | `sky_ambient_still_sun` | lighting | manual | 0 |

## Style (depend on the art direction)

| Recipe | Id | Area | Kit | Tier |
|---|---|---|---|---|
| Bevel and normal maps from high-poly | `bevel_normals` | lighting | manual | 0 |
| Time-of-day palettes, haze and weather | `atmosphere` | materials | manual | 0 |
| Seamless hand-painted material textures | `painted_materials` | textures | manual | 0 |
| Texel density and texture budget | `texel_budget` | textures | manual | 0 |
| Cloud shadows | `cloud_shadows` | art | planned | 0 |
| Terrain texture blending by slope and height | `terrain_blend` | art | planned | 0 |
| Ground clutter | `ground_clutter` | art | planned | 0 |
| Worn paths | `path_wear` | art | planned | 0 |
| Per-instance colour variation | `instance_tint` | art | planned | 0 |
| Backlit leaves | `leaf_translucency` | art | planned | 0 |
| Grass that parts | `grass_interaction` | art | automatic | 0 |
| Lively faces | `faces` | art | manual | 0 |
| Lit windows at night | `lit_windows` | art | planned | 0 |
| Lived-in interiors | `interior_dressing` | art | manual | 0 |
| Market stall dressing | `stall_dressing` | art | manual | 0 |
| Ambient creatures | `ambient_creatures` | art | planned | 0 |
| Sculpt a hero statue from an image | `sculpt_from_image` | art | manual | 1 |
| Sculpt from several generated views | `multiview_sculpt` | art | manual | 2 |
| Masterplan houses, convex-wing roofs and door arches from a style profile | `masterplan_house` | geometry | automatic | 0 |
| Lanterns that read as lit at dusk and night | `lit_lantern` | lighting | manual | 0 |
