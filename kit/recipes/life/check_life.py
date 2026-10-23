#!/usr/bin/env python3
"""Check a world scene uses the life recipes, and that the recipes cite real city files.

usage: check_life.py <scene.json> <iamar-checkout>

Prints LIFE_OK when every check passes, otherwise one FAIL line per problem.
Data-only: it does not run the world (see README "What is not verified").
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIN_FEATURES = 4
SIX_RECIPES = 6


def scene_features(scene: dict) -> dict[str, bool]:
    """Which life features the scene uses, by the data that drives them."""
    sounds = scene.get("sounds", [])
    return {
        "idle_npc": any(n.get("idle") for n in scene.get("npcs", [])),
        "wind_sway": any(o.get("sway") is True for o in scene.get("objects", [])),
        "ambient_loop": any(s.get("loop") and "position" not in s for s in sounds),
        "wandering_creature": any(c.get("wander_radius", 0) > 0 for c in scene.get("creatures", [])),
        "positional_fire_sound": any(
            s.get("loop") and "position" in s and s.get("radius", 0) > 0 for s in sounds
        ),
    }


def cited_paths(readme: str) -> set[str]:
    """Backticked city file paths in the README (scripts/, shaders/, ...)."""
    found = set()
    for token in re.findall(r"`([^`\s]+)`", readme):
        if "/" in token and re.search(r"\.(gd|gdshader|gdshaderinc)$", token):
            found.add(token)
    return found


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip())
        return 2
    scene_path, checkout = Path(sys.argv[1]), Path(sys.argv[2])
    failures: list[str] = []

    try:
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        print(f"FAIL scene does not load: {err}")
        return 1
    if scene.get("format") != "iamar-scene" or scene.get("format_version") != 0:
        failures.append("FAIL scene header is not iamar-scene format_version 0")

    schema_path = checkout / "schemas" / "scene.schema.json"
    try:
        import jsonschema
    except ImportError:
        print("NOTE jsonschema not installed: scene schema not checked")
    else:
        if not schema_path.is_file():
            failures.append(f"FAIL scene schema missing in checkout: {schema_path}")
        else:
            validator = jsonschema.Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
            for err in sorted(validator.iter_errors(scene), key=str):
                failures.append(f"FAIL scene schema {list(err.path)}: {err.message}")

    features = scene_features(scene)
    used = [name for name, on in features.items() if on]
    if len(used) < MIN_FEATURES:
        failures.append(f"FAIL scene uses {len(used)} life features, need {MIN_FEATURES}: {used}")

    readme = (HERE / "README.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (\d+)\. ", readme, flags=re.M)
    if headings != [str(i) for i in range(1, SIX_RECIPES + 1)]:
        failures.append(f"FAIL README recipe headings are {headings}, expected 1..{SIX_RECIPES}")

    paths = cited_paths(readme)
    if not paths:
        failures.append("FAIL README cites no city files")
    for rel in sorted(paths):
        if not (checkout / rel).is_file():
            failures.append(f"FAIL cited file missing in checkout: {rel}")

    if failures:
        print("\n".join(failures))
        return 1
    print(f"LIFE_OK features={','.join(used)} cited_files={len(paths)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
