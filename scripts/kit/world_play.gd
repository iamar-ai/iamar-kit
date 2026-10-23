extends SceneTree
## Walk an unsigned draft world in the real browser game at once (kit command
## `iamar-world play`, kit/play/README.md). No keygen, sign, package or add-to-browser.
##
##   iamar-world play <world folder> [--hero human_male] [--timeout 600] [--no-reload] [--quit-after S] [--headless]
##   (the launchers run: <browser> -- --kit-script res://scripts/kit/world_play.gd --cwd <dir> ...)
##
## It boots the browser's own game scene, picks a hero and enters the folder the way
## playtest does (WorldSwitcher._enter_package: the world's scripts, NPCs, quests, water,
## swimming), then hands the game to the person. A "DRAFT - not published" banner stays
## on screen. The draft is local only: the run is offline (no hub, no other visitors) and
## nothing is signed, packaged or hosted. Saving any file of the world (scene.json,
## manifest.json, scripts, assets) rebuilds it in place and keeps the player where they
## stand; a save that does not open keeps the last good build and says why.
## Prints:
##   PLAY READY <id> after <s> s                    the person is in the world
##   PLAY RELOADED <id> (<n>)                       a save was picked up
##   PLAY RELOAD FAILED <why>                       a save does not open; the last build stays
##   WARN <text>                                    the world's own warnings (first 5)
##   PLAY END <id>                                  --quit-after ran out, or the window closed
## Exit 0 after a normal end, 1 when the browser or the world does not start, 2 bad input.
## The launchers give the browser a separate draft profile (settings, saves, world data),
## so the player's own profile is never read or written.

const BROWSER_FLAGS := ["--offline"]
const MAIN_SCENE := "res://scenes/main.tscn"
const NEXT_BOOT_META := "iamar_next_boot"   ## Main's "start"/"city" (Main.NEXT_BOOT_META)
const WELCOME_QUESTS := ["thornbury_welcome", "welcome_menus"]
const BANNER := "DRAFT - not published"
const POLL_S := 1.0          ## how often the folder is checked for saves
const MAX_FILES := 4000      ## files compared per check (a bigger folder only checks the first ones)

var _world_dir := ""
var _hero := "human_male"
var _cwd := ""
var _timeout := 600.0
var _quit_after := -1.0
var _reload := true
var _t0 := 0
var _main: Node
var _shell: Node
var _pkg: WorldPackage
var _wid := ""
var _address := ""
var _stamp := ""             ## the folder's file list + sizes + times at the last build
var _pending := ""           ## a changed stamp seen once: built when the next check sees it again (saves settle)
var _reloads := 0
var _busy := false
var _banner: Label
var _status: Label


func _initialize() -> void:
	_t0 = Time.get_ticks_msec()
	var err := _parse(OS.get_cmdline_user_args())
	if err != "":
		printerr("ERROR play: " + err)
		quit(2)
		return
	if OS.get_environment("OAK_SETTINGS") == "":
		var dir := OS.get_temp_dir().path_join("iamar-play-%d" % OS.get_process_id())
		DirAccess.make_dir_recursive_absolute(dir)
		OS.set_environment("OAK_SETTINGS", dir.path_join("settings.cfg"))
	_run.call_deferred()


func _parse(a: PackedStringArray) -> String:
	var pos: Array = []
	var i := 0
	if a.size() >= 2 and a[0] == "--kit-script":
		i = 2
	while i < a.size():
		var s := String(a[i])
		if s in ["--hero", "--timeout", "--quit-after", "--cwd"]:
			if i + 1 >= a.size():
				return "%s needs a value" % s
			var v := String(a[i + 1])
			match s:
				"--hero": _hero = v
				"--timeout": _timeout = float(v)
				"--quit-after": _quit_after = float(v)
				"--cwd": _cwd = v
			i += 2
			continue
		if s in BROWSER_FLAGS:
			i += 1
			continue
		if s == "--no-reload":
			_reload = false
			i += 1
			continue
		if s.begins_with("--"):
			return "unknown option " + s
		pos.append(s)
		i += 1
	if _cwd == "":
		_cwd = OS.get_environment("PWD")   # iamar-world.cmd sets it (cmd has no --cwd form)
	if pos.size() != 1:
		return "usage: iamar-world play <world folder> [--hero ID] [--timeout S] [--no-reload] [--quit-after S]"
	_world_dir = _abs(String(pos[0]))
	if not DirAccess.dir_exists_absolute(_world_dir):
		return "%s is not a folder (play takes the world's folder, not a .iamar package)" % _world_dir
	return ""


