extends SceneTree
## Stand-alone viewer for iamar world packages: validates a package, builds it,
## and saves screenshots with triangle and draw-call counts (the precursor of
## the agent kit's `iamar-world preview` and `perf`).
##
##   godot --headless --path . -s res://scripts/kit/world_view.gd -- --validate worlds/mission_hall
##   DISPLAY=:0 godot --path . -s res://scripts/kit/world_view.gd -- worlds/mission_hall /tmp/shots/mission_hall
##       [--view "x,y,z>lx,ly,lz"]... [--npcs all|models|none] [--frames 60] [--size 1280x720] [--tier low|medium|high|ultra] [--quick]
##       [--quest-done <quest id>[,<id>...]|all]
##
## Without --view it shoots: the spawn point at eye height, four views around
## the world's objects (water and terrain planes left out), one from above,
## and one of the npcs. Prints
## VIEW <i> <name> draw=<draw calls> prims=<primitives> fps=<fps> per shot, and
## STATS / WARN / ERROR lines. Exit code 1 if the package does not open.
## Quests' on_complete show/hide (docs/WORLD_FORMAT.md 4.14) start as a visitor
## first sees them: every quest not done. --quest-done renders the named quests
## (or all) handed in instead, to judge a quest's end state.

const ValidationReport = preload("res://scripts/worlds/validation_report.gd")
const ScriptPreview = preload("res://scripts/kit/world_script_preview.gd")
const PageCheck = preload("res://scripts/kit/world_page_check.gd")
const FrameSpike = preload("res://scripts/kit/frame_spike.gd")
const ViewBounds = preload("res://scripts/kit/view_bounds.gd")
const WorldChecks = preload("res://scripts/kit/world_checks.gd")
var _report_v1 := false
var _quests_done: PackedStringArray = []   ## --quest-done: quest ids drawn as handed in ("all": every quest)
var _pkg: WorldPackage
var _views: Array = []
var _prefix := ""
var _cam: Camera3D
var _i := 0
var _wait := 0
var _frames := 60
var _size := Vector2i(1280, 720)   ## --size: the screenshot size
var _quick := false                ## --quick: 640x360, 25 frames, at most QUICK_VIEWS views (CPU-only hosts)
var _run_t0 := 0                   # msec when the run started, for the PREVIEW_MS summary
var _view_t0 := 0                  # msec when the current view's camera was placed
var _view_ms: Array = []           # per view: [name, msec to settle and shoot it]
const QUICK_SIZE := Vector2i(640, 360)
const QUICK_FRAMES := 25           # more than the 20 settle frames, so worst_frame_ms is still measured
const QUICK_VIEWS := 3
var _fps_acc := 0.0
## The playbook's hard targets for the low tier (kit/AGENT_KIT.md "Hard targets").
const TARGET_TRIS := 150000
const TARGET_DRAWS := 150
const TARGET_VRAM_MB := 600.0
const TARGET_FRAME_MS := 50.0
const TARGET_SCRIPT_MS := 2.0   ## all world scripts together, per frame (AGENT_KIT.md "World scripts")
var _worst_frame = FrameSpike.new(TARGET_FRAME_MS)   # worst frame after settling; over-limit views measured twice
var _remeasure := false               # this pass re-measures the current view (no new screenshot)
var _vram_max := 0.0
var _fps_n := 0
var _scripts: Array = []             ## sandboxed, playerless preview; not a visitor session
var _script_current: Callable
var _script_us_seen := 0
var _script_ms_max := [0.0, ""]       # worst frame's total script time, view
var _script_ms_sum := 0.0
var _script_frames := 0
var _world: Node3D
var _started := false
var _preview_requested := false
var _worst := ["", -1, 0]             # busiest view: name, primitives, draw calls
var _max_draws := ["", 0]             # view with the most draw calls: name, draw calls (the draw_calls TARGET)
var _visible_views := 0                 # reject a renderer that produced only empty frames


static func _abs(p: String) -> String:
	return KitLoop.absolute_path(p)


