"""Inert source/model regression; never imports or executes repository code."""
from pathlib import Path
import hashlib
import itertools
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/kit/world_sign.gd"
REPLACEMENT = '{"name":"New } \\"Signer\\\\","key_id":"rsa:' + "a" * 32 + '"}'

def parse_or_none(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None

def skip_space(text, start):
    while start < len(text) and text[start] in " \t\r\n":
        start += 1
    return start

def set_signer_model(text, signer_json, parse=parse_or_none):
    # Mirrors the reviewed pure GDScript helper, not its I/O/signing callers.
    manifest = parse(text)
    if not isinstance(manifest, dict) or not isinstance(parse(signer_json), dict):
        return ""
    depth = 0
    string_start = -1
    escaped = False
    value_start = -1
    value_end = -1
    root_end = -1
    for i, c in enumerate(text):
        if string_start >= 0:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                if depth == 1:
                    colon = skip_space(text, i + 1)
                    if (colon < len(text) and text[colon] == ":"
                            and parse_or_none(text[string_start:i + 1]) == "signer"):
                        if value_start >= 0:
                            return ""
                        value_start = skip_space(text, colon + 1)
                        if value_start >= len(text) or text[value_start] != "{":
                            return ""
                string_start = -1
            continue
        if ord(c) < 32 and c not in "\t\r\n":
            return ""
        if c == '"':
            string_start = i
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if value_start >= 0 and value_end < 0 and depth == 1:
                value_end = i + 1
            elif depth == 0:
                root_end = i
    if value_start >= 0:
        if value_end < value_start:
            return ""
        return text[:value_start] + signer_json + text[value_end:]
    if root_end < 0:
        return ""
    insert_at = root_end
    while insert_at > 0 and text[insert_at - 1] in " \t\r\n":
        insert_at -= 1
    comma = "" if not manifest else ","
    if insert_at > 0 and text[insert_at - 1] == ",":
        comma = ""
    return text[:insert_at] + comma + '\n  "signer": ' + signer_json + text[insert_at:]

def oracle(text, signer_json):
    # Independent span oracle uses JSONDecoder to consume each root key/value.
    # It does not share the depth/string/escape scanner with the model.
    if not isinstance(parse_or_none(text), dict) or not isinstance(parse_or_none(signer_json), dict):
        return ""
    decoder = json.JSONDecoder()
    cursor = skip_space(text, 0) + 1
    members = []
    found = None
    while True:
        cursor = skip_space(text, cursor)
        if text[cursor] == "}":
            root_end = cursor
            break
        key, cursor = decoder.raw_decode(text, cursor)
        cursor = skip_space(text, cursor)
        assert text[cursor] == ":"
        start = skip_space(text, cursor + 1)
        value, end = decoder.raw_decode(text, start)
        members.append(key)
        if key == "signer":
            if found is not None or not isinstance(value, dict):
                return ""
            found = (start, end)
        cursor = skip_space(text, end)
        if text[cursor] == ",":
            cursor += 1
    if found is not None:
        return text[:found[0]] + signer_json + text[found[1]:]
    insert_at = root_end
    while insert_at > 0 and text[insert_at - 1] in " \t\r\n":
        insert_at -= 1
    return text[:insert_at] + ("," if members else "") + '\n  "signer": ' + signer_json + text[insert_at:]

def legacy_model(text, signer_json):
    pattern = r'"signer"\s*:\s*\{[^}]*\}'
    if re.search(pattern, text):
        return re.sub(pattern, lambda _: '"signer": ' + signer_json, text, count=1)
    end = text.rstrip(" \n\r\t")
    if not end.endswith("}"):
        return ""
    return end[:-1].rstrip(" \n\r\t") + ',\n  "signer": ' + signer_json + "\n}\n"

def function(source, name):
    match = re.search(r"^(?:static )?func " + re.escape(name) + r"\(", source, re.M)
    assert match, name
    rest = source[match.start():]
    end = re.search(r"^(?:static )?func ", rest[1:], re.M)
    return rest[:end.start() + 1] if end else rest

class SignerTextTests(unittest.TestCase):
    def check_document(self, text):
        actual = set_signer_model(text, REPLACEMENT)
        self.assertEqual(actual, oracle(text, REPLACEMENT))
        if actual:
            result = json.loads(actual)
            self.assertEqual(result["signer"], json.loads(REPLACEMENT))
            before = json.loads(text)
            before.pop("signer", None)
            result.pop("signer")
            self.assertEqual(result, before)
            self.assertEqual(set_signer_model(actual, REPLACEMENT), actual)
            # Deterministic exact manifest input for the unchanged signing path.
            self.assertEqual(hashlib.sha256(actual.encode()).digest(),
                             hashlib.sha256(set_signer_model(text, REPLACEMENT).encode()).digest())

    def test_existing_claim_preserves_exact_outer_bytes(self):
        old = '{"name": "Old } \\"Signer\\\\", "key_id": "rsa:' + "b" * 32 + '", "x-meta": {"a": [1, {"signer": {}}]}}'
        prefix = ' \t{\r\n "version": "1.0.0", "x-number": 1.2300e+04,\r\n "signer" \t:\n '
        suffix = ',\r\n "name": "世界", "x-space": "  kept  "\r\n}\r\n\t '
        self.assertEqual(set_signer_model(prefix + old + suffix, REPLACEMENT), prefix + REPLACEMENT + suffix)
        self.check_document(prefix + old + suffix)

    def test_nested_decoys_do_not_replace_or_hide_root(self):
        for decoy in [
            {"signer": {}},
            {"signer": {"name": "decoy}"}},
            [{"signer": {"name": "decoy"}}],
            {"deeper": [{"signer": {"x-nested": {"k": "}"}}}]},
            '"signer": {"name": "quoted decoy"}',
        ]:
            for root in [None, {"name": "owner", "key_id": "rsa:" + "b" * 32}]:
                doc = {"x-decoy": decoy, "description": "signer"}
                if root is not None:
                    doc["signer"] = root
                self.check_document(json.dumps(doc, ensure_ascii=False, indent=2))

    def test_escaped_root_member_is_replaced_in_place(self):
        text = '{"sig\\u006eer"\t : {"name": "old"}, "x-note": "kept"}\n'
        expected = '{"sig\\u006eer"\t : ' + REPLACEMENT + ', "x-note": "kept"}\n'
        self.assertEqual(set_signer_model(text, REPLACEMENT), expected)
        self.check_document(text)

    def test_duplicate_root_claims_are_refused(self):
        for key in ['"signer"', '"sig\\u006eer"']:
            for values in [({}, {}), ({}, None), (None, {}), ({}, {"name": "}"} )]:
                text = '{"signer": ' + json.dumps(values[0]) + ', ' + key + ': ' + json.dumps(values[1]) + "}"
                self.assertEqual(set_signer_model(text, REPLACEMENT), "")
                self.assertEqual(oracle(text, REPLACEMENT), "")

    def test_malformed_and_nonobject_inputs_are_refused(self):
        for text in ["", "{", '{"x": }', '{"signer": {"name": "oops}}', '[]', 'null',
                     '"text"', '{"signer": {}} trailing', '{"x": "\\q"}']:
            self.assertEqual(set_signer_model(text, REPLACEMENT), "")
        for value in [None, [], "str", 1, True]:
            self.assertEqual(set_signer_model(json.dumps({"signer": value}), REPLACEMENT), "")
        for replacement in ["", "{", "null", "[]", "1", '"str"']:
            self.assertEqual(set_signer_model('{"name":"world"}', replacement), "")

    def test_insertion_preserves_source_whitespace_and_empty_objects(self):
        for text in ["{}", "{  }", "\t{\r\n}\n", '{"name":"world"}',
                     '{"name":"world" \t\r\n}\r\n',
                     '{ "x-decoy": {"signer": {}} }']:
            self.check_document(text)
        self.assertEqual(set_signer_model('{"name":"world" \t\r\n}\r\n', REPLACEMENT),
                         '{"name":"world",\n  "signer": ' + REPLACEMENT + ' \t\r\n}\r\n')

    def test_escape_depth_and_order_matrix(self):
        names = ["plain", "}", "{", 'quote"', "back\\slash", 'even\\\\"}', 'odd\\\"}',
                 "世界🙂", "\n\r\t", '"signer": {}', "\\u007d"]
        whitespace = [None, 0, 2, "\t"]
        orders = list(itertools.permutations(["x-before", "signer", "x-after"]))
        for name, indent, order in itertools.product(names, whitespace, orders):
            entries = {
                "x-before": {"signer": {"name": name}, "array": [1, "}", {"a": "{\""}]},
                "signer": {"name": name, "key_id": "rsa:" + "b" * 32,
                           "x-extension": {"deep": [{"signer": {"name": name}}]}},
                "x-after": [name, {"signer": {"x-array": [[]]}}],
            }
            with self.subTest(name=name, indent=indent, order=order):
                self.check_document(json.dumps({k: entries[k] for k in order}, ensure_ascii=False, indent=indent))

    def test_simulated_godot_trailing_comma_acceptance(self):
        # Godot documents accepting trailing commas; Python rejects them.
        # Supply the known parsed object only for each exact fixture input.
        # This is not an implementation or execution of Godot's parser.
        for prefix, suffix in [('{"name":"world",', '}'),
                               (' {"x-decoy":{"signer":{}},', ' \t\r\n}\r\n')]:
            text = prefix + suffix
            def parse(value):
                return json.loads(prefix[:-1] + suffix) if value == text else parse_or_none(value)
            expected = prefix + '\n  "signer": ' + REPLACEMENT + suffix
            actual = set_signer_model(text, REPLACEMENT, parse)
            self.assertEqual(actual, expected)
            self.assertEqual(json.loads(actual)["signer"], json.loads(REPLACEMENT))
            self.assertEqual(set_signer_model(actual, REPLACEMENT), actual)

    def test_simulated_engine_control_whitespace_is_refused(self):
        # The documented/versioned engine tokenizer may accept non-JSON
        # control whitespace or terminate at NUL. Do not emulate that parser;
        # simulate admission of exact fixtures and assert fail-closed scanning.
        for code in set(range(32)) - {9, 10, 13}:
            control = chr(code)
            for text, parsed in [
                ('{"signer"' + control + ':{"name":"old"}}', {"signer": {"name": "old"}}),
                ('{"signer":{},"signer"' + control + ':{}}', {"signer": {}}),
                (control + '{"name":"world"}', {"name": "world"}),
                ('{"name":"world"}' + control, {"name": "world"}),
                ('{"name":"world"}' + control + '{"signer":{}}', {"name": "world"}),
            ]:
                def parse(value):
                    return parsed if value == text else parse_or_none(value)
                with self.subTest(code=code, text=text):
                    self.assertEqual(set_signer_model(text, REPLACEMENT, parse), "")

    def test_legacy_defects_are_reproduced_without_signing(self):
        text = '{"name":"world","signer":{"name":"A } B","key_id":"old"}}'
        with self.assertRaises(json.JSONDecodeError):
            json.loads(legacy_model(text, REPLACEMENT))
        text = '{"x-extension":{"signer":{"name":"decoy"}},"signer":{"name":"owner"}}'
        actual = json.loads(legacy_model(text, REPLACEMENT))
        self.assertEqual(actual["signer"]["name"], "owner")
        self.assertNotEqual(actual["x-extension"]["signer"]["name"], "decoy")
        self.assertEqual(json.loads(set_signer_model(text, REPLACEMENT))["signer"], json.loads(REPLACEMENT))
        with self.assertRaises(json.JSONDecodeError):
            json.loads(legacy_model("{}", REPLACEMENT))

    def test_source_contract(self):
        source = SOURCE.read_text()
        helper = function(source, "_set_signer")
        for expected in [
            "var manifest: Variant = JSON.parse_string(text)",
            "not manifest is Dictionary",
            "not JSON.parse_string(signer_json) is Dictionary",
            "if string_start >= 0:",
            "if escaped:",
            'if c.unicode_at(0) < 32 and not (c in ["\\t", "\\r", "\\n"]):',
            'elif c == "\\\\":',
            "if depth == 1:",
            "var colon := _skip_json_space(text, i + 1)",
            'JSON.parse_string(text.substr(string_start, i - string_start + 1)) == "signer"',
            "if value_start >= 0:\n\t\t\t\t\t\t\treturn \"\"",
            'text[value_start] != "{"',
            'elif c == "{" or c == "[":',
            'elif c == "}" or c == "]":',
            "value_start >= 0 and value_end < 0 and depth == 1",
            "text.substr(0, value_start) + signer_json + text.substr(value_end)",
            'var comma := "" if manifest.is_empty() else ","',
            'if insert_at > 0 and text[insert_at - 1] == ",":\n\t\tcomma = ""',
            "text.substr(insert_at)",
        ]:
            self.assertIn(expected, helper)
        for forbidden in ["RegEx", "JSON.stringify", "FileAccess", "Crypto", "OS.", "WorldPieces"]:
            self.assertNotIn(forbidden, helper)
        self.assertIn("start < text.length()", function(source, "_skip_json_space"))
        caller = function(source, "_sign")
        self.assertLess(caller.index('if out == "":'), caller.index("FileAccess.open(mpath, FileAccess.WRITE)"))
        self.assertIn("WorldSignature.make(src, key, signer)", caller)
        self.assertIn("if _verify(folder) != 0:\n\t\treturn 1", caller)
        self.assertLess(caller.index("if _verify(folder) != 0:"), caller.index('print("SIGNED '))
        self.assertIn("WorldPieces.pack(folder, out, key, signer)", function(source, "_pack"))
        self.assertIn("return _verify(out)", function(source, "_pack"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
