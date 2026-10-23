#!/usr/bin/env python3
"""Pure exact-helper control-flow model and source checks, never Godot or a world.

Translate only the inspected _argv_error helper's small syntax subset to Python.
Godot string predicates have explicit finite test doubles. No native/parser,
package, compiler, renderer, script, subprocess or network is invoked.
"""
import ast
import hashlib
import math
import os
from pathlib import Path
import re
import unittest

def source_root_text(value, name, default=None):
    """Reject explicit blank roots before lookup; preserve nonblank path text."""
    if value is None and default is not None:
        return default
    if value is None or not value.strip():
        raise RuntimeError("Set " + name + " to a nonblank source checkout path")
    return value


ROOT = Path(source_root_text(os.environ.get("IAMAR_TEST_SOURCE_ROOT"),
                             "IAMAR_TEST_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
SOURCE = (ROOT / 'scripts/kit/world_view.gd').read_text()
MARKER = '## Syntax-only preflight. Preserve the original arguments and all downstream\n'
SIGNATURE = 'static func _argv_error(args: PackedStringArray) -> String:\n'
CWD_GUARD = '\tvar cwd_error := KitLoop._cwd_error(OS.get_cmdline_user_args())\n\tif cwd_error != "":\n\t\tprinterr("usage: world_view.gd -- [--validate] <package> [out_prefix] [--view x,y,z>lx,ly,lz] [--npcs mode] [--tier t] [--frames n] [--size widthxheight]")\n\t\tprinterr(cwd_error)\n\t\tquit(2)\n\t\treturn\n'
GUARD = '''\tvar argument_error := _argv_error(args)
\tif argument_error != "":
\t\tprinterr("usage: world_view.gd -- [--validate] <package> [out_prefix] [--view x,y,z>lx,ly,lz] [--npcs mode] [--tier t] [--frames n] [--size widthxheight]")
\t\tprinterr(argument_error)
\t\tquit(2)
\t\treturn
'''


def godot_float_predicate(text):
    # Source-derived double of Godot 4.5-stable String::is_valid_float(),
    # core/string/ustring.cpp lines 4773-4808. It permits incomplete exponents.
    if not text:
        return False
    start = 1 if text[0] in '+-' else 0
    exponent = period = sign = exponent_digits = mantissa_digits = False
    for char in text[start:]:
        if '0' <= char <= '9':
            if exponent:
                exponent_digits = True
            else:
                mantissa_digits = True
        elif mantissa_digits and not exponent and char in 'eE':
            exponent = True
        elif not period and not exponent and char == '.':
            period = True
        elif char in '+-' and exponent and not exponent_digits and not sign:
            sign = True
        else:
            return False
    return mantissa_digits


def godot_float_model(text):
    # The upstream converter returns the finite mantissa for an empty exponent.
    # Cover that specific behavior instead of hiding it behind Python float().
    incomplete = re.fullmatch(r'(.+)[eE][+-]?', text.strip())
    return float(incomplete[1] if incomplete else text)


def load_helper(source=SOURCE):
    assert source.count(SIGNATURE) == 1, 'Missing unique argv preflight helper'
    helper = source.split(SIGNATURE, 1)[1].split('\n\nfunc _init()', 1)[0]
    translated = 'def argv_error(args):\n' + helper
    translated = translated.replace('\t', '    ')
    translated = re.sub(r'\bvar ([a-z_]+) := ', r'\1 = ', translated)
    translated = re.sub(r'\btrue\b', 'True', translated)
    translated = re.sub(r'\bfalse\b', 'False', translated)
    translated = re.sub(r'([a-z_]+)\.size\(\)', r'len(\1)', translated)
    translated = translated.replace('String(', 'str(').replace('.begins_with(', '.startswith(')
    translated = translated.replace('.strip_edges()', '.strip()').replace('.to_lower()', '.lower()')
    translated = re.sub(r'([a-z_]+)\.substr\(exponent \+ 1\)\.is_valid_int\(\)', r'valid_int(\1[exponent + 1:])', translated)
    translated = re.sub(r'([a-z_]+)\.is_valid_float\(\)', r'valid_float(\1)', translated)
    translated = re.sub(r'([a-z_]+)\.strip\(\)\.is_valid_float\(\)', r'valid_float(\1.strip())', translated)
    translated = re.sub(r'([a-z_]+)\.strip\(\)\.is_valid_int\(\)', r'valid_int(\1.strip())', translated)
    translated = translated.replace(', True)', ')')  # split keeps empty components.
    tree = ast.parse(translated)
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Assign,
               ast.Name, ast.Load, ast.Store, ast.Constant, ast.While, ast.Compare,
               ast.Lt, ast.Gt, ast.GtE, ast.Eq, ast.NotEq, ast.In, ast.Call,
               ast.Subscript, ast.If, ast.List, ast.BinOp, ast.Add, ast.Return,
               ast.BoolOp, ast.Or, ast.And, ast.Attribute, ast.For, ast.UnaryOp,
               ast.Not, ast.AugAssign, ast.Slice)
    for node in ast.walk(tree):
        assert isinstance(node, allowed), f'Unexpected helper syntax: {type(node).__name__}'
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id in {'len', 'str', 'valid_float', 'valid_int', 'float', 'is_finite'}
            else:
                assert isinstance(node.func, ast.Attribute)
                assert node.func.attr in {'split', 'strip', 'startswith', 'lower', 'find'}
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert all(isinstance(t, ast.Name) and t.id != 'args' for t in targets)
    namespace = {
        '__builtins__': {}, 'len': len, 'str': str, 'float': godot_float_model,
        'is_finite': math.isfinite,
        'valid_int': lambda s: re.fullmatch(r'[+-]?[0-9]+', s) is not None,
        'valid_float': godot_float_predicate,
    }
    exec(compile(tree, '<exact argv helper model>', 'exec'), namespace)
    return namespace['argv_error']


class ViewArgvTests(unittest.TestCase):
    def test_source_root_selection_rejects_explicit_blank_overrides(self):
        default = Path("kit-default")
        self.assertEqual(source_root_text(None, "IAMAR_TEST_SOURCE_ROOT", default), default)
        for value in ["", " ", "\t\n"]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "IAMAR_TEST_SOURCE_ROOT"):
                    source_root_text(value, "IAMAR_TEST_SOURCE_ROOT", default)
        for value in ["source checkout", " source checkout "]:
            self.assertEqual(source_root_text(value, "IAMAR_TEST_SOURCE_ROOT", default), value)

    def check(self, args, valid):
        original = list(args)
        result = load_helper()(args)
        self.assertEqual(args, original, 'preflight mutated argument representations')
        self.assertIsInstance(result, str)
        self.assertEqual(result == '', valid, (args, result))
        self.assertLess(len(result), 100)
        return result

    def test_all_value_options_missing_empty_or_followed_by_a_flag(self):
        for option in ['--view', '--npcs', '--tier', '--frames', '--size', '--quest-done']:
            for tail in [[], [''], ['--validate'], ['--size', '800x600']]:
                with self.subTest(option=option, tail=tail):
                    self.check(['--validate', 'saved world', option] + tail, False)

    def test_missing_extra_empty_and_unknown_operands(self):
        for args in [[], ['--validate'], [''], ['world', ''], ['a', 'b', 'c'], ['--unknown', 'world'], ['world', '--unknown'], ['world', '--'], ['world', '--view=0,0,0>1,1,1']]:
            with self.subTest(args=args):
                self.check(args, False)

    def test_malformed_view_shapes(self):
        values = ['0,0,0', '>', '0,0,0>', '>1,1,1', '0,0>1,1,1', '0,0,0>1,1',
                  '0,0,0,0>1,1,1', '0,0,0>1,1,1>2,2,2', '0,,0>1,1,1', '0,0,0>1,,1',
                  'a,0,0>1,1,1', '0,0,0>1,1,word', '0,0,0>1,1,1junk', '0,0,0>1,1,NaN',
                  'inf,0,0>1,1,1', '1e999,0,0>1,1,1']
        for value in values:
            with self.subTest(value=value):
                self.check(['world', 'shots', '--view', value], False)

    def test_incomplete_exponents_reject_at_all_six_positions_with_engine_predicate(self):
        guard = '\t\t\t\t\t\tif exponent >= 0 and not number.substr(exponent + 1).is_valid_int():\n\t\t\t\t\t\t\treturn "--view exponents must contain integer digits."\n'
        self.assertIn(guard, SOURCE)
        without_guard = load_helper(SOURCE.replace(guard, '', 1))
        for number in ['1e', '1e+', '1e-', '2E', '2E+', '2E-']:
            self.assertTrue(godot_float_predicate(number))
            self.assertTrue(math.isfinite(godot_float_model(number)))
            for index in range(6):
                axes = ['0', '0', '0', '1', '1', '1']
                axes[index] = number
                view = ','.join(axes[:3]) + '>' + ','.join(axes[3:])
                with self.subTest(number=number, component=index):
                    args = ['world', 'shots', '--view', view]
                    self.check(args, False)
                    self.assertEqual(without_guard(args), '')

    def test_malformed_size_and_frames_syntax(self):
        for value in ['800', 'x600', '800x', 'x', '800x600x1', '800X600', '8.5x600', 'eightx600', '800x600junk']:
            with self.subTest(size=value):
                self.check(['world', 'shots', '--size', value], False)
        for value in ['1.5', '1e2', 'NaN', '+', '60junk']:
            with self.subTest(frames=value):
                self.check(['world', 'shots', '--frames', value], False)

    def test_valid_inputs_keep_every_argument_byte_and_existing_numeric_policy(self):
        rows = [
            ['saved world'], ['--validate', 'saved world'], ['saved world', 'shot prefix'],
            ['--validate', 'saved world', 'optional ignored prefix'],
            ['world', '--view', '-1,2.5,3e2>+4,.5,-6.'],
            ['world', 'shots', '--view', ' 0, 2,12 > 0,1,0 ', '--view', '1,2,3>4,5,6'],
            ['world', '--frames', '60', '--frames', '+0003', '--size', ' 1280 x 720 '],
            # Syntax preflight introduces no new frame-count or renderer-size policy.
            ['world', '--frames', '0', '--size', '0x0'],
            ['world', '--frames', '-1', '--size', '-1x-1'],
            ['world', '--tier', 'low', '--tier', 'custom-tier', '--npcs', 'custom-mode'],
            ['--report-v1', '--validate', 'world'], ['world', '--validate', '--report-v1'],
            ['./--package', 'shots'], ['C:\\worlds\\my world', 'C:\\shots\\my view'],
        ]
        for args in rows:
            with self.subTest(args=args):
                self.check(args, True)

    def test_report_without_validate_preserves_existing_refusal(self):
        self.check(['world', '--report-v1'], False)
        self.check(['world', 'shots', '--report-v1'], False)

    def test_diagnostics_do_not_reflect_authored_paths_or_option_values(self):
        secret = 'TOKEN=private-path'
        for args in [[secret, '--' + secret], [secret, '--view', secret], [secret, '--size', secret]]:
            self.assertNotIn(secret, self.check(args, False))

    def test_guard_precedes_state_mutation_package_open_and_execution(self):
        init = SOURCE.split('func _init() -> void:\n', 1)[1].split('\nfunc ', 1)[0].replace(CWD_GUARD, '', 1)
        self.assertTrue(init.startswith('\tvar args := KitLoop.user_args()\n' + GUARD))
        for downstream in ['var pos: Array', 'WorldPackage.open(', '_pkg.build(']:
            self.assertLess(init.index(GUARD), init.index(downstream))
        self.assertNotIn('PackageScriptHost.attach(', SOURCE)
        self.assertNotIn('ScriptPreview.attach(', init)
        process = SOURCE.split('func _process(', 1)[1].split('\nfunc ', 1)[0]
        self.assertIn('ScriptPreview.attach(_pkg, _world, root)', process)
        self.assertIn('\t\tquit(2)\n\t\treturn\n', GUARD)

    def test_reviewed_parser_and_downstream_snapshot_are_byte_preserved(self):
        # Kit b2707865: re-reviewed from argv baseline ad8f4266. The only
        # downstream changes are cwd preflight, playerless preview lifecycle,
        # and UI-page validation. Keep a full snapshot fence, not a loose match.
        # Re-fenced 2026-10-20 (an agent, an internal task) after reviewing both deltas: 8754574
        # (header comment: worlds/mission_hall examples) and the windowed --size fix in
        # _process (window_set_size; preview ignored --size without --resolution).
        # Re-fenced 2026-10-20 (an agent, an internal task) after reviewing both deltas: c44610e
        # (FrameSpike worst frame, one re-measure of an over-limit view, WORST_FRAME line)
        # and 7776df4 (auto views from ViewBounds.frame_box/ring_views; _bounds removed).
        # Re-fenced 2026-10-21 (an agent, an internal task, author of the delta; review job
        # filed): --quest-done option, _attach_quest_effects after _pkg.build (QuestEffects
        # loaded by path, fixed quest state), header comment.
        # Re-fenced 2026-10-22 (an agent, an internal task, author of the delta): no timed frame
        # prints "NOT MEASURED" / fps "not measured" instead of PASS 0.0.
        # Re-fenced 2026-10-22 (an agent, an internal task, author of the delta): --quick option,
        # VIEWTIME / PREVIEW_MS timing lines, software-renderer NOTE.
        # Re-fenced 2026-10-23 (an agent, an internal task, author of the delta): _world_checks
        # adds WorldChecks.room_light_warnings (house rooms sidecar read from a folder package).
        self.assertEqual(SOURCE.count(MARKER), 1)
        before, rest = SOURCE.split(MARKER, 1)
        after = rest.split('func _init() -> void:\n', 1)[1]
        projected = before + 'func _init() -> void:\n' + after.replace(CWD_GUARD, '', 1).replace(GUARD, '', 1)
        self.assertEqual(hashlib.sha256(projected.encode()).hexdigest(), 'a6c08063a5cfdc6dda7e48e8a80896e4f993beb2cad357f6e94d98dd0f942ba7')

    def test_unmeasured_frames_are_not_reported_as_pass(self):
        self.assertIn('TARGET worst_frame_ms   NOT MEASURED', SOURCE)
        self.assertIn('if _worst_frame.worst[2] >= 0 else []', SOURCE)
        self.assertIn('"not measured"', SOURCE)
        self.assertNotIn('fps=%.1f', SOURCE)

    def test_quick_mode_is_wired(self):
        self.check(['--quick', 'w', 'out'], True)
        self.check(['w', 'out', '--quick', '--size', '800x450'], True)
        self.check(['w', '--quick', '--bogus'], False)
        self.assertIn('"--quick": _quick = true', SOURCE)
        self.assertIn('const QUICK_FRAMES := 25', SOURCE)   # above the 20 settle frames
        self.assertIn('print("VIEWTIME %d %s ms=%d"', SOURCE)
        self.assertIn('PREVIEW_MS total=', SOURCE)
        # the VIEW line itself is parsed by shots.py and lighting.py: it must not change
        self.assertIn('draw=%d prims=%d objects=%d fps=%s -> %s', SOURCE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