static func _vec(s: String) -> Vector3:
	var p := s.split(",")
	return Vector3(float(p[0]), float(p[1]), float(p[2]))


## Syntax-only preflight. Preserve the original arguments and all downstream
## package/tier/render policy; malformed CLI input must fail before opening it.
static func _argv_error(args: PackedStringArray) -> String:
	var positional_count := 0
	var validate := false
	var report := false
	var quick := false
	var i := 0
	while i < args.size():
		var arg := args[i]
		if arg == "--validate":
			validate = true
		elif arg == "--report-v1":
			report = true
		elif arg == "--quick":
			quick = true
		elif arg in ["--view", "--npcs", "--tier", "--frames", "--size", "--quest-done"]:
			if i + 1 >= args.size():
				return "An option is missing its value."
			var value := String(args[i + 1])
			if value == "" or value.begins_with("--"):
				return "An option is missing its value."
			if arg == "--view":
				var ends := value.split(">", true)
				if ends.size() != 2:
					return "--view needs x,y,z>look_x,look_y,look_z."
				for end in ends:
					var xyz := end.split(",", true)
					if xyz.size() != 3:
						return "--view needs two three-coordinate vectors."
					for axis in xyz:
						var number := axis.strip_edges()
						var exponent := number.to_lower().find("e")
						# Godot's float predicate accepts an unfinished exponent.
						if exponent >= 0 and not number.substr(exponent + 1).is_valid_int():
							return "--view exponents must contain integer digits."
						if not number.is_valid_float() or not is_finite(float(axis)):
							return "--view coordinates must be finite numbers."
			elif arg == "--size":
				var dimensions := value.split("x", true)
				if dimensions.size() != 2:
					return "--size needs widthxheight."
				for dimension in dimensions:
					if not dimension.strip_edges().is_valid_int():
						return "--size dimensions must be integers."
			elif arg == "--frames":
				if not value.strip_edges().is_valid_int():
					return "--frames must be an integer."
			i += 1
		elif arg.begins_with("--"):
			return "Unknown option."
		else:
			if arg == "":
				return "Package and output prefix must not be empty."
			positional_count += 1
		i += 1
	if positional_count < 1 or positional_count > 2:
		return "Provide a package and, optionally, one output prefix."
	if report and not validate:
		return "--report-v1 requires --validate."
	return ""


