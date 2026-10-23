extends SceneTree
## Scripted playtest of a world package in the real browser game (kit command
## `iamar-world playtest`, see kit/playtest/README.md for the steps file).
##
##   iamar-world playtest <world> <out> --steps <steps.json> [--headless] [--hero human_male] [--hour 12] [--timeout 600] [--online]
##   iamar-world playtest <world> <out> --auto [--steps <steps.json>] ...   (walk to every room, portal, water body, NPC, object)
##   (the launchers run: <browser> [--headless] -- --kit-script res://scripts/kit/world_playtest.gd --cwd <dir> ...)
##
## It boots the browser's own game scene, picks a hero, and enters <world> the way a
## visitor does (WorldSwitcher._enter_package: QuestBridge for NPCs and quests,
## PackageScriptHost for the world scripts, the real Gameplay node for talk and pickups).
## Then it runs the steps (goto / talk / pickup / use / wait, and the exploration steps
## walk_to / enter / climb / swim_to / dive / surface / look_at that really walk and swim the
## visitor, an internal task), each followed by the step's expectations, and prints per step:
##   STEP <n> <do> ok|FAIL <why>
##   QUEST <id> <state> step=<i> counts=[..]       every quest of the world
##   EFFECT moved|light|sound|note|visible ...     what the world's scripts changed
##   EXPECT ok|FAIL <what>
##   SHOT <path>                                   when a renderer is present (not --headless)
## and writes <out>/playtest.json. Ends with PLAYTEST PASS|FAIL; exit 0 pass, 1 fail, 2 bad input.
## The launchers give the browser a private profile for the run (OAK_SETTINGS, XDG_DATA_HOME,
## APPDATA on Windows), so the player's settings, saves and world data are never touched.

const STEP_KINDS := ["goto", "talk", "pickup", "use", "wait", "walk_to", "enter", "climb", "swim_to", "dive", "surface", "look_at"]
const Routes := preload("res://scripts/kit/world_playtest_routes.gd")
const WAYPOINT := 0.45       ## m: a route's waypoint counts as passed this close (horizontally)
const STUCK_S := 2.5         ## script seconds without 0.3 m of progress: the walk is stuck
const FALL := 3.0            ## m dropped through the air (not into water) is reported as a fall
## the browser's own flags, read by the game scene (--offline: no hub, no other visitors)
const BROWSER_FLAGS := ["--offline"]
const MAIN_SCENE := "res://scenes/main.tscn"
const PROGRESS_SCRIPT := "res://scripts/gameplay/progress.gd"
const NEXT_BOOT_META := "iamar_next_boot"   ## Main's "start"/"city" (Main.NEXT_BOOT_META)
const NEAR := 1.6            ## metres from an NPC, pickup or entity when the step walks up to it
const MOVED := 0.05          ## an entity that moved further than this (m) during a step is reported
const LIGHT_DELTA := 0.01
## The browser's own first-visit quests. Until the second is done, its two welcome guides
## (Goodwife Alys, Guide Rowan: SpawnGuides) walk with the player into EVERY world, a kit
## world too; they are the browser's, not the world's (an internal task).
const WELCOME_QUESTS := ["thornbury_welcome", "welcome_menus"]

var _world_dir := ""
var _out := ""
var _steps_path := ""
var _hero := "human_male"
var _cwd := ""
var _hour := -1.0
var _timeout := 600.0
var _main: Node
var _gp: Node
var _shell: Node
var _pkg: WorldPackage
var _wid := ""
var _scripts: Array = []
var _sounds: Array = []      ## [name, Vector3] since the last step began
var _notes: Array = []       ## world script notes since the last step began
var _report := {"steps": [], "ok": false}
var _fails := 0
var _t0 := 0
var _shots := true
var _ignore: Array = []      ## entity kinds left out of EFFECT lines (ambient motion: gulls, boats)
var _scene_fx: Dictionary = {}   ## scene id -> Node: what quests' on_complete show, hide or light (QuestEffects)
var _new_visitor := false    ## steps file "new_visitor": true keeps the welcome guides (a first-time player)
var _online := false         ## --online / steps file "online": true: connect to the hub (default: offline)
var _practice_notice := ""   ## the browser's offline-practice line, cut from dialog text
var _step_n := 0             ## the step running now (0 before the first), for progress-reset warnings
var _slow_s := 0.0           ## wall seconds the waits ran behind script time (frames over 1/15 s; see _script_seconds)
var _auto := false           ## --auto: add the steps that visit every room, portal, water body, NPC and object
var _rooms_cache := {}       ## asset path -> its rooms sidecar ({} for none)


func _initialize() -> void:
	_t0 = Time.get_ticks_msec()
	var err := _parse(OS.get_cmdline_user_args())
	if err != "":
		printerr("ERROR playtest: " + err)
		quit(2)
		return
	_shots = DisplayServer.get_name() != "headless"
	# never the player's own profile (settings, hero, tutorial): a private file per run
	if OS.get_environment("OAK_SETTINGS") == "":
		var dir := OS.get_temp_dir().path_join("iamar-playtest-%d" % OS.get_process_id())
		DirAccess.make_dir_recursive_absolute(dir)
		OS.set_environment("OAK_SETTINGS", dir.path_join("settings.cfg"))
	_run.call_deferred()


func _parse(a: PackedStringArray) -> String:
	var pos: Array = []
	var i := 0
	# skip the dispatcher's own "--kit-script <path>"
	if a.size() >= 2 and a[0] == "--kit-script":
		i = 2
	while i < a.size():
		var s := String(a[i])
		if s in ["--steps", "--hero", "--hour", "--timeout", "--cwd"]:
			if i + 1 >= a.size():
				return "%s needs a value" % s
			var v := String(a[i + 1])
			match s:
				"--steps": _steps_path = v
				"--hero": _hero = v
				"--hour": _hour = float(v)
				"--timeout": _timeout = float(v)
				"--cwd": _cwd = v
			i += 2
			continue
		if s in BROWSER_FLAGS:
			i += 1
			continue
		if s == "--online":
			_online = true
			i += 1
			continue
		if s == "--auto":
			_auto = true
			i += 1
			continue
		if s.begins_with("--"):
			return "unknown option " + s
		pos.append(s)
		i += 1
	if _cwd == "":
		_cwd = OS.get_environment("PWD")   # iamar-world.cmd sets it (cmd has no --cwd form)
	if pos.size() != 2 or (_steps_path == "" and not _auto):
		return "usage: world_playtest.gd <world> <out> --steps <steps.json> | --auto"
	_world_dir = _abs(String(pos[0]))
	_out = _abs(String(pos[1]))
	if _steps_path != "":
		_steps_path = _abs(_steps_path)
	return ""


## A path given on the command line, relative to --cwd (the wrappers pass the caller's folder).
func _abs(p: String) -> String:
	if p.is_absolute_path() or _cwd == "":
		return p
	return _cwd.path_join(p).simplify_path()


func _elapsed() -> float:
	return (Time.get_ticks_msec() - _t0) / 1000.0


## What is left of the --timeout budget (s). A first rendered run with a fresh profile
## builds the whole city before hero selection, which can take many minutes.
func _left() -> float:
	return maxf(0.0, _timeout - _elapsed())


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _seconds(s: float) -> void:
	var end := Time.get_ticks_msec() + int(s * 1000.0)
	while Time.get_ticks_msec() < end:
		await process_frame


## A step's `wait` and `settle`: s seconds of SCRIPT time, the clock of iamar.time() and
## timer_after (WorldScript adds up each frame's delta). The engine caps one frame's delta at
## max_physics_steps_per_frame / physics_ticks_per_second (4 / 60 s in the browser), so below
## 15 fps script time runs behind the wall clock: a wall-clock settle of 3 s ended before the
## harbour lamp's 1.8 s timer_after came due (harbour a5 gap G15b; at 250 ms frames on any
## computer). Boot and entry waits stay on the wall clock (_seconds): they wait for the browser.
func _script_seconds(s: float) -> void:
	var game := 0.0
	var w0 := Time.get_ticks_msec()
	while game < s and _elapsed() <= _timeout:
		await process_frame
		game += root.get_process_delta_time()
	var wall := (Time.get_ticks_msec() - w0) / 1000.0
	if wall > game + 0.5:
		_slow_s += wall - game