func _abs(p: String) -> String:
	if p.is_absolute_path() or _cwd == "":
		return p
	return _cwd.path_join(p).simplify_path()


func _elapsed() -> float:
	return (Time.get_ticks_msec() - _t0) / 1000.0


func _left() -> float:
	return maxf(0.0, _timeout - _elapsed())


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _seconds(s: float) -> void:
	await create_timer(s, true, false, true).timeout


func _until(cond: Callable, limit: float) -> bool:
	var end := _elapsed() + limit
	while not cond.call():
		if _elapsed() > end:
			return false
		await _seconds(0.1)
	return true


func _end(code: int, why := "") -> void:
	if why != "":
		printerr("ERROR play: " + why)
	if code == 0:
		print("PLAY END %s" % _wid)
	quit(code)


func _run() -> void:
	_pkg = WorldPackage.open(_world_dir)
	if _pkg == null or not _pkg.ok:
		_end(2, "the world does not open: %s (run iamar-world validate %s)" % [
			"; ".join(_pkg.errors.slice(0, 3)) if _pkg else _world_dir, _world_dir])
		return
	_wid = _pkg.id
	_address = "iamar://local/" + _wid
	_stamp = _folder_stamp()
	print("PLAY %s: a DRAFT (unsigned, local only, offline, never hosted). Close the window to stop%s." % [
		_wid, "; saving any file of the world reloads it" if _reload else ""])
	_warnings(_pkg)
	# offline: a draft is never offered to the hub or to other visitors (runtime only)
	Settings.set_value("net", "enabled", false)
	Settings.set_value("tutorial", "done", true)
	var main_path := MAIN_SCENE if ResourceLoader.exists(MAIN_SCENE) \
		else String(ProjectSettings.get_setting("application/run/main_scene"))
	root.set_meta(NEXT_BOOT_META, "city")
	var scene := load(main_path) as PackedScene
	if scene == null:
		_end(1, "the browser's main scene does not load")
		return
	_main = scene.instantiate()
	root.add_child(_main)
	current_scene = _main
	print("play: starting the browser ...")
	if not await _until(func() -> bool:
			return _main.get("state") == 1 and is_instance_valid(_main.get("select_ui")) and not bool(_main.get("_entry_pending")), _left()):
		_end(1, "the browser did not reach hero selection within --timeout %d s (a first start builds the city once: raise --timeout)" % int(_timeout))
		return
	if DisplayServer.get_name() != "headless" and "_loading" in _main:
		await _until(func() -> bool: return _main.get("_loading") == null, _left())
	_main.select_ui._select(_hero)
	await _frames(2)
	_main._enter_world(_main.select_ui.hero_id, _main.select_ui.hero_name(), _main.select_ui.outfit)
	if not await _until(func() -> bool:
			return _main.get("state") == 2 and _main.get_node_or_null("Shell") != null, _left()):
		_end(1, "the browser did not enter play within --timeout %d s (raise --timeout)" % int(_timeout))
		return
	_shell = _main.get_node("Shell")
	await _seconds(1.0)
	_returning_visitor()
	var why: String = _shell._enter_package(_pkg, "", _address)
	if why != "":
		_end(1, "entering the world failed: " + why)
		return
	if String(_shell.get("current_id")) != _wid:
		_end(1, "the browser is in %s, not the draft %s" % [_shell.get("current_id"), _wid])
		return
	_make_banner()
	print("PLAY READY %s after %.1f s" % [_wid, _elapsed()])
	if _reload:
		_watch()
	if _quit_after >= 0.0:
		await _seconds(_quit_after)
		_end(0)


## The browser's welcome guides would walk into the draft with a fresh profile (playtest does the same).
func _returning_visitor() -> void:
	for q in WELCOME_QUESTS:
		if Progress.quest(q) != "done":
			Progress.set_quest(q, "done")


