#!/usr/bin/env python3
"""Keep the generated recipe book honest about current versus planned support."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


KIT = Path(__file__).resolve().parents[1]
RECIPES = KIT / "recipes"


def browser_source() -> Path | None:
    """A browser checkout (the iamar browser source (not public)) to check WorldTechniques against, if any."""
    for env in ("IAMAR_BROWSER_SOURCE_ROOT", "IAMAR_BROWSER_REPO", "IAMAR_SRC"):
        if os.environ.get(env):
            root = Path(os.environ[env])
            assert (root / "scripts/kit/world_techniques.gd").is_file(), (env, root)
            return root
    for root in (KIT.parent.parent / "iamar", Path.home() / "code/iamar"):
        if (root / "scripts/kit/world_techniques.gd").is_file():
            return root
    return None


def check_browser_techniques(by_id: dict, browser_file: dict) -> str:
    """One file per automatic recipe on both sides: the entries that name a
    BROWSER_TECHNIQUE are exactly the recipes WorldTechniques runs (an internal task)."""
    for rid, path in browser_file.items():
        assert by_id[rid]["kit"] == "automatic" and path == "scripts/kit/techniques/%s.gd" % rid, (rid, path)
    root = browser_source()
    if root is None:
        return "browser sync skipped (no the iamar browser source (not public) checkout: set IAMAR_BROWSER_SOURCE_ROOT)"
    core = (root / "scripts/kit/world_techniques.gd").read_text(encoding="utf-8")
    registry = re.search(r"^const TECHNIQUES := \[(.*?)^\]", core, re.M | re.S)
    assert registry, "WorldTechniques.TECHNIQUES not found"
    runs = []
    for path in re.findall(r'preload\("res://([^"]+)"\)', registry.group(1)):
        text = (root / path).read_text(encoding="utf-8")
        rid = re.search(r'^const ID := "([a-z0-9_]+)"', text, re.M).group(1)
        assert path == "scripts/kit/techniques/%s.gd" % rid, (path, rid)
        runs.append(rid)
    listed = re.search(r"^const RECIPES := \[(.*?)\]", core, re.M | re.S).group(1)
    assert sorted(re.findall(r'"([a-z0-9_]+)"', listed)) == sorted(runs), "WorldTechniques.RECIPES != TECHNIQUES"
    assert sorted(runs) == sorted(browser_file), ("browser runs", sorted(runs), "recipe book marks", sorted(browser_file))
    return "browser sync: %d techniques (%s)" % (len(runs), root)


def main() -> None:
    data = json.loads((RECIPES / "techniques.json").read_text())
    assert data["format"] == "iamar-recipes"
    assert "not acceptance requirements" in data["note"]
    statuses = {recipe["kit"] for recipe in data["recipes"]}
    assert statuses == {"automatic", "manual", "planned"}
    by_id = {recipe["id"]: recipe for recipe in data["recipes"]}
    assert by_id["bake_sky_sun"]["kit"] == "manual"
    assert "KHR_materials_unlit" in " ".join(by_id["bake_sky_sun"]["steps"])
    # recipes with a kit tool name a file that ships in kit/ and are available today
    tools = {rid: recipe["tool"] for rid, recipe in by_id.items() if recipe.get("tool")}
    assert {"bake_sky_sun", "bake_ao_vertex", "bevel_normals", "painted_materials"} <= set(tools)
    for rid, tool in tools.items():
        assert tool.startswith("kit/") and (KIT.parent / tool).is_file(), (rid, tool)
        assert by_id[rid]["kit"] in ("manual", "automatic"), rid

    markdown = (RECIPES / "TECHNIQUES.md").read_text()
    assert "Planned recipes do not\nblock validation, signing, or completion." in markdown
    assert "will apply the *planned* ones" not in markdown

    assert all(r["layer"] in ("engineering", "style") and r["tier"] in (0, 1, 2) for r in data["recipes"])
    layered = (RECIPES / "TECHNIQUES_BY_LAYER.md").read_text()
    assert layered.index("## Engineering") < layered.index("`lod_chain`") < layered.index("## Style") < layered.index("`atmosphere`")
    assert by_id["lod_chain"]["layer"] == "engineering" and by_id["multiview_sculpt"]["tier"] == 2

    # one recipe = one entry file, and the browser runs exactly the ones marked BROWSER_TECHNIQUE
    spec = importlib.util.spec_from_file_location("make_recipes", RECIPES / "make_recipes.py")
    make = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make)
    entries = make.load_entries()
    assert [x["id"] for x in entries] == [x["id"] for x in data["recipes"]]
    assert sorted(p.stem for p in (RECIPES / "entries").glob("*.py")) == sorted(by_id)
    assert {"lod_chain", "instancing", "merge_static", "light_pool"} <= set(make.BROWSER_TECHNIQUE)
    sync = check_browser_techniques(by_id, make.BROWSER_TECHNIQUE)

    with tempfile.TemporaryDirectory(prefix="iamar-recipes-") as raw:
        root = Path(raw)
        target = root / "kit" / "recipes"
        shutil.copytree(RECIPES, target)
        subprocess.run([sys.executable, "kit/recipes/make_recipes.py"], cwd=root, check=True)
        assert (target / "techniques.json").read_bytes() == (RECIPES / "techniques.json").read_bytes()
        assert (target / "TECHNIQUES.md").read_bytes() == (RECIPES / "TECHNIQUES.md").read_bytes()
        assert (target / "TECHNIQUES_BY_LAYER.md").read_bytes() == (RECIPES / "TECHNIQUES_BY_LAYER.md").read_bytes()

    print(sync)
    print("kit recipe tests: 18/18")


if __name__ == "__main__":
    main()