## Waits until cond is true (polling every frame); false after `limit` seconds.
func _until(cond: Callable, limit: float) -> bool:
	var end := Time.get_ticks_msec() + int(limit * 1000.0)
	while not bool(cond.call()):
		if Time.get_ticks_msec() > end or _elapsed() > _timeout:
			return false
		await process_frame
	return true


func _finish(code: int, why := "") -> void:
	_step_n = 0   # quitting ends the progress lifetime too: not a reset during a step
	if why != "":
		printerr("ERROR playtest: " + why)
		_report["error"] = why
	_report["ok"] = code == 0
	_report["seconds"] = snappedf(_elapsed(), 0.1)
	if _slow_s > 0.0:
		_report["slow_frames_s"] = snappedf(_slow_s, 0.1)
		print("NOTE slow frames: the steps' waits ran %.1f s longer than script time (frames over 1/15 s: the engine caps each frame's delta, so world scripts' timers run late on this computer; wait and settle count script time)" % _slow_s)
	DirAccess.make_dir_recursive_absolute(_out)
	var f := FileAccess.open(_out.path_join("playtest.json"), FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(_report, "  "))
		f.close()
	print("PLAYTEST %s: %d step(s), %d failed -> %s" % ["PASS" if code == 0 else "FAIL",
		(_report.steps as Array).size(), _fails, _out.path_join("playtest.json")])
	quit(code)


func _run() -> void:
	var data: Variant = {"steps": []} if _steps_path == "" else JSON.parse_string(FileAccess.get_file_as_string(_steps_path))
	if not data is Dictionary or not (data as Dictionary).get("steps") is Array:
		_finish(2, "steps file %s needs {\"steps\": [...]}" % _steps_path)
		return
	var steps: Array = data.steps
	if data.has("hero"): _hero = String(data.hero)
	if data.has("hour"): _hour = float(data.hour)
	if data.get("ignore") is Array: _ignore = data.ignore
	_new_visitor = bool(data.get("new_visitor", false))
	_online = _online or bool(data.get("online", false))
	for s in steps:
		if not s is Dictionary or not String(s.get("do", "")) in STEP_KINDS:
			_finish(2, "every step needs \"do\": one of %s" % ", ".join(STEP_KINDS))
			return
	_pkg = WorldPackage.open(_world_dir)
	if _pkg == null or not _pkg.ok:
		_finish(2, "the world does not open: %s" % ("; ".join(_pkg.errors.slice(0, 3)) if _pkg else _world_dir))
		return
	_wid = _pkg.id
	_report["world"] = _wid
	if _auto:
		var auto := Routes.auto_steps(_pkg.scene, _rooms_of, _pkg.spawn_point.origin)
		steps = steps + auto
		print("playtest: --auto adds %d step(s): every water body, house room, portal, NPC and named object, each walked from the spawn" % auto.size())
	# offline by default (an internal task): online, every hub/session change (connect, scene
	# admitted, reconnect) restarts the browser's progress lifetime and drops unsaved
	# practice quests. Headless those land before step 1; on a slow renderer they land
	# mid-run (lost_net went active -> '-' at the pickup). Runtime-only, never saved.
	if not _online:
		Settings.set_value("net", "enabled", false)
		print("playtest: offline (no hub, no other visitors; --online or steps \"online\": true to connect)")
	_report["online"] = _online
	Progress.changes.reset.connect(func(practice: bool, _discarded: bool) -> void:
		if _step_n > 0:
			print("WARN playtest: the browser reset quest progress during step %d (%s session): quest states after it start over" % [
				_step_n, "practice" if practice else "retained"]))
	# a returning visitor: the first-run tutorial ("Welcome to iamar") would hold the
	# interact key. Written to the run's private profile only (OAK_SETTINGS).
	Settings.set_value("tutorial", "done", true)
	# the browser's own game scene (the kit dispatcher dropped it before handing over).
	# Main itself, not the light boot scene that swaps itself for Main (browser 9adabe41),
	# and straight to the city: with a renderer Main would otherwise show the sign-in
	# start page and wait for a click that never comes (an internal task, harbour gap G17).
	var main_path := MAIN_SCENE if ResourceLoader.exists(MAIN_SCENE) \
		else String(ProjectSettings.get_setting("application/run/main_scene"))
	root.set_meta(NEXT_BOOT_META, "city")
	var scene := load(main_path) as PackedScene
	if scene == null:
		_finish(1, "the browser's main scene does not load")
		return
	_main = scene.instantiate()
	root.add_child(_main)
	current_scene = _main
	print("playtest: starting the browser ...")
	if not await _until(func() -> bool:
			return _main.get("state") == 1 and is_instance_valid(_main.get("select_ui")) and not bool(_main.get("_entry_pending")), _left()):
		_finish(1, "the browser did not reach hero selection within --timeout %d s (a first load can be slow: raise --timeout)" % int(_timeout))
		return
	# with a renderer Main is in hero selection while its startup screen is still held over
	# it (Main._loading, null once it starts fading): wait for it, or every shot shows the
	# "Initializing the app" screen instead of the world
	if _shots and "_loading" in _main:
		await _until(func() -> bool: return _main.get("_loading") == null, _left())
		await _seconds(1.5)   # its fade
	_main.select_ui._select(_hero)
	await _frames(2)
	_main._enter_world(_main.select_ui.hero_id, _main.select_ui.hero_name(), _main.select_ui.outfit)
	if not await _until(func() -> bool:
			return _main.get("state") == 2 and _main.get_node_or_null("Shell") != null and _main.get_node_or_null("Gameplay") != null, _left()):
		_finish(1, "the browser did not enter play within --timeout %d s (raise --timeout)" % int(_timeout))
		return
	_shell = _main.get_node("Shell")
	_gp = _main.get_node("Gameplay")
	await _seconds(1.0)
	if not _new_visitor:
		_returning_visitor()
	print("playtest: entering %s ..." % _wid)
	var why: String = _shell._enter_package(_pkg, "", "iamar://local/" + _wid)
	if why != "":
		_finish(1, "entering the world failed: " + why)
		return
	if _hour >= 0.0 and _main.get("world") and _main.world.get("day_night"):
		_main.world.day_night.set_hour(_hour)
		# the city's DayNight is parked with the city: the world keeps its own light
		var env: Dictionary = _pkg.scene.get("environment", {})
		print("NOTE hour %.1f sets the browser's clock only: a world's light is fixed by scene.json environment (time_of_day %s%s); to see it at another time use iamar-world shots --times" % [
			_hour, str(env.get("time_of_day", 12.0)), ", sun.direction set" if (env.get("sun", {}) as Dictionary).has("direction") else ""])
	_scripts = (_shell.get("package_scripts") as Array).duplicate() if _shell.get("package_scripts") is Array else []
	if not await _until(func() -> bool:
			for ws in _scripts:
				if not is_instance_valid(ws) or ws.loading or not ws.loaded:
					return false
			return true, 120.0):
		_finish(1, "the world's scripts did not finish loading")
		return
	_hook_quest_effects()
	for ws in _scripts:
		_hook(ws)
		if not ws.errors.is_empty():
			print("WARN script %s: %s" % [ws.script_path, "; ".join(ws.errors)])
	await _seconds(1.5)   # on_init / on_enter run, the player lands
	# with a renderer the arrival (fade, entry overlay) keeps the player's input off for a
	# while after the world is in: wait for it, else step 1 finds "player input off".
	# Still blocked after this, the first step reports why.
	await _until(func() -> bool:
			var pl: Node = _main.player
			return is_instance_valid(pl) and bool(pl.get("input_enabled")) \
				and (not pl.has_method("can_control") or bool(pl.call("can_control"))), minf(60.0, _left()))
	_report["scripts"] = _scripts.size()
	_report["quests"] = _quest_ids()
	print("playtest: in %s after %.1f s, %d script(s), quests %s" % [_wid, _elapsed(), _scripts.size(), ", ".join(_report.quests)])
	var n := 0
	for s in steps:
		n += 1
		if _elapsed() > _timeout:
			_finish(1, "timed out after %d s" % int(_timeout))
			return
		_step_n = n
		await _step(n, s)
	if _auto:
		_auto_summary()
	_finish(0 if _fails == 0 else 1)


