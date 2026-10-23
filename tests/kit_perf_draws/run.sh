#!/usr/bin/env bash
# Source contract (an internal task): the perf draw_calls TARGET uses the maximum draws over every VIEW,
# not the draws of the view with the most triangles.   tests/kit_perf_draws/run.sh
set -euo pipefail
F="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/scripts/kit/world_view.gd"
grep -q 'if dc > _max_draws\[1\]:' "$F"
grep -q '\["draw_calls", _max_draws\[1\], TARGET_DRAWS' "$F"
grep -q 'MAXDRAWS view' "$F"
if grep -q '"draw_calls", _worst\[2\]' "$F"; then echo "PERF_DRAWS FAIL: TARGET still reads the busiest-triangle view"; exit 1; fi
echo "PERF_DRAWS PASS"