func _init() -> void:
	var cwd_error := KitLoop._cwd_error(OS.get_cmdline_user_args())
	if cwd_error != "":
		printerr("usage: world_view.gd -- [--validate] <package> [out_prefix] [--view x,y,z>lx,ly,lz] [--npcs mode] [--tier t] [--frames n] [--size widthxheight]")
		printerr(cwd_error)
		quit(2)
		return
	var args := KitLoop.user_args()
	var argument_error := _argv_error(args)
	if argument_error != "":
		printerr("usage: world_view.gd -- [--validate] <package> [out_prefix] [--view x,y,z>lx,ly,lz] [--npcs mode] [--tier t] [--frames n] [--size widthxheight]")
		printerr(argument_error)
		quit(2)
		return
	var pos: Array = []
	var validate := false
	var npcs := "all"
	var tier := ""   ## --tier low|medium|high|ultra: preview / perf that hardware tier (docs/WORLD_TIERS.md)
	var i := 0
	var size := Vector2i(1280, 720)
	var size_set := false
	var frames_set := false
	while i < args.size():
		var a := args[i]
		match a:
			"--validate": validate = true
			"--report-v1": _report_v1 = true
			"--quick": _quick = true
			"--view":
				i += 1
				var parts := args[i].split(">")
				_views.append(["custom%d" % _views.size(), _vec(parts[0]), _vec(parts[1])])
			"--npcs":
				i += 1
				npcs = args[i]
			"--tier":
				i += 1
				tier = args[i]
			"--frames":
				i += 1
				_frames = int(args[i])
				frames_set = true
			"--size":
				i += 1
				var wh := args[i].split("x")
				size = Vector2i(int(wh[0]), int(wh[1]))
				size_set = true
			"--quest-done":
				i += 1
				_quests_done = args[i].split(",", false)
			_: pos.append(a)
		i += 1
	if _quick:   # explicit --size / --frames still win over the quick defaults
		if not size_set:
			size = QUICK_SIZE
		if not frames_set:
			_frames = QUICK_FRAMES
	if pos.is_empty():
		printerr("usage: world_view.gd -- [--validate] <package> [out_prefix] [--view ...] [--tier t] [--quick]")
		quit(2)
		return
	if _report_v1 and not validate:
		quit(2)
		return
	var t0 := Time.get_ticks_msec()
	_run_t0 = t0
	# the playbook's hard targets are the low tier's: measure that unless asked
	_pkg = WorldPackage.open(_abs(pos[0]), {"tier": tier if tier != "" else "low"})
	print("OPEN_MS ", Time.get_ticks_msec() - t0)
	if _pkg.ok:
		_world_checks(validate or pos.size() < 2)
	if not _report_v1:
		_report()
	if not _pkg.ok:
		if _report_v1:
			_emit_validation_report([_pkg], false)
		quit(0 if _report_v1 else 1)
		return
	# every hardware tier the world has opens and fits its own budgets (docs/WORLD_TIERS.md)
	var checked: Array = [_pkg]
	var tiers := WorldTiers.declared(_pkg.manifest)
	if tiers.size() > 1:
		var bad := false
		for t in tiers:
			var tp := WorldPackage.open(_abs(pos[0]), {"tier": t})
			checked.append(tp)
			if not _report_v1:
				print("TIER %-6s %s triangles=%d texture_size=%d texture_bytes=%d %s" % [t, "OK" if tp.ok else "FAILED",
				int(tp.stats.get("triangles", 0)), int(tp.stats.get("texture_size", 0)), int(tp.stats.get("texture_bytes", 0)),
				"; ".join(tp.errors)])
			bad = bad or not tp.ok
		if bad:
			if _report_v1:
				_emit_validation_report(checked, false)
			quit(0 if _report_v1 else 1)
			return
	if validate or pos.size() < 2:
		# the package's own UI page files, checked as the browser would (U7)
		var pages := PageCheck.check_package(_pkg)
		if not _report_v1:
			for line in pages.lines:
				print(line)
		if not pages.errors.is_empty():
			if _report_v1:
				for e in pages.errors:
					ValidationReport.add(_pkg.validation_issues, "reference.invalid" if String(e[1]).contains("not in the package") else "schema.invalid", e[0])
				_pkg.errors.append("%d UI page file(s) refused" % pages.errors.size())
				_emit_validation_report(checked, false)
			else:
				print("FAILED")
			quit(0 if _report_v1 else 1)
			return
		if _report_v1:
			_emit_validation_report(checked, true)
		quit(0)
		return
	_prefix = _abs(pos[1])
	DirAccess.make_dir_recursive_absolute(_prefix.get_base_dir())
	root.size = size
	_size = size
	Controls.setup()
	t0 = Time.get_ticks_msec()
	var world := _pkg.build(root, {"npcs": npcs})
	print("BUILD_MS ", Time.get_ticks_msec() - t0)
	var adapter := RenderingServer.get_video_adapter_name().to_lower()
	if not _quick and (adapter.contains("llvmpipe") or adapter.contains("software") or adapter.contains("swrast")):
		print("NOTE software renderer (%s): each view is slow; add --quick for a 640x360 look with %d views" % [adapter, QUICK_VIEWS])
	if world == null:
		printerr("ERROR: preview could not build a world root.")
		quit(1)
		return
	_pkg.portal_entered.connect(func(a: String) -> void: print("PORTAL ", a))
	_world = world
	_attach_quest_effects(world)
	_preview_requested = true
	# screenshots of a window nobody looks at: vsync would throttle to a crawl
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)


