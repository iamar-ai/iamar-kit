# Gallery: good and bad examples from the iamar build

Generated from gallery.json by gallery.py build. Do not edit by hand.
Each entry is a real outcome recorded in its source. WORKS, PARTIAL or FAILED.
Pictures stay in the source repository (the iamar browser source (not public)); the source column says where.

## Houses (6)

### G01 Every landmark cut its door at the house height - FAILED
- Seen: Landmarks shared the house door height, so the big buildings lost their grandeur.
- Lesson: Give each landmark its own entrance height in its spec; carry the scale with the arch ring and painted carving, not extra polygons.
- Recipe: `traps` (engineering layer)
- Source: `docs/MASTERPLAN_JOBS.md:78`

### G02 Monumental gate and bridges: grandeur from width and rhythm - PARTIAL
- Seen: A 6.1 m bridge against a 14 m street narrowed the grandest moment of the route.
- Lesson: Set gate and bridge widths from the approach, not from the minimum road. The South target of 18-20 m stayed open at the time of writing.
- Recipe: `style_iamar_proportions` (style layer)
- Source: `docs/MASTERPLAN_ART_TECHNIQUES.md:158`

### G03 Street lamps placed inside the carriageway - FAILED
- Seen: On a 3 m castle road the lamps sat 0.35 m inside the paved edge.
- Lesson: Offset lamps outside the road half-width plus a margin (w * 0.5 + 0.6 m) and test them against the road ribbon.
- Recipe: `traps` (engineering layer)
- Source: `docs/MASTERPLAN_JOBS.md:121`

### G05 Extra LOD levels on baked building shells - FAILED
- Seen: Levels past the 1 m error cap lost windows, trims and lit windows at 50-110 m. Three audit rounds over 76 views gained 0.86% of primitives.
- Lesson: Do not add simplifier levels to baked shells for a small gain. Lossless savings need per-building impostors or a far-LOD set.
- Recipe: `lod_chain_baked_facades` (engineering layer)
- Source: `docs/perf/fps_f12_lod_chains.md:1`

### G06 Coarsest baked LOD cut on 148 of 197 meshes - FAILED
- Seen: The round cut 37.1% of triangles at the coarsest level (361,706 to 227,541). Windows and lit windows failed at 50-110 m and nothing was published.
- Lesson: Judge a LOD round by what is visible at its switch distance, in a rendered view, before counting triangles.
- Recipe: `baked_lod_chains` (engineering layer)
- Source: `docs/perf/fps_f12_lod_chains_table.md:3`

### G07 Hidden-face culling on buildings - PARTIAL
- Seen: Removing the hidden faces of buildings saved 0.8% of LOD0 triangles, because the generator already culled them. A dressing split netted -0.8% to +0.2% with 11 more draw calls.
- Lesson: Measure a culling pass on the real building set before adding it. Long dressing pieces must stay readable at range.
- Recipe: `never_seen_face_culling` (engineering layer)
- Source: `docs/masterplan_audit/a34_baseline.md:164`

## Props (6)

### G08 Instance uniforms for per-house looks - FAILED
- Seen: A shared instance-uniform buffer overflowed at 4,096 items.
- Lesson: Use material variants for per-house looks; do not rely on instance uniform buffers for large sets.
- Recipe: `traps` (engineering layer)
- Source: `docs/MASTERPLAN_ART_TECHNIQUES.md:231`

### G09 Night far trees glow white - FAILED
- Seen: Impostor billboards at night were not lit like real trees and glowed white.
- Lesson: Fixed on 2026-10-09; the root cause was the same as the normal-atlas encoding trap. Check far impostors in night light.
- Recipe: `traps` (engineering layer)
- Source: `docs/MASTERPLAN_JOBS.md:740`

### G10 Far-only tree impostor cards - FAILED
- Seen: On the Balanced preset, far-only tree cards dropped the frame rate from 42 to 24 fps.
- Lesson: Measure impostor cards on the target preset. Cutting at 50-60 m with better blended cards is the open proposal.
- Recipe: `forest_far_cards` (style layer)
- Source: `docs/JANE_PARALLEL_WORK.md:19`

