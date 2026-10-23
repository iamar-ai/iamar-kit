extends SceneTree
## Playtest routes (scripts/kit/world_playtest_routes.gd, an internal task), headless in a throwaway
## project: for houses from the house generator, every room's route (front door, corridor,
## stair, doorway, room) is clear of the house's triangles at knee and chest height, ends
## inside its room, and is placed with the object's transform; --auto plans every water
## body, room, portal, NPC and named object. Run by tests/kit_playtest/routes.sh.

const H = preload("res://scripts/kit/kit_house_rooms.gd")
const R = preload("res://scripts/kit/world_playtest_routes.gd")
var passed := 0
var failed := 0


func check(ok: bool, what: String) -> void:
	if ok:
		passed += 1
	else:
		failed += 1
		print("FAIL ", what)


func _init() -> void:
	for c in [{"rooms": "bedroom:3,living,kitchen,bath:2", "floors": "2", "style": "beach"},
			{"rooms": "bedroom:3,living,kitchen,bath:2", "floors": "1", "style": "modern"},
			{"rooms": "bedroom:4,living,dining,kitchen,study,bath:3", "floors": "2", "style": "plaster", "roof": "flat"}]:
		_house_case(c)
	_placed()
	_auto()
	print("KIT PLAYTEST ROUTES TEST %d passed, %d failed" % [passed, failed])
	quit(0 if failed == 0 else 1)


func _house_case(c: Dictionary) -> void:
	var got := H.build(c)
	var name := "%s/%s" % [c.rooms, c.floors]
	check(not got.has("error"), name + " builds")
	if got.has("error"):
		return
	var info: Dictionary = got.info
	var tris := _triangles(got.mesh)
	# the check sees walls: straight from outside the front door to a room's middle hits one
	var r0 := R.room_route(info, Transform3D.IDENTITY, info.rooms[0])
	check(_hits(tris, r0[0].p + Vector3(0, 1.0, 0), r0[-1].p + Vector3(0, 1.0, 0)) != "", name + " a straight line through the walls is caught")
	for room in info.rooms:
		var route := R.room_route(info, Transform3D.IDENTITY, room)
		var rn := "%s %s" % [name, room.name]
		check(route[0].why == "outside the front door" and route[-1].why == "room", rn + " route starts outside, ends in the room")
		check(R.in_room(info, Transform3D.IDENTITY, room, route[-1].p), rn + " route ends inside the room")
		check(not R.in_room(info, Transform3D.IDENTITY, room, route[0].p), rn + " route starts outside the room")
		var up := int(room.floor) == 1
		var whys: Array = []
		for w in route:
			whys.append(w.why)
		check(whys.has("stair top") == up, rn + (" goes up the stair" if up else " stays downstairs"))
		for i in route.size() - 1:
			var a: Vector3 = route[i].p
			var b: Vector3 = route[i + 1].p
			for hgt in [0.6, 1.6]:
				var hit := _hits(tris, a + Vector3(0, hgt, 0), b + Vector3(0, hgt, 0))
				check(hit == "", "%s leg %s -> %s clear at %.1f m%s" % [rn, route[i].why, route[i + 1].why, hgt, hit])


## The same route through a placed house (moved, turned 90 degrees, scaled 1) is the local one transformed.
func _placed() -> void:
	var info: Dictionary = H.build({"rooms": "bedroom:2,living,kitchen,bath", "floors": "2"}).info
	var o := {"position": [30, 0, -12], "rotation": [0, 90, 0]}
	var xf := R.xform_of(o)
	check(xf.origin == Vector3(30, 0, -12) and (xf.basis * Vector3(1, 0, 0)).distance_to(Vector3(0, 0, -1)) < 0.001, "xform_of: yaw 90 turns +x to -z")
	var room: Dictionary = info.rooms[0]
	var local := R.room_route(info, Transform3D.IDENTITY, room)
	var world := R.room_route(info, xf, room)
	var same := local.size() == world.size()
	for i in mini(local.size(), world.size()):
		same = same and (xf * (local[i].p as Vector3)).distance_to(world[i].p) < 0.001
	check(same, "placed route = local route through the object's transform")
	check(R.in_room(info, xf, room, world[-1].p), "in_room works in world space")
	check(R.xform_of({"scale": 2}).basis.get_scale().distance_to(Vector3(2, 2, 2)) < 0.001, "xform_of: number scale")
	var d := R.door_route(info, xf)
	check(d.size() == 2 and (d[0].p as Vector3).distance_to(xf * (Vector3(info.front_door[0], info.front_door[1], info.front_door[2]) + Vector3(-R.DOOR_OUT, 0, 0))) < 0.001, "door route starts DOOR_OUT m in front of the door")
	check(R.portal_front({"position": [0, 0, 10], "yaw": 0}).distance_to(Vector3(0, 0, 10 + R.PORTAL_STANDOFF)) < 0.001, "portal front: +z of a yaw-0 portal")
	check(R.portal_front({"position": [0, 0, 0], "yaw": 90}).distance_to(Vector3(R.PORTAL_STANDOFF, 0, 0)) < 0.001, "portal front turns with yaw")


