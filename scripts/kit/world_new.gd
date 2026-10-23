extends SceneTree
const WorldScaffold = preload("res://scripts/kit/world_scaffold.gd")
const FromBrief = preload("res://scripts/kit/world_from_brief.gd")
const KitHouseRooms = preload("res://scripts/kit/kit_house_rooms.gd")
## `iamar-world new <folder> [--id my_world] [--title "My World"] [--author "Name"] [--template beach]`:
## scaffolds a minimal, valid world package (docs/WORLD_FORMAT.md) to build on - by
## default a flat meadow with a sky, sun, a few shapes, a spawn point and a portal home
## to Oakhaven - and checks that it opens. --template picks a lit starting scene instead
## (beach, interior, forest, town: WorldScaffold.TEMPLATES in the browser).
## --from-brief brief.json blocks the world out from an interview brief: the template, a
## house from its rooms, spawn, portal and path (FromBrief; docs/WORLD_FROM_BRIEF.md).


## Reject incomplete CLI requests before resolving paths or creating a draft.
## Keep non-option values opaque; the scaffold owns identity/text validation.
static func _argv_error(args: PackedStringArray) -> String:
	if args.is_empty() or args[0] == "" or args[0].begins_with("--"):
		return "Provide a destination folder before the options."
	var i := 1
	while i < args.size():
		if not args[i] in ["--id", "--title", "--author", "--template", "--from-brief"]:
			return "Expected --id, --title, --author, --template or --from-brief and a value."
		if i + 1 >= args.size() or args[i + 1] == "" or args[i + 1].begins_with("--"):
			return "An option is missing its value."
		i += 2
	return ""


func _initialize() -> void:
	var cwd_error := KitLoop._cwd_error(OS.get_cmdline_user_args())
	if cwd_error != "":
		printerr("usage: new <folder> [--id id] [--title title] [--author name] [--template meadow|beach|interior|forest|town] [--from-brief brief.json]")
		printerr(cwd_error)
		quit(2)
		return
	var args := KitLoop.user_args()
	var argument_error := _argv_error(args)
	if argument_error != "":
		printerr("usage: new <folder> [--id id] [--title title] [--author name] [--template meadow|beach|interior|forest|town] [--from-brief brief.json]")
		printerr(argument_error)
		quit(2)
		return
	if args.is_empty():
		printerr("usage: new <folder> [--id id] [--title title] [--author name] [--template meadow|beach|interior|forest|town] [--from-brief brief.json]")
		quit(2)
		return
	var dir := _abs(args[0])
	var opt := {}
	for i in range(1, args.size() - 1):
		if args[i].begins_with("--"):
			opt[args[i].substr(2)] = args[i + 1]
	var brief_plan := {}
	if opt.has("from-brief"):
		brief_plan = _read_brief(_abs(String(opt["from-brief"])), String(opt.get("template", "")))
		if brief_plan.has("error"):
			printerr("brief: " + String(brief_plan.error))
			quit(2)
			return
		for key in ["id", "title"]:
			if not opt.has(key) and String(brief_plan[key]) != "":
				opt[key] = brief_plan[key]
		opt["template"] = brief_plan.template
	var id := String(opt.get("id", dir.get_file().to_lower().replace(" ", "_").replace("-", "_")))
	var title := String(opt.get("title", id.capitalize()))
	# Never default to the OS login name: author.name is signed and shown to every visitor.
	var author := String(opt.get("author", "World builder"))
	var template := String(opt.get("template", "meadow"))
	var scaffold: Script = WorldScaffold
	var templates: Dictionary = scaffold.get_script_constant_map().get("TEMPLATES", {"meadow": ""})
	if not templates.has(template):
		printerr("usage: new <folder> [--id id] [--title title] [--author name] [--template meadow|beach|interior|forest|town] [--from-brief brief.json]")
		printerr("unknown template; this browser has: %s" % ", ".join(PackedStringArray(templates.keys()))
			+ ("" if templates.size() > 1 else " (update the iamar browser for beach, interior, forest and town)"))
		quit(2)
		return
	# A browser older than the templates has the four-argument create only.
	var result: Dictionary = WorldScaffold.create(dir, id, title, author) if template == "meadow" \
		else scaffold.callv("create", [dir, id, title, author, template])
	if not result.ok:
		if result.error_kind == "validation":
			printerr("the scaffold does not validate (please report):\n  " + "\n  ".join(result.errors))
		else:
			printerr("\n".join(result.errors))
		quit(int(result.exit_code))
		return
	dir = String(result.path)
	if template != "meadow":
		print("TEMPLATE %s: %s" % [template, templates[template]])
	if not brief_plan.is_empty():
		var code := _lay_out(dir, brief_plan, scaffold)
		if code != 0:
			quit(code)
			return
	print("NEW %s (%s) in %s - next: edit scene.json, then `iamar-world validate %s`" % [id, title, dir, args[0]])
	quit(0)


