"""Source assertions: sign/pack/keygen/keyid resolve a bare key name the way the launchers do."""
from pathlib import Path
import unittest


class KeyNameContract(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2]
        self.text = (root / "scripts/kit/world_sign.gd").read_text()

    def test_every_key_argument_goes_through_key_arg(self):
        init = self.text.split("func _init()", 1)[1].split("func _load_key", 1)[0]
        for call in ("_keygen(key_arg(a[1]))", "_sign(_abs(a[1]), key_arg(a[2])",
                     "key_arg(a[3]) if a.size() >= 4", "_keyid(key_arg(a[1]))"):
            self.assertIn(call, init)

    def test_signing_dir_matches_the_launchers(self):
        fn = self.text.split("static func signing_dir()", 1)[1].split("static func key_arg", 1)[0]
        self.assertIn('OS.get_environment("APPDATA")', fn)
        self.assertIn('"/iamar/signing"', fn)
        self.assertIn("XDG_CONFIG_HOME", fn)

    def test_bare_name_rule(self):
        fn = self.text.split("static func key_arg", 1)[1].split("func _init", 1)[0]
        for part in ('contains("/")', 'contains("\\\\")', 'ends_with(".key")'):
            self.assertIn(part, fn)

    def test_error_names_path_and_keygen(self):
        self.assertIn("run keygen <name> first", self.text)
        self.assertIn("selected signing key for package preflight: \", key_path", self.text)


if __name__ == "__main__":
    unittest.main()
