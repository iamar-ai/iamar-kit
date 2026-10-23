# `new` CLI argument preflight

Run the inert source/model suite with Python only:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_new_argv/test_inert.py
```

This suite never starts Godot, creates a draft, opens a world, or calls a
compiler. It translates only the exact pure `_argv_error` helper into a limited
Python branch/string model. An AST/call allowlist rejects unexpected behavior.
It is a source/model gate, not proof that GDScript compiles or that the native
command returns the expected process status.

## Contract

- A destination folder is required before options.
- The remaining arguments must be complete pairs using `--id`, `--title`, or
  `--author`. Missing/empty values, unknown options and extra operands fail.
- A value beginning with `--` is treated as a missing option value. The legacy
  downstream loop does not skip consumed values, so such a token is ambiguous
  and may be interpreted again as another option. This intentionally rejects
  previously accepted ambiguous inputs such as `new draft --title --author`.
- Valid argument strings are not changed. Option order, duplicate-key last-win
  behavior, whitespace/Unicode/quoted text, single-dash text and defaults are
  preserved. Non-option values remain opaque: world ID and title/author policy
  belongs to the existing scaffold, not to this guard.
- A folder whose name starts with `--` can be expressed with an explicit path,
  for example `./--draft`; the guard rejects a bare leading option token.
- Invalid input prints the normal usage line plus a fixed, bounded diagnostic,
  calls `quit(2)` and returns before path resolution, default evaluation or
  `WorldScaffold.create`. Diagnostics do not reflect user-supplied text.
- Removing only the additive helper and early-return guard restores the exact
  original CLI source bytes, including the existing parser, scaffold call,
  defaults and success/error reporting.

The suite covers trailing flags after several valid prefixes, empty/missing
operands, all recognized/unknown option-as-value pairings, unknown flags, extra
positionals, valid options in different orders, duplicate options, special text
and fixed diagnostics. A separate finite model of the old parser demonstrates
that trailing options were silently discarded. This is source-level evidence;
it does not create a directory or reproduce the old native behavior.

## Remaining native qualification

Separately authorized Godot checks should verify syntax/type checking, status 2
and normal usage for every malformed form through each shipped entrypoint,
and no destination/file/package activity on those error paths. Valid forms
should produce the same draft/defaults/content as before, including duplicate
option precedence. Shared `WorldScaffold`, desktop authoring and templates are
outside this change. Global `KitLoop` argument rewriting occurs before this
preflight and needs its own independent handling; this patch does not change it.
