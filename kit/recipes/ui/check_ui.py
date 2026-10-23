#!/usr/bin/env python3
"""Check a world UI page against the world API 0.4 schema and the host limits.

usage: check_ui.py <page.json> <iamar-checkout>

Prints UI_OK when the page passes, otherwise one FAIL line per problem. The schema
(api/ui_page.schema.json in the checkout) is checked when jsonschema is installed;
the host limits the schema cannot state are always checked here. Data-only: it does
not build the page (see README "What is not verified").
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MAX_NODES = 512        # per page, list rows excluded (ui_page_schema description)
MAX_DEPTH = 32
MAX_BYTES = 64 * 1024  # ui_page_set JSON limit
URL = re.compile(r"(https?:|www\.|\bmailto:)", re.IGNORECASE)


def walk(node: dict, depth: int, out: dict) -> None:
    """Collect ids, node count and depth, and any URL text, from one node."""
    out["count"] += 1
    out["depth"] = max(out["depth"], depth)
    node_id = node.get("id")
    if node_id is not None:
        out["ids"].append(node_id)
    text = node.get("text", "")
    if isinstance(text, str) and URL.search(text):
        out["urls"].append(text)
    for child in node.get("children", []):
        walk(child, depth + 1, out)
    if node.get("type") == "list":
        # list rows are built only when visible, so they are not counted per page
        for item in node.get("items", []):
            if isinstance(item, dict):
                probe = {"count": 0, "depth": 0, "ids": [], "urls": []}
                walk(item, depth + 1, probe)
                out["urls"].extend(probe["urls"])


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip())
        return 2
    page_path, checkout = Path(sys.argv[1]), Path(sys.argv[2])
    failures: list[str] = []

    raw = page_path.read_bytes()
    if len(raw) > MAX_BYTES:
        failures.append(f"FAIL page is {len(raw)} bytes, limit {MAX_BYTES}")
    try:
        page = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        print(f"FAIL page does not load: {err}")
        return 1
    if not isinstance(page.get("root"), dict):
        failures.append("FAIL page has no root node")
        print("\n".join(failures))
        return 1

    schema_path = checkout / "api" / "ui_page.schema.json"
    try:
        import jsonschema
    except ImportError:
        print("NOTE jsonschema not installed: UI page schema not checked")
    else:
        if not schema_path.is_file():
            failures.append(f"FAIL UI page schema missing in checkout: {schema_path}")
        else:
            validator = jsonschema.Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
            for err in sorted(validator.iter_errors(page), key=str):
                failures.append(f"FAIL schema {list(err.path)}: {err.message}")

    out = {"count": 0, "depth": 0, "ids": [], "urls": []}
    walk(page["root"], 1, out)
    if out["count"] > MAX_NODES:
        failures.append(f"FAIL page has {out['count']} nodes, limit {MAX_NODES}")
    if out["depth"] > MAX_DEPTH:
        failures.append(f"FAIL nesting {out['depth']} levels, limit {MAX_DEPTH}")
    dupes = sorted({i for i in out["ids"] if out["ids"].count(i) > 1})
    if dupes:
        failures.append(f"FAIL node ids not unique within the page: {dupes}")
    for text in out["urls"]:
        failures.append(f"FAIL text contains a URL (no URLs or network in pages): {text[:60]!r}")

    if failures:
        print("\n".join(failures))
        return 1
    print(f"UI_OK nodes={out['count']} depth={out['depth']} ids={len(out['ids'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
