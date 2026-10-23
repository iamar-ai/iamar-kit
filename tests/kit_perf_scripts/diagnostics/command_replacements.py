#!/usr/bin/env python3
"""Inert command-replacement cases. Never invokes Godot, Wasm, or native code.

Not executed as part of source preparation. Explicit future use only:
  python3 tests/kit_perf_scripts/diagnostics/command_replacements.py --run-inert
Creates an isolated synthetic repository with a fake launcher/renderer/timeout.
All .wasm paths contain inert text. No real project or installed runtime is used.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

CHICKENS = '''SCRIPTS 1 running (playerless preview)
SCRIPT_MS mean=0.001 worst=0.002 in view spawn over 120 frames
SCRIPT perfscripts/scripts/script_chickens.wasm on_tick calls=120 us_max=2 us_total=120
TARGET world_scripts_ms PASS 0.00 / 2.00
TARGETS PASS
'''
HOSTILE = '''[world perfscripts] spin: loaded, will loop forever in on_tick
SCRIPTS 1 running (playerless preview)
[world perfscripts] script problem: on_tick trapped (fuel): all fuel consumed by WebAssembly
ERROR: world script preview failed: A declared preview script failed, trapped or stopped.
'''
# Every process in this generated fake launcher is Python; it does not read,
# instantiate, import, compile or execute the inert .wasm placeholders.
LAUNCHER = '''import json, os, pathlib, sys
case = json.loads(pathlib.Path(os.environ['INERT_CASE']).read_text())
with open(os.environ['INERT_CALLS'], 'a') as f:
    f.write(' '.join(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'new':
    print('synthetic scaffold complete output')
    if case.get('fail_step') == 'scaffold':
        sys.exit(23)
    p = pathlib.Path(sys.argv[2]); p.mkdir()
    (p / 'manifest.json').write_text('{broken' if case.get('fail_step') == 'manifest' else '{"id":"perfscripts"}')
    sys.exit(0)
if sys.argv[1] != 'perf':
    sys.exit(90)
s = pathlib.Path(sys.argv[2]).name
# Assert the runner really copied both fixtures and wrote the script entry.
p = pathlib.Path(sys.argv[2])
m = json.loads((p / 'manifest.json').read_text())
assert m['scripts'] == [{'path': 'scripts/' + s + '.wasm'}]
assert (p / 'scripts' / (s + '.wasm')).read_text() == 'INERT: not WebAssembly\\n'
print(case[s], end='')
sys.exit(case[s + '_rc'])
'''
COPY = '''import json, os, pathlib, shutil, sys
case = json.loads(pathlib.Path(os.environ['INERT_CASE']).read_text())
a = sys.argv[1:]
if case.get('fail_step') == 'copy_world' and a[0] == '-r':
    print('synthetic world-copy failure', file=sys.stderr); sys.exit(24)
if case.get('fail_step') == 'copy_wasm' and a[0].endswith('.wasm'):
    print('synthetic Wasm-copy failure', file=sys.stderr); sys.exit(25)
if a[0] == '-r': shutil.copytree(a[1], a[2])
else: shutil.copy(a[0], a[1])
'''


def cases():
    yield 'valid_abort', {}, True
    yield 'valid_rounded_zero', {'script_chickens': CHICKENS.replace('0.001 worst=0.002', '0.000 worst=0.000')}, True
    report = HOSTILE.split('ERROR:')[0] + 'TARGET world_scripts_ok   FAIL  perfscripts/scripts/hostile_spin.wasm  -> a script trapped or was stopped\nTARGETS FAIL (1)\n'
    yield 'valid_report', {'hostile_spin': report}, True
    for step in ('scaffold', 'copy_world', 'copy_wasm', 'manifest'):
        yield 'setup_' + step, {'fail_step': step}, False
    for name, content in (
        ('missing_stats', '\n'.join(x for x in CHICKENS.splitlines() if not x.startswith('SCRIPT ')) + '\n'),
        ('zero_calls', CHICKENS.replace('calls=120', 'calls=0')),
        ('zero_microseconds', CHICKENS.replace('us_max=2 us_total=120', 'us_max=0 us_total=0')),
        ('zero_frames', CHICKENS.replace('120 frames', '0 frames')),
        ('invalid_timing', CHICKENS.replace('mean=0.001', 'mean=NaN')),
        ('disabled', CHICKENS.replace('us_total=120', 'us_total=120 DISABLED')),
        ('empty', ''),
        ('runtime_error', CHICKENS + 'ERROR: native runtime failed\n'),
        ('missing_target', CHICKENS.replace('TARGETS PASS\n', '')),
    ):
        yield 'chickens_' + name, {'script_chickens': content}, False
    yield 'chickens_failed_process', {'script_chickens_rc': 1}, False
    for name, content in (
        ('generic_error', 'ERROR: world script preview failed: The package declares scripts, but the WebAssembly runtime is unavailable.\n'),
        ('additional_runtime_error', HOSTILE + 'SCRIPT ERROR: runtime malfunction\n'),
        ('no_startup', '\n'.join(HOSTILE.splitlines()[1:]) + '\n'),
        ('wrong_world', HOSTILE.replace('[world perfscripts]', '[world unrelated]')),
        ('wrong_trap', HOSTILE.replace('trapped (fuel)', 'trapped (error)')),
        ('no_trap', HOSTILE.replace('script problem: on_tick trapped (fuel): all fuel consumed by WebAssembly', 'unrelated diagnostic')),
        ('no_failure', HOSTILE.split('ERROR:')[0]),
        ('generic_after_trap', HOSTILE.split('ERROR:')[0] + 'ERROR: world script preview failed: A declared preview script could not load.\n'),
    ):
        yield 'hostile_' + name, {'hostile_spin': content}, False
    for rc in (0, 2, 124, 125, 126, 127, 137, 143):
        yield 'hostile_exit_' + str(rc), {'hostile_spin_rc': rc, 'hostile_spin': HOSTILE + 'EXIT 1\n'}, False


def executable(path, body):
    path.write_text('#!' + sys.executable + ' -I\n' + body)
    path.chmod(0o755)


def inert_environment(root):
    # Never inherit shell startup hooks, Python import paths, runtime selectors,
    # credentials or other user settings into synthetic command replacements.
    return dict(PATH=str(root / 'bin') + ':/usr/bin:/bin',
                HOME=str(root / 'home'), TMPDIR=str(root / 'tmp'), LC_ALL='C',
                IAMAR_PROJECT=str(root / 'browser'),
                INERT_CASE=str(root / 'case.json'), INERT_CALLS=str(root / 'calls'),
                PERF_SCRIPTS_LOG_DIR=str(root / 'evidence'))


def check_environment_contract(root):
    expected = inert_environment(root)
    poison = {key: '/must-not-be-used' for key in (
        'BASH_ENV', 'ENV', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP',
        'LD_PRELOAD', 'DYLD_INSERT_LIBRARIES', 'IAMAR_BROWSER', 'GODOT')}
    # This only authors a future inert regression; source preparation does not
    # execute it. Even under a polluted parent, children get the closed allowlist.
    with patch.dict(os.environ, poison):
        actual = inert_environment(root)
    assert actual == expected
    assert not (actual.keys() & poison.keys())
    assert set(actual) == {'PATH', 'HOME', 'TMPDIR', 'LC_ALL', 'IAMAR_PROJECT',
                           'INERT_CASE', 'INERT_CALLS', 'PERF_SCRIPTS_LOG_DIR'}
    return actual


def main():
    if sys.argv[1:] != ['--run-inert']:
        sys.exit('Source-only diagnostic fixtures. Pass --run-inert explicitly to run replacements, never actual perf.')
    runner = Path(__file__).resolve().parents[1] / 'run.sh'
    bash = shutil.which('bash', path='/usr/bin:/bin')
    assert bash
    count = 0
    for name, changes, expected in cases():
        with tempfile.TemporaryDirectory(prefix='inert-perf-classification-') as d:
            root = Path(d)
            for p in ('tests/kit_perf_scripts', 'kit', 'browser/examples/wasm', 'bin', 'evidence', 'home', 'tmp'):
                (root / p).mkdir(parents=True)
            shutil.copyfile(runner, root / 'tests/kit_perf_scripts/run.sh')
            for s in ('script_chickens', 'hostile_spin'):
                (root / 'browser/examples/wasm' / (s + '.wasm')).write_text('INERT: not WebAssembly\n')
            executable(root / 'kit/iamar-world', LAUNCHER)
            executable(root / 'bin/cp', COPY)
            executable(root / 'bin/offscreen', 'import os, sys\nos.execv(sys.argv[1], sys.argv[1:])\n')
            executable(root / 'bin/timeout', "import os, sys\nassert sys.argv[1] == '600'\nos.execv(sys.argv[2], sys.argv[2:])\n")
            case = dict(script_chickens=CHICKENS, hostile_spin=HOSTILE, script_chickens_rc=0, hostile_spin_rc=1)
            case.update(changes)
            (root / 'case.json').write_text(json.dumps(case))
            env = check_environment_contract(root)
            # Isolated Python ignores user import/startup settings and user site.
            executable(root / 'bin/python3',
                       "import os, sys\nos.execv(sys.executable, [sys.executable, '-I', *sys.argv[1:]])\n")
            result = subprocess.run([bash, str(root / 'tests/kit_perf_scripts/run.sh')], env=env,
                                    capture_output=True, text=True, timeout=10)
            assert (result.returncode == 0) == expected, (name, result.returncode, result.stdout, result.stderr)
            evidence, = (root / 'evidence').iterdir()
            exits = (evidence / 'exits.tsv').read_text()
            assert 'scaffold\t' in exits and 'runner\t' in exits, (name, exits)
            assert 'synthetic scaffold complete output' in (evidence / 'scaffold.log').read_text()
            calls = (root / 'calls').read_text().splitlines()
            if 'fail_step' in case:
                assert not any(x.startswith('perf ') for x in calls), (name, calls)
            else:
                assert (evidence / 'script_chickens.log').read_text() == case['script_chickens']
                assert (evidence / 'hostile_spin.log').read_text() == case['hostile_spin']
                assert f"script_chickens\t{case['script_chickens_rc']}\t" in exits
                assert f"hostile_spin\t{case['hostile_spin_rc']}\t" in exits
                assert 'KIT PERF SCRIPTS TEST ' in (evidence / 'assertions.log').read_text()
            count += 1
            print('PASS inert case', name)
    print(f'{count} inert diagnostic cases passed; no performance or runtime claim')


if __name__ == '__main__':
    main()
