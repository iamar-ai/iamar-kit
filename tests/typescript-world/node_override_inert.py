#!/usr/bin/env python3
"""Exact shell selection/availability fragment; no Node/compiler/engine runs."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'kit/iamar-world').read_text()
# Include only executable selection and the existing availability check. The
# real version probe, compiler and packer are deliberately outside this fragment.
start = SOURCE.index('  # An explicitly set Node override') if '  # An explicitly set Node override' in SOURCE else SOURCE.index('  node_bin="${IAMAR_TS_NODE:-')
end = SOURCE.index('  [[ "$("$node_bin" -p ', start)
FRAGMENT = SOURCE[start:end]
UNSET = object()

class NodeOverride(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='iamar-node-override-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        # These are inert files, never executed. The shell checks their mode only.
        self.approved = self.folder / 'approved node'
        self.fallback = self.folder / 'PATH node'
        self.nonexec = self.folder / 'non executable node'
        for path in [self.approved, self.fallback, self.nonexec]:
            path.write_text('inert fixture; must never be executed\n')
            path.chmod(0o700 if path != self.nonexec else 0o600)

    def run_fragment(self, override=UNSET, found=True):
        env = {k: v for k, v in os.environ.items() if k not in ('IAMAR_TS_NODE', 'BASH_ENV', 'ENV') and not k.startswith('BASH_FUNC_')}
        env['MOCK_NODE'] = str(self.fallback) if found else ''
        if override is not UNSET:
            env['IAMAR_TS_NODE'] = str(override)
        script = '''set -euo pipefail
command() {
  [[ "$#" == 2 && "$1" == -v && "$2" == node ]] || exit 97
  printf 'DISCOVERED_NODE\\n' >&2
  [[ -n "$MOCK_NODE" ]] || return 1
  printf '%s\\n' "$MOCK_NODE"
}
''' + FRAGMENT + '''printf '%s\\n' "$node_bin"
'''
        return subprocess.run(['/bin/bash', '--noprofile', '--norc', '-c', script], env=env, text=True, capture_output=True, timeout=5)

    def test_unset_uses_path_once(self):
        result = self.run_fragment()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.fallback))
        self.assertEqual(result.stderr, 'DISCOVERED_NODE\n')

    def test_empty_override_fails_without_path_discovery(self):
        result = self.run_fragment('')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('DISCOVERED_NODE', result.stderr)

    def test_explicit_spaced_path_is_preserved(self):
        result = self.run_fragment(self.approved)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.approved))
        self.assertEqual(result.stderr, '')

    def test_invalid_overrides_do_not_fall_back(self):
        for override in [self.folder / 'missing node', self.nonexec, '   ']:
            with self.subTest(override=str(override)):
                result = self.run_fragment(override)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertNotIn('DISCOVERED_NODE', result.stderr)

    def test_missing_path_node_fails(self):
        result = self.run_fragment(found=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr.count('DISCOVERED_NODE'), 1)

    def test_explicit_override_does_not_need_path_node(self):
        result = self.run_fragment(self.approved, found=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.approved))
        self.assertEqual(result.stderr, '')

    def test_fragment_never_invokes_node_or_compiler(self):
        self.assertNotIn(' -p ', FRAGMENT)
        self.assertNotIn('exec ', FRAGMENT)
        self.assertNotIn('"$packer"', FRAGMENT)
        self.assertNotIn('"$node_bin" "', FRAGMENT)

if __name__ == '__main__':
    unittest.main(verbosity=2)