## --auto: one line per place the visitor could not reach, then a count.
func _auto_summary() -> void:
	var places := 0
	var bad := 0
	var falls := 0
	for rec in _report.steps:
		falls += (rec.get("falls", []) as Array).size()
		if not (rec as Dictionary).has("auto"):
			continue
		places += 1
		if not rec.ok:
			bad += 1
			print("AUTO unreachable %s: %s" % [rec.auto, rec.get("error", "an expectation failed")])
	print("AUTO %d step(s): %d ok, %d failed, %d fall(s)" % [places, places - bad, bad, falls])
	_report["auto"] = {"steps": places, "failed": bad, "falls": falls}


## A returning visitor (as with the tutorial above): the welcome quests are marked done in the
## run's private profile, so the browser's welcome guides stay out of the world and the
## talk prompt finds only the world's own NPCs. Steps file "new_visitor": true keeps them.
func _returning_visitor() -> void:
	var marked: Array = []
	for q in WELCOME_QUESTS:
		if Progress.quest(q) != "done":
			if Progress.set_quest(q, "done"):
				marked.append(q)
			else:
				print("WARN playtest: could not mark %s done: the browser's welcome guides may follow the player" % q)
	_report["returning_visitor"] = true
	if not marked.is_empty():
		print("playtest: a returning visitor (%s done: the browser's welcome guides stay out)" % ", ".join(marked))


## Counts what the world's scripts do: sounds they play and notes they show.
func _hook(ws: Node) -> void:
	var orig_sound: Callable = ws.sound
	ws.sound = func(name: String, at: Vector3) -> bool:
		_sounds.append([name, at])
		return orig_sound.call(name, at) if orig_sound.is_valid() else false
	# a package sound (sound_play "asset:<path>.ogg") goes to ws.play_stream with the stream
	# only: its name is the one the stream was loaded under in ws.ext's sound cache
	var orig_stream: Callable = ws.play_stream
	if orig_stream.is_valid():
		ws.play_stream = func(st: AudioStream, at: Vector3) -> void:
			_sounds.append([_stream_name(ws, st), at])
			orig_stream.call(st, at)
	var orig_note: Callable = ws.note
	ws.note = func(t: String) -> void:
		_notes.append(t)
		if orig_note.is_valid(): orig_note.call(t)


## "asset:<path>.ogg" of a stream the world's script loaded, or "asset:?" if not found.
func _stream_name(ws: Node, st: AudioStream) -> String:
	var ext: Object = ws.get("ext")
	var cache: Variant = ext.get("_sounds") if ext != null else null
	if cache is Dictionary:
		for rel in cache:
			if cache[rel] == st:
				return "asset:" + String(rel)
	return "asset:?"


## A quest's on_complete (scene.json quests[].on_complete: show, hide, play) is applied by
## the browser's QuestEffects node, not by a world script: its show/hide nodes join the
## snapshot under their scene id, and its sounds are counted like a script's ws.sound.
## Duck-typed (script path, `_rules`), so a browser without QuestEffects still runs.
func _hook_quest_effects() -> void:
	for fx in root.find_children("QuestEffects*", "", true, false):
		var sc: Script = fx.get_script()
		if sc == null or not sc.resource_path.ends_with("quest_effects.gd") or not fx.get("_rules") is Array:
			continue
		for r in fx.get("_rules"):
			for n in (r.get("show", []) as Array) + (r.get("hide", []) as Array):
				if is_instance_valid(n):
					_scene_fx[String(n.name)] = n
			var play: Array = []
			for n in r.get("play", []):
				play.append(_SoundProbe.new(n, self) if is_instance_valid(n) else n)
			r["play"] = play


## Stands in for a scene sound in a QuestEffects rule: records the play, then plays it.
class _SoundProbe extends RefCounted:
	var target: Node
	var pt: Object
	func _init(t: Node, p: Object) -> void:
		target = t
		pt = p
	func play() -> void:
		var at: Vector3 = (target as Node3D).global_position if target is Node3D else Vector3.ZERO
		(pt.get("_sounds") as Array).append([String(target.name), at])
		if target.has_method("play"):
			target.play()


# ---------------------------------------------------------------- the steps

func _step(n: int, s: Dictionary) -> void:
	var kind := String(s.do)
	var rec := {"n": n, "do": kind, "ok": true}
	_sounds.clear()
	_notes.clear()
	if s.has("auto"):
		rec.auto = String(s.auto)
	if String(s.get("from", "")) == "spawn":
		await _to_spawn()
	var before := _snapshot()
	var err := ""
	match kind:
		"goto": err = await _goto(s)
		"talk": err = await _talk(s, rec)
		"pickup": err = await _pickup(s)
		"use": err = await _use(s)
		"wait": await _script_seconds(clampf(float(s.get("s", 1.0)), 0.0, 120.0))
		"walk_to": err = await _walk_to(s, rec)
		"enter": err = await _enter(s, rec)
		"climb": err = await _climb(s, rec)
		"swim_to": err = await _swim_to(s, rec)
		"dive": err = await _dive(s, rec)
		"surface": err = await _surface(rec)
		"look_at": err = await _look_at(s, rec)
	# the visitor's state right after the step's action (a diver drifts up during the settle)
	rec.state = _player_state()
	await _script_seconds(clampf(float(s.get("settle", 1.0)), 0.0, 30.0))
	if err != "":
		rec.ok = false
		rec.error = err
	print("STEP %d %s %s%s%s" % [n, kind, "ok" if err == "" else "FAIL ", err, "  (auto: %s)" % rec.auto if rec.has("auto") else ""])
	rec.quests = _quests()
	for q in rec.quests:
		var d: Dictionary = rec.quests[q]
		print("QUEST %s %s step=%d counts=%s" % [q, d.state if d.state != "" else "-", d.step, str(d.counts)])
	rec.effects = _effects(before, _snapshot())
	for e in rec.effects:
		print("EFFECT " + _effect_text(e))
	var p: Vector3 = _main.player.global_position
	rec.player = [snappedf(p.x, 0.01), snappedf(p.y, 0.01), snappedf(p.z, 0.01)]
	for x in s.get("expect", []):
		var r := _expect(x, rec)
		print("EXPECT %s %s" % ["ok  " if r[0] else "FAIL", r[1]])
		(rec.get_or_add("expect", []) as Array).append({"ok": r[0], "what": r[1]})
		if not r[0]:
			rec.ok = false
	if _shots:
		rec.shot = await _shot(n, kind)
		if rec.shot != "":
			print("SHOT " + rec.shot)
	if not rec.ok:
		_fails += 1
	(_report.steps as Array).append(rec)


## goto: {"at": [x, z] | [x, y, z]} | {"npc": id} | {"trigger": id} | {"pickup": quest id or true} | {"entity": kind}
func _goto(s: Dictionary) -> String:
	var t := _target_of(s)
	if t.has("error"):
		return t.error
	_place(t.pos, t.get("face", t.pos), float(t.get("near", 0.0)))
	return ""


func _talk(s: Dictionary, rec: Dictionary) -> String:
	var who := _npc_name(String(s.get("npc", "")))
	if who == "":
		return "no NPC %s in this world" % s.get("npc", "")
	var npc: Variant = (_gp.get("_npcs") as Dictionary).get(who)
	if not is_instance_valid(npc):
		return "NPC %s is not spawned" % who
	_place(npc.global_position, npc.global_position, NEAR)
	await _frames(3)
	var dialog: Node = _main.hud.dialog
	# On a slow renderer (llvmpipe: 100 to 400 ms a frame) the key's target settles late: wait
	# for the dialog, and press the key again (up to 3 times) before giving up.
	for _try in 3:
		_gp.interact()   # the interact key
		await _frames(2)
		if await _until(func(): return dialog.visible and String(_gp.get("_talking")) == who, 3.0):
			break
		if dialog.visible:
			break
	if not dialog.visible or String(_gp.get("_talking")) != who:
		return "interact did not open %s's dialog (%s)" % [who, _why_no_target(npc)]
	var labels := _choices()
	rec.dialog = {"npc": who, "text": _dialog_text(dialog), "choices": labels}
	print("DIALOG %s: %s" % [who, " | ".join(labels)])
	var want := String(s.get("choose", ""))
	if want == "":
		if bool(s.get("close", true)):
			_gp._close_panels()   # walk away, as a visitor does; the next talk is not blocked
		return ""
	var b := _choice_button(want)
	if b == null:
		return "no choice %s (offered: %s)" % [want, ", ".join(labels)]
	b.pressed.emit()
	await _frames(3)
	if dialog.visible:
		rec.reply = _dialog_text(dialog)
		print("REPLY " + String(rec.reply).replace("\n", " "))
	if bool(s.get("close", true)):
		_gp._close_panels()
	return ""


