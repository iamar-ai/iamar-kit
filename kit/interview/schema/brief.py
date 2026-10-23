#!/usr/bin/env python3
"""Validate a design brief (brief.json), its readable twin (world.brief.md) and the final build report.

  python3 kit/interview/schema/brief.py check brief.json [--md world.brief.md] [--approved]
  python3 kit/interview/schema/brief.py report brief.json report.json

`check` exits 1 on any error and prints one ERROR line each. `--approved` also demands the approval
record and no open questions (use it before the build starts). `report` compares the build report with
the brief: every budget and every feature must be reported, and a measured value over its budget fails.
Fields are described in kit/interview/PROTOCOL.md section 6.
Python 3.8+, standard library only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TYPES = ["town", "nature", "interior", "social", "quest", "shop", "education", "gallery", "event", "other"]
TRACKS = ["A", "B", "C"]
TIERS = ["low", "medium", "high", "ultra"]
ACCESS = ["private", "buddies", "public"]
# Triangle and texture caps per hardware tier: docs/WORLD_TIERS.md (low = manifest.budgets).
TIER_CAPS = {
    "low": {"triangles": 150000, "texture_size": 1024},
    "medium": {"triangles": 400000, "texture_size": 2048},
    "high": {"triangles": 900000, "texture_size": 2048},
    "ultra": {"triangles": 1000000, "texture_size": 4096},
}
BUDGET_KEYS = ["triangles", "texture_size", "texture_bytes", "download_mb"]
CHARACTERS = ("standard", "restyled", "custom")
REQUIRED = ["vision", "audience", "type", "track", "style_profile", "mood", "setup", "tier_target",
            "budgets", "reuse", "connections", "features", "checkpoints", "answers"]


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def check_brief(b: dict, approved: bool = False) -> list:
    errs = []
    if not isinstance(b, dict):
        return ["brief is not an object"]
    for k in REQUIRED:
        if k not in b:
            errs.append(f"missing field: {k}")
    if errs:
        return errs

    if not isinstance(b["vision"], str) or not b["vision"].strip():
        errs.append("vision must be one non-empty sentence")
    a = b["audience"]
    if not isinstance(a, dict) or a.get("access") not in ACCESS or not _is_int(a.get("concurrent")) or a["concurrent"] < 1:
        errs.append(f"audience needs access ({'/'.join(ACCESS)}) and concurrent >= 1")
        a = {}
    if b["type"] not in TYPES:
        errs.append(f"type must be one of {TYPES}")
    chars = b.get("characters", "standard")
    if chars not in CHARACTERS:
        errs.append(f"characters must be one of {CHARACTERS}")
    elif chars == "custom" and not b.get("custom_characters"):
        errs.append("characters 'custom' needs custom_characters: the models the builder supplies")
    extra = b.get("extra_types", [])
    if not isinstance(extra, list) or any(t not in TYPES or t == b["type"] for t in extra):
        errs.append("extra_types must be other world types")
    if b["track"] not in TRACKS:
        errs.append("track must be A, B or C")
    if b["tier_target"] not in TIERS:
        errs.append(f"tier_target must be one of {TIERS}")

    sp = b["style_profile"]
    if not isinstance(sp, str) or not sp:
        errs.append("style_profile must be 'iamar' or the path of a style.json")
    elif b["track"] == "A" and sp != "iamar":
        errs.append("track A uses the iamar style profile")
    elif b["track"] in ("B", "C") and sp == "iamar":
        errs.append(f"track {b['track']} needs its own style.json, not the iamar profile")
    sf = b.get("style_file")
    if sf is not None:
        if not isinstance(sf, str) or not sf.endswith(".json"):
            errs.append("style_file must be the path of the world's style.json")
        elif b["track"] != "A":
            errs.append("style_file is for track A only; tracks B and C name their style.json in style_profile")

    s = b["setup"]
    if not isinstance(s, dict) or s.get("build_tier") not in (0, 1, 2) or not isinstance(s.get("blender"), bool) \
            or not isinstance(s.get("gpu"), bool):
        errs.append("setup needs blender (bool), gpu (bool) and build_tier (0, 1 or 2)")
    else:
        if s["build_tier"] == 2 and not s["gpu"]:
            errs.append("build_tier 2 needs a local GPU (setup.gpu)")
        if b.get("hero_quality") == "city" and s["build_tier"] == 0:
            errs.append("conflict F3: city-grade hero assets need build_tier 1 or 2")

    bud = b["budgets"]
    if not isinstance(bud, dict):
        errs.append("budgets must be an object")
    else:
        bad = [k for k in BUDGET_KEYS if not _is_int(bud.get(k)) or bud[k] <= 0]
        for k in bad:
            errs.append(f"budgets.{k} must be a positive integer")
        cap = TIER_CAPS.get(b["tier_target"])
        if cap and not bad:
            for k, v in cap.items():
                if bud[k] > v:
                    errs.append(f"budgets.{k} {bud[k]} is over the {b['tier_target']} tier cap {v}")

    c = b["connections"]
    if isinstance(c, dict) and a.get("access") == "public" and c.get("hosting") == "own-computer" \
            and a.get("concurrent", 0) > 30:
        errs.append("conflict F1: a public world of over 30 visitors needs stronger hosting than one's own computer")

    for k in ("reuse", "features", "checkpoints"):
        if not isinstance(b[k], list):
            errs.append(f"{k} must be a list")
    feats = b["features"] if isinstance(b["features"], list) else []
    for f in feats:
        if not isinstance(f, dict) or not f.get("id") or not f.get("kind"):
            errs.append("every feature needs id and kind")
    if b["tier_target"] == "low" and sum(1 for f in feats if isinstance(f, dict) and f.get("kind") == "npc") > 20:
        errs.append("conflict F2: more than 20 animated characters will not hold 30 fps on the low tier")
    if isinstance(b["checkpoints"], list) and not b["checkpoints"]:
        errs.append("checkpoints must name at least one stage where the user sees screenshots")

    ans = b["answers"]
    if not isinstance(ans, list) or not ans:
        errs.append("answers must be a non-empty list")
    else:
        for x in ans:
            if not isinstance(x, dict) or not x.get("id") or "value" not in x:
                errs.append("every answer needs id and value")
                continue
            if x.get("source") not in ("chosen", "default"):
                errs.append(f"answer {x['id']}: source must be chosen or default")
            elif x["source"] == "default" and x.get("shown") is not True:
                errs.append(f"answer {x['id']}: a default must be shown to the user (shown: true)")
        seen = [x.get("id") for x in ans if isinstance(x, dict)]
        if len(seen) != len(set(seen)):
            errs.append("answer ids must be unique")

    if approved:
        if b.get("open_questions"):
            errs.append("open_questions must be empty before the build")
        ap = b.get("approval")
        if not isinstance(ap, dict) or not ap.get("date") or not str(ap.get("user_words", "")).strip():
            errs.append("approval needs date and the user's own words")
    return errs


def check_md(b: dict, md: str) -> list:
    errs = []
    if b["vision"].strip() not in md:
        errs.append("world.brief.md does not contain the vision sentence of brief.json")
    for x in b["answers"]:
        if x.get("source") == "default" and x["id"] not in md:
            errs.append(f"world.brief.md does not list default answer {x['id']}")
    flat = md.replace(",", "")
    for k in BUDGET_KEYS:
        if str(b["budgets"][k]) not in flat:
            errs.append(f"world.brief.md does not state budgets.{k} ({b['budgets'][k]})")
    return errs


def check_report(b: dict, r: dict) -> list:
    errs = []
    got = r.get("budgets", {}) if isinstance(r, dict) else {}
    for k in BUDGET_KEYS:
        m = got.get(k)
        if not isinstance(m, dict) or not isinstance(m.get("measured"), (int, float)):
            errs.append(f"report has no measured value for budgets.{k}")
        elif m["measured"] > b["budgets"][k]:
            errs.append(f"budgets.{k} exceeded: {m['measured']} > {b['budgets'][k]}")
    fs = r.get("features", {}) if isinstance(r, dict) else {}
    for f in b["features"]:
        st = fs.get(f["id"])
        if st is None:
            errs.append(f"report does not mention feature {f['id']}")
        elif st.get("met") is not True:
            errs.append(f"feature {f['id']} not met: {st.get('note', 'no note')}")
    return errs


def check_style_file(b: dict, brief_path: Path) -> list:
    """A track A style_file that exists must extend the iamar profile (it may be written after the brief)."""
    sf = b.get("style_file")
    if not isinstance(sf, str) or b.get("track") != "A":
        return []
    for cand in (Path(sf), brief_path.parent / sf, brief_path.parent / Path(sf).name):
        if cand.is_file():
            ext = _load(cand).get("extends")
            return [] if ext == "iamar" else [f"style_file {sf} must extend iamar (extends: {ext!r})"]
    return []


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main(argv) -> int:
    if len(argv) < 3 or argv[1] not in ("check", "report") or (argv[1] == "report" and len(argv) < 4):
        print(__doc__)
        return 2
    try:
        b = _load(argv[2])
        errs = check_brief(b, approved="--approved" in argv)
        if not errs and argv[1] == "check":
            errs += check_style_file(b, Path(argv[2]))
        if not errs and argv[1] == "check" and "--md" in argv:
            errs += check_md(b, Path(argv[argv.index("--md") + 1]).read_text(encoding="utf-8"))
        if not errs and argv[1] == "report":
            errs += check_report(b, _load(argv[3]))
    except (OSError, ValueError) as e:
        errs = [str(e)]
    for e in errs:
        print("ERROR", e)
    if not errs:
        print("OK")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
