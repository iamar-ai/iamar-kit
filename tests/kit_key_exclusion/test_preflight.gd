extends SceneTree
## Future separately authorized Godot test only. No keygen, sign or pack calls.
## WorldSource.open loads address-book custody dependencies: NOT dependency-isolated.
const Tool = preload("res://scripts/kit/world_sign.gd")
const INERT := "INERT SELECTED KEY PLACEHOLDER: NOT A CRYPTOGRAPHIC KEY\n"

func _init() -> void:
	var base := ProjectSettings.globalize_path("user://key-exclusion-fixture-%d" % OS.get_process_id()).simplify_path()
	# Fresh directory only. Never delete preexisting files. Do not put side
	# effects or required checks inside assert(), which release builds omit.
	if not _check(not DirAccess.dir_exists_absolute(base), "fixture directory already exists"):
		return
	var made := DirAccess.make_dir_recursive_absolute(base.path_join("world/assets"))
	if not _check(made == OK, "cannot create world fixture directory"):
		return
	made = DirAccess.make_dir_recursive_absolute(base.path_join("keys"))
	if not _check(made == OK, "cannot create key fixture directory"):
		return
	var world := base.path_join("world")
	var selected := base.path_join("keys/selected.fixture")
	if not _write(world.path_join("manifest.json"), "{}\n") or not _write(selected, INERT):
		return
	if not _check(Tool._pack_key_is_external(world, selected), "external inert file refused"):
		return
	if not _write(world.path_join("assets/opaque.bin"), INERT):
		return
	if not _check(not Tool._pack_key_is_external(world, selected), "copied inert bytes accepted"):
		return
	if not _check(not Tool._pack_key_is_external(world, world.path_join("assets/opaque.bin")), "in-tree selected file accepted"):
		return
	var removed := DirAccess.remove_absolute(world.path_join("assets/opaque.bin"))
	if not _check(removed == OK, "cannot remove copied inert fixture"):
		return
	if not _write(world.path_join(".ignored.fixture"), INERT):
		return
	if not _check(not Tool._pack_key_is_external(world, world.path_join(".ignored.fixture")), "in-tree ignored selected file accepted"):
		return
	if not _check(Tool._pack_key_is_external(world, selected), "ignored entry unexpectedly captured"):
		return
	if not _check(not Tool._pack_key_is_external(world, base.path_join("missing.fixture")), "missing selected file accepted"):
		return
	var d := DirAccess.open(base)
	if not _check(d != null, "cannot open fixture directory for link test"):
		return
	# An unavailable link fixture is inconclusive, never a passing link test.
	var link_error := d.create_link(world, "world-link")
	if link_error != OK:
		printerr("UNTESTED symlink fixture: ", link_error, "; retained fixtures: ", base)
		quit(2)
		return
	if not _check(not Tool._pack_key_is_external(base.path_join("world-link"), selected), "symlinked root accepted"):
		return
	print("Inert preflight checks finished; inspect retained fixtures: ", base)
	quit(0)

func _check(condition: bool, message: String) -> bool:
	if not condition:
		printerr("FAIL: ", message)
		quit(1)
	return condition

func _write(path: String, value: String) -> bool:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if not _check(f != null, "cannot create inert fixture"):
		return false
	var stored := f.store_string(value)
	var write_error := f.get_error()
	f.close()
	return _check(stored and write_error == OK, "cannot completely write inert fixture")
