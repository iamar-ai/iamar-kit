extends SceneTree
## Evidence shots for an internal task (not part of the test): a furnished house seen from above with
## everything over 2.3 m above a floor cut away, one picture per floor, and a view into the first room of each type from its doorway.
##   SHOT_GLB=house.glb SHOT_OUT=dir godot --rendering-driver opengl3 -s shot.gd   (needs a display)

func _init() -> void:
	var glb := OS.get_environment("SHOT_GLB")
	var out := OS.get_environment("SHOT_OUT")
	var side: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(glb.get_basename() + ".rooms.json"))
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	doc.append_from_file(glb, st)
	var house := doc.generate_scene(st)
	root.add_child(house)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.25, 0.3, 0.35)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.85, 0.85, 0.85)
	env.ambient_light_energy = 0.9
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-60, 30, 0)
	root.add_child(sun)
	for l: Dictionary in side.get("lights", []):
		var o := OmniLight3D.new()
		o.position = Vector3(l.position[0], l.position[1], l.position[2])
		o.omni_range = float(l.range)
		o.light_energy = float(l.energy)
		o.light_color = Color(String(l.color))
		root.add_child(o)
	root.size = Vector2i(1280, 960)
	var cam := Camera3D.new()
	root.add_child(cam)
	cam.current = true
	var length: float = side.size[0]
	var depth: float = side.size[1]
	for f in int(side.floors):
		var y := 0.15 + f * float(side.storey)
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = maxf(length, depth * 4.0 / 3.0) * 1.05 * 0.75
		cam.position = Vector3(0, y + 2.3, 0)
		cam.rotation_degrees = Vector3(-90, 0, 0)
		cam.near = 0.05
		cam.far = 3.0
		await _save(out.path_join("plan_floor_%d.png" % f))
	# into the first room of each type from its doorway
	var seen := {}
	for room: Dictionary in side.rooms:
		if not seen.has(room.type):
			seen[room.type] = true
			var d: Array = room.door
			var r: Array = room.rect
			var c := Vector3((r[0] + r[2]) / 2.0, float(d[1]) + 1.6, (r[1] + r[3]) / 2.0)
			cam.projection = Camera3D.PROJECTION_PERSPECTIVE
			cam.fov = 80
			cam.near = 0.05
			cam.far = 50
			var from := Vector3(d[0], float(d[1]) + 1.6, d[2]) + (Vector3(d[0], 0, d[2]) - Vector3(c.x, 0, c.z)).normalized() * 0.5
			cam.position = from
			cam.look_at(c - Vector3(0, 0.6, 0))
			await _save(out.path_join("%s_from_door.png" % room.type))
	quit(0)


func _save(path: String) -> void:
	for i in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(path)
	print("SHOT ", path)
