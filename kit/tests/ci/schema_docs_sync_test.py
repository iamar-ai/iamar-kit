#!/usr/bin/env python3
"""Every objects key documented in docs/WORLD_FORMAT.md section 4.4 must be
understood by the pinned kit runtime's browser.

Each documented key either appears in the pinned browser's scene schema
($defs/object properties) or carries a `browser <sha> and later` version
marker saying which browser introduced it, so a world built from the docs is
never rejected by the browser `kit/runtime.lock` pins (its schema sets
additionalProperties:false, so unknown keys are hard errors).

The pinned schema lives in kit/tests/ci/pinned_browser_object_schema.json;
regenerate it from schemas/scene.schema.json at the newly pinned commit in
the iamar browser source (not public) whenever kit/runtime.lock's browser pin changes.

board: iamar-creator-knowledge an internal task
"""

import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
WORLD_FORMAT = os.path.join(REPO, "docs", "WORLD_FORMAT.md")
RUNTIME_LOCK = os.path.join(REPO, "kit", "runtime.lock")
FIXTURE = os.path.join(REPO, "kit", "tests", "ci", "pinned_browser_object_schema.json")
MARKER_RE = re.compile(r"browser\s+[0-9a-f]{8}\s+and\s+later", re.IGNORECASE)


def section_4_4(text):
    start = text.index("### 4.4 objects")
    end = text.index("### 4.5 primitives")
    return text[start:end]


def documented_object_keys(section):
    """Map each documented object key -> its bullet paragraph.

    Only the first backtick key of each bullet is the object key (later
    backticks name sub-keys or values, e.g. `bone` under `attach`).
    """
    keys = {}
    for bullet in re.findall(r"^\* (.*?)(?=^\* |\Z)", section, re.M | re.S):
        m = re.match(r"`([a-z][a-z0-9_]*)`", bullet.strip())
        if m:
            keys.setdefault(m.group(1), " ".join(bullet.split()))
    return keys


def runtime_lock_browser_pin():
    for line in open(RUNTIME_LOCK):
        line = line.strip()
        if line.startswith("browser") and not line.startswith("#"):
            return line.split()[2]
    raise AssertionError("no browser line in kit/runtime.lock")


def main():
    errors = []
    section = section_4_4(open(WORLD_FORMAT).read())
    keys = documented_object_keys(section)
    fixture = json.load(open(FIXTURE))
    pin = runtime_lock_browser_pin()
    if fixture["pinned_browser_sha"] != pin:
        errors.append(
            f"fixture pins {fixture['pinned_browser_sha']} but kit/runtime.lock "
            f"pins browser {pin}: regenerate kit/tests/ci/pinned_browser_object_schema.json "
            "from schemas/scene.schema.json at the new pin (see the test's docstring)."
        )
    props = fixture["object"].get("properties", {})
    additional = fixture["object"].get("additionalProperties", True)
    if additional is not False:
        errors.append(
            "fixture schema no longer sets additionalProperties:false on $defs/object; "
            "the 'unknown key' premise of this test no longer holds — update the test."
        )
    for key, bullet in sorted(keys.items()):
        in_schema = key in props
        has_marker = bool(MARKER_RE.search(bullet))
        if in_schema and has_marker:
            errors.append(
                f"`{key}` is now accepted by the pinned browser's schema but still "
                f"carries a `browser <sha> and later` marker: the runtime pin advanced, "
                "remove the marker (or move the feature note) in docs/WORLD_FORMAT.md 4.4."
            )
        elif not in_schema and not has_marker:
            errors.append(
                f"`{key}` is documented in docs/WORLD_FORMAT.md 4.4 but the pinned "
                f"browser ({pin}) refuses it (not in its scene schema) and the doc "
                "carries no `browser <sha> and later` marker: add the marker saying "
                "which browser introduced it and that the pinned runtime refuses it."
            )
    if errors:
        print("\n".join(f"FAIL: {e}" for e in errors), file=sys.stderr)
        return 1
    print(f"OK: {len(keys)} documented 4.4 object keys consistent with "
          f"pinned browser {pin} scene schema ({len(props)} props).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
