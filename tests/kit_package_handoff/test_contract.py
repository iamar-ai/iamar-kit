"""Source checks and inert filename/failure models; no Godot, signing or ZIP I/O."""
from pathlib import Path
import argparse
import re
import unittest

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument("--baseline", action="store_true", help="reproduce the old mismatch only")
args = parser.parse_args()
source = (args.root / "scripts/worlds/world_pieces.gd").read_text()
installer = (args.root / "scripts/host/local_world_install.gd").read_text()
signer = (args.root / "scripts/kit/world_sign.gd").read_text()
host = (args.root / "scripts/shell/self_host.gd").read_text()


def function(name):
    start = re.search(r"^static func " + re.escape(name) + r"\(", source, re.M)
    assert start, name
    end = re.search(r"^static func ", source[start.end():], re.M)
    return source[start.start():start.end() + end.start()] if end else source[start.start():]


def adjacent(path):
    """Inert get_basename equivalent; this does not establish import eligibility."""
    slash = max(path.rfind("/"), path.rfind("\\"))
    dot = path.rfind(".")
    return (path[:dot] if dot > slash else path) + ".pieces.json"


def producer(path, identity):
    """Recognize only the exact old/new return expressions, never execute GDScript."""
    body = function("pieces_path_for")
    if 'return package_path.get_basename() + ".pieces.json"' in body:
        return adjacent(path)
    assert 'return package_path.get_base_dir().path_join("%s-%s.pieces.json" % [list.id, list.version])' in body
    slash = max(path.rfind("/"), path.rfind("\\"))
    return path[:slash + 1] + identity["id"] + "-" + identity["version"] + ".pieces.json"


def modeled_pack(files, archive, identity, fail=None):
    """Specification model using marker values, not actual archives or signatures."""
    sidecar = producer(archive, identity)
    events = []
    if archive in files or sidecar in files:
        return False, events
    # Preflight cannot promise success: retain partial output on later failures.
    if fail == "open_archive":
        return False, events
    files[archive] = "partial archive"
    events.append("open_archive")
    if fail == "write_archive":
        return False, events
    files[archive] = "complete archive"
    if fail == "open_sidecar":
        return False, events
    files[sidecar] = "partial sidecar"
    events.append("open_sidecar")
    if fail == "write_sidecar":
        return False, events
    files[sidecar] = "complete sidecar"
    return True, events


identity = {"id": "my-world", "version": "1.0.0"}
if args.baseline:
    produced = producer("out/release.iamar", identity)
    required = adjacent("out/release.iamar")
    assert produced == "out/my-world-1.0.0.pieces.json" and produced != required
    print(f"REPRODUCED: producer={produced}; importer requires={required}")
    raise SystemExit(0)