func _auto() -> void:
	var info: Dictionary = H.build({"rooms": "bedroom:3,living,kitchen,bath:2", "floors": "2"}).info
	var scene := {
		"water": [{"id": "sea", "position": [0, 0, 40], "size": [60, 30]}, {"id": "pond", "position": [5, 0, 5], "swimmable": false}],
		"objects": [{"id": "house", "asset": "assets/house.glb", "position": [0, 0, 0]},
			{"id": "ground", "asset": "assets/ground.glb", "scale": 10, "collision": "mesh"},
			{"id": "palm_far", "asset": "assets/palm.glb", "position": [50, 0, 0]},
			{"id": "palm_near", "asset": "assets/palm.glb", "position": [3, 0, 0]},
			{"asset": "assets/rock.glb", "position": [1, 0, 1]}],
		"portals": [{"id": "to_town", "to": "town", "position": [0, 0, -20]}],
		"npcs": [{"id": "lifeguard", "name": "Lifeguard"}],
		"primitives": [{"id": "buoy", "shape": "sphere", "size": [1, 1, 1], "position": [0, 2, 30]}, {"id": "floor_slab", "shape": "box", "size": [20, 0.2, 20]}]}
	var rooms_of := func(asset: String) -> Dictionary: return info if asset == "assets/house.glb" else {}
	var steps := R.auto_steps(scene, rooms_of, Vector3.ZERO)
	var autos: Array = []
	for s in steps:
		autos.append(String(s.get("auto", "")))
		check(s.has("do") and s.has("auto"), "every auto step has do and auto: %s" % JSON.stringify(s))
	var kinds: Array = []
	for s in steps:
		kinds.append(String(s.do))
	check(kinds.slice(0, 4) == ["swim_to", "dive", "surface", "walk_to"], "swimmable water: swim, dive, surface, get out (%s)" % str(kinds.slice(0, 4)))
	check(not autos.has("water pond"), "not swimmable water is not swum")
	check(autos.has("house house"), "the house is entered")
	var rooms_seen := 0
	for s in steps:
		if s.has("room"):
			rooms_seen += 1
			check(s.get("expect", [])[0].get("in_room", "") == s.room, "room step expects in_room " + String(s.room))
	check(rooms_seen == info.rooms.size(), "every room of the house is visited (%d of %d)" % [rooms_seen, info.rooms.size()])
	check(autos.has("portal to_town") and autos.has("npc lifeguard"), "portal and NPC are visited")
	check(not autos.has("object ground") and not autos.has("object house"), "the ground and the house are not walked to as objects")
	check(autos.find("object palm_near") >= 0 and autos.find("object palm_near") < autos.find("object palm_far"), "named objects nearest first")
	check(autos.has("object buoy") and not autos.has("object floor_slab"), "named primitives are visited, big slabs are not")
	check(steps[-1].do == "look_at" and bool(steps[-1].get("spawn_view", false)), "ends with the spawn view")
	for s in steps:
		if s.do != "dive" and s.do != "surface" and not (s.do == "walk_to" and s.get("spawn", false)) and s.do != "look_at":
			check(String(s.get("from", "")) == "spawn", "%s starts from the spawn" % s.auto)


static func _triangles(mesh: ArrayMesh) -> Array:
	var out := []
	for si in mesh.get_surface_count():
		var a := mesh.surface_get_arrays(si)
		var v: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
		var idx: Variant = a[Mesh.ARRAY_INDEX]
		var ids: PackedInt32Array = idx if idx != null else PackedInt32Array(range(v.size()))
		for i in range(0, ids.size(), 3):
			out.append([v[ids[i]], v[ids[i + 1]], v[ids[i + 2]]])
	return out


## "" when the segment a-b crosses no triangle, else " (hits near <point>)".
static func _hits(tris: Array, a: Vector3, b: Vector3) -> String:
	for t in tris:
		var p: Variant = Geometry3D.segment_intersects_triangle(a, b, t[0], t[1], t[2])
		if p != null:
			return " (hits near %s)" % str((p as Vector3).snappedf(0.01))
	return ""