## The dialog's text without the browser's own offline notice ("Offline practice. ...",
## Progress.PRACTICE_NOTICE), which it puts before an NPC's reply in an offline run: the
## world's words only, as in an online run.
func _dialog_text(dialog: Node) -> String:
	var t := (dialog.get("_text") as RichTextLabel).get_parsed_text().strip_edges()
	if _practice_notice == "" and ResourceLoader.exists(PROGRESS_SCRIPT):
		var sc := load(PROGRESS_SCRIPT) as Script
		_practice_notice = String(sc.get_script_constant_map().get("PRACTICE_NOTICE", "")) if sc else ""
	if _practice_notice != "" and t.begins_with(_practice_notice):
		t = t.substr(_practice_notice.length()).strip_edges()
	return t


func _pickup(s: Dictionary) -> String:
	var pk := _live_pickup(String(s.get("quest", "")))
	if pk == null:
		return "no pickup is waiting (is its quest active and at that step?)"
	_place(pk.global_position, pk.global_position, 1.0)
	await _frames(3)
	if not is_instance_valid(pk):
		return "the pickup went away before the key was pressed (its quest was reset?)"
	var pk_id := pk.get_instance_id()   # the pickup frees itself when taken: no capture of pk
	for _try in 3:   # a slow renderer settles the key's target late (see _talk)
		_gp.interact()
		await _frames(2)
		if await _until(func(): return not is_instance_id_valid(pk_id) or not (_gp.get("_pickups") as Array).has(instance_from_id(pk_id)), 3.0):
			break
	if is_instance_valid(pk) and (_gp.get("_pickups") as Array).has(pk):
		return "interact did not pick up %s (%s)" % [pk.item, _why_no_target(pk)]
	return ""


func _use(s: Dictionary) -> String:
	var hit := _entity(String(s.get("entity", "")), int(s.get("index", 0)))
	if hit.is_empty():
		return "no script entity %s" % s.get("entity", "")
	var e: Node3D = hit.e
	_place(e.global_position, e.global_position, 1.8)
	await _frames(3)
	if not (hit.ws.get("_exports") as Dictionary).has("on_interact"):
		return "the script of %s has no on_interact: the interact key does nothing to it" % e.kind
	# the interact key (WorldScript._input) acts on the NEAREST script entity within
	# INTERACT_RANGE of the player's feet, not on the one the step names
	var key := _key_pick()
	if key.is_empty():
		var me: Node3D = hit.ws.call("_player_node", 1)
		var off := e.global_position - me.global_position
		return "no script entity within the key's %.1f m: %s is %.2f m away (%.2f m across, %.2f m up) from where a visitor stands" % [
			_key_range(), e.kind, off.length(), Vector2(off.x, off.z).length(), off.y]
	if key.e != e:
		return "nearest script entity is %s at %.2f m (key range %.1f m), not %s at %.2f m" % [
			key.e.kind, key.d, _key_range(), e.kind, e.global_position.distance_to(key.me.global_position)]
	key.ws.interact(1, int(key.h))   # what WorldScript._input does for that key press
	return ""


func _key_range() -> float:
	return float(WorldScript.INTERACT_RANGE)


## {ws, h, e, d, me} for the script entity the interact key would act on now: the nearest
## within INTERACT_RANGE (3D, from the local player's feet) among scripts that export
## on_interact, or {} when none is in range.
func _key_pick() -> Dictionary:
	var best := {}
	var bd := _key_range()
	for ws in _scripts:
		if not is_instance_valid(ws) or not (ws.get("_exports") as Dictionary).has("on_interact"):
			continue
		var me: Node3D = ws.call("_player_node", 1)
		if me == null:
			continue
		var ents: Dictionary = ws.get("_entities")
		for h in ents:
			var e: Node3D = ents[h]
			if not is_instance_valid(e):
				continue
			var d := e.global_position.distance_to(me.global_position)
			if d < bd:
				bd = d
				best = {"ws": ws, "h": h, "e": e, "d": d, "me": me}
	return best


## Why the interact key found nothing: the reasons Gameplay.interact checks, in order.
func _why_no_target(n: Node3D) -> String:
	var pl: Node3D = _main.player
	if not bool(_gp.call("_interaction_allowed")):
		return "interaction not allowed now: %s" % ", ".join(_blockers())
	var off := n.global_position - pl.global_position
	var bits := "target: %s, %.2f m away, %.2f m up, player at %s" % [str(_gp.get("_target").get("kind", "none")),
		Vector2(off.x, off.z).length(), off.y, str(_v(pl.global_position))]
	if not ContextTargeting.clear_line(pl, pl.global_position + Vector3(0, 1.2, 0), n.global_position + Vector3(0, 1.0, 0)):
		bits += ", world geometry blocks the line to it"
	return bits


## What keeps the player from acting: open panels, menus, a disabled player.
func _blockers() -> Array:
	var out: Array = []
	var pl: Node = _main.player
	if not bool(pl.get("input_enabled")): out.append("player input off")
	if pl.has_method("can_control") and not bool(pl.call("can_control")): out.append("player cannot be controlled")
	if _main.hud.menu.visible: out.append("menu open")
	if _main.hud.char_panel.visible: out.append("character panel open")
	if bool(_gp.call("panel_open")): out.append("a gameplay panel is open")
	for panel in UiNav._panels:
		if is_instance_valid(panel) and panel.is_visible_in_tree():
			out.append("panel %s open" % _panel_name(panel))
	if paused: out.append("game paused")
	return out


func _panel_name(panel: Node) -> String:
	var n := String(panel.name)
	if n.begins_with("@"):
		var sc: Script = panel.get_script()
		n = sc.resource_path.get_file() if sc else panel.get_parent().name + "/" + panel.get_class()
	for l in panel.find_children("*", "Label", true, false):
		if (l as Label).text.strip_edges() != "":
			return "%s (\"%s\")" % [n, (l as Label).text.strip_edges().left(60)]
	return n


# ---------------------------------------------------------------- exploration (an internal task)
# These steps WALK and SWIM the visitor with the browser's own movement (the move keys held,
# the hero steered toward each waypoint), so a wall, a too-high step, a gap or a missing
# shore shows up as "stuck", "did not reach" or a fall, the way a visitor would meet it.

## The visitor back on the spawn point (each --auto step starts there: "from": "spawn").
func _to_spawn() -> void:
	var sp: Transform3D = _pkg.spawn_point
	var f := -sp.basis.z
	var yaw := atan2(-f.x, -f.z) if Vector2(f.x, f.z).length() > 0.01 else 0.0
	_main.player.teleport(sp.origin + Vector3(0, 0.3, 0), yaw)
	_main.player.cam_yaw = yaw
	await _script_seconds(0.5)


## walk_to: {"at": [x, z] | [x, y, z]} | {"npc"} | {"trigger"} | {"entity"} | {"pickup"}
## | {"object": id} | {"portal": id} | {"water": id} | {"room": "<object>/<room>"} | {"spawn": true}
## Walks there; "near" (m) overrides how close counts as arrived.
func _walk_to(s: Dictionary, rec: Dictionary) -> String:
	var t := _walk_target(s)
	if t.has("error"):
		return t.error
	var err: String = await _walk_route(t.route, float(s.get("near", t.near)), rec, t.get("box"))
	if err == "" and t.has("room"):
		err = _room_check(t.room)
	return err


## enter: {"object": house id} walks in at its front door; {"room": "<house>/<room>"} walks
## through the front door and the corridor (and up the stair) into that room.
func _enter(s: Dictionary, rec: Dictionary) -> String:
	if s.has("room"):
		return await _walk_to({"room": s.room, "near": s.get("near", 0.6)}, rec)
	var h := _house(String(s.get("object", "")))
	if h.has("error"):
		return h.error
	return await _walk_route(Routes.door_route(h.rooms, h.xf), float(s.get("near", 0.5)), rec)


