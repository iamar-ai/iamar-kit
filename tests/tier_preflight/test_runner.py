"""Timeout log controls: mock the child, never launch Godot or the bootstrap."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('tier_runner', Path(__file__).with_name('run.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TimeoutLogs(unittest.TestCase):
    def exercise(self, stdout, stderr):
        base = Path(os.environ.get('IAMAR_TEST_SCRATCH', os.environ.get('TMPDIR', str(Path.home() / 'mp_run' / os.environ.get('AGENTCOORD_AGENT', 'tier-runner-tests')))))
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='tier-timeout-', dir=base) as directory:
            out = Path(directory) / 'output'
            error = subprocess.TimeoutExpired(['controlled-child'], 40, output=stdout, stderr=stderr)
            dependency_root = Path(directory) / 'dependencies'
            fixture = dependency_root / 'tests/creator_world_validation/fixtures/valid_minimal'
            fixture.mkdir(parents=True)
            (fixture / 'manifest.json').write_text('{}')
            (fixture / 'scene.json').write_text('{}')
            argv = ['run.py', '--out', str(out), '--dependency-root', str(dependency_root),
                    '--godot', '/controlled/no-engine']
            with patch.object(sys, 'argv', argv), patch.object(runner, 'prepare_source_root'), \
                    patch.object(runner.subprocess, 'run', side_effect=error) as child:
                with self.assertRaisesRegex(AssertionError, 'valid-tiered-world: timeout after 40 seconds'):
                    runner.main()
            self.assertEqual(child.call_count, 1)
            self.assertIn('tier_preflight_bootstrap.py', str(child.call_args.args[0]))
            log = (out / 'valid-tiered-world.log').read_text()
            for value in (stdout, stderr):
                expected = value.decode('utf-8', 'replace') if isinstance(value, bytes) else value or ''
                self.assertIn(expected, log)
            self.assertIn('TIMEOUT in valid-tiered-world after 40 seconds', log)
            self.assertNotIn('TIER_PREFLIGHT_V1 OK', log)

    def test_bytes_and_stderr_retained(self):
        self.exercise(b'\xffPARTIAL_NATIVE_DIAGNOSTIC\n', b'CONTROL_STDERR\n')

    def test_text_retained(self):
        self.exercise('PARTIAL_NATIVE_DIAGNOSTIC 界\n', None)

    def test_empty_timeout_still_records_stage(self):
        self.exercise(None, None)


if __name__ == '__main__':
    unittest.main()
