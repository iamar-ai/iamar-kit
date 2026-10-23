// Real production supervisor plus real Bash launcher and an inert Python engine.
// No Godot, graphics, audio driver, package opener, signing or network is run.
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
const backend=resolve(process.argv[2]);
const {runOwnedKit}=await import(pathToFileURL(join(backend,'host/creator_process.js')));
const root=mkdtempSync(join(tmpdir(),'kit-audio-owned-')),engine=join(root,'inert-engine'),project=join(root,'project'),draft=join(root,'draft'),mode=join(root,'mode.json');
mkdirSync(project);mkdirSync(draft);writeFileSync(join(project,'project.godot'),'config_version=5\n');writeFileSync(join(draft,'manifest.json'),'{}');
writeFileSync(engine,`#!/usr/bin/python3\nimport json,sys\nmode=json.load(open(${JSON.stringify(mode)}))\nassert sys.argv[1:3]==['--audio-driver','Dummy']\nprint(json.dumps({'args':sys.argv[1:],'inert':True}))\nsys.stderr.write(mode.get('stderr',''))\nsys.exit(mode.get('exit',0))\n`,{mode:0o700});
const launcher=fileURLToPath(new URL('../../kit/iamar-world',import.meta.url));
const checks=[];
try{
 for(const command of ['new','validate','preview','pack','verify']){
  for(const [label,settings,expected] of [
   ['warning',{stderr:'WARNING: optional non-audio warning\n'},null],
   ['script-error',{stderr:'SCRIPT ERROR: synthetic refusal\n'},'kit-failed'],
   ['alsa-shaped-error',{stderr:'ERROR: Condition "status < 0" is true. Returning: ERR_CANT_OPEN\n'},'kit-failed'],
   ['nonzero',{exit:7},'kit-failed']]){
   writeFileSync(mode,JSON.stringify(settings));
   const run=runOwnedKit(launcher,[command,draft,join(root,'unused.out'),join(root,'unused.key'),'Synthetic'],{env:{PATH:'/usr/bin:/bin',HOME:root,GODOT:engine,IAMAR_PROJECT:project},timeoutMs:2000,maxOutputBytes:16384});
   if(expected)await assert.rejects(run,error=>error.code===expected);else assert((await run).stdout.includes('"inert": true'));
   checks.push(command+': '+label);
  }
 }
 console.log(JSON.stringify({passed:true,checks:checks.length,engineInvocations:0,supervisedInertCases:checks}));
}finally{rmSync(root,{recursive:true,force:true});}