## Quest end states as the game shows them (QuestEffects, which QuestBridge attaches
## for a visitor): `show` entries hidden and `hide` entries drawn until the quest is
## done. Loaded by path, so a browser without QuestEffects still previews (NOTE line).
func _attach_quest_effects(world: Node3D) -> void:
	var path := "res://scripts/worlds/quest_effects.gd"
	if not ResourceLoader.exists(path):
		if not _quests_done.is_empty():
			print("NOTE --quest-done ignored: this browser has no QuestEffects")
		return
	var done := _quests_done
	var state := func(qid: String) -> String:
		for q in done:
			if q == "all" or qid == q or qid.ends_with("." + q):
				return "done"
		return ""
	var fx: Node = load(path).attach(_pkg, world, state)
	if fx != null:
		print("QUESTS ", "start" if done.is_empty() else "done: " + ",".join(done))


func _emit_validation_report(packages: Array, valid: bool) -> void:
	var issues: Array = []
	var errors := 0
	var warnings := 0
	# Error details first: warnings must not displace the rejection cause.
	for pkg in packages:
		errors += pkg.errors.size()
		warnings += pkg.warnings.size()
		for issue in pkg.validation_issues:
			if not issue[0] in ["feature.skipped", "validation.warning", "signature.unsigned"]:
				var resource: String = issue[1]
				if resource == "" and String(issue[2]).begins_with("manifest"):
					resource = "manifest.json"
				ValidationReport.add(issues, issue[0], resource, issue[2])
	for pkg in packages:
		for issue in pkg.validation_warning_issues:
			ValidationReport.add(issues, issue[0], issue[1], issue[2])
		for index in range(pkg.validation_warning_issues.size(), pkg.warnings.size()):
			ValidationReport.add(issues, "validation.warning")
	print(ValidationReport.encode(valid, issues, errors, warnings))


