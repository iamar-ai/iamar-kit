extends SceneTree
## House-from-rooms generator (scripts/kit/kit_house_rooms.gd, an internal task), headless:
## room parsing, budgets, consistent winding, open doorways and front door, stair headroom,
## the rooms sidecar and a glTF round trip. Run by tests/kit_house_rooms/run.sh.

const H = preload("res://scripts/kit/kit_house_rooms.gd")
var passed := 0
var failed := 0


func check(ok: bool, what: String) -> void:
	if ok:
		passed += 1
	else:
		failed += 1
		print("FAIL ", what)


func _init() -> void:
	check(H.parse_rooms("bedroom:3,living,kitchen,bath:2") is Array and (H.parse_rooms("bedroom:3,living,kitchen,bath:2") as Array).size() == 7, "parse 7 rooms")
	check(H.parse_rooms("Bedrooms:2, Bathroom") is Array, "aliases and spaces")
	check(H.parse_rooms("bedroom,garage") is String and String(H.parse_rooms("bedroom,garage")).contains("garage"), "unknown room named")
	check(H.parse_rooms("bedroom:0") is String, "bad count refused")
	check(H.parse_rooms("bedroom:20") is String, "too many rooms refused")
	check(H.build({"rooms": "bedroom", "style": "gothic"}).has("error"), "unknown style refused")
	check(H.build({"rooms": "bedroom", "roof": "dome"}).has("error"), "unknown roof refused")
	var cases := [
		{"rooms": "bedroom:3,living,kitchen,bath:2", "floors": "2", "style": "beach"},
		{"rooms": "bedroom:3,living,kitchen,bath:2", "floors": "1", "style": "modern"},
		{"rooms": "living,kitchen,bath", "style": "stone"},
		{"rooms": "bedroom:4,living,dining,kitchen,study,bath:3", "floors": "2", "style": "plaster", "roof": "flat"},
	]
	for c in cases:
		_case(c)
	_export()
	print("KIT HOUSE ROOMS TEST %d passed, %d failed" % [passed, failed])
	quit(0 if failed == 0 else 1)