### G11 Forest LOD: blocky canopy and snapping impostors - FAILED
- Seen: Blocky crowns and 22.5-degree view snapping made trees look as if they changed shape.
- Lesson: Keep the crown silhouette across LODs and avoid snapping impostor views on a coarse angle grid.
- Recipe: `traps` (style layer)
- Source: `docs/MASTERPLAN_ART_TECHNIQUES.md:471`

### G12 Raising the mesh LOD threshold under load - FAILED
- Seen: Raising the threshold above 4 px visibly broke a fountain about 15 m away and simplified stalls at x8.
- Lesson: Under load, reduce render scale first; use mesh LOD only at the floor.
- Recipe: `dynamic_mesh_lod_lever` (engineering layer)
- Source: `docs/DYNAMIC_RESOLUTION.md:73`

### G39 Imported split normals stopped Godot making LODs - FAILED
- Seen: The first bake exported 23,970 split vertices. Godot generated no LODs for the custom split normals.
- Lesson: Clear custom split normals before export, or Godot silently makes no LODs.
- Recipe: `mesh_import_split_normals_lods` (engineering layer)
- Source: `docs/masterplan_shots/f4_135_face/README.md:27`

## Creatures (7)

### G14 Derivative bump on small creatures - FAILED
- Seen: bump * texture scale made a crosshatch on small creatures. Bump at 0 read as smooth feathers.
- Lesson: Keep bump low on small creatures; test it at the viewing distance.
- Recipe: `traps` (style layer)
- Source: `docs/MASTERPLAN_ART_TECHNIQUES.md:541`

### G15 Griffin beak covered the face like a mask - FAILED
- Seen: The beak grew from the skull end ring and read as a big yellow toucan beak.
- Lesson: Grow the beak from the feathered face, compressed to about 0.74x with a dark tip.
- Recipe: `traps` (style layer)
- Source: `docs/masterplan_griffin/README.md:39`

### G16 Lowering horse detail to the budget - PARTIAL
- Seen: LOD0 went from 9,780 to 8,284 triangles against a 6k budget. Lower detail lost the hooves and the loft profile between stations.
- Lesson: Keep hooves and the loft profile when cutting; meet the budget with texture and bake instead of cutting silhouette.
- Recipe: `creature_triangle_budget` (style layer)
- Source: `docs/perf/horse_f10/README.md:43`

### G17 Rebuilt MultiMesh lost the instance colour - FAILED
- Seen: A creature script rebuilt the body MultiMesh and read the coat tint back too early. The body drew black while head and legs kept colour.
- Lesson: Each instance restores its coat on its first pose. Verify instance colours in the game, not in a headless run.
- Recipe: `multimesh_custom_data_colour` (engineering layer)
- Source: `docs/MASTERPLAN_TODO.md:124`

### G18 Procedural legs float on uneven ground - PARTIAL
- Seen: Separate lower-leg parts with knee and hock flex are not IK. Blender inspection caught floating wolf paws.
- Lesson: Overlap the pastern and paw so no gap shows, and inspect feet in Blender at the walking pose.
- Recipe: `creature_leg_flex_limits` (style layer)
- Source: `docs/wildlife_detail_upgrade.md:12`

### G19 Beard stretched over the collar by the hair fit - FAILED
- Seen: A posed fit loop over every hair mesh, beards included, pushed the beard tip out over a chain collar. The run failed at score 87.4 from 90.4.
- Lesson: Skip beards in the posed fit; they follow the build through body weights.
- Recipe: `character_hair_fit_exclude_beard` (style layer)
- Source: `docs/masterplan_shots/rv2/r65/VERDICT.md:1`

### G20 Herd close and far mesh switch - PARTIAL
- Seen: A cow went from 7,604 close triangles to 21,924 with the close mesh; the far mesh is 2,418.
- Lesson: Switch at 22 m and back within 18 m using the closest member. The swap is discrete with no crossfade, and close detail multiplies the cost, so set a budget first.
- Recipe: `herd_multimesh_lod` (engineering layer)
- Source: `docs/animal_detail_upgrade.md:12`

## Terrain (4)

