"""Package CLI source/argv model only; never starts native tools or signs files."""
import hashlib
import os
from pathlib import Path
import unittest

ROOT = Path(os.environ.get('IAMAR_TEST_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
SOURCE = (ROOT / 'scripts/kit/world_package.gd').read_text()
GUIDE = (ROOT / 'kit/AGENT_KIT.md').read_text()
PIECES = (ROOT / 'scripts/worlds/world_pieces.gd').read_text()
INSTALLER = (ROOT / 'scripts/host/local_world_install.gd').read_text()
ADD = (ROOT / 'scripts/host/world_host_add.gd').read_text()
GUARD = '''\tif not args[1].ends_with(".iamar"):
\t\tprinterr("package output must end in lowercase .iamar for browser import")
\t\tquit(2)
\t\treturn
'''
OLD_PREFIX = '''\tvar args := KitLoop.user_args()
\tif args.size() < 4:
\t\tprinterr("usage: package <folder> <out.iamar> <key> <signer name>")
\t\tquit(2)
\t\treturn
'''
GUIDE_ADDITION = '''The output filename must end in lowercase `.iamar`, matching browser import;
other suffixes are refused before rebuilding tiers or signing.
'''


def git_blob(text):
    data = text.encode()
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def prefix(source):
    text = source.split('func _initialize() -> void:\n', 1)[1].split('\tvar folder := KitLoop.absolute_path(args[0])\n', 1)[0]
    if text not in (OLD_PREFIX, OLD_PREFIX + GUARD):
        raise AssertionError('Uninspected CLI prefix; review the inert translation')
    return text


def preflight(args, source=SOURCE):
    # Translate only the two exact inspected source prefixes above. Child tools,
    # path resolution and package I/O are represented by a recorder after return.
    p = prefix(source).replace('\tvar args := KitLoop.user_args()\n', '')
    p = p.replace('args.size()', 'len(args)').replace('.ends_with(', '.endswith(')
    code = 'def run(args, printerr, quit, dispatch):\n' + p + '\tdispatch(args)\n'
    env = {'__builtins__': {'len': len}}
    exec(compile(code, '<inert package argv prefix>', 'exec'), env)
    events = []
    env['run'](args, lambda s: events.append(('error', s)),
               lambda c: events.append(('quit', c)),
               lambda a: events.append(('dispatch', tuple(a))))
    return events


class PackageOutputContract(unittest.TestCase):
    def test_incompatible_suffixes_stop_before_dispatch(self):
        for output in ['', 'release', 'release.zip', 'release.IAMAR', 'release.Iamar',
                       'release.iamar.tmp', 'release.iamar/', 'release.iamar ',
                       'dir.iamar/release', 'release.iamar\\']:
            with self.subTest(output=output):
                events = preflight(['world', output, 'approved.key', 'Name'])
                self.assertEqual(events, [('error', 'package output must end in lowercase .iamar for browser import'), ('quit', 2)])

    def test_exact_baseline_admitted_now_unimportable_names(self):
        baseline = SOURCE.replace(GUARD, '')
        for output in ['release', 'release.zip', 'release.IAMAR', 'release.iamar.tmp']:
            args = ['world', output, 'approved.key', 'Name']
            self.assertEqual(preflight(args, baseline), [('dispatch', tuple(args))])
            self.assertNotEqual(preflight(args), [('dispatch', tuple(args))])

    def test_missing_operands_keep_original_usage_precedence(self):
        for size in range(4):
            args = ['world', 'bad.zip', 'approved.key'][:size]
            self.assertEqual(preflight(args), [('error', 'usage: package <folder> <out.iamar> <key> <signer name>'), ('quit', 2)])

    def test_valid_paths_and_arguments_are_not_normalized_or_consumed(self):
        for output in ['release.iamar', 'out/My World.iamar', '/tmp/旅 世界.iamar',
                       r'C:\My Worlds\RELEASE.iamar', './release.iamar', '../out/release.iamar',
                       'release.zip.iamar', 'release..iamar']:
            args = ['relative world', output, '../approved key.key', 'Mixed Case 名', 'retained-extra']
            original = list(args)
            self.assertEqual(preflight(args), [('dispatch', tuple(original))])
            self.assertEqual(args, original)

    def test_guard_precedes_all_path_tier_and_child_work(self):
        self.assertEqual(prefix(SOURCE), OLD_PREFIX + GUARD)
        pos = SOURCE.index(GUARD)
        for token in ['var folder := KitLoop.absolute_path(args[0])', '_declares_tiers(folder)',
                      'OS.get_environment("IAMAR_NO_TIERS")', '_tool("res://scripts/kit/world_tiers_build.gd"',
                      '_tool("res://scripts/kit/world_sign.gd"']:
            self.assertLess(pos + len(GUARD), SOURCE.index(token))
        self.assertEqual(SOURCE.count(GUARD), 1)

    def test_every_downstream_byte_and_low_level_contract_unchanged(self):
        self.assertEqual(git_blob(SOURCE.replace(GUARD, '')), 'bbec987b2af73422824572b905d020be6aa2a5eb')
        self.assertEqual(git_blob(PIECES), '8ab056c5c2ffcfbb2c5352ed930c70debc62c2d2')
        low_level = PIECES.split('static func pack(', 1)[1].split('\n\nstatic func ', 1)[0]
        self.assertNotIn('ends_with(".iamar")', low_level)

    def test_exact_case_policy_matches_both_import_entrypoints(self):
        self.assertIn('if _source == "" or not _source.ends_with(".iamar"):', INSTALLER)
        self.assertIn('if src == "" or not src.ends_with(".iamar"):', ADD)
        self.assertIn('if not args[1].ends_with(".iamar"):', SOURCE)
        self.assertNotIn('to_lower()', GUARD)

    def test_documentation_only_adds_the_same_cli_contract(self):
        # The guide keeps growing (U7 page checks etc.), so pin only the package-output
        # contract: stated once, inside the `package` paragraph, and every documented
        # `iamar-world package` example writes a lowercase .iamar (an internal task).
        self.assertEqual(GUIDE.count(GUIDE_ADDITION), 1)
        paragraph = GUIDE.split('`package` (also accepted as `pack`)', 1)[1].split('\n\n', 1)[0]
        self.assertIn(GUIDE_ADDITION.strip(), paragraph)
        examples = [line.split()[3] for line in GUIDE.splitlines()
                    if line.startswith('iamar-world package ') and len(line.split()) > 3]
        self.assertTrue(examples)
        for out in examples:
            self.assertTrue(out.endswith('.iamar'), out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
