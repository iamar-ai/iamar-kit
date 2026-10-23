"""Inert source/model regression. No Godot, keys, signing, or package execution."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PREIMAGE = ROOT / "tests/kit_key_exclusion/fixtures/world_sign.b2707865.gd.txt"
SOURCE = ROOT / "scripts/kit/world_sign.gd"

def verify_function(source):
    return source.split("func _verify(p: String) -> int:\n", 1)[1].split("\n\treturn 0\n", 1)[0] + "\n\treturn 0\n"

def package_ok_model(case, require_signature):
    # Model of browser 935abc39 WorldPackage unsigned admission only.
    # Does not implement cryptography, schema, file, or native admission.
    return case["otherwise_valid"] and case["status"] != "invalid" and (
        case["status"] != "unsigned" or not require_signature
    )

class VerifyContractTests(unittest.TestCase):
    def test_exact_one_line_change_in_verify(self):
        old = verify_function(PREIMAGE.read_text())
        new = verify_function(SOURCE.read_text())
        before = 'var pkg := WorldPackage.open(p)\n'
        after = 'var pkg := WorldPackage.open(p, {"require_signature": true})\n'
        self.assertEqual(old.count(before), 1)
        self.assertEqual(new, old.replace(before, after))

    def test_explicit_signature_not_trust_gate(self):
        body = verify_function(SOURCE.read_text())
        self.assertIn('WorldPackage.open(p, {"require_signature": true})', body)
        self.assertNotIn("require_trusted", body)
        self.assertIn('print("STATUS ", pkg.signature.get("status", "?"))', body)
        self.assertIn('if not pkg.ok:\n\t\treturn 1', body)
        self.assertIn('print("OK")\n\treturn 0', body)

    def test_deterministic_admission_cases(self):
        cases = json.loads((Path(__file__).with_name("fixtures.json")).read_text())
        for case in cases:
            with self.subTest(case=case["name"]):
                rc = 0 if package_ok_model(case, True) else 1
                self.assertEqual(rc, case["expected_rc"])
                if case["status"] == "unsigned" and case["otherwise_valid"]:
                    self.assertTrue(package_ok_model(case, False))

    def test_existing_callers_preserved(self):
        text = SOURCE.read_text()
        self.assertIn('"verify": code = _verify(_abs(a[1]))', text)
        self.assertIn('if _verify(folder) != 0:', text)
        self.assertIn('return _verify(out)', text)

if __name__ == "__main__":
    unittest.main(verbosity=2)

