"""Finite data-only kit integration tests; no Node/compiler/guest/native execution."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = os.environ.get('IAMAR_TEST_TYPESCRIPT_ARCHIVE')
# The TypeScript packer lives in the browser repository (the iamar browser source (not public)), not in the kit.
# IAMAR_BROWSER_REPO names a checkout of it; without one the helper and manifest are
# stubs, which is enough for every test that does not assemble a real archive.
_BROWSER = os.environ.get('IAMAR_BROWSER_REPO')
TS_SOURCE = next((p for p in (Path(_BROWSER) / 'tools/typescript-world' if _BROWSER else None,
                              ROOT / 'tools/typescript-world')
                  if p and (p / 'bundle_runtime.py').is_file()), None)
MODULES = ('pack.mjs', 'compiler.mjs', 'audit-wasm.mjs', 'api_generated.mjs',
           'dependencies.mjs', 'gen_bindings.mjs', 'template-files.mjs')


class KitBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='iamar kit integration ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'source tree'
        self.out = self.base / 'delivered layout'
        self.kit = self.out / 'kit'
        # Minimal synthetic source data; these files must never be executed.
        files = {
            'kit/iamar-world': '#!/bin/sh\nexit 97\n',
            'kit/iamar-world.cmd': '@exit /b 97\n',
            'kit/AGENT_KIT.md': (ROOT / 'kit/AGENT_KIT.md').read_text(),
            'kit/export/rules.json': (ROOT / 'kit/export/rules.json').read_text(),
            'kit/inventory/mem0_export.json': '{"internal":"record"}\n',
            'kit/blindtest/run1/RUN.md': 'operator run record\n',
            'kit/thumbnails/excluded.txt': 'excluded',
            'kit/turntables/excluded.txt': 'excluded',
            'tools/typescript-world/prebuilt/iamar_ts_guest.wasm': 'guest fixture, not executed',
            'tools/typescript-world/prebuilt/provenance.json': '{"fixture":true}\n',
            'tools/typescript-world/guest/THIRD_PARTY_NOTICES.txt': 'guest notice fixture\n',
            'tools/typescript-world/guest/LICENSES_RECEIPT.json': '{"guest_receipt":true}\n',
            'api/typescript/iamar-world.d.ts': 'export {};\n',
            'api/world_api.json': '{"fixture":true}\n',
            'api/ui_page.schema.json': '{"schema_fixture":true}\n',
        }
        files.update({f'docs/{name}.md': name for name in ('WORLD_FORMAT', 'WORLD_API', 'WORLD_TIERS', 'TYPESCRIPT_WORLDS')})
        files.update({f'tools/typescript-world/{name}': 'throw new Error("must not execute");\n'
                      for name in MODULES})
        for name, data in files.items():
            p = self.repo / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(data)
        (self.repo / 'kit/iamar-world').chmod(0o755)
        for name in ('bundle_runtime.py', 'runtime_manifest.json'):
            dest = self.repo / 'tools/typescript-world' / name
            if TS_SOURCE:
                shutil.copyfile(TS_SOURCE / name, dest)
            else:
                dest.write_text('raise SystemExit("stub helper must not run")\n'
                                if name.endswith('.py') else '{"stub":true}\n')
        self.env = dict(os.environ, KIT_BUNDLE_REPO=str(self.repo), PYTHONDONTWRITEBYTECODE='1')
        # The bundle must read the fixture tree, not the browser checkout named above.
        for name in ('IAMAR_BROWSER_REPO', 'IAMAR_BROWSER_REV'):
            self.env.pop(name, None)

    def run_bundle(self, *extra, revision='WORKTREE', out=None):
        return subprocess.run(['bash', str(ROOT / 'tools/kit_bundle.sh'), str(out or self.out),
                               revision, *map(str, extra)], env=self.env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)

    def ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def refused(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('KIT ', result.stdout)

    def archive(self):
        if not ARCHIVE:
            self.skipTest('IAMAR_TEST_TYPESCRIPT_ARCHIVE was not supplied; no acquisition attempted')
        if not TS_SOURCE:
            self.skipTest('IAMAR_BROWSER_REPO (the iamar browser source (not public) checkout) was not supplied')
        self.assertTrue(Path(ARCHIVE).is_file(), 'supplied archive is missing')
        return Path(ARCHIVE)

    def assert_no_index(self):
        self.assertFalse((self.kit / 'index.html').exists())

    def commit_fixture(self):
        def git(*args):
            result = subprocess.run(['git', '-C', str(self.repo), *args], text=True,
                                    capture_output=True, timeout=15)
            self.ok(result)
            return result.stdout.strip()
        git('init', '-q')
        git('add', '.')
        git('-c', 'user.name=Kit fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'synthetic trusted source fixture')
        return git('rev-parse', 'HEAD')

    def test_selected_revision_schema_bytes_ignore_poisoned_checkout(self):
        schema = self.repo / 'api/ui_page.schema.json'
        expected = schema.read_bytes()
        revision = self.commit_fixture()
        schema.write_bytes(b'poisoned checkout schema; not JSON\n')
        self.ok(self.run_bundle(revision=revision))
        self.assertEqual((self.kit / 'ts-world/ui_page.schema.json').read_bytes(), expected)
        self.assertIn('ts-world/ui_page.schema.json', (self.kit / 'index.html').read_text())

    def test_missing_worktree_schema_is_fatal_without_final_index(self):
        (self.repo / 'api/ui_page.schema.json').unlink()
        self.refused(self.run_bundle())
        self.assert_no_index()

    def test_missing_selected_revision_schema_cannot_use_checkout(self):
        schema = self.repo / 'api/ui_page.schema.json'
        expected = schema.read_bytes()
        schema.unlink()
        revision = self.commit_fixture()
        schema.write_bytes(expected)
        self.refused(self.run_bundle(revision=revision))
        self.assert_no_index()

    def test_internal_records_are_pruned_by_the_export_rules(self):
        self.ok(self.run_bundle())
        for gone in ('inventory', 'blindtest', 'export'):
            self.assertFalse((self.kit / gone).exists(), gone)
        self.assertTrue((self.kit / 'AGENT_KIT.md').is_file())

    def test_leak_in_kit_text_is_rewritten_or_refused(self):
        (self.repo / 'kit/NOTES.md').write_text('built on the build host by the maintainer\n')
        self.ok(self.run_bundle())
        text = (self.kit / 'NOTES.md').read_text()
        self.assertNotIn('the build host', text)
        self.assertNotIn('the maintainer', text)
        (self.repo / 'kit/NOTES.md').write_text('token = "ghp_' + 'a' * 36 + '"\n')
        self.refused(self.run_bundle())
        self.assertFalse(self.kit.exists())

    def test_missing_export_rules_fail_closed(self):
        (self.repo / 'kit/export/rules.json').unlink()
        self.refused(self.run_bundle())

    def test_default_external_mode_copies_existing_tooling(self):
        self.ok(self.run_bundle())
        ts = self.kit / 'ts-world'
        self.assertFalse((ts / 'node_modules').exists())
        self.assertFalse((ts / 'TYPESCRIPT_ASSEMBLY.json').exists())
        self.assertFalse((self.kit / 'thumbnails').exists())
        self.assertFalse((self.kit / 'turntables').exists())
        self.assertNotIn('](../docs/', (self.kit / 'AGENT_KIT.md').read_text())
        for name in MODULES:
            self.assertEqual((ts / name).read_bytes(), (self.repo / 'tools/typescript-world' / name).read_bytes())
        for name in ('LICENSES_RECEIPT.json', 'THIRD_PARTY_NOTICES.txt'):
            self.assertEqual((ts / name).read_bytes(), (self.repo / 'tools/typescript-world/guest' / name).read_bytes())
            self.assertIn(f'ts-world/{name}', (self.kit / 'index.html').read_text())
        for name in ('world_api.json', 'ui_page.schema.json'):
            self.assertEqual((ts / name).read_bytes(), (self.repo / 'api' / name).read_bytes())
            self.assertIn(f'ts-world/{name}', (self.kit / 'index.html').read_text())
        self.assertIn('not bundled in this kit', (ts / 'TYPESCRIPT.md').read_text())

    def test_default_does_not_invoke_python(self):
        bins = self.base / 'no python'
        bins.mkdir()
        stub = bins / 'python3'
        real = sys.executable.replace(os.sep, '/')
        # only the public-export prune may run Python; the TypeScript assembly must not
        stub.write_text('#!/bin/sh\ncase "$1" in */kit_prune_public.py) exec "%s" "$@";; esac\n'
                        'echo unexpected-python >&2\nexit 96\n' % real)
        stub.chmod(0o755)
        self.env['PATH'] = str(bins) + os.pathsep + self.env['PATH']
        self.ok(self.run_bundle())

    def test_setup_records_runtime_and_correct_native_handoff(self):
        self.ok(self.run_bundle())
        text = (self.kit / 'ts-world/TYPESCRIPT.md').read_text()
        for expected in ('Node **20 or newer**', 'No Node executable is bundled',
                         'validate fresh-output/world', 'preview fresh-output/world',
                         'does not execute the guest', 'separately configured scoped creator service',
                         'already signed artifact', 'version equality alone does not authenticate'):
            self.assertIn(expected, text)
        self.assertIn('external Node', (self.kit / 'index.html').read_text())

    def test_bad_options_fail_before_existing_kit_reset(self):
        self.kit.mkdir(parents=True)
        sentinel = self.kit / 'sentinel'
        sentinel.write_text('preserve')
        for args in (('--bad', '/tmp/input'), ('--typescript-archive',),
                     ('--typescript-archive', ''), ('--typescript-archive', '/tmp/input', 'extra')):
            with self.subTest(args=args):
                self.refused(self.run_bundle(*args))
                self.assertEqual(sentinel.read_text(), 'preserve')

    def test_input_inside_output_refused_before_reset(self):
        self.kit.mkdir(parents=True)
        archive = self.kit / 'input.tgz'
        archive.write_bytes(b'preserve')
        self.refused(self.run_bundle('--typescript-archive', archive))
        self.assertEqual(archive.read_bytes(), b'preserve')

    def test_alias_of_input_inside_output_refused_before_reset(self):
        self.kit.mkdir(parents=True)
        archive = self.kit / 'input.tgz'
        archive.write_bytes(b'preserve')
        alias = self.base / 'alias.tgz'
        alias.symlink_to(archive)
        self.refused(self.run_bundle('--typescript-archive', alias))
        self.assertEqual(archive.read_bytes(), b'preserve')

    def test_noncanonical_offline_paths_are_refused(self):
        for out, archive in (('relative-output', '/approved/input.tgz'),
                             (self.out, 'relative-input.tgz'),
                             (str(self.out) + '/..', '/approved/input.tgz')):
            with self.subTest(out=out, archive=archive):
                self.refused(self.run_bundle('--typescript-archive', archive, out=out))
        self.assertFalse(self.out.exists())

    def test_missing_or_bad_archive_is_fatal_without_final_index(self):
        bad = self.base / 'bad.tgz'
        for exists in (False, True):
            if exists:
                bad.write_bytes(b'unapproved')
            self.refused(self.run_bundle('--typescript-archive', bad))
            self.assert_no_index()
            self.assertFalse((self.kit / 'ts-world/node_modules/typescript').exists())
            self.assertFalse(list(self.out.glob('.typescript-assembler.*')))

    def test_exact_compiler_inventory_and_notices_precede_index(self):
        self.ok(self.run_bundle('--typescript-archive', self.archive()))
        ts = self.kit / 'ts-world'
        dest = ts / 'node_modules/typescript'
        manifest = json.loads((TS_SOURCE / 'runtime_manifest.json').read_text())
        expected = {f['path']: f for f in manifest['files']}
        self.assertEqual(set(expected), {str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file()})
        self.assertEqual(len(expected), 104)
        index = (self.kit / 'index.html').read_text()
        for name, entry in expected.items():
            data = (dest / name).read_bytes()
            self.assertEqual(len(data), entry['size'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
            self.assertIn('ts-world/node_modules/typescript/' + name, index)
        receipt = json.loads((ts / 'TYPESCRIPT_ASSEMBLY.json').read_text())
        self.assertEqual(receipt['files'], 104)
        self.assertEqual(receipt['bytes'], 12305048)
        self.assertEqual(receipt['destination'], str(dest))
        self.assertIn('TYPESCRIPT_ASSEMBLY.json', index)
        self.assertFalse(list(self.out.glob('.typescript-assembler.*')))
        self.assertFalse((ts / 'bundle_runtime.py').exists())
        text = (ts / 'TYPESCRIPT.md').read_text()
        self.assertIn('bundled compiler', text)
        self.assertNotIn('npm i', text)
        self.assertIn('100', text)
        self.assertIn('No Node executable is bundled', text)
        guide = (self.kit / 'AGENT_KIT.md').read_text()
        self.assertIn('no separate compiler install is needed', guide)
        self.assertNotIn('npm i typescript@5.9.3', guide)
        self.assertNotIn('installed Node.js and TypeScript', guide)
        self.assertIn('ts-world/TYPESCRIPT.md', guide)

    def test_changed_guide_refuses_offline_success(self):
        archive = self.archive()
        guide = self.repo / 'kit/AGENT_KIT.md'
        guide.write_text(guide.read_text().replace('Bash or Python.', 'Different source wording.'))
        result = self.run_bundle('--typescript-archive', archive)
        self.refused(result)
        self.assertIn('compiler guidance changed', result.stderr)
        self.assert_no_index()

    def test_repeat_bundle_resets_only_disposable_kit(self):
        archive = self.archive()
        self.ok(self.run_bundle('--typescript-archive', archive))
        sentinel = self.out / 'outside-kit'
        sentinel.write_text('preserve')
        (self.kit / 'stale').write_text('remove')
        self.ok(self.run_bundle('--typescript-archive', archive))
        self.assertFalse((self.kit / 'stale').exists())
        self.assertEqual(sentinel.read_text(), 'preserve')
        self.ok(self.run_bundle())
        self.assertFalse((self.kit / 'ts-world/node_modules').exists())
        self.assertIn('external compiler', (self.kit / 'ts-world/TYPESCRIPT.md').read_text())

    def test_tampered_approved_archive_is_refused(self):
        original = self.archive().read_bytes()
        tampered = self.base / 'tampered.tgz'
        tampered.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        self.refused(self.run_bundle('--typescript-archive', tampered))
        self.assert_no_index()

    def test_symlink_archive_is_refused(self):
        alias = self.base / 'archive symlink.tgz'
        alias.symlink_to(self.archive())
        self.refused(self.run_bundle('--typescript-archive', alias))
        self.assert_no_index()

    def test_bad_selected_manifest_is_fatal(self):
        archive = self.archive()
        (self.repo / 'tools/typescript-world/runtime_manifest.json').write_text('{}')
        self.refused(self.run_bundle('--typescript-archive', archive))
        self.assert_no_index()
        self.assertFalse(list(self.out.glob('.typescript-assembler.*')))

    def test_selected_git_revision_supplies_helper_and_manifest(self):
        archive = self.archive()
        expected_schema = (self.repo / 'api/ui_page.schema.json').read_bytes()
        revision = self.commit_fixture()
        (self.repo / 'tools/typescript-world/bundle_runtime.py').write_text('raise RuntimeError("wrong checkout helper")')
        (self.repo / 'tools/typescript-world/runtime_manifest.json').write_text('{}')
        (self.repo / 'tools/typescript-world/pack.mjs').write_text('different checkout packer')
        (self.repo / 'api/ui_page.schema.json').write_bytes(b'poisoned checkout schema; not JSON\n')
        self.ok(self.run_bundle('--typescript-archive', archive, revision=revision))
        self.assertEqual((self.kit / 'ts-world/ui_page.schema.json').read_bytes(), expected_schema)
        self.assertEqual((self.kit / 'ts-world/pack.mjs').read_text(), 'throw new Error("must not execute");\n')
        self.assertEqual(json.loads((self.kit / 'ts-world/TYPESCRIPT_ASSEMBLY.json').read_text())['files'], 104)


if __name__ == '__main__':
    unittest.main()
