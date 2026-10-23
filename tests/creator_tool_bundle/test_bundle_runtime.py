"""Data-only tests: supply the already approved archive; never download/execute it."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('bundle_runtime', ROOT / 'tools/typescript-world/bundle_runtime.py')
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)
ARCHIVE = os.environ.get('IAMAR_TEST_TYPESCRIPT_ARCHIVE')


@unittest.skipUnless(sys.platform == 'linux' and ARCHIVE, 'Requires Linux and IAMAR_TEST_TYPESCRIPT_ARCHIVE (no download)')
class Assembly(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='iamar-creator-bundle-')
        self.root = Path(self.temp.name)
        self.parent = self.root / 'kit/ts-world/node_modules'
        self.parent.mkdir(parents=True)
        self.destination = self.parent / 'typescript'
        self.archive = str(Path(ARCHIVE).absolute())

    def tearDown(self):
        self.temp.cleanup()

    def run_bundle(self, source=None, destination=None):
        return bundle.assemble(source or self.archive, str(destination or self.destination))

    def test_complete_exact_inventory_and_notices(self):
        result = self.run_bundle()
        manifest = bundle.load_manifest()
        self.assertEqual(result['files'], 104)
        actual = sorted(p.relative_to(self.destination).as_posix() for p in self.destination.rglob('*') if p.is_file())
        self.assertEqual(actual, sorted(s['path'] for s in manifest['files']))
        for spec in manifest['files']:
            p = self.destination / spec['path']
            self.assertEqual(p.stat().st_size, spec['size'])
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), spec['sha256'])
        self.assertEqual(len(list((self.destination / 'lib').glob('lib.*.d.ts'))), 99)
        self.assertTrue((self.destination / 'lib/lib.d.ts').is_file())
        self.assertEqual(len(list((self.destination / 'lib').glob('*.d.ts'))), 100)
        self.assertFalse((self.destination / 'bin').exists())
        self.assertEqual(list(self.parent.glob('.typescript-stage-*')), [])

    def test_second_run_preserves_existing_package(self):
        self.run_bundle()
        with self.assertRaises(bundle.BundleError):
            self.run_bundle()
        self.assertTrue((self.destination / 'LICENSE.txt').is_file())

    def test_modified_archive_no_output(self):
        source = self.root / 'bad.tgz'
        data = bytearray(Path(self.archive).read_bytes()); data[-1] ^= 1
        source.write_bytes(data)
        with self.assertRaises(bundle.BundleError):
            self.run_bundle(str(source))
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_truncated_archive_no_output(self):
        source = self.root / 'bad.tgz'; source.write_bytes(b'bad')
        with self.assertRaises(bundle.BundleError):
            self.run_bundle(str(source))
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_missing_parent_not_created(self):
        destination = self.root / 'other/kit/ts-world/node_modules/typescript'
        with self.assertRaises(OSError):
            self.run_bundle(destination=destination)
        self.assertFalse((self.root / 'other').exists())

    def test_bad_destination_shapes(self):
        for dest in [str(self.root / 'typescript'), str(self.parent / '../typescript'), 'relative/kit/ts-world/node_modules/typescript', str(self.destination) + '/', str(self.root) + '//kit/ts-world/node_modules/typescript']:
            with self.subTest(dest=dest), self.assertRaises(bundle.BundleError):
                self.run_bundle(destination=dest)
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_source_symlink(self):
        source = self.root / 'link.tgz'; source.symlink_to(self.archive)
        with self.assertRaises(OSError):
            self.run_bundle(str(source))

    def test_source_ancestor_symlink(self):
        link = self.root / 'link'; link.symlink_to(Path(self.archive).parent, target_is_directory=True)
        with self.assertRaises(OSError):
            self.run_bundle(str(link / Path(self.archive).name))

    def test_source_hardlink(self):
        source = self.root / 'input.tgz'; source.write_bytes(Path(self.archive).read_bytes())
        linked = self.root / 'hard.tgz'; os.link(source, linked)
        with self.assertRaises(bundle.BundleError):
            self.run_bundle(str(linked))

    def test_source_fifo_does_not_block(self):
        source = self.root / 'fifo'; os.mkfifo(source)
        with self.assertRaises(bundle.BundleError):
            self.run_bundle(str(source))

    def test_destination_symlink(self):
        outside = self.root / 'outside'; outside.mkdir()
        self.destination.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(bundle.BundleError):
            self.run_bundle()
        self.assertEqual(list(outside.iterdir()), [])

    def test_destination_ancestor_symlink(self):
        self.parent.rmdir()
        outside = self.root / 'outside'; outside.mkdir()
        self.parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            self.run_bundle()
        self.assertEqual(list(outside.iterdir()), [])

    def test_existing_file_not_overwritten(self):
        self.destination.write_text('keep')
        with self.assertRaises(bundle.BundleError):
            self.run_bundle()
        self.assertEqual(self.destination.read_text(), 'keep')

    def test_write_failure_retains_stage_not_destination(self):
        with mock.patch.object(bundle, 'write_payloads', side_effect=OSError('simulated disk failure')):
            with self.assertRaisesRegex(bundle.BundleError, 'staging retained'):
                self.run_bundle()
        self.assertFalse(self.destination.exists())
        self.assertEqual(len(list(self.parent.glob('.typescript-stage-*'))), 1)

    def test_publish_race_does_not_replace_empty_directory(self):
        real = bundle.rename_noreplace
        def race(parent, stage, dest):
            os.mkdir(dest, dir_fd=parent)
            return real(parent, stage, dest)
        with mock.patch.object(bundle, 'rename_noreplace', side_effect=race):
            with self.assertRaises(bundle.BundleError):
                self.run_bundle()
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assertEqual(len(list(self.parent.glob('.typescript-stage-*'))), 1)

    def test_publish_unavailable_fails_closed(self):
        with mock.patch.object(bundle, 'rename_noreplace', side_effect=bundle.BundleError('unsupported')):
            with self.assertRaises(bundle.BundleError):
                self.run_bundle()
        self.assertFalse(self.destination.exists())

    def test_stage_name_substitution_refused(self):
        real = bundle.write_payloads
        def swap(stage, payloads):
            real(stage, payloads)
            path = next(self.parent.glob('.typescript-stage-*'))
            path.rename(self.parent / 'retained-original-stage')
            path.mkdir()
        with mock.patch.object(bundle, 'write_payloads', side_effect=swap):
            with self.assertRaises(bundle.BundleError):
                self.run_bundle()
        self.assertFalse(self.destination.exists())
        self.assertTrue((self.parent / 'retained-original-stage/LICENSE.txt').is_file())

    def test_parent_substitution_refused(self):
        real = bundle.write_payloads
        def swap(stage, payloads):
            real(stage, payloads)
            self.parent.rename(self.parent.with_name('retained-original-parent'))
            self.parent.mkdir()
        with mock.patch.object(bundle, 'write_payloads', side_effect=swap):
            with self.assertRaises(bundle.BundleError):
                self.run_bundle()
        self.assertEqual(list(self.parent.iterdir()), [])
        self.assertFalse((self.parent.with_name('retained-original-parent') / 'typescript').exists())

    def test_member_count_limit(self):
        with mock.patch.object(bundle, 'MAX_MEMBERS', 1):
            with self.assertRaisesRegex(bundle.BundleError, 'Too many'):
                bundle.select_members(Path(self.archive).read_bytes(), bundle.load_manifest())

    def test_expanded_size_limit(self):
        with mock.patch.object(bundle, 'MAX_EXPANDED', 1):
            with self.assertRaisesRegex(bundle.BundleError, 'expanded-size'):
                bundle.select_members(Path(self.archive).read_bytes(), bundle.load_manifest())

    def test_source_output_overlap(self):
        with self.assertRaisesRegex(bundle.BundleError, 'overlap'):
            self.run_bundle(str(self.destination / 'source.tgz'))

    def test_wrong_manifest_refused(self):
        with mock.patch.object(bundle, 'MANIFEST_SHA256', '0' * 64):
            with self.assertRaisesRegex(bundle.BundleError, 'manifest hash'):
                self.run_bundle()
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_wrong_npm_integrity_refused(self):
        manifest = bundle.load_manifest(); manifest['archive']['integrity'] = 'wrong'
        with self.assertRaisesRegex(bundle.BundleError, 'npm integrity'):
            bundle.verified_payloads(self.archive, manifest)

    def test_member_validation_negative_cases(self):
        # Exercise structural defenses below the production archive-hash gate.
        cases = [('package/../escape', tarfile.REGTYPE, False, 1),
                 ('/escape', tarfile.REGTYPE, False, 1),
                 ('package\\escape', tarfile.REGTYPE, False, 1),
                 ('package/lib/link', tarfile.SYMTYPE, False, 1),
                 ('package/lib/hard', tarfile.LNKTYPE, False, 1),
                 ('package/lib/fifo', tarfile.FIFOTYPE, False, 1),
                 ('package/lib/duplicate', tarfile.REGTYPE, True, 1),
                 ('package/lib/typescript.js', tarfile.REGTYPE, False, 1)]
        for name, kind, duplicate, size in cases:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode='w:gz') as t:
                member = tarfile.TarInfo(name); member.type = kind; member.size = size if kind == tarfile.REGTYPE else 0
                t.addfile(member, io.BytesIO(b'x' * member.size))
                if duplicate: t.addfile(member, io.BytesIO(b'x' * member.size))
            with self.subTest(name=name), self.assertRaises(bundle.BundleError):
                bundle.select_members(buf.getvalue(), bundle.load_manifest())

    def test_missing_members_refused(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz'): pass
        with self.assertRaisesRegex(bundle.BundleError, 'Missing'):
            bundle.select_members(buf.getvalue(), bundle.load_manifest())

    def test_changed_member_hash_refused(self):
        spec = next(s for s in bundle.load_manifest()['files'] if s['path'] == 'LICENSE.txt')
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as t:
            member = tarfile.TarInfo('package/LICENSE.txt'); member.size = spec['size']
            t.addfile(member, io.BytesIO(b'x' * member.size))
        with self.assertRaisesRegex(bundle.BundleError, 'hash mismatch'):
            bundle.select_members(buf.getvalue(), bundle.load_manifest())


if __name__ == '__main__':
    if not ARCHIVE:
        sys.exit('Set IAMAR_TEST_TYPESCRIPT_ARCHIVE to the already approved official 5.9.3 archive; no tests run.')
    unittest.main()
