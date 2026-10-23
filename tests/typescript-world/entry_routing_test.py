#!/usr/bin/env python3
"""Recorder-only shell routing checks. No compiler, guest or native engine runs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


# Pass the source project root explicitly; this does not execute a native engine.
if len(sys.argv) != 2:
    raise SystemExit('usage: entry_routing_test.py <source-project-root>')
ROOT = Path(sys.argv[1]).resolve(strict=True)
candidate = ROOT / 'kit/iamar-world'
run = Path(tempfile.mkdtemp(prefix='iamar-typescript-entry-routing-'))
# Reconstruct only the recorded wrapper preimage, and prove its identity before
# using it for recorder comparisons. No untouched repository snapshot is shipped.
current = candidate.read_bytes()
anchor = b'cmd="${1:-help}"; shift || true\n'
next_line = b'if [[ -z "$browser" && ! -f "$project/project.godot" && "$cmd" != blender && "$cmd" != blender-run ]]; then\n'
insertion_bytes = current.split(anchor, 1)[1].split(next_line, 1)[0]
preimage = current.replace(insertion_bytes, b'', 1)
# Pin updated 2026-10-10: the candidate was first reviewed against the draft
# branch's wrapper (preimage d9b232ae...). On main the wrapper had since become
# the native kit CLI (commit a75e0dcf, "Embed cross-platform world kit CLI in
# browser"), and the TypeScript branch was inserted into that file. This pin is
# the sha256 of `git show a75e0dcf:kit/iamar-world`, i.e. main's wrapper before
# the insertion, so the check still proves the insertion is the only change.
assert hashlib.sha256(preimage).hexdigest() == '8359d4a6cd504cda584e6e91e82014d8c0c41b2c5b1512ffb13350840f2219ae', 'Wrapper preimage drift: reconcile the intended baseline first'
baseline = run / 'recorded-wrapper-preimage'
baseline.write_bytes(preimage)

project = run / 'project with spaces'
work = run / 'work'
work.mkdir()
for parent in ['tools/typescript-world', 'api/typescript', 'kit']:
    (project / parent).mkdir(parents=True, exist_ok=True)
(project / 'tools/typescript-world/build.mjs').write_text('// routing placeholder; never evaluated\n')
(project / 'api/typescript/iamar-world.d.ts').write_text('// routing placeholder\n')
compiler = run / 'compiler lib/typescript.js'
compiler.parent.mkdir(); compiler.write_text('// routing placeholder\n')
lock = run / 'dependency lock.json'; lock.write_text('{}\n')
quickjs = run / 'quickjs sources'; quickjs.mkdir()
sdk = run / 'wasi sdk'; sdk.mkdir()
source = work / 'world $(touch SHOULD_NOT_EXIST); [x] *.ts'
source.write_text('function on_init(): void {}\n')
template = work / 'template ; literal'; template.mkdir()
output = work / 'out $(touch ALSO_NOT_CREATED); space'
node = run / 'node recorder'
native = run / 'native recorder'
recorder = '#!' + sys.executable + '\nimport json,os,sys\nprint(json.dumps({"program":sys.argv[0],"argv":sys.argv[1:],"cwd":os.getcwd()}))\nsys.exit(int(os.environ.get("RECORDER_EXIT","0")))\n'
for path in [node, native]:
    path.write_text(recorder); path.chmod(0o755)
env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'HOME': str(run),
       'IAMAR_PROJECT': str(project), 'IAMAR_BROWSER': str(native), 'GODOT': str(native),
       'IAMAR_TS_NODE': str(node), 'IAMAR_TS_COMPILER': str(compiler),
       'IAMAR_TS_QUICKJS': str(quickjs), 'IAMAR_TS_WASI_SDK': str(sdk),
       'IAMAR_TS_DEPENDENCY_LOCK': str(lock)}
# the clang source build is opt-in since the prebuilt-guest packer became the
# default (bodhi-inbox #191); this test covers the --from-source routing
args = ['compile-typescript', '--from-source', str(source), str(template), str(output)]
checks = []


def call(arguments, changes=None, wrapper=candidate):
    e = dict(env)
    for key, value in (changes or {}).items():
        if value is None: e.pop(key, None)
        else: e[key] = value
    return subprocess.run(['/bin/bash', str(wrapper), *arguments], env=e, cwd=work,
                          capture_output=True, text=True, timeout=5)


def check(name, condition, observed=None):
    checks.append({'name': name, 'pass': bool(condition), **({'observed': observed} if observed is not None else {})})


for count in [0, 1, 2, 3, 5]:
    values = args[1:] + ['unexpected']
    r = call(['compile-typescript', *values[:count]])
    check('Refuse positional arity ' + str(count), r.returncode == 2 and not r.stdout)
for key in ['IAMAR_TS_NODE', 'IAMAR_TS_COMPILER', 'IAMAR_TS_QUICKJS', 'IAMAR_TS_WASI_SDK', 'IAMAR_TS_DEPENDENCY_LOCK']:
    for label, value in [('missing', None), ('relative', 'relative/path')]:
        r = call(args, {key: value})
        check('Refuse ' + label + ' ' + key, r.returncode == 2 and not r.stdout)
for key in ['IAMAR_TS_NODE', 'IAMAR_TS_COMPILER', 'IAMAR_TS_QUICKJS', 'IAMAR_TS_WASI_SDK', 'IAMAR_TS_DEPENDENCY_LOCK']:
    r = call(args, {key: str(run / 'absent')})
    check('Refuse unavailable ' + key, r.returncode == 2 and not r.stdout)
nonexec = run / 'nonexecutable node'; nonexec.write_text('never run\n'); nonexec.chmod(0o644)
r = call(args, {'IAMAR_TS_NODE': str(nonexec)})
check('Refuse nonexecutable Node', r.returncode == 2 and not r.stdout)
for rel in ['tools/typescript-world/build.mjs', 'api/typescript/iamar-world.d.ts']:
    p = project / rel; original = p.read_bytes(); p.unlink()
    r = call(args); p.write_bytes(original)
    check('Refuse missing project ' + rel, r.returncode == 2 and not r.stdout)
for index, label in [(2, 'source'), (3, 'template')]:
    a = list(args); a[index] = str(run / 'absent')
    r = call(a); check('Refuse missing ' + label, r.returncode == 2 and not r.stdout)
r = call(args, {'OSTYPE': 'darwin23'})
check('Refuse non-Linux author host', r.returncode == 2 and not r.stdout)
r = call(args, {'HOSTTYPE': 'aarch64'})
check('Refuse non-x86_64 author host', r.returncode == 2 and not r.stdout)
r = call(args)
expected = [str(project / 'tools/typescript-world/build.mjs'), '--source', str(source),
            '--sdk', str(project / 'api/typescript/iamar-world.d.ts'), '--typescript', str(compiler),
            '--quickjs', str(quickjs), '--wasi-sdk', str(sdk), '--dependency-lock', str(lock),
            '--template', str(template), '--out', str(output)]
got = json.loads(r.stdout) if r.stdout else {}
check('Fixed quoted argv preserves whitespace/metacharacters', r.returncode == 0 and got.get('argv') == expected, got)
check('Compile path uses configured Node, not native recorder', got.get('program') == str(node))
check('Working directory preserved', got.get('cwd') == str(work))
# the default (packer) path refuses cleanly when the packer / prebuilt guest are absent
r = call(['compile-typescript', str(source), str(template), str(output)])
check('Default packer path refuses without packer or prebuilt guest', r.returncode == 2 and not r.stdout)
check('Shell metacharacters did not execute', not (work / 'SHOULD_NOT_EXIST').exists() and not (work / 'ALSO_NOT_CREATED').exists())
check('Recorder-only test did not produce a compiled output', not output.exists())
r = call(args, {'RECORDER_EXIT': '23'})
check('Compiler exit status propagates', r.returncode == 23)
for command, positional in [('validate', ['world with spaces']), ('preview', ['world with spaces', 'shots ; literal'])]:
    old = call([command, *positional], wrapper=baseline)
    new = call([command, *positional])
    check('Existing ' + command + ' route exactly unchanged', old.returncode == new.returncode == 0 and old.stdout == new.stdout, json.loads(new.stdout))
old = baseline.read_text(); new = candidate.read_text(); anchor = 'cmd="${1:-help}"; shift || true\n'
tail = 'if [[ -z "$browser" && ! -f "$project/project.godot" && "$cmd" != blender && "$cmd" != blender-run ]]; then\n'
insertion = new.split(anchor, 1)[1].split(tail, 1)[0]
check('All baseline bytes preserved around one insertion', new.replace(insertion, '', 1) == old)
# The draft branch's tier-preflight block is not part of main's wrapper; check
# instead that main's managed-upload block survives the insertion byte for byte.
check('Managed-upload publish block retained exactly', old[old.index('# Managed upload'):old.index('headless=(--headless)\ncase')] in new)
syntax = subprocess.run(['/bin/bash', '-n', str(candidate)], capture_output=True, text=True, timeout=5)
check('Bash syntax accepted', syntax.returncode == 0)
result = {'evidence': 'Recorder-only shell routing/source preservation checks; no compiler, guest or native engine executed',
          'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
          'baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
          'test_run': str(run), 'passed': sum(c['pass'] for c in checks),
          'failed': sum(not c['pass'] for c in checks), 'checks': checks}
(run / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['failed'] == 0 else 1)
