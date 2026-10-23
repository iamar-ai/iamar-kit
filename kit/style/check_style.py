#!/usr/bin/env python3
"""Check a style profile (style.json) and paint its materials.

    python3 kit/style/check_style.py [PROFILE ...]          check (default: every kit/style/*/style.json)
    python3 kit/style/check_style.py --paint OUT [--profile P] [--size N] [--only a,b]
                                                           paint P's material layers, tinted, into OUT

PROFILE is a path to a style.json or a profile id under kit/style/<id>/. A profile with
"extends": "<id>" is merged over that profile first (this file wins); the merged result
is what gets checked and painted.

Checks (exit 1 on any ERROR):
  * the JSON Schema kit/style/schema/style.schema.json (needs the jsonschema module;
    without it only the required fields are checked and a WARN says so);
  * every material layer exists in the painter (kit/tools/paint_materials.py LAYERS);
  * atmosphere presets use only scene.environment fields that exist
    (docs/WORLD_FORMAT.md 4.1): nothing invented;
  * a profile that extends another may tighten triangle budgets, never loosen them;
  * a profile that declares "sources" cites a source for every palette colour and region;
  * no palette colour is pure black or missing-texture pink (lint.min_albedo_value).

--paint writes OUT/<material>.png (seamless, 256 px/m at 1024) for every entry in
materials.layers, tinted to its colour, plus OUT/style_materials.json (profile id,
material -> file, layer, tint, metres per tile). Needs numpy and Pillow (the painter's).
"""
from __future__ import annotations

import argparse
import colorsys
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

STYLE_DIR = Path(__file__).resolve().parent
KIT = STYLE_DIR.parent
SCHEMA = STYLE_DIR / "schema" / "style.schema.json"
PAINTER = KIT / "tools" / "paint_materials.py"

# docs/WORLD_FORMAT.md 4.1 environment: the fields a package may set.
ENV_FIELDS = {
    "": {"sky", "time_of_day", "day_length_minutes", "sun", "ambient", "fog", "weather", "exposure"},
    "sky": {"type", "top_color", "horizon_color", "ground_color", "color", "faces", "rotation", "energy"},
    "sun": {"enabled", "color", "energy", "shadows", "direction"},
    "ambient": {"color", "energy", "source"},
    "fog": {"enabled", "color", "density", "height", "height_density", "sky_affect"},
    "weather": {"kind"},
}


def painter_layers() -> list[str]:
    """The painter's LAYERS list, read from its source (no numpy needed)."""
    m = re.search(r"^LAYERS\s*=\s*\[(.*?)\]", PAINTER.read_text(encoding="utf-8"), re.S | re.M)
    return re.findall(r'"([a-z_]+)"', m.group(1)) if m else []


def merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = copy.deepcopy(base)
        for k, v in over.items():
            out[k] = merge(base[k], v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


def resolve(ref: str) -> Path:
    p = Path(ref)
    if p.suffix == ".json" or p.exists():
        return p
    return STYLE_DIR / ref / "style.json"


def load(ref: str, seen=None) -> tuple[dict, dict | None]:
    """(merged profile, parent merged profile or None)."""
    seen = seen or []
    path = resolve(ref)
    raw = json.loads(path.read_text(encoding="utf-8"))
    parent_id = raw.get("extends")
    if not parent_id:
        return raw, None
    if parent_id in seen or parent_id == raw.get("id"):
        raise ValueError("extends cycle: %s" % " -> ".join(seen + [parent_id]))
    parent, _ = load(parent_id, seen + [raw.get("id", str(path))])
    merged = merge(parent, raw)
    return merged, parent


def hex_value(h: str) -> tuple[float, float, float]:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)


