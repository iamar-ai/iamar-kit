# Kit viewer argv preflight: inert source/model checks

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_view_argv/test_inert.py
```

This suite reads the production `world_view.gd` and translates only its pure
`_argv_error` helper's inspected control-flow subset into Python. Its numeric
string predicates are explicit finite doubles, informed by Godot's documented
[float](https://docs.godotengine.org/en/stable/classes/class_string.html#class-string-method-is-valid-float)
and [integer](https://docs.godotengine.org/en/stable/classes/class_string.html#class-string-method-is-valid-int)
string syntax and the upstream
[String::is_valid_float implementation](https://github.com/godotengine/godot/blob/4.5-stable/core/string/ustring.cpp#L4773-L4808).
That engine predicate accepts unfinished exponents, so production explicitly
requires integer exponent digits. The model retains the engine's permissive
predicate and finite-mantissa conversion, rather than masking this behavior
with a stricter Python regular expression. The translated AST permits only the expected operations and
has no filesystem, process, package, rendering or networking capability.
`IAMAR_TEST_SOURCE_ROOT` can select a different source tree.

Ten test groups cover missing/empty values for every value-taking option,
options accidentally used as values, malformed view vectors and dimensions,
bad numeric spellings, unknown options, missing/extra/empty operands, report
mode's existing validate requirement, unchanged valid argument bytes, repeated
views and options, whitespace/sign/exponent numeric forms and fixed diagnostics
that never reflect user-supplied paths or values. Six unfinished exponent forms
are checked at all six view-vector component positions. Removing the explicit
exponent guard makes those 36 cases incorrectly pass in the source-derived model.

The production guard prints usage and a fixed error, then exits 2 before any
package opening or render/script state is reached. A source-projection digest
checks that the entire original parser and downstream implementation remain
byte-identical to the reviewed baseline. The helper never modifies its input.

This is syntax preflight, not new renderer, tier, NPC or resource policy.
Existing integer range handling, including zero/negative integer spellings,
remains downstream; no new size/frame upper limit is introduced. Finite view
numbers are required, while all existing conversion of accepted representations
is left to the original parser. Package validity and report output remain the
existing validator's responsibility.

These are source and finite model checks, not a Godot parser or native CLI run.
Godot's exact string conversion, platform numeric representation, native usage
exit behavior, release entry routing, package validation and renderer/script
nonactivation still require separately authorized native checks. No compiler,
Godot, world, package, subprocess, listener, service or network is executed by
this suite. A successful test run does not close creator/visitor acceptance.