func _case(c: Dictionary) -> void:
	var name := "%s/%s" % [c.rooms, c.get("floors", "auto")]
	var got := H.build(c)
	check(not got.has("error"), name + " builds: " + String(got.get("error", "")))
	if got.has("error"):
		return
	var info: Dictionary = got.info
	var mesh: ArrayMesh = got.mesh
	var tris := _triangles(mesh)
	check(tris.size() == int(info.triangles), name + " triangle count matches info")
	check(tris.size() < 8000, name + " under 8k triangles (%d)" % tris.size())
	check(info.rooms.size() == (H.parse_rooms(c.rooms) as Array).size(), name + " every room placed")
	# winding: Godot front faces are clockwise, so the right-hand normal points inward
	var bad := 0
	for t in tris:
		if (t[1] - t[0]).cross(t[2] - t[0]).dot(t[3]) >= 0.0:
			bad += 1
	check(bad == 0, name + " all %d triangles wound clockwise to their normal (%d bad)" % [tris.size(), bad])
	# every doorway is open: no geometry in the opening
	for room in info.rooms:
		var d: Array = room.door
		var lo := Vector3(d[0] - H.DOOR_W / 2.0 + 0.05, d[1] + 0.05, d[2] - 0.3)
		var hi := Vector3(d[0] + H.DOOR_W / 2.0 - 0.05, d[1] + H.DOOR_H - 0.05, d[2] + 0.3)
		check(_clear(tris, AABB(lo, hi - lo)), name + " doorway of " + String(room.name) + " is open")
		# a room's door leads onto the corridor
		check(absf(float(d[2])) <= H.CORRIDOR / 2.0 + 0.01, name + " " + String(room.name) + " opens onto the corridor")
		var r: Array = room.rect
		check(float(r[0]) <= float(d[0]) and float(d[0]) <= float(r[2]), name + " " + String(room.name) + " door inside its room's width")
	var fd: Array = info.front_door
	var flo := Vector3(fd[0] - 0.5, fd[1] + 0.05, fd[2] - H.FRONT_DOOR_W / 2.0 + 0.05)
	var fhi := Vector3(fd[0] + 0.5, fd[1] + H.DOOR_H - 0.05, fd[2] + H.FRONT_DOOR_W / 2.0 - 0.05)
	check(_clear(tris, AABB(flo, fhi - flo)), name + " front door open from outside to inside")
	# the corridor is clear from the front door to the far end at walking height
	var size: Array = info.size
	var clo := Vector3(-float(size[0]) / 2.0 + 0.25, H.BASE + 0.05, -H.CORRIDOR / 2.0 + 0.1)
	var chi := Vector3(float(size[0]) / 2.0 - 0.25 - (H.STAIR_BAY if int(info.floors) == 2 else 0.0), H.BASE + 2.0, H.CORRIDOR / 2.0 - 0.1)
	check(_clear(tris, AABB(clo, chi - clo)), name + " ground corridor clear")
	if int(info.floors) == 2:
		var st: Dictionary = info.stair
		var sr: Array = st.rect
		var rise := H.STOREY / H.RISERS
		var head_ok := true
		for s in H.RISERS - 1:
			var z1 := float(sr[3]) - s * 0.28
			var y := H.BASE + (s + 1) * rise
			var slo := Vector3(float(sr[0]) + 0.05, y + 0.02, z1 - 0.26)
			var shi := Vector3(float(sr[2]) - 0.05, y + 2.0, z1 - 0.02)
			if not _clear(tris, AABB(slo, shi - slo)):
				head_ok = false
		check(head_ok, name + " 2 m headroom over every step")
		# an internal task: a visitor is a 0.8 m-wide body, not a centre line. The stair
		# opening must run 0.3 m past the stair onto the walkway side, so a 0.8 m
		# body path at the walkway side of the opening still has 2 m headroom.
		var hw := float(sr[0]) - 0.3
		var path_ok := true
		for s in H.RISERS - 1:
			var z1 := float(sr[3]) - s * 0.28
			var y := H.BASE + (s + 1) * rise
			var plo := Vector3(hw + 0.05, y + 0.02, z1 - 0.26)
			var phi := Vector3(hw + 0.85, y + 2.0, z1 - 0.02)
			if not _clear(tris, AABB(plo, phi - plo)):
				path_ok = false
		check(path_ok, name + " 2 m headroom over a 0.8 m body path at the walkway side")
		check(absf(float(st.top[1]) - (H.BASE + H.STOREY)) < 0.01, name + " stair reaches the upper floor")
		# upstairs every room exists and the top of the stair lands in the corridor band
		check(absf(float(st.top[2])) <= H.CORRIDOR / 2.0 + 0.6, name + " stair top near the upper corridor")
		var up := 0
		for room in info.rooms:
			if int(room.floor) == 1:
				up += 1
		check(up > 0, name + " rooms upstairs")
	# windows: glass on every floor
	check(_has_surface(mesh, "house_glass"), name + " has glazed windows")
	# lights (an internal task): at most 6 (the renderer lights one mesh with 8 at most), inside the
	# house below the ceiling, on every floor, and every room reached by a light on its floor
	var lights: Array = info.lights
	check(lights.size() >= int(info.floors) and lights.size() <= H.MAX_LIGHTS, name + " 1..6 lights (%d)" % lights.size())
	var inside := true
	for l in lights:
		var p: Array = l.position
		if absf(float(p[0])) > float(size[0]) / 2.0 or absf(float(p[2])) > float(size[1]) / 2.0 or String(l.type) != "point":
			inside = false
		if _clear(tris, AABB(Vector3(p[0], p[1], p[2]) - Vector3.ONE * 0.05, Vector3.ONE * 0.1)) == false:
			inside = false   # not inside a wall or slab
	check(inside, name + " lights are points inside the house, in the open")
	for f in int(info.floors):
		var on := 0
		for l in lights:
			if float(l.position[1]) > H.BASE + f * H.STOREY and float(l.position[1]) < H.BASE + (f + 1) * H.STOREY - H.SLAB:
				on += 1
		check(on > 0, name + " floor %d has a light" % f)
	var dark := []
	for room in info.rooms:
		if (room.lit_by as Array).is_empty():
			dark.append(room.name)
	check(dark.is_empty(), name + " every room is lit (dark: %s)" % ", ".join(dark))


