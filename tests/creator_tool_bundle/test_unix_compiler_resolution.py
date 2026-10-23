#!/usr/bin/env python3
"""Recorder-only wrapper routing checks. Never executes Node, compiler or engine."""
import itertools
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

WRAPPER = Path(__file__).resolve().parents[2] / 'kit' / 'iamar-world'

class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='iamar resolver ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.kit = self.root / 'download/kit'
        self.kit.mkdir(parents=True)
        self.wrapper = self.kit / 'iamar-world'
        shutil.copyfile(WRAPPER, self.wrapper)
        self.project = self.root / 'source checkout'
        self.project.mkdir()
        self.template = self.root / 'template'; self.template.mkdir()
        self.source = self.file('world source.ts')
        self.compiler = self.file('official compiler/typescript.js')
        self.log = self.root / 'calls'
        self.stub = self.file('recorder', '''#!/bin/bash
printf '%s\\0' "$@" >> "$RECORD"
printf '\\n' >> "$RECORD"
if [[ "${1:-}" == -p ]]; then printf '%s\\n' "${NODE_OK:-true}"; exit 0; fi
exit "${RECORDER_STATUS:-0}"
''')
        self.stub.chmod(0o755)
        self.env = {k:v for k,v in os.environ.items() if not k.startswith('IAMAR_') and k not in ('GODOT','BLENDER')}
        self.env.update(IAMAR_TS_NODE=str(self.stub), IAMAR_BROWSER=str(self.stub), GODOT=str(self.stub), BLENDER=str(self.stub), RECORD=str(self.log))

    def file(self, path, text='inert fixture; never executed\n'):
        p = self.root / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text); return p

    def layout(self, source=False, mask=7):
        base = self.project / 'tools/typescript-world' if source else self.kit / 'ts-world'
        paths = [base/'pack.mjs', base/'prebuilt/iamar_ts_guest.wasm', self.project/'api/typescript/iamar-world.d.ts' if source else base/'iamar-world.d.ts']
        for i,p in enumerate(paths):
            if mask & (1 << i): self.file(p)
            elif p.exists(): p.unlink()
        return paths

    def bundled(self, loose=False):
        return self.file(self.kit / ('ts-world/typescript.js' if loose else 'ts-world/node_modules/typescript/lib/typescript.js'))

    def run_wrapper(self, extra=None, args=None):
        env = self.env.copy(); env.update(extra or {})
        if self.log.exists(): self.log.unlink()
        proc = subprocess.run(['/bin/bash', str(self.wrapper), *(args or ['compile-typescript', str(self.source), str(self.template), str(self.root/'fresh output')])], cwd=self.root, env=env, capture_output=True, text=True, timeout=5)
        calls = [row.split(b'\0')[:-1] for row in self.log.read_bytes().splitlines()] if self.log.exists() else []
        self.assertFalse((self.root/'fresh output').exists())
        return proc, [[x.decode() for x in row] for row in calls]

    def assert_pack(self, calls, paths, compiler):
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], '-p')
        self.assertEqual(calls[1], [str(paths[0]), '--source', str(self.source), '--sdk', str(paths[2]), '--typescript', str(compiler), '--prebuilt', str(paths[1]), '--template', str(self.template), '--out', str(self.root/'fresh output')])

    def test_complete_kit_default_and_module_precedence(self):
        paths=self.layout(); compiler=self.bundled(); self.bundled(loose=True); self.layout(source=True)
        proc,calls=self.run_wrapper(); self.assertEqual(proc.returncode,0,proc.stderr); self.assert_pack(calls,paths,compiler)

    def test_loose_legacy_compiler(self):
        paths=self.layout(); compiler=self.bundled(loose=True)
        proc,calls=self.run_wrapper(); self.assertEqual(proc.returncode,0); self.assert_pack(calls,paths,compiler)

    def test_explicit_compiler_is_authoritative(self):
        paths=self.layout(); self.bundled()
        proc,calls=self.run_wrapper({'IAMAR_TS_COMPILER':str(self.compiler)})
        self.assertEqual(proc.returncode,0); self.assert_pack(calls,paths,self.compiler)

    def test_invalid_explicit_compilers_fail_before_node(self):
        self.layout(); self.bundled()
        for value in ['', str(self.root/'missing'), 'relative.js', str(self.template)]:
            with self.subTest(value=value):
                proc,calls=self.run_wrapper({'IAMAR_TS_COMPILER':value})
                self.assertEqual(proc.returncode,2); self.assertIn('IAMAR_TS_COMPILER',proc.stderr); self.assertEqual(calls,[])

    def test_inherited_project_keeps_complete_kit(self):
        paths=self.layout(); compiler=self.bundled(); self.layout(source=True)
        for value in [str(self.project), '', 'relative', str(self.root/'missing')]:
            with self.subTest(project=value):
                proc,calls=self.run_wrapper({'IAMAR_PROJECT':value})
                self.assertEqual(proc.returncode,0,proc.stderr); self.assert_pack(calls,paths,compiler)

    def test_source_set_compiler_discovery(self):
        paths=self.layout(source=True); self.bundled()
        proc,calls=self.run_wrapper({'IAMAR_PROJECT':str(self.project)})
        self.assertEqual(proc.returncode,2); self.assertEqual(calls,[])
        for name in ['typescript.js','node_modules/typescript/lib/typescript.js']:
            compiler=self.file(self.project/'tools/typescript-world'/name)
            proc,calls=self.run_wrapper({'IAMAR_PROJECT':str(self.project)})
            self.assertEqual(proc.returncode,0,proc.stderr); self.assert_pack(calls,paths,compiler)

    def test_all_layout_combinations_never_mix(self):
        self.bundled()
        for kit_mask,source_mask in itertools.product(range(8),range(8)):
            with self.subTest(kit=kit_mask,source=source_mask):
                kit=self.layout(mask=kit_mask); source=self.layout(source=True,mask=source_mask)
                env={'IAMAR_TS_COMPILER':str(self.compiler),'IAMAR_PROJECT':str(self.project)}
                proc,calls=self.run_wrapper(env)
                kit_selected=bool(kit_mask & 1)
                complete=(kit_mask if kit_selected else source_mask)==7
                self.assertEqual(proc.returncode,0 if complete else 2,proc.stderr)
                if complete: self.assert_pack(calls,kit if kit_selected else source,self.compiler)
                else: self.assertIn('incomplete',proc.stderr); self.assertEqual(calls,[])

    def test_documented_adjacent_source_checkout_fallback(self):
        self.project=self.kit.parent
        paths=self.layout(source=True)
        proc,calls=self.run_wrapper({'IAMAR_TS_COMPILER':str(self.compiler)})
        self.assertEqual(proc.returncode,0,proc.stderr); self.assert_pack(calls,paths,self.compiler)

    def test_invalid_authoritative_kit_entries_refuse_fallback(self):
        self.layout(source=True); packer=self.kit/'ts-world/pack.mjs'
        packer.parent.mkdir(parents=True); packer.mkdir()
        env={'IAMAR_PROJECT':str(self.project),'IAMAR_TS_COMPILER':str(self.compiler)}
        proc,calls=self.run_wrapper(env); self.assertEqual(proc.returncode,2); self.assertEqual(calls,[])
        packer.rmdir(); packer.symlink_to(self.root/'missing-packer')
        proc,calls=self.run_wrapper(env); self.assertEqual(proc.returncode,2); self.assertEqual(calls,[])

    def test_missing_compiler_and_old_node(self):
        self.layout()
        proc,calls=self.run_wrapper(); self.assertEqual(proc.returncode,2); self.assertEqual(calls,[])
        self.bundled()
        proc,calls=self.run_wrapper({'NODE_OK':'false'}); self.assertEqual(proc.returncode,2); self.assertEqual(len(calls),1)

    def test_packer_exit_propagates(self):
        self.layout(); self.bundled()
        proc,calls=self.run_wrapper({'RECORDER_STATUS':'7'}); self.assertEqual(proc.returncode,7); self.assertEqual(len(calls),2)

    def test_from_source_legacy_route(self):
        self.file(self.project/'tools/typescript-world/build.mjs'); self.file(self.project/'api/typescript/iamar-world.d.ts')
        lock=self.file('lock.json'); qjs=self.root/'quickjs'; qjs.mkdir(); wasi=self.root/'wasi'; wasi.mkdir()
        proc,calls=self.run_wrapper({'IAMAR_PROJECT':str(self.project),'IAMAR_TS_COMPILER':str(self.compiler),'IAMAR_TS_DEPENDENCY_LOCK':str(lock),'IAMAR_TS_QUICKJS':str(qjs),'IAMAR_TS_WASI_SDK':str(wasi)}, ['compile-typescript','--from-source',str(self.source),str(self.template),str(self.root/'fresh output')])
        self.assertEqual(proc.returncode,0,proc.stderr); self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][0],str(self.project/'tools/typescript-world/build.mjs')); self.assertIn('--quickjs',calls[0]); self.assertNotIn('--prebuilt',calls[0])

    def test_legacy_native_dispatch_recorder_only(self):
        # The first command asks the browser once (`--kit where`, check_browser) and stamps
        # kit/runtime/.compatible-<key>; later commands with the same browser file dispatch only.
        probe=['--headless','--audio-driver','Dummy','--','--kit','where']
        for i,command in enumerate(['new','validate','preview','perf','impostors','help','package']):
            with self.subTest(command=command):
                proc,calls=self.run_wrapper({'IAMAR_TS_COMPILER':'bad','IAMAR_PROJECT':''},[command,'argument with spaces'])
                self.assertEqual(proc.returncode,0,proc.stderr)
                if i == 0:
                    self.assertEqual(len(calls),2); self.assertEqual(calls[0],probe); calls=calls[1:]
                    self.assertTrue(any(p.name.startswith('.compatible-') for p in (self.kit/'runtime').iterdir()))
                self.assertEqual(len(calls),1)
                expected=['--audio-driver','Dummy']+([] if command in ['preview','perf','impostors'] else ['--headless'])+['--','--kit',command,'--cwd',str(self.root),'argument with spaces']
                self.assertEqual(calls[0],expected)

if __name__ == '__main__': unittest.main(verbosity=2)
