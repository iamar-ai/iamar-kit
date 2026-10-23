#!/usr/bin/env python3
"""Creator raw-cwd caller guard model. No native/runtime/filesystem operations."""
import ast
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import unittest

def kit_source_root_text(value, default):
    """Only an omitted variable uses the default; explicit blanks fail closed."""
    if value is None:
        return default
    if not value.strip():
        raise RuntimeError('IAMAR_TEST_SOURCE_ROOT must be a nonblank kit source root')
    return value


MODEL_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(kit_source_root_text(os.environ.get('IAMAR_TEST_SOURCE_ROOT'), str(MODEL_ROOT))).resolve()
spec = importlib.util.spec_from_file_location('cwd_model', MODEL_ROOT / 'tests/kit_cwd_argv/test_inert.py')
cwd_model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cwd_model)
TOOLS = {
    'new': ('_initialize', '15eee7dea338269f0d56095aaa0f289ac4ac1eaa718ba509dff9b45146bc98dd'),  # an internal task author default, an internal task --from-brief
    'view': ('_init', '2a01caaee62e323a2507192956e24fdec55302bfb71ab8f2cf9a5a05b7cbe83b'),
}
GUARD_START = '\tvar cwd_error := KitLoop._cwd_error(OS.get_cmdline_user_args())\n'


def source_and_guard(tool):
    source = (ROOT / f'scripts/kit/world_{tool}.gd').read_text()
    method = TOOLS[tool][0]
    body = source.split(f'func {method}() -> void:\n', 1)[1]
    guard = body.split('\tvar args := KitLoop.user_args()\n', 1)[0]
    assert guard.startswith(GUARD_START), 'Missing raw-cwd guard before user_args'
    assert guard.endswith('\t\tquit(2)\n\t\treturn\n'), 'Missing immediate quit/return'
    return source, guard


def run_prefix(tool, raw, remove_return=False):
    """Translate the exact additive caller prefix; replaced APIs only record events."""
    _, guard = source_and_guard(tool)
    if remove_return:
        guard = guard.replace('\t\treturn\n', '', 1)
    text = 'def preflight(raw):\n' + guard.replace('\t', '    ')
    text = re.sub(r'\bvar ([a-z_]+) := ', r'\1 = ', text)
    text = text.replace('KitLoop._cwd_error(OS.get_cmdline_user_args())', 'parse_cwd_error(raw)')
    text += '    user_args()\n'
    tree = ast.parse(text)
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Assign,
               ast.Name, ast.Store, ast.Load, ast.Call, ast.If, ast.Compare,
               ast.NotEq, ast.Constant, ast.Expr, ast.Return)
    for node in ast.walk(tree):
        assert isinstance(node, allowed), f'Unexpected prefix syntax: {type(node).__name__}'
        if isinstance(node, ast.Call):
            assert isinstance(node.func, ast.Name)
            assert node.func.id in {'parse_cwd_error', 'printerr', 'quit', 'user_args'}
    events = []
    namespace = {
        '__builtins__': {},
        'parse_cwd_error': cwd_model.load_helper(),
        'printerr': lambda value: events.append(('stderr', value)),
        'quit': lambda status: events.append(('quit', status)),
        'user_args': lambda: events.append(('user_args',)),
    }
    exec(compile(tree, '<exact direct cwd prefix model>', 'exec'), namespace)
    namespace['preflight'](raw)
    return events


