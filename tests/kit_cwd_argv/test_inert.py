#!/usr/bin/env python3
"""Source/pure-helper model only. No engine, chdir, tool or world execution."""
import ast
import hashlib
import os
from pathlib import Path
import re
import unittest

def browser_source_root_text(value):
    """Validate selection before any source lookup; preserve nonblank path text."""
    if value is None or not value.strip():
        raise RuntimeError('Set IAMAR_BROWSER_SOURCE_ROOT to the matching browser source root')
    return value


# KitLoop belongs to the browser, not this standalone kit repository.
ROOT = Path(browser_source_root_text(os.environ.get('IAMAR_BROWSER_SOURCE_ROOT'))).resolve()
SOURCE = (ROOT / 'scripts/kit/kit_loop.gd').read_text()
SIGNATURE = 'static func _cwd_error(args: PackedStringArray) -> String:\n'
GUARD = '''\tvar cwd_error := _cwd_error(a.slice(2))
\tif cwd_error != "":
\t\t_fail(cwd_error)
\t\treturn
'''


def method_source(name, source=SOURCE):
    pattern = r'(?m)^(?:static )?func ' + re.escape(name) + r'\([^\n]*\n(?:\t[^\n]*\n|\n)*'
    matches = re.findall(pattern, source)
    assert len(matches) == 1, f'Missing unique method: {name}'
    return matches[0].rstrip('\n') + '\n'


def load_helper(source=SOURCE):
    assert source.count(SIGNATURE) == 1, 'Missing unique cwd preflight helper'
    body = method_source('_cwd_error', source).split(SIGNATURE, 1)[1]
    text = 'def cwd_error(args):\n' + body.replace('\t', '    ')
    text = re.sub(r'\bvar ([a-z_]+) := ', r'\1 = ', text)
    text = text.replace('args.size()', 'len(args)').replace('.begins_with(', '.startswith(')
    tree = ast.parse(text)
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.If,
               ast.BoolOp, ast.Or, ast.Name, ast.Load, ast.Store, ast.Subscript,
               ast.Constant, ast.Compare, ast.Eq, ast.Lt, ast.GtE, ast.Call,
               ast.Attribute, ast.Assign, ast.While, ast.Return, ast.BinOp,
               ast.Add, ast.AugAssign, ast.Continue)
    for node in ast.walk(tree):
        assert isinstance(node, allowed), f'Unexpected helper syntax: {type(node).__name__}'
        if isinstance(node, ast.Call):
            assert (isinstance(node.func, ast.Name) and node.func.id == 'len') or (
                isinstance(node.func, ast.Attribute) and node.func.attr == 'startswith')
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert all(isinstance(t, ast.Name) and t.id == 'i' for t in targets)
    namespace = {'__builtins__': {}, 'len': len}
    exec(compile(tree, '<exact cwd helper model>', 'exec'), namespace)
    return namespace['cwd_error']


def run_dispatch_prefix(raw, source=SOURCE):
    """Only the exact prefix before path selection; all effects are event sentinels."""
    prefix = method_source('_initialize', source).split('\n', 1)[1].split('\tvar path := ""\n', 1)[0]
    text = 'def preflight(raw):\n' + prefix.replace('\t', '    ')
    text = re.sub(r'\bvar ([a-z_]+) := ', r'\1 = ', text)
    for old, new in [('OS.get_cmdline_user_args()', 'raw'), ('a.is_empty()', 'not a'),
                     ('a.slice(2)', 'a[2:]'), ('PackagePrewarm.start()', 'prewarm()'),
                     ('_drop_game_scene()', 'drop_scene()')]:
        text = text.replace(old, new)
    text += '    dispatch_boundary()\n'
    tree = ast.parse(text)
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Assign,
               ast.Name, ast.Store, ast.Load, ast.Call, ast.If, ast.Compare,
               ast.NotEq, ast.Constant, ast.Expr, ast.Return, ast.BoolOp, ast.Or,
               ast.UnaryOp, ast.Not, ast.In, ast.List, ast.Subscript, ast.Slice)
    for node in ast.walk(tree):
        assert isinstance(node, allowed), f'Unexpected dispatcher-prefix syntax: {type(node).__name__}'
        if isinstance(node, ast.Call):
            assert isinstance(node.func, ast.Name)
            assert node.func.id in {'prewarm', 'drop_scene', '_cwd_error', '_fail', 'dispatch_boundary'}
    events = []
    namespace = {'__builtins__': {}, 'FLAG': '--kit', 'LEGACY_FLAG': '--kit-script',
                 '_cwd_error': load_helper(source),
                 'prewarm': lambda: events.append(('prewarm',)),
                 'drop_scene': lambda: events.append(('drop_scene',)),
                 '_fail': lambda message: events.append(('fail', message)),
                 'dispatch_boundary': lambda: events.append(('dispatch_boundary',))}
    exec(compile(tree, '<exact dispatcher prefix model>', 'exec'), namespace)
    namespace['preflight'](raw)
    return events


