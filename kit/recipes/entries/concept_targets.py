"""Recipe concept_targets (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 600
TIER = 1
r("concept_targets", "Painted concept targets from fixed cameras", "art",
  "Before polishing a view, paint what it SHOULD look like from the same camera, so every later pass (textures, light, layout) is judged against a picture instead of a feeling.",
  "Every world, before the art passes: 2-15 views a visitor really sees (arrival, main street, landmark, each quarter); after the greybox is approved.",
  ["Write a concept set (`kit/concept/README.md`): the size, one STYLE block from the world's style profile or style bible, and per camera eye, at and a SCENE text.",
   "`python kit/concept/concept.py cams SET WORLD OUT --run` shoots each camera with `iamar-world preview` (OUT/<camera>_now.png).",
   "`concept.py paint SET OUT` stretches each frame to the image API size, repaints it (SCENE + STYLE + LAYOUT + AVOID, the user's own key from the environment) and stretches it back so pixels line up; no key: `--provider manual` and `concept.py import`.",
   "`concept.py compare SET OUT` writes now | target | blend | edges sheets; look at every one and reject paintings that moved the layout (no automatic score does this reliably).",
   "Match the look with paint, light and texture; layout changes go through the plan, not the painting."],
  {"size": [1536, 864], "api_size": "1536x1024", "model": "gpt-image-1.5", "quality": "high", "input_fidelity": "low"},
  "kit/tests/concept/concept_test.py (mocked image API); compare sheets reviewed by a different agent.",
  "About 70-130 s and one paid image call per view; nothing at run time.",
  "the iamar browser source (not public) c2ec3b5e (P0 visual targets: docs/masterplan_targets cameras.json, prompts.json, tests/masterplan_city/concept_cam_shots.gd), docs/MASTERPLAN_ART_TECHNIQUES.md 'Painted concept targets' (10/10 kept first try); automatic layout score FAILED (kit/concept/README.md)", "manual", "kit/concept/concept.py")