## climb: {"object": house id} walks up the house's stair; {"to": [x, y, z]} walks there.
## Fails unless the visitor's feet end within 0.6 m of the top's height.
func _climb(s: Dictionary, rec: Dictionary) -> String:
	var route: Array = []
	var top := Vector3.ZERO
	if s.has("object"):
		var h := _house(String(s.object))
		if h.has("error"):
			return h.error
		if not (h.rooms.get("stair", {}) as Dictionary).has("top"):
			return "house %s has one floor: no stair" % s.object
		for w in Routes.room_route(h.rooms, h.xf, {"floor": 1, "door": [0, 0, 0], "rect": [0, 0, 0, 0]}):
			route.append(w)
			if w.why == "off the stair":
				break
		top = (route.back() as Dictionary).p
	elif s.get("to") is Array and (s.to as Array).size() == 3:
		top = Vector3(float(s.to[0]), float(s.to[1]), float(s.to[2]))
		route = [{"p": top, "why": "the top"}]
	else:
		return "climb needs object (a house with a stair) or to: [x, y, z]"
	var err: String = await _walk_route(route, float(s.get("near", 0.5)), rec)
	if err != "":
		return err
	var y: float = _main.player.global_position.y
	if absf(y - top.y) > 0.6:
		return "did not climb: feet at y %.2f, the top is at %.2f" % [y, top.y]
	return ""


## swim_to: {"water": id | index} (its middle) or {"at": [x, z]}: walks into the water and
## swims there. Fails when the visitor is not swimming on arrival (the water is too shallow,
## not swimmable, or has no shore to walk in from).
func _swim_to(s: Dictionary, rec: Dictionary) -> String:
	var t := _walk_target(s)
	if t.has("error"):
		return t.error
	var err: String = await _walk_route(t.route, float(s.get("near", t.near)), rec)
	if err != "":
		return err
	await _script_seconds(0.3)
	if not bool(_main.player.swimming):
		var p: Vector3 = _main.player.global_position
		var lvl := _water_level(p)
		return "arrived but not swimming: %s" % ("no water here" if lvl < -1e8 else "water %.2f m deep over the feet (the hero floats at about 1.3 m: too shallow, or swimmable false?)" % (lvl - p.y))
	return ""


## dive: {"depth": m (default 1.5), "s": max seconds (default 10)}: holds swim-down until the
## visitor's head is `depth` m under the surface (or the floor stops it) and reports what the
## visitor sees: UNDERWATER head <m> under, floor <m> below, sight <m>, fog <colour>, view on|off.
func _dive(s: Dictionary, rec: Dictionary) -> String:
	var pl = _main.player   # the browser's Player (untyped: its own members)
	if not bool(pl.swimming):
		return "not swimming (swim_to the water first)"
	var depth := float(s.get("depth", 1.5))
	var limit := float(s.get("s", 10.0))
	pl.cam_pitch = -0.3
	Input.action_press("swim_down")
	var t := 0.0
	var best := -INF
	var still := 0.0
	var why := ""
	var dt := 1.0 / float(Engine.physics_ticks_per_second)
	while t < limit and _elapsed() <= _timeout:
		await physics_frame
		t += dt
		var under := _water_level(pl.global_position) - (pl.head_position() as Vector3).y
		if under >= depth:
			break
		if under > best + 0.02:
			best = under
			still = 0.0
		else:
			still += dt
			if still > 1.5:
				why = "the floor stops the dive"
				break
	Input.action_release("swim_down")
	# look level, as a diver looking around does: looking down, the camera stays above the
	# surface behind the hero, and the view is the surface, not the water
	pl.cam_pitch = 0.0
	await _frames(20)   # the camera eases in; Underwater checks it every frame
	var u := _underwater_view()
	rec.underwater = u
	print("UNDERWATER head %.2f m under, camera %s, floor %s below, sight %s, fog %s, view %s%s" % [u.head_under_m,
		"%.2f m under" % u.camera_under_m if u.camera_under_m > 0.0 else "above the surface",
		"%.2f m" % u.floor_m if u.floor_m >= 0.0 else "none", "%.0f m" % u.sight_m if u.sight_m > 0.0 else "?",
		u.fog, "on" if u.view else "off", " (%s)" % why if why != "" else ""])
	if u.head_under_m < 0.05:
		return "the head never went under (%s)" % (why if why != "" else "timed out")
	return ""


## surface: holds swim-up until the head is out of the water.
func _surface(_rec: Dictionary) -> String:
	var pl = _main.player
	if not bool(pl.swimming):
		return "not swimming"
	if bool(pl.head_under):
		Input.action_press("jump")   # under water it rises (only a press AT the surface jumps out)
		await _until(func() -> bool: return not bool(pl.head_under), 12.0)
		Input.action_release("jump")
	await _script_seconds(0.5)
	if bool(pl.head_under):
		return "the head is still under water"
	return ""


## look_at: {"at": [x, y, z]} | {"npc"} | {"entity"} | {"object"} | {"trigger"} | {"water"}
## | {"spawn_view": true}: turns the view to it from where the visitor stands (spawn_view:
## back on the spawn, facing the spawn's way) and reports the distance and whether world
## geometry blocks the line of sight ("clear": true makes a blocked view fail the step).
## With a renderer the step's shot shows the view.
func _look_at(s: Dictionary, rec: Dictionary) -> String:
	var pl = _main.player
	if bool(s.get("spawn_view", false)):
		await _to_spawn()
		pl.cam_pitch = deg_to_rad(-10.0)
		print("LOOK spawn view at %s" % str(_v(pl.global_position)))
		return ""
	var t := _walk_target(s)
	if t.has("error"):
		return t.error
	var aim: Vector3 = (t.route.back() as Dictionary).p
	if s.get("at") is Array and (s.at as Array).size() == 3:
		aim = Vector3(float(s.at[0]), float(s.at[1]), float(s.at[2]))
	elif not s.has("at"):
		aim += Vector3(0, 1.0, 0)
	var eye: Vector3 = pl.call("head_position")
	var d := aim - eye
	var yaw := atan2(-d.x, -d.z)
	pl.facing = yaw
	pl.cam_yaw = yaw
	pl.cam_pitch = clampf(atan2(d.y, Vector2(d.x, d.z).length()), -1.2, 1.0)
	await _frames(3)
	var q := PhysicsRayQueryParameters3D.create(eye, aim, (pl as CollisionObject3D).collision_mask)
	q.exclude = [(pl as CollisionObject3D).get_rid()]
	var hit: Dictionary = (pl as Node3D).get_world_3d().direct_space_state.intersect_ray(q)
	var blocked: bool = not hit.is_empty() and (hit.position as Vector3).distance_to(aim) > 0.5
	rec.look = {"distance": snappedf(d.length(), 0.01), "clear": not blocked}
	print("LOOK %.1f m, line of sight %s" % [d.length(), "blocked by %s at %s" % [_hit_name(hit), str(_v(hit.position))] if blocked else "clear"])
	if blocked and bool(s.get("clear", false)):
		return "line of sight blocked by %s" % _hit_name(hit)
	return ""


func _hit_name(hit: Dictionary) -> String:
	var c: Object = hit.get("collider")
	if c is Node:
		var n: Node = c
		return "%s/%s" % [n.get_parent().name, n.name] if n.get_parent() else String(n.name)
	return "?"


## {route: [{p, why}], near, [box: AABB], [room: {...}]} or {error}.
func _walk_target(s: Dictionary) -> Dictionary:
	if bool(s.get("spawn", false)):
		return {"route": [{"p": _pkg.spawn_point.origin, "why": "the spawn"}], "near": 1.0}
	if s.has("room"):
		var bits := String(s.room).split("/")
		if bits.size() != 2:
			return {"error": "room needs \"<house object id>/<room name>\" (e.g. house/bedroom_1)"}
		var h := _house(bits[0])
		if h.has("error"):
			return h
		var r := Routes.room_of(h.rooms, bits[1])
		if r.is_empty():
			var names: Array = []
			for x in h.rooms.get("rooms", []):
				names.append(String(x.get("name", "")))
			return {"error": "house %s has no room %s (rooms: %s)" % [bits[0], bits[1], ", ".join(names)]}
		return {"route": Routes.room_route(h.rooms, h.xf, r), "near": 0.6, "room": {"house": h, "room": r, "name": String(s.room)}}
	if s.has("object"):
		var o := _scene_entry("objects", String(s.object))
		if o.is_empty():
			o = _scene_entry("primitives", String(s.object))
		if o.is_empty():
			return {"error": "no object or primitive %s in scene.json" % s.object}
		return {"route": [{"p": Routes.xform_of(o).origin, "why": "object %s" % s.object}], "near": 1.5, "box": _node_box(String(s.object))}
	if s.has("portal"):
		var p := _scene_entry("portals", String(s.portal))
		if p.is_empty():
			return {"error": "no portal %s in scene.json" % s.portal}
		return {"route": [{"p": Routes.portal_front(p), "why": "in front of portal %s" % s.portal}], "near": 0.8}
	if s.has("water"):
		var w := _scene_entry("water", String(s.water))
		if w.is_empty():
			return {"error": "no water %s in scene.json" % s.water}
		var c := Routes.xform_of({"position": w.get("position", [0, 0, 0])}).origin
		return {"route": [{"p": c, "why": "the middle of water %s" % s.water}], "near": 1.5}
	var t := _target_of(s)
	if t.has("error"):
		return t
	return {"route": [{"p": t.pos, "why": "the target"}], "near": maxf(float(t.get("near", 0.0)), 0.6)}