def check(ref: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    err = lambda m: out.append(("ERROR", m))
    warn = lambda m: out.append(("WARN", m))
    try:
        prof, parent = load(ref)
    except (OSError, ValueError) as e:
        return [("ERROR", "cannot load: %s" % e)]

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        import jsonschema
        for e in sorted(jsonschema.Draft202012Validator(schema).iter_errors(prof), key=lambda e: list(e.path)):
            err("schema: %s: %s" % ("/".join(map(str, e.path)) or "(root)", e.message))
    except ImportError:
        warn("jsonschema not installed: only required fields checked")
        for k in schema["required"]:
            if k not in prof:
                err("schema: missing %s" % k)
        if prof.get("schema") != "iamar-style/1":
            err("schema: 'schema' must be iamar-style/1")
        for name, s in (prof.get("palette") or {}).items():
            if not (isinstance(s, dict) and re.fullmatch(r"#[0-9a-fA-F]{6}", str(s.get("hex", "")))):
                err("schema: palette/%s/hex: not #rrggbb" % name)

    layers = set(painter_layers())
    for name, m in (prof.get("materials", {}).get("layers") or {}).items():
        if isinstance(m, dict) and m.get("layer") not in layers:
            err("materials.layers.%s: painter has no layer %r (known: %s)" % (name, m.get("layer"), ", ".join(sorted(layers))))
    for name, s in (prof.get("palette") or {}).items():
        if isinstance(s, dict) and s.get("pattern") and s["pattern"] not in layers:
            err("palette.%s: pattern %r is not a painter layer" % (name, s["pattern"]))

    for pname, preset in (prof.get("atmosphere", {}).get("presets") or {}).items():
        env = preset.get("environment", {}) if isinstance(preset, dict) else {}
        for k, v in env.items():
            if k not in ENV_FIELDS[""]:
                err("atmosphere.%s: scene.environment has no field %r (do not invent scene fields)" % (pname, k))
            elif isinstance(v, dict) and k in ENV_FIELDS:
                for sub in v:
                    if sub not in ENV_FIELDS[k]:
                        err("atmosphere.%s.%s: no field %r in WORLD_FORMAT.md 4.1" % (pname, k, sub))

    gd = (prof.get("dimensions") or {}).get("grand_door_m")
    if gd is not None:
        if not isinstance(gd, dict):
            err("dimensions.grand_door_m: must be an object {building kind: metres or [min, max]}, got %s" % type(gd).__name__)
        else:
            for k, v in gd.items():
                vals = v if isinstance(v, list) else [v]
                if not vals or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in vals):
                    err("dimensions.grand_door_m.%s: must be a number or a list of numbers" % k)

    if parent is not None:
        mine = prof.get("budgets", {}).get("triangles", {})
        theirs = parent.get("budgets", {}).get("triangles", {})
        for k, v in mine.items():
            if k in theirs and isinstance(v, int) and v > theirs[k]:
                err("budgets.triangles.%s: %d loosens %s's %d (a profile may only tighten)" % (k, v, parent.get("id"), theirs[k]))

    if "sources" in prof:
        for name, s in (prof.get("palette") or {}).items():
            if isinstance(s, dict) and not s.get("source"):
                err("palette.%s: no source (profiles that declare sources cite every colour)" % name)
        for name, r in (prof.get("regions") or {}).items():
            if isinstance(r, dict) and not r.get("source"):
                err("regions.%s: no source" % name)

    min_v = float(prof.get("lint", {}).get("min_albedo_value", 0.0))
    for name, s in (prof.get("palette") or {}).items():
        h = s.get("hex", "") if isinstance(s, dict) else ""
        if re.fullmatch(r"#[0-9a-fA-F]{6}", h):
            hh, ss, vv = hex_value(h)
            if vv < min_v:
                err("palette.%s: %s is darker than lint.min_albedo_value %.2f (no black surfaces)" % (name, h, min_v))
            if h.lower() == "#ff00ff":
                err("palette.%s: missing-texture pink" % name)
    return out


def paint(ref: str, out_dir: Path, size: int, only=None) -> int:
    prof, _ = load(ref)
    mats = prof.get("materials", {}).get("layers") or {}
    if only:
        unknown = sorted(set(only) - set(mats))
        if unknown:
            print("ERROR %s has no material(s) %s" % (ref, ", ".join(unknown)))
            return 1
        mats = {k: v for k, v in mats.items() if k in only}
    if not mats:
        print("ERROR %s has no materials.layers" % ref)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    index = {"profile": prof["id"], "size": size, "tile_m": prof.get("materials", {}).get("tile_m", 4.0), "materials": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for name, m in mats.items():
            cmd = [sys.executable, str(PAINTER), tmp, "--materials", m["layer"], "--size", str(size)]
            if m.get("tint"):
                cmd += ["--tint", "%s=%s" % (m["layer"], m["tint"])]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print("ERROR painting %s: %s" % (name, (r.stderr or r.stdout).strip()))
                return 1
            shutil.move(str(Path(tmp) / ("%s.png" % m["layer"])), str(out_dir / ("%s.png" % name)))
            index["materials"][name] = {"file": "%s.png" % name, "layer": m["layer"], "tint": m.get("tint")}
            print("PAINTED %s (%s %s)" % (out_dir / ("%s.png" % name), m["layer"], m.get("tint", "untinted")))
    (out_dir / "style_materials.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("profiles", nargs="*")
    ap.add_argument("--paint", metavar="OUT")
    ap.add_argument("--profile", default="iamar")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--only", help="comma-separated material names to paint (default all)")
    a = ap.parse_args(argv)
    if a.paint:
        return paint(a.profile, Path(a.paint), a.size, [n.strip() for n in a.only.split(",")] if a.only else None)
    refs = a.profiles or [str(p) for p in sorted(STYLE_DIR.glob("*/style.json"))]
    bad = 0
    for ref in refs:
        found = check(ref)
        errors = [m for lvl, m in found if lvl == "ERROR"]
        for lvl, m in found:
            print("%s %s: %s" % (lvl, ref, m))
        print("%s %s" % ("FAIL" if errors else "OK", ref))
        bad += bool(errors)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