func _report() -> void:
	print("PACKAGE ", _pkg.path)
	if _pkg.manifest.size() > 0:
		print("WORLD %s \"%s\" %s by %s" % [_pkg.id, _pkg.title, _pkg.version, _pkg.manifest.get("author", {}).get("name", "?")])
	print("SIGNER ", _pkg.signer_text())
	for w in _pkg.warnings:
		print("WARN ", w)
	# browsers refuse reused records sourced from another world (an internal task): only builtin reuse resolves
	for r in _pkg.manifest.get("reused", []):
		if r is Dictionary and String((r.get("source", {}) as Dictionary).get("kind", "")) == "world":
			print("WARN reused %s is sourced from another world; browsers refuse it. Carry the file (iamar-world assets use does) and drop the reused record" % String(r.get("path", "?")).left(80).replace("\n", " "))
	for e in _pkg.errors:
		print("ERROR ", e)
	if _pkg.ok:
		var b: Dictionary = _pkg.budgets if not _pkg.budgets.is_empty() else _pkg.manifest.budgets   # the tier opened (docs/WORLD_TIERS.md)
		for k in _pkg.stats:
			print("STATS %-14s %10d / %s" % [k, int(_pkg.stats[k]), str(int(b[k])) if b.has(k) else "-"])
		print("NPCS %d  QUESTS %d  SPAWN %s" % [_pkg.npcs.size(), _pkg.quests.size(), _pkg.spawn_point.origin])
		# reuse first (kit/AGENT_KIT.md): what visitors download versus what they already have
		var rr := _pkg.reuse_report()
		print("REUSE new %d bytes (%.1f MB), reused %d bytes (%.1f MB) in %d objects" % [rr.new, rr.new / 1048576.0, rr.reused, rr.reused / 1048576.0, rr.objects])
		for line in _pkg.attribution_text().split("
", false):
			print("CREDIT ", line)
	print("OK" if _pkg.ok else "FAILED")


func _auto_views(world: Node3D) -> void:
	var sp := _pkg.spawn_point
	var eye := sp.origin + Vector3(0, 1.7, 0)
	_views.append(["spawn", eye, eye - sp.basis.z * 10.0])
	# Frame the objects and the spawn point, not the water and terrain planes (ViewBounds).
	_views.append_array(ViewBounds.ring_views(ViewBounds.frame_box(world, sp.origin)))
	var npcs := world.get_node_or_null("Npcs")
	if npcs and npcs.get_child_count() > 0:
		var mid := Vector3.ZERO
		var count := 0
		for n in npcs.get_children():
			if n is Node3D:   # (an NPC bridge can hold non-spatial helpers too)
				mid += (n as Node3D).global_position
				count += 1
		mid /= maxi(count, 1)
		var from := eye if eye.distance_to(mid) > 3.0 else mid + Vector3(0, 1.8, 6)
		var d := (mid - from)
		d.y = 0
		_views.append(["npcs", mid - d.normalized() * minf(d.length(), 7.0) + Vector3(0, 1.6, 0), mid + Vector3(0, 1.0, 0)])
	if _quick and _views.size() > QUICK_VIEWS:
		# the spawn view first, then views spread evenly over the rest (ring, top, npcs)
		var kept: Array = [_views[0]]
		var rest := _views.size() - 1
		for k in range(QUICK_VIEWS - 1):
			kept.append(_views[1 + int(float(k) * rest / float(QUICK_VIEWS - 1))])
		print("QUICK %d of %d views (give --view for others)" % [kept.size(), _views.size()])
		_views = kept


func _apply() -> void:
	var v: Array = _views[_i]
	_view_t0 = Time.get_ticks_msec()
	_cam.look_at_from_position(v[1], v[2], Vector3.UP if absf((v[2] - v[1]).normalized().y) < 0.99 else Vector3.FORWARD)
	_cam.environment = _underwater_env(v[1])
	if _cam.environment != null:
		print("UNDERWATER view %d %s: below the water surface, water fog instead of the sky" % [_i, v[0]])
	_wait = 0
	_fps_acc = 0.0
	_fps_n = 0


## The look a visitor gets with the camera at `at` under a package world's water
## (Underwater.view_env: fog tinted by the water, the sky behind it), or null above
## water. A browser older than PackageWater has no underwater look in packages: null.
func _underwater_env(at: Vector3) -> Environment:
	if not ResourceLoader.exists("res://scripts/worlds/package_water.gd"):
		return null
	var uw: Script = load("res://scripts/world/underwater.gd")
	if uw == null:
		return null
	var w := _cam.get_world_3d()
	return uw.view_env(w.environment if w else null, at)


func _process(delta: float) -> bool:
	if not _preview_requested:
		return false
	if not _started:
		# SceneTree._init runs before tree entry. Script custody, on_init,
		# bounds and NPC positions need the actual entered world root.
		_started = true
		# A windowed run opens the main window at the project size (1280x720) after _init,
		# so root.size there did not stick and --size was ignored unless the engine also got
		# --resolution. Size the window now; headless has no window to size.
		if DisplayServer.get_name() != "headless" and root.size != _size:
			DisplayServer.window_set_size(_size)
			root.size = _size
		var preview := ScriptPreview.attach(_pkg, _world, root)
		if not preview.ok:
			printerr("ERROR: world script preview failed: " + String(preview.error))
			quit(1)
			return true
		_scripts = preview.scripts
		_script_current = preview.current
		_script_us_seen = _script_us()   # exclude on_init from per-frame cost
		if not _scripts.is_empty():
			print("SCRIPTS %d running (playerless preview)" % _scripts.size())
		# Preserve the viewer camera's precedence over on_init camera requests.
		_cam = Camera3D.new()
		_cam.fov = 65
		_cam.far = 2000
		_cam.near = 0.1
		root.add_child(_cam)
		_cam.current = true
		if _views.is_empty():
			_auto_views(_world)
		_apply()
		return false
	var script_error := ScriptPreview.check(_scripts, _script_current, _world)
	if script_error != "":
		printerr("ERROR: world script preview failed: " + script_error)
		ScriptPreview.dispose(_scripts)
		_scripts.clear()
		quit(1)
		return true
	_wait += 1
	# world scripts count on every frame, settling ones too (a script's cost is
	# not part of the loading hitch the 20 settle frames skip)
	var us := _script_us()
	var ms := (us - _script_us_seen) / 1000.0
	_script_us_seen = us
	if not _scripts.is_empty():
		_script_ms_sum += ms
		_script_frames += 1
		if ms > _script_ms_max[0]:
			_script_ms_max = [ms, String(_views[_i][0])]
	if _wait > 20:
		_fps_acc += delta
		_fps_n += 1
		_worst_frame.frame(delta * 1000.0, _wait)
	if _wait == _frames and not _remeasure:
		var img := root.get_texture().get_image()
		var file := "%s_%d_%s.png" % [_prefix, _i, _views[_i][0]]
		img.save_png(file)
		var dc := int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
		var pr := int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME))
		var objects := int(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME))
		var view_ms := Time.get_ticks_msec() - _view_t0
		_view_ms.append([String(_views[_i][0]), view_ms])
		print("VIEW %d %s draw=%d prims=%d objects=%d fps=%s -> %s" % [_i, _views[_i][0],
			dc, pr, objects, ("%.1f" % (_fps_n / maxf(_fps_acc, 0.001))) if _fps_n > 0 else "not measured", file])
		print("VIEWTIME %d %s ms=%d" % [_i, _views[_i][0], view_ms])
		if dc > 0 or pr > 0 or objects > 0:
			_visible_views += 1
		if pr > _worst[1]:
			_worst = [String(_views[_i][0]), pr, dc]
		if dc > _max_draws[1]:
			_max_draws = [String(_views[_i][0]), dc]
		_vram_max = maxf(_vram_max, Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0)
	if _wait == _frames:
		# a view over the frame limit is measured once more from where it stands (already
		# settled, no new screenshot); a stall that does not come back was the computer
		if _worst_frame.end_pass(String(_views[_i][0])):
			print("REMEASURE view %s: worst frame %.1f ms is over %.0f ms; measuring it again" % [_views[_i][0], _worst_frame.first_pass_ms, TARGET_FRAME_MS])
			_remeasure = true
			_wait = 19   # frame 20 still carries the screenshot's readback stall: not counted
			return false
		_remeasure = false
		_i += 1
		if _i >= _views.size():
			print("PREVIEW_MS total=%d views=%d (%s)%s" % [Time.get_ticks_msec() - _run_t0, _view_ms.size(),
				", ".join(_view_ms.map(func(e): return "%s %d" % e)), "" if _quick else "  (--quick: smaller, fewer views, faster on CPU-only hosts)"])
			print("WORST view %s: prims=%d draws=%d (budgets: stay under ~150 draw calls and your declared triangles)" % _worst)
			print("MAXDRAWS view %s: draws=%d" % _max_draws)
			print(_worst_frame.describe(_frames))
			# the hard targets from kit/AGENT_KIT.md; fix any FAIL with the recipe named
			var fails := 0
			if _visible_views == 0:
				fails += 1
				printerr("ERROR: preview rendered no world geometry (every VIEW had draw=0 prims=0 objects=0).")
				printerr("  Do not accept these screenshots or performance numbers; update the browser/runtime and retry.")
			for t in [["triangles", _worst[1], TARGET_TRIS, "lod_chain, impostor, merge_static"],
					["draw_calls", _max_draws[1], TARGET_DRAWS, "merge_static, instancing, occluders"],
					["video_memory_mb", snappedf(_vram_max, 0.1), TARGET_VRAM_MB, "texture_compression, texture_sizes"]] \
					+ ([["worst_frame_ms", snappedf(float(_worst_frame.worst[0]), 0.1), TARGET_FRAME_MS, "progressive_build, merge_static"]] if _worst_frame.worst[2] >= 0 else []) \
					+ ([["world_scripts_ms", snappedf(_script_ms_max[0], 0.01), TARGET_SCRIPT_MS, "fewer on_tick calls (tick_hz), work spread over on_timer, smaller messages"]] if not _scripts.is_empty() else []):
				var ok: bool = float(t[1]) <= float(t[2])
				fails += 0 if ok else 1
				print("TARGET %-16s %s  %s (limit %s)%s" % [t[0], "PASS" if ok else "FAIL", str(t[1]), str(t[2]),
					"" if ok else "  -> recipes: " + t[3]])
			if _worst_frame.worst[2] < 0:
				print("TARGET worst_frame_ms   NOT MEASURED  no frame was timed: each view needs more than 20 frames (the first 20 settle); rerun with --frames 60 or more")
			var broken: Array = []
			for ws in _scripts:
				if is_instance_valid(ws) and ((ws as WorldScript).disabled or not (ws as WorldScript).errors.is_empty()):
					broken.append("%s (%s)" % [ws.script_path, String((ws as WorldScript).errors[0]).split("\n")[0] if not (ws as WorldScript).errors.is_empty() else "stopped"])
			if not broken.is_empty():
				fails += 1
				print("TARGET world_scripts_ok   FAIL  %s  -> a script trapped or was stopped: stay inside its fuel and time budgets (docs/WORLD_API.md)" % ", ".join(broken))
			if _scripts.is_empty():
				print("TARGET world_scripts_ms INFO  no world scripts")
			else:
				print("SCRIPT_MS mean=%.3f worst=%.3f in view %s over %d frames" % [_script_ms_sum / maxf(_script_frames, 1), _script_ms_max[0], _script_ms_max[1], _script_frames])
				for ws in _scripts:
					if is_instance_valid(ws):
						for fn in (ws as WorldScript).stats:
							var st: Dictionary = ws.stats[fn]
							print("SCRIPT %s %s calls=%d us_max=%d us_total=%d%s" % [ws.script_path, fn, st.calls, st.us_max, st.us_total, " DISABLED" if ws.disabled else ""])
			print("TARGET fps_here         INFO  %s (the 30 fps target is for the low tier, e.g. a Radeon HD 5750; measure there)" % (("%.1f" % (_fps_n / maxf(_fps_acc, 0.001))) if _fps_n > 0 else "not measured"))
			print("TARGETS %s" % ("PASS" if fails == 0 else "FAIL (%d)" % fails))
			if fails > 0:
				quit(1)
			ScriptPreview.dispose(_scripts)
			_scripts.clear()
			return true
		_apply()
	return false


