#!/usr/bin/env python3
"""kit/ci/pre-push runs the public-export scan: a clone of this checkout passes, and the same clone
with a host name committed into an evidence doc is refused (an internal task)."""
import os, shutil, subprocess, tempfile, unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

def git(root, *a):
    subprocess.run(["git", "-C", root, *a], check=True, capture_output=True)

def hook(root, **env):
    p = subprocess.run(["sh", os.path.join(root, "kit", "ci", "pre-push")], cwd=root, capture_output=True,
                       text=True, env={**os.environ, **env})
    return p.returncode, p.stdout + p.stderr

class PrePushExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp(prefix="kit_prepush_")
        subprocess.run(["git", "clone", "-q", "--no-hardlinks", ROOT, cls.d], check=True, capture_output=True)
        # test this checkout's hook and exporter, even when they are not committed yet
        for rel in ("kit/ci/pre-push", "tools/export_public.py", "kit/export/rules.json"):
            shutil.copy(os.path.join(ROOT, rel), os.path.join(cls.d, rel))
        git(cls.d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "hook under test", "--allow-empty")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, True)

    def test_1_clean_head_passes(self):
        rc, out = hook(self.d)
        self.assertEqual(rc, 0, out)
        self.assertIn("export scan OK", out)

    def test_2_host_name_refused(self):
        p = os.path.join(self.d, "docs", "evidence", "prepush_seed", "SHOTS.md")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        host = "end" + "sley"  # split so this file itself passes the scan
        open(p, "w").write(f"Rendered offscreen on {host}, 2026-10-21.\n")
        git(self.d, "add", p)
        git(self.d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed host name")
        rc, out = hook(self.d)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("docs/evidence/prepush_seed/SHOTS.md", out)
        self.assertIn("export scan failed", out)
        rc, out = hook(self.d, KIT_PREPUSH_EXPORT="0")
        self.assertEqual(rc, 0, out)
    def test_3_exporter_error_is_shown(self):
        d = tempfile.mkdtemp(prefix="kit_prepush_bad_")
        try:
            subprocess.run(["git", "clone", "-q", "--no-hardlinks", self.d, d], check=True, capture_output=True)
            open(os.path.join(d, "kit", "export", "rules.json"), "w").write("{not json\n")
            git(d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "broken rules")
            rc, out = hook(d)
            self.assertNotEqual(rc, 0, out)
            self.assertIn("export scan failed", out)
            self.assertIn("cannot read rules", out)  # the exporter's own error reaches the user, not just the refusal
        finally:
            shutil.rmtree(d, True)

if __name__ == "__main__":
    unittest.main()
