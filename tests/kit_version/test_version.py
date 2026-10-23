import json, pathlib, subprocess, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "kit" / "version" / "version.py"


def run(*a):
    p = subprocess.run([sys.executable, str(TOOL), *a], capture_output=True, text=True)
    return p.returncode, p.stdout


class KitVersion(unittest.TestCase):
    def test_version_json_matches_version_file(self):
        d = json.load(open(ROOT / "kit" / "VERSION.json"))
        self.assertEqual(d["kit_version"], (ROOT / "VERSION").read_text().strip())

    def test_plain_report(self):
        code, out = run("--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["kit_version"], (ROOT / "VERSION").read_text().strip())

    def test_check_current_and_newer(self):
        v = (ROOT / "VERSION").read_text().strip()
        code, out = run("--check", "--latest", v, "--json")
        self.assertEqual(code, 0); self.assertTrue(json.loads(out)["current"])
        code, out = run("--check", "--latest", "99.0.0", "--json")
        self.assertEqual(code, 1); self.assertFalse(json.loads(out)["current"])

    def test_bad_latest_is_exit_2(self):
        code, out = run("--check", "--latest", "/nonexistent", "--json")
        self.assertEqual(code, 2); self.assertIn("check_error", json.loads(out))


if __name__ == "__main__":
    unittest.main()
