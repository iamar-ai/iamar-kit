"""Build and check the annotated good/bad gallery.

    python gallery.py build   # render gallery.md from gallery.json
    python gallery.py check   # validate gallery.json (exit 1 on any error)
    python gallery.py check --sources <iamar repo dir>   # also confirm each source file exists

gallery.json is the source of truth; gallery.md is generated from it.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "gallery.json")
OUT = os.path.join(HERE, "gallery.md")
STATUSES = {"WORKS", "PARTIAL", "FAILED"}
LAYERS = {"engineering", "style"}
MIN_ENTRIES = 30
REQUIRED_KEYS = ["id", "category", "status", "layer", "recipe", "title", "seen", "lesson", "source"]
SOURCE_RE = re.compile(r"^docs/[^:]+:\d+$")


def load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def check(data, sources=None):
    errors = []
    entries = data["entries"]
    if len(entries) < MIN_ENTRIES:
        errors.append(f"only {len(entries)} entries, need {MIN_ENTRIES}")
    seen_ids = set()
    for e in entries:
        where = e.get("id", "?")
        for key in REQUIRED_KEYS:
            if not e.get(key):
                errors.append(f"{where}: missing {key}")
        if where in seen_ids:
            errors.append(f"{where}: duplicate id")
        seen_ids.add(where)
        if e.get("category") not in data["categories"]:
            errors.append(f"{where}: unknown category {e.get('category')}")
        if e.get("status") not in STATUSES:
            errors.append(f"{where}: bad status {e.get('status')}")
        if e.get("layer") not in LAYERS:
            errors.append(f"{where}: bad layer {e.get('layer')}")
        src = e.get("source", "")
        if not SOURCE_RE.match(src):
            errors.append(f"{where}: source must be docs/<path>:<line>, got {src!r}")
        elif sources:
            path = src.rsplit(":", 1)[0]
            if not os.path.isfile(os.path.join(sources, path)):
                errors.append(f"{where}: source file not found: {path}")
    covered = {e.get("category") for e in entries}
    for cat in data["categories"]:
        if cat not in covered:
            errors.append(f"category {cat} has no entry")
    return errors


def render(data):
    lines = [
        "# Gallery: good and bad examples from the iamar build",
        "",
        "Generated from gallery.json by gallery.py build. Do not edit by hand.",
        "Each entry is a real outcome recorded in its source. WORKS, PARTIAL or FAILED.",
        "Pictures stay in the source repository (the iamar browser source (not public)); the source column says where.",
        "",
    ]
    for cat in data["categories"]:
        items = [e for e in data["entries"] if e["category"] == cat]
        if not items:
            continue
        lines += [f"## {cat.capitalize()} ({len(items)})", ""]
        for e in items:
            lines += [
                f"### {e['id']} {e['title']} - {e['status']}",
                f"- Seen: {e['seen']}",
                f"- Lesson: {e['lesson']}",
                f"- Recipe: `{e['recipe']}` ({e['layer']} layer)",
                f"- Source: `{e['source']}`",
                "",
            ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv):
    if len(argv) < 2 or argv[1] not in ("build", "check"):
        print(__doc__)
        return 2
    data = load()
    if argv[1] == "build":
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            f.write(render(data))
        print(f"wrote {OUT} ({len(data['entries'])} entries)")
        return 0
    sources = None
    if "--sources" in argv:
        sources = argv[argv.index("--sources") + 1]
    errors = check(data, sources)
    for err in errors:
        print("ERROR", err)
    print(f"entries={len(data['entries'])} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
