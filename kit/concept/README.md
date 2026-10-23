# Concept targets: paint the view before you polish it

Recipe `concept_targets` (tier 1, engineering layer: the workflow is the same for every style; the
STYLE block is what changes). Tool: `kit/concept/concept.py`. Test: `python kit/tests/concept/concept_test.py`.

The iamar city's look was set this way (the iamar browser source (not public) `docs/masterplan_targets`, commit c2ec3b5e,
technique TD012): 14 fixed cameras, each screenshot repainted by an image model into what the view
should become, and every later pass (textures, trim sheets, light, layout) judged against the
painting **from the same camera**. Without a target, "make it look better" has no end; with one, a
reviewer can put the shot and the painting side by side and say what is missing.

## When

After the greybox is approved (`kit/recipes/greybox`), before the art passes. Pick 2-15 views a
visitor really sees: the arrival, the main street, each landmark, one per quarter or zone. Fewer,
well-chosen views beat many.

## The concept set

One JSON file drives every step. Examples: `examples/iamar_city_sample.concept.json` (iamar
family, Track A: the city's own STYLE, LAYOUT and AVOID blocks, verbatim) and
`examples/desert_post.concept.json` (brand-new world, Track B: STYLE written from that world's
style bible, kit default LAYOUT and AVOID).

```json
{
 "schema": "iamar-concept/1",
 "world": "worlds/my_world",
 "size": [1536, 864],
 "blocks": {"STYLE": "...the look of THIS world...", "LAYOUT": "(optional)", "AVOID": "(optional)"},
 "image_model": {"provider": "openai", "model": "gpt-image-1.5", "quality": "high",
                 "input_fidelity": "low", "key_env": "OPENAI_API_KEY"},
 "cameras": [
  {"name": "arrival", "eye": [0, 1.7, 14], "at": [0, 2.5, 0],
   "scene": "What this view should show: the objects, materials, life and mood, in plain words."}
 ]
}
```

- `eye`, `at`: world metres (x, y up, z). Eye height 1.7 m for a standing visitor.
- `blocks.STYLE` (required): write it from the world's style profile (`style.json`) or style bible:
  palette, materials, proportions, light, finish. For an iamar-family world copy the iamar block.
- `LAYOUT` and `AVOID` default to the kit's style-independent text (keep the camera and layout;
  original design only, no lettering, no watermark or UI). Override only to add, never to drop
  "keep the camera".
- `scene` per camera: what that view should show (40+ characters; be concrete).
- `python kit/concept/concept.py check SET` validates the set (also: no key in the file).

## Steps

```bash
S=worlds/my_world/concept.json; OUT=concept_out
python kit/concept/concept.py check  $S
python kit/concept/concept.py cams   $S worlds/my_world $OUT --run   # OUT/<camera>_now.png
python kit/concept/concept.py prompt $S arrival                      # read the prompt first
python kit/concept/concept.py paint  $S $OUT                         # OUT/<camera>_target.png + .json
python kit/concept/concept.py compare $S $OUT                        # OUT/<camera>_compare.png
```

1. **cams** runs `iamar-world preview <world> OUT/raw/now --size WxH --view eye>at ...` (one
   `--view` per camera, in order) and renames the frames to `<camera>_now.png`. Without `--run`
   it prints the command; run it yourself (any launcher: `kit/iamar-world`, `iamar-world.cmd`,
   the browser) and then `cams SET WORLD OUT --collect` renames the frames. On Windows `--run`
   uses `kit/iamar-world.cmd` and quotes every argument (the `>` in `--view` is a cmd redirect
   otherwise). Preview renders at a 65 degree vertical fov; frames from another renderer (A1
   `iamar-world shots`, a city harness) work too: name them `<camera>_now.png`.
   `paint` refuses a now frame that is not at the set's size.
   **From `iamar-world shots`** (`kit/shots`, same eye-height cameras at day, dusk and night):
   give the concept cameras the shots.json camera names, render with
   `iamar-world shots <world> <shots_out> --size 1536x864`, then
   `cams SET WORLD OUT --from-shots <shots_out> [--time dusk]`. A dusk or night target is
   painted from that time's frame.
2. **paint** stretches each now frame to the API size of the nearest aspect (1536x864 ->
   1536x1024), sends it with the prompt `SCENE: ... STYLE: ... LAYOUT: ... AVOID: ...` to the
   image edit endpoint, and stretches the answer back to the camera size. `<camera>_target.json`
   records model, settings, prompt and the SHA-256 of the now frame and the target (never the key).
   `--only a,b` repaints some views; `--dry-run` prepares without calling the API.
3. **compare** writes one sheet per camera: now | target | 50 % blend | the now frame's edges in
   red over the target. **Look at every sheet.** It fails only on mechanical faults: a missing
   frame, a target not at the camera's size (not aligned), or a blank target.
