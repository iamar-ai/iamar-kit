# Package CLI output handoff

The `package`/`pack` CLI requires an output filename ending in lowercase `.iamar`,
matching `add-to-browser` and the shared UI importer. Wrong or absent suffixes now
fail with exit 2 before path resolution, tier rebuilding or signing child calls.
Valid arguments retain their exact representation and existing downstream behavior.
The low-level WorldPieces packing API still accepts other output suffixes.

Run from the repository root:

    PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_package_output/test_inert.py

Eight groups exercise only source and an inert argv preflight. The test translates
one of two exact-whitelisted source prefixes, records error/quit/dispatch calls,
and pins unchanged downstream and low-level source bytes. It covers final-suffix
case policy, missing operands, spaces/Unicode/Windows paths, preserved arguments,
the old mismatch and one-sentence guide scope. It reads source support files but
performs no path resolution or real package/file operations.

No Godot/GDScript runtime, compiler, signing/key operation, package generation,
import, host, network or user machine is executed. This removes one CLI filename
mismatch; valid output naming alone does not establish package integrity, trust,
import success, native platform support or end-to-end creator acceptance.
