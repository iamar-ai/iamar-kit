// Data-only generator regression. No compiler, guest, native engine or network.
// Run: node --test tests/creator_tool_bundle/installed_schema.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

// The generator and API files live in the browser repository (the iamar browser source (not public)); like
// tools/kit_bundle.sh, read them from IAMAR_BROWSER_REPO, else from this root.
const root = process.env.IAMAR_BROWSER_REPO || resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const missing = existsSync(join(root, 'tools/typescript-world/gen_bindings.mjs')) ? false
  : 'generator source not here: set IAMAR_BROWSER_REPO to an the iamar browser source (not public) checkout';
test('installed generation uses its spec-adjacent schema without source fallback', {skip: missing}, async () => {
  const temp = mkdtempSync(join(tmpdir(), 'iamar installed schema '));
  try {
    const installed = join(temp, 'kit', 'ts-world');
    mkdirSync(installed, {recursive: true});
    copyFileSync(join(root, 'tools/typescript-world/gen_bindings.mjs'), join(installed, 'gen_bindings.mjs'));
    for (const name of ['world_api.json', 'ui_page.schema.json']) {
      copyFileSync(join(root, 'api', name), join(installed, name));
    }
    const {generate} = await import(pathToFileURL(join(installed, 'gen_bindings.mjs')).href);
    const spec = join(installed, 'world_api.json');
    const schema = join(installed, 'ui_page.schema.json');
    const output = generate(spec);
    const sdkKey = Object.keys(output).find(k => k.endsWith('iamar-world.d.ts'));
    const moduleKey = Object.keys(output).find(k => k.endsWith('api_generated.mjs'));
    assert.equal(output[sdkKey], readFileSync(join(root, 'api/typescript/iamar-world.d.ts'), 'utf8'));
    assert.equal(output[moduleKey], readFileSync(join(root, 'tools/typescript-world/api_generated.mjs'), 'utf8'));
    // Poison the old repo-relative location: it must never be selected.
    mkdirSync(join(temp, 'api'));
    writeFileSync(join(temp, 'api/ui_page.schema.json'), 'not JSON');
    assert.deepEqual(generate(spec), output);
    rmSync(schema);
    assert.throws(() => generate(spec), error => error.code === 'ENOENT' && error.path === schema);
    writeFileSync(schema, 'not JSON');
    assert.throws(() => generate(spec), SyntaxError);
    // Explicit alternate schema remains supported for controlled generation.
    assert.deepEqual(generate(spec, join(root, 'api/ui_page.schema.json')), output);

    // A custom spec selects its own sibling, not the installed kit's schema.
    copyFileSync(join(root, 'api/ui_page.schema.json'), schema);
    const customDir = join(temp, 'custom spec');
    mkdirSync(customDir);
    const customSpec = join(customDir, 'world_api.json');
    const customSchema = join(customDir, 'ui_page.schema.json');
    copyFileSync(spec, customSpec);
    assert.throws(() => generate(customSpec), error => error.code === 'ENOENT' && error.path === customSchema);
    assert.deepEqual(generate(customSpec, schema), output);
    copyFileSync(schema, customSchema);
    assert.deepEqual(generate(customSpec), output);
    writeFileSync(customSchema, 'not JSON');
    assert.throws(() => generate(customSpec), SyntaxError);
  } finally {
    rmSync(temp, {recursive: true, force: true});
  }
});
