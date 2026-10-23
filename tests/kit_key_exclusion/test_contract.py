"""Static contract checks; not a Godot/security proof.

The historical fixture is the exact source blob from kit commit b2707865,
kept as inert text so this suite works in a normal source checkout.
The native private-pair proposal intentionally replaces historical keygen; its
API-v1 boundary is checked explicitly while packing/signature contracts remain.
"""
from pathlib import Path
import hashlib
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'scripts/kit/world_sign.gd').read_text()
PREIMAGE = (Path(__file__).with_name('fixtures') / 'world_sign.b2707865.gd.txt').read_bytes()

class Contract(unittest.TestCase):
    def test_exact_preimage(self):
        blob = b'blob ' + str(len(PREIMAGE)).encode() + b'\0' + PREIMAGE
        self.assertEqual(hashlib.sha1(blob).hexdigest(), '67bb7253bb237515b70b0edaed1303e3f008635b')

    def test_guard_before_any_pack_side_effect(self):
        pack = SOURCE.split('func _pack(folder:', 1)[1]
        self.assertLess(pack.index('_pack_key_is_external(folder, key_path)'), pack.index('_load_key(key_path)'))
        self.assertLess(pack.index('_pack_key_is_external(folder, key_path)'), pack.index('_sign(folder, key_path, signer)'))
        self.assertLess(pack.index('_pack_key_is_external(folder, key_path)'), pack.index('WorldPieces.pack('))

    def test_keygen_requires_native_private_pair_v1(self):
        keygen = SOURCE.split('func _keygen(', 1)[1].split('func _keyid(', 1)[0]
        self.assertIn('ClassDB.class_exists("IamarPrivateKeyPair")', keygen)
        self.assertIn('transaction.call("get_api_version") != 1', keygen)
        self.assertLess(keygen.index('call("begin", p)'), keygen.index('generate_rsa(2048)'))
        self.assertLess(keygen.index('if not _keygen_result_ok(started):'), keygen.index('generate_rsa(2048)'))
        self.assertLess(keygen.index('generate_rsa(2048)'), keygen.index('call("write_pair",'))
        self.assertLess(keygen.index('call("write_pair",'), keygen.index('call("commit")'))
        self.assertLess(keygen.index('call("commit")'), keygen.index('print("KEY ", p)'))
        for status in ('public_published', 'private_published'):
            self.assertIn('not committed.get("%s", false)' % status, keygen)
        self.assertIn('committed.get("uncertain", true)', keygen)
        self.assertIn('transaction.call("abort")', keygen)
        for unsafe in ('k.save(p)', 'FilePerms.private_file', 'FileAccess.WRITE', 'make_dir_recursive'):
            self.assertNotIn(unsafe, keygen)

    def test_verify_requires_signature_not_trust(self):
        verify = SOURCE.split('func _verify(', 1)[1].split('static func ', 1)[0]
        self.assertIn('WorldPackage.open(p, {"require_signature": true})', verify)
        self.assertNotIn('require_trusted', verify)

    def test_snapshot_not_filename_denylist(self):
        guard = SOURCE.split('static func _pack_key_is_external(', 1)[1].split('func _pack(', 1)[0]
        self.assertIn('for rel in src.list():', guard)
        self.assertIn('var entry := src.read(rel)', guard)
        self.assertIn('if entry == key_bytes:', guard)
        self.assertIn('if not src.ok() or entry.size() != n:', guard)
        self.assertIn('var complete_source := src.ok()', guard)
        self.assertIn('return complete_source', guard)
        self.assertNotIn('.ends_with(".key")', guard)

if __name__ == '__main__':
    unittest.main()
