"""Read-only source assertions; authored, not run. No Godot or key generation."""
from pathlib import Path
import unittest


class PrivateKeygenContract(unittest.TestCase):
    def test_windows_launcher_does_not_provision_parent(self):
        root = Path(__file__).resolve().parents[2]
        launcher = (root / "kit/iamar-world.cmd").read_text()
        keygen = launcher.split("\n:keygen\n", 1)[1].split("\n:findblender\n", 1)[0]
        self.assertNotIn("mkdir", keygen.lower())
        self.assertIn('set "K=%APPDATA%\\iamar\\signing\\%K%.key"', keygen)
        self.assertIn('world_sign.gd%E% keygen "%K%"', keygen)

    def test_no_unsafe_fallback(self):
        root = Path(__file__).resolve().parents[2]
        text = (root / "scripts/kit/world_sign.gd").read_text()
        keygen = text.split("func _keygen(p: String)", 1)[1].split("func _keyid(", 1)[0]
        for forbidden in ("k.save(p)", "FilePerms.private_file", "FileAccess.WRITE", "make_dir_recursive"):
            self.assertNotIn(forbidden, keygen)
        self.assertLess(keygen.index('call("begin", p)'), keygen.index("generate_rsa(2048)"))
        self.assertLess(keygen.index('call("commit")'), keygen.index('print("KEY ", p)'))
        self.assertIn('call("get_api_version") != 1', keygen)
        self.assertIn('committed.get("private_published", false)', keygen)
        self.assertIn('committed.get("public_published", false)', keygen)
        self.assertIn('committed.get("uncertain", true)', keygen)


if __name__ == "__main__":
    unittest.main()
