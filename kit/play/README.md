# iamar-world play: walk your draft at once

```
iamar-world play <world folder> [--hero human_male] [--timeout 600] [--no-reload] [--quit-after S] [--headless]
```

Opens the world folder you are building in the real iamar browser game and puts you in it:
walk, swim, talk to its NPCs and run its quests. No keygen, sign, package or add-to-browser
first. Those steps are only for sharing the world (`iamar-world publish`, AGENT_KIT.md).

- **A draft, never published.** A "DRAFT - not published" banner stays at the top of the
  screen. The run is offline (no hub, no other visitors), and nothing is signed, packaged,
  uploaded or hosted. The HUD shows the world as unsigned.
- **Reloads when you save.** Save any file of the world (scene.json, manifest.json, a script,
  an asset) and the world is rebuilt within about two seconds, with you standing where you
  were. A save that does not open (broken JSON, a missing file) keeps the last good build;
  the banner and the console say why (`PLAY RELOAD FAILED ...`). `--no-reload` turns it off.
- **Your own profile is never touched.** The launchers run the browser with a separate draft
  profile (`iamar-draft-profile` in your user data folder: `~/.local/share` on Linux,
  `%LOCALAPPDATA%` on Windows; `IAMAR_PLAY_PROFILE` picks another folder). It is kept between
  runs, so only the first `play` builds the city cache (a minute or more on a slow computer;
  raise `--timeout` if it gives up).
- **Stop** by closing the window.

Who does what: the agent runs `iamar-world play <folder>`; the person walks around and says
what to change; the agent edits and saves, and the open window shows the change.

Console lines (for agents):

| Line | Meaning |
|---|---|
| `PLAY <id>: a DRAFT (unsigned, local only, offline, never hosted) ...` | the folder opened |
| `PLAY READY <id> after <s> s` | the person is in the world |
| `PLAY RELOADED <id> (<n>)` | a save was picked up |
| `PLAY RELOAD FAILED <why>` | the save does not open; the last build stays |
| `WARN <text>` | the world's own warnings (first 5; `iamar-world validate` lists all) |
| `PLAY END <id>` | `--quit-after` ran out |

Exit 0 after a normal end, 1 when the browser or the world does not start, 2 bad input
(not a folder, a folder that does not open, an unknown option).

`--quit-after S` ends the run S seconds after arrival, `--headless` runs without a window:
both are for tests and agents checking that a folder plays (`tests/kit_play/run.sh`).
For a scripted walk with checks, use `iamar-world playtest` (kit/playtest/README.md).

Implementation: `scripts/kit/world_play.gd` (Godot side); test: `tests/kit_play/run.sh`.
