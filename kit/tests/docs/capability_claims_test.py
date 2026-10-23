#!/usr/bin/env python3
"""Docs-vs-runtime capability check (an internal task).

Extracts the claims the kit docs make (world API version, built-in creature kinds, which kinds
are rendered vs reserved) and checks (1) every doc agrees with WORLD_API.md, and (2) when a
browser source tree is given (IAMAR_BROWSER_SRC=<the iamar browser source (not public) checkout>), they match the
browser: WorldApi.VERSION and the kinds in scripts/worlds/world_creatures.gd.
Without a browser tree only (1) runs and the test says so.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
def rd(p): return open(os.path.join(ROOT, p), encoding="utf-8").read()

api, fmt, kit, ts = (rd(p) for p in ("docs/WORLD_API.md", "docs/WORLD_FORMAT.md",
                                     "kit/AGENT_KIT.md", "docs/TYPESCRIPT_WORLDS.md"))
bad = []
def vkey(v): return tuple(int(x) for x in v.split("."))

m = re.match(r"# iamar world API — version (\d+\.\d+)", api)
if not m:
    sys.exit("WORLD_API.md has no 'version X.Y' title")
CUR = m.group(1)

# 1a. "current"/budget statements must name the current version; declared versions may be older
for name, txt in (("WORLD_FORMAT", fmt), ("AGENT_KIT", kit), ("TYPESCRIPT_WORLDS", ts), ("WORLD_API", api)):
    for mm in re.finditer(r"current API is (\d+\.\d+)|\(world API (\d+\.\d+)\)|\(API (\d+\.\d+)\)", txt):
        v = next(g for g in mm.groups() if g)
        if v != CUR:
            bad.append("%s says current API %s, WORLD_API.md says %s: %r" % (name, v, CUR, mm.group(0)))
    for mm in re.finditer(r'"api_version":\s*"(\d+\.\d+)"', txt):
        if vkey(mm.group(1)) > vkey(CUR):
            bad.append("%s declares api_version %s newer than %s" % (name, mm.group(1), CUR))
# api_version() return value documented as (major<<16)|minor
mm = re.search(r"minor of the browser's API: (\d+) for (\d+\.\d+)", api)
if mm and (mm.group(2) != CUR or int(mm.group(1)) != int(CUR.split(".")[1])):
    bad.append("api_version() row says %s for %s, current is %s" % (mm.group(1), mm.group(2), CUR))

# 1b. creature kinds: the three doc statements must agree
def kinds_in(s): return set(re.findall(r"`([a-z_]+)`", s))
sec = re.search(r"Creature `kind` is(.*?)WORLD_FORMAT", kit, re.S).group(1)
res_part = sec.split("reserved")[0]
rendered_kit = kinds_in(re.sub(r"\([^)]*\)", "", res_part.split("the slimes")[0]))
reserved_kit = kinds_in(sec.split("the slimes", 1)[1]) if "the slimes" in sec else set()
rows = re.findall(r"^\| ([^|]+) \| (rendered[^|]*|reserved[^|]*) \|$", fmt, re.M)
rendered_fmt, reserved_fmt = set(), set()
for ks, st in rows:
    ks = kinds_in(ks)
    if not ks or not st.startswith(("rendered", "reserved")):
        continue
    (rendered_fmt if st.startswith("rendered") else reserved_fmt).update(ks)
creatures = {"chicken", "bunny", "cow", "horse", "deer", "wolf", "duck", "duckling", "fish", "frog", "turtle"}
rendered_fmt &= creatures
if rendered_kit != creatures:
    bad.append("AGENT_KIT rendered creature kinds differ: %s" % sorted(rendered_kit ^ creatures))
if rendered_fmt != creatures:
    bad.append("WORLD_FORMAT rendered creature rows differ: %s" % sorted(rendered_fmt ^ creatures))

# 2. against the browser source, when available
src = os.environ.get("IAMAR_BROWSER_SRC")
if src:
    gd = open(os.path.join(src, "scripts/worlds/world_creatures.gd"), encoding="utf-8").read()
    speed = re.search(r"const SPEED := \{(.*?)\}", gd, re.S).group(1)
    browser_kinds = set(re.findall(r'"([a-z_]+)"\s*:', speed))
    if browser_kinds != rendered_kit:
        bad.append("browser draws %s, AGENT_KIT says %s (diff %s)" % (
            sorted(browser_kinds), sorted(rendered_kit), sorted(browser_kinds ^ rendered_kit)))
    wa = open(os.path.join(src, "scripts/sandbox/world_api.gd"), encoding="utf-8").read()
    bv = re.search(r'const VERSION := "(\d+\.\d+)"', wa).group(1)
    if bv != CUR:
        bad.append("browser WorldApi.VERSION %s, docs current %s" % (bv, CUR))
else:
    print("note: IAMAR_BROWSER_SRC not set; browser comparison skipped")

if bad:
    print("FAIL"); [print(" -", b) for b in bad]; sys.exit(1)
print("ok: docs agree on API %s and %d creature kinds" % (CUR, len(creatures)))
