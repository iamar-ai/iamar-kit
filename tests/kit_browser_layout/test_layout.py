#!/usr/bin/env python3
"""Job 3971: the launchers find the browser in the natural unzip layout.

Unzipping the two homepage downloads side by side gives <dir>/kit/ (the kit zip's top folder) and
<dir>/iamar/iamar.exe (the browser zip's top folder 'iamar'). The launchers must find that browser
with IAMAR_BROWSER unset and never fall through to runtime_fetch (which asks for a download pass).

The Linux test runs the real kit/iamar-world against an inert stub browser; the Windows test runs
the real kit/iamar-world.cmd 'where' the same way. Source checks run everywhere.
"""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(os.environ.get('IAMAR_TEST_SOURCE_ROOT') or Path(__file__).resolve().parents[2])
SH = ROOT / 'kit' / 'iamar-world'
CMD = ROOT / 'kit' / 'iamar-world.cmd'


def _env():
    env = {k: v for k, v in os.environ.items()
           if k not in ('IAMAR_BROWSER', 'IAMAR_PROJECT', 'GODOT', 'IAMAR_KIT_PACK')}
    env['IAMAR_KIT_NO_NEXT'] = '1'
    env['IAMAR_KIT_NO_FETCH'] = '1'
    return env


class SourceTests(unittest.TestCase):
    def test_cmd_looks_in_iamar_subfolder_before_fetching(self):
        s = CMD.read_text(encoding='utf-8')
        look = s.index('"%HERE%..\\iamar\\iamar.exe"')
        self.assertLess(look, s.index('runtime_fetch.cmd" browser'))

    def test_sh_looks_in_iamar_subfolder_before_fetching(self):
        s = SH.read_text(encoding='utf-8')
        look = s.index('"$here/../iamar/iamar"')
        self.assertLess(look, s.index('"$here/runtime_fetch.sh" browser'))


@unittest.skipIf(os.name == 'nt', 'bash launcher')
class LinuxLayoutTest(unittest.TestCase):
    def _layout(self, top, exe):
        kit = top / 'kit'
        kit.mkdir()
        shutil.copy2(SH, kit / 'iamar-world')
        # A fetch would create this marker; the side-by-side browser must be found first.
        fetch = kit / 'runtime_fetch.sh'
        fetch.write_text('#!/bin/sh\n: > "$(dirname "$0")/FETCHED"\nexit 1\n')
        browser = top / 'iamar' / exe
        browser.parent.mkdir()
        browser.write_text('#!/bin/sh\necho "STUB $0 $*"\nexit 0\n')
        for f in (kit / 'iamar-world', fetch, browser):
            f.chmod(f.stat().st_mode | stat.S_IXUSR)
        return kit, browser

    def test_where_finds_side_by_side_browser(self):
        for exe in ('iamar', 'iamar.x86_64'):
            with self.subTest(exe=exe), tempfile.TemporaryDirectory() as t:
                kit, browser = self._layout(Path(t), exe)
                r = subprocess.run(['bash', str(kit / 'iamar-world'), 'where'], cwd=t, env=_env(),
                                   capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn('STUB ' + str(browser.resolve()) + ' ', r.stdout)
                self.assertIn('--kit where', r.stdout)
                self.assertFalse((kit / 'FETCHED').exists(), 'runtime_fetch was called')

    def test_missing_browser_names_the_layout(self):
        with tempfile.TemporaryDirectory() as t:
            kit, browser = self._layout(Path(t), 'iamar')
            browser.unlink()
            r = subprocess.run(['bash', str(kit / 'iamar-world'), 'validate', 'w'], cwd=t, env=_env(),
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 2)
            self.assertIn('/iamar/', r.stderr)
            self.assertIn('side by side', r.stderr)


@unittest.skipUnless(os.name == 'nt', 'Windows launcher')
class WindowsLayoutTest(unittest.TestCase):
    def test_where_finds_side_by_side_browser(self):
        with tempfile.TemporaryDirectory() as t:
            top = Path(t)
            kit = top / 'kit'
            kit.mkdir()
            shutil.copy2(CMD, kit / 'iamar-world.cmd')
            (kit / 'runtime_fetch.cmd').write_text('@echo off\r\ntype nul > "%~dp0FETCHED"\r\nexit /b 1\r\n')
            (top / 'iamar').mkdir()
            browser = top / 'iamar' / 'iamar.exe'
            browser.write_bytes(b'MZ')  # 'where' only names it; nothing runs it
            r = subprocess.run(['cmd.exe', '/d', '/c', str(kit / 'iamar-world.cmd'), 'where'], cwd=t,
                               env=_env(), capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('BROWSER ' + str(browser.resolve()), r.stdout)
            self.assertFalse((kit / 'FETCHED').exists(), 'runtime_fetch was called')


if __name__ == '__main__':
    unittest.main()