### G13 LOD flag on painted ground - PARTIAL
- Seen: generate_lods on ground with class colours and UV seams cut the slice by 1.8%. Position-only far siblings halved the paved meshes but the net gain was about 1% of a view.
- Lesson: Do not expect the LOD flag to help painted ground. Build a far re-gridded tile.
- Recipe: `far_ground_lod` (engineering layer)
- Source: `docs/masterplan_audit/a34_baseline.md:141`

### G22 Paving disc 3 cm under the lowest ground point - FAILED
- Seen: The paving disc z-fought with the ground wherever the ground dipped below it.
- Lesson: Cut the footprint out of the ground and lay paving 2-5 cm above it with a kerb ring. Check fountains, wells, statues and stalls.
- Recipe: `traps` (engineering layer)
- Source: `docs/MASTERPLAN_JOBS.md:109`

### G23 Far ground groups show coarse flat ground through fine paving - PARTIAL
- Seen: Far ground groups were measured from the group centre, so coarse ground showed through fine paving near the player.
- Lesson: Measure far-LOD visibility range from the player, not from the group centre.
- Recipe: `far_ground_lod_visibility_range` (engineering layer)
- Source: `docs/masterplan_audit/r11_gaps.md:63`

### G24 Footing faces below ground bake black - PARTIAL
- Seen: Footing tops at street level baked black and showed as strips where the ground dipped. Rebaking did not help until the geometry was culled or sunk.
- Lesson: Cull or sink hidden footing faces before baking; a rebake alone will not fix them.
- Recipe: `bake_dark_texel_audit` (engineering layer)
- Source: `docs/masterplan_audit/dark_bakes_player.md:61`

## Water (3)

### G26 Pond water floating above the terrain - PARTIAL
- Seen: Water was raised 0.25 m over a 1.42x shoreline, and the height shelf ran after the terrain hook.
- Lesson: Dip the basin below ground and slope the banks. Apply the height shelf before the terrain hook.
- Recipe: `water_effects` (engineering layer)
- Source: `docs/MASTERPLAN_JOBS.md:760`

### G27 Dry pale apron round a pond reads as a sand smear - FAILED
- Seen: The carve flattened an apron 0.2 m above the water. It read as a dry sand smear.
- Lesson: Raise the water over the apron or dip the bowl; keep shafts and haze 8 m off the water.
- Recipe: `traps` (style layer)
- Source: `docs/masterplan_stream/README.md:30`

### G28 Road ribbon built before the pond was carved - FAILED
- Seen: The road ribbon lay across the water and the bridge deck.
- Lesson: Defer the road build until the ground is carved, skip rows over the pond and the bridge decks, and keep waymarkers off the bridge.
- Recipe: `traps` (engineering layer)
- Source: `docs/masterplan_forest/README.md:155`

## Lighting (6)

### G29 Warm peach fog tinted the valley yellow - FAILED
- Seen: Warm fog tinted the whole valley yellow when seen from the air.
- Lesson: Keep the warmth in the sun and the surfaces; keep the fog cool and light.
- Recipe: `traps` (style layer)
- Source: `docs/WORLD_ART_GUIDE.md:192`

### G30 Lighting a focal statue - PARTIAL
- Seen: Warm key from braziers, a cool rim, shafts and animated flame cards read well. A flickering light moved the shadows.
- Lesson: Use real animated flames with embers so the light and the shadows move together.
- Recipe: `lighting_presets` (style layer)
- Source: `docs/MASTERPLAN_JOBS.md:607`

### G31 Reduced lightmap decoded to the wrong format - FAILED
- Seen: An LA8 lightmap decoded as RGBA8 lost the sun shadows and washed out the walls.
- Lesson: Convert decoded images back to the stored format, and test that the sun is read from alpha.
- Recipe: `lightmap_format_conversion` (engineering layer)
- Source: `docs/LOWEND_HALF_LIGHTMAPS.md:39`

### G32 Shadow cost measured with the wrong sun - FAILED
- Seen: The budget tool used 4 splits over 60 m, so a 25k-triangle landmark drew as 101k shadow triangles. The shipped game uses 1 split over 45 m; the true share was 16-24% of the frame, not 41-49%.
- Lesson: Measure with the shipped lighting, not a tool default.
- Recipe: `shadow_pass_measurement` (engineering layer)
- Source: `docs/MASTERPLAN_TODO.md:183`

