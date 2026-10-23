extends SceneTree
## `iamar-world where`: where this kit's pieces are, for the instructions a builder
## gives their agent: KIT (the folder with AGENT_KIT.md, or its public URL when the
## browser has no kit beside it), DOCS (the format docs) and BROWSER (this binary).


func _initialize() -> void:
	var kit := BuildersGuild.kit_dir()
	# The kit's tools come from iamar-kit.pck; the folder it sits in is the kit (if it has the guide).
	var pack := KitLoop.find_pack()
	if pack != "" and FileAccess.file_exists(pack.get_base_dir().path_join("AGENT_KIT.md")):
		kit = pack.get_base_dir()
	print("KIT ", kit)
	if pack != "":
		print("PACK ", pack)
	print("DOCS ", kit.path_join("docs"))
	print("AGENT_KIT ", kit.path_join("AGENT_KIT.md"))
	print("BROWSER ", OS.get_executable_path())
	quit(0)
