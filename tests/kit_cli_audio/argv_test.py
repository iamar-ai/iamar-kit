"""Exercise the real thin POSIX launcher against an inert browser/Godot recorder."""
import json, os, pathlib, shutil, subprocess, tempfile

source=pathlib.Path(__file__).resolve().parents[2]
commands={
 'new':['draft with spaces','--author','Fixture Name'],
 'validate':['draft with spaces','--report-v1'],
 'preview':['draft with spaces','out','--view','1,2,3>4,5,6'],
 'perf':['draft with spaces','out'],'impostors':['draft with spaces','--px','64'],
 'techniques':['draft with spaces','--strict'],'tiers':['draft with spaces'],
 'assets':['search','--worlds','oak tree'],'sign':['draft with spaces','key.key','Fixture Name'],
 'verify':['draft with spaces'],'pack':['draft with spaces','out.iamar','key.key','Fixture Name'],
 'package':['draft with spaces','out.iamar','key.key','Fixture Name'],
 'keygen':['key.key'],'serve':['--package=out.iamar','--port=0'],
 'host':['--package=out.iamar','--port=0'],'add-to-browser':['out.iamar'],
 'where':[],'help':[],
}
checks=[]
def require(value,label):
 if not value: raise AssertionError(label)
 checks.append(label)
with tempfile.TemporaryDirectory(prefix='iamar kit argv ') as directory:
 root=pathlib.Path(directory); log=root/'argv.jsonl'; engine=root/'inert engine'
 engine.write_text('#!/usr/bin/python3\nimport json,pathlib,sys\np=pathlib.Path('+repr(str(log))+')\nif sys.argv[-3:]==["--","--kit","where"]: sys.exit(0)  # check_browser compatibility probe\nwith p.open("a") as out: out.write(json.dumps(sys.argv[1:])+"\\n")\n')
 engine.chmod(0o700)
 project=root/'source project'; project.mkdir(); (project/'project.godot').write_text('config_version=5\n')
 for route in ['source','explicit-downloaded','auto-downloaded']:
  home=root/route; home.mkdir(); launcher=source/'kit/iamar-world'
  env={'PATH':'/usr/bin:/bin','HOME':str(home),'GODOT':str(engine),'IAMAR_PROJECT':str(project)}
  if route=='explicit-downloaded': env['IAMAR_BROWSER']=str(engine)
  if route=='auto-downloaded':
   bundle=home/'bundle'; (bundle/'kit').mkdir(parents=True); launcher=bundle/'kit/iamar-world'
   shutil.copy2(source/'kit/iamar-world',launcher); shutil.copy2(engine,bundle/'Oakhaven.x86_64'); env.pop('IAMAR_PROJECT')
  for command,arguments in commands.items():
   log.write_text('')
   completed=subprocess.run(['/bin/bash',str(launcher),command,*arguments],env=env,cwd=root,capture_output=True,timeout=5)
   require(completed.returncode==0,f'{route}/{command} exits')
   records=[json.loads(line) for line in log.read_text().splitlines()]
   require(len(records)==1,f'{route}/{command} exactly one browser invocation')
   record=records[0]; sep=record.index('--')
   require(record[:sep].count('--audio-driver')==1,f'{route}/{command} dummy audio once')
   require(record[sep+1:sep+3]==['--kit',command],f'{route}/{command} built-in dispatch')
   require(record[sep+3:sep+5]==['--cwd',str(root)],f'{route}/{command} explicit cwd')
   if command=='assets': require(record[sep+5:]==['search','oak tree'],f'{route}/assets search --worlds reaches the browser without the flag')
   should_headless=command not in {'preview','perf','impostors'}
   require(('--headless' in record[:sep])==should_headless,f'{route}/{command} headless policy')
 windows=(source/'kit/iamar-world.cmd').read_text()
 require('set "PWD=%CD%"' in windows,'Windows wrapper supplies its cwd to embedded tools')
 require('if /i "%CMD%"=="package"        goto pack' in windows,'Windows package alias')
 print(json.dumps({'passed':True,'checks':len(checks),'routes':3,'commands':len(commands),'engineInvocations':3*len(commands)},indent=2))
