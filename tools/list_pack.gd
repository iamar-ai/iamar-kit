extends SceneTree
## godot --headless --path <empty project> -s list_pack.gd -- <pack.pck>
## Mounts a pack and prints "PACK res://path" for every file in it.

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1 or not ProjectSettings.load_resource_pack(args[0]):
		printerr("list_pack: cannot mount %s" % [args])
		quit(2)
		return
	_walk("res://")
	quit(0)


func _walk(dir: String) -> void:
	var d := DirAccess.open(dir)
	if d == null:
		return
	for sub in d.get_directories():
		if sub != ".godot":
			_walk(dir.path_join(sub))
	for f in d.get_files():
		if dir == "res://" and f in ["project.godot", "list_pack.gd"]:
			continue
		print("PACK ", dir.path_join(f))
