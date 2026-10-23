# Worked example: a harbour quarter with a founder statue (iamar-family extension)

End to end, from the interview to the reviewed world. It reuses the composition example
(`kit/recipes/composition/examples/harbour_quarter.composition.json`: lighthouse 120 m ahead, fish hall
at 80 m, harbour gate at 100 m, crane and net shed as obstacles). Statue and prop rules:
`kit/examples/STATUE_PROP_PROTOCOL.md`. Numbers marked (city) were measured in the iamar city
build; (target) are the budgets this example must meet; nothing here claims a measured result for
the harbour world until a run records it in `pipeline.json`.

## Steps, commands, expected numbers

| # | Step | Command | Expected |
|---|---|---|---|
| 1 | Interview, track A (iamar-family), world type town/district; brief approved | `kit/interview/` (common.md, tracks) and its validator | brief with quarter name, reuse list, portal back to the city |
| 2 | Scaffold | `iamar-world new worlds/harbour --id harbour --title "Harbour Quarter" --author "<user>"` | folder with `manifest.json`, `scene.json`, `assets/`, `scripts/` |
| 3 | Greybox the layout and sightlines | edit `scene.json`; `check_composition.py composition.json` | COMPOSITION_OK (6 roofs spread above 0.6 m) |
| 4 | Reuse first: houses, lamps, bollards from the catalogue | `iamar-world assets search "harbour house"` | entries with triangles per LOD; no new mesh if one fits |
| 5 | Founder statue (concept to 8k model) | protocol steps 1-10 | 80k high-poly -> 8,000 tris; LODs 8000/2000/1000/500 (city); two 2048 maps about 6-8 MB (city); shape generation 2-3 min on an 11 GB GPU (city); bake minutes depend on hardware (CPU Cycles: minutes) |
| 6 | Statue check | `check_statue_spec.py founder_statue.spec.json` | STATUE_SPEC_OK |
| 7 | Props (bollards, crates, nets) | protocol prop steps; `asset_pipeline.py -- bollard.glb out --budget 150 --atlas --light unlit` | at most 600 each; `pipeline.json` lists triangles per LOD |
| 8 | Wire the world | merge `world_fragment.json` into `scene.json`: object, spawn point `from_old_town`, portal `to_old_town` -> `oakhaven#from_harbour`, NPC, quest | portal `to` names the spawn; the city side needs the reverse portal and spawn id `from_harbour` (a separate step in the city repo, not part of this swarm) |
| 9 | Validate | `iamar-world validate worlds/harbour` | no ERROR; read every WARN |
| 10 | Look | `iamar-world preview worlds/harbour /tmp/harbour` and `iamar-world shots` (day, dusk, night) | eye height 1.7 m shots with triangle counts |
| 11 | Style lint and shot comparison | `kit/lint/style_lint.py` with the iamar profile | passes |
| 12 | Review gate | reviewer who is not the author uses `kit/review/REVIEWER.md` | score 0.6 x Beauty + 0.4 x Efficiency at least 70 |

## Review checklist

- Statue: face reads as a face from 4 m at eye height; neck present; no ground slab; shots day and night from both sides.
- Triangles: statue at most 8,000, each prop at most 600, quarter visible under 1M; Efficiency 100 only when all are within budget.
- Composition: from the arrival point the lighthouse, fish hall and gate are visible; no footprint blocks them.
- Portal: ring or arch faces the approach; `to` resolves; spawn point exists in the target.
- NPC and quest: the NPC has a greeting; quest step coordinates are on walkable ground near the statue.
- Licences: every generator and downloaded asset recorded in the statue spec and the world's credits.

## Limits of this example

The commands in steps 9-12 need the iamar browser (`iamar-world` fetches it with the user's
invitation code); steps 5-7 need Blender (Tier 0) and for the sculpt a Tier 1 or Tier 2 generator.
`world_fragment.json` follows `docs/WORLD_FORMAT.md` sections 4.4, 4.7, 4.9, 4.13 and 4.14 but was
not run through `iamar-world validate` on this host (no browser here); the first worker with a
browser must run step 9 and record the result.
