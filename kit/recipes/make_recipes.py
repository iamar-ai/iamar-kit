"""Writes kit/recipes/techniques.json (the source of truth) and TECHNIQUES.md from it.

One recipe = one file in kit/recipes/entries/<id>.py, so recipes added at the same time
never collide. An entry calls r(...) once and sets:
  ORDER   its place in the book (entries sort by ORDER, then id; leave gaps of 10)
  LAYER   "style" when it depends on the art direction (default "engineering": applies to
          every world whatever its look: speed, correctness, loading; a Track B/C world may
          choose differently for style ones)
  TIER    lowest build tier that can apply it (default 0 Blender and kit tools only; 1 needs
          an image/3D generation service; 2 needs a local GPU for the concept-to-mesh pipeline)
  BROWSER_TECHNIQUE  for a kit: "automatic" recipe the browser's WorldTechniques applies to
          every world: its file there (scripts/kit/techniques/<id>.gd in the iamar browser source (not public));
          kit/tests/recipes_test.py checks both sides list the same recipes
(layer and tier: an internal task, H8; the split: iamar-fps an internal task, K5-2)
"""
import json
from pathlib import Path

ENTRIES = Path(__file__).resolve().parent / "entries"

R = []
BROWSER_TECHNIQUE = {}   # recipe id -> its WorldTechniques file in the browser (not in techniques.json)
def r(id, title, area, purpose, when, steps, defaults=None, check="", cost="", source="", kit="manual", tool=""):
    R.append({"id": id, "title": title, "area": area, "purpose": purpose, "when": when,
              "defaults": defaults or {}, "steps": steps, "kit": kit, "check": check, "cost": cost, "source": source})
    if tool:   # the kit file that does it (Blender tools run with iamar-world blender-run)
        R[-1]["tool"] = tool


def load_entries(folder=ENTRIES):
    """The recipes of every entry file, in book order."""
    got = []
    for f in sorted(folder.glob("*.py")):
        R.clear()
        ns = {"r": r, "__file__": str(f)}
        exec(compile(f.read_text(encoding="utf-8"), str(f), "exec"), ns)
        assert len(R) == 1, "%s must call r(...) exactly once (it called it %d times)" % (f.name, len(R))
        x = R[0]
        assert x["id"] == f.stem, "%s defines recipe %r: name the file after its id" % (f.name, x["id"])
        assert isinstance(ns.get("ORDER"), int), "%s needs ORDER = <int>" % f.name
        x["layer"] = ns.get("LAYER", "engineering")
        x["tier"] = ns.get("TIER", 0)
        assert x["layer"] in ("engineering", "style") and x["tier"] in (0, 1, 2), f.name
        if ns.get("BROWSER_TECHNIQUE"):
            assert x["kit"] == "automatic", "%s: a browser technique is kit: automatic" % f.name
            BROWSER_TECHNIQUE[x["id"]] = ns["BROWSER_TECHNIQUE"]
        got.append((ns["ORDER"], x["id"], x))
    got.sort(key=lambda g: (g[0], g[1]))
    R.clear()
    R.extend(g[2] for g in got)
    return R


def main():
    load_entries()

    data = {"format": "iamar-recipes", "version": 1,
            "note": "The source of truth for how iamar worlds are engineered. 'kit' says whether the browser applies a recipe today (automatic), the builder can author it today (manual), or it has no supported package field/tool yet (planned). Planned recipes are reference/backlog, not acceptance requirements: skip and report them; never invent fields.",
            "recipes": R}
    json.dump(data, open("kit/recipes/techniques.json", "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)

    md = ["# iamar world recipes", "",
          "How to engineer an iamar world that looks good and runs smoothly on every visitor's GPU.",
          "Each recipe says what it is for, when to use it, the steps, the defaults, how the",
          "kit checks it and where it comes from. `techniques.json` beside this file is the",
          "source of truth (this page is generated from it). The browser applies recipes",
          "marked *automatic*. Builders can apply *manual* recipes with today's format/tools.",
          "A *planned* recipe has no supported package field or tool yet: skip it, report it",
          "as unavailable when relevant, and never invent a field. Planned recipes do not",
          "block validation, signing, or completion.", ""]
    areas = []
    for x in R:
        if x["area"] not in areas:
            areas.append(x["area"])
    for a in areas:
        md += ["## " + a.capitalize(), ""]
        for x in R:
            if x["area"] != a:
                continue
            md += ["### %s  (`%s`, kit: %s)" % (x["title"], x["id"], x["kit"]), "", x["purpose"], "", "**When:** " + x["when"], ""]
            md += ["%d. %s" % (i + 1, s) for i, s in enumerate(x["steps"])]
            md.append("")
            if x["defaults"]:
                md += ["**Defaults:** " + ", ".join("`%s` = %s" % (k, json.dumps(v)) for k, v in x["defaults"].items()), ""]
            if x["check"]:
                md += ["**Check:** " + x["check"], ""]
            if x["cost"]:
                md += ["**Cost:** " + x["cost"], ""]
            if x.get("tool"):
                md += ["**Kit tool:** `%s`" % x["tool"], ""]
            md += ["**From:** " + x["source"], ""]
    open("kit/recipes/TECHNIQUES.md", "w", encoding="utf-8", newline="\n").write("\n".join(md))

    lv = ["# iamar recipes by layer and build tier", "",
          "Generated from `techniques.json` (`layer`, `tier`). **Engineering** recipes apply to every world",
          "whatever its look; **style** recipes depend on the art direction (see `kit/style`). Tier is the",
          "lowest build tier that can apply the recipe (0 Blender and kit tools, 1 plus a generation",
          "service, 2 plus a local GPU).", ""]
    for lay, head in (("engineering", "Engineering (apply to every world)"), ("style", "Style (depend on the art direction)")):
        lv += ["## " + head, "", "| Recipe | Id | Area | Kit | Tier |", "|---|---|---|---|---|"]
        for x in R:
            if x["layer"] == lay:
                lv.append("| %s | `%s` | %s | %s | %d |" % (x["title"], x["id"], x["area"], x["kit"], x["tier"]))
        lv.append("")
    open("kit/recipes/TECHNIQUES_BY_LAYER.md", "w", encoding="utf-8", newline="\n").write("\n".join(lv))
    print(len(R), "recipes")


if __name__ == "__main__":
    main()
