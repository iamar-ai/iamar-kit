# Signer input regression

Run from the repository root, after the root-signer text-replacement dependency:

    PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_signer_input/test_model.py
    PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_signer_text/test_model.py

These finite tests read production source as text and run inert Python models.
They do not run GDScript, access or generate keys, sign, create packages, start
hosts, import repository implementation code or use the network. The existing
`tests/kit_signer_text/test_model.py` pure model is the only local dependency.

The confirmed pre-existing bug is global pretty-print substitution after JSON
serialization: the signer `Alice":Bob` becomes `Alice": Bob`. An escaped quote
still contains a quote-colon substring, which the global substitution changes
inside the JSON string. Removing both cosmetic substitutions and using the
existing JSON serializer's output directly preserves string values. A plain
comma-before-quote name does not independently reproduce the bug, because JSON
escapes the quote; the regression explicitly records that negative case.

Seven test groups cover:

- Four reproductions of quote-colon corruption and the corrected model output.
- 2,380 short-name combinations plus whitespace, Unicode normalization forms,
  control escapes and a long value, comparing decoded UTF-8 name bytes.
- The caller-to-root-member model pipeline, exact outer manifest preservation,
  insertion, escaped root keys, nested decoys and idempotence.
- Missing direct `pack` operands, including the old two-argument bounds error.
- Existing dispatch for three/four operands, path-normalization spy calls,
  unchanged name forwarding with spaces and punctuation, and extra operands.
- Direct `_pack` empty key/name refusal, separately from raw CLI arguments.
- Source assertions tying those decisions to the two modified production lines,
  unchanged signing argument and pre-write/pre-key-load refusal order.

The dispatch change only checks that the required output operand exists before
reading it. Existing `_pack` still rejects missing key/name operands. The root
signer scanner, signature construction, signed piece-list flow and verification
are unchanged. Compact signer-object separators are intentional; only that
newly constructed member's cosmetic whitespace changes.

Path conversion is a recording spy, not a platform-path implementation. A key
operand explicitly supplied as the empty string is passed through `_abs` and
resolved relative to the working directory before `_pack`; it is different from
an omitted key operand. Tests do not claim that this CLI case returns usage code
2. Downstream work returns a distinctive spy sentinel, not a pack success code.
The direct `_pack` tests alone pass an actual empty key-path value to its guard.

Canonical signing-text construction is untouched. Because the manifest's raw
bytes are hashed, compact separators intentionally change its digest even for
an ordinary name. The signing path rewrites the manifest before constructing the
new signature, so this is not a claim that old and new signature inputs match.

Passing provides source/model evidence, not a GDScript parse or execution result.
Python JSON encoding is not a qualification of Godot JSON encoding. Native
argument dispatch, key handling, real signing, file writes, package admission
and supported-platform behavior remain separate authorized validation gates.
