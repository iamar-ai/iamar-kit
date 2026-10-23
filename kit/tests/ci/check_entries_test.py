#!/usr/bin/env python3
"""Seeded-miss test for kit/ci/check_entries.py: the real tree passes and each seeded miss fails."""
import json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CHECK = os.path.join(ROOT, "kit", "ci", "check_entries.py")

def run(root):
    p = subprocess.run([sys.executable, CHECK, "--root", root, "--json"], capture_output=True, text=True)
    return p.returncode, json.loads(p.stdout)["errors"]

def git(root, *a):
    subprocess.run(["git", "-C", root, *a], check=True, capture_output=True)

class Seeded(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="ckci_")
        git(self.d, "init", "-q")
        for rel in ("kit/inventory/scripts.json", "kit/inventory/scripts_added.json", "kit/catalog/catalog.json",
                    "kit/recipes/techniques.json", "kit/recipes/TECHNIQUES.md"):
            os.makedirs(os.path.join(self.d, os.path.dirname(rel)), exist_ok=True)
            shutil.copy(os.path.join(ROOT, rel), os.path.join(self.d, rel))
        s = json.load(open(os.path.join(self.d, "kit/inventory/scripts.json")))
        s["rows"] = [r for r in s["rows"] if r["repo"] == "iamar-kit"]
        for p in s["patterns"]: p["members"] = [m for m in p["members"]] if p["repo"] == "iamar-kit" else []
        # a clean mini tree: only files the inventory knows are not created, so rows for missing files are tolerated
        json.dump({"rows": [], "patterns": []}, open(os.path.join(self.d, "kit/inventory/scripts.json"), "w"))
        json.dump({"rows": []}, open(os.path.join(self.d, "kit/inventory/scripts_added.json"), "w"))
        self.addCleanup(shutil.rmtree, self.d, True)

    def put(self, rel, text="# a seeded kit script for the check\n"):
        p = os.path.join(self.d, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(text); git(self.d, "add", rel)

    def test_clean_tree_passes(self):
        rc, errs = run(self.d); self.assertEqual((rc, errs), (0, []))

    def test_new_script_without_row_fails(self):
        self.put("kit/blender/new_tool.py")
        rc, errs = run(self.d); self.assertEqual(rc, 1); self.assertTrue(any("new_tool.py" in e for e in errs))

    def test_row_fixes_it(self):
        self.put("kit/blender/new_tool.py")
        json.dump({"rows": [{"repo": "iamar-kit", "path": "kit/blender/new_tool.py", "purpose": "x tool", "disposition": "internal"}]},
                  open(os.path.join(self.d, "kit/inventory/scripts_added.json"), "w"))
        self.assertEqual(run(self.d)[0], 0)

    def test_ship_without_test_or_doc_fails(self):
        self.put("kit/blender/new_tool.py")
        json.dump({"rows": [{"repo": "iamar-kit", "path": "kit/blender/new_tool.py", "purpose": "x tool", "disposition": "ship"}]},
                  open(os.path.join(self.d, "kit/inventory/scripts_added.json"), "w"))
        rc, errs = run(self.d); self.assertEqual(rc, 1); self.assertTrue(any("no test or doc" in e for e in errs))
        self.put("kit/blender/README.md", "new_tool.py makes things\n")
        self.assertEqual(run(self.d)[0], 0)

    def test_catalogue_asset_without_entry_fails(self):
        self.put("kit/catalog/assets/props/orphan_crate.glb", "glTF")
        rc, errs = run(self.d); self.assertEqual(rc, 1); self.assertTrue(any("orphan_crate.glb" in e for e in errs))

    def test_recipe_without_evidence_fails(self):
        p = os.path.join(self.d, "kit/recipes/techniques.json"); t = json.load(open(p))
        t["recipes"][0]["source"] = ""; json.dump(t, open(p, "w"))
        rc, errs = run(self.d); self.assertEqual(rc, 1); self.assertTrue(any("lacks source" in e for e in errs))

    def test_recipe_missing_from_book_fails(self):
        p = os.path.join(self.d, "kit/recipes/techniques.json"); t = json.load(open(p))
        t["recipes"].append(dict(t["recipes"][0], id="zz_new_unlisted_recipe")); json.dump(t, open(p, "w"))
        rc, errs = run(self.d); self.assertEqual(rc, 1); self.assertTrue(any("zz_new_unlisted_recipe" in e for e in errs))

class RealTree(unittest.TestCase):
    def test_repo_passes(self):
        rc, errs = run(ROOT); self.assertEqual(errs, []); self.assertEqual(rc, 0)

if __name__ == "__main__":
    unittest.main()