static func _abs(p: String) -> String:
	return KitLoop.absolute_path(p)


static func _read_brief(path: String, template_override: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {"error": "no brief at %s (write it with the interview, kit/interview/PROTOCOL.md)" % path}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if parsed == null:
		return {"error": "%s is not valid JSON" % path.get_file()}
	return FromBrief.plan(parsed, template_override)


static func _read_json(path: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}


static func _write_json(path: String, data: Dictionary) -> bool:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string(JSON.stringify(data, "  ") + "\n")
	f.close()
	return true


## The template's ground height at x, z (the browser builds the same terrain).
static func _ground(scaffold: Script, template: String) -> Callable:
	if template == "beach" and "beach_height" in _static_names(scaffold):
		return func(x: float, z: float) -> float: return float(scaffold.call("beach_height", x, z))
	if template == "forest" and "forest_height" in _static_names(scaffold):
		var noise: Variant = scaffold.call("_forest_noise")
		return func(x: float, z: float) -> float: return float(scaffold.call("forest_height", noise, x, z))
	return func(_x: float, _z: float) -> float: return 0.0


static func _static_names(scaffold: Script) -> PackedStringArray:
	var names := PackedStringArray()
	for m in scaffold.get_script_method_list():
		names.append(String(m.name))
	return names


## Builds the brief's house and places it and the rest of the layout in the new folder,
## then checks the folder still opens. Returns the exit code.
static func _lay_out(dir: String, brief_plan: Dictionary, scaffold: Script) -> int:
	var template := String(brief_plan.template)
	print("BRIEF template %s zones %s%s" % [template, ",".join(PackedStringArray(brief_plan.zones)) if not (brief_plan.zones as Array).is_empty() else "none",
		(" house %s style %s" % [brief_plan.house.rooms, brief_plan.house.style]) if not (brief_plan.house as Dictionary).is_empty() else ""])
	var house := {}
	if not (brief_plan.house as Dictionary).is_empty():
		var out := dir.path_join("assets/house.glb")
		var code := KitHouseRooms.export(out, brief_plan.house)
		if code != 0:
			printerr("brief: the house could not be built; change the rooms in brief.layout.zones")
			return code
		var info := _read_json(out.get_basename() + ".rooms.json")
		if info.is_empty():
			printerr("brief: the house was built but its rooms sidecar is missing")
			return 1
		house = {"asset": "assets/house.glb", "info": info}
	var manifest := _read_json(dir.path_join("manifest.json"))
	var scene := _read_json(dir.path_join("scene.json"))
	if manifest.is_empty() or scene.is_empty():
		printerr("brief: could not reread the new manifest.json/scene.json")
		return 1
	var lines := FromBrief.apply(scene, manifest, brief_plan, house, _ground(scaffold, template))
	if not _write_json(dir.path_join("manifest.json"), manifest) or not _write_json(dir.path_join("scene.json"), scene):
		printerr("brief: could not save the laid-out manifest.json/scene.json")
		return 1
	for line in lines:
		print(line)
	for note in brief_plan.notes:
		print("NOTE " + String(note))
	var pkg := WorldPackage.open(dir)
	if not pkg.ok:
		printerr("the laid-out world does not validate (please report, with the brief):\n  " + "\n  ".join(pkg.errors))
		return 1
	return 0
