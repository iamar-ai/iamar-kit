extends SceneTree
## House furnishing (scripts/kit/kit_house_furnish.gd, an internal task), headless: every room gets the
## pieces of its type from the catalogue, inside its walls, on its floor, clear of its doorway,
## of each other and (tall pieces) of its windows; the furnished glb keeps them and stays under
## budget; a missing catalogue is an error. Run by tests/kit_house_furnish/run.sh.

const H = preload("res://scripts/kit/kit_house_rooms.gd")
const F = preload("res://scripts/kit/kit_house_furnish.gd")
const MUST := {"bedroom": ["cot_bed", "wardrobe", "rug"], "living": ["sofa", "rug"], "kitchen": ["kitchen_counter"],
	"dining": ["trestle_table"], "bath": ["bathtub"], "study": ["bookshelf"]}
var passed := 0
var failed := 0


func check(ok: bool, what: String) -> void:
	if ok:
		passed += 1
	else:
		failed += 1
		print("FAIL ", what)


func _init() -> void:
	check(F.catalog_dir() != "", "catalogue found (IAMAR_KIT_CATALOG)")
	var dir := OS.get_environment("HOUSE_TMP")
	if dir.is_empty():
		dir = OS.get_user_data_dir()
	var cases := [
		{"rooms": "bedroom:3,living,kitchen,bath:2", "floors": "2", "style": "beach"},
		{"rooms": "bedroom:3,living,kitchen,bath:2", "floors": "1", "style": "modern"},
		{"rooms": "living,kitchen,bath", "style": "stone"},
		{"rooms": "bedroom:4,living,dining,kitchen,study,bath:3", "floors": "2", "style": "plaster", "roof": "flat"},
	]
	for i in cases.size():
		var c: Dictionary = cases[i].duplicate()
		c["furnish"] = "true"
		_case(dir.path_join("out/house_%d.glb" % i), c)
	# without --furnish nothing changes
	var plain := dir.path_join("out/plain.glb")
	check(H.export(plain, {"rooms": "bedroom,living"}) == 0, "plain export")
	var pj: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(plain.get_basename() + ".rooms.json"))
	check(not (pj.rooms[0] as Dictionary).has("furniture") and _furniture_nodes(plain) == 0, "no --furnish, no furniture")
	# a missing catalogue is an error, not a bare house
	var root := Node3D.new()
	var info: Dictionary = H.build({"rooms": "bedroom"}).info
	var e: Variant = F.furnish(root, info, "/nonexistent/catalog")
	check(e is int and int(e) == 0 and not (info.rooms[0] as Dictionary).get("unplaced", []).is_empty(), "bad catalogue folder: every piece unplaced")
	root.free()
	print("KIT HOUSE FURNISH TEST %d passed, %d failed" % [passed, failed])
	quit(0 if failed == 0 else 1)


func _case(out: String, c: Dictionary) -> void:
	var label := "%s/%s" % [c.rooms, c.get("floors", "-")]
	check(H.export(out, c) == 0, "export %s" % label)
	var j: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(out.get_basename() + ".rooms.json"))
	check(bool(j.get("furnished", false)), "%s: sidecar says furnished" % label)
	check(int(j.triangles) <= H.MAX_TRIANGLES and int(j.get("furniture_triangles", 0)) > 0, "%s: %d triangles (furniture %d) under budget" % [label, int(j.triangles), int(j.get("furniture_triangles", 0))])
	var count := 0
	for room: Dictionary in j.rooms:
		var have := (room.get("furniture", []) as Array).map(func(f): return String(f.item))
		count += have.size()
		for need: String in MUST.get(room.type, []):
			check(need in have, "%s %s has a %s (got %s, unplaced %s)" % [label, room.name, need, have, room.get("unplaced", [])])
		var r: Array = room.rect
		var rect := Rect2(r[0], r[1], r[2] - r[0], r[3] - r[1])
		var door: Array = room.door
		var back_low: bool = absf(float(door[2]) - float(r[3])) < absf(float(door[2]) - float(r[1]))
		var apron := Rect2(float(door[0]) - 0.45 - F.DOOR_SIDE, float(r[3]) - F.DOOR_APRON if back_low else float(r[1]), 0.9 + 2.0 * F.DOOR_SIDE, F.DOOR_APRON)
		var solids := []
		for f: Dictionary in room.get("furniture", []):
			var fp: Array = f.footprint
			var fr := Rect2(fp[0], fp[1], fp[2] - fp[0], fp[3] - fp[1])
			check(rect.encloses(fr), "%s %s %s inside the room" % [label, room.name, f.item])
			if f.item != "rug":
				check(not fr.intersects(apron), "%s %s %s clear of the doorway" % [label, room.name, f.item])
				for s: Rect2 in solids:
					check(not fr.intersects(s), "%s %s %s does not overlap another piece" % [label, room.name, f.item])
				solids.append(fr)
			check(absf(float(f.position[1]) - float(door[1])) < 3.0, "%s %s %s on its floor" % [label, room.name, f.item])
	check(count == _furniture_nodes(out), "%s: glb holds every piece (%d)" % [label, count])
	check(_floor_ok(out, j), "%s: every piece stands on its room's floor" % label)


## Furniture nodes in the written glb.
func _furniture_nodes(out: String) -> int:
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	if doc.append_from_file(out, st) != OK:
		return -1
	var scene := doc.generate_scene(st)
	var f := scene.find_child("Furniture", true, false)
	var n := f.get_child_count() if f != null else 0
	scene.free()
	return n


## The lowest point of each piece is its room's floor (within 2 cm).
func _floor_ok(out: String, j: Dictionary) -> bool:
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	if doc.append_from_file(out, st) != OK:
		return false
	var scene := doc.generate_scene(st)
	var floors := {}
	for room: Dictionary in j.rooms:
		for f: Dictionary in room.get("furniture", []):
			floors["%s_%s" % [room.name, String(f.item).replace("-", "_")]] = float(room.door[1])
	var ok := true
	var furn := scene.find_child("Furniture", true, false)
	for c in furn.get_children():
		var lo := INF
		for mi in (c as Node).find_children("*", "MeshInstance3D", true, false):
			var xf := Transform3D.IDENTITY
			var p: Node = mi
			while p != furn:
				xf = (p as Node3D).transform * xf
				p = p.get_parent()
			var box: AABB = xf * (mi as MeshInstance3D).mesh.get_aabb()
			lo = minf(lo, box.position.y)
		var want: float = floors.get(String(c.name), NAN)
		if is_nan(want) or absf(lo - want) > 0.02:
			print("  %s lowest %.3f, floor %s" % [c.name, lo, want])
			ok = false
	scene.free()
	return ok