class DirectCwdTests(unittest.TestCase):
    def test_kit_root_defaults_only_when_omitted(self):
        default = '/local-kit'
        self.assertEqual(kit_source_root_text(None, default), default)
        for value in ['', ' ', '\t', '\r\n', ' \t\n ']:
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'IAMAR_TEST_SOURCE_ROOT'):
                kit_source_root_text(value, default)
        for value in ['/other-kit', 'relative kit', ' /kit with spaces ']:
            self.assertEqual(kit_source_root_text(value, default), value)

    def test_invalid_raw_arguments_never_reach_global_stripping(self):
        invalid = [
            ['world', '--cwd'], ['world', '--cwd', ''], ['world', '--cwd='],
            ['world', '--cwd', '--title'], ['world', '--cwd', '--size', '1x1'],
            ['world', '--cwd', '/valid', '--cwd'],
            ['world', '--cwd=', '--cwd', '/valid'],
            ['world', '--cwd', '--cwd=/valid'],
        ]
        for tool in TOOLS:
            for prefix in [[], ['--kit', 'new' if tool == 'new' else 'validate'],
                           ['--kit-script', f'res://scripts/kit/world_{tool}.gd']]:
                for args in invalid:
                    raw = prefix + args
                    saved = list(raw)
                    with self.subTest(tool=tool, raw=raw):
                        events = run_prefix(tool, raw)
                        self.assertEqual(raw, saved)
                        self.assertEqual([e[0] for e in events], ['stderr', 'stderr', 'quit'])
                        self.assertTrue(events[0][1].startswith('usage: '))
                        self.assertEqual(events[1][1], 'kit: --cwd needs a nonempty folder (run --kit help)')
                        self.assertEqual(events[-1], ('quit', 2))

    def test_valid_raw_arguments_reach_unchanged_existing_parser(self):
        valid = [
            ['world'], ['--cwd', '/work', 'world'], ['world', '--cwd=/work'],
            ['world', '--cwd', 'relative'], ['world', '--cwd', 'with spaces'],
            ['world', '--cwd', 'Unicode 園'], ['world', '--cwd', '-literal'],
            ['world', '--cwd=--literal'], ['world', '--cwd', '   '],
            ['world', '--cwd', '/first', '--cwd=/second'],
        ]
        for tool in TOOLS:
            for raw in valid:
                saved = list(raw)
                with self.subTest(tool=tool, raw=raw):
                    self.assertEqual(run_prefix(tool, raw), [('user_args',)])
                    self.assertEqual(raw, saved)

    def test_reviewed_creator_sources_excluding_cwd_guard_are_pinned(self):
        # world_new adds --template (an internal task); world_view includes reviewed page checks
        # and entered-tree ScriptPreview custody (see accompanying provenance).
        for tool, (_, expected) in TOOLS.items():
            source, guard = source_and_guard(tool)
            self.assertEqual(source.count(guard), 1)
            projected = source.replace(guard, '', 1)
            self.assertEqual(hashlib.sha256(projected.encode()).hexdigest(), expected)

    def test_guard_precedes_path_scaffold_package_and_renderer_work(self):
        for tool in TOOLS:
            source, guard = source_and_guard(tool)
            body = source.split(f'func {TOOLS[tool][0]}() -> void:\n', 1)[1]
            self.assertTrue(body.startswith(guard + '\tvar args := KitLoop.user_args()\n'))
            self.assertLess(body.index(guard), body.index('_argv_error(args)'))
            boundary = 'WorldScaffold.create(' if tool == 'new' else 'WorldPackage.open('
            self.assertLess(body.index(guard), body.index(boundary))

    def test_creator_argument_preflight_remains_exact_and_terminating(self):
        original_argv = {'new': '5ab455c86f7f1cfecaad9c57a9213b3fc2469c77cb0616217b71f980cf181ff8', 'view': '9d495e44b0ffb93447571a54f184adfab460a9a97e1ba918815bcc5c337a0a98'}
        for tool, expected in original_argv.items():
            source, guard = source_and_guard(tool)
            self.assertEqual(hashlib.sha256(cwd_model.method_source('_argv_error', source).encode()).hexdigest(), expected)
            body = source.split(f'func {TOOLS[tool][0]}() -> void:\n', 1)[1]
            argument_guard = body.split('\tvar argument_error := _argv_error(args)\n', 1)[1]
            argument_guard = argument_guard.split('\t\treturn\n', 1)[0] + '\t\treturn\n'
            self.assertTrue(argument_guard.startswith('\tif argument_error != "":\n'))
            self.assertTrue(argument_guard.endswith('\t\tprinterr(argument_error)\n\t\tquit(2)\n\t\treturn\n'))
            for boundary in (['var dir := _abs(args[0])', 'WorldScaffold.create('] if tool == 'new'
                             else ['var pos: Array', 'WorldPackage.open(', 'PageCheck.check_package(', '_pkg.build(']):
                self.assertLess(body.index(argument_guard), body.index(boundary))

    def test_missing_return_mutation_allows_continuation_and_is_detected(self):
        for tool in TOOLS:
            self.assertEqual(run_prefix(tool, ['world', '--cwd'])[-1], ('quit', 2))
            self.assertEqual(run_prefix(tool, ['world', '--cwd'], remove_return=True)[-1], ('user_args',))

    def test_diagnostics_never_reflect_private_operand_text(self):
        secret = 'PRIVATE_WORKSPACE_TOKEN'
        for tool in TOOLS:
            events = run_prefix(tool, [secret, '--cwd', '--' + secret])
            self.assertNotIn(secret, repr(events))

    def test_published_helper_dependency_is_exact(self):
        # Browser-owned helper comes from the explicit IAMAR_BROWSER_SOURCE_ROOT.
        helper = cwd_model.method_source('_cwd_error').encode()
        self.assertEqual(hashlib.sha256(helper).hexdigest(),
                         '80ea8aabd5566563936f75154a80b5397f8c510641c54dd25299c7fe2633a259')


if __name__ == '__main__':
    unittest.main(verbosity=2)
