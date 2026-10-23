extends SceneTree
## Brief-to-layout planner (scripts/kit/world_from_brief.gd, an internal task), headless: zones and
## the template read from a brief, the house rooms and style, errors for bad briefs, and the
## layout on a beach and a meadow: the house on dry ground with its door to the view, the
## spawn in front of it facing the house, the portal off the house site, nothing left
## standing inside the house. Run by tests/kit_from_brief/run.sh.

const B = preload("res://scripts/kit/world_from_brief.gd")
const H = preload("res://scripts/kit/kit_house_rooms.gd")
const BEACH_HOUSE := "A large 3-bedroom beach house by the beach, water clear enough to swim in, fish visible in the water."
var passed := 0
var failed := 0


func check(ok: bool, what: String) -> void:
	if ok:
		passed += 1
	else:
		failed += 1
		print("FAIL ", what)


## The beach template's ground (a copy of WorldScaffold.beach_height, browser e76c4602).
static func beach_height(x: float, z: float) -> float:
	var s := z - 6.0 * sin(x / 23.0)
	if s >= 14.0:
		return 1.6 + 0.35 * sin(x / 9.0) * sin(z / 11.0) * smoothstep(14.0, 24.0, s)
	if s >= 0.0:
		return lerpf(0.25, 1.6, smoothstep(0.0, 14.0, s))
	return maxf(0.25 + s * 0.09, -5.5)


func _init() -> void:
	_plans()
	_errors()
	_beach_layout()
	_meadow_layout()
	print("KIT FROM BRIEF TEST %d passed, %d failed" % [passed, failed])
	quit(0 if failed == 0 else 1)


func _plans() -> void:
	var p := B.plan({"vision": BEACH_HOUSE, "type": "nature", "mood": {"time": "golden hour"},
		"budgets": {"triangles": 120000, "texture_size": 1024}, "connections": {"name": "iamar://sea-glass-house"},
		"approval": {"date": "2026-10-22", "user_words": "yes"}})
	check(not p.has("error"), "beach brief plans: %s" % p.get("error", ""))
	check(p.template == "beach", "beach brief -> beach template (%s)" % p.template)
	check("house" in p.zones and "beach" in p.zones and "sea" in p.zones, "beach brief zones %s" % [p.zones])
	check(p.house.get("rooms") == "bedroom:3,living,kitchen,bath:2", "3 bedrooms, 2 baths (%s)" % p.house.get("rooms"))
	check(H.parse_rooms(String(p.house.rooms)) is Array, "the room list parses for the generator")
	check(p.house.style == "beach", "beach style")
	check(is_equal_approx(float(p.time_of_day), 17.5), "golden hour -> 17.5")
	check(p.budgets.get("triangles") == 120000 and p.budgets.get("texture_size") == 1024, "budgets copied")
	check(p.id == "sea_glass_house" and p.title == "Sea Glass House", "id/title from the address (%s / %s)" % [p.id, p.title])
	check(p.notes.is_empty(), "approved beach brief has no notes: %s" % [p.notes])
	var words := B.plan({"vision": "A modern two-bedroom cottage with a study and a garden", "type": "other"})
	check(words.house.get("rooms") == "bedroom:2,living,kitchen,study,bath:1", "word count + study (%s)" % words.house.get("rooms"))
	check(words.house.style == "modern" and words.template == "meadow" and "garden" in words.zones, "modern cottage on the meadow")
	check(words.notes.size() == 1 and String(words.notes[0]).contains("approval"), "unapproved brief noted")
	var listed := B.plan({"vision": "x", "type": "town", "layout": {"zones": [
		{"kind": "house", "rooms": "bedroom,living,kitchen,bath", "style": "stone", "roof": "flat"}, "plaza", "lake"]}})
	check(listed.template == "town" and listed.house.rooms == "bedroom,living,kitchen,bath" and listed.house.roof == "flat", "layout.zones override the vision")
	check(listed.notes.size() >= 2 and String(listed.notes[0]).contains("terrain lake"), "lake points at the terrain helper")
	var harbour := B.plan(JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("FROM_BRIEF_SAMPLE"))))
	check(not harbour.has("error") and harbour.template == "beach" and harbour.house.is_empty(), "the interview's sample brief (harbour village) plans")
	check(harbour.id == "mira_harbour", "sample id from iamar://mira-harbour")
	var forced := B.plan({"vision": BEACH_HOUSE}, "interior")
	check(forced.template == "interior" and forced.house.is_empty(), "--template interior keeps no house")
	var room := B.plan({"vision": "A cosy reading room", "type": "interior"})
	check(room.template == "interior" and room.house.is_empty(), "interior type -> interior template")


func _errors() -> void:
	for bad in [[], "text", {}, {"vision": "x", "layout": {"zones": []}}, {"vision": "x", "layout": {"zones": ["castle"]}},
			{"vision": "x", "layout": "beach"}, {"vision": "x", "layout": {"zones": [{"kind": "house", "style": "gothic"}]}}]:
		var got := B.plan(bad)
		check(got.has("error"), "refused: %s" % [bad])


## Footprint of the placed house on the ground: half sizes and centre (world x, z).
func _footprint(o: Dictionary, info: Dictionary) -> Dictionary:
	var yaw := float(o.rotation[1])
	var along_z := absf(sin(deg_to_rad(yaw))) > 0.5
	var l := float(info.size[0]) * 0.5
	var d := float(info.size[1]) * 0.5
	return {"c": Vector2(float(o.position[0]), float(o.position[2])), "h": Vector2(d, l) if along_z else Vector2(l, d)}


func _inside(fp: Dictionary, at: Vector2, pad := 0.0) -> bool:
	return absf(at.x - fp.c.x) < fp.h.x + pad and absf(at.y - fp.c.y) < fp.h.y + pad