## The scene.json entry of a section with that id (or index, for entries without an id), or {}.
func _scene_entry(section: String, id: String) -> Dictionary:
	var i := 0
	for e in _pkg.scene.get(section, []):
		if e is Dictionary and (String(e.get("id", "")) == id or (String(e.get("id", "")) == "" and str(i) == id)):
			return e
		i += 1
	return {}


## A house: {rooms: its rooms sidecar, xf: its placement} or {error}.
func _house(id: String) -> Dictionary:
	var o := _scene_entry("objects", id)
	if o.is_empty():
		return {"error": "no object %s in scene.json" % id}
	var rooms := _rooms_of(String(o.get("asset", "")))
	if rooms.is_empty():
		return {"error": "object %s has no rooms sidecar %s (iamar-world assets building house writes it beside the .glb)" % [id, _rooms_path(String(o.get("asset", ""))).get_file()]}
	return {"rooms": rooms, "xf": Routes.xform_of(o)}


func _rooms_path(asset: String) -> String:
	return _world_dir.path_join(asset).get_basename() + ".rooms.json"


## The rooms sidecar of a glTF in the package ({} for none).
func _rooms_of(asset: String) -> Dictionary:
	if asset == "" or asset.contains(":"):
		return {}
	if not _rooms_cache.has(asset):
		var p := _rooms_path(asset)
		var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(p)) if FileAccess.file_exists(p) else null
		_rooms_cache[asset] = d if d is Dictionary and (d as Dictionary).get("rooms") is Array else {}
	return _rooms_cache[asset]


func _room_check(t: Dictionary) -> String:
	if Routes.in_room(t.house.rooms, t.house.xf, t.room, _main.player.global_position):
		return ""
	return "walked to the middle of %s but is not inside it (feet at %s)" % [t.name, str(_v(_main.player.global_position))]


## The world AABB of a built scene object (its meshes), or an empty AABB.
func _node_box(id: String) -> AABB:
	var box := AABB()
	var first := true
	for w in root.find_children("World_" + _wid, "", true, false):
		var n := w.find_child(id, true, false)
		if n == null:
			continue
		for mi in [n] + n.find_children("*", "MeshInstance3D", true, false):
			if mi is MeshInstance3D:
				var b: AABB = (mi as MeshInstance3D).global_transform * (mi as MeshInstance3D).get_aabb()
				box = b if first else box.merge(b)
				first = false
		break
	return box


## Walks the visitor along route ([{p, why}]) with the move keys, steering toward each
## waypoint. Arrived at a waypoint: within WAYPOINT m (the last: `near` m, or `near` m of
## `box` when given) horizontally and 1.3 m vertically (swimming: any height). Fails "stuck"
## after STUCK_S script seconds without 0.3 m of progress, "did not reach" after the
## waypoint's time, or "fell" after a drop of FALL m. Records rec.walked (m), rec.route
## (the waypoints passed) and rec.falls.
func _walk_route(route: Array, near: float, rec: Dictionary, box: Variant = null) -> String:
	var pl: CharacterBody3D = _main.player
	if route.is_empty():
		return "no route"
	var walked := 0.0
	var passed: Array = []
	var falls: Array = rec.get_or_add("falls", [])
	var err := ""
	var top := pl.global_position.y   # highest point since the feet left the floor
	var prev := pl.global_position
	var dt := 1.0 / float(Engine.physics_ticks_per_second)
	pl.set("rmb", true)   # the hero faces where the camera looks (the steering below)
	pl.set("cam_pitch", 0.0)   # level: swimming forward at the surface does not dive
	Input.action_press("move_forward")
	for i in route.size():
		var w: Dictionary = route[i]
		var wp: Vector3 = w.p
		var last := i == route.size() - 1
		var r := near if last else (float(w.r) if float(w.get("r", -1.0)) > 0.0 else WAYPOINT)
		var start := pl.global_position
		var limit := 6.0 + Vector2(wp.x - start.x, wp.z - start.z).length() / 1.2
		var t := 0.0
		var mark := start
		var mark_t := 0.0
		while true:
			var p := pl.global_position
			var d := wp - p
			var hd := Vector2(d.x, d.z).length()
			if last and box is AABB and (box as AABB).size != Vector3.ZERO:
				var b: AABB = box
				hd = Vector2(maxf(maxf(b.position.x - p.x, p.x - b.end.x), 0.0), maxf(maxf(b.position.z - p.z, p.z - b.end.z), 0.0)).length()
			if hd < r and (absf(d.y) < 1.3 or bool(pl.get("swimming")) or (last and box is AABB)):
				break
			var yaw := atan2(-d.x, -d.z)
			pl.set("cam_yaw", yaw)
			pl.set("facing", yaw)
			pl.set("walking", hd < 1.2 and not bool(pl.get("swimming")))   # slower, so a doorway is not overshot
			await physics_frame
			t += dt
			var np := pl.global_position
			walked += Vector2(np.x - prev.x, np.z - prev.z).length()
			prev = np
			if bool(pl.get("swimming")) or pl.is_on_floor():
				if top - np.y > FALL and not bool(pl.get("swimming")):
					falls.append({"metres": snappedf(top - np.y, 0.1), "at": _v(np)})
					print("FALL %.1f m at %s (on the way to %s)" % [top - np.y, str(_v(np)), w.why])
				top = np.y
			else:
				top = maxf(top, np.y)
			if np.distance_to(mark) > 0.3:
				mark = np
				mark_t = t
			elif t - mark_t > STUCK_S:
				err = "stuck at %s, %.1f m short of %s (waypoint %d/%d)" % [str(_v(np)), hd, w.why, i + 1, route.size()]
				break
			if t > limit or _elapsed() > _timeout:
				err = "did not reach %s within %.0f s: %.1f m short, at %s (waypoint %d/%d)" % [w.why, limit, hd, str(_v(np)), i + 1, route.size()]
				break
		if err != "":
			break
		passed.append(w.why)
	Input.action_release("move_forward")
	pl.set("rmb", false)
	pl.set("walking", false)
	await _frames(2)
	rec.walked = snappedf(walked, 0.1)
	rec.route = passed
	if err == "" and not falls.is_empty():
		var f: Dictionary = falls.back()
		err = "fell %.1f m at %s" % [f.metres, str(f.at)]
	return err


## {swimming, head_under, underwater, y} of the visitor now.
func _player_state() -> Dictionary:
	var pl: Node = _main.player
	var uw: Variant = pl.get("_underwater")
	return {"swimming": bool(pl.get("swimming")), "head_under": bool(pl.get("head_under")),
		"underwater": bool((uw as Node).get("under")) if uw is Node else false, "y": snappedf((pl as Node3D).global_position.y, 0.01)}


## Water surface at p (package water or the city's), -1e9 for none.
func _water_level(p: Vector3) -> float:
	return MpWater.level_at(p)


