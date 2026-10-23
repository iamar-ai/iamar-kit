"""Recipe lit_lantern (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 650
LAYER = "style"
r("lit_lantern", "Lanterns that read as lit at dusk and night", "lighting",
  "Street and wall lanterns whose glass glows warm from every side, paired with a point light that lights the street around them.",
  "Every lamp a brief promises at dusk or night (quays, doors, lanes, bridge ends).",
  ["`iamar-world style-gen lantern assets/lantern.glb [--mount post|wall] [--height 2.6] [--glow 1.3] --json`: an open iron frame (base plate, four corner bars, pyramid cap) around emissive glass in the profile's `lamp_glow`, LOD0-2 within the prop budget; `--world preview --check` shows it at night with its light.",
   "Copy the report's `light` into scene.json `lights` once per lantern, adding the object's position (rotated by its yaw): a point light at the glass centre, energy 1.4, range 9, no shadows. Keep to the manifest's `lights` budget (under 8 in a small world; the browser gives the nearest few a real light, light_pool).",
   "Never put the glass inside a closed shell: the harbour blind test hid emissive glass inside a solid iron lathe and its lanterns read as dark grey boxes at night.",
   "Keep `--glow` at 1-2: higher clips the glass to white in the browser's linear tonemap and loses the warm colour.",
   "Lanterns are props: keep them live-lit (pipeline --light ao, not a light bake), and bake their light into the walls with bake_night when the world is seen at night."],
  {"glow": 1.3, "light_energy": 1.4, "light_range_m": 9, "post_height_m": 2.6, "budget_lod0": 300},
  "kit/tests/style/gen/style_gen_test.py (glass visible: no iron face in front of it, emissive strength set, audits on every LOD, light at the glass centre); night shots: the glass is warm, not white, and a pool of light lies on the ground; kit/style/lighting/gallery/night_bake.",
  "~100 triangles per lantern; one real light each (the nearest few are live).",
  "harbour blind-test review (docs/reviews/2026-10-20-an agent-blindtest-harbour.md gap 3, sheet_n); iamar-kit kit/style/gen/lantern.py (an internal task)", "manual", "kit/style/gen/gen.py")
