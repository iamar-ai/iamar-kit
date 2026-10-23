#!/usr/bin/env python3
"""Bounded real bootstrap and public-custody regressions; private scratch only."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BAD = ("SCRIPT ERROR", "ERROR:", "Parse Error", "Compile Error", "FAIL ")


def prepare_source_root(dependency_root, destination):
    """Stage the exact reviewed closure; never refresh pins to fit local files."""
    spec = importlib.util.spec_from_file_location('bootstrap', ROOT / 'kit/tier_preflight_bootstrap.py')
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    content = bootstrap.source_bytes(bootstrap.checked(dependency_root, True))
    expected = json.loads((ROOT / 'kit/tier_preflight_manifest.json').read_text())
    if bootstrap.inventory(content) != expected:
        raise AssertionError('dependency root differs from the reviewed tier closure')
    for name, data in content.items():
        bootstrap.write_new(destination / name, data)
    bootstrap.write_new(destination / 'kit/tier_preflight_manifest.json',
                        (ROOT / 'kit/tier_preflight_manifest.json').read_bytes())
    return bootstrap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--dependency-root', type=Path, required=True,
                        help='explicit reviewed browser source/test tree; no auto-discovery')
    parser.add_argument('--godot', default=os.environ.get('GODOT', 'godot'))
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(mode=0o700)  # New private output: never overwrite earlier evidence.
    dependency_root = args.dependency_root.resolve(strict=True)
    source_root = out / 'verified-root'
    bootstrap = prepare_source_root(dependency_root, source_root)
    godot = Path(shutil.which(args.godot) or args.godot).resolve()
    env = os.environ.copy()
    env['GODOT'] = str(godot)
    env.pop('IAMAR_BROWSER', None)
    checks = 0

    def run(label, command, marker, code=0, process_env=env):
        nonlocal checks
        try:
            result = subprocess.run(command, env=process_env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    timeout=40)
        except subprocess.TimeoutExpired as error:
            captured = error.stdout or ''
            captured = captured.decode('utf-8', 'replace') if isinstance(captured, bytes) else captured
            stderr = error.stderr or ''
            stderr = stderr.decode('utf-8', 'replace') if isinstance(stderr, bytes) else stderr
            (out / (label + '.log')).write_text(captured + stderr +
                f'\nTIMEOUT in {label} after 40 seconds\n')
            raise AssertionError(f'{label}: timeout after 40 seconds') from error
        (out / (label + '.log')).write_text(result.stdout)
        if result.returncode != code or marker not in result.stdout or any(x in result.stdout for x in BAD):
            raise AssertionError(f'{label}: exit {result.returncode}\n{result.stdout}')
        checks += 1
        print('PASS ' + label, flush=True)
        return result

    base = dependency_root / 'tests/creator_world_validation/fixtures/valid_minimal'

    def sidecar(label, mutate=None, code=0, marker='TIER_PREFLIGHT_V1 OK', root=source_root):
        case = out / label
        case.mkdir(mode=0o700)
        source = case / 'source'
        shutil.copytree(base, source)
        manifest = json.loads((source / 'manifest.json').read_text())
        manifest['tiers'] = {'medium': {'budgets': {'objects': 4}}}
        if mutate:
            mutate(manifest, source)
        (source / 'manifest.json').write_text(json.dumps(manifest))
        runtime = case / 'runtime'
        runtime.mkdir(mode=0o700)
        run(label, [sys.executable, '-I', str(ROOT / 'kit/tier_preflight_bootstrap.py'),
                    str(root), str(source), str(runtime)], marker, code)
        return runtime / 'project'

    project = sidecar('valid-tiered-world')
    assert not (project / 'scripts/worlds/world_address_book.gd').exists()
    assert not (project / 'scripts/worlds/world_fetcher.gd').exists()
    assert '[autoload]' not in (project / 'project.godot').read_text()
    checks += 1
    sidecar('missing-tiers', lambda m, s: m.pop('tiers'), 1,
            'ERROR tier source needs an explicit valid tiers declaration')
    def over_budget(manifest, source):
        manifest['tiers']['medium']['budgets']['objects'] = 0
        scene = json.loads((source / 'scene.json').read_text())
        scene['lights'] = [{'type': 'point'}]
        (source / 'scene.json').write_text(json.dumps(scene))

    sidecar('tier-budget', over_budget, 1,
            'ERROR budget objects: the world has 1, over its budget of 0')
    sidecar('malformed-media', lambda m, s: (s / 'bad.png').write_bytes(b'not an image'), 1,
            'ERROR bad.png:')
    # Exercise the actual fail-closed bootstrap pin, not just inventory().
    pinned = out / 'pinned-root'
    for name, data in bootstrap.source_bytes(source_root).items():
        bootstrap.write_new(pinned / name, data)
    bootstrap.write_new(pinned / 'kit/tier_preflight_manifest.json',
                        (ROOT / 'kit/tier_preflight_manifest.json').read_bytes())
    with (pinned / 'scripts/worlds/world_source.gd').open('ab') as stream:
        stream.write(b'\n# controlled pin drift\n')
    sidecar('pin-drift', code=2,
            marker='ERROR data-only tier preflight requires a verified source-Godot sidecar and private runtime', root=pinned)

    # The sidecar deliberately omits browser custody. Its private folder method
    # works, but accidental public-path calls must fail before any file read.
    blocked = '''extends SceneTree
func _initialize() -> void:
    var source := WorldSource.open(OS.get_cmdline_user_args()[0])
    var direct := WorldSource.new()
    direct._open_zip(OS.get_cmdline_user_args()[0])
    if source.error != "public package custody is unavailable" or not source._files.is_empty() or source._zip != null or direct.error != source.error or direct._zip != null:
        printerr("FAIL unprotected pathname read")
        quit(1)
        return
    print("UNPROTECTED_READ_REFUSED")
    quit(0)
'''
    (project / 'blocked.gd').write_text(blocked)
    private_env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
    for key in ('HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME'):
        path = out / key
        path.mkdir(mode=0o700)
        private_env[key] = str(path)
    command = [str(godot), '--headless', '--audio-driver', 'Dummy', '--path', str(project),
               '--script', 'res://blocked.gd', '--', str(out / 'valid-tiered-world/source/manifest.json')]
    run('missing-custody', command, 'UNPROTECTED_READ_REFUSED', process_env=private_env)
    # A present but wrong helper is not a substitute for the real custody API.
    (project / 'scripts/worlds/world_address_book.gd').write_text('extends RefCounted\n')
    run('invalid-custody-api', command, 'UNPROTECTED_READ_REFUSED', process_env=private_env)

    # Existing snapshot preparer supplies exact production dependencies + class
    # registry, not a custody stub. The browser dependency chain has a few
    # preloaded fonts/images/sounds, so import this separate project explicitly;
    # the pinned sidecar above still never runs any editor/import pass.
    custody = out / 'custody'
    subprocess.run([sys.executable, str(dependency_root / 'tests/world_source_snapshot/prepare_tests.py'),
                    str(custody)], check=True, stdout=subprocess.DEVNULL, env=env, timeout=20)
    shutil.copyfile(ROOT / 'tests/tier_preflight/custody.gd', custody / 'custody.gd')
    cache = custody / 'completed'
    cache.mkdir()
    archive = cache / ('verified-' + 'a' * 64 + '.iamar')
    second = cache / ('verified-' + 'b' * 64 + '.iamar')
    for path in (archive, second):
        with zipfile.ZipFile(path, 'w') as package:
            package.writestr('manifest.json', '{}')
    (cache / 'addresses.json').write_text(json.dumps({'worlds': {}, 'retired': [str(archive)]}))
    run('custody-import', [str(godot), '--headless', '--audio-driver', 'Dummy', '--path', str(custody),
                           '--editor', '--import', '--quit'], '', process_env=private_env)
    run('real-public-custody', [str(godot), '--headless', '--audio-driver', 'Dummy', '--path', str(custody),
                               '--script', 'res://custody.gd', '--', str(archive)],
        'TIER_CUSTODY_PASS 11 checks, 0 failures', process_env=private_env)
    run('folder-zip-snapshots', [str(godot), '--headless', '--audio-driver', 'Dummy', '--path', str(custody),
                                '--script', 'res://test.gd'],
        'RESULT 29 checks, 0 failures', process_env=private_env)
    print(f'TIER_PREFLIGHT_TEST {checks} passed, 0 failed')


if __name__ == '__main__':
    main()
