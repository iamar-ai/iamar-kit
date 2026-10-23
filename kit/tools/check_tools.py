#!/usr/bin/env python3
"""Fail if a tool entry lacks a field, or a licence URL / fallback, or a ship script has no kit entry.

Usage: python check_tools.py [--allow-pending] [--ship FILE]   (FILE: another ship_scripts.json, for tests)

tools.json: every tool has command, inputs, outputs, hardware, licence (https URL), region limits and fallback.
ship_scripts.json: every kit/inventory/scripts.json row marked ship / ship after wrapping outside
iamar-ai/iamar-kit has exactly one entry, and the entry's kit files, test and doc exist. An entry still
"pending" (a follow-up job brings it in) fails unless --allow-pending (progress view only).
"""
import json, pathlib, sys
here = pathlib.Path(__file__).resolve().parent
root = here.parent.parent
need = "id tier command inputs outputs hardware licence licence_url region_limits redistributable fallback".split()
d = json.loads((here / "tools.json").read_text(encoding="utf-8"))
bad = [f"{t.get('id','?')}: missing {k}" for t in d["tools"] for k in need if t.get(k) in (None, "")]
bad += [f"{t['id']}: licence_url not https" for t in d["tools"] if not t["licence_url"].startswith("https://")]

# What each ship_scripts.json status must carry (an internal task, PUB8).
SHIP_NEED = {"in-kit": ["kit", "command", "test", "doc"], "covered": ["kit", "command", "test", "doc", "reason"],
             "bundled": ["bundle", "dest", "command", "test", "doc"], "browser": ["reason", "doc"],
             "internal": ["reason"], "pending": ["job", "reason"]}
args = sys.argv[1:]
inv_file = root / "kit/inventory/scripts.json"
if not inv_file.exists():  # the public export leaves out kit/inventory (kit/export/rules.json)
    print("\n".join(bad) or f"TOOLS_OK {len(d['tools'])} tools (ship scripts not checked: no kit/inventory/scripts.json)")
    sys.exit(1 if bad else 0)
inv = json.loads(inv_file.read_text(encoding="utf-8"))
ship = {(r["repo"], r["path"]) for r in inv["rows"] if r["repo"] != "iamar-kit" and r["disposition"] in ("ship", "ship after wrapping")}
ship_file = pathlib.Path(args[args.index("--ship") + 1]) if "--ship" in args else here / "ship_scripts.json"
entries = json.loads(ship_file.read_text(encoding="utf-8"))["scripts"]
seen, pending = set(), []
for e in entries:
    key, name = (e.get("repo"), e.get("path")), f"{e.get('repo')}:{e.get('path')}"
    if key in seen:
        bad.append(f"{name}: listed twice in ship_scripts.json")
    seen.add(key)
    if key not in ship:
        bad.append(f"{name}: not a ship row outside the kit in kit/inventory/scripts.json")
    st = e.get("status")
    if st not in SHIP_NEED:
        bad.append(f"{name}: unknown status {st!r}")
        continue
    bad += [f"{name}: {st} entry missing {k}" for k in SHIP_NEED[st] if e.get(k) in (None, "", [])]
    files = list(e.get("kit") or []) + [e[k] for k in ("test", "doc", "bundle") if e.get(k)]
    bad += [f"{name}: {f} does not exist" for f in files if not (root / f).exists()]
    if st == "bundled" and e.get("bundle") and (root / e["bundle"]).exists():
        if pathlib.PurePosixPath(e["path"]).name not in (root / e["bundle"]).read_text(encoding="utf-8"):
            bad.append(f"{name}: {e['bundle']} does not copy it")
    if st == "pending":
        if not isinstance(e.get("job"), int):
            bad.append(f"{name}: pending entry needs a job number")
        pending.append(f"{name}: pending, job {e.get('job')}")
bad += [f"{r}:{p}: ship row without a kit entry (add it to kit/tools/ship_scripts.json)" for r, p in sorted(ship - seen)]
if "--allow-pending" in args:
    print("\n".join(pending))
else:
    bad += pending
print("\n".join(bad) or f"TOOLS_OK {len(d['tools'])} tools, {len(entries)} ship scripts ({len(pending)} pending)")
sys.exit(1 if bad else 0)
