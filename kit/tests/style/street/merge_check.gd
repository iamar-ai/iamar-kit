extends SceneTree
## Imports .glb files as the browser does (GLTFDocument; vertex colours on, as
## the iamar browser source (not public) scripts/worlds/world_package.gd _glb_vertex_colours) and groups
## their surfaces by the browser's merge_static key (scripts/kit/world_techniques.gd
## _mat_key, copied here). Prints MERGE_CHECK surfaces=<draws before> merged_draws=<after>.
##   godot --headless --path <dir with this file and a project.godot> --script merge_check.gd -- a.glb ...

func _mat_key(m: Material) -> String:
	var b := m as BaseMaterial3D
	if b == null:
		return "obj%d" % (m.get_instance_id() if m else 0)
	var t := b.albedo_texture.get_rid().get_id() if b.albedo_texture else 0
	var nt := b.normal_texture.get_rid().get_id() if b.normal_enabled and b.normal_texture else 0
	return "%s/%d/%d/%d/%d/%d/%d/%.2f/%.2f/%d/%.2f" % [b.albedo_color.to_html(), t, nt, b.transparency, b.cull_mode,
		b.shading_mode, int(b.vertex_color_use_as_albedo), b.roughness, b.metallic, b.texture_filter, b.alpha_scissor_threshold]


func _init() -> void:
	var keys := {}
	var surfaces := 0
	var roots: Array[Node] = []
	for path in OS.get_cmdline_user_args():
		var doc := GLTFDocument.new()
		var state := GLTFState.new()
		if doc.append_from_file(path, state) != OK:
			print("MERGE_CHECK_FAIL cannot read ", path)
			quit(1)
			return
		var root := doc.generate_scene(state)
		roots.append(root)
		for mi in root.find_children("*", "MeshInstance3D", true, false):
			var mesh: Mesh = mi.mesh
			for s in mesh.get_surface_count():
				var m: Material = mi.get_surface_override_material(s)
				if m == null:
					m = mesh.surface_get_material(s)
				var b := m as BaseMaterial3D
				if b and mesh.surface_get_format(s) & Mesh.ARRAY_FORMAT_COLOR != 0:
					b.vertex_color_use_as_albedo = true
				surfaces += 1
				keys[_mat_key(m)] = true
	print("MERGE_CHECK surfaces=%d merged_draws=%d" % [surfaces, keys.size()])
	for r in roots:
		r.free()
	quit(0)
