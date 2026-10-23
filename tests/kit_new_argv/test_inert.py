#!/usr/bin/env python3
"""Exact pure-helper control-flow model; never creates a world or launches Godot."""
import ast
import hashlib
import os
from pathlib import Path
import re
import unittest

ROOT = Path(os.environ.get('IAMAR_TEST_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
SOURCE = (ROOT / 'scripts/kit/world_new.gd').read_text()
MARKER = '## Reject incomplete CLI requests before resolving paths or creating a draft.\n'
SIGNATURE = 'static func _argv_error(args: PackedStringArray) -> String:\n'
CWD_GUARD = '\tvar cwd_error := KitLoop._cwd_error(OS.get_cmdline_user_args())\n\tif cwd_error != "":\n\t\tprinterr("usage: new <folder> [--id id] [--title title] [--author name] [--template meadow|beach|interior|forest|town] [--from-brief brief.json]")\n\t\tprinterr(cwd_error)\n\t\tquit(2)\n\t\treturn\n'
GUARD = '''\tvar argument_error := _argv_error(args)
\tif argument_error != "":
\t\tprinterr("usage: new <folder> [--id id] [--title title] [--author name] [--template meadow|beach|interior|forest|town] [--from-brief brief.json]")
\t\tprinterr(argument_error)
\t\tquit(2)
\t\treturn
'''


def load_helper():
    assert SOURCE.count(SIGNATURE) == 1, 'Missing unique argv preflight helper'
    body = SOURCE.split(SIGNATURE, 1)[1].split('\n\nfunc _initialize()', 1)[0]
    text = 'def argv_error(args):\n' + body.replace('\t', '    ')
    text = re.sub(r'\bvar ([a-z_]+) := ', r'\1 = ', text)
    text = text.replace('args.is_empty()', 'not args').replace('args.size()', 'len(args)')
    text = text.replace('.begins_with(', '.startswith(')
    tree = ast.parse(text)
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.If,
               ast.BoolOp, ast.Or, ast.And, ast.UnaryOp, ast.Not, ast.Name,
               ast.Load, ast.Store, ast.Subscript, ast.Constant, ast.Compare,
               ast.Eq, ast.Lt, ast.GtE, ast.In, ast.Call, ast.Attribute,
               ast.Assign, ast.While, ast.List, ast.Return, ast.BinOp,
               ast.Add, ast.AugAssign)
    for node in ast.walk(tree):
        assert isinstance(node, allowed), f'Unexpected helper syntax: {type(node).__name__}'
        if isinstance(node, ast.Call):
            assert (isinstance(node.func, ast.Name) and node.func.id == 'len') or (
                isinstance(node.func, ast.Attribute) and node.func.attr == 'startswith')
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert all(isinstance(t, ast.Name) and t.id == 'i' for t in targets)
    namespace = {'__builtins__': {}, 'len': len}
    exec(compile(tree, '<exact new argv helper model>', 'exec'), namespace)
    return namespace['argv_error']


def old_options(args):
    """Finite model of the preserved legacy option loop; no scaffold or filesystem."""
    opt = {}
    for index in range(1, len(args) - 1):
        if args[index].startswith('--'):
            opt[args[index][2:]] = args[index + 1]
    return opt


class NewArgvTests(unittest.TestCase):
    def check(self, args, valid):
        saved = list(args)
        old = old_options(args)
        result = load_helper()(args)
        self.assertEqual(args, saved)
        self.assertEqual(old_options(args), old)
        self.assertEqual(result == '', valid, (args, result))
        self.assertLess(len(result), 100)
        return result

    def test_trailing_flags_are_refused_instead_of_silently_discarded(self):
        for option in ['--id', '--title', '--author', '--template', '--from-brief']:
            for prefix in [[], ['--title', 'A garden'], ['--id', 'garden', '--author', 'Builder']]:
                args = ['draft'] + prefix + [option]
                with self.subTest(args=args):
                    self.check(args, False)
                    # The old loop silently drops the final token and still
                    # reaches WorldScaffold.create with defaults/prior values.
                    self.assertEqual(old_options(args), old_options(args[:-1]))

    def test_empty_values_and_missing_folder_do_not_reach_scaffold(self):
        for option in ['--id', '--title', '--author', '--template', '--from-brief']:
            self.check(['draft', option, ''], False)
        for args in [[], [''], ['--title', 'Garden'], ['--author', 'Builder'], ['--id', 'garden'], ['--help']]:
            self.check(args, False)

    def test_unknown_options_and_extra_positionals_fail(self):
        for args in [['draft', 'extra'], ['draft', '--unknown', 'value'], ['draft', '--titel', 'Garden'],
                     ['draft', '--title', 'Garden', 'extra'], ['draft', '--title', '--author', 'Builder'],
                     ['draft', '--id=garden'], ['draft', '--'], ['draft', '--templates', 'beach'], ['draft', '--from_brief', 'b.json'],
                     ['draft', '--template', 'beach', 'extra']]:
            self.check(args, False)

    def test_options_cannot_be_reinterpreted_as_option_values(self):
        for option in ['--id', '--title', '--author', '--template', '--from-brief']:
            for value in ['--id', '--title', '--author', '--template', '--from-brief', '--unknown', '--']:
                for suffix in [[], ['--author', 'Builder']]:
                    args = ['draft', option, value] + suffix
                    with self.subTest(args=args):
                        self.check(args, False)

    def test_valid_defaults_pairs_order_duplicates_and_opaque_values_are_unchanged(self):
        rows = [
            ['draft'], ['draft', '--title', 'A garden'], ['draft', '--id', 'garden'],
            ['draft', '--author', 'Builder'],
            ['draft', '--author', 'A', '--id', 'garden', '--title', 'Garden'],
            ['draft', '--title', 'First', '--title', 'Second'],
            ['draft', '--id', 'first', '--id', 'second'],
            ['draft', '--author', 'First', '--author', 'Second'],
            ['folder with spaces', '--title', 'A "quoted" world', '--author', 'A & B'],
            ['C:\\worlds\\new world', '--title', 'Unicode 園', '--author', 'Zoë'],
            ['./--draft', '--title', '-banner', '--author', 'Builder'],
            ['draft', '--title', 'Use --author for the author'],
            # Identity/text semantics remain with WorldScaffold, not this guard.
            ['draft', '--title', '   ', '--id', 'NOT_A_VALID_ID'],
            ['draft', '--template', 'beach'], ['draft', '--id', 'shore', '--template', 'interior'],
            # The template name is checked against the browser's WorldScaffold.TEMPLATES, not here.
            ['draft', '--template', 'no_such_template'],
            # --from-brief (iamar-creator-ux an internal task): the brief file is read after this guard.
            ['draft', '--from-brief', 'brief.json'], ['draft', '--from-brief', 'b.json', '--template', 'beach', '--id', 'shore'],
        ]
        for args in rows:
            with self.subTest(args=args):
                self.check(args, True)
        self.assertEqual(old_options(rows[5])['title'], 'Second')

    def test_diagnostics_do_not_reflect_user_paths_or_flags(self):
        secret = 'TOKEN=private-name'
        for args in [[secret, '--' + secret, 'value'], [secret, '--title'], [secret, 'extra']]:
            self.assertNotIn(secret, self.check(args, False))

    def test_error_returns_before_path_resolution_defaults_or_scaffold(self):
        init = SOURCE.split('func _initialize() -> void:\n', 1)[1].replace(CWD_GUARD, '', 1)
        self.assertTrue(init.startswith('\tvar args := KitLoop.user_args()\n' + GUARD))
        for boundary in ['var dir := _abs(args[0])', 'var opt := {}', 'WorldScaffold.create(']:
            self.assertLess(init.index(GUARD), init.index(boundary))
        self.assertIn('\t\tquit(2)\n\t\treturn\n', GUARD)

    def test_author_default_never_reads_the_os_login_name(self):
        # kit-9 (iamar-sec-kit an internal task): author.name is signed into the pack and shown
        # to every visitor, so omitting --author must not publish $USER/%USERNAME%.
        init = SOURCE.split('func _initialize() -> void:\n', 1)[1]
        for name in ['USER', 'USERNAME', 'LOGNAME']:
            self.assertNotIn('get_environment("%s")' % name, SOURCE)
        self.assertNotIn('get_environment(', init)
        self.assertEqual(init.count('var author := String(opt.get("author", "World builder"))\n'), 1)

    def test_original_cli_defaults_scaffold_call_and_reporting_are_byte_preserved(self):
        self.assertEqual(SOURCE.count(MARKER), 1)
        before, rest = SOURCE.split(MARKER, 1)
        after = rest.split('func _initialize() -> void:\n', 1)[1]
        projected = before + 'func _initialize() -> void:\n' + after.replace(CWD_GUARD, '', 1).replace(GUARD, '', 1)
        # re-pinned for --template (iamar-creator-ux an internal task), the login-name-free author default (iamar-sec-kit an internal task)
        # and --from-brief (iamar-creator-ux an internal task)
        self.assertEqual(hashlib.sha256(projected.encode()).hexdigest(), 'b91942c1584f44b00ce1e62219c52ecf1523a4c186cffeadd0dc314b5c165fa2')


if __name__ == '__main__':
    unittest.main(verbosity=2)
