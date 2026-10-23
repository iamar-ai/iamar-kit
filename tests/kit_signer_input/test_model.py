"""Inert source/model checks only; no GDScript, signing, keys or packages run."""
from pathlib import Path
import itertools
import json
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/kit/world_sign.gd"
# Reuse the already-reviewed pure test model, not production implementation.
SIGNER_TEXT = runpy.run_path(str(ROOT / "tests/kit_signer_text/test_model.py"))
SET_SIGNER = SIGNER_TEXT["set_signer_model"]
FUNCTION = SIGNER_TEXT["function"]
KEY_ID = "rsa:" + "a" * 32  # Identifier-shaped inert text, not key material.
DOWNSTREAM_SENTINEL = 73  # A spy return value, never a claimed pack success.


def signer_json_model(name):
    # String/dictionary-only JSON model. This does not qualify Godot's encoder.
    return json.dumps({"name": name, "key_id": KEY_ID}, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"))


def legacy_signer_json_model(name):
    return signer_json_model(name).replace('\":', '\": ').replace(',\"', ', \"')


def absolute_path_spy(path, calls):
    # Records the _abs boundary; does not implement platform path normalization.
    # In particular an explicitly supplied empty path is not a missing operand:
    # KitLoop.absolute_path resolves it relative to the working directory.
    calls.append(path)
    return "<absolute:" + path + ">"


def pack_refusal_model(key_path, signer, downstream_calls):
    # Mirrors only _pack's initial refusal, with an inert downstream spy.
    if key_path == "" or signer == "":
        return 2
    downstream_calls.append((key_path, signer))
    return DOWNSTREAM_SENTINEL


def pack_dispatch_model(args, calls, path_calls, downstream_calls):
    # _abs is a recording spy. No paths or keys are accessed and no downstream
    # return code is predicted: only the existing refusal and forwarding run.
    code = 2
    if len(args) >= 2 and args[0] == "pack":
        if len(args) >= 3:
            folder = absolute_path_spy(args[1], path_calls)
            out = absolute_path_spy(args[2], path_calls)
            key_path = absolute_path_spy(args[3], path_calls) if len(args) >= 4 else ""
            signer = args[4] if len(args) >= 5 else ""
            calls.append((folder, out, key_path, signer))
            code = pack_refusal_model(key_path, signer, downstream_calls)
    return code


class SignerInputTests(unittest.TestCase):
    def test_verified_legacy_quote_colon_corruption(self):
        for name in ['Alice":Bob', '\\":', 'A":B,"C', '":  kept']:
            with self.subTest(name=name):
                old = json.loads(legacy_signer_json_model(name))["name"]
                self.assertNotEqual(old.encode("utf-8"), name.encode("utf-8"))
                fixed = json.loads(signer_json_model(name))["name"]
                self.assertEqual(fixed.encode("utf-8"), name.encode("utf-8"))
        self.assertEqual(json.loads(legacy_signer_json_model('Alice":Bob'))["name"],
                         'Alice": Bob')
        # A comma before an escaped quote does not trigger the comma replacement.
        self.assertEqual(json.loads(legacy_signer_json_model('Alice,"Bob'))["name"],
                         'Alice,"Bob')

    def test_name_round_trip_matrix(self):
        fragments = ['A', ' ', ':', ',', '"', '\\', '}', '{', '\t', '\n', 'é', '世', '🦊']
        checked = 0
        for length in range(4):
            for pieces in itertools.product(fragments, repeat=length):
                name = "".join(pieces)
                decoded = json.loads(signer_json_model(name))
                self.assertEqual(set(decoded), {"name", "key_id"})
                self.assertEqual(decoded["name"].encode("utf-8"), name.encode("utf-8"))
                self.assertEqual(decoded["key_id"], KEY_ID)
                checked += 1
        self.assertEqual(checked, 2380)
        for name in ['  name  ', 'é', 'e\u0301', '\r\n\t\b\f\x00\x1f', 'x' * 4096]:
            self.assertEqual(json.loads(signer_json_model(name))["name"].encode("utf-8"),
                             name.encode("utf-8"))

    def test_pipeline_preserves_name_and_surrounding_manifest_bytes(self):
        # Existing/insertion paths are modeled by the frozen root-member scanner.
        fixtures = [
            ('{"signer": ', '{"name":"old"}', ', "x": 1.2300e+04}\r\n'),
            (' {\n"sig\\u006eer" \t: ', '{}', ',"x":{"signer":{"name":"decoy"}}}\n'),
        ]
        for name in ['A":B', '\\":', 'A,"B', '  世🦊e\u0301  ', '\t\n"{}']:
            replacement = signer_json_model(name)
            for prefix, old, suffix in fixtures:
                actual = SET_SIGNER(prefix + old + suffix, replacement)
                self.assertEqual(actual, prefix + replacement + suffix)
                self.assertEqual(json.loads(actual)["signer"]["name"], name)
                self.assertEqual(SET_SIGNER(actual, replacement), actual)
            for source in ['{}\n', '{"x":{"signer":{"name":"decoy"}}}\r\n']:
                actual = SET_SIGNER(source, replacement)
                self.assertEqual(json.loads(actual)["signer"]["name"], name)
                self.assertEqual(SET_SIGNER(actual, replacement), actual)

    def test_pack_missing_operands_do_not_index_out_of_bounds(self):
        # The legacy expression indexes a[2] after only the outer >= 2 guard.
        with self.assertRaises(IndexError):
            _ = ["pack", "folder"][2]
        for args in [[], ["pack"], ["pack", "folder"]]:
            calls, path_calls, downstream_calls = [], [], []
            self.assertEqual(pack_dispatch_model(args, calls, path_calls, downstream_calls), 2)
            self.assertEqual(calls, [])
            self.assertEqual(path_calls, [])
            self.assertEqual(downstream_calls, [])
        for args in [["pack", "folder", "out"], ["pack", "folder", "out", "key"]]:
            calls, path_calls, downstream_calls = [], [], []
            self.assertEqual(pack_dispatch_model(args, calls, path_calls, downstream_calls), 2)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][:2], ("<absolute:folder>", "<absolute:out>"))
            self.assertEqual(calls[0][3], "")
            self.assertEqual(calls[0][2], "<absolute:key>" if len(args) == 4 else "")
            self.assertEqual(path_calls, args[1:])
            self.assertEqual(downstream_calls, [])

    def test_pack_dispatch_normalizes_paths_and_forwards_name_unchanged(self):
        for name in ['Alice":Bob', '  世  ', '\\":']:
            for extras in [[], ["unchanged-extra"]]:
                calls, path_calls, downstream_calls = [], [], []
                args = ["pack", "folder path", "out path", "key path", name] + extras
                self.assertEqual(pack_dispatch_model(args, calls, path_calls, downstream_calls),
                                 DOWNSTREAM_SENTINEL)
                self.assertEqual(calls, [("<absolute:folder path>", "<absolute:out path>",
                                         "<absolute:key path>", name)])
                self.assertEqual(path_calls, ["folder path", "out path", "key path"])
                self.assertEqual(downstream_calls, [("<absolute:key path>", name)])
        for key, name in [("", "Name"), ("key", ""), ("", "")]:
            calls, path_calls, downstream_calls = [], [], []
            code = pack_dispatch_model(["pack", "folder", "out", key, name],
                                       calls, path_calls, downstream_calls)
            self.assertEqual(path_calls, ["folder", "out", key])
            self.assertEqual(calls[0][2], "<absolute:" + key + ">")
            if name == "":
                self.assertEqual(code, 2)
                self.assertEqual(downstream_calls, [])
            else:
                # Explicit CLI "" key is normalized before _pack: no claim
                # about whether the real downstream key load succeeds or fails.
                self.assertEqual(code, DOWNSTREAM_SENTINEL)
                self.assertEqual(downstream_calls, [("<absolute:>", name)])

    def test_direct_pack_refuses_empty_identity_before_downstream(self):
        # These are direct _pack arguments, not raw CLI arguments before _abs.
        for key, name in [("", "Name"), ("key", ""), ("", "")]:
            downstream_calls = []
            self.assertEqual(pack_refusal_model(key, name, downstream_calls), 2)
            self.assertEqual(downstream_calls, [])
        downstream_calls = []
        self.assertEqual(pack_refusal_model("key", "Name", downstream_calls), DOWNSTREAM_SENTINEL)
        self.assertEqual(downstream_calls, [("key", "Name")])

    def test_production_uses_unmodified_json_and_guarded_pack_dispatch(self):
        source = SOURCE.read_text()
        sign = FUNCTION(source, "_sign")
        self.assertIn('var out := _set_signer(text, JSON.stringify({"name": signer, "key_id": kid}))', sign)
        self.assertNotIn('.replace(', sign)
        self.assertIn('WorldSignature.make(src, key, signer)', sign)
        self.assertLess(sign.index('if out == "":'), sign.index('FileAccess.open(mpath, FileAccess.WRITE)'))
        self.assertLess(sign.index('f.store_string(out)'), sign.index('var src := WorldSource.open(folder)'))
        self.assertLess(sign.index('var src := WorldSource.open(folder)'),
                        sign.index('WorldSignature.make(src, key, signer)'))
        self.assertIn('return KitLoop.absolute_path(p)', FUNCTION(source, "_abs"))
        init = FUNCTION(source, "_init")
        self.assertIn('if a.size() >= 2:', init)
        self.assertIn('"pack": code = _pack(_abs(a[1]), _abs(a[2]), _abs(a[3]) if a.size() >= 4 else "", a[4] if a.size() >= 5 else "") if a.size() >= 3 else 2', init)
        self.assertIn('if code == 2:', init)
        self.assertIn('quit(code)', init)
        pack = FUNCTION(source, "_pack")
        self.assertLess(pack.index('if key_path == "" or signer == "":'), pack.index('_load_key(key_path)'))
        self.assertIn('WorldPieces.pack(folder, out, key, signer)', pack)
        self.assertIn('return _verify(out)', pack)


if __name__ == "__main__":
    unittest.main(verbosity=2)
