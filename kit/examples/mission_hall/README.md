# Worked example: the Mission Hall (a fully baked interior world)

A round guild hall under a dome: eight mission-givers in booths, braziers, a shaft of light
through the oculus, a portal on the dais back to the city, 18 quests. In the iamar city it is
built in three steps, all in this folder: geometry and baked light in Blender, the scene,
the sounds.

| # | Step | Command | Writes |
|---|---|---|---|
| 1 | Geometry and baked light (Blender 4.2+, Tier 0) | `blender -b --python kit/examples/mission_hall/mission_hall.py -- worlds/mission_hall [samples] [--quick] [--preview] [--props DIR]` | `assets/hall.glb`, `hall_collision.glb`, `shaft.glb`, `veil.glb`, `flame.glb`; prints `HALL ... done`; scratch and previews in `worlds/build/mission_hall_work/` (outside the package) |
| 2 | Scene: NPCs, quests, lights, sounds, portal | `python3 kit/examples/mission_hall/hall_scene.py worlds/mission_hall --city iamar://local/oakhaven --id mission_hall --owner <you> --author "<name>"` | `manifest.json`, `scene.json`; prints `SCENE 8 npcs 18 quests 12 objects 10 lights` |
| 3 | Sounds, synthesised (no recordings) | `python3 kit/examples/mission_hall/hall_audio.py worlds/mission_hall` | `audio/hall_ambience.ogg` (22.5 s loop), `audio/brazier.ogg` (9.2 s loop); about 3 s on a laptop CPU |
| 4 | Validate and look | `iamar-world validate worlds/mission_hall`, `iamar-world preview ...` | no ERROR |

Needs: Python 3; step 1 Blender 4.2+ with Cycles (a GPU makes the full 384-sample bake
minutes instead of an hour; `--quick` bakes quarter-size maps with 48 samples or fewer in
under a minute on a GPU); step 3 numpy and ffmpeg with libvorbis. Test:
`python3 kit/tests/examples/mission_hall_test.py` (prints `MISSION_HALL_TEST_OK`; the audio
part prints SKIPPED without numpy or ffmpeg, the Blender part without Blender: set
`BLENDER=/path/to/blender`).

### Step 1 inputs

- **Surfaces**: `--textures DIR` (default `kit/style/materials/library`): the hall uses
  `ashlar` (walls), `plaster` (vaults, coffers, marble), `trim` (mouldings), `timber` (wood),
  `stone` (floors), each tinted in `mission_hall.py` (`mat_tex`). Any folder with maps of those
  names (`.jpg`, `.png` or `.webp`) restyles the hall.
- **Props**: `--props DIR`, a folder of glTF files named as `BOOTH_PROPS` lists them
  (`Table_Large.gltf`, `Chalice.gltf`, ...: the Quaternius Fantasy Props MegaKit, CC0,
  quaternius.com; `iamar-world assets search table` finds each with its sha256). Without it every
  prop is a box of its catalogue size (`kit/catalog/catalog.json`) in dark wood, so the booths
  keep their layout and the bake its shadows: a greybox you can bake, look at and replace.
  With the props the hall's props atlas grows from about 7k to 54k triangles.

## Techniques shown

- **Bake the light into unlit atlases.** Everything static is built per atlas (floor, walls,
  upper, columns, dome, props); Cycles bakes colour, light (direct + bounced, denoised),
  ambient occlusion and emission separately, and `mission_hall.py` combines them
  (colour x (light + a little occlusion fill) + emission, with a soft shoulder for the sunlit
  pool) into one texture per atlas on `KHR_materials_unlit` materials: one draw call per
  atlas, the light already in the texture.
- **Lightmap UVs checked, not trusted.** After unwrapping, the `unwrapped ... density` lines
  report texel density per atlas (p5/p95 near 1, `zero 0`): a face with no texels would bake
  black.
- **Positions from the geometry, not by hand.** Booths every 45 degrees at radius 34, braziers
  at radius 19 between them, gallery at y 8: `at(angle, radius, y)` places every NPC, light and
  sound, so moving the hall's radius in the Blender step moves everything with it.
- **Baked interior, live accents.** The hall is unlit baked atlases (`cast_shadow: false`, sun
  off); only the oculus spot, one warm point per booth and the portal glow are live lights (10,
  under the manifest's budget of 12).
- **Separate collision mesh.** `hall_collision` has `collision: mesh` and `visible_range: 0.01`
  so it collides but never draws; the visible hall has `collision: none`.
- **Loop-safe procedural audio.** `loop_fade` crossfades the end into the start, so the files
  loop without a click; a few short echoes stand in for a stone room's reverb.
- **Cross-world quests.** Some quests send the player into `--city` and back (`world`,
  `turn_in_world`). Their NPC names (Tomas Pell, Brother Aldous) are NPCs of the iamar city:
  with another `--city`, edit those quests to name NPCs that exist there.

## Parameters

`--city` is the world the portal and cross-world quests lead to (any address of
`docs/WORLD_FORMAT.md`, for example `iamar://local/oakhaven` or `iamar://alice/town`); the
city must also have a spawn point `from_mission_hall` and a portal back to this world's
`from_oakhaven` spawn. `--id`, `--owner` and `--author` fill the manifest.