## What a diver sees: head depth, floor below, the water's sight distance and fog colour
## (PackageWater.look_at, browser 8444e450 and later), and whether the Underwater view is on.
func _underwater_view() -> Dictionary:
	var pl: Node3D = _main.player
	var head: Vector3 = pl.call("head_position")
	var lvl := _water_level(head)
	var out := {"head_under_m": snappedf(maxf(lvl - head.y, 0.0), 0.01) if lvl > -1e8 else 0.0,
		"floor_m": -1.0, "sight_m": 0.0, "fog": "?", "view": bool(_player_state().underwater), "camera_under_m": 0.0}
	var cam: Variant = pl.get("camera")
	if cam is Camera3D:
		var cp := (cam as Camera3D).global_position
		var cl := _water_level(cp)
		out.camera_under_m = snappedf(maxf(cl - cp.y, 0.0), 0.01) if cl > -1e8 else 0.0
	var fl: float = MpWater.floor_at(head)
	if is_finite(fl):
		out.floor_m = snappedf(head.y - fl, 0.01)
	var pw := _global_class("PackageWater")
	if pw:
		var lk: Variant = pw.call("look_at", head)
		if lk is Dictionary and not (lk as Dictionary).is_empty():
			out.sight_m = snappedf(float(lk.get("sight", 0.0)), 0.1)
			out.fog = "#" + (lk.get("fog", Color.BLACK) as Color).to_html(false)
	return out


## A browser class by its class_name (null when this browser has none), so the playtest
## still runs on a browser that predates it.
func _global_class(cname: String) -> Script:
	for c in ProjectSettings.get_global_class_list():
		if String(c.get("class", "")) == cname:
			return load(String(c.path)) as Script
	return null


# ---------------------------------------------------------------- where things are

func _target_of(s: Dictionary) -> Dictionary:
	if s.has("at"):
		var a: Array = s.at
		if a.size() == 2:
			# Probe from just above the visitor, not from the sky: [x, z] inside a roofed hall
			# then lands on its floor, not on the roof ridge. A visitor on a roof gets the roof.
			var py: float = _main.player.global_position.y
			var gy := _ground(float(a[0]), float(a[1]), NAN, py + 2.5)
			if is_nan(gy):   # higher ground than the visitor can step onto: the top surface
				gy = _ground(float(a[0]), float(a[1]), 0.0)
			return {"pos": Vector3(float(a[0]), gy, float(a[1]))}
		if a.size() == 3:
			return {"pos": Vector3(float(a[0]), float(a[1]), float(a[2]))}
		return {"error": "at needs [x, z] or [x, y, z]"}
	if s.has("trigger"):
		for t in _pkg.scene.get("triggers", []):
			if String(t.get("id", "")) == String(s.trigger):
				var tp: Array = t.position
				return {"pos": Vector3(float(tp[0]), _ground(float(tp[0]), float(tp[2]), float(tp[1]), float(tp[1]) + 1.5), float(tp[2]))}
		return {"error": "no trigger %s in scene.json" % s.trigger}
	if s.has("npc"):
		var who := _npc_name(String(s.npc))
		var npc: Variant = (_gp.get("_npcs") as Dictionary).get(who)
		if not is_instance_valid(npc):
			return {"error": "no NPC %s" % s.npc}
		return {"pos": npc.global_position, "near": NEAR}
	if s.has("pickup"):
		var pk := _live_pickup(String(s.pickup) if s.pickup is String else "")
		if pk == null:
			return {"error": "no pickup is waiting"}
		return {"pos": pk.global_position, "near": 1.0}
	if s.has("entity"):
		var hit := _entity(String(s.entity), int(s.get("index", 0)))
		if hit.is_empty():
			return {"error": "no script entity %s" % s.entity}
		return {"pos": (hit.e as Node3D).global_position, "near": 1.8}
	return {"error": "goto needs at, npc, trigger, pickup or entity"}


## The floor under (x, z): probed down from `from_y` (the sky by default; just above a
## target, so a step stands on the floor of a hall and not on its roof).
func _ground(x: float, z: float, fallback: float, from_y := 500.0) -> float:
	if _pkg.ground:
		var h: float = _pkg.ground.height_at(x, z, from_y, NAN)
		if not is_nan(h):
			return h
	return fallback


## Stands the player `near` m from pos (on the side facing the spawn), facing `face`.
func _place(pos: Vector3, face: Vector3, near: float) -> void:
	var p := pos
	if near > 0.0:
		var away := _pkg.spawn_point.origin - pos
		away.y = 0.0
		if away.length() < 0.01:
			away = Vector3(0, 0, 1)
		p = pos + away.normalized() * near
		p.y = _ground(p.x, p.z, pos.y, pos.y + 1.5)
	var d := face - p
	var yaw := atan2(-d.x, -d.z) if Vector2(d.x, d.z).length() > 0.01 else float(_main.player.facing)
	_main.player.teleport(p + Vector3(0, 0.3, 0), yaw)
	_main.player.cam_yaw = yaw


func _npc_name(id: String) -> String:
	for d in _pkg.npcs:
		if String(d.get("id", "")) == id or String(d.get("name", "")) == id:
			return String(d.get("name", d.id))
	return ""


func _qid(id: String) -> String:
	return id if id.contains(".") else "%s.%s" % [_wid, id]


func _quest_ids() -> Array:
	var out: Array = []
	for q in _pkg.quests:
		out.append(String(q.get("id", "")))
	return out


func _live_pickup(quest: String) -> Node3D:
	for pk in _gp.get("_pickups"):
		if is_instance_valid(pk) and pk.is_inside_tree() and (quest == "" or pk.quest == _qid(quest)):
			return pk
	return null


## {ws, h, e} for the index-th script entity whose kind is `kind` ("asset:assets/bell.glb",
## "light", "cylinder", ...; a bare file name matches "asset:.../<name>"), or {}.
func _entity(kind: String, index: int) -> Dictionary:
	var k := 0
	for ws in _scripts:
		if not is_instance_valid(ws):
			continue
		var ents: Dictionary = ws.get("_entities")
		var hs := ents.keys()
		hs.sort()
		for h in hs:
			var e: Node3D = ents[h]
			if is_instance_valid(e) and (String(e.kind) == kind or String(e.kind).get_file() == kind):
				if k == index:
					return {"ws": ws, "h": h, "e": e}
				k += 1
	return {}


func _choices() -> Array:
	var out: Array = []
	for b in (_main.hud.dialog.get("_buttons") as Node).get_children():
		if b is Button and not b.is_queued_for_deletion():
			out.append((b as Button).text)
	return out


## "accept" / "complete" pick the first Accept: / Complete: choice; anything else is the
## exact text of a choice (or the start of it).
func _choice_button(want: String) -> Button:
	var lw := want.to_lower()
	for b in (_main.hud.dialog.get("_buttons") as Node).get_children():
		if not b is Button or b.is_queued_for_deletion():
			continue
		var t := (b as Button).text
		if (lw == "accept" and t.begins_with("Accept:")) or (lw == "complete" and t.begins_with("Complete:")) \
				or (lw == "bye" and t == "Farewell") or t == want:
			return b
	for b in (_main.hud.dialog.get("_buttons") as Node).get_children():
		if b is Button and not b.is_queued_for_deletion() and (b as Button).text.begins_with(want):
			return b
	return null


# ---------------------------------------------------------------- state and effects

func _quests() -> Dictionary:
	var out := {}
	for q in _quest_ids():
		var id := _qid(q)
		if not QuestDefs.QUESTS.has(id):
			# the world declares it, but the browser has no definition: nobody can be offered it
			out[q] = {"state": "unregistered", "step": 0, "counts": []}
			continue
		var counts: Array = []
		for i in QuestDefs.objs(id, Progress.quest_step(id)).size():
			counts.append(Progress.quest_count(id, i))
		out[q] = {"state": Progress.quest(id), "step": Progress.quest_step(id), "counts": counts}
	return out


## handle key -> {kind, pos, visible, light}
func _snapshot() -> Dictionary:
	var out := {}
	var si := 0
	for ws in _scripts:
		si += 1
		if not is_instance_valid(ws):
			continue
		var ents: Dictionary = ws.get("_entities")
		for h in ents:
			var e: Node3D = ents[h]
			if not is_instance_valid(e):
				continue
			var light: Variant = e.get("_light")
			out["%d:%d" % [si, h]] = {"kind": String(e.kind), "pos": e.global_position, "visible": e.is_visible_in_tree(),
				"light": (light as Light3D).light_energy if light is Light3D else -1.0}
	for id in _scene_fx:
		var n: Node = _scene_fx[id]
		if not is_instance_valid(n):
			continue
		var l := _first_light(n)
		out["scene:" + id] = {"kind": id, "pos": (n as Node3D).global_position if n is Node3D else Vector3.ZERO,
			"visible": (n as Node3D).is_visible_in_tree() if n is Node3D else true,
			"light": _shown_energy(n, l)}
	return out


