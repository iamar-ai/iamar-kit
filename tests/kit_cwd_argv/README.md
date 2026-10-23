# Built-in dispatcher `--cwd` preflight

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_cwd_argv/test_inert.py
```

The suite executes only an exact-source pure-helper model under a limited
Python AST/call allowlist. It does not start Godot, invoke any tool, change the
working directory, read the user's environment, resolve paths or create/open a
world. The source/model gate does not establish native GDScript qualification.

## Scope

Recognized `--kit <command>` and `--kit-script <tool-path>` invocations validate
post-command global `--cwd` syntax after dropping the normal game scene but
before loading or attaching a tool script. A trailing bare flag, an empty split
operand, `--cwd=`, or a split operand beginning with another long option fails
with the existing error/status-2 path. Error text is constant and bounded.

Every duplicate occurrence must be well-formed. All valid arguments remain
unchanged, including existing first-occurrence cwd precedence. Values remain
opaque: relative/absolute paths, spaces, Unicode, single-dash names and an
explicit `--cwd=--literal` retain their old behavior. No path-existence,
normalization, authorization or new absolute-path policy is introduced.
The original user_args, working_dir and absolute_path implementations are
byte-identical, as are every command mapping and downstream dispatch step.

The documented grammar requires `--kit`, then command, then arguments including
`--cwd`. This guard does not reorder `--cwd` before the command or reinterpret
ordinary game arguments as kit routing. Ordinary non-kit startup stays unchanged.

## Direct source mode remains a separate gap

Windows source mode still uses direct `-s` tool invocation, bypassing
KitLoop._initialize. This dispatcher guard therefore does not validate malformed
cwd globally for that path. The Windows downloaded-browser `--kit-script` route
and Unix wrapper's `--kit` route are within the source-level boundary. A static
user_args function calling quit and returning an empty array would not reliably
abort its caller, so no such unsafe substitute is added. Completing direct mode
requires a separately reviewed caller guard or routing change.

## Regression coverage and native gate

Cases cover missing/empty/next-option values, split/equals syntax, valid and
invalid duplicates, opaque paths, unknown non-cwd options, argv immutability,
fixed diagnostics, exact original-source preservation, the guard's placement
before load/set_script, and a next-option guard mutation. A finite old-parser
model exhibits silent stripping and invalid directory selection without any
filesystem activity.

Separately authorized native acceptance should check syntax, exit 2, diagnostics,
no tool load/initialization on malformed arguments, and valid command/path parity
through both dispatcher modes. The existing native kit-release suite is not run
by this test. No full creator/visitor journey or platform acceptance is claimed.
