"""Inert index fixtures, NOT real builder/ZIP/native acceptance.

These tests run only the builder's index-editing Python heredocs when authorized.
They never invoke shell/build_pack/kit_bundle/Godot or a delivered payload.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tools/build_kit_release.sh'


def heredoc(label):
    # Review the exact isolated block, rather than reimplementing its behavior.
    source = SOURCE.read_text()
    return source.split("<<'" + label + "'\n", 1)[1].split('\n' + label + '\n', 1)[0]


class ReleaseIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inert-release-index-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kit = self.root / 'zip-index.html'
        self.site = self.root / 'site-index.html'
        self.original = ('<h1>iamar world kit</h1><ul>\n'
                         '<li><a href="iamar-kit.pck">iamar-kit.pck</a></li>\n'
                         '<li><a href="AGENT_KIT.md">AGENT_KIT.md</a></li>\n</ul>')
        self.kit.write_text(self.original)

    def invoke(self, label, path, *args, optimized=False):
        command = [sys.executable] + (['-O'] if optimized else [])
        return subprocess.run(command + ['-c', heredoc(label), str(path), *args],
                              capture_output=True, text=True, check=False)

    def site_update(self, optimized=False):
        return self.invoke('PY_SITE_INDEX', self.site, '0.1.0', 'a' * 64,
                           '123', 'iamar-kit-0.1.0.zip', optimized=optimized)

    def test_zip_keeps_pack_and_site_removes_only_pack_entry(self):
        self.assertEqual(self.invoke('PY_INDEX', self.kit).returncode, 0)
        archived_index = self.kit.read_bytes()
        self.site.write_bytes(archived_index)
        self.assertEqual(self.site_update().returncode, 0)
        self.assertEqual(self.kit.read_bytes(), archived_index)
        self.assertIn('href="iamar-kit.pck"', archived_index.decode())
        self.assertNotIn('href="iamar-kit.pck"', self.site.read_text())
        for path in (self.kit, self.site):
            self.assertIn('href="KIT_VERSION.json"', path.read_text())
            self.assertIn('href="AGENT_KIT.md"', path.read_text())
        self.assertNotIn('href="iamar-kit-0.1.0.zip"', self.site.read_text())

    def test_public_page_links_the_published_downloads(self):
        # tools/publish_kit_release.sh publishes the fixed-name zips, SHA256SUMS and manifest.json beside the
        # page (ungated, decision #59); the installer link only when the build made the .exe.
        out = self.root / 'out'
        page = out / 'site/kit/index.html'
        page.parent.mkdir(parents=True)
        for optimized in (False, True):
            for with_exe in (False, True):
                with self.subTest(optimized=optimized, with_exe=with_exe):
                    exe = out / 'iamar-kit-0.1.0-windows-setup.exe'
                    if with_exe:
                        exe.write_bytes(b'MZ')
                    elif exe.exists():
                        exe.unlink()
                    page.write_text(self.original)
                    result = self.invoke('PY_SITE_INDEX', page, '0.1.0', 'a' * 64, '123',
                                         'iamar-kit-0.1.0.zip', optimized=optimized)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    rendered = page.read_text()
                    self.assertIn('kit version 0.1.0', rendered)
                    for name in ('windows', 'macos', 'linux'):
                        self.assertIn(f'href="iamar-kit-latest-{name}.zip"', rendered)
                    self.assertIn('href="SHA256SUMS"', rendered)
                    self.assertIn('href="manifest.json"', rendered)
                    self.assertEqual('href="iamar-kit-latest-windows-setup.exe"' in rendered, with_exe)
                    self.assertNotIn('href="iamar-kit-0.1.0.zip"', rendered)
                    self.assertNotIn('not a ZIP download', rendered)
                    # Developer mode's own download is described only once it ships (iamar-devmode).
                    self.assertNotIn('turn on Developer mode', rendered)
                    self.assertNotIn('href="docs/DEVMODE_MIGRATION.md"', rendered)

    def test_metadata_marker_failures_survive_optimization(self):
        for optimized in (False, True):
            for text in ('<ul>', '<ul></ul></ul>'):
                with self.subTest(optimized=optimized, text=text):
                    self.kit.write_text(text)
                    result = self.invoke('PY_INDEX', self.kit, optimized=optimized)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.kit.read_text(), text)

    def test_site_marker_failures_do_not_write(self):
        pack_entry = '<li><a href="iamar-kit.pck">iamar-kit.pck</a></li>'
        heading = '<h1>iamar world kit</h1>'
        for text in (self.original.replace(pack_entry, ''),
                     self.original + pack_entry,
                     self.original.replace(heading, ''), self.original + heading):
            with self.subTest(text=text):
                self.site.write_text(text)
                self.assertNotEqual(self.site_update(optimized=True).returncode, 0)
                self.assertEqual(self.site.read_text(), text)

    def test_source_order_and_pinned_inputs_only_structural(self):
        # Deliberately only a structural assertion. This cannot establish actual
        # shell control flow, exact archive contents or clean-install behavior.
        source = SOURCE.read_text()
        self.assertLess(source.index("<<'PY_INDEX'"), source.index('echo "== zip"'))
        self.assertLess(source.index('echo "== zip"'), source.index("<<'PY_SITE_INDEX'"))
        self.assertIn('"$ROOT/tools/build_pack.sh" "$OUT/iamar-kit.pck" "$KIT_COMMIT"', source)
        self.assertIn('REV="$KIT_COMMIT"', source)
        self.assertIn('IAMAR_BROWSER_REV="$BROWSER_COMMIT"', source)
        self.assertIn('--worktree) echo "build_kit_release: working-tree development builds are not release-qualified;', source)
        self.assertNotIn('REV=WORKTREE', source)
        replacement_guard = source.index('export GIT_NO_REPLACE_OBJECTS=1')
        self.assertLess(replacement_guard, source.index('git -C'))
        self.assertLess(replacement_guard, source.index('\"$ROOT/tools/kit_bundle.sh\"'))


if __name__ == '__main__':
    unittest.main()
