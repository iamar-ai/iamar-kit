extends SceneTree
## World UI pages offline (iamar-ui-pages U7): the agent kit checks and renders a
## page's JSON without running a world, with the same rules the browser applies
## at ui_page_set (UiPageValidator, the world's page limits) plus the checks only
## a package can answer: every `asset:` image a page names is in the package, is a
## PNG/JPEG/WebP and fits max_image_px, and a page uses at most max_page_images.
##
##   iamar-world validate shop.page.json [more.page.json | folder ...] [--package folder]
##   iamar-world preview  shop.page.json out/shop [--mode overlay|modal|both]
##                        [--size 1280x720] [--package folder] [--frames n]
##
## kit_loop.gd sends `validate` / `preview` here when the first path ends in .json;
## `iamar-world validate <world folder>` also checks every *.page.json and
## *.patch.json in the package (world_view.gd calls check_package). A file named
## *.patch.json is checked as a ui_page_patch body. Exit 0 all good, 1 a page is
## refused, 2 usage.
##
## Preview builds the page exactly as the browser shows it (UiPageHost: the
## overlay column on the right, or the modal framed in the world's colour) over a
## dark backdrop and saves <out_prefix>_<mode>.png. It needs graphics: run it
## under `offscreen`, never on a desktop someone is using.

const MODES := {"overlay": 1, "modal": 2}

var _fails := 0
var _ws: WorldScript
var _host: UiPageHost
var _shots: Array = []   ## [mode name, file]
var _prefix := ""
var _frames := 12
var _wait := 0
var _done := false
var _rc := 0
var _package := ""


## Errors for one page (or patch) text; [] when the browser would accept it.
## limits: WorldApi.limits(manifest budgets). source: a WorldSource for image
## checks, or null (images then are not checked).
static func check_text(text: String, is_patch: bool, limits: Dictionary, source: Variant) -> Dictionary:
	var cap := int(limits.get("max_patch_bytes" if is_patch else "max_page_bytes", UiPageVocab.MAX_PATCH_BYTES if is_patch else UiPageVocab.MAX_PAGE_BYTES))
	var bytes := text.to_utf8_buffer().size()
	if bytes > cap:
		return {"errors": ["$: %d bytes is over the %d byte limit" % [bytes, cap]], "nodes": 0, "images": 0}
	var r := UiPageValidator.patch(text) if is_patch else \
		UiPageValidator.page(text, clampi(int(limits.get("max_page_nodes", UiPageVocab.MAX_PAGE_NODES)), 1, UiPageVocab.MAX_PAGE_NODES))
	if not r.ok:
		return {"errors": [String(r.error)], "nodes": 0, "images": 0}
	var srcs := {}
	_assets(r.patch if is_patch else r.page.root, srcs)
	var errors: Array = []
	var max_images := int(limits.get("max_page_images", WorldApi.LIMITS.get("max_page_images", 32)))
	if srcs.size() > max_images:
		errors.append("$: %d images, over this world's %d page images" % [srcs.size(), max_images])
	if source != null:
		var max_px := int(limits.get("max_image_px", WorldApi.LIMITS.get("max_image_px", 2048)))
		for src in srcs:
			var rel := String(src).trim_prefix("asset:")
			if not source.has(rel):
				errors.append("%s: %s is not in the package" % [srcs[src], src])
				continue
			var head := UiPageImages.header(source.read(rel))
			if head.is_empty():
				errors.append("%s: %s is not a PNG, JPEG or WebP image" % [srcs[src], src])
			elif int(head.w) > max_px or int(head.h) > max_px:
				errors.append("%s: %s is %dx%d, over %d px a side" % [srcs[src], src, int(head.w), int(head.h), max_px])
	return {"errors": errors, "nodes": 0 if is_patch else int(r.nodes), "images": srcs.size()}


## Every asset: image under a node (or patch), as src -> the first JSON path naming it.
static func _assets(v: Variant, out: Dictionary, where := "$.root") -> void:
	if v is Dictionary:
		for k in v:
			var x = v[k]
			if (k == "src" or k == "icon") and x is String and String(x).begins_with("asset:"):
				if not out.has(x):
					out[x] = "%s.%s" % [where, k]
			elif x is Dictionary or x is Array:
				_assets(x, out, "%s.%s" % [where, k])
	elif v is Array:
		for i in v.size():
			_assets(v[i], out, "%s[%d]" % [where, i])


## A page that names images, checked without a readable package, is refused: an
## OK would claim images that were never looked at.
static func unread_images(r: Dictionary, source: WorldSource) -> void:
	if int(r.images) > 0 and (source == null or not source.ok()):
		r.errors.append("$: its %d image(s) were not checked: the folder %s cannot be read as a package (%s); pass --package <world folder>"
			% [int(r.images), source.path if source != null else "?", source.error if source != null else "no source"])


