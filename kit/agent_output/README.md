# Agent-readable kit output: `--json` and `NEXT:`

`agent_output.py` turns the tagged text lines of the native kit commands (`STATS`, `VIEW`,
`TARGET`, `WARN`, `ERROR` ...) into one JSON object, adds a fix hint to every error and
warning, and works out the next command. Both launchers (`kit/iamar-world`,
`kit\iamar-world.cmd`) use it. Python 3, standard library only.

## `--json`

```sh
iamar-world validate worlds/beach --json
iamar-world perf worlds/beach shots/beach/view --json
```

Commands: `new validate preview perf techniques tiers impostors assets package pack sign verify
keygen add-to-browser playtest where`. The launcher runs the command as usual without `--json`
(the browser never sees it) and prints one JSON object instead of the text, with the same exit
code. `doctor`, `lint`, `audit`, `terrain`, `compare-shots` and `assets search` have their own
`--json`. Without Python the launcher still prints JSON: an error saying Python 3 is missing.

Schema `iamar-kit-output/1` (`tests/kit_agent_output` pins the keys):

| key | meaning |
|---|---|
| `schema`, `command`, `args`, `exit_code`, `ok` | `ok` is `exit_code == 0`; `args` exclude `--json` |
| `errors`, `warnings` | `[{message, fix}]`: ERROR / WARN lines, failed TARGETs, a failed run's stderr. `fix` is never empty |
| `notes` | NOTE lines |
| `next` | `{command, why, human_step, after_failure}` or `null`: the next command on the happy path, or the rerun after a failure. `human_step` names what only the user does (approve a key, Start Hosting) |
| `data` | what was measured (below) |
| `records` | every tagged stdout line in order, `{tag, text}`, for anything `data` does not cover |
| `other` | untagged lines (stdout, then stderr) |

`data` by command (present when the command printed it):

* validate / preview / perf: `package`, `world {id,title,version,author}`, `signer`,
  `stats {name: {used, budget}}`, `npcs`, `quests`, `spawn`, `reuse {new_bytes, reused_bytes, objects}`,
  `tiers [{tier, ok, triangles, texture_size, texture_bytes, errors}]`, `result` (`OK`/`FAILED`),
  `views [{index, name, draw_calls, primitives, objects, fps, file}]` (`fps` null when not measured),
  `targets [{name, status, value, limit, recipes, text}]` (`status` PASS, FAIL, INFO or NOT_MEASURED),
  `targets_result`, `timings_ms {open, build, preview}`, `report` (the `--report-v1` JSON)
* new: `new {id, title, folder}`, `template`
* techniques: `techniques {name: {count, text}}`, `advice []`, `off []`
* package / pack: `packed {path, bytes, pieces, sha256}`, `pieces {path, signed}`
* sign: `signed {folder, files, key_id, signer}`; verify: `signer`, `status`; keygen: `key`, `public`, `key_id`
* add-to-browser: `added`, `human_step`; playtest: `playtest {result, steps, failed, report}`
* where: `kit`, `pack`, `docs`, `agent_kit`, `browser`; assets: `count`, `used`

## Fix hints

A message's own advice is its fix (`... Set its y to 0.00.` gives `Set its y to 0.00.`; a TARGET
FAIL gives its recipes). Messages without advice are matched against `FIX_TABLE`; anything else
gets a pointer to AGENT_KIT.md and WORLD_FORMAT.md. When a native message has no advice, prefer
adding the advice to the message itself (`scripts/kit/*.gd`) over growing the table.

## `NEXT:`

Every human-mode run of the commands above ends with one line, for example

```
NEXT: iamar-world preview worlds/beach shots/beach/view
NEXT: iamar-world validate worlds/beach   (fix the ERROR lines above, then rerun)
NEXT: iamar-world package worlds/beach out/beach.iamar <key> "<Your Name>"   (your user: approve the signing key (and its name) before packaging)
```

The chain: new > validate > preview > perf > playtest > (review gate) > package > verify >
add-to-browser > the user's Start Hosting. `IAMAR_KIT_NO_NEXT=1` turns the line off.

## Direct use

```sh
python3 kit/agent_output/agent_output.py parse validate 0 worlds/beach < validate.log   # a saved log
python3 kit/agent_output/agent_output.py next validate 0 worlds/beach                    # just the NEXT line
```

## Activity log (an internal task)

Every run of a world command (`new validate preview perf techniques tiers impostors package pack sign verify
add-to-browser playtest play lint audit shots`) appends one JSON line to `<world folder>/.iamar/activity.jsonl`:
`time, command, args, ok, exit_code, errors, warnings, next, human_step`. `errors` and `warnings` are lists in
`--json` runs and `null` in human runs. The Studio reads the file. `validate` and `package` read only what
`scene.json` and `manifest.json` list, so `.iamar/` is never validated or packed. `IAMAR_KIT_NO_ACTIVITY=1`
turns the log off; it is trimmed to the last 200 lines past 256 KB. Test: `tests/kit_activity/test_activity.py`.
