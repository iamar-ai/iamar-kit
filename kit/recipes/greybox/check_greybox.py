#!/usr/bin/env python3
"""Greybox check (recipe book: kit/recipes/greybox/README.md).

Reads a world's `greybox.json` sidecar (format in the README) and fails when a rule of the
greybox-first process breaks: painting before the layout was approved, wrong scale, a building
without an opening, too few eye-height pictures, a missing or empty user approval, an over-budget
block-out. Pure Python 3, no engine needed.

Usage:  check_greybox.py greybox.json [--brief brief.json]
        exit 0 = GREYBOX_OK, 1 = rules broken (one FAIL line each), 2 = bad arguments or unreadable JSON

Approvals follow the checkpoints the user chose in the brief (`checkpoints`, interview D4): copy
them into greybox.json `checkpoints`, or pass `--brief`. The layout (greybox) approval is always
needed before painting; the scale approval only when the brief names a scale checkpoint. Without
either, all three checkpoints are required.
"""
from __future__ import annotations

import json
import sys

STAGES = ["greybox", "scale", "paint"]
# defaults; a world's style profile may state its own (greybox.json "limits" overrides these)
LIMITS = {
    "person_m": [1.6, 2.0],
    "door_m": [2.0, 2.4],
    "storey_m": [2.6, 3.6],
    "eye_m": [1.5, 1.9],
    "triangles": {"building": 3000, "prop": 300, "character": 12000, "creature": 6000, "landmark": 15000},
    "min_eye_shots": 4,
    "min_approval_words": 3,
}
# brief checkpoint names (free text in the interview) -> greybox stages; other checkpoints (for
# example "quest walkthrough") are not greybox stages and are ignored here
CHECKPOINT_STAGE = {"greybox": "greybox", "layout": "greybox", "block-out": "greybox", "blockout": "greybox",
                    "scale": "scale", "scale check": "scale", "size": "scale",
                    "paint": "paint", "look": "paint"}
# names not in the table are matched by keyword ("scale walk", "Scale check at 1.7 m"), so a
# reworded checkpoint never silently drops an approval the user asked to give
CHECKPOINT_KEYWORDS = (("scale", "scale"), ("size", "scale"), ("greybox", "greybox"), ("layout", "greybox"),
                       ("block", "greybox"), ("paint", "paint"), ("look", "paint"))
EYE_KINDS = {"spawn", "street", "landmark", "portal"}
OVERVIEW_KINDS = {"aerial", "map"}


def _in(v, rng):
    return isinstance(v, (int, float)) and rng[0] <= v <= rng[1]


def _stage_of(name) -> str | None:
    n = str(name).strip().lower()
    if n in CHECKPOINT_STAGE:
        return CHECKPOINT_STAGE[n]
    return next((stage for word, stage in CHECKPOINT_KEYWORDS if word in n), None)


def required_stages(checkpoints) -> tuple[set[str], list[str]]:
    """Greybox stages the user asked to approve, from the brief's checkpoints (None = all three)."""
    if checkpoints is None:
        return set(STAGES), []
    if not isinstance(checkpoints, list):
        return set(STAGES), [f"FAIL checkpoints: must be the brief's list of checkpoint names, got {checkpoints!r}"]
    names = {_stage_of(c) for c in checkpoints}
    # greybox first: the layout is approved before anything is painted, whatever the brief says
    return {n for n in names if n} | {"greybox"}, []