func _warnings(pkg: WorldPackage) -> void:
	for w in pkg.warnings.slice(0, 5):
		print("WARN " + w)
	if pkg.warnings.size() > 5:
		print("WARN ... %d more (iamar-world validate lists them all)" % (pkg.warnings.size() - 5))


## Banner and reload status, on the root so they outlive every world rebuild.
func _make_banner() -> void:
	var layer := CanvasLayer.new()
	layer.name = "DraftBanner"
	layer.layer = 120
	root.add_child(layer)
	var box := VBoxContainer.new()
	# top centre, under the browser bar and its offline note (they end about 52 px down): the
	# bottom belongs to the interaction prompt ("[G] Talk to ...") and the player name (an internal task)
	box.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	box.grow_horizontal = Control.GROW_DIRECTION_BOTH
	box.offset_top = 62.0
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(box)
	_banner = _label(box, "%s  -  %s  -  local only%s" % [BANNER, SafeText.clean(_pkg.title, 48),
		", reloads when you save" if _reload else ""], 18, Color(1.0, 0.86, 0.35))
	_status = _label(box, "", 14, Color(0.9, 0.9, 0.9))


func _label(parent: Control, text: String, size: int, colour: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	l.add_theme_constant_override("outline_size", 6)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(l)
	return l


func _set_status(text: String) -> void:
	if is_instance_valid(_status):
		_status.text = text


## Every file of the folder (hidden ones skipped) with its size and time: any save changes it.
func _folder_stamp() -> String:
	var parts := PackedStringArray()
	var todo: Array = [""]
	while not todo.is_empty() and parts.size() < MAX_FILES:
		var rel: String = todo.pop_back()
		var dir := DirAccess.open(_world_dir.path_join(rel))
		if dir == null:
			continue
		dir.include_hidden = false
		for d in dir.get_directories():
			todo.append(rel.path_join(d))
		for f in dir.get_files():
			var p := _world_dir.path_join(rel).path_join(f)
			var fa := FileAccess.open(p, FileAccess.READ)
			var size := fa.get_length() if fa else -1
			parts.append("%s:%d:%d" % [rel.path_join(f), size, FileAccess.get_modified_time(p)])
			if parts.size() >= MAX_FILES:
				break
	parts.sort()
	return "\n".join(parts)


func _watch() -> void:
	while true:
		await _seconds(POLL_S)
		if _busy or not is_instance_valid(_shell):
			continue
		var now := _folder_stamp()
		if now == _stamp:
			_pending = ""
			continue
		# a save in progress (an editor writing several files): build once it holds still
		if now != _pending:
			_pending = now
			continue
		_pending = ""
		_stamp = now
		await _rebuild()


func _rebuild() -> void:
	_busy = true
	var pkg := WorldPackage.open(_world_dir)
	if pkg == null or not pkg.ok:
		var bad := "; ".join(pkg.errors.slice(0, 3)) if pkg else "the folder does not open"
		print("PLAY RELOAD FAILED %s (the last good build stays; iamar-world validate shows every problem)" % bad)
		_set_status("reload failed: %s" % bad.left(140))
		_busy = false
		return
	var player: Node3D = _main.get("player")
	var had := is_instance_valid(player)
	var keep := player.global_transform if had else Transform3D()
	var why: String = _shell._enter_package(pkg, "", "iamar://local/" + pkg.id)
	if why != "":
		print("PLAY RELOAD FAILED %s (the last good build stays)" % why)
		_set_status("reload failed: %s" % why.left(140))
		_busy = false
		return
	_pkg = pkg
	_wid = pkg.id
	_reloads += 1
	# stay where you stood (the world's spawn only on the first entry)
	await _frames(2)
	player = _main.get("player")
	if had and is_instance_valid(player):
		player.global_transform = keep
		if "velocity" in player:
			player.set("velocity", Vector3.ZERO)
	_warnings(pkg)
	print("PLAY RELOADED %s (%d)" % [_wid, _reloads])
	_set_status("reloaded %s" % Time.get_time_string_from_system())
	if is_instance_valid(_banner):
		_banner.text = "%s  -  %s  -  local only, reloads when you save" % [BANNER, SafeText.clean(pkg.title, 48)]
	_busy = false
