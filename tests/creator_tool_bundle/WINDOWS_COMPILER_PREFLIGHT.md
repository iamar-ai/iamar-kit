# Windows TypeScript wrapper preflight

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/creator_tool_bundle/test_windows_compiler_preflight.py
```

This finite source/model suite does not launch `cmd.exe`, Node, TypeScript,
Godot, a guest, a service or a subprocess. It reads `kit/iamar-world.cmd` and
evaluates only its inspected SET/IF/GOTO/WHERE selection statements against
virtual Windows file/directory sets. It fails on unrecognized model statements.
`IAMAR_TEST_SOURCE_ROOT` selects another source tree for source-contract checks.

The wrapper routes `compile-typescript` before browser discovery, the native
browser prerequisite and native argument shifting. That pure-Node command can
therefore select a complete kit without an adjacent browser executable. The
three original operands are retained; missing/empty operands and excess operands
are refused. The unsupported `--from-source` route keeps its Linux-only guidance.
An existing kit packer selects kit SDK/guest files as one set; absent dependencies
do not borrow individually from `IAMAR_PROJECT`. Source-checkout fallback applies
when there is no kit packer. Compiler discovery prefers the package layout over
the loose legacy file, and an explicit nonempty compiler/Node selection is
authoritative. Missing files and directory substitutions fail preflight.

Source checks also cover the literal-exclamation-mark setup when the caller uses
delayed expansion, clearing a caller-defined `ERRORLEVEL` before packer launch,
the exact quoted packer operands, and byte preservation of unrelated native
dispatch. The selection model exercises all 64 kit/source presence combinations,
directory substitutions, compiler precedence, explicit invalid choices and PATH
Node selection. These checks do not substitute for running the batch language.

Windows `cmd.exe` quoting/expansion, actual file access and permissions, PATHEXT,
reparse points, junctions and dangling links, Node versions, real compiler and
package output, and released-browser/platform acceptance remain unrun. Empty
Windows environment variables behave as absent; this is not a Unix empty-value
override test. No SDK, source snapshot, native command, signing or host behavior
is changed by this patch.
