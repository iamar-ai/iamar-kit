# Anti-repetition: variety check, jitter and prop scatter (A9, an internal task)

Engineering practice for every world: copies placed near each other read as repeats.
`variety.py` (plain Python 3, no extra packages) works on a world's `scene.json`.

| Command | What it does |
|---|---|
| `python3 kit/style/variety/variety.py check <world> [--style P] [--json]` | Lint rule. Exit 1 and `VARIETY_FAIL n` on a repeat, `VARIETY_OK` otherwise |
| `python3 kit/style/variety/variety.py jitter <scene.json> --seed N --write` | Seeded per-object yaw, scale and `x-tint` shift (repeatable) |
| `python3 kit/style/variety/variety.py scatter A.glb B.glb --area X0 Z0 X1 Z1 --count N --min-dist 2.5 [--avoid x z r] --out scene.json` | Poisson-disc prop scatter; never the same asset twice in a row |

Rules (`check`): **neighbours** (same asset closer than `lint.neighbour_m` must differ by yaw >= 20 deg,
scale >= 5 % or `x-tint`), **sequence** (no 3 of one asset in a straight, evenly spaced ground row, each within 20 m
with nothing between; scene.json order does not matter, random scatters pass), **share** (one asset at most 40 % of 6+ placements),
**props** (same prop closer than 1 m). Override any threshold in a profile's optional `variety` block
(`min_yaw_deg`, `min_scale_delta`, `min_tint_delta`, `max_run`, `run_m`, `run_deg`, `run_even`, `max_share`, `share_min_objects`, `prop_min_dist`);
`neighbour_m` is read from the profile's `lint` block, like `iamar-world lint`.

Order: place, `jitter`, then `check`. Test: `python3 kit/tests/style/variety_test.py` (`VARIETY_TESTS_OK`).
The look rule itself (tint, storeys, timber, windows, roof) stays a style practice: `weathering.neighbour_rule`.
