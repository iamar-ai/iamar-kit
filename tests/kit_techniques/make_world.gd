extends SceneTree
## Writes a small world that misses the recipes the kit cannot apply by itself:
## -- <folder> fixed|unfixed. Used by tests/kit_techniques/run.sh.

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var dir: String = args[0]
	var fixed: bool = args[1] == "fixed"
	DirAccess.make_dir_recursive_absolute(dir.path_join("assets"))
	_glb(dir.path_join("assets/tower.glb"), 64, 32, Vector3(3, 12, 3))     # 12 m tall, ~4k triangles
	var m := {"format": "iamar-world", "format_version": 0, "id": "techtest", "name": "Technique test",
		"author": {"name": "test"}, "version": "0.1.0", "api_version": "0.1", "scene": "scene.json",
		"features": ["sky", "sun", "terrain", "objects", "lights"],
		"budgets": {"triangles": 50000, "objects": 50, "texture_size": 1024, "texture_bytes": 16777216,
			"lights": 8, "package_bytes": 64000000, "audio_bytes": 0, "script_bytes": 0}}
	var lights := []
	for i in 3:
		lights.append({"id": "lamp%d" % i, "type": "point", "position": [i * 4, 3, 0], "shadows": not fixed})
	var tower := {"id": "far_tower", "asset": "assets/tower.glb", "position": [0, 0, -120], "collision": "box" if fixed else "mesh"}
	if fixed:
		tower["impostor"] = 50
	var s := {"format": "iamar-scene", "format_version": 0,
		"environment": {"sky": {"type": "procedural"}, "sun": {"enabled": true}},
		"terrain": {"type": "flat", "size": [400, 400]},
		"spawn_points": [{"id": "default", "position": [0, 0, 5]}],
		"objects": [tower], "lights": lights}
	FileAccess.open(dir.path_join("manifest.json"), FileAccess.WRITE).store_string(JSON.stringify(m, "\t"))
	FileAccess.open(dir.path_join("scene.json"), FileAccess.WRITE).store_string(JSON.stringify(s, "\t"))
	quit()


func _glb(path: String, seg: int, rings: int, size: Vector3) -> void:
	var r := Node3D.new()
	var mi := MeshInstance3D.new()
	var c := CylinderMesh.new()
	c.radial_segments = seg
	c.rings = rings
	c.height = size.y
	c.top_radius = size.x * 0.5
	c.bottom_radius = size.x * 0.5
	var am := ArrayMesh.new()
	var arr := c.get_mesh_arrays()
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	for i in v.size():
		v[i].y += size.y * 0.5
	arr[Mesh.ARRAY_VERTEX] = v
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	mi.mesh = am
	r.add_child(mi)
	mi.owner = r
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	doc.append_from_scene(r, st)
	doc.write_to_filesystem(st, path)
	r.free()