func _forward(yaw: float) -> Vector2:
	return Vector2(-sin(deg_to_rad(yaw)), -cos(deg_to_rad(yaw)))


func _layout(scene: Dictionary, p: Dictionary, ground: Callable, name: String) -> Dictionary:
	var built := H.build(p.house)
	check(not built.has("error"), name + " house builds")
	var manifest := {"spawn": "spawn", "features": ["sky", "terrain", "primitives", "portals"], "budgets": {"triangles": 150000, "texture_size": 2048}}
	var lines := B.apply(scene, manifest, p, {"asset": "assets/house.glb", "info": built.info}, ground)
	check(lines.size() >= 3 and String(lines[0]).begins_with("PLACED"), name + " reports placements: %s" % [lines])
	check("objects" in manifest.features and "paths" in manifest.features, name + " declares objects and paths")
	var house: Dictionary = scene.objects[0]
	check(house.asset == "assets/house.glb" and house.collision == "mesh", name + " house is a walkable mesh object")
	var fp := _footprint(house, built.info)
	# the floor slab is at or above every bit of ground under it
	for i in 11:
		for j in 11:
			var at: Vector2 = fp.c + Vector2((i / 5.0 - 1.0) * fp.h.x, (j / 5.0 - 1.0) * fp.h.y)
			if float(ground.call(at.x, at.y)) > float(house.position[1]) + 0.01:
				check(false, name + " ground pokes through the floor at %s" % at)
				return {}
	# nothing from the template is left inside the house
	for e in scene.primitives:
		var id := String(e.id)
		if id == "house_foundation" or id.begins_with("front_step"):
			continue
		check(not _inside(fp, Vector2(float(e.position[0]), float(e.position[2]))), name + " %s not inside the house" % id)
	for e in scene.portals:
		check(not _inside(fp, Vector2(float(e.position[0]), float(e.position[2])), 1.0), name + " portal %s off the house site" % e.id)
	var spawn: Dictionary = scene.spawn_points[0]
	var s := Vector2(float(spawn.position[0]), float(spawn.position[2]))
	check(not _inside(fp, s, 2.0), name + " spawn outside the house")
	var to_house: Vector2 = (fp.c - s).normalized()
	check(_forward(float(spawn.yaw)).dot(to_house) > 0.99, name + " spawn faces the house")
	check(absf(float(spawn.position[1]) - float(ground.call(s.x, s.y)) - 0.2) < 0.02, name + " spawn stands on the ground")
	check(scene.paths.size() == 1 and scene.paths[0].points.size() == 3, name + " front path")
	check(manifest.budgets.triangles == mini(150000, int(p.budgets.get("triangles", 150000))), name + " budget never raised")
	return {"fp": fp, "spawn": s, "house": house}


func _beach_layout() -> void:
	var p := B.plan({"vision": BEACH_HOUSE, "budgets": {"triangles": 900000}})
	var scene := {
		"environment": {"time_of_day": 11.0},
		"water": [{"id": "sea", "position": [0, 0, -36], "size": [160, 88], "depth": 6}],
		"primitives": [
			{"id": "parasol", "shape": "cylinder", "position": [-6, 2.9, 9]},
			{"id": "palm_trunk_1", "shape": "cylinder", "position": [10, 4.5, 20]},
			{"id": "palm_trunk_0", "shape": "cylinder", "position": [-14, 4.5, 17]},
		],
		"spawn_points": [{"id": "spawn", "position": [0, 1.8, 22], "yaw": 0}],
		"portals": [{"id": "home", "position": [-20, 1.7, 26], "yaw": 30}],
	}
	var got := _layout(scene, p, beach_height, "beach")
	if got.is_empty():
		return
	var fp: Dictionary = got.fp
	# the whole house is on the dunes, off the sand
	var low := INF
	for i in 11:
		for j in 11:
			var at: Vector2 = fp.c + Vector2((i / 5.0 - 1.0) * fp.h.x, (j / 5.0 - 1.0) * fp.h.y)
			low = minf(low, beach_height(at.x, at.y))
	check(low >= 1.45, "beach house stands on dry dune (lowest ground %.2f)" % low)
	check(float(got.house.rotation[1]) == -90.0, "front door faces the sea (yaw %s)" % got.house.rotation[1])
	var s: Vector2 = got.spawn
	check(s.y < fp.c.y - fp.h.y and beach_height(s.x, s.y) > 0.2, "spawn on the beach between the house and the sea")
	check(scene.environment.time_of_day == 11.0, "no mood: the template's time kept")


func _meadow_layout() -> void:
	var p := B.plan({"vision": "A two-bedroom home with a garden and a little plaza", "type": "other"}, "meadow")
	var scene := {
		"primitives": [
			{"id": "stone", "shape": "box", "position": [4, 1, -4]},
			{"id": "pillar", "shape": "cylinder", "position": [-4, 2, -4]},
		],
		"spawn_points": [{"id": "spawn", "position": [0, 0, 8], "yaw": 0}],
		"portals": [{"id": "home", "position": [0, 0, -12], "yaw": 0}],
	}
	var flat := func(_x: float, _z: float) -> float: return 0.0
	var got := _layout(scene, p, flat, "meadow")
	if got.is_empty():
		return
	var ids := PackedStringArray()
	for e in scene.primitives:
		ids.append(String(e.id))
	check("plaza" in ids and "plaza_fountain" in ids, "plaza on the meadow")
	check("garden_bed_0" in ids and "garden_bed_2" in ids, "garden beds both sides")
	check(not "house_foundation" in ids, "no foundation on flat ground")
	check(float(got.house.rotation[1]) == 90.0, "front door faces the spawn side (+z)")
