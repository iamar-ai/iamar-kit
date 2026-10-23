extends SceneTree
## godot --headless --path pack -s tools/build_pack.gd -- <out.pck> <scripts/kit dir> 
## Writes iamar-kit.pck with every *.gd in the folder under res://scripts/kit/ and nothing
## else (no project.binary, no .godot caches: `--export-pack` adds those, and a mounted pack
## must not replace the browser's own project state).

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 2:
		printerr("usage: build_pack.gd -- <out.pck> <scripts/kit folder>")
		quit(2)
		return
	var out := args[0]
	var dir := args[1]
	var names := PackedStringArray()
	for f in DirAccess.get_files_at(dir):
		if f.ends_with(".gd"):
			names.append(f)
	names.sort()
	if names.is_empty():
		printerr("build_pack: no .gd files in %s" % dir)
		quit(1)
		return
	var packer := PCKPacker.new()
	if packer.pck_start(out) != OK:
		printerr("build_pack: cannot start %s" % out)
		quit(1)
		return
	for f in names:
		if packer.add_file("res://scripts/kit/" + f, dir.path_join(f)) != OK:
			printerr("build_pack: cannot add %s" % f)
			quit(1)
			return
	if packer.flush(false) != OK:
		printerr("build_pack: cannot write %s" % out)
		quit(1)
		return
	print("packed %d scripts" % names.size())
	quit(0)
