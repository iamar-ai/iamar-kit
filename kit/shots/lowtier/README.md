# iamar-world lowtier: does the lowest tier still look right?

`iamar-world lowtier <world> <out> [--cameras FILE] [--times day,night] [--tier low] [--no-high] [--impostor-slack F] [--npcs all|models|none] [--size WxH] [--json]`

Runs `iamar-world shots` at the low tier, then reads the raw pictures. Per camera and time it fails on:

| Check | Fails when |
|---|---|
| `blank` | the picture is one flat colour (nothing drew) |
| `magenta` | over 2% of pixels are missing-texture pink |
| `crushed` | 90% of pixels are black (not checked at night): shadows or ambient light broken |
| `blown` | 90% of pixels are white: exposure or sun broken |
| `triangles` | none drawn, or over the world's triangle budget |
| `impostors` | the low tier draws more triangles than the high tier for the same shot (far LODs and impostors not working), by more than 1%: script entities (birds, boats, walkers) stand elsewhere in the two runs, so equal tiers differ by a few hundred triangles (`--impostor-slack 0.0`..`1.0` changes the share; a world with big wandering creatures, such as ducks of 2000 triangles each, still fails falsely: run `--npcs none` so neither run draws them); skipped with `--no-high` |

Output: `<out>/low/` and `<out>/high/` (the two shots runs), `<out>/LOWTIER.md`, `<out>/lowtier.json`.
Exit 0 all good, 1 a check or render failed, 2 bad input. Pixel checks need Pillow.

Tests: `python3 kit/tests/shots/lowtier_test.py` (fake renderer; a real render needs a browser, as for `shots`).
Thresholds are the constants at the top of `lowtier.py`.