4. Hand the sheets to the reviewer (`kit/review/REVIEWER.md`) as the bar for that view; keep the
   sets and targets in the world's repository (`docs/targets/` or similar), not the package.

## The API key (the user's own)

- The kit never ships or stores a key. `paint` reads it only from the environment variable named
  by `key_env` (default `OPENAI_API_KEY`): `export OPENAI_API_KEY=...` (PowerShell:
  `$env:OPENAI_API_KEY = "..."`) in the shell that runs it. Not from a file, not from the command
  line (shell history), never written to a record or a log; API error text is shown with the key
  replaced by `<key>`.
- The set check fails when a set contains `api_key`, `key` or `token`.
- `IAMAR_CONCEPT_API_BASE` points the client at another OpenAI-compatible endpoint (the test
  uses it for a local mock server).
- Cost: one paid image call per view per try (high quality, 1536x1024); about 70-130 s each.
- Region: only where OpenAI's service is offered (`kit/tools/TOOL.md`).

**No key, or no API in your region:** `paint --provider manual` writes
`OUT/paint/<camera>_input_1536x1024.png` and `<camera>_prompt.txt`. Paint over the input by hand,
or with any image tool the user may use, at that size (or at the camera's size), then
`concept.py import SET OUT <camera> painting.png` stretches it back and records it. It warns when a
painting is at neither aspect (it would not overlay the frame).

## What works and what does not (with evidence)

| Technique | Status | Evidence |
|---|---|---|
| Same-camera repaint: stretch to 1536x1024, gpt-image-1.5 edit, `input_fidelity` low, `quality` high, prompt SCENE + STYLE + LAYOUT + AVOID, stretch back | WORKS | city P0 targets, the iamar browser source (not public) c2ec3b5e, `docs/MASTERPLAN_ART_TECHNIQUES.md` "Painted concept targets": 10/10 kept first try, ~70-130 s each |
| Stretch, never crop or pad, between camera and API size | WORKS | the city's 14 targets overlay their now frames pixel for pixel (`docs/masterplan_targets/now/` vs the targets) |
| Paint in what the renderer cannot show yet (creatures the playerless harness does not spawn) | PARTIAL | city frames 07-10: creatures were painted in because MpWalk has no creatures; the target then shows things no screenshot can match until they exist (README "Reproduce the 'now' frame") |
| Change the layout through the painting | FAILED (by rule) | "Match the look; layout changes go through tools/city_map (P4), not the painting" (MASTERPLAN_ART_TECHNIQUES.md): a painting that moves a street sends builders after a picture no plan matches |
| Automatic "layout kept" score (edge or luminance correlation between now and target) | FAILED | measured 2026-10-20 on the city's 14 now/target pairs (an agent, an internal task): gradient correlation at 320/64/32 px, luminance at 32/16 px and rank correlation; a painting's own now frame was its best match for only 4-6 of 14 views, and mismatched pairs scored up to 0.40-0.60, above most true pairs (true-pair minimum -0.38 to 0.02). `compare` therefore reports `edge_corr` as information and fails only mechanical faults; `--min-edge-corr` exists for a user who calibrates it on their own world |
| Windowed `iamar-world preview --size WxH` before iamar-kit fix (an internal task) | FAILED (fixed) | on zoe (Windows, Godot 4.7.2) every frame came out 1280x720 (the project window size): `root.size` set in `_init` did not stick in a windowed run; the city's shot tool passed `--resolution` as well. `scripts/kit/world_view.gd` now sizes the window when the preview starts: 1536x864, 1280x720 and 864x1536 verified. A browser older than the fix still ignores `--size`; `paint` and `compare` catch it |
| Recompress targets to 256-colour PNG for the repository | WORKS | the iamar browser source (not public) 9b1722c3: all frames ~0.8 MB each |

## Checks

- `python kit/tests/concept/concept_test.py`: set check and seeded faults, prompt order, API size
  choice, preview command and frame renaming, paint against a local mock image API (auth header,
  multipart fields, stretched 1536x1024 input, aligned output, provenance record, key never
  written to any file, key redacted from an API error), the manual fallback and import, and
  compare (sheets, blank and misaligned targets fail).
- `python kit/concept/concept.py check examples/*.concept.json` prints `CONCEPT_SET_OK`.

Verified on real renders (zoe, Windows, Godot 4.7.2, Arc GPU, 2026-10-20, an internal task): both example
sets on their sample worlds (`kit/lint/samples/desert_post`, `kit/lint/samples/iamar_city`)
through `iamar-world preview` at 1536x864, and desert_post through `iamar-world shots` at dusk
(`--from-shots`), then `paint` against the test's mock image API and `compare`: `COMPARE_OK`
on every view. In a source checkout on Windows `iamar-world.cmd` cannot run preview (it calls
`res://scripts/kit/*.gd` directly and the kit tools live in the pack); use a downloaded browser
(IAMAR_BROWSER), or the bash launcher from Git Bash (`shots.py --runner '["bash", "kit/iamar-world"]'`).
