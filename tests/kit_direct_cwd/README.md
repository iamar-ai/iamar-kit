# Creator direct-source cwd guard

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_direct_cwd/test_inert.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_cwd_argv/test_inert.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_new_argv/test_inert.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_view_argv/test_inert.py
```

The additive guards in world_new._initialize and world_view._init call the same
pure KitLoop._cwd_error helper on raw process arguments before user_args strips
global options. This covers direct source `-s` entrypoints for new, validate,
preview and perf, including the current Windows source wrapper route.

Malformed cwd arguments use each tool's existing usage text and the helper's
fixed diagnostic, then quit(2) and return immediately. Valid raw arguments are
not rewritten. The existing creator option parsers, directory resolution,
scaffold/package logic, reports, tiers and rendering code stay byte-identical.
Dispatched calls can safely repeat this pure check; no new routing is added.

The tests translate only the exact additive caller prefix and the shared pure
helper under constrained AST/call allowlists. Engine calls are replaced with
inert event-recording sentinels. They show that malformed cases do not reach the
user_args sentinel and that removing the return permits continuation. They do
not execute Godot, query a process environment, resolve a path, change cwd,
create/open a world or invoke any package/renderer/script code.

Exact-source projection checks remove only the additive guard and recover the
previously accepted new/view source hashes. Existing option suites retain their
original helper and downstream preservation checks, adjusted only to recognize
the new additive prefix. The KitLoop helper is an explicit previously reviewed
dependency; no second parser copy is introduced.

This is limited to these creator entrypoints. It does not change wrappers,
signing, host, assets, tiers, techniques or other direct source tools. Standalone
host argument parsing remains independently owned. Native GDScript/CLI syntax,
status/diagnostics, actual side-effect absence and platform qualification remain
unrun and require separate authorization. No full creator journey is closed by
these source/model results.