static func is_page_file(rel: String) -> bool:
	return rel.ends_with(".page.json") or rel.ends_with(".patch.json")


## The package's own page files (*.page.json, *.patch.json), checked against its
## manifest budgets and files. Returns {checked, errors: [[rel, message]], lines}.
static func check_package(pkg: WorldPackage) -> Dictionary:
	var out := {"checked": 0, "errors": [], "lines": []}
	if pkg == null or pkg.source == null:
		return out
	var limits := WorldApi.limits(pkg.manifest.get("budgets", {}) if pkg.manifest.get("budgets", {}) is Dictionary else {})
	var total := 0
	for rel in pkg.source.list():
		if not is_page_file(rel):
			continue
		out.checked += 1
		var r := check_text(pkg.source.read(rel).get_string_from_utf8(), rel.ends_with(".patch.json"), limits, pkg.source)
		total += int(r.nodes)
		for e in r.errors:
			out.errors.append([rel, e])
			out.lines.append("ERROR page %s %s" % [rel, e])
		if r.errors.is_empty():
			out.lines.append("PAGE %s OK%s" % [rel, "" if rel.ends_with(".patch.json") else " nodes=%d" % int(r.nodes)])
	if out.checked > 0:
		var cap := int(limits.get("page_nodes_total", UiPageVocab.PAGE_NODES_TOTAL))
		out.lines.append("PAGES %d files, %d nodes (a script may show at most %d nodes at once)" % [out.checked, total, cap])
	return out


## The package folder a loose page file belongs to: the nearest folder above it
## with a manifest.json, else the page's own folder.
static func package_dir(file: String) -> String:
	var d := file.get_base_dir()
	while d != "" and d != "/" and not d.ends_with(":/"):
		if FileAccess.file_exists(d.path_join("manifest.json")):
			return d
		var up := d.get_base_dir()
		if up == d:
			break
		d = up
	return file.get_base_dir()


static func _budgets(dir: String) -> Dictionary:
	var m = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("manifest.json"))) \
		if FileAccess.file_exists(dir.path_join("manifest.json")) else null
	return m.budgets if m is Dictionary and m.get("budgets") is Dictionary else {}


func _usage() -> void:
	printerr("usage: iamar-world validate <file.page.json|folder> ... [--package folder]")
	printerr("       iamar-world preview <file.page.json> <out_prefix> [--mode overlay|modal|both] [--size WxH] [--package folder] [--frames n]")
	quit(2)


func _init() -> void:
	var args := KitLoop.user_args()
	var validate := not args.is_empty() and args[0] == "--validate"
	if validate:
		args = args.slice(1)
	var pos: Array = []
	var mode := "both"
	var size := Vector2i(1280, 720)
	var package := ""
	var i := 0
	while i < args.size():
		var a := String(args[i])
		if a in ["--mode", "--size", "--package", "--frames"]:
			if i + 1 >= args.size():
				_usage()
				return
			var v := String(args[i + 1])
			match a:
				"--mode": mode = v
				"--size":
					var wh := v.split("x")
					size = Vector2i(int(wh[0]), int(wh[1])) if wh.size() == 2 else Vector2i.ZERO
				"--package": package = KitLoop.absolute_path(v)
				"--frames": _frames = int(v)
			i += 2
			continue
		pos.append(KitLoop.absolute_path(a))
		i += 1
	if pos.is_empty() or (not validate and pos.size() != 2) or not (mode == "both" or MODES.has(mode)) \
			or size.x < 64 or size.y < 64 or _frames < 1:
		_usage()
		return
	if validate:
		_package = package
		quit(_validate(pos))
		return
	_preview(pos[0], pos[1], mode, size, package)


func _validate(paths: Array) -> int:
	var files: Array = []
	for p in paths:
		if DirAccess.dir_exists_absolute(p):
			_collect(p, files)
		elif FileAccess.file_exists(p):
			files.append(p)
		else:
			print("ERROR %s: no such file or folder" % p)
			_fails += 1
	if files.is_empty() and _fails == 0:
		print("ERROR no *.page.json or *.patch.json files found")
		return 1
	for f in files:
		var dir := _package if _package != "" else package_dir(f)
		var source := WorldSource.open(dir)
		var r := check_text(FileAccess.get_file_as_string(f), String(f).ends_with(".patch.json"), WorldApi.limits(_budgets(dir)),
			source if source != null and source.ok() else null)
		unread_images(r, source)
		for e in r.errors:
			print("ERROR %s %s" % [f, e])
		if r.errors.is_empty():
			print("PAGE %s OK%s" % [f, "" if String(f).ends_with(".patch.json") else " nodes=%d" % int(r.nodes)])
		else:
			_fails += 1
		if source != null:
			source.close()
	print("OK" if _fails == 0 else "FAILED (%d)" % _fails)
	return 0 if _fails == 0 else 1