func _export() -> void:
	var dir := OS.get_environment("HOUSE_TMP")
	if dir.is_empty():
		dir = OS.get_user_data_dir()
	var out := dir.path_join("out/beach_house.glb")
	var code := H.export(out, {"rooms": "bedroom:3,living,kitchen,bath:2", "floors": "2", "style": "beach"})
	check(code == 0, "export returns 0")
	check(FileAccess.file_exists(out), "glb written")
	var side := dir.path_join("out/beach_house.rooms.json")
	var j: Variant = JSON.parse_string(FileAccess.get_file_as_string(side))
	check(j is Dictionary and (j as Dictionary).rooms.size() == 7 and int((j as Dictionary).floors) == 2, "rooms sidecar")
	check(j is Dictionary and not ((j as Dictionary).get("lights", []) as Array).is_empty(), "sidecar has the lights")
	# placed at (10, 0, -4) turned 90 degrees: model +x goes to world -z
	var placed := H.scene_lights(j, Vector3(10, 0, -4), 90.0, "beach")
	var l0: Dictionary = (j as Dictionary).lights[0]
	var p0: Array = placed[0].position
	check(placed.size() == (j as Dictionary).lights.size() and String(placed[0].id) == "beach_light_1", "scene_lights keeps every light with prefixed ids")
	check(absf(float(p0[0]) - (10.0 + float(l0.position[2]))) < 0.02 and absf(float(p0[2]) - (-4.0 - float(l0.position[0]))) < 0.02
		and absf(float(p0[1]) - float(l0.position[1])) < 0.02, "scene_lights places by position and yaw (%s from %s)" % [p0, l0.position])
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	check(doc.append_from_file(out, st) == OK, "glb loads")
	var scene := doc.generate_scene(st)
	var n := 0
	for mi in scene.find_children("*", "MeshInstance3D", true, false):
		var m: Mesh = (mi as MeshInstance3D).mesh
		for si in m.get_surface_count():
			n += (m.surface_get_arrays(si)[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3 if m.surface_get_arrays(si)[Mesh.ARRAY_INDEX] != null else (m.surface_get_arrays(si)[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	check(n == int((j as Dictionary).triangles), "glb keeps every triangle (%d vs %d)" % [n, int((j as Dictionary).triangles)])
	scene.free()
	check(H.export(dir.path_join("out/bad.glb"), {"rooms": "castle"}) == 2, "bad rooms exit 2")


static func _triangles(mesh: ArrayMesh) -> Array:
	var out := []
	for si in mesh.get_surface_count():
		var a := mesh.surface_get_arrays(si)
		var v: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
		var nr: PackedVector3Array = a[Mesh.ARRAY_NORMAL]
		var idx: Variant = a[Mesh.ARRAY_INDEX]
		var ids: PackedInt32Array = idx if idx != null else PackedInt32Array(range(v.size()))
		for i in range(0, ids.size(), 3):
			out.append([v[ids[i]], v[ids[i + 1]], v[ids[i + 2]], nr[ids[i]]])
	return out


static func _clear(tris: Array, box: AABB) -> bool:
	for t in tris:
		var tb := AABB(t[0], Vector3.ZERO).expand(t[1]).expand(t[2])
		if tb.intersects(box):
			return false
	return true


static func _has_surface(mesh: ArrayMesh, mat_name: String) -> bool:
	for si in mesh.get_surface_count():
		var m := mesh.surface_get_material(si)
		if m != null and m.resource_name == mat_name:
			return true
	return false
