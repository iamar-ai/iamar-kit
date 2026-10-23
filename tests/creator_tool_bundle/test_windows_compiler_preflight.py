#!/usr/bin/env python3
"""Source and finite path-selection model only; never launches cmd or a compiler.

The model executes only the inspected dependency/compiler selection statements,
using virtual file/directory sets. It is not a Windows command interpreter and
cannot qualify Windows quoting, permissions, junctions, PATHEXT or process launch.
"""
import hashlib
import itertools
import ntpath
import os
from pathlib import Path
import re
import unittest

ROOT = Path(os.environ.get('IAMAR_TEST_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
SOURCE = (ROOT / 'kit/iamar-world.cmd').read_text()
DISPATCH = 'if /i "%CMD%"=="compile-typescript" goto cmd_compile_typescript\n'


def section(start, end):
    return SOURCE.split(start, 1)[1].split(end, 1)[0]


class Selection:
    """Small fail-closed evaluator of only SET/IF/GOTO/WHERE selection lines."""
    def __init__(self, files=(), directories=(), env=None, path_nodes=(), old_nodes=(), fetched_node=None):
        self.files = {ntpath.normcase(ntpath.normpath(p)) for p in files}
        self.directories = {ntpath.normcase(ntpath.normpath(p)) for p in directories}
        self.env = {'HERE': 'C:\\bundle\\kit\\', 'IAMAR_PROJECT': 'C:\\source checkout'}
        self.env.update(env or {})
        self.path_nodes = path_nodes
        # Nodes whose major version is below 20 (:node20 fails), and what runtime_fetch.cmd prints.
        self.old_nodes = set(old_nodes)
        self.fetched_node = fetched_node
        self.jump = None

    def expand(self, value):
        return re.sub(r'%([A-Z_]+)%', lambda m: self.env.get(m[1], ''), value)

    def exists(self, path):
        # A trailing separator tests a directory in this finite model.
        normalized = ntpath.normcase(ntpath.normpath(path))
        if path.endswith('\\'):
            return normalized in self.directories
        return normalized in self.files or normalized in self.directories

    def line(self, line):
        line = line.strip()
        if not line or line.startswith('rem '):
            return
        match = re.fullmatch(r'if (not )?defined ([A-Z_]+) (.+)', line)
        if match:
            present = bool(self.env.get(match[2], ''))
            if present != bool(match[1]):
                self.line(match[3])
            return
        match = re.fullmatch(r'if (not )?exist "([^"]+)" (.+)', line)
        if match:
            if self.exists(self.expand(match[2])) != bool(match[1]):
                self.line(match[3])
            return
        match = re.fullmatch(r'set "([A-Z_]+)=(.*)"', line)
        if match:
            self.env[match[1]] = self.expand(match[2])
            return
        match = re.fullmatch(r'goto ([a-z_]+)', line)
        if match:
            self.jump = match[1]
            return
        match = re.fullmatch(r'call :node20 \|\| (.+)', line)
        if match:
            if self.env.get('NODE', '') in self.old_nodes:
                self.line(match[1])
            return
        fetch = 'for /f "usebackq delims=" %%P in (`call "%HERE%runtime_fetch.cmd" node`) do set "NODE=%%P"'
        if line == fetch:
            if self.fetched_node:
                self.env['NODE'] = self.fetched_node
            return
        # where.exe from System32, searching PATH only ($PATH:, never the current directory).
        expected = 'for /f "delims=" %%P in (\'%SystemRoot%\\System32\\where.exe $PATH:node 2^>nul\') do if not defined NODE set "NODE=%%P"'
        if line == expected:
            for path in self.path_nodes:
                if not self.env.get('NODE'):
                    self.env['NODE'] = path
            return
        raise AssertionError('Unmodeled production statement: ' + line)

    def lines(self, text):
        for line in text.splitlines():
            self.line(line)
            if self.jump:
                break

    def dependencies(self):
        block = section('rem Select one complete dependency set. An existing kit packer never borrows\n', ':compile_dependencies_selected\n')
        self.lines(block)
        if self.jump not in (None, 'compile_dependencies_selected'):
            raise AssertionError(self.jump)
        self.jump = None
        self.line(section(':compile_dependencies_selected\n', '\nfor %%F').strip())
        loop = section(':compile_dependencies_selected\n', '\nrem Resolve the compiler').split('for %%F in (', 1)[1].split('\n)', 1)[0]
        arguments, body = loop.split(') do (\n', 1)
        for path in re.findall(r'"([^"]+)"', arguments):
            for line in body.splitlines():
                self.line(line.replace('%%~F', self.expand(path)))
                if self.jump:
                    return self.jump
        return None

    def compiler_and_node(self):
        block = section('rem Resolve the compiler before any Node invocation; an explicit choice wins.\n', '\n"%NODE%" "%TSW%\\pack.mjs"')
        self.lines(block)
        return self.jump


class WindowsCompilerPreflightTests(unittest.TestCase):
    def test_compile_dispatch_precedes_native_browser_guard_and_argument_shift(self):
        self.assertEqual(SOURCE.count(DISPATCH), 1)
        self.assertLess(SOURCE.index(DISPATCH), SOURCE.index('if not defined IAMAR_BROWSER'))
        self.assertLess(SOURCE.index(DISPATCH), SOURCE.index('\nshift\n'))

    def test_original_three_operands_and_all_extras_have_explicit_guards(self):
        block = section(':cmd_compile_typescript\n', '\nrem Select one complete dependency set.')
        for index in range(1, 4):
            self.assertIn(f'set "A{index}=%~{index + 1}"', block)
            self.assertIn(f'if "%A{index}%"=="" goto compile_usage', block)
        self.assertIn('set "EXTRA=%~5"', block)
        self.assertIn('if defined EXTRA goto compile_usage', block)
        self.assertIn('if not "%5"=="" goto compile_usage', block)
        # A nonempty raw argument must never reach the second comparison.
        self.assertLess(block.index('if defined EXTRA'), block.index('if not "%5"'))
        self.assertNotIn('shift', '\n'.join(block.splitlines()[1:]))

    def test_from_source_retains_linux_only_diagnostic_before_operand_count(self):
        block = section(':cmd_compile_typescript\n', '\nrem Select one complete dependency set.')
        self.assertLess(block.index('if /i "%A1%"=="--from-source"'), block.index('if defined EXTRA'))
        self.assertIn('compile-typescript --from-source needs the Linux x86_64 source builder', block)

    def test_source_template_and_compiler_are_checked_as_files(self):
        for path, label in [('%A1%', 'compile_source_missing'), ('%A2%\\manifest.json', 'compile_template_missing'), ('%TSC%', 'compile_compiler_missing'), ('%NODE%', 'compile_node_missing')]:
            self.assertIn(f'if not exist "{path}" goto {label}', SOURCE)
            self.assertIn(f'if exist "{path}\\" goto {label}', SOURCE)

    def test_exact_launch_arguments_and_exit_code_propagation(self):
        self.assertIn('"%NODE%" "%TSW%\\pack.mjs" --source "%A1%" --sdk "%SDK%" --typescript "%TSC%" --prebuilt "%PREBUILT%" --template "%A2%" --out "%A3%"\nexit /b %ERRORLEVEL%', SOURCE)
        self.assertNotIn('IAMAR_BROWSER', section(':cmd_compile_typescript\n', '\n:end\n'))

    def test_compile_paths_disable_inherited_delayed_expansion_before_capture(self):
        guard = 'if /i "%~1"=="compile-typescript" setlocal DisableDelayedExpansion'
        self.assertIn(guard, SOURCE)
        self.assertLess(SOURCE.index(guard), SOURCE.index('set "HERE=%~dp0"'))
        self.assertEqual(SOURCE.count('DisableDelayedExpansion'), 1)

    def test_caller_errorlevel_variable_cannot_shadow_process_status(self):
        self.assertIn('set "ERRORLEVEL="\n"%NODE%" "%TSW%\\pack.mjs"', SOURCE)
        self.assertIn('exit /b %ERRORLEVEL%', section(':cmd_compile_typescript\n', '\n:end\n'))

    def test_unrelated_native_dispatch_is_byte_preserved(self):
        start = SOURCE.index(':cmd_compile_typescript\n')
        end = SOURCE.index('\n:end\n', start)
        projected = (SOURCE[:start] + SOURCE[end:]).replace(DISPATCH, '')
        projected = projected.replace('rem Keep literal exclamation marks in TypeScript paths, even under cmd /v:on.\nif /i "%~1"=="compile-typescript" setlocal DisableDelayedExpansion\n', '')
        projected = projected.replace('rem TypeScript packing is independent of the browser and native command setup.\n', '')
        self.assertEqual(hashlib.sha256(projected.encode()).hexdigest(), 'd548ffbdfb79721d597a7759f74784600baf328c48fb38b37d41d8d3526b92f2')

    def paths(self, source=False):
        base = 'C:\\source checkout\\tools\\typescript-world' if source else 'C:\\bundle\\kit\\ts-world'
        sdk = 'C:\\source checkout\\api\\typescript\\iamar-world.d.ts' if source else base + '\\iamar-world.d.ts'
        return [base + '\\pack.mjs', base + '\\prebuilt\\iamar_ts_guest.wasm', sdk]

    def test_all_64_kit_source_layouts_select_one_complete_set(self):
        kit, source = self.paths(), self.paths(True)
        for kit_mask, source_mask in itertools.product(range(8), repeat=2):
            with self.subTest(kit=kit_mask, source=source_mask):
                files = [p for mask, paths in [(kit_mask, kit), (source_mask, source)] for i, p in enumerate(paths) if mask & (1 << i)]
                model = Selection(files)
                chosen = kit if kit_mask & 1 else source
                complete = (kit_mask if kit_mask & 1 else source_mask) == 7
                self.assertEqual(model.dependencies(), None if complete else 'compile_dependencies_missing')
                self.assertEqual(model.env['SDK'], chosen[2])
                self.assertEqual(model.env['PREBUILT'], chosen[1])

    def test_directories_do_not_satisfy_selected_dependency_files(self):
        kit, source = self.paths(), self.paths(True)
        for index in range(3):
            model = Selection(kit[:index] + kit[index + 1:] + source, [kit[index]])
            self.assertEqual(model.dependencies(), 'compile_dependencies_missing')
            self.assertEqual(model.env['SDK'], kit[2])

    def configured(self, extra=(), env=None, directories=(), path_nodes=(), old_nodes=(), fetched_node=None):
        model = Selection(self.paths() + list(extra), directories, env, path_nodes, old_nodes, fetched_node)
        self.assertIsNone(model.dependencies())
        return model

    def test_package_compiler_precedes_loose_legacy_compiler(self):
        base = 'C:\\bundle\\kit\\ts-world'
        package = base + '\\node_modules\\typescript\\lib\\typescript.js'
        loose, node = base + '\\typescript.js', 'C:\\approved tools\\node.exe'
        for available, expected in [([package, loose], package), ([loose], loose)]:
            model = self.configured(available + [node], {'IAMAR_TS_NODE': node})
            self.assertIsNone(model.compiler_and_node())
            self.assertEqual(model.env['TSC'], expected)

    def test_invalid_explicit_compiler_never_falls_back_or_selects_node(self):
        bundled = 'C:\\bundle\\kit\\ts-world\\typescript.js'
        for explicit, dirs in [('C:\\missing.js', []), ('C:\\directory.js', ['C:\\directory.js'])]:
            model = self.configured([bundled], {'IAMAR_TS_COMPILER': explicit}, dirs, ['C:\\PATH node.exe'])
            self.assertEqual(model.compiler_and_node(), 'compile_compiler_missing')
            self.assertEqual(model.env['TSC'], explicit)
            self.assertNotIn('NODE', model.env)

    def test_node_selection_retains_explicit_path_and_refuses_missing_or_directory(self):
        compiler, node = 'C:\\approved tools\\typescript.js', 'C:\\approved tools\\node.exe'
        for valid, directories in [(True, []), (False, []), (False, [node])]:
            model = self.configured([compiler] + ([node] if valid else []), {'IAMAR_TS_COMPILER': compiler, 'IAMAR_TS_NODE': node}, directories, ['C:\\fallback.exe'])
            self.assertEqual(model.compiler_and_node(), None if valid else 'compile_node_missing')
            self.assertEqual(model.env['NODE'], node)
        model = self.configured([compiler, node], {'IAMAR_TS_COMPILER': compiler}, path_nodes=[node, 'C:\\later.exe'])
        self.assertIsNone(model.compiler_and_node())
        self.assertEqual(model.env['NODE'], node)

    def test_old_path_node_falls_back_to_fetched_runtime_node(self):
        compiler, old = 'C:\\approved tools\\typescript.js', 'C:\\old\\node.exe'
        fetched = 'C:\\bundle\\kit\\runtime\\node\\node.exe'
        env = {'IAMAR_TS_COMPILER': compiler}
        model = self.configured([compiler, old, fetched], env, path_nodes=[old], old_nodes=[old], fetched_node=fetched)
        self.assertIsNone(model.compiler_and_node())
        self.assertEqual(model.env['NODE'], fetched)
        # A current PATH node is kept and nothing is fetched.
        model = self.configured([compiler, old, fetched], env, path_nodes=[old], fetched_node=fetched)
        self.assertIsNone(model.compiler_and_node())
        self.assertEqual(model.env['NODE'], old)
        # No PATH node: the fetched one; nothing fetched either: refused.
        model = self.configured([compiler, fetched], env, fetched_node=fetched)
        self.assertIsNone(model.compiler_and_node())
        self.assertEqual(model.env['NODE'], fetched)
        model = self.configured([compiler, old], env, path_nodes=[old], old_nodes=[old])
        self.assertEqual(model.compiler_and_node(), 'compile_node_missing')
        self.assertNotIn(model.env.get('NODE'), (old, fetched))

    def test_explicit_node_is_never_version_replaced_or_fetched(self):
        compiler, node = 'C:\\approved tools\\typescript.js', 'C:\\approved tools\\node.exe'
        model = self.configured([compiler, node], {'IAMAR_TS_COMPILER': compiler, 'IAMAR_TS_NODE': node}, old_nodes=[node], fetched_node='C:\\fetched.exe')
        self.assertIsNone(model.compiler_and_node())
        self.assertEqual(model.env['NODE'], node)


if __name__ == '__main__':
    unittest.main(verbosity=2)
