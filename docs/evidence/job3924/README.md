# Job 3924: frame primitive, remaining patches

The mesh half is on the iamar browser source (not public) main (02e75029: `frame` in world_builder.gd,
tests/primitive_frame_test.gd). Two patches wait on files claimed by an internal task:

- `iamar-format-schema.patch` (the iamar browser source (not public): world_format.gd needs size for
  `frame`; scene.schema.json shape enum + `thickness` + `sill`).
  `git apply --3way` in an iamar checkout. With it, `tests/primitive_frame_test.gd`
  prints FRAME_DONE 0 (zoe, Godot 4.7.2 headless).
- `kit-world-format-docs.patch` (this repo: docs/WORLD_FORMAT.md 4.5 documents
  `wedge` and `frame`). Apply after the browser pin includes both.

After the schema change, re-pin kit/tier_preflight_manifest.json (scene.schema.json hash).
