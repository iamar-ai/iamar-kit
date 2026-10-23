#!/usr/bin/env bash
# Discovered by tools/run_all_tests.sh via tests/**/run.sh.
# Bounded bundle fixtures and generator only: no compiler/guest/native execution.
# Requires existing Python 3, Git, Bash and Node >=20; acquires no tools or data.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/creator_tool_bundle/test_kit_bundle.py"
python3 "$ROOT/tests/creator_tool_bundle/test_kit_pack_check.py"
python3 "$ROOT/tests/creator_tool_bundle/test_unix_compiler_resolution.py"
python3 "$ROOT/tests/creator_tool_bundle/test_creator_kit_inventory.py"
node --test "$ROOT/tests/creator_tool_bundle/installed_schema.test.mjs"
