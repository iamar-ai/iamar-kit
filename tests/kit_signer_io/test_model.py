#!/usr/bin/env python3
"""Finite, in-memory signer I/O decisions plus production text assertions.

No GDScript, keys, cryptography, package/file writes, processes, or network.
The fake device models failures; it does not qualify a FileAccess backend.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/kit/world_sign.gd"
OLD_MANIFEST = b'{"name":"old"}\n'
NEW_MANIFEST = b'{"name":"old","signer":{"name":"inert"}}\n'
OLD_SIGNATURE = b"old signature bytes"
NEW_SIGNATURE = b'{"files":["manifest.json","scene.json"],"signature":"inert"}\n'


class Device:
    """An in-memory outcome recorder, never an actual file or signing API."""

    def __init__(self, failure="", old_signature=True):
        self.failure = failure
        self.files = {"manifest": OLD_MANIFEST, "scene": b"scene bytes"}
        if old_signature:
            self.files["signature"] = OLD_SIGNATURE
        self.events = []
        self.errors = []
        self.read_sizes = []
        self.signed_files = None

    def step(self, name):
        self.events.append(name)
        return self.failure != name

    def fail(self, message):
        self.errors.append(message)
        return 1

    def write(self, name, value):
        if not self.step(name + "_open"):
            return False
        # WRITE can truncate immediately; do not model rollback or preservation.
        self.files[name] = b""
        self.events.append(name + "_store")
        stored = self.failure != name + "_store_false"
        store_error = self.failure == name + "_store_error"
        self.events.append(name + "_flush")
        flush_error = self.failure == name + "_flush_error"
        partial = (not stored or store_error or flush_error or
                   self.failure == name + "_silent_flush")
        self.files[name] = value[:3] if partial else value
        if self.failure == name + "_wrong_bytes":
            self.files[name] = b"!" + value[1:]  # equal length, unequal bytes
        self.events.append(name + "_close")
        return stored and not store_error and not flush_error


def sign_model(d):
    """Decision model only. All data, key/make/verify results are inert spies."""
    if not d.step("key"):
        return d.fail("key")
    if not d.step("directory") or not d.step("preflight_links"):
        return d.fail("folder or output link")
    if not d.step("preflight"):
        return d.fail("source")
    if not d.step("manifest_input") or not d.step("signer_input"):
        return d.fail("manifest input")
    d.events.append("release_preflight")
    if not d.step("manifest_link"):
        return d.fail("manifest link")
    if not d.step("folder_probe"):
        return d.fail("folder not writable")
    if not d.write("manifest", NEW_MANIFEST):
        return d.fail("manifest write")
    if not d.step("recapture"):
        return d.fail("source")
    if d.files["manifest"] != NEW_MANIFEST:
        return d.fail("manifest readback")
    d.events.append("make")
    d.signed_files = {k: v for k, v in d.files.items() if k != "signature"}
    d.events.append("release_source")
    # A supplied size-limit failure models the guard without a large allocation.
    if not d.step("signature_limit"):
        return d.fail("signature size")
    if not d.step("signature_link"):
        return d.fail("signature link")
    if "signature" in d.files:
        if not d.step("signature_remove"):
            return d.fail("signature removal")
        del d.files["signature"]
    if not d.write("signature", NEW_SIGNATURE):
        return d.fail("signature write")
    if not d.step("signature_read_open"):
        return d.fail("signature read open")
    readback = b""
    size = len(d.files["signature"])
    if d.failure == "signature_length_before":
        size += 1
    if size == len(NEW_SIGNATURE):
        d.read_sizes.append(len(NEW_SIGNATURE))
        readback = d.files["signature"][:len(NEW_SIGNATURE)]
    read_error = d.failure == "signature_read_error"
    size_matches = (len(d.files["signature"]) == len(NEW_SIGNATURE) and
                    d.failure != "signature_length_after")
    d.events.append("signature_read_close")
    if read_error or not size_matches or readback != NEW_SIGNATURE:
        return d.fail("signature readback")
    if not d.step("verify"):
        return d.fail("verification")
    d.events.append("SIGNED")
    return 0


def function(source, name):
    match = re.search(r"^(?:static )?func " + re.escape(name) + r"\(", source, re.M)
    assert match, name
    end = re.search(r"^(?:static )?func ", source[match.end():], re.M)
    return source[match.start():match.end() + end.start()] if end else source[match.start():]


class SignerIOTests(unittest.TestCase):
    def test_preflight_refusals_do_not_mutate_either_output(self):
        for failure in ["key", "directory", "preflight_links", "preflight",
                        "manifest_input", "signer_input", "manifest_link", "folder_probe"]:
            for old_signature in [False, True]:
                with self.subTest(failure=failure, old_signature=old_signature):
                    d = Device(failure, old_signature)
                    original = d.files.copy()
                    self.assertEqual(sign_model(d), 1)
                    self.assertEqual(d.files, original)
                    self.assertNotIn("manifest_open", d.events)
                    self.assertNotIn("make", d.events)
                    self.assertTrue(d.errors)

    def test_manifest_open_failure_preserves_existing_output(self):
        d = Device("manifest_open")
        self.assertEqual(sign_model(d), 1)
        self.assertEqual(d.files["manifest"], OLD_MANIFEST)
        self.assertEqual(d.files["signature"], OLD_SIGNATURE)
        self.assertNotIn("manifest_store", d.events)

    def test_manifest_write_and_recapture_failures_keep_old_signature_only(self):
        for failure in ["manifest_store_false", "manifest_store_error", "manifest_flush_error",
                        "manifest_silent_flush", "manifest_wrong_bytes", "recapture"]:
            with self.subTest(failure=failure):
                d = Device(failure)
                self.assertEqual(sign_model(d), 1)
                self.assertNotEqual(d.files["manifest"], OLD_MANIFEST)
                self.assertEqual(d.files["signature"], OLD_SIGNATURE)
                self.assertNotIn("make", d.events)
                self.assertNotIn("signature_open", d.events)
                self.assertNotIn("SIGNED", d.events)
                self.assertTrue(d.errors)

    def test_signature_limit_link_and_remove_failure_leave_changed_manifest(self):
        for failure in ["signature_limit", "signature_link", "signature_remove"]:
            d = Device(failure)
            self.assertEqual(sign_model(d), 1)
            self.assertEqual(d.files["manifest"], NEW_MANIFEST)
            self.assertEqual(d.files["signature"], OLD_SIGNATURE)
            self.assertNotIn("signature_store", d.events)
            self.assertNotIn("SIGNED", d.events)

    def test_signature_open_failure_after_unlink_loses_previous_signature(self):
        for old_signature in [False, True]:
            d = Device("signature_open", old_signature)
            self.assertEqual(sign_model(d), 1)
            self.assertEqual(d.files["manifest"], NEW_MANIFEST)
            self.assertNotIn("signature", d.files)
            self.assertNotIn("signature_store", d.events)
            self.assertNotIn("SIGNED", d.events)
            self.assertTrue(d.errors)
            self.assertEqual("signature_remove" in d.events, old_signature)

    def test_unlink_then_create_model_preserves_other_hardlink_contents(self):
        # Two directory entries reference one inert bytearray inode. This is
        # a semantic model, not a native symlink/hardlink or permissions test.
        inode = bytearray(OLD_SIGNATURE)
        entries = {"signature": inode, "outside": inode}
        entries["signature"].clear()  # direct WRITE would truncate both aliases
        self.assertEqual(entries["outside"], b"")
        inode = bytearray(OLD_SIGNATURE)
        entries = {"signature": inode, "outside": inode}
        del entries["signature"]
        entries["signature"] = bytearray(NEW_SIGNATURE)
        self.assertEqual(entries["outside"], OLD_SIGNATURE)
        self.assertEqual(entries["signature"], NEW_SIGNATURE)

    def test_signature_write_and_read_failures_are_nonzero_without_success(self):
        for failure in ["signature_store_false", "signature_store_error", "signature_flush_error",
                        "signature_silent_flush", "signature_wrong_bytes", "signature_read_open",
                        "signature_length_before", "signature_length_after", "signature_read_error"]:
            with self.subTest(failure=failure):
                d = Device(failure)
                self.assertEqual(sign_model(d), 1)
                self.assertEqual(d.files["manifest"], NEW_MANIFEST)
                self.assertNotEqual(d.files["signature"], OLD_SIGNATURE)
                self.assertNotIn("verify", d.events)
                self.assertNotIn("SIGNED", d.events)
                self.assertTrue(d.errors)
                self.assertTrue(all(n == len(NEW_SIGNATURE) for n in d.read_sizes))
                if failure in ["signature_silent_flush", "signature_length_before"]:
                    self.assertEqual(d.read_sizes, [])

    def test_verification_failure_does_not_print_signed(self):
        d = Device("verify")
        self.assertEqual(sign_model(d), 1)
        self.assertEqual(d.files["manifest"], NEW_MANIFEST)
        self.assertEqual(d.files["signature"], NEW_SIGNATURE)
        self.assertNotIn("SIGNED", d.events)

    def test_success_uses_changed_manifest_excludes_old_signature_and_verifies_first(self):
        for old_signature in [False, True]:
            d = Device(old_signature=old_signature)
            self.assertEqual(sign_model(d), 0)
            self.assertEqual(d.signed_files, {"manifest": NEW_MANIFEST, "scene": b"scene bytes"})
            self.assertEqual(d.read_sizes, [len(NEW_SIGNATURE)])
            self.assertLess(d.events.index("release_preflight"), d.events.index("recapture"))
            self.assertLess(d.events.index("verify"), d.events.index("SIGNED"))
            if old_signature:
                self.assertLess(d.events.index("signature_limit"), d.events.index("signature_remove"))
                self.assertLess(d.events.index("signature_remove"), d.events.index("signature_open"))
            self.assertEqual(d.errors, [])

    def test_source_preflight_snapshot_and_no_early_signature_deletion(self):
        sign = function(SOURCE.read_text(), "_sign")
        ordered = ["var output_dir := DirAccess.open(folder)", "if output_dir == null:",
                   "if output_dir.is_link(WorldFormat.MANIFEST) or output_dir.is_link(WorldFormat.SIGNATURE):",
                   "var preflight := WorldSource.open(folder)", "if not preflight.ok():",
                   "preflight.read(WorldFormat.MANIFEST).get_string_from_utf8()",
                   "preflight.close()", "preflight = null", "if output_dir.is_link(WorldFormat.MANIFEST):",
                   "if not _folder_writable(folder):\n\t\treturn 1",
                   "FileAccess.open(mpath, FileAccess.WRITE)",
                   "f.store_string(out)", "var src := WorldSource.open(folder)",
                   "if src.read(WorldFormat.MANIFEST) != out.to_utf8_buffer():",
                   "WorldSignature.make(src, key, signer)", "src.close()", "src = null",
                   "if sig_bytes.size() > WorldSignature.MAX_SIGNATURE_JSON:",
                   "if output_dir.is_link(WorldFormat.SIGNATURE):",
                   "if FileAccess.file_exists(sig_path):", "var remove_error := DirAccess.remove_absolute(sig_path)",
                   "if remove_error != OK:",
                   "FileAccess.open(sig_path, FileAccess.WRITE)"]
        positions = [sign.index(s) for s in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(sign.count("DirAccess.remove_absolute("), 1)
        self.assertIn('if remove_error != OK:\n\t\t\tprinterr("cannot remove old signature.json: ", remove_error)\n\t\t\treturn 1', sign)
        for forbidden in ["rename_absolute", "get_file_as_string", "get_file_as_bytes"]:
            self.assertNotIn(forbidden, sign)

    def test_source_folder_probe_creates_and_removes_before_any_write(self):
        probe = function(SOURCE.read_text(), "_folder_writable")
        ordered = ["FileAccess.file_exists(", "FileAccess.open(probe, FileAccess.WRITE)",
                   "if f == null:\n\t\tprinterr", "f.close()",
                   "DirAccess.remove_absolute(probe)", "if remove_error != OK:", "return true"]
        positions = [probe.index(s) for s in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("store_", probe)
        self.assertNotIn("MANIFEST", probe)
        self.assertNotIn("SIGNATURE", probe)

    def test_source_write_guards_and_bounded_readback(self):
        sign = function(SOURCE.read_text(), "_sign")
        self.assertEqual(sign.count("if f == null:"), 3)
        self.assertEqual(sign.count("f.flush()"), 2)
        self.assertEqual(sign.count("if not stored or store_error != OK or flush_error != OK:"), 2)
        for value in ["out", "sig_text"]:
            at = sign.index("f.store_string(" + value + ")")
            tail = sign[at:]
            ordered = ["store_error", "f.flush()", "flush_error", "f.close()",
                       "if not stored or store_error != OK or flush_error != OK:"]
            positions = [tail.index(s) for s in ordered]
            self.assertEqual(positions, sorted(positions))
        readback = sign[sign.index("f = FileAccess.open(sig_path, FileAccess.READ)"):]
        for text in ["if f == null:\n\t\tprinterr", "return 1",
                     "if f.get_length() == sig_bytes.size():\n\t\treadback = f.get_buffer(sig_bytes.size())",
                     "var read_error := f.get_error()", "var size_matches := f.get_length() == sig_bytes.size()",
                     "if read_error != OK or not size_matches or readback != sig_bytes:\n\t\tprinterr",
                     "if _verify(folder) != 0:\n\t\treturn 1"]:
            self.assertIn(text, readback)
        self.assertEqual(readback.count("f.get_buffer("), 1)
        self.assertLess(readback.index("f.close()"), readback.index("if _verify(folder) != 0:"))
        self.assertLess(readback.index("if _verify(folder) != 0:"), readback.index('print("SIGNED '))
        self.assertTrue(readback.rstrip().endswith("return 0"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
