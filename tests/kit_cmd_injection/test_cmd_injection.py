#!/usr/bin/env python3
"""kit-5 (BatBadBut): arguments to the Windows launchers are never run as cmd syntax.

Source checks run everywhere. On Windows the real kit/iamar-world.cmd and kit/runtime_fetch.cmd
run against an inert stub browser (a .cmd that only echoes its arguments) in a temporary folder;
every payload tries to create a marker file there, and no marker may appear.
Out of scope (cannot be fixed inside a .cmd): an unquoted & | < > that the caller's own cmd.exe
splits off before the launcher starts, e.g. list2cmdline(['new', 'a "&calc']).
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(os.environ.get('IAMAR_TEST_SOURCE_ROOT') or Path(__file__).resolve().parents[2])
LAUNCHER = ROOT / 'kit' / 'iamar-world.cmd'
FETCH = ROOT / 'kit' / 'runtime_fetch.cmd'
SOURCE = LAUNCHER.read_text(encoding='utf-8').replace('\r\n', '\n')
FETCH_SOURCE = FETCH.read_text(encoding='utf-8').replace('\r\n', '\n')

# (arguments, marker): each payload would create <marker> in the working folder if it ran.
PAYLOADS = [
    (['keygen', 'a&md pwned_keygen'], 'pwned_keygen'),           # keygen echoed the name unquoted
    (['new', 'a^&md.pwned_new'], '.pwned_new'),                   # caret reaches set ARGS=%ARGS% %1
    (['playtest', 'a^&md.pwned_play'], '.pwned_play'),            # ... and the playtest call set
    (['validate', 'x', 'a^&md.pwned_val'], '.pwned_val'),
    (['new', 'w', '--title', 'Fish&md pwned_title'], 'pwned_title'),
    (['sign', 'w', 'k.key', 'R&D|md pwned_pipe'], 'pwned_pipe'),
]


class SourceTests(unittest.TestCase):
    def test_guard_reads_raw_arguments_only_in_a_rem_line_before_any_expansion(self):
        guard = 'for %%a in (1) do rem #%*#'
        self.assertIn(guard, SOURCE)
        start = SOURCE.index(guard)
        for use in ('%~1', '%1', '%*', '%~2'):
            first = SOURCE.index(use)
            self.assertGreaterEqual(first, start, use + ' is expanded before the argument guard')
        self.assertIn('"%SystemRoot%\\System32\\findstr.exe" /r /c:"[&|<>^%%]" "%ARGV_FILE%" >nul', SOURCE)
        # findstr exits 1 for no match; anything else (match, or the check could not run) refuses
        self.assertIn('if "%ARGV_RC%"=="1" goto argv_ok', SOURCE)

    def test_no_known_sink_remains(self):
        self.assertNotIn('echo %K%', SOURCE)
        self.assertFalse('call set' in SOURCE.lower(), 'call set expands arguments twice')
        self.assertNotIn("'%NAME%'", FETCH_SOURCE)


@unittest.skipUnless(os.name == 'nt', 'runs the real cmd.exe launchers')
class WindowsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kit cmd injection ')
        self.dir = Path(self.tmp.name)
        self.work = self.dir / 'work'
        self.work.mkdir()
        stub = self.dir / 'stub browser.cmd'
        stub.write_bytes(b'@echo off\r\necho STUB %*\r\n')
        self.env = dict(os.environ, IAMAR_BROWSER=str(stub), IAMAR_KIT_NO_FETCH='1',
                        APPDATA=str(self.dir / 'appdata'), IAMAR_KIT_RUNTIME=str(self.dir / 'runtime'))
        self.env.pop('IAMAR_PROJECT', None)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, launcher, args):
        return subprocess.run([str(launcher)] + args, env=self.env, cwd=self.work,
                              capture_output=True, text=True, timeout=60)

    def test_done_when_cases_do_not_print_pwned(self):
        for args in (['keygen', 'a&echo PWNED'], ['new', 'w&echo PWNED']):
            r = self.run_cmd(LAUNCHER, args)
            self.assertNotIn('PWNED', r.stdout + r.stderr, args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn('refused', r.stderr, args)

    def test_payloads_never_run(self):
        for args, marker in PAYLOADS:
            r = self.run_cmd(LAUNCHER, args)
            self.assertFalse((self.work / marker).exists(), f'{args} ran: {r.stdout} {r.stderr}')
            self.assertNotIn('STUB', r.stdout, f'{args} reached the browser')

    def test_runtime_fetch_never_echoes_its_argument(self):
        r = self.run_cmd(FETCH, ['x&md pwned_fetch&rem'])
        self.assertFalse((self.work / 'pwned_fetch').exists(), r.stderr)
        self.assertEqual(r.returncode, 2)

    def test_ordinary_arguments_still_reach_the_browser(self):
        r = self.run_cmd(LAUNCHER, ['new', 'C:\\Program Files (x86)\\my world', '--title', "Mary's Inn!"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('world_new.gd "C:\\Program Files (x86)\\my world" --title "Mary\'s Inn!"', r.stdout)
        r = self.run_cmd(LAUNCHER, ['playtest', 'w', '--headless', 'x y'])
        self.assertIn('STUB --audio-driver Dummy --headless -- --kit-script res://scripts/kit/world_playtest.gd w "x y"', r.stdout)
        r = self.run_cmd(LAUNCHER, ['assets', 'search', '--worlds', 'oak tree'])
        self.assertIn('world_assets.gd search "oak tree"', r.stdout)
        r = self.run_cmd(LAUNCHER, ['where'])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_keygen_bare_name_and_path(self):
        r = self.run_cmd(LAUNCHER, ['keygen', 'me'])
        self.assertIn('keygen "' + str(self.dir / 'appdata' / 'iamar' / 'signing' / 'me.key') + '"', r.stdout)
        for path in ('C:\\keys\\me', 'keys/me', 'me.key'):
            r = self.run_cmd(LAUNCHER, ['keygen', path])
            self.assertIn('keygen "' + path + '"', r.stdout, path)


if __name__ == '__main__':
    unittest.main()
