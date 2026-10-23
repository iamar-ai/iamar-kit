#!/usr/bin/env python3
"""Read-only source contract for Windows guide/dispatch. No cmd/native execution."""
import os
from pathlib import Path
import unittest

ROOT = Path(os.environ.get('IAMAR_TEST_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
GUIDE = (ROOT / 'kit/AGENT_KIT.md').read_text()
WRAPPER = (ROOT / 'kit/iamar-world.cmd').read_text()
COMPILE = 'if /i "%CMD%"=="compile-typescript" goto cmd_compile_typescript'
NATIVE_GUARD = 'if not defined IAMAR_BROWSER if not exist "%IAMAR_PROJECT%\\project.godot"'


class WindowsGuideContractTests(unittest.TestCase):
    def test_compile_browser_independence_matches_early_dispatch(self):
        self.assertIn('runs independently of browser discovery and does not require `IAMAR_BROWSER`.', GUIDE)
        self.assertNotIn('before compilation when no source project is present', GUIDE)
        self.assertEqual(WRAPPER.count(COMPILE), 1)
        self.assertLess(WRAPPER.index(COMPILE), WRAPPER.index(NATIVE_GUARD))
        branch = WRAPPER.split(':cmd_compile_typescript\n', 1)[1].split('\n:end\n', 1)[0]
        self.assertNotIn('IAMAR_BROWSER', branch)

    def test_native_lookup_order_matches_current_then_legacy_names(self):
        self.assertIn('Otherwise the wrapper looks beside `kit/` for `iamar.exe`, then the legacy\n`Oakhaven.exe`, then in `iamar/` beside `kit/`', GUIDE)
        probes = [line for line in WRAPPER.splitlines()
                  if line.startswith(NATIVE_GUARD + ' if exist ')]
        current = [line for line in probes if '"%HERE%..\\iamar.exe"' in line]
        legacy = [line for line in probes if '"%HERE%..\\Oakhaven.exe"' in line]
        self.assertEqual(len(current), 1)
        self.assertEqual(len(legacy), 1)
        self.assertLess(WRAPPER.index(current[0]), WRAPPER.index(legacy[0]))
        unzipped = [line for line in probes if '"%HERE%..\\iamar\\iamar.exe"' in line]
        self.assertEqual(len(unzipped), 1)
        self.assertLess(WRAPPER.index(legacy[0]), WRAPPER.index(unzipped[0]))

    def test_native_override_and_source_project_precede_discovery(self):
        self.assertIn('Native kit commands use `IAMAR_BROWSER` when set, or the source project when present.', GUIDE)
        for executable in ['iamar.exe', 'Oakhaven.exe']:
            self.assertIn(NATIVE_GUARD + f' if exist "%HERE%..\\{executable}"', WRAPPER)
        self.assertIn('if defined IAMAR_BROWSER (set "RUN=', WRAPPER)
        self.assertIn('set "RUN="%GODOT%" --audio-driver Dummy --path "%IAMAR_PROJECT%"', WRAPPER)

    def test_custom_browser_filename_keeps_explicit_override_guidance(self):
        self.assertIn('For a different browser filename, set `IAMAR_BROWSER` to the actual\nabsolute executable path.', GUIDE)
        self.assertIn('In Windows cmd: `set "IAMAR_BROWSER=C:\\path\\to\\iamar.exe"`.', GUIDE)
        self.assertIn('"%IAMAR_BROWSER%" --audio-driver Dummy', WRAPPER)


if __name__ == '__main__':
    unittest.main(verbosity=2)
