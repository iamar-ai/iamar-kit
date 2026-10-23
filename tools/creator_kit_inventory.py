#!/usr/bin/env python3
"""Read-only, Linux/POSIX static inventory check of an already assembled kit.

Supply an independently reviewed inventory JSON and its SHA-256 through separate
trusted channels; NEVER create that inventory from the candidate being checked.
The inventory contains schema=1, source_revision (40 lower-case hex), mode
('external' or 'bundled'), evidence_kind ('fixture' or 'existing-payload'), and
files: [{path, size, sha256, mode}], where mode is an integer such as 420 (0644).
Every delivered file, including generated guide/setup/index bytes, must be pinned.
Packer, SDK, spec and guest must be reviewed together at source_revision. Hashes
prove agreement with this supplied baseline, not correctness or authenticity of
that baseline. There is deliberately no inventory-generation/signing command.

Example: python3 tools/creator_kit_inventory.py --kit /staging/kit \
 --inventory /reviewed/inventory.json --inventory-sha256 <reviewed-sha256> \
 --profile release
Bundled mode also reads --typescript-manifest (default: adjacent existing
 tools/typescript-world/runtime_manifest.json), with a fixed source pin.
Select --profile release explicitly for downloaded release-folder checks: it
requires iamar-kit.pck and KIT_VERSION.json in addition to the generic files.
The generic default preserves historical fixture callers; profiles are never
inferred from file presence. Neither profile establishes release qualification.
No code in the kit is imported or executed. No archive is opened or extracted.
This is not release/archive, native, compiler-runtime or supported-target QA.
Use a quiescent staging directory: this is not an atomic filesystem snapshot.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import stat
import sys

MANIFEST_SHA256 = '7f474b5420a2e62c407f88eefd4b9c4ce40b7a9a3ce134694939dd009074a8a5'
ARCHIVE_SHA256 = '10e108c9cf7d5f2879053dff18515fb405abf2ccef63eaaf017d9c571687a1d3'
TS_PREFIX = 'ts-world/node_modules/typescript/'
MAX_FILES = 4096
MAX_ENTRIES = 8192
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_JSON = 2 * 1024 * 1024
REQUIRED = frozenset('''AGENT_KIT.md iamar-world iamar-world.cmd
blender/starter_build.py recipes/TECHNIQUES.md recipes/make_recipes.py
recipes/techniques.json tests/cli_shell_test.sh tests/recipes_test.py
tier_preflight_bootstrap.py tier_preflight_manifest.json
docs/WORLD_FORMAT.md docs/WORLD_API.md docs/WORLD_TIERS.md index.html
ts-world/pack.mjs ts-world/compiler.mjs ts-world/audit-wasm.mjs
ts-world/api_generated.mjs ts-world/dependencies.mjs ts-world/gen_bindings.mjs
ts-world/template-files.mjs
ts-world/iamar-world.d.ts ts-world/world_api.json
ts-world/prebuilt/iamar_ts_guest.wasm ts-world/prebuilt/provenance.json
ts-world/THIRD_PARTY_NOTICES.txt ts-world/LICENSES_RECEIPT.json
ts-world/TYPESCRIPT.md'''.split())
RELEASE_REQUIRED = REQUIRED | frozenset(('iamar-kit.pck', 'KIT_VERSION.json'))
EXECUTABLES = frozenset(('iamar-world', 'tests/cli_shell_test.sh', 'tests/recipes_test.py'))


class InventoryError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InventoryError(message)


def relative_path(value):
    require(isinstance(value, str) and len(value) <= 512, 'Invalid inventory path')
    require(all(re.fullmatch(r'[A-Za-z0-9_.-]+', p) and p not in ('.', '..')
                for p in value.split('/')) and len(value.split('/')) <= 16,
            'Unsafe inventory path')
    return value


def directory(raw):
    """Open every absolute path component without following symbolic links."""
    raw = os.fspath(raw)
    require(isinstance(raw, str) and raw.startswith('/') and '\\' not in raw
            and '\0' not in raw, 'Expected absolute POSIX path')
    parts = raw.split('/')[1:]
    require(parts and all(p not in ('', '.', '..') for p in parts), 'Noncanonical path')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_regular(fd, name, limit, collect=False):
    f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        before = os.fstat(f)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                'Non-regular or hard-linked file: ' + name)
        require(before.st_size <= limit, 'File size limit: ' + name)
        digest, chunks, count = hashlib.sha256(), [], 0
        while True:
            chunk = os.read(f, min(65536, limit - count + 1))
            if not chunk:
                break
            count += len(chunk)
            require(count <= limit, 'File grew beyond limit: ' + name)
            digest.update(chunk)
            if collect:
                chunks.append(chunk)
        after = os.fstat(f)
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns) and count == before.st_size,
                'File changed during read: ' + name)
        return {'size': count, 'sha256': digest.hexdigest(),
                'mode': stat.S_IMODE(before.st_mode)}, b''.join(chunks)
    finally:
        os.close(f)


def read_path(path, limit=MAX_JSON):
    path = os.fspath(path)
    parent, name = os.path.split(path)
    require(name not in ('', '.', '..'), 'Invalid input file path')
    fd = directory(parent)
    try:
        return read_regular(fd, name, limit, True)[1]
    finally:
        os.close(fd)


def parse_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(InventoryError('Nonfinite JSON')))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise InventoryError('Invalid JSON: ' + str(error)) from error


def scan(kit):
    records, data, dirs = {}, {}, set()
    total = entries = 0
    wanted = {'index.html', 'ts-world/prebuilt/provenance.json', 'ts-world/LICENSES_RECEIPT.json',
              'ts-world/TYPESCRIPT_ASSEMBLY.json'}
    def visit(fd, prefix='', depth=0):
        nonlocal total, entries
        require(depth <= 16, 'Directory depth limit')
        # scandir consumes entries incrementally, rather than allocating an unbounded list.
        with os.scandir(fd) as iterator:
            for entry in iterator:
                entries += 1
                require(entries <= MAX_ENTRIES, 'Directory entry limit')
                path = relative_path(prefix + entry.name)
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    dirs.add(path)
                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        visit(child, path + '/', depth + 1)
                    finally:
                        os.close(child)
                else:
                    require(stat.S_ISREG(info.st_mode), 'Special file or symlink: ' + path)
                    require(len(records) < MAX_FILES, 'File count limit')
                    record, content = read_regular(fd, entry.name,
                        min(MAX_JSON if path in wanted else MAX_FILE, MAX_TOTAL - total), path in wanted)
                    records[path] = record
                    total += record['size']
                    if path in wanted:
                        data[path] = content
    fd = directory(kit)
    try:
        visit(fd)
    finally:
        os.close(fd)
    return records, data, dirs


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(value for key, value in attrs if key == 'href')


def verify(kit, inventory, inventory_sha256, typescript_manifest=None, *, profile='generic'):
    require(profile in ('generic', 'release'), 'Unknown inventory profile')
    required = RELEASE_REQUIRED if profile == 'release' else REQUIRED
    require(isinstance(inventory_sha256, str) and re.fullmatch('[0-9a-f]{64}', inventory_sha256),
            'Expected reviewed inventory SHA-256')
    raw = read_path(inventory)
    require(hashlib.sha256(raw).hexdigest() == inventory_sha256, 'Inventory pin mismatch')
    plan = parse_json(raw)
    require(isinstance(plan, dict) and set(plan) ==
            {'schema', 'source_revision', 'mode', 'evidence_kind', 'files'}, 'Inventory schema fields')
    require(type(plan['schema']) is int and plan['schema'] == 1, 'Inventory schema version')
    require(isinstance(plan['source_revision'], str) and
            re.fullmatch('[0-9a-f]{40}', plan['source_revision']), 'Source revision required')
    require(plan['mode'] in ('bundled', 'external'), 'Compiler mode required')
    require(plan['evidence_kind'] in ('fixture', 'existing-payload'), 'Evidence kind required')
    require(isinstance(plan['files'], list) and 0 < len(plan['files']) <= MAX_FILES, 'Inventory count')
    expected = {}
    for entry in plan['files']:
        require(isinstance(entry, dict) and set(entry) == {'path', 'size', 'sha256', 'mode'}, 'File schema')
        path = relative_path(entry['path'])
        require(path not in expected, 'Duplicate inventory path')
        require(type(entry['size']) is int and 0 <= entry['size'] <= MAX_FILE, 'Invalid file size')
        require(type(entry['mode']) is int and entry['mode'] in (0o644, 0o755), 'Invalid file mode')
        require(isinstance(entry['sha256'], str) and re.fullmatch('[0-9a-f]{64}', entry['sha256']), 'Invalid hash')
        expected[path] = {k: entry[k] for k in ('size', 'sha256', 'mode')}
    require(required <= expected.keys(), 'Incomplete required kit inventory')
    require(all(expected[p]['mode'] == (0o755 if p in EXECUTABLES else 0o644)
                for p in required), 'Required file mode mismatch')
    actual, data, dirs = scan(kit)
    require(actual.keys() == expected.keys(), 'Missing or unexpected kit files')
    expected_dirs = {str(p) for name in expected for p in Path(name).parents if str(p) != '.'}
    require(dirs == expected_dirs, 'Missing or unexpected kit directories')
    require(actual == expected, 'Kit size, hash or mode mismatch')
    provenance = parse_json(data['ts-world/prebuilt/provenance.json'])
    receipt = parse_json(data['ts-world/LICENSES_RECEIPT.json'])
    try:
        for key, path in (('guest', 'ts-world/prebuilt/iamar_ts_guest.wasm'),
                          ('spec', 'ts-world/world_api.json'),
                          ('thirdPartyNotices', 'ts-world/THIRD_PARTY_NOTICES.txt')):
            require(provenance[key]['sha256'] == actual[path]['sha256'], 'Guest provenance hash mismatch: ' + key)
            if key != 'spec':
                require(provenance[key]['bytes'] == actual[path]['size'], 'Guest provenance size mismatch: ' + key)
        require(provenance['noticeCoverage']['receiptSha256'] == actual['ts-world/LICENSES_RECEIPT.json']['sha256']
                and provenance['noticeCoverage']['uncoveredMembers'] == [], 'Guest notice coverage mismatch')
        require(receipt['notices_sha256'] == actual['ts-world/THIRD_PARTY_NOTICES.txt']['sha256']
                and receipt['notices_bytes'] == actual['ts-world/THIRD_PARTY_NOTICES.txt']['size']
                and receipt['unresolved'] == [], 'Guest license receipt mismatch')
    except (KeyError, TypeError) as error:
        raise InventoryError('Incomplete guest provenance/notice receipt') from error
    compiler = {p[len(TS_PREFIX):]: record for p, record in actual.items() if p.startswith(TS_PREFIX)}
    if plan['mode'] == 'bundled':
        require(typescript_manifest is not None, 'Bundled mode requires pinned TypeScript manifest')
        ts_raw = read_path(typescript_manifest)
        require(hashlib.sha256(ts_raw).hexdigest() == MANIFEST_SHA256, 'TypeScript manifest pin mismatch')
        ts = parse_json(ts_raw)
        official = {entry['path']: {**{k: entry[k] for k in ('size', 'sha256')}, 'mode': 0o644}
                    for entry in ts['files']}
        require(len(official) == 104 and compiler == official, 'Official TypeScript 104-file closure mismatch')
        require('ts-world/TYPESCRIPT_ASSEMBLY.json' in data, 'Missing compiler assembly receipt')
        assembly = parse_json(data['ts-world/TYPESCRIPT_ASSEMBLY.json'])
        require(isinstance(assembly, dict) and assembly.get('version') == '5.9.3'
                and type(assembly.get('files')) is int and assembly['files'] == 104
                and assembly.get('bytes') == sum(e['size'] for e in official.values())
                and assembly.get('archive_sha256') == ARCHIVE_SHA256, 'Compiler assembly receipt mismatch')
    else:
        require(not compiler and 'ts-world/TYPESCRIPT_ASSEMBLY.json' not in actual
                and not any(p.startswith('ts-world/node_modules/') for p in actual), 'External compiler mode mismatch')
    links = Links()
    try:
        links.feed(data['index.html'].decode('utf-8'))
    except (UnicodeError, ValueError) as error:
        raise InventoryError('Invalid index HTML') from error
    # The human-facing bundle index intentionally summarizes thumbnails rather
    # than linking each one. They remain fully covered by the reviewed inventory
    # and the exact size/hash/mode comparison above; only HTML coverage differs.
    delivered_links = set(actual) - {'index.html'}
    required_links = {p for p in delivered_links if not p.startswith('thumbnails/')}
    require(required_links <= set(links.links) <= delivered_links,
            'Index does not cover required kit files or links an undelivered file')
    return {'status': 'static-inventory-verified', 'evidence_kind': plan['evidence_kind'],
            'source_revision': plan['source_revision'], 'mode': plan['mode'], 'profile': profile,
            'files': len(actual), 'bytes': sum(v['size'] for v in actual.values()),
            'inventory_sha256': inventory_sha256, 'release_qualified': False,
            'limitations': 'Reviewed baseline agreement only; no archive, signature, runtime, native or target qualification.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--kit', required=True)
    parser.add_argument('--inventory', required=True)
    parser.add_argument('--inventory-sha256', required=True)
    parser.add_argument('--typescript-manifest', default=str(Path(__file__).absolute().parent / 'typescript-world/runtime_manifest.json'))
    parser.add_argument('--profile', choices=('generic', 'release'), default='generic',
                        help='Explicitly select release for downloaded kit folders; no auto-detection')
    args = parser.parse_args(argv)
    try:
        result = verify(args.kit, args.inventory, args.inventory_sha256, args.typescript_manifest,
                        profile=args.profile)
    except (InventoryError, OSError) as error:
        print('creator_kit_inventory: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