### G33 Blob shadow reads as a black hole - PARTIAL
- Seen: On the Fast preset the sun shadows were off, and an unshaded near-black disc drew under characters. Five players reported it as a black spot.
- Lesson: Use alpha around 0.25, tint it to the ground, multiply-blend it and fade it at night and in rain.
- Recipe: `blob_shadow_ground_patch` (engineering layer)
- Source: `docs/masterplan_audit/f4_triage.md:144`

### G34 Covered passages bake near-black - PARTIAL
- Seen: Road decks inside gate passages baked at sky 0.08 with no sun and read 10-12% of open-road brightness.
- Lesson: Hold sky light at 0.6 on up-facing texels of named fortification meshes, or add lamps.
- Recipe: `bake_covered_floor_lift` (engineering layer)
- Source: `docs/masterplan_audit/dark_bakes.md:128`

## Statues (4)

### G21 Multi-view generation traps on a winged creature - PARTIAL
- Seen: Front-only views gave blob backs. Side views folded the wings into the cloak. A thin sword vanished. Flat grey patches became planks.
- Lesson: Name the wings in the prompt with a negative prompt, pick from several seeds, and drop flat untextured patches before modelling.
- Recipe: `statue_from_concept` (style layer)
- Source: `docs/masterplan_audit/south_gate_heroes/README.md:56`

### G36 Hero face pasted onto image-to-3D statues - FAILED
- Seen: Sculpts decimated to 3,500-8,000 triangles gave soft blob faces. A pasted hero face (about 10,032 triangles in total) was called horrible and removed in an internal task.
- Lesson: Do not paste a hero face mesh onto a generated statue. Fix the sculpt at its source.
- Recipe: `statue_pasted_hero_face` (style layer)
- Source: `docs/masterplan_shots/job1627_statue_faces/README.md:11`

### G37 Statues from posed character models - PARTIAL
- Seen: A CPU-skinned posed mesh of about 2k triangles with AO in vertex colour worked. The moat-bridge statue drew black and stays open.
- Lesson: Check the bake and the UV2 and material of every statue after a worker-thread load.
- Recipe: `statue_protocol` (style layer)
- Source: `docs/MASTERPLAN_ART_TECHNIQUES.md:165`

### G38 Stale bake signature draws a statue unbaked - PARTIAL
- Seen: A reverted mesh no longer matched its bake, so the game drew it with live light and no baked AO.
- Lesson: Compare before and after shots only after the bake signature matches the built mesh.
- Recipe: `bake_signature_mismatch` (engineering layer)
- Source: `docs/masterplan_shots/f4/f4_156_south_mage_gamelight.md:28`

## Process (4)

### G35 LOD swaps judged on stills - PARTIAL
- Seen: Far-level switches and hand-overs show as horizon rings and pops that stills do not reveal.
- Lesson: Judge LOD swaps on 30 fps frame sequences. A hard switch may need a 1-2 m hysteresis band.
- Recipe: `lod_popping_check` (engineering layer)
- Source: `docs/masterplan_audit/r11_plan.md:72`

### G40 Harness reported PASS despite script errors - FAILED
- Seen: A pond fixture reported PASS while its dependencies logged SCRIPT ERRORs.
- Lesson: A green run is not proof. Fail the run on any script error in the log, and check the log, not only the exit code.
- Recipe: `stale_class_cache_false_pass` (engineering layer)
- Source: `docs/testing/pond_detail_fixture.md:20`

### G41 Stale class cache gave RESULT ok with parse errors - FAILED
- Seen: A stale global script class cache printed RESULT ok while the scripts had parse errors.
- Lesson: Clear the class cache before a gate run; treat parse errors as a failure.
- Recipe: `stale_class_cache_false_pass` (engineering layer)
- Source: `docs/testing/gate_statues_generator_1339.md:61`

### G42 Probe exited 0 while a check had failed - FAILED
- Seen: The probe printed exit 0 while script errors hid a failed check.
- Lesson: Make the probe count errors and exit non-zero on any failed check.
- Recipe: `headless_false_pass` (engineering layer)
- Source: `docs/masterplan_audit/citygrow_correspondence_holds.md:34`