## Microseconds all the world's scripts have spent in the sandbox so far
## (WorldScript.stats, every export call).
func _script_us() -> int:
	var total := 0
	for ws in _scripts:
		if is_instance_valid(ws):
			for fn in (ws as WorldScript).stats:
				total += int(ws.stats[fn].us_total)
	return total


## Mistakes that open fine but play or look wrong (scripts/kit/world_checks.gd), as WARN
## lines. validate builds the world once, bare and headless, to see where each spawn lands.
func _world_checks(spawns: bool) -> void:
	var b: Dictionary = _pkg.budgets if not _pkg.budgets.is_empty() else _pkg.manifest.get("budgets", {})
	_pkg.warnings.append_array(WorldChecks.terrain_warnings(_pkg.scene, int(b.get("triangles", TARGET_TRIS))))
	_pkg.warnings.append_array(WorldChecks.tonemap_warnings(_pkg.scene))
	var folder := _pkg.path if DirAccess.dir_exists_absolute(_pkg.path) else ""
	_pkg.warnings.append_array(WorldChecks.room_light_warnings(_pkg.scene, WorldChecks.rooms_reader(folder)))
	if not spawns:
		return
	var raw := WorldChecks.raw_spawns(_pkg.manifest, _pkg.scene)
	if raw.is_empty():
		return
	var world := _pkg.build(root, {"npcs": "none", "environment": false, "sounds": false, "portals": false, "triggers": false, "creatures": false})
	if world == null or _pkg.ground == null:
		return
	var shapes := WorldChecks.solids(world)
	var solid := func(feet: Vector3) -> String: return WorldChecks.solid_hit(shapes, feet)
	_pkg.warnings.append_array(WorldChecks.spawn_warnings(raw, _pkg.scene.get("water", []), _pkg.ground.height_at, solid))
	world.get_parent().remove_child(world)
	world.free()