def legacy_strip(args):
    """Unchanged post-command stripping model; no process/environment behavior."""
    out = []
    i = 0
    while i < len(args):
        if args[i] == '--cwd' and i + 1 < len(args):
            i += 2
            continue
        if args[i].startswith('--cwd='):
            i += 1
            continue
        out.append(args[i])
        i += 1
    return out


def legacy_first_cwd(args):
    """Returns only selected raw text, never resolves or inspects a path."""
    for i, token in enumerate(args):
        if token == '--cwd' and i + 1 < len(args):
            return args[i + 1]
        if token.startswith('--cwd='):
            return token[6:]
    return None


class CwdArgvTests(unittest.TestCase):
    def test_browser_root_requires_an_explicit_nonblank_value(self):
        for value in [None, '', ' ', '\t', '\r\n', ' \t\n ']:
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'IAMAR_BROWSER_SOURCE_ROOT'):
                browser_source_root_text(value)
        for value in ['/browser', 'relative browser', ' /browser with spaces ']:
            self.assertEqual(browser_source_root_text(value), value)

    def check(self, args, valid):
        saved = list(args)
        before = legacy_strip(args), legacy_first_cwd(args)
        error = load_helper()(args)
        self.assertEqual(args, saved)
        self.assertEqual((legacy_strip(args), legacy_first_cwd(args)), before)
        self.assertEqual(error == '', valid, (args, error))
        self.assertLess(len(error), 100)
        return error

    def test_missing_empty_and_next_long_option_values_fail(self):
        for prefix in [[], ['world'], ['--cwd', '/first', 'world']]:
            self.check(prefix + ['--cwd'], False)
            self.check(prefix + ['--cwd='], False)
            for value in ['', '--cwd', '--cwd=/second', '--view', '--validate', '--help', '--unknown']:
                with self.subTest(prefix=prefix, value=value):
                    self.check(prefix + ['--cwd', value], False)

    def test_every_duplicate_is_checked_without_changing_first_wins(self):
        for first in [['--cwd', '/first'], ['--cwd=/first']]:
            for second in [['--cwd', '/second'], ['--cwd=/second']]:
                args = first + ['world'] + second
                self.check(args, True)
                self.assertEqual(legacy_first_cwd(args), '/first')
                self.assertEqual(legacy_strip(args), ['world'])
            for second in [['--cwd'], ['--cwd', ''], ['--cwd='], ['--cwd', '--frames', '1']]:
                self.check(first + ['world'] + second, False)
        for first in [['--cwd', ''], ['--cwd='], ['--cwd', '--unknown']]:
            self.check(first + ['--cwd', '/valid', 'world'], False)

    def test_valid_path_spellings_and_non_cwd_options_are_opaque(self):
        for value in ['/tmp/work', 'relative', '.', '..', './--literal', '-single',
                      'with spaces', '   ', 'Unicode 園', 'C:\\new world',
                      '\\\\host\\share', 'res://worlds', 'user://worlds', '~/worlds',
                      'a=b', 'quote"literal', 'bang!literal']:
            for args in [['--cwd', value, 'world'], ['world', '--cwd=' + value]]:
                self.check(args, True)
                self.assertEqual(legacy_first_cwd(args), value)
        for args in [[], ['world'], ['--unknown', 'text'], ['--cwdish', 'x'],
                     ['--cwd=--literal', 'world'], ['world', '--title', 'Use --cwd later']]:
            self.check(args, True)

    def test_legacy_failures_are_exposed_without_world_execution(self):
        self.assertEqual(legacy_strip(['world', '--cwd']), ['world', '--cwd'])
        self.assertIsNone(legacy_first_cwd(['world', '--cwd']))
        self.assertEqual(legacy_strip(['world', '--cwd', '--scripts']), ['world'])
        self.assertEqual(legacy_first_cwd(['world', '--cwd', '--scripts']), '--scripts')
        self.assertEqual(legacy_strip(['world', '--cwd=']), ['world'])
        self.assertEqual(legacy_first_cwd(['world', '--cwd=']), '')
        for args in [['world', '--cwd'], ['world', '--cwd', '--scripts'], ['world', '--cwd=']]:
            self.check(args, False)

    def test_fixed_diagnostic_does_not_echo_paths_or_tokens(self):
        secret = 'TOKEN=private-workspace'
        for args in [[secret, '--cwd'], [secret, '--cwd', '--' + secret]]:
            self.assertNotIn(secret, self.check(args, False))

    def test_guard_is_only_after_kit_recognition_and_scene_drop_before_load(self):
        init = method_source('_initialize')
        ordinary = ('\tif a.is_empty() or not a[0] in [FLAG, LEGACY_FLAG]:\n'
                    '\t\tPackagePrewarm.start()   # the game: warm the package into the OS file cache (L5)\n'
                    '\t\treturn\n')
        self.assertIn(ordinary, init)
        self.assertEqual(init.count('PackagePrewarm.start()'), 1)
        self.assertIn('\t_drop_game_scene()\n' + GUARD + '\tvar path := ""', init)
        self.assertLess(init.index(ordinary), init.index('_drop_game_scene()'))
        for boundary in ['_first_path(a.slice(2))', 'ensure_tool(path)', 'load(path)',
                         'set_script(s)', 'call("_initialize")']:
            self.assertLess(init.index(GUARD), init.index(boundary))
        self.assertEqual(method_source('_finalize'),
                         'func _finalize() -> void:\n\tPackagePrewarm.stop()\n')

    def test_reviewed_browser_dispatcher_and_unchanged_cwd_contracts(self):
        # Reviewed split-PCK loader, page dispatch and game-only prewarming.
        # Full provenance/diff is in the compatibility review accompanying this change.
        self.assertEqual(hashlib.sha256(SOURCE.encode()).hexdigest(),
                         'e87596b6089faea0c2b81d3c4ba47ed1d749effc44f13347e3a2d828ac06dedf')
        original_methods = {'_cwd_error': '80ea8aabd5566563936f75154a80b5397f8c510641c54dd25299c7fe2633a259', '_drop_game_scene': '4deb73719581c0d79a3374bf94deae4d923809f3ec4720a0bde841cb654dd1f5', '_fail': 'fb8ccabf8092147b61cb9f2a571129fc5d8c7afed6de9a7f3e858fe4b7835a26', 'user_args': 'ce1c26a9ce4c12295aee7b7eaf4dba27037374732b2bc0383fda664dacc9d2af', 'working_dir': '53c242365d86a97720120fd24f0b4768b19eebcd2409286a14541da645cc3cfa', 'absolute_path': 'c0fc4638ef82c29e7635cc62848723774d17233980473f92466fab94666bd539'}
        for name, expected in original_methods.items():
            with self.subTest(method=name):
                self.assertEqual(hashlib.sha256(method_source(name).encode()).hexdigest(), expected)

    def test_dispatch_prefix_keeps_game_and_invalid_kit_paths_separate(self):
        for raw in [[], ['world'], ['--cwd'], ['--unknown', '--cwd=']]:
            self.assertEqual(run_dispatch_prefix(raw), [('prewarm',)])
        for flag, command in [('--kit', 'new'), ('--kit', 'unknown'),
                              ('--kit', 'help'), ('--kit-script', 'res://scripts/kit/world_new.gd')]:
            for args in [['--cwd'], ['--cwd='], ['--cwd', '--view'],
                         ['--cwd', '/first', '--cwd']]:
                raw = [flag, command] + args
                saved = list(raw)
                events = run_dispatch_prefix(raw)
                self.assertEqual(raw, saved)
                self.assertEqual([event[0] for event in events], ['drop_scene', 'fail'])
                self.assertEqual(events[-1][1], 'kit: --cwd needs a nonempty folder (run --kit help)')
            self.assertEqual(run_dispatch_prefix([flag, command, 'world', '--cwd=/work']),
                             [('drop_scene',), ('dispatch_boundary',)])
        for raw in [['--kit'], ['--kit-script']]:
            self.assertEqual(run_dispatch_prefix(raw), [('drop_scene',), ('dispatch_boundary',)])

    def test_dispatch_missing_return_and_prewarm_scope_mutations_are_detected(self):
        invalid = ['--kit', 'new', 'world', '--cwd']
        mutated = SOURCE.replace(GUARD, GUARD.replace('\t\treturn\n', ''), 1)
        self.assertNotEqual(mutated, SOURCE)
        self.assertEqual(run_dispatch_prefix(invalid, mutated)[-1], ('dispatch_boundary',))
        mutated = SOURCE.replace('\t_drop_game_scene()\n',
                                 '\tPackagePrewarm.start()\n\t_drop_game_scene()\n', 1)
        self.assertIn(('prewarm',), run_dispatch_prefix(invalid, mutated))
        self.assertNotIn(('prewarm',), run_dispatch_prefix(invalid))
        mutated = SOURCE.replace('\t_drop_game_scene()\n', '', 1)
        self.assertNotIn(('drop_scene',), run_dispatch_prefix(invalid, mutated))
        self.assertEqual(run_dispatch_prefix(invalid)[0], ('drop_scene',))
        mutated = SOURCE.replace('\t\treturn\n', '', 1)
        self.assertEqual(run_dispatch_prefix([], mutated),
                         [('prewarm',), ('drop_scene',), ('dispatch_boundary',)])

    def test_option_value_guard_mutation_is_detectable(self):
        mutated = SOURCE.replace(' or args[i + 1].begins_with("--")', '', 1)
        self.assertNotEqual(mutated, SOURCE)
        helper = load_helper(mutated)
        for value in ['--cwd', '--cwd=/tmp', '--view', '--validate', '--unknown']:
            self.assertNotEqual(load_helper()(['world', '--cwd', value]), '')
            self.assertEqual(helper(['world', '--cwd', value]), '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