func _first_light(n: Node) -> Node:
	if n is Light3D:
		return n
	for c in n.find_children("*", "Light3D", true, false):
		return c
	return null


## A light's energy as a visitor sees it: 0 while it (or its scene node) is hidden; -1 for no light.
func _shown_energy(n: Node, l: Node) -> float:
	if not l is Light3D:
		return -1.0
	if (n is Node3D and not (n as Node3D).is_visible_in_tree()) or not (l as Light3D).is_visible_in_tree():
		return 0.0
	return (l as Light3D).light_energy


func _effects(a: Dictionary, b: Dictionary) -> Array:
	var out: Array = []
	for k in b:
		var nb: Dictionary = b[k]
		if _ignored(String(nb.kind)):
			continue
		if not a.has(k):
			out.append({"kind": "spawned", "entity": nb.kind, "to": _v(nb.pos)})
			continue
		var na: Dictionary = a[k]
		var d: float = (nb.pos as Vector3).distance_to(na.pos)
		if d > MOVED:
			out.append({"kind": "moved", "entity": nb.kind, "from": _v(na.pos), "to": _v(nb.pos), "metres": snappedf(d, 0.01)})
		if absf(float(nb.light) - float(na.light)) > LIGHT_DELTA:
			out.append({"kind": "light", "entity": nb.kind, "from": snappedf(na.light, 0.01), "to": snappedf(nb.light, 0.01)})
		if nb.visible != na.visible:
			out.append({"kind": "visible", "entity": nb.kind, "to": nb.visible})
	for k in a:
		if not b.has(k) and not _ignored(String(a[k].kind)):
			out.append({"kind": "removed", "entity": a[k].kind})
	for s in _sounds:
		out.append({"kind": "sound", "name": s[0], "at": _v(s[1])})
	for t in _notes:
		out.append({"kind": "note", "text": t})
	return out


## A sound's name as an expectation may give it: the name played ("bell",
## "asset:audio/harbour_bell.ogg"), a package sound's path without "asset:"
## ("audio/harbour_bell.ogg") or its file name without .ogg ("harbour_bell").
func _sound_is(played: String, want: String) -> bool:
	if played == want:
		return true
	if not played.begins_with("asset:"):
		return false
	var rel := played.substr(6)
	return rel == want or rel.get_file().get_basename() == want


func _ignored(kind: String) -> bool:
	return kind in _ignore or kind.get_file() in _ignore


func _v(p: Vector3) -> Array:
	return [snappedf(p.x, 0.01), snappedf(p.y, 0.01), snappedf(p.z, 0.01)]


func _effect_text(e: Dictionary) -> String:
	match String(e.kind):
		"moved": return "moved %s %s -> %s (%.2f m)" % [e.entity, str(e.from), str(e.to), e.metres]
		"light": return "light %s energy %.2f -> %.2f" % [e.entity, e.from, e.to]
		"sound": return "sound %s at %s" % [e.name, str(e.at)]
		"note": return "note %s" % e.text
		"visible": return "visible %s %s" % [e.entity, e.to]
		"spawned": return "spawned %s at %s" % [e.entity, str(e.to)]
		"removed": return "removed %s" % e.entity
	return str(e)


## One expectation: {"quest": id, "state": "active"|"ready"|"done"|"", "step": i}
## {"moved": kind} {"light": kind, "above": e} {"sound": name} {"note": text part}
## {"visible": kind, "is": true|false} {"dialog": text part} {"choice": text part}
## {"player_y": [min, max]} (the visitor's feet, metres)
## {"swimming": bool} {"head_under": bool} {"underwater": bool} (the Underwater view), read
## right after the step's action, and {"in_room": "<house>/<room>"}.  -> [ok, description]
## kind: a script entity's kind, or the id of a scene object, primitive or light that a
## quest's on_complete shows or hides.
func _expect(x: Variant, rec: Dictionary) -> Array:
	if not x is Dictionary:
		return [false, "expectation must be an object"]
	var e: Dictionary = x
	for k in ["swimming", "head_under", "underwater"]:
		if e.has(k):
			var st: Dictionary = rec.get("state", {})
			return [bool(st.get(k, false)) == bool(e[k]), "%s %s (is %s)" % [k, str(bool(e[k])), str(bool(st.get(k, false)))]]
	if e.has("in_room"):
		var bits := String(e.in_room).split("/")
		var h := _house(bits[0]) if bits.size() == 2 else {"error": "in_room needs <house>/<room>"}
		if h.has("error"):
			return [false, "in room %s: %s" % [e.in_room, h.error]]
		var room := Routes.room_of(h.rooms, bits[1])
		var pl: Vector3 = Vector3(rec.player[0], rec.player[1], rec.player[2])
		return [not room.is_empty() and Routes.in_room(h.rooms, h.xf, room, pl), "in room %s" % e.in_room]
	if e.has("quest"):
		var q: Dictionary = (rec.quests as Dictionary).get(String(e.quest), {})
		if q.is_empty():
			return [false, "quest %s is not in this world" % e.quest]
		var ok := true
		var what := "quest %s" % e.quest
		if e.has("state"):
			ok = ok and q.state == String(e.state)
			what += " state %s (is %s)" % [e.state, q.state if q.state != "" else "-"]
		if e.has("step"):
			ok = ok and int(q.step) == int(e.step)
			what += " step %d (is %d)" % [int(e.step), q.step]
		return [ok, what]
	var effects: Array = rec.effects
	if e.has("player_y"):
		var r: Array = e.player_y
		var py: float = rec.player[1]
		return [r.size() == 2 and py >= float(r[0]) and py <= float(r[1]), "player y %.2f in [%s, %s]" % [py, r[0], r[1]] if r.size() == 2 else "player_y needs [min, max]"]
	if e.has("moved"):
		for f in effects:
			if f.kind == "moved" and (f.entity == String(e.moved) or String(f.entity).get_file() == String(e.moved)):
				return [true, "%s moved %.2f m" % [e.moved, f.metres]]
		return [false, "%s moved" % e.moved]
	if e.has("light"):
		var above := float(e.get("above", 0.0))
		var snap := _snapshot()
		for k in snap:
			var s: Dictionary = snap[k]
			if (s.kind == String(e.light) or String(s.kind).get_file() == String(e.light)) and float(s.light) >= 0.0:
				return [float(s.light) > above, "light %s energy %.2f > %.2f" % [e.light, s.light, above]]
		return [false, "light %s exists" % e.light]
	if e.has("visible"):
		var want := bool(e.get("is", true))
		var snap := _snapshot()
		for k in snap:
			var s: Dictionary = snap[k]
			if s.kind == String(e.visible) or String(s.kind).get_file() == String(e.visible):
				return [bool(s.visible) == want, "%s %s (is %s)" % [e.visible, "shown" if want else "hidden", "shown" if s.visible else "hidden"]]
		return [false, "%s exists (a script entity, or shown/hidden by a quest's on_complete)" % e.visible]
	if e.has("sound"):
		for f in effects:
			if f.kind == "sound" and _sound_is(String(f.name), String(e.sound)):
				return [true, "sound %s played" % e.sound]
		return [false, "sound %s played" % e.sound]
	if e.has("note"):
		for f in effects:
			if f.kind == "note" and String(f.text).contains(String(e.note)):
				return [true, "note contains %s" % e.note]
		return [false, "note contains %s" % e.note]
	if e.has("dialog") or e.has("choice"):
		var d: Dictionary = rec.get("dialog", {})
		if e.has("dialog"):
			var all := String(d.get("text", "")) + "\n" + String(rec.get("reply", ""))
			return [all.contains(String(e.dialog)), "dialog says %s" % e.dialog]
		for c in d.get("choices", []):
			if String(c).contains(String(e.choice)):
				return [true, "choice %s offered" % e.choice]
		return [false, "choice %s offered" % e.choice]
	return [false, "unknown expectation %s" % JSON.stringify(e)]


func _shot(n: int, kind: String) -> String:
	await RenderingServer.frame_post_draw
	var img := root.get_texture().get_image()
	if img == null or img.is_empty():
		return ""
	DirAccess.make_dir_recursive_absolute(_out.path_join("shots"))
	var p := _out.path_join("shots/step_%02d_%s.png" % [n, kind])
	return p if img.save_png(p) == OK else ""
