extends SceneTree
## The city's own objects in the catalogue (kit/catalog/sources/city_models.json, files in
## kit/catalog/assets/) load in a sample world through the browser's production path
## (WorldPackage.open + build) and keep what they do there:
##   - every model opens, with the triangles and size its catalogue record states;
##   - props keep their collision (the GLB's own OMI physics body, or scene.json "collision");
##   - skinned creatures (dragons) keep their skeleton;
##   - every creature kind in sources/procedural.json wanders and does what its entry
##     declares (graze, sniff, flee from the player, float on or swim under the water...);
##   - trees placed with "sway": true sway in the browser's shared wind.
## Run from an the iamar browser source (not public) checkout (headless, no display):
##   godot --headless --path <iamar checkout> -s <iamar-kit>/kit/tests/catalog/city_assets_test.gd
## (IAMAR_KIT_ROOT=<iamar-kit> when the script is copied elsewhere; CITY_ASSETS_TEST_TMP: scratch folder)

var _checks := 0
var _failures := 0
var _tmp := ""
var _kit := ""


func _check(what: String, cond: bool, detail := "") -> void:
	_checks += 1
	if cond:
		print("PASS ", what)
	else:
		_failures += 1
		print("FAIL ", what, " ", detail)


func _init() -> void:
	# this file is <kit repo>/kit/tests/catalog/city_assets_test.gd
	_kit = (get_script() as Script).resource_path.get_base_dir().get_base_dir().get_base_dir()
	if OS.get_environment("IAMAR_KIT_ROOT") != "":
		_kit = OS.get_environment("IAMAR_KIT_ROOT").path_join("kit")
	_tmp = OS.get_environment("CITY_ASSETS_TEST_TMP")
	if _tmp == "":
		_tmp = OS.get_cache_dir().path_join("city_assets_test")
	_rm(_tmp)
	DirAccess.make_dir_recursive_absolute(_tmp)
	_run.call_deferred()