def check(g: dict, brief_checkpoints=None) -> list[str]:
    fails = []
    checkpoints = brief_checkpoints if brief_checkpoints is not None else g.get("checkpoints")
    required, cp_fails = required_stages(checkpoints)
    fails += cp_fails
    lim = json.loads(json.dumps(LIMITS))
    for k, v in (g.get("limits") or {}).items():
        if isinstance(v, dict) and isinstance(lim.get(k), dict):
            lim[k].update(v)
        else:
            lim[k] = v
    stage = g.get("stage")
    if stage not in STAGES:
        return [f"FAIL stage: must be one of {STAGES}, got {stage!r}"]
    at = STAGES.index(stage)

    # G1 painting: nothing is painted or baked at the greybox stage
    objects = g.get("objects") or []
    if not objects:
        fails.append("FAIL objects: a greybox lists the objects it blocks out")
    if stage == "greybox":
        for o in objects:
            if o.get("painted") or o.get("baked"):
                fails.append(f"FAIL G1 painted-too-early: {o.get('id')} is painted or baked at the greybox stage")

    # G2 scale
    m = g.get("measurements") or {}
    for key, rng_key in (("person_m", "person_m"), ("door_m", "door_m"), ("storey_m", "storey_m")):
        if key not in m:
            fails.append(f"FAIL G2 scale: measurements.{key} missing (measure it in the block-out, do not assume)")
        elif not _in(m[key], lim[rng_key]):
            fails.append(f"FAIL G2 scale: {key} {m[key]} outside {lim[rng_key]}")

    # G3 openings and G6 budgets
    for o in objects:
        cls = o.get("class", "")
        if cls in ("building", "landmark") and o.get("enterable", True) and not o.get("openings"):
            fails.append(f"FAIL G3 openings: {o.get('id')} has no door or opening (a hole is not an opening: name the opening)")
        budget = lim["triangles"].get(cls)
        if budget and isinstance(o.get("triangles"), (int, float)) and o["triangles"] > budget:
            fails.append(f"FAIL G6 budget: {o.get('id')} {o['triangles']} triangles over the {cls} budget {budget} (a greybox is the cheapest version)")

    # G4 eye-height pictures
    shots = g.get("shots") or []
    eye = [s for s in shots if s.get("kind") in EYE_KINDS]
    for s in eye:
        if not _in(s.get("eye_m"), lim["eye_m"]):
            fails.append(f"FAIL G4 eye height: shot {s.get('file')} eye_m {s.get('eye_m')} outside {lim['eye_m']} (judge from 1.7 m, not from a flying camera)")
    if len(eye) < lim["min_eye_shots"]:
        fails.append(f"FAIL G4 shots: {len(eye)} eye-height shots, need {lim['min_eye_shots']} (spawn, a street, a landmark, the portal arrival)")
    if not any(s.get("kind") in OVERVIEW_KINDS for s in shots):
        fails.append("FAIL G4 shots: no aerial or map overview")

    # G5 approvals: each stage needs the earlier stages approved, with date and the user's words
    approvals = {a.get("checkpoint"): a for a in (g.get("approvals") or [])}
    for needed in STAGES[:at]:
        if needed not in required:
            continue
        a = approvals.get(needed)
        if not a:
            why = ("" if checkpoints is not None else
                   " (no checkpoints given: copy the brief's `checkpoints` into greybox.json or pass --brief)")
            fails.append(f"FAIL G5 approval: stage {stage} needs the user's approval of the {needed} checkpoint first{why}")
        elif not a.get("date") or len(str(a.get("words", "")).split()) < lim["min_approval_words"]:
            fails.append(f"FAIL G5 approval: the {needed} approval needs a date and the user's own words (at least {lim['min_approval_words']})")
    return fails


def _load(path: str, what: str):
    """The JSON object in path, or None after printing why it cannot be read (exit 2)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        print(f"FAIL input: cannot read {what} {path}: {e}")
        return None
    if not isinstance(data, dict):
        print(f"FAIL input: {what} {path} must be a JSON object, got {type(data).__name__}")
        return None
    return data


def main(argv: list[str]) -> int:
    args = argv[1:]
    brief_path = None
    if "--brief" in args:
        i = args.index("--brief")
        if i + 1 >= len(args):
            print(__doc__)
            return 2
        brief_path = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) != 1:
        print(__doc__)
        return 2
    brief_cp = None
    if brief_path is not None:
        brief = _load(brief_path, "brief")
        if brief is None:
            return 2
        brief_cp = brief.get("checkpoints")
        if brief_cp is None:
            print(f"FAIL checkpoints: {brief_path} has no `checkpoints`")
            return 1
    g = _load(args[0], "greybox")
    if g is None:
        return 2
    fails = check(g, brief_cp)
    for line in fails:
        print(line)
    if fails:
        return 1
    print("GREYBOX_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
