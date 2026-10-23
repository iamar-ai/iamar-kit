# Root signer text-replacement regression

Run from the repository root:

    PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_signer_text/test_model.py

This finite check reads `scripts/kit/world_sign.gd` as text and runs only an
inert Python model. It does not import repository implementation code, launch
Godot, read or generate keys, create packages, sign files, start a host or use
the network. It needs only the Python standard library.

The source assertions bind the model's important control-flow decisions to the
pure `_set_signer` helper and confirm that its caller rejects failure before
the existing manifest write. The independent oracle consumes root members with
Python's JSON decoder rather than sharing the helper's depth/string scanner.
The matrix covers 264 combinations of escaped strings, nested extension values,
member order and formatting. Additional cases cover escaped root member names,
duplicate root claims, nonobject and malformed inputs, empty objects, insertion,
idempotence, exact surrounding byte preservation and deterministic manifest
hash input. The former regex's corruption and nested-decoy failures are
reproduced without executing the signing tool.

Two explicitly labeled cases simulate Godot accepting a root trailing comma
(which Python's JSON parser rejects) and confirm that insertion reuses it.
They supply only each known fixture's parsed object; they do not emulate or
qualify Godot's parser.
Another 145 cases simulate parser acceptance/early termination for nonstandard
control bytes outside strings and confirm safe refusal, including raw NUL and
controls separating a root signer key from its colon. This avoids relying on
the engine's broader whitespace rules for member identity or duplicate checks.

Passing is source/model evidence only. Python's JSON parser does not establish
Godot's JSON parsing semantics, and these checks do not parse or execute
GDScript, verify RSA, exercise file writes or qualify native packaging. The
existing native release fixture (`tests/kit_release/run.sh`) generates keys,
exports and runs a browser; it is intentionally not invoked here. Actual
native helper/signing/package checks remain a separate authorized gate.

The production change replaces only the root signer value (or inserts a new
root member). It leaves other manifest bytes in place, refuses duplicate root
signer members and nonobject claims, and leaves canonical signature and signed
piece-list creation/verification unchanged.