func _collect(dir: String, out: Array) -> void:
	for f in DirAccess.get_files_at(dir):
		if is_page_file(f):
			out.append(dir.path_join(f))
	for d in DirAccess.get_directories_at(dir):
		if not d.begins_with("."):
			_collect(dir.path_join(d), out)


func _preview(file: String, prefix: String, mode: String, size: Vector2i, package: String) -> void:
	if not FileAccess.file_exists(file) or file.ends_with(".patch.json"):
		printerr("ERROR preview needs a page file (*.page.json): " + file)
		quit(2)
		return
	var dir := package if package != "" else package_dir(file)
	var source := WorldSource.open(dir)
	var src: Variant = source if source != null and source.ok() else null
	var text := FileAccess.get_file_as_string(file)
	var r := check_text(text, false, WorldApi.limits(_budgets(dir)), src)
	unread_images(r, source)
	for e in r.errors:
		print("ERROR %s %s" % [file, e])
	if not r.errors.is_empty():
		quit(1)
		return
	if DisplayServer.get_name() == "headless":
		printerr("ERROR preview needs graphics: run it under offscreen, not --headless (validate works headless)")
		quit(1)
		return
	_prefix = prefix
	DirAccess.make_dir_recursive_absolute(prefix.get_base_dir())
	DisplayServer.window_set_size(size)
	root.size = size
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.set_default_clear_color(Color(0.13, 0.14, 0.16))
	# The browser's own page host, driven here without wasm or players.
	_ws = WorldScript.new()
	_ws.world_id = file.get_file().get_basename().get_basename()
	_ws.limits = WorldApi.limits(_budgets(dir))
	_ws.process_mode = Node.PROCESS_MODE_DISABLED
	_ws.loaded = true
	_ws._started = true
	_ws.asset_root = "package:"
	_ws.asset_reader = func(rel: String) -> PackedByteArray:
		return src.read(rel) if src != null and src.has(rel) else PackedByteArray()
	root.add_child(_ws)
	_host = _ws.ext._pages()
	var res := _host.set_page(1, text)
	if int(res.code) != WorldApi.OK:
		print("ERROR %s %s" % [file, res.error])
		quit(1)
		return
	for m in (MODES.keys() if mode == "both" else [mode]):
		_shots.append([m, "%s_%s.png" % [prefix, m]])
	print("PAGE %s OK nodes=%d" % [file, int(r.nodes)])


## Percent of a grid of points in `r` (the page root's rect) that differ from the
## clear colour: 0 means the page was laid out but never reached the screen.
func _drawn(img: Image, r: Rect2) -> int:
	var bg := Color(0.13, 0.14, 0.16)
	var area := Rect2i(r).intersection(Rect2i(Vector2i.ZERO, img.get_size()))
	if area.size.x <= 0 or area.size.y <= 0:
		return 0
	var n := 0
	var hit := 0
	for y in range(area.position.y, area.end.y, 4):
		for x in range(area.position.x, area.end.x, 4):
			n += 1
			var c := img.get_pixel(x, y)
			if absf(c.r - bg.r) + absf(c.g - bg.g) + absf(c.b - bg.b) > 0.06:
				hit += 1
	return ceili(100.0 * hit / maxf(n, 1.0)) if hit > 0 else 0


func _process(_delta: float) -> bool:
	if _done:
		quit(_rc)   # a frame after the page host was freed, so nothing leaks at exit
		return true
	if _host == null or _shots.is_empty():
		return false
	if _wait == 0:
		_host.show(1, MODES[_shots[0][0]])
	_host.store.step(1_000_000)
	# the host's _process is off here (the script is disabled): draw the overlay
	# column's page caches (UiPageOverlayCache, U9b) as it would
	if _host.overlay_cache != null:
		_host.overlay_cache.step()
	_wait += 1
	if _wait < _frames or (_host.store.images.pending() > 0 and _wait < _frames + 120):
		return false
	var img := root.get_texture().get_image()
	if img == null or img.is_empty():
		printerr("ERROR preview rendered nothing")
		_rc = 1
		_host.clear()
		_ws.queue_free()
		_shots.clear()
		_done = true
		return false
	var file: String = _shots[0][1]
	img.save_png(file)
	var drawn := _drawn(img, _host.store.pages[1].builder.root.get_global_rect())
	print("SHOT %s %dx%d -> %s (page area %d%% drawn)" % [_shots[0][0], img.get_width(), img.get_height(), file, drawn])
	if drawn == 0:
		printerr("ERROR preview: the page drew nothing where it sits (%s)" % _shots[0][0])
		_rc = 1
	_shots.pop_front()
	_wait = 0
	if _shots.is_empty():
		_host.clear()   # as WorldScriptExt.clear does when a world unloads
		_ws.queue_free()
		_done = true
	return false