func _run() -> void:
	var src = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/sources/city_models.json")))
	_check("city_models.json readable at " + _kit, src is Dictionary and (src.models as Array).size() > 0)
	if not src is Dictionary:
		return _end()
	var models: Array = src.models
	# the insects (sources/insects.json, same row format) ride along: each loops its "play" clip
	var ins = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/sources/insects.json")))
	_check("insects.json readable", ins is Dictionary and (ins.models as Array).size() > 0)
	if ins is Dictionary:
		models = models + (ins.models as Array)
	# the furniture, crops and flora exported by export_city_pieces.gd (sources/city_pieces.json)
	var pcs = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/sources/city_pieces.json")))
	_check("city_pieces.json readable", pcs is Dictionary and (pcs.models as Array).size() > 0)
	if pcs is Dictionary:
		models = models + (pcs.models as Array)
	# houses per quarter and landmarks, re-centred by import_city_buildings.py (sources/city_buildings.json)
	var bld = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/sources/city_buildings.json")))
	_check("city_buildings.json readable", bld is Dictionary and (bld.models as Array).size() > 0)
	if bld is Dictionary:
		models = models + (bld.models as Array)
	# closed variants of the open-sided houses (close_open_sides.py, sources/city_buildings_closed.json)
	var cls = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/sources/city_buildings_closed.json")))
	_check("city_buildings_closed.json readable", cls is Dictionary and (cls.models as Array).size() > 0)
	if cls is Dictionary:
		models = models + (cls.models as Array)
	# room interiors moved by their shell's offset (import_city_interiors.py, sources/city_interiors.json)
	var rms = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/sources/city_interiors.json")))
	_check("city_interiors.json readable", rms is Dictionary and (rms.models as Array).size() > 0)
	if rms is Dictionary:
		models = models + (rms.models as Array)
	# the griffin (LOD0-2), dragon breeds and giant eagle rebuilt by export_city_mounts.gd (sources/city_mounts.json)
	var mts = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/sources/city_mounts.json")))
	_check("city_mounts.json readable", mts is Dictionary and (mts.models as Array).size() > 0)
	if mts is Dictionary:
		models = models + (mts.models as Array)
	# the harbour set (sources/harbour.json, an internal task): models in the same row format, plus sounds
	# (kind audio) that go into scene.json sounds below
	var hb = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/sources/harbour.json")))
	_check("harbour.json readable", hb is Dictionary and (hb.models as Array).size() > 0)
	var sounds := []
	for r in (hb.models if hb is Dictionary else []):
		if String(r.get("kind", "")) == "audio":
			sounds.append(r)
		else:
			models.append(r)
	# the coastal and home set (sources/coastal.json, an internal task): the beach-house brief's objects
	var cs = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/sources/coastal.json")))
	_check("coastal.json readable", cs is Dictionary and (cs.models as Array).size() > 0)
	if cs is Dictionary:
		models = models + (cs.models as Array)
	var w := _tmp.path_join("w_city")
	DirAccess.make_dir_recursive_absolute(w.path_join("assets"))
	var objects := []
	var tri_total := 0
	for i in models.size():
		var r: Dictionary = models[i]
		var rel := "assets/" + String(r.file).get_file()
		var bytes := FileAccess.get_file_as_bytes(_kit.path_join("catalog/assets").path_join(String(r.file)))
		_put(w.path_join(rel), bytes)
		tri_total += int(r.triangles)
		# a grid 60 m apart: the dragons are big
		var o := {"id": "m%02d" % i, "asset": rel, "position": [(i % 8) * 60.0, 0, (i / 8) * 60.0]}
		if float(r.get("place_scale", 1.0)) != 1.0:
			o.scale = float(r.place_scale)   # as the catalogue's use line says
		if String(r.get("collision", "none")) != "none" and not bool(r.get("physics_body", false)):
			o.collision = String(r.collision)
		if r.has("play"):
			o.animation = String(r.play)   # as the catalogue's use line says
		if String(r.category) == "tree":
			o.sway = true   # as the catalogue's use line says
		objects.append(o)
	# the creature kinds built by kind (sources/procedural.json): each herd's declared behaviours are checked below
	var proc = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/sources/procedural.json")))
	_check("procedural.json readable", proc is Dictionary and (proc.creatures as Array).size() > 0)
	var declared := {}   # kind -> behaviours
	var creatures := []
	for c in (proc.creatures if proc is Dictionary else []):
		declared[String(c.kind)] = c.get("behaviours", [])
		creatures.append({"id": c.kind, "kind": c.kind, "position": [creatures.size() * 30.0, 0, -40.0], "count": 2, "wander_radius": 6, "seed": 7})
	var m := {"format": "iamar-world", "format_version": 0, "id": "city_assets_test", "name": "City assets test",
		"author": {"name": "kit test"}, "version": "1.0.0", "api_version": "0.1",
		"features": ["objects", "creatures"],
		"budgets": {"triangles": tri_total + 100000, "objects": objects.size() + 2 * creatures.size() + 16, "texture_size": 4096,
			"texture_bytes": 512 << 20, "package_bytes": 256 << 20}}
	# each sound as its catalogue use line says: copied to audio/, its scene.json sounds entry
	var snd_list := []
	DirAccess.make_dir_recursive_absolute(w.path_join("audio"))
	for r in sounds:
		var d: Dictionary = (r.sound as Dictionary).duplicate()
		d.file = "audio/" + String(r.file).get_file()
		_put(w.path_join(d.file), FileAccess.get_file_as_bytes(_kit.path_join("catalog/assets").path_join(String(r.file))))
		snd_list.append(d)
	if not snd_list.is_empty():
		m.features.append("sounds")
	var sc := {"format": "iamar-scene", "format_version": 0, "environment": {"sun": {"enabled": false}},
		"terrain": {"type": "none"}, "objects": objects, "creatures": creatures, "sounds": snd_list}
	_put(w.path_join("manifest.json"), JSON.stringify(m, "  ", false).to_utf8_buffer())
	_put(w.path_join("scene.json"), JSON.stringify(sc, "  ", false).to_utf8_buffer())

	var pkg := WorldPackage.open(w)
	_check("the sample world with %d city models and %d creature kinds opens" % [models.size(), creatures.size()], pkg.ok, "\n".join(pkg.errors))
	if not pkg.ok:
		return _end()
	var holder := Node3D.new()
	root.add_child(holder)
	var built: Node3D = pkg.build(holder)
	for f in 3:
		await physics_frame

	var objs := built.find_child("Objects", true, false)
	var colliders := built.find_child("Colliders", true, false)
	var report := []
	for i in models.size():
		var r: Dictionary = models[i]
		var label := "%s (%s)" % [r.name, r.file]
		var inst := objs.get_node_or_null("m%02d" % i) as Node3D if objs else null
		if inst == null:
			_check(label + " placed", false)
			continue
		var tris := 0
		var box := AABB()
		var first := true
		for mi in inst.find_children("*", "MeshInstance3D", true, false):
			var mesh: Mesh = (mi as MeshInstance3D).mesh
			if mesh == null:
				continue
			tris += WorldPackage.mesh_triangles(mesh)
			var b: AABB = (inst.global_transform.affine_inverse() * (mi as MeshInstance3D).global_transform) * mesh.get_aabb()
			box = b if first else box.merge(b)
			first = false
		var want := int(r.triangles)
		var tri_ok := tris == want
		var size: Array = r.get("size", [])
		var size_ok := size.size() == 3 and box.size.distance_to(Vector3(size[0], size[1], size[2])) <= maxf(0.15, box.size.length() * 0.05)
		# the GLB's own physics body sits inside the object; scene.json "collision" adds
		# <id>_box / <id>_mesh under the world's Colliders group, scaled with the object
		var body := inst.find_children("*", "CollisionObject3D", true, false).size()
		var scaled_ok := true
		for suffix in ["_box", "_mesh"]:
			var c := colliders.get_node_or_null("m%02d%s" % [i, suffix]) if colliders else null
			if c is CollisionObject3D:
				body += 1
				var shape := ((c as Node).get_child(0) as CollisionShape3D).shape
				if shape is BoxShape3D:
					var want_box := box.size * float(r.get("place_scale", 1.0))
					scaled_ok = (shape as BoxShape3D).size.distance_to(want_box) <= maxf(0.15, want_box.length() * 0.05)
		var wants_body := String(r.get("collision", "none")) != "none" or bool(r.get("physics_body", false))
		var skel_ok := true
		if bool(r.get("skinned", false)):
			var sk := inst.find_children("*", "Skeleton3D", true, false)
			skel_ok = sk.size() > 0 and (sk[0] as Skeleton3D).get_bone_count() > 0
		var ok := tri_ok and size_ok and (body > 0 or not wants_body) and skel_ok and scaled_ok
		_check(label + " loads with its triangles, size%s%s" % [", collision" if wants_body else "", ", skeleton" if bool(r.get("skinned", false)) else ""],
			ok, "tris %d/%d size %s/%s bodies %d skeleton %s collider at place scale %s" % [tris, want, box.size, size, body, skel_ok, scaled_ok])
		report.append("%s tris=%d size=%.2fx%.2fx%.2f bodies=%d" % [r.file, tris, box.size.x, box.size.y, box.size.z, body])

	# insects: the world loops the clip named in "animation", and it moves the wings
	for i in models.size():
		var r: Dictionary = models[i]
		if not r.has("play") or r.has("moves"):
			continue
		var inst := objs.get_node_or_null("m%02d" % i) if objs else null
		var ap := inst.find_child("AnimationPlayer", true, false) as AnimationPlayer if inst else null
		var wing := inst.find_child("WingFR", true, false) as Node3D if inst else null
		var clips_ok := ap != null and Array(ap.get_animation_list()) == Array(r.animations)
		var playing := ap != null and ap.is_playing() and ap.current_animation == String(r.play) \
			and ap.get_animation(String(r.play)).loop_mode == Animation.LOOP_LINEAR
		# the widest swing over one pass of the clip at 60 fps (as imported: glTF clips come
		# in resampled at 30 fps, which erases strokes faster than 15 Hz)
		var moved := 0.0
		if playing and wing:
			var q0 := wing.quaternion
			for step in ceili(ap.current_animation_length * 60.0):
				ap.advance(1.0 / 60.0)
				moved = maxf(moved, q0.angle_to(wing.quaternion))
		_check("%s loops its clip \"%s\" and beats its wings" % [r.name, r.play], clips_ok and playing and moved > 0.3,
			"clips %s/%s playing %s wing moved %.3f rad" % [ap.get_animation_list() if ap else [], r.animations, playing, moved])

	# harbour models: the world loops the "play" clip, and every clip in "moves" swings the node it
	# names (the boat heaves, the bell swings, the gull's head turns and its wings beat)
	for i in models.size():
		var r: Dictionary = models[i]
		if not r.has("moves"):
			continue
		var inst := objs.get_node_or_null("m%02d" % i) if objs else null
		var ap := inst.find_child("AnimationPlayer", true, false) as AnimationPlayer if inst else null
		var clips_ok := ap != null and Array(ap.get_animation_list()) == Array(r.animations)
		var looping := ap != null and ap.is_playing() and ap.current_animation == String(r.play) \
			and ap.get_animation(String(r.play)).loop_mode == Animation.LOOP_LINEAR
		for clip in r.moves:
			var node := inst.find_child(String(r.moves[clip][0]), true, false) as Node3D if inst else null
			var least := float(r.moves[clip][1])
			var moved := 0.0
			if ap and node and ap.has_animation(clip):
				ap.play(clip)
				ap.seek(0.0, true)
				var q0 := node.quaternion
				var p0 := node.position
				for step in ceili(ap.get_animation(clip).length * 60.0):
					ap.advance(1.0 / 60.0)
					moved = maxf(moved, maxf(q0.angle_to(node.quaternion), p0.distance_to(node.position)))
			_check("%s plays its clip \"%s\" and moves %s" % [r.name, clip, r.moves[clip][0]],
				clips_ok and looping and node != null and moved >= least,
				"clips %s/%s looping %s moved %.3f (least %.3f)" % [ap.get_animation_list() if ap else [], r.animations, looping, moved, least])

	# sounds: each loads and plays in the world with its length, loop flag and position
	var snd_group := built.find_child("Sounds", true, false)
	for r in sounds:
		var d: Dictionary = r.sound
		var n := snd_group.get_node_or_null(String(d.id)) if snd_group else null
		var stream: AudioStream = n.get("stream") if n else null
		var len_ok := stream != null and absf(stream.get_length() - float(r.audio.seconds)) < 0.05
		var loop_ok := stream is AudioStreamOggVorbis and (stream as AudioStreamOggVorbis).loop == bool(d.get("loop", true))
		var where_ok := (n is AudioStreamPlayer3D and (n as Node3D).position.distance_to(Vector3(d.position[0], d.position[1], d.position[2])) < 0.01) \
			if d.has("position") else n is AudioStreamPlayer
		if n and not bool(d.get("autoplay", true)):
			n.call("play")   # a one-shot (the bell) is played by a quest or a script
		await process_frame
		var playing := n != null and bool(n.call("is_playing"))
		_check("%s sound loads and plays in the world (%s, %.1f s)" % [r.name, "positional" if d.has("position") else "ambient", float(r.audio.seconds)],
			len_ok and loop_ok and where_ok and playing,
			"node %s length %s loop %s where %s playing %s" % [n, stream.get_length() if stream else -1.0, loop_ok, where_ok, playing])

	# creatures wander: positions change over simulated time
	var herds := []
	for n in built.find_children("*", "Node3D", true, false):
		if n is WorldCreatures:
			herds.append(n)
	_check("%d creature herds built" % creatures.size(), herds.size() == creatures.size(), str(herds.size()))
	for h in herds:
		var c := h as WorldCreatures
		var before := []
		for a in c.animals:
			before.append(a.pos)
		for step in 600:   # 30 s at 20 Hz
			c._process(0.05)
		var moved := 0
		for j in c.animals.size():
			if (c.animals[j].pos as Vector3).distance_to(before[j]) > 0.3:
				moved += 1
		var inside := true
		for a in c.animals:
			var p: Vector3 = a.pos
			inside = inside and Vector2(p.x - c.center.x, p.z - c.center.z).length() <= c.radius + 0.5
		_check("%s wander inside their radius" % c.kind, moved > 0 and inside, "moved %d of %d, inside %s" % [moved, c.animals.size(), inside])
		# idle and gait behaviours the catalogue names, sampled over 60 s at 20 Hz: the head goes
		# down (graze, nibble, peck) and the gait phase advances while moving (the bunny's hop is
		# |sin(gait phase)| lifting the body; the headless renderer does not keep MultiMesh
		# transforms, so the phase is what can be read)
		var head_min := 0.0
		var step_before := []
		var body_y := []   # body height relative to the herd's y (the water surface for swimmers)
		for a in c.animals:
			step_before.append(float(a.step))
		for step in 1200:
			c._process(0.05)
			for j in c.animals.size():
				head_min = minf(head_min, float(c.animals[j].head))
				if step % 40 == 0:
					body_y.append(c.pose_of(j, "body").origin.y - c.center.y)
		var gait := 0.0
		for j in c.animals.size():
			gait = maxf(gait, float(c.animals[j].step) - float(step_before[j]))
		var does: Array = declared.get(c.kind, [])
		if does.any(func(b): return b in ["graze", "nibble", "peck"]):
			_check("BEHAVIOUR %s head goes down when idle (graze / nibble / peck)" % c.kind, head_min < -0.5, "lowest head angle %.2f" % head_min)
		if does.any(func(b): return b in ["sniff", "dabble"]):
			_check("BEHAVIOUR %s head dips when idle (sniff / dabble)" % c.kind, head_min < -0.3, "lowest head angle %.2f" % head_min)
		_check("BEHAVIOUR %s gait phase advances while moving (hop / walk)" % c.kind, gait > 1.0, "phase advanced %.2f" % gait)
		if "float" in does:
			_check("BEHAVIOUR %s floats on the water surface (position y)" % c.kind, body_y.all(func(y): return absf(y) < 0.15), "body heights %s" % [body_y.slice(0, 4)])
		if "swim" in does:
			_check("BEHAVIOUR %s swims below the water surface (position y)" % c.kind, body_y.all(func(y): return y < -0.1 and y > -1.0), "body heights %s" % [body_y.slice(0, 4)])
		# fleeing: a player standing in the herd scatters it (deer, wolves); other kinds stay calm
		var player := Node3D.new()
		root.add_child(player)
		player.global_position = c.global_transform * c.center
		c.threat = player
		var d0 := 0.0
		for a in c.animals:
			d0 += Vector2(a.pos.x - c.center.x, a.pos.z - c.center.z).length()
		var fled := {}
		for step in 60:   # 3 s
			c._process(0.05)
			for j in c.animals.size():
				if c.animals[j].fleeing:
					fled[j] = true
		var d1 := 0.0
		for a in c.animals:
			d1 += Vector2(a.pos.x - c.center.x, a.pos.z - c.center.z).length()
		c.threat = null
		player.queue_free()
		if "flee" in does:
			_check("BEHAVIOUR %s runs from the player" % c.kind, fled.size() == c.animals.size() and d1 > d0 + 4.0 * c.animals.size(),
				"%d of %d fled, mean distance %.1f -> %.1f m" % [fled.size(), c.animals.size(), d0 / c.animals.size(), d1 / c.animals.size()])
		else:
			_check("%s stays calm near the player (declares no flee)" % c.kind, fled.is_empty(), "%d fled" % fled.size())

	# trees: "sway" puts them in the shared wind (WindField.adopt_tree: the wind_plant shader in
	# tree mode; the city's own foliage.gdshader cannot travel in a GLB)
	for i in models.size():
		if String(models[i].category) != "tree":
			continue
		var inst := objs.get_node_or_null("m%02d" % i)
		var sway := false
		for mi in inst.find_children("*", "MeshInstance3D", true, false):
			var mesh: Mesh = (mi as MeshInstance3D).mesh
			for s in (mesh.get_surface_count() if mesh else 0):
				var sm := mesh.surface_get_material(s) as ShaderMaterial
				if sm and sm.shader and sm.shader.resource_path.contains("wind_plant") and int(sm.get_shader_parameter("sway_mode")) == 1:
					sway = true
		_check("BEHAVIOUR %s sways in the shared wind" % models[i].name, sway)

	# vertex colour: the city's objects are painted by COLOR_0, which glTF multiplies into
	# the base colour; Godot's runtime GLTFDocument leaves it off, so before the iamar browser source (not public)
	# d7d034da (an internal task) they drew white. From then on WorldPackage turns it on and reads
	# these Godot-made files as sRGB; on an older browser this stays a KNOWN-GAP line.
	var browser_fixed := (load("res://scripts/worlds/world_package.gd") as Script).get_script_method_list() 		.any(func(mm): return mm.name == "_glb_vertex_colours")
	var vc_files := 0
	var vc_shown := 0
	var vc_srgb := 0
	for i in models.size():
		var inst := objs.get_node_or_null("m%02d" % i) if objs else null
		var has_vc := false
		var shown := false
		var srgb := false
		for mi in (inst.find_children("*", "MeshInstance3D", true, false) if inst else []):
			var mesh: Mesh = (mi as MeshInstance3D).mesh
			for s in (mesh.get_surface_count() if mesh else 0):
				if mesh.surface_get_format(s) & Mesh.ARRAY_FORMAT_COLOR:
					has_vc = true
					var mat := mesh.surface_get_material(s)
					if (mi as MeshInstance3D).get_surface_override_material(s) != null:
						mat = (mi as MeshInstance3D).get_surface_override_material(s)
					# a swayed tree carries the flag into its wind material (use_vcol)
					if mat is ShaderMaterial:
						shown = shown or bool((mat as ShaderMaterial).get_shader_parameter("use_vcol"))
						srgb = srgb or bool((mat as ShaderMaterial).get_shader_parameter("vcol_srgb"))
					else:
						shown = shown or (mat is BaseMaterial3D and (mat as BaseMaterial3D).vertex_color_use_as_albedo)
						srgb = srgb or (mat is BaseMaterial3D and (mat as BaseMaterial3D).vertex_color_is_srgb)
		vc_files += 1 if has_vc else 0
		vc_shown += 1 if has_vc and shown else 0
		vc_srgb += 1 if has_vc and shown and srgb else 0
	if browser_fixed:
		_check("every vertex-painted model draws its colours in the package world, read as sRGB",
			vc_files > 0 and vc_shown == vc_files and vc_srgb == vc_files, "%d of %d drawn, %d sRGB" % [vc_shown, vc_files, vc_srgb])
		# the issue's own repro: rabbit.glb through the browser's decode
		var dec: Dictionary = WorldPackage._glb_decode(FileAccess.get_file_as_bytes(_kit.path_join("catalog/assets/creatures/rabbit.glb")))
		var rab := dec.get("scene") is Node
		var rab_n := 0
		for mi in ((dec.scene as Node).find_children("*", "MeshInstance3D", true, false) if rab else []):
			var mesh: Mesh = (mi as MeshInstance3D).mesh
			for s in (mesh.get_surface_count() if mesh else 0):
				if mesh.surface_get_format(s) & Mesh.ARRAY_FORMAT_COLOR:
					rab_n += 1
					var bm := mesh.surface_get_material(s) as BaseMaterial3D
					rab = rab and bm != null and bm.vertex_color_use_as_albedo and bm.vertex_color_is_srgb
		_check("rabbit.glb decoded by WorldPackage has vertex colours on (sRGB)", rab and rab_n > 0, "%d painted surfaces" % rab_n)
		if dec.get("scene") is Node:
			(dec.scene as Node).free()
	else:
		print("KNOWN-GAP vertex colours drawn in the package world: %d of %d vertex-painted models (browser before the iamar browser source (not public) d7d034da)" % [vc_shown, vc_files])

	for line in report:
		print("MEASURED ", line)
	holder.queue_free()
	_end()


func _end() -> void:
	print("CITY ASSETS TEST %d passed, %d failed" % [_checks - _failures, _failures])
	_rm(_tmp)
	quit(1 if _failures else 0)


func _put(p: String, b: PackedByteArray) -> void:
	var f := FileAccess.open(p, FileAccess.WRITE)
	f.store_buffer(b)
	f.close()


func _rm(p: String) -> void:
	var d := DirAccess.open(p)
	if d == null:
		return
	for f in d.get_files():
		DirAccess.remove_absolute(p.path_join(f))
	for s in d.get_directories():
		_rm(p.path_join(s))
	DirAccess.remove_absolute(p)
