extends SceneTree
## WorldChecks (scripts/kit/world_checks.gd): the validate WARNs of an internal task.
## Run with tests/kit_world_checks/run.sh (headless, a throwaway stub project).

const WorldChecks = preload("res://world_checks.gd")
var _fails := 0


func _check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ") + what)
	if not ok:
		_fails += 1


func _has(lines: PackedStringArray, parts: Array) -> bool:
	for l in lines:
		var all := true
		for p in parts:
			all = all and l.contains(p)
		if all:
			return true
	return false


## Ground: y -0.45 for |x| < 50, a 5 m high plateau for 60 <= x <= 70 (its top only), nothing elsewhere.
func _height(x: float, _z: float, from_y: float) -> float:
	if x >= 60.0 and x <= 70.0:
		return 5.0 if from_y >= 5.0 else NAN
	if absf(x) < 50.0:
		return -0.45 if from_y >= -0.45 else NAN
	return NAN


func _solid(feet: Vector3) -> String:
	return "Wall_3" if feet.x >= 30.0 and feet.x <= 31.0 else ""


func _spawn(p: Vector3, waters := []) -> PackedStringArray:
	return WorldChecks.spawn_warnings({"s": p}, waters, _height, _solid)


func _init() -> void:
	# spawns: the simulation's mid-air spawn, and right ones
	var air := _spawn(Vector3(0, 1.5, 0))
	_check(air.size() == 1 and _has(air, ["spawn 's'", "1.95 m above the ground", "ground y -0.45", "Set its y to -0.45"]),
		"spawn 1.5 over ground -0.45: in the air, fix names y -0.45")
	_check(_spawn(Vector3(0, -0.45, 0)).is_empty(), "spawn on the ground: no warning")
	_check(_spawn(Vector3(0, -0.2, 0)).is_empty(), "spawn 0.25 m above ground: no warning")
	_check(_has(_spawn(Vector3(100, 0, 0)), ["no ground under it", "fall forever"]), "spawn over nothing: no ground")
	_check(_has(_spawn(Vector3(65, 0, 0)), ["5.00 m under the ground", "Set its y to 5.00"]), "spawn under a plateau: under the ground, fix names its top")
	_check(_spawn(Vector3(65, 5, 0)).is_empty(), "spawn on the plateau: no warning")
	# water: the beach brief's spawn in the sea, and in the shallows
	var sea := [{"id": "sea", "position": [0, 1.5, 20], "size": [20, 20], "depth": 3}]
	_check(_has(_spawn(Vector3(0, -0.45, 20), sea), ["is under water", "water 'sea'", "y 1.50", "1.95 m above its ground"]),
		"spawn 1.95 m under the sea surface: under water")
	var shallows := [{"id": "shallows", "position": [0, 0.0, 20], "size": [20, 20]}]
	var wade := _spawn(Vector3(0, -0.45, 20), shallows)
	_check(_has(wade, ["stands in 0.45 m of water"]) and not _has(wade, ["under water"]), "spawn in 0.45 m of water: wading, not under water")
	_check(_spawn(Vector3(0, -0.45, 40), sea).is_empty(), "spawn beside the sea: no warning")
	var lagoon := [{"id": "lagoon", "position": [65, 1.0, 0], "size": [40, 40]}]
	_check(_spawn(Vector3(65, 5, 0), lagoon).is_empty(), "spawn on ground above the water surface: no warning")
	# solids
	_check(_has(_spawn(Vector3(30.5, -0.45, 0)), ["inside a solid (Wall_3)", "ground y -0.45"]), "spawn in a wall: inside a solid, names it")
	_check(WorldChecks.spawn_warnings({"s": Vector3(30.5, -0.45, 0)}, [], _height).is_empty(), "no solid query (data only): no solid warning")
	# solid_hit: the convex colliders validate tests a standing visitor against
	var wall := BoxShape3D.new()
	wall.size = Vector3(2, 3, 2)
	var pillar := CylinderShape3D.new()
	pillar.radius = 0.4
	pillar.height = 4.0
	var shapes := [["wall", Transform3D(Basis.IDENTITY, Vector3(10, 1.05, 0)), wall],
		["pillar", Transform3D(Basis.IDENTITY, Vector3(-10, 2, 0)), pillar]]
	_check(WorldChecks.solid_hit(shapes, Vector3(10, -0.45, 0)) == "wall", "solid_hit: feet inside a wall standing on its base")
	_check(WorldChecks.solid_hit(shapes, Vector3(11.2, -0.45, 0)) == "wall", "solid_hit: 0.2 m from the wall face is touching it")
	_check(WorldChecks.solid_hit(shapes, Vector3(12, -0.45, 0)) == "", "solid_hit: 1 m from the wall is clear")
	_check(WorldChecks.solid_hit(shapes, Vector3(10, 2.55, 0)) == "", "solid_hit: standing on top of the wall is clear")
	_check(WorldChecks.solid_hit(shapes, Vector3(-10.5, 0, 0)) == "pillar", "solid_hit: against a pillar")
	var root := Node3D.new()
	var body := StaticBody3D.new()
	body.name = "Wall_7"
	var cs := CollisionShape3D.new()
	cs.shape = wall
	body.add_child(cs)
	root.add_child(body)
	var mesh_body := StaticBody3D.new()
	var mcs := CollisionShape3D.new()
	mcs.shape = ConcavePolygonShape3D.new()
	mesh_body.add_child(mcs)
	root.add_child(mesh_body)
	body.position = Vector3(3, 0, 0)
	root.position = Vector3(0, 1, 0)
	var found := WorldChecks.solids(root)
	_check(found.size() == 1 and found[0][0] == "Wall_7" and (found[0][1] as Transform3D).origin == Vector3(3, 1, 0), "solids: convex static colliders only, named by their body, placed out of the tree")
	var slab := BoxShape3D.new()
	slab.size = Vector3(120, 1, 120)
	_check(WorldChecks.solid_hit([["beach", Transform3D(Basis.IDENTITY, Vector3(0, -0.95, 0)), slab]], Vector3(0, -0.45, 0)) == "", "solid_hit: standing on a ground slab is clear")
	root.free()
	# raw spawns: scene spawn_points and the manifest's own spawn
	var raw := WorldChecks.raw_spawns({"spawn": {"position": [1, 2, 3], "yaw": 90}},
		{"spawn_points": [{"id": "default", "position": [4, 5, 6]}, {"id": "bad", "position": [1]}]})
	_check(raw.size() == 2 and raw["spawn"] == Vector3(1, 2, 3) and raw["default"] == Vector3(4, 5, 6), "raw_spawns: manifest spawn and spawn_points, malformed skipped")

	# terrain: the simulation's 241 on the low tier's 150k
	var big := WorldChecks.terrain_warnings({"terrain": {"type": "heightmap", "resolution": 241, "size": [256, 256]}}, 150000)
	_check(big.size() == 1 and _has(big, ["resolution 241", "115200 triangles", "77%", "\"resolution\": 129", "32768 triangles", "22%", "2.0 m"]),
		"terrain 241 of 150k: WARN, suggests 129")
	_check(WorldChecks.terrain_warnings({"terrain": {"type": "procedural", "resolution": 129}}, 150000).is_empty(), "terrain 129: no warning")
	_check(WorldChecks.terrain_warnings({"terrain": {"type": "procedural"}}, 0).is_empty(), "terrain default resolution, no budget: no warning")
	_check(WorldChecks.terrain_warnings({"terrain": {"type": "flat", "resolution": 1025}}, 150000).is_empty(), "flat terrain: resolution ignored, no warning")
	_check(WorldChecks.terrain_warnings({}, 150000).is_empty(), "no terrain: no warning")
	_check(WorldChecks.suggested_resolution(150000) == 129 and WorldChecks.suggested_resolution(600000) == 257 and WorldChecks.suggested_resolution(1000) == 17,
		"suggested_resolution: 129 at 150k, 257 at 600k, at least 17")

	# tonemap: the simulation's sand washes out; the default grass does not
	var scene := {"terrain": {"type": "procedural", "materials": [{"name": "sand", "color": "#e9dbb4"}, {"name": "grass", "color": "#6f8f4a"}]},
		"water": [{"id": "sea", "color": "#3fc1c9cc", "position": [0, 0, 0], "size": [10, 10]}],
		"primitives": [{"shape": "box", "color": "#E9DBB4"}, {"shape": "box", "color": "#e9dbb4"}, {"shape": "box", "color": "#e9dbb4"},
			{"shape": "box", "color": "#e9dbb4"}, {"id": "lamp", "shape": "sphere", "color": "#ffffff", "unlit": true}]}
	var tm := WorldChecks.tonemap_warnings(scene)
	for l in tm:
		print("  ", l)
	_check(_has(tm, ["terrain material sand", "#e9dbb4", "clips it to flat white"]), "sand terrain #e9dbb4 at noon: clips")
	_check(not _has(tm, ["grass"]), "grass #6f8f4a: no warning")
	_check(not _has(tm, ["lamp"]), "unlit primitive: no warning")
	_check(_has(tm, ["primitive box_0, box_1, box_2 (+1 more)"]), "same colour on 4 primitives: one line, 3 names +1 more")
	var fix := ""
	for l in tm:
		if l.contains("terrain material sand"):
			fix = l.get_slice("Use ", 1).get_slice(" ", 0)
	var fixed := WorldChecks.tonemap_warnings({"terrain": {"type": "procedural", "materials": [{"name": "sand", "color": fix}]}})
	_check(fix.begins_with("#") and fixed.is_empty(), "the suggested colour %s no longer clips" % fix)
	var dawn := WorldChecks.tonemap_warnings({"environment": {"time_of_day": 6.2, "ambient": {"energy": 0.3}}, "terrain": {"type": "procedural", "materials": [{"color": "#e9dbb4"}]}})
	_check(dawn.is_empty(), "same sand at dawn with dim ambient: no warning")
	var hot := WorldChecks.tonemap_warnings({"environment": {"exposure": 2.0}, "primitives": [{"id": "wall", "shape": "box", "color": "#b0b0b0"}]})
	_check(_has(hot, ["primitive wall", "#b0b0b0"]), "exposure 2 clips a light grey")
	var light := WorldChecks.scene_light({})
	_check(light.r > 1.0 and light.r < 1.3, "default light: sun + grey ambient = %.2f" % light.r)

	# rooms no light reaches (an internal task): a two-room, two-floor house sidecar placed at (20, 0, 0)
	# turned 90 degrees (model +x -> world -z)
	var house := {"storey": 3.0, "rooms": [
		{"name": "living_1", "floor": 0, "rect": [-4, -4, 0, 0]},
		{"name": "bedroom_2", "floor": 1, "rect": [0, -4, 4, 0]}],
		"lights": [{"id": "light_1", "type": "point", "position": [-2, 2.6, -2], "range": 6}]}
	var rooms_of := func(a: String) -> Variant: return house if a == "models/house.glb" else {}
	var obj := {"asset": "models/house.glb", "position": [20, 0, 0], "rotation": [0, 90, 0]}
	var none := WorldChecks.room_light_warnings({"objects": [obj, {"asset": "models/tree.glb"}]}, rooms_of)
	for l in none:
		print("  ", l)
	_check(none.size() == 1 and _has(none, ["objects[0] models/house.glb", "2 of 2 rooms", "living_1, bedroom_2", "\"type\": \"point\"", "house.rooms.json"]),
		"house without lights: one WARN naming both rooms, a light to add and the sidecar's lights")
	# living_1's centre (-2, -2) lands at world (18, -, 2); bedroom_2's (2, -2) at (18, -, -2)
	var down := {"type": "point", "position": [18, 2.6, 2], "range": 5}
	var one := WorldChecks.room_light_warnings({"objects": [obj], "lights": [down]}, rooms_of)
	_check(_has(one, ["1 of 2 rooms", "(bedroom_2)"]) and not _has(one, ["living_1"]),
		"a light in the ground-floor room lights it, not the room upstairs (other floor)")
	var up := {"type": "point", "position": [18, 5.6, -2], "range": 5}
	_check(WorldChecks.room_light_warnings({"objects": [obj], "lights": [down, up]}, rooms_of).is_empty(), "a light on each floor: no warning")
	var far := {"type": "point", "position": [40, 2.6, 2], "range": 5}
	_check(_has(WorldChecks.room_light_warnings({"objects": [obj], "lights": [far, up]}, rooms_of), ["(living_1)"]), "a light out of range does not count")
	var sun := {"type": "directional", "position": [18, 2.6, 2]}
	_check(_has(WorldChecks.room_light_warnings({"objects": [obj], "lights": [sun, up]}, rooms_of), ["(living_1)"]), "a directional light does not count as a room light")
	# the suggested light fixes the room it names
	var fix_room := ""
	for l in one:
		fix_room = l.get_slice("e.g. ", 1).get_slice("}", 0) + "}"
	var parsed: Variant = JSON.parse_string(fix_room)
	_check(parsed is Dictionary and WorldChecks.room_light_warnings({"objects": [obj], "lights": [down, parsed]}, rooms_of).is_empty(),
		"the suggested light %s lights the dark room" % fix_room)
	_check(WorldChecks.rooms_reader("").call("models/house.glb") is Dictionary and (WorldChecks.rooms_reader("").call("models/house.glb") as Dictionary).is_empty(),
		"rooms_reader with no folder (a packed .iamar): no sidecar, no check")

	print("WORLD_CHECKS %s (%d failed)" % ["PASS" if _fails == 0 else "FAIL", _fails])
	quit(0 if _fails == 0 else 1)
