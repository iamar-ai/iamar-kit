#!/usr/bin/env python3
"""Source/virtual-layout checks only; no cmd.exe, browser or tool is launched.

Run: python3 tests/creator_tool_bundle/test_windows_browser_discovery.py
IAMAR_TEST_SOURCE_ROOT may select a source snapshot. This deliberately small
evaluator accepts only the inspected IF/FOR selection grammar, not batch code
generally. Windows quoting, expansion, permissions and native launch remain unrun.
"""
import itertools
import ntpath
import os
from pathlib import Path
import re
import unittest

ROOT = Path(os.environ.get('IAMAR_TEST_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
SOURCE = (ROOT / 'kit/iamar-world.cmd').read_text()
DISPATCH = 'if /i "%CMD%"=="compile-typescript" goto cmd_compile_typescript'
PREFIX = 'if not defined IAMAR_BROWSER if not exist "%IAMAR_PROJECT%\\project.godot"'
PROBES = [line for line in SOURCE.splitlines()
          if line.startswith(PREFIX + ' if exist ')]


def normalized(path):
    return ntpath.normcase(ntpath.normpath(path))


class Discovery:
    """Execute only production discovery lines against virtual path existence."""
    def __init__(self, paths=(), env=None, directories=()):
        self.paths = {normalized(path) for path in paths}
        self.directories = {normalized(path) for path in directories}
        self.env = {'HERE': 'C:\\bundle\\kit\\', 'IAMAR_PROJECT': 'C:\\bundle'}
        self.env.update(env or {})

    def expand(self, value):
        return re.sub(r'%([A-Z_]+)%', lambda match: self.env.get(match[1], ''), value)

    def line(self, line):
        match = re.fullmatch(r'if not defined ([A-Z_]+) (.+)', line)
        if match:
            if not self.env.get(match[1]):
                self.line(match[2])
            return
        match = re.fullmatch(r'if (not )?exist "([^"]+)" (.+)', line)
        if match:
            path = self.expand(match[2])
            exists = normalized(path) in (self.directories if path.endswith('\\')
                                           else self.paths | self.directories)
            if exists != bool(match[1]):
                self.line(match[3])
            return
        match = re.fullmatch(r'for %%I in \("([^"]+)"\) do set "IAMAR_BROWSER=%%~fI"', line)
        if match:
            path = ntpath.normpath(self.expand(match[1]))
            if not ntpath.isabs(path):
                raise AssertionError('Only absolute fixture paths are supported')
            self.env['IAMAR_BROWSER'] = path
            return
        raise AssertionError('Unmodeled production statement: ' + line)

    def choose(self):
        for line in PROBES:
            self.line(line)
        return self.env.get('IAMAR_BROWSER')


class WindowsBrowserDiscoveryTests(unittest.TestCase):
    def test_exact_guarded_probe_order(self):
        expected = [
            PREFIX + ' if exist "%HERE%..\\iamar.exe" if not exist "%HERE%..\\iamar.exe\\" for %%I in ("%HERE%..\\iamar.exe") do set "IAMAR_BROWSER=%%~fI"',
            PREFIX + ' if exist "%HERE%..\\Oakhaven.exe" for %%I in ("%HERE%..\\Oakhaven.exe") do set "IAMAR_BROWSER=%%~fI"',
            PREFIX + ' if exist "%HERE%..\\iamar\\iamar.exe" if not exist "%HERE%..\\iamar\\iamar.exe\\" for %%I in ("%HERE%..\\iamar\\iamar.exe") do set "IAMAR_BROWSER=%%~fI"',
        ]
        self.assertEqual(PROBES, expected)

    def test_current_export_name_is_discovered(self):
        self.assertEqual(Discovery(['C:\\bundle\\iamar.exe']).choose(),
                         'C:\\bundle\\iamar.exe')

    def test_legacy_export_name_is_retained(self):
        self.assertEqual(Discovery(['C:\\bundle\\Oakhaven.exe']).choose(),
                         'C:\\bundle\\Oakhaven.exe')

    def test_side_by_side_unzip_layout_is_discovered(self):
        # Job 3971: the two downloads unzipped side by side give kit\ and iamar\iamar.exe.
        self.assertEqual(Discovery(['C:\\bundle\\iamar\\iamar.exe']).choose(),
                         'C:\\bundle\\iamar\\iamar.exe')
        self.assertIsNone(Discovery(directories=['C:\\bundle\\iamar\\iamar.exe']).choose())

    def test_modern_name_directory_cannot_shadow_valid_legacy(self):
        directories = ['C:\\bundle\\iamar.exe']
        self.assertEqual(Discovery(['C:\\bundle\\Oakhaven.exe'],
                                   directories=directories).choose(), 'C:\\bundle\\Oakhaven.exe')
        self.assertIsNone(Discovery(directories=directories).choose())

    def test_all_presence_combinations_prefer_current_name(self):
        names = ['C:\\bundle\\iamar.exe', 'C:\\bundle\\Oakhaven.exe', 'C:\\bundle\\iamar\\iamar.exe']
        for present in itertools.product((False, True), repeat=3):
            paths = [path for path, exists in zip(names, present) if exists]
            with self.subTest(present=present):
                self.assertEqual(Discovery(paths).choose(), paths[0] if paths else None)

    def test_explicit_override_is_authoritative_even_if_missing(self):
        paths = ['C:\\bundle\\iamar.exe', 'C:\\bundle\\Oakhaven.exe',
                 'C:\\bundle\\project.godot']
        for override in ('C:\\chosen browser\\custom.exe', 'C:\\missing.exe'):
            with self.subTest(override=override):
                self.assertEqual(Discovery(paths, {'IAMAR_BROWSER': override}).choose(), override)

    def test_source_project_precedes_automatic_browser_discovery(self):
        paths = ['C:\\bundle\\iamar.exe', 'C:\\bundle\\Oakhaven.exe']
        for project in ('C:\\bundle', 'D:\\source checkout'):
            with self.subTest(project=project):
                self.assertIsNone(Discovery(paths + [project + '\\project.godot'],
                                            {'IAMAR_PROJECT': project}).choose())

    def test_spaces_and_case_insensitive_virtual_paths(self):
        env = {'HERE': 'D:\\download with spaces\\KIT\\',
               'IAMAR_PROJECT': 'D:\\download with spaces'}
        model = Discovery(['d:\\DOWNLOAD WITH SPACES\\IAMAR.EXE'], env)
        self.assertEqual(model.choose(), 'D:\\download with spaces\\iamar.exe')

    def test_empty_windows_override_behaves_as_unset(self):
        self.assertEqual(Discovery(['C:\\bundle\\iamar.exe'],
                                   {'IAMAR_BROWSER': ''}).choose(), 'C:\\bundle\\iamar.exe')

    def test_compile_still_bypasses_discovery_and_native_operand_shift(self):
        self.assertEqual(SOURCE.count(DISPATCH), 1)
        self.assertLess(SOURCE.index(DISPATCH), SOURCE.index(PREFIX))
        self.assertLess(SOURCE.index(DISPATCH), SOURCE.index('\nshift\n'))
        compile_body = SOURCE.split(':cmd_compile_typescript\n', 1)[1].split('\n:end\n', 1)[0]
        self.assertNotIn('IAMAR_BROWSER', compile_body)

    def test_missing_browser_refusal_and_exemptions_are_preserved(self):
        guard = PREFIX + ' if /i not "%CMD%"=="help" if /i not "%CMD%"=="where" if /i not "%CMD%"=="blender" if /i not "%CMD%"=="blender-run" ('
        block = SOURCE.split(guard + '\n', 1)[1].split('\n)', 1)[0]
        self.assertIn('no iamar.exe beside this kit folder', block)
        self.assertIn('%HERE%..\\iamar\\iamar.exe', block)
        self.assertIn('IAMAR_BROWSER=C:\\path\\to\\iamar.exe', block)
        self.assertIn('\n  exit /b 2', block)
        self.assertLess(SOURCE.index(PROBES[-1]), SOURCE.index(guard))

    def test_model_refuses_uninspected_statements(self):
        with self.assertRaisesRegex(AssertionError, 'Unmodeled'):
            Discovery().line('call unexpected-helper.cmd')


if __name__ == '__main__':
    unittest.main(verbosity=2)
