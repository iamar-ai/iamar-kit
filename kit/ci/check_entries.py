#!/usr/bin/env python3
"""CI check: fail when a script, catalogue asset or recipe is added without its entry.

  python3 kit/ci/check_entries.py [--root DIR] [--json]
  python3 kit/ci/check_entries.py --suggest     print scripts_added.json stub rows for uncovered scripts

Rules (each failure names the file to edit):
  1. Every tracked script (.py .gd .sh .mjs .cmd .js .ts) must have a row in kit/inventory/scripts.json
     (rows or pattern members, repo iamar-kit) or in kit/inventory/scripts_added.json (scripts added
     after the harvest pin; same row format, disposition from the same list).
  2. Every tracked glTF/GLB under kit/catalog/assets/ must be referenced by an entry of kit/catalog/catalog.json.
  3. Every recipe in kit/recipes/techniques.json has id, source (evidence), check (not for kit=automatic), layer and tier, and
     every recipe id appears in kit/recipes/TECHNIQUES.md (the generated book is current).
  4. Every added script row has a valid disposition; a "ship" script needs a test or doc mention
     (its basename appears in some other tracked kit/tests/** or docs/** or *.md file).
Files come from `git ls-files` (committed or staged), so a seeded miss must be `git add`ed to count;
with --root outside a git repo the working tree is walked instead. Python 3.8+, stdlib only.
Exit 0 = pass, 1 = failures.
"""
import argparse, json, os, re, subprocess, sys

EXT = (".py", ".gd", ".sh", ".mjs", ".cmd", ".js", ".ts")
DISP = re.compile(r"^(ship|ship after wrapping|document only|internal|dropped \(.+\))$")
SKIP_PARTS = ("__pycache__/", "node_modules/")

def tracked(root):
    try:
        out = subprocess.check_output(["git", "-C", root, "ls-files", "-co", "--exclude-standard"], text=True, stderr=subprocess.DEVNULL)
        return [f for f in out.split("\n") if f and os.path.exists(os.path.join(root, f))]
    except (subprocess.CalledProcessError, FileNotFoundError):
        res = []
        for d, _, fs in os.walk(root):
            for f in fs:
                res.append(os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/"))
        return res

def load(root, rel, default):
    p = os.path.join(root, rel)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

def covered_scripts(root):
    s = load(root, "kit/inventory/scripts.json", {"rows": [], "patterns": []})
    cov = {r["path"]: r.get("disposition", "") for r in s["rows"] if r.get("repo") == "iamar-kit"}
    for p in s.get("patterns", []):
        if p.get("repo") == "iamar-kit":
            for m in p["members"]:
                cov[m] = p.get("disposition", "")
    added = {}
    for rel in ("kit/inventory/scripts_added.json", "kit/inventory/scripts_added_more.json"):
        for r in load(root, rel, {"rows": []})["rows"]:
            added[r["path"]] = r
    for k, r in added.items():
        cov[k] = r.get("disposition", "")
    return cov, added

def check(root):
    errs, files = [], tracked(root)
    files = [f for f in files if not any(x in f for x in SKIP_PARTS)]
    fileset = set(files)
    cov, added = covered_scripts(root)
    scripts = [f for f in files if f.endswith(EXT)]
    for f in scripts:
        if f not in cov:
            errs.append(f"script without inventory row: {f} (add it to kit/inventory/scripts_added.json)")
    for k, r in added.items():
        if k not in fileset:
            errs.append(f"scripts_added.json row for missing file: {k}")
        if not DISP.match(r.get("disposition", "")):
            errs.append(f"scripts_added.json bad disposition for {k}: {r.get('disposition')!r}")
        for fld in ("purpose", "disposition"):
            if not r.get(fld):
                errs.append(f"scripts_added.json row {k} lacks {fld}")
    docs = [f for f in files if f.endswith(".md") or "/tests/" in f]
    text_cache = {}
    def mentioned(base, own):
        for d in docs:
            if d == own:
                continue
            if d not in text_cache:
                try: text_cache[d] = open(os.path.join(root, d), encoding="utf-8", errors="ignore").read()
                except OSError: text_cache[d] = ""
            if base in text_cache[d]:
                return True
        return False
    for k, r in added.items():
        if r.get("disposition") == "ship" and k in fileset and not mentioned(os.path.basename(k), k):
            errs.append(f"ship script {k} has no test or doc mention (name it in kit/tests/** or a .md)")
    cat = load(root, "kit/catalog/catalog.json", None)
    if cat is not None:
        blob = json.dumps(cat)
        for f in files:
            if f.startswith("kit/catalog/assets/") and f.endswith((".glb", ".gltf")):
                if f not in blob and f[len("kit/catalog/"):] not in blob:
                    errs.append(f"catalogue asset without catalog.json entry: {f} (python3 kit/catalog/catalog.py build)")
    rec = load(root, "kit/recipes/techniques.json", None)
    if rec is not None:
        book = ""
        bp = os.path.join(root, "kit/recipes/TECHNIQUES.md")
        if os.path.exists(bp):
            book = open(bp, encoding="utf-8", errors="ignore").read()
        for r in rec["recipes"]:
            rid = r.get("id", "?")
            for fld in ("id", "source", "check", "layer", "tier"):
                if fld == "check" and r.get("kit") == "automatic":
                    continue  # the engine does it; the builder has no command to run
                if r.get(fld) in (None, "", []):
                    errs.append(f"recipe {rid} lacks {fld}")
            if rid not in book:
                errs.append(f"recipe {rid} missing from TECHNIQUES.md (python3 kit/recipes/make_recipes.py)")
    return errs, scripts

def suggest(root):
    cov, _ = covered_scripts(root)
    rows = []
    for f in sorted(tracked(root)):
        if f.endswith(EXT) and f not in cov and not any(x in f for x in SKIP_PARTS):
            t = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read(2000)
            doc = [l.strip().lstrip("#/*\"' ").rstrip("\"'* ") for l in t.splitlines()
                   if l.strip().startswith(("#", "//", '"""', "'''", "/*")) and not l.startswith("#!")]
            doc = [d for d in doc if len(d) > 12]
            purpose = doc[0] if doc else os.path.basename(f)
            disp = "internal" if ("/tests/" in f or ".test." in f or "_test" in f) else "ship"
            rows.append({"repo": "iamar-kit", "path": f, "purpose": purpose[:160], "disposition": disp})
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    ap.add_argument("--suggest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.suggest:
        print(json.dumps({"rows": suggest(a.root)}, indent=1)); return 0
    errs, scripts = check(a.root)
    if a.json:
        print(json.dumps({"scripts": len(scripts), "errors": errs}, indent=1))
    else:
        print(f"CI entries: scripts={len(scripts)} errors={len(errs)}")
        for e in errs[:60]: print("  FAIL", e)
    return 1 if errs else 0

if __name__ == "__main__":
    sys.exit(main())
