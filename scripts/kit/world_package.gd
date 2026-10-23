extends SceneTree
## `iamar-world package` / `pack`: the self-contained release-binary workflow.
## Lower tiers are rebuilt first when declared, then the exact folder is signed and
## packed.  Child tools are the same embedded scripts and the same executable; no
## Godot editor, shell, Python or source checkout is involved.


func _initialize() -> void:
	var args := KitLoop.user_args()
	if args.size() < 4:
		printerr("usage: package <folder> <out.iamar> <key> <signer name>")
		quit(2)
		return
	if not args[1].ends_with(".iamar"):
		printerr("package output must end in lowercase .iamar for browser import")
		quit(2)
		return
	var folder := KitLoop.absolute_path(args[0])
	if _declares_tiers(folder) and OS.get_environment("IAMAR_NO_TIERS") == "":
		print("TIERS building the lower tiers of %s (IAMAR_NO_TIERS=1 skips this)" % args[0])
		var code := _tool("res://scripts/kit/world_tiers_build.gd", PackedStringArray([folder]))
		if code != 0:
			printerr("TIERS failed: fix the tier above (or its budgets) before packaging")
			quit(code)
			return
	# Child processes do not inherit the dispatcher's --cwd argument. Resolve every
	# path at this boundary so source-editor and native-export runs behave identically.
	var pack_args := PackedStringArray(["pack", folder, KitLoop.absolute_path(args[1]),
		KitLoop.absolute_path(args[2]), args[3]])
	var packed := _tool("res://scripts/kit/world_sign.gd", pack_args)
	if packed != 0:
		quit(packed)
		return
	if OS.get_environment("IAMAR_NO_TECHNIQUES") == "":
		_tool("res://scripts/kit/world_techniques_check.gd", PackedStringArray([folder]))
	quit(0)


func _declares_tiers(folder: String) -> bool:
	var value: Variant = JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("manifest.json")))
	return value is Dictionary and value.has("tiers")


func _tool(script: String, args: PackedStringArray) -> int:
	var child := PackedStringArray(["--headless", "--audio-driver", "Dummy"])
	# An editor/source invocation needs its project path; an exported executable has
	# its embedded PCK and must not depend on a source directory.
	if OS.has_feature("editor"):
		child.append_array(["--path", ProjectSettings.globalize_path("res://")])
	child.append_array(["--", "--kit-script", script])
	child.append_array(args)
	var output := []
	var code := OS.execute(OS.get_executable_path(), child, output, true)
	if not output.is_empty():
		print("".join(output).strip_edges())
	if code == -1:
		printerr("ERROR: could not start embedded kit tool %s with %s" % [script, OS.get_executable_path()])
	return code