class FilenameContract(unittest.TestCase):
    def test_arbitrary_output_pairs(self):
        paths = ["out/release.iamar", "release.iamar", "./release.iamar",
                 "/build output/world.v2.iamar", "user://out/release.iamar",
                 "C:/My Worlds/release.iamar", r"C:\My Worlds\release.iamar",
                 "out.with.dots/世界.iamar", "/out/.release.iamar"]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(producer(path, identity), adjacent(path))

    def test_canonical_name_unchanged(self):
        self.assertEqual(producer("out/my-world-1.0.0.iamar", identity),
                         "out/my-world-1.0.0.pieces.json")

    def test_other_output_extensions_still_do_not_imply_import(self):
        # The pack API does not require a lowercase .iamar suffix. Keep that
        # behavior, while import retains its existing lowercase suffix gate.
        for path in ["out/release.IAMAR", "out/release", "out/release.zip"]:
            with self.subTest(path=path):
                self.assertEqual(producer(path, identity), "out/release.pieces.json")
                self.assertFalse(path.endswith(".iamar"))
        self.assertIn('not _source.ends_with(".iamar")', installer)
        self.assertNotIn('ends_with(".iamar")', function("pack"))

    def test_distinct_outputs_same_identity_do_not_share_sidecar(self):
        a = producer("out/release.iamar", identity)
        b = producer("out/review.iamar", identity)
        self.assertNotEqual(a, b)
        files = {}
        self.assertTrue(modeled_pack(files, "out/release.iamar", identity)[0])
        first = dict(files)
        self.assertTrue(modeled_pack(files, "out/review.iamar", identity)[0])
        self.assertTrue(all(files[p] == v for p, v in first.items()))

    def test_identity_does_not_choose_sidecar_path(self):
        other = {"id": "other-world", "version": "2.0.0"}
        self.assertEqual(producer("out/release.iamar", identity),
                         producer("out/release.iamar", other))

    def test_import_and_discovery_remain_exact_adjacent(self):
        self.assertIn('_source.get_basename() + ".pieces.json"', installer)
        self.assertIn('f.trim_suffix(".pieces.json") + ".iamar"', host)
        self.assertIn('WorldPieces.load_list(work.list_path)', installer)
        self.assertIn('WorldPieces.verify_piece(list, _piece_index, bytes)', installer)
        self.assertIn('WorldPieces.open_assembled(work.list, work.package_path, {"require_signature": true})', installer)

    def test_two_argument_api_and_result_path_retained(self):
        self.assertIn('pieces_path_for(package_path: String, _list: Dictionary)', source)
        pack = function("pack")
        self.assertIn('var pp := pieces_path_for(out_path, m)', pack)
        self.assertIn('FileAccess.open(pp, FileAccess.WRITE)', pack)
        self.assertIn('r.pieces_path = pp', pack)
        self.assertIn('r.list = list', pack)

    def test_output_preflight_precedes_both_writes(self):
        pack = function("pack")
        guard = pack.index('if _output_exists(out_path) or _output_exists(pp):')
        self.assertLess(guard, pack.index('DirAccess.make_dir_recursive_absolute('))
        self.assertLess(guard, pack.index('z.open(out_path)'))
        self.assertLess(guard, pack.index('FileAccess.open(pp, FileAccess.WRITE)'))
        self.assertIn('return r', pack[guard:pack.index('z.open(out_path)')])
        exists = function("_output_exists")
        self.assertIn('FileAccess.file_exists(path) or DirAccess.dir_exists_absolute(path)', exists)
        self.assertIn('DirAccess.open(parent if parent != "" else ".")', exists)
        self.assertIn('directory != null and directory.is_link(path.get_file())', exists)

    def test_source_signing_still_precedes_pack_refusal(self):
        # This is a documented limitation, not a transaction/no-side-effect claim.
        self.assertLess(signer.index('if _sign(folder, key_path, signer) != 0:'),
                        signer.index('WorldPieces.pack(folder, out, key, signer)'))

    def test_archive_and_sidecar_collisions_do_not_write(self):
        for path in ["out/release.iamar", "out/release.pieces.json"]:
            for kind in ["existing file", "directory", "symlink", "dangling symlink"]:
                with self.subTest(path=path, kind=kind):
                    files = {path: kind, "out/unrelated": "keep"}
                    before = dict(files)
                    ok, events = modeled_pack(files, "out/release.iamar", identity)
                    self.assertFalse(ok)
                    self.assertEqual(events, [])
                    self.assertEqual(files, before)

    def test_old_identity_named_sidecar_is_not_touched(self):
        files = {"out/my-world-1.0.0.pieces.json": "older result"}
        self.assertTrue(modeled_pack(files, "out/release.iamar", identity)[0])
        self.assertEqual(files["out/my-world-1.0.0.pieces.json"], "older result")

    def test_different_extensions_sharing_basename_are_refused(self):
        for alternative in ["out/release.IAMAR", "out/release", "out/release.zip"]:
            with self.subTest(alternative=alternative):
                files = {}
                self.assertTrue(modeled_pack(files, "out/release.iamar", identity)[0])
                before = dict(files)
                self.assertEqual(modeled_pack(files, alternative, identity), (False, []))
                self.assertEqual(files, before)

    def test_failure_is_not_success_and_partial_retry_is_refused(self):
        for failure in ["open_archive", "write_archive", "open_sidecar", "write_sidecar"]:
            with self.subTest(failure=failure):
                files = {"out/unrelated": "keep"}
                ok, _ = modeled_pack(files, "out/release.iamar", identity, failure)
                self.assertFalse(ok)
                self.assertEqual(files["out/unrelated"], "keep")
                if failure != "open_archive":
                    before = dict(files)
                    self.assertEqual(modeled_pack(files, "out/release.iamar", identity), (False, []))
                    self.assertEqual(files, before)

    def test_existing_failure_and_verification_gates_retained(self):
        pack = function("pack")
        for token in ['if z.open(out_path) != OK:', 'if z.close() != OK:',
                      'if f == null:', 'if not f.store_string(',
                      'make_list(bytes, String(m.id), String(m.version), key, signer)']:
            self.assertIn(token, pack)
        self.assertLess(pack.index('f.close()'), pack.index('r.ok = true'))
        self.assertIn('WorldSignature.sign_text(signing_text(list), key)', function("make_list"))
        self.assertIn('WorldSignature.verify_text(signing_text(list)', function("check_list"))
        self.assertIn('the package is not signed by the piece list', function("check_assembled"))


suite = unittest.defaultTestLoader.loadTestsFromTestCase(FilenameContract)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print("Source/specification models only; GDScript, cryptography, archives, native I/O and UI remain unrun.")
raise SystemExit(0 if result.wasSuccessful() else 1)
