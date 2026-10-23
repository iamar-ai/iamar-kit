"""Static data-only fixtures. A pass never establishes real released-kit QA."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('inventory', ROOT / 'tools/creator_kit_inventory.py')
inv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inv)


def encoded(value):
    return json.dumps(value, sort_keys=True).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inventory data only ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.kit = self.base / 'kit'
        self.inventory = self.base / 'reviewed.json'
        self.mode = 'external'
        self.ts_manifest = None
        for name in inv.REQUIRED:
            self.write(name, b'INERT FIXTURE; NEVER EXECUTE\n')
        self.refresh_provenance()
        self.freeze()

    def write(self, name, value):
        path = self.kit / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        path.chmod(0o755 if name in inv.EXECUTABLES else 0o644)

    def refresh_provenance(self):
        notice = (self.kit / 'ts-world/THIRD_PARTY_NOTICES.txt').read_bytes()
        receipt = {'notices_sha256': sha(notice), 'notices_bytes': len(notice), 'unresolved': []}
        self.write('ts-world/LICENSES_RECEIPT.json', encoded(receipt))
        provenance = {'noticeCoverage': {'receiptSha256': sha(encoded(receipt)), 'uncoveredMembers': []}}
        for key, name in [('guest', 'ts-world/prebuilt/iamar_ts_guest.wasm'),
                          ('spec', 'ts-world/world_api.json'), ('thirdPartyNotices', 'ts-world/THIRD_PARTY_NOTICES.txt')]:
            data = (self.kit / name).read_bytes()
            provenance[key] = {'sha256': sha(data), 'bytes': len(data)}
        self.write('ts-world/prebuilt/provenance.json', encoded(provenance))

    def freeze(self, index=True):
        # Fixture-only baseline writer, intentionally absent from production tool.
        if index:
            names = sorted(str(p.relative_to(self.kit)) for p in self.kit.rglob('*') if p.is_file())
            self.write('index.html', ''.join(f'<a href="{p}">{p}</a>' for p in names if p != 'index.html').encode())
        self.plan = {'schema': 1, 'source_revision': 'a' * 40, 'mode': self.mode,
                     'evidence_kind': 'fixture', 'files': []}
        for p in sorted(self.kit.rglob('*')):
            if p.is_file():
                content = p.read_bytes()
                self.plan['files'].append({'path': str(p.relative_to(self.kit)), 'size': len(content),
                                          'sha256': sha(content), 'mode': p.stat().st_mode & 0o7777})
        self.save_plan()

    def save_plan(self):
        content = encoded(self.plan)
        self.inventory.write_bytes(content)
        self.pin = sha(content)

    def verify(self, profile='generic'):
        return inv.verify(str(self.kit), str(self.inventory), self.pin, self.ts_manifest,
                          profile=profile)

    def refused(self):
        with self.assertRaises((inv.InventoryError, OSError)):
            self.verify()

    def test_complete_fixture_is_explicitly_not_release_qualification(self):
        result = self.verify()
        self.assertEqual(result['evidence_kind'], 'fixture')
        self.assertFalse(result['release_qualified'])
        self.assertEqual(result['files'], len(inv.REQUIRED))

    def test_existing_payload_label_does_not_claim_release(self):
        self.plan['evidence_kind'] = 'existing-payload'
        self.save_plan()
        self.assertFalse(self.verify()['release_qualified'])

    def test_missing_every_required_file(self):
        for name in inv.REQUIRED:
            with self.subTest(name=name):
                path = self.kit / name
                data, mode = path.read_bytes(), path.stat().st_mode
                path.unlink()
                self.refused()
                path.write_bytes(data)
                path.chmod(mode)

    def test_wrong_bytes_each_required_file(self):
        for name in inv.REQUIRED:
            with self.subTest(name=name):
                path = self.kit / name
                data = path.read_bytes()
                path.write_bytes(b'X' + data[1:])
                self.refused()
                path.write_bytes(data)

    def test_unexpected_file(self):
        self.write('ts-world/loose.js', b'unapproved')
        self.refused()

    def test_unexpected_empty_directory(self):
        (self.kit / 'unapproved').mkdir()
        self.refused()

    def test_wrapper_mode(self):
        (self.kit / 'iamar-world').chmod(0o644)
        self.refused()
        self.freeze()
        self.refused()  # A re-pinned baseline cannot waive required wrapper mode.

    def test_windows_wrapper_executable_refused(self):
        (self.kit / 'iamar-world.cmd').chmod(0o755)
        self.freeze()
        self.refused()

    def test_incomplete_reapproved_inventory(self):
        self.plan['files'] = [p for p in self.plan['files'] if p['path'] != 'ts-world/compiler.mjs']
        self.save_plan()
        self.refused()

    def test_inventory_pin_mismatch(self):
        self.pin = '0' * 64
        self.refused()

    def test_template_copy_module_required_even_if_inventory_repinned(self):
        # pack.mjs imports this module before any command can run. A matching
        # inventory pin must not waive its presence. These are inert bytes only.
        name = 'ts-world/template-files.mjs'
        self.write(name, b'INERT FIXTURE; NEVER EXECUTE\n')
        self.freeze()
        self.verify()
        (self.kit / name).unlink()
        self.freeze()
        with self.assertRaisesRegex(inv.InventoryError, 'Incomplete required kit inventory'):
            self.verify()

    def test_template_copy_dependency_source_contract(self):
        # Inspect declarations as source; do not import or run the packer,
        # bundler or bundle fixture (which can assemble compiler payloads).
        name = 'template-files.mjs'
        self.assertIn('ts-world/' + name, inv.REQUIRED)
        bundler = (ROOT / 'tools/kit_bundle.sh').read_text()
        copy_loop = next(line for line in bundler.splitlines()
                         if line.startswith('for f in pack.mjs '))
        self.assertIn(name, copy_loop.removeprefix('for f in ').removesuffix('; do').split())
        fixture = ast.parse((ROOT / 'tests/creator_tool_bundle/test_kit_bundle.py').read_text())
        modules = next(node.value for node in fixture.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'MODULES'
                               for target in node.targets))
        self.assertIn(name, ast.literal_eval(modules))
        # The packer lives in the browser repository (the iamar browser source (not public)); kit_bundle.sh reads it
        # from IAMAR_BROWSER_REPO, else from this root (tools/kit_bundle.sh TS_ROOT).
        packer_path = Path(os.environ.get('IAMAR_BROWSER_REPO') or ROOT) / 'tools/typescript-world/pack.mjs'
        if not packer_path.is_file():
            self.skipTest('packer source not here: set IAMAR_BROWSER_REPO to an the iamar browser source (not public) checkout')
        self.assertIn("from './template-files.mjs';", packer_path.read_text())

    def test_duplicate_path(self):
        self.plan['files'].append(self.plan['files'][0])
        self.save_plan()
        self.refused()

    def test_bad_paths(self):
        for value in ('../escape', '/absolute', 'a//b', 'a/./b', 'a\\b', 'a\nb', 'a:b', 'a/' * 17 + 'b'):
            with self.subTest(value=value):
                self.plan['files'][0]['path'] = value
                self.save_plan()
                self.refused()

    def test_bad_schema_values(self):
        for key, value in [('schema', True), ('source_revision', 'main'), ('mode', 'auto'),
                           ('evidence_kind', 'released')]:
            original = self.plan[key]
            self.plan[key] = value
            self.save_plan()
            self.refused()
            self.plan[key] = original

    def test_duplicate_json_keys(self):
        self.inventory.write_bytes(b'{"schema":1,"schema":1}')
        self.pin = sha(self.inventory.read_bytes())
        self.refused()

    def test_json_bounded_before_read(self):
        self.inventory.write_bytes(b' ' * (inv.MAX_JSON + 1))
        self.refused()

    def test_file_bound(self):
        with patch.object(inv, 'MAX_FILE', 16):
            self.refused()

    def test_total_bound(self):
        with patch.object(inv, 'MAX_TOTAL', 100):
            self.refused()

    def test_entry_bound(self):
        with patch.object(inv, 'MAX_ENTRIES', 2):
            self.refused()

    def test_count_bound(self):
        with patch.object(inv, 'MAX_FILES', 2):
            self.refused()

    def test_symlink_file(self):
        path = self.kit / 'iamar-world'
        path.unlink()
        path.symlink_to(self.inventory)
        self.refused()

    def test_symlink_ancestor(self):
        link = self.base / 'alias'
        link.symlink_to(self.kit, target_is_directory=True)
        self.kit = link
        self.refused()

    def test_symlink_directory(self):
        (self.kit / 'alias').symlink_to(self.kit / 'ts-world', target_is_directory=True)
        self.refused()

    def test_hardlink(self):
        os.link(self.kit / 'iamar-world', self.base / 'hardlink')
        self.refused()

    def test_fifo_refused_without_blocking(self):
        os.mkfifo(self.kit / 'pipe')
        self.refused()

    def test_mixed_guest_even_if_inventory_reapproved(self):
        self.write('ts-world/prebuilt/iamar_ts_guest.wasm', b'mixed guest')
        self.freeze()
        self.refused()

    def test_mixed_spec_even_if_inventory_reapproved(self):
        self.write('ts-world/world_api.json', b'mixed spec')
        self.freeze()
        self.refused()

    def test_mixed_notice_even_if_inventory_reapproved(self):
        self.write('ts-world/THIRD_PARTY_NOTICES.txt', b'mixed notice')
        self.freeze()
        self.refused()

    def test_unresolved_notice_receipt(self):
        path = self.kit / 'ts-world/LICENSES_RECEIPT.json'
        receipt = json.loads(path.read_bytes())
        receipt['unresolved'] = ['missing']
        self.write(str(path.relative_to(self.kit)), encoded(receipt))
        provenance = json.loads((self.kit / 'ts-world/prebuilt/provenance.json').read_bytes())
        provenance['noticeCoverage']['receiptSha256'] = sha(encoded(receipt))
        self.write('ts-world/prebuilt/provenance.json', encoded(provenance))
        self.freeze()
        self.refused()

    def test_incomplete_provenance(self):
        self.write('ts-world/prebuilt/provenance.json', b'{}')
        self.freeze()
        self.refused()

    def test_index_missing_entry_even_if_repinned(self):
        self.write('index.html', b'<a href="AGENT_KIT.md">guide</a>')
        self.freeze(index=False)
        self.refused()

    def test_index_extra_external_link(self):
        path = self.kit / 'index.html'
        path.write_bytes(path.read_bytes() + b'<a href="https://example.invalid">extra</a>')
        self.freeze(index=False)
        self.refused()

    def test_thumbnail_summary_allows_omitted_links_but_pins_every_byte(self):
        self.write('thumbnails/example.png', b'INERT IMAGE FIXTURE')
        # Keep the original non-thumbnail index, exactly as kit_bundle does.
        self.freeze(index=False)
        self.assertFalse(self.verify()['release_qualified'])
        self.write('thumbnails/example.png', b'CHANGED IMAGE FIXTURE')
        self.refused()

    def test_thumbnail_links_are_optional_when_delivered(self):
        self.write('thumbnails/example.png', b'INERT IMAGE FIXTURE')
        self.freeze()
        self.assertFalse(self.verify()['release_qualified'])

    def test_missing_thumbnail_still_refused(self):
        self.write('thumbnails/example.png', b'INERT IMAGE FIXTURE')
        self.freeze(index=False)
        (self.kit / 'thumbnails/example.png').unlink()
        self.refused()

    def test_undelivered_thumbnail_link_refused(self):
        path = self.kit / 'index.html'
        path.write_bytes(path.read_bytes() + b'<a href="thumbnails/missing.png">missing</a>')
        self.freeze(index=False)
        self.refused()

    def test_release_metadata_requires_link_even_if_repinned(self):
        self.write('KIT_VERSION.json', b'{"kit_version":"0.1.0"}')
        self.freeze(index=False)
        self.refused()
        self.freeze()
        self.assertFalse(self.verify()['release_qualified'])

    def test_only_thumbnail_subtree_can_omit_links(self):
        for name in ('thumbnails-extra/example.png', 'docs/extra.md'):
            with self.subTest(name=name):
                self.write(name, b'INERT FIXTURE')
                self.freeze(index=False)
                self.refused()
                (self.kit / name).unlink()
                if name.startswith('thumbnails-extra/'):
                    (self.kit / name).parent.rmdir()

    def test_release_metadata_index_update_precedes_zip(self):
        # Read shell source only. Never execute a release build or payload.
        source = (ROOT / 'tools/build_kit_release.sh').read_text()
        metadata = source.index('python3 - "$KIT/KIT_VERSION.json"')
        index = source.index('python3 - "$KIT/index.html"')
        archive = source.index('echo "== zip"')
        self.assertLess(metadata, index)
        self.assertLess(index, archive)
        self.assertIn('<li><a href="KIT_VERSION.json">KIT_VERSION.json</a></li>', source)

    def test_release_profile_requires_both_files_without_downgrade(self):
        # Neither file, each file alone, and both: inventory is re-pinned each
        # time to prove required presence cannot be waived by a fresh baseline.
        for files in ((), ('iamar-kit.pck',), ('KIT_VERSION.json',)):
            with self.subTest(files=files):
                for name in ('iamar-kit.pck', 'KIT_VERSION.json'):
                    (self.kit / name).unlink(missing_ok=True)
                for name in files:
                    self.write(name, b'INERT RELEASE FIXTURE')
                self.freeze()
                self.assertEqual(self.verify()['profile'], 'generic')
                with self.assertRaisesRegex(inv.InventoryError, 'Incomplete required kit inventory'):
                    self.verify(profile='release')
        for name in ('iamar-kit.pck', 'KIT_VERSION.json'):
            self.write(name, b'INERT RELEASE FIXTURE')
        self.freeze()
        result = self.verify(profile='release')
        self.assertEqual(result['profile'], 'release')
        self.assertFalse(result['release_qualified'])

    def test_release_profile_preserves_hash_and_mode_coverage(self):
        for name in ('iamar-kit.pck', 'KIT_VERSION.json'):
            self.write(name, b'INERT RELEASE FIXTURE')
        self.freeze()
        for name in ('iamar-kit.pck', 'KIT_VERSION.json'):
            with self.subTest(name=name):
                path = self.kit / name
                path.write_bytes(b'CHANGED RELEASE FIXTURE')
                with self.assertRaisesRegex(inv.InventoryError, 'Kit size, hash or mode mismatch'):
                    self.verify(profile='release')
                self.write(name, b'INERT RELEASE FIXTURE')
                path.chmod(0o755)
                self.freeze()
                with self.assertRaisesRegex(inv.InventoryError, 'Required file mode mismatch'):
                    self.verify(profile='release')
                path.chmod(0o644)
                self.freeze()

    def test_unknown_profile_refused(self):
        with self.assertRaisesRegex(inv.InventoryError, 'Unknown inventory profile'):
            self.verify(profile='auto')

    def test_external_mode_rejects_compiler(self):
        self.write(inv.TS_PREFIX + 'lib/typescript.js', b'not official')
        self.freeze()
        self.refused()

    def test_external_mode_rejects_receipt(self):
        self.write('ts-world/TYPESCRIPT_ASSEMBLY.json', b'{}')
        self.freeze()
        self.refused()

    def test_bundled_requires_pinned_manifest(self):
        self.mode = 'bundled'
        self.freeze()
        self.refused()
        manifest = self.base / 'fake-manifest.json'
        manifest.write_bytes(b'{}')
        self.ts_manifest = str(manifest)
        self.refused()

    def bundled(self):
        source = os.environ.get('IAMAR_TEST_TYPESCRIPT_PAYLOAD')
        manifest = os.environ.get('IAMAR_TEST_TYPESCRIPT_MANIFEST')
        if not source or not manifest:
            self.skipTest('Existing approved TypeScript payload and manifest not supplied; no acquisition or extraction')
        self.ts_manifest = str(Path(manifest).absolute())
        self.assertEqual(sha(Path(manifest).read_bytes()), inv.MANIFEST_SHA256)
        shutil.copytree(source, self.kit / inv.TS_PREFIX)
        metadata = json.loads(Path(manifest).read_bytes())
        self.write('ts-world/TYPESCRIPT_ASSEMBLY.json', encoded({
            'version': '5.9.3', 'files': 104, 'bytes': sum(p['size'] for p in metadata['files']),
            'archive_sha256': inv.ARCHIVE_SHA256, 'destination': 'fixture receipt; not a trust anchor'}))
        self.mode = 'bundled'
        self.freeze()

    def test_bundled_official_bytes_static_fixture(self):
        self.bundled()
        self.assertEqual(self.verify()['files'], len(inv.REQUIRED) + 105)
        self.assertEqual(self.verify()['evidence_kind'], 'fixture')

    def test_bundled_compiler_wrong_bytes_even_if_repinned(self):
        self.bundled()
        self.write(inv.TS_PREFIX + 'lib/typescript.js', b'wrong compiler')
        self.freeze()
        self.refused()

    def test_bundled_missing_declaration_even_if_repinned(self):
        self.bundled()
        (self.kit / inv.TS_PREFIX / 'lib/lib.d.ts').unlink()
        self.freeze()
        self.refused()

    def test_bundled_extra_file_even_if_repinned(self):
        self.bundled()
        self.write(inv.TS_PREFIX + 'bin/tsc', b'extra CLI')
        self.freeze()
        self.refused()

    def test_bundled_wrong_receipt_even_if_repinned(self):
        self.bundled()
        self.write('ts-world/TYPESCRIPT_ASSEMBLY.json', b'{}')
        self.freeze()
        self.refused()

    def test_no_runtime_execution_api(self):
        text = (ROOT / 'tools/creator_kit_inventory.py').read_text()
        for token in ('import subprocess', 'os.system(', 'os.exec', 'tarfile', 'zipfile'):
            self.assertNotIn(token, text)


if __name__ == '__main__':
    unittest.main()
