extends SceneTree
## Real WorldAddressBook + WorldSource; no custody stub or private-path authority.
var checks := 0
var failures := 0
var _reader: ZIPReader

func check(value: bool, label: String) -> void:
	checks += 1
	if not value:
		failures += 1
		printerr("FAIL " + label)

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var path := OS.get_cmdline_user_args()[0]
	var dir := path.get_base_dir()
	_hold_source(path)
	# Observe after the allocating helper returns: a VM call temporary is also
	# an actual owner, not evidence that WorldAddressBook leaked a weak hold.
	check(WorldAddressBook.protected_copy(path), "retained ZIPReader independently holds custody")
	check(WorldAddressBook.sweep(dir) == 0, "retained reader prevents deletion")
	_reader = null
	check(not WorldAddressBook.protected_copy(path), "custody settles after last actual owner expires")
	check(WorldAddressBook.sweep(dir) == 1 and not FileAccess.file_exists(path), "retired copy deleted only after settlement")
	var direct_path := dir.path_join("verified-" + "b".repeat(64) + ".iamar")
	_direct_zip(direct_path)
	check(not WorldAddressBook.protected_copy(direct_path), "direct ZIP owners expire normally")
	print("TIER_CUSTODY_PASS ", checks, " checks, ", failures, " failures")
	quit(0 if failures == 0 else 1)

func _hold_source(path: String) -> void:
	var dir := path.get_base_dir()
	var source := WorldSource.open(path)
	check(source.ok() and source.is_zip, "public ZIP still opens")
	check(source.read("manifest.json").get_string_from_utf8() == "{}", "ZIP bytes unchanged")
	check(WorldAddressBook.protected_copy(path), "source and reader acquire real custody")
	check(WorldAddressBook.sweep(dir) == 0 and FileAccess.file_exists(path), "sweep preserves live source")
	_reader = source._zip
	source.close()
	check(WorldAddressBook.protected_copy(path), "close alone does not refund actual owners")

func _direct_zip(path: String) -> void:
	# _open_zip is also called directly by trusted callers. It must still hold
	# both actual owners, independent of the static factory's guard.
	var direct := WorldSource.new()
	direct._open_zip(path)
	check(direct.ok() and direct._zip != null and WorldAddressBook.protected_copy(path), "direct ZIP route protects actual readers")
	direct.close()
