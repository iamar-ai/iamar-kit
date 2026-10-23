extends RefCounted
## Routes for `iamar-world playtest` exploration steps (an internal task): the waypoints a walking
## visitor follows into a room of a generated house, and the steps `playtest --auto` plays
## to visit every water body, house room, portal, NPC and named object of a world.
## Plain Godot only (no browser classes), so a throwaway project can test it
## (tests/kit_playtest/routes_test.gd).
##
## A house is a scene object whose glTF has a rooms sidecar beside it (`<asset>.rooms.json`,
## written by `iamar-world assets building house`, docs/HOUSE_ROOMS.md): its front door, its
## rooms' rectangles and doorways, and the stair, in the model's own space.

const DOOR_OUT := 2.0       ## m in front of the front door where the walk in starts
const DOOR_IN := 1.0        ## m inside the front door
const PORTAL_STANDOFF := 2.5  ## m in front of a portal: close enough to see it, not to travel
const MAX_OBJECTS := 24     ## named objects --auto walks to (the nearest first)


## The object's placement, as the browser's WorldBuilder.xform_of: rotation [x, y, z] in
## degrees (intrinsic Y-X-Z), scale a number or [x, y, z], position its origin.
static func xform_of(d: Dictionary) -> Transform3D:
	var r := _v3(d.get("rotation", [0, 0, 0]), Vector3.ZERO)
	var basis := Basis.from_euler(Vector3(deg_to_rad(r.x), deg_to_rad(r.y), deg_to_rad(r.z)), EULER_ORDER_YXZ)
	var s: Variant = d.get("scale", 1.0)
	var sv := Vector3.ONE * float(s) if (s is float or s is int) else _v3(s, Vector3.ONE)
	return Transform3D(basis.scaled_local(sv), _v3(d.get("position", [0, 0, 0]), Vector3.ZERO))


static func _v3(a: Variant, def: Vector3) -> Vector3:
	if a is Array and (a as Array).size() >= 3:
		return Vector3(float(a[0]), float(a[1]), float(a[2]))
	return def


## The room `name` ("bedroom_1") of a rooms sidecar, or {}.
static func room_of(rooms: Dictionary, name: String) -> Dictionary:
	for r in rooms.get("rooms", []):
		if String(r.get("name", "")) == name:
			return r
	return {}


## World-space waypoints from outside the front door to the middle of `room` (a row of
## rooms.json "rooms"), through the corridor and, for an upper floor, up the stair:
## [{"p": Vector3, "why": "front door"}, ...]. The last waypoint is the room's middle.
static func room_route(rooms: Dictionary, xf: Transform3D, room: Dictionary) -> Array:
	var local := _room_route_local(rooms, room)
	var out: Array = []
	for w in local:
		out.append({"p": xf * (w.p as Vector3), "why": w.why, "r": float(w.get("r", -1.0))})
	return out


## The front door walk in only (outside, then just inside), in world space.
static func door_route(rooms: Dictionary, xf: Transform3D) -> Array:
	var out: Array = []
	for w in _door_local(rooms):
		out.append({"p": xf * (w.p as Vector3), "why": w.why, "r": float(w.get("r", -1.0))})
	return out


static func _door_local(rooms: Dictionary) -> Array:
	var door := _v3(rooms.get("front_door", [0, 0, 0]), Vector3.ZERO)
	var facing := _v3(rooms.get("facing", [-1, 0, 0]), Vector3(-1, 0, 0))
	facing.y = 0.0
	facing = facing.normalized() if facing.length() > 0.01 else Vector3(-1, 0, 0)
	return [{"p": door + facing * DOOR_OUT, "why": "outside the front door"},
		{"p": door - facing * DOOR_IN, "why": "inside the front door"}]


static func _room_route_local(rooms: Dictionary, room: Dictionary) -> Array:
	var out := _door_local(rooms)
	var door := _v3(rooms.get("front_door", [0, 0, 0]), Vector3.ZERO)
	var cz := door.z                       # the corridor runs along x through the front door
	var storey := float(rooms.get("storey", 3.0))
	var floor_i := int(room.get("floor", 0))
	var rd := _v3(room.get("door", [0, 0, 0]), Vector3.ZERO)
	var rect: Array = room.get("rect", [rd.x, rd.z, rd.x, rd.z])
	var mid := Vector3((float(rect[0]) + float(rect[2])) / 2.0, rd.y, (float(rect[1]) + float(rect[3])) / 2.0)
	if floor_i > 0 and (rooms.get("stair", {}) as Dictionary).has("bottom"):
		var st: Dictionary = rooms.stair
		var bottom := _v3(st.bottom, Vector3.ZERO)
		var top := _v3(st.top, Vector3.ZERO)
		var sr: Array = st.get("rect", [bottom.x - 0.5, top.z, bottom.x + 0.5, bottom.z])
		var walk_x := float(sr[0]) - 0.7    # the walkway beside the stair (its open side)
		var down := 1.0 if bottom.z > top.z else -1.0   # from the top toward the bottom
		out.append({"p": Vector3(walk_x, door.y, cz), "why": "corridor at the stair"})
		# the stair's foot is against the outside wall: step onto it at its open side, then
		# straight up (heading for the middle of the foot pinned the hero between the wall
		# and the second riser)
		out.append({"p": Vector3(walk_x, door.y, bottom.z - down * 0.3), "why": "beside the stair foot"})
		out.append({"p": Vector3(float(sr[0]) + 0.3, bottom.y, bottom.z - down * 0.3), "why": "stair foot"})
		# onto the stair's middle while the ceiling is still high: higher up, at the edge of
		# the opening, the hero's head meets the floor above
		out.append({"p": Vector3(bottom.x, bottom.y + 0.4, bottom.z - down * 0.9), "why": "on the stair", "r": 0.12})
		out.append({"p": Vector3(top.x, top.y, top.z), "why": "stair top"})
		out.append({"p": Vector3(top.x, top.y, top.z - down * 0.5), "why": "off the stair"})
		out.append({"p": Vector3(walk_x, top.y, top.z - down * 0.5), "why": "upstairs landing"})
		out.append({"p": Vector3(walk_x - 0.5, top.y, cz), "why": "upstairs corridor"})
	var fy := door.y + floor_i * storey
	out.append({"p": Vector3(rd.x, fy, cz), "why": "corridor at the doorway"})
	out.append({"p": Vector3(rd.x, fy, rd.z), "why": "doorway"})
	out.append({"p": Vector3(mid.x, fy, mid.z), "why": "room"})
	return out


## The world-space rectangle test for "the visitor is in this room": p in the room's
## rectangle (shrunk 0.1 m) and within 1.5 m of its floor.
static func in_room(rooms: Dictionary, xf: Transform3D, room: Dictionary, p: Vector3) -> bool:
	var q := xf.affine_inverse() * p
	var r: Array = room.get("rect", [])
	if r.size() < 4:
		return false
	var fy := float((rooms.get("front_door", [0, 0, 0]) as Array)[1]) + int(room.get("floor", 0)) * float(rooms.get("storey", 3.0))
	return q.x > float(r[0]) + 0.1 and q.x < float(r[2]) - 0.1 and q.z > float(r[1]) + 0.1 and q.z < float(r[3]) - 0.1 \
		and absf(q.y - fy) < 1.5


## Where a visitor stands to look at a portal: PORTAL_STANDOFF m in front of it (a portal with
## yaw 0 is entered walking toward -Z, so its front is +Z).
static func portal_front(p: Dictionary) -> Vector3:
	var pos := _v3(p.get("position", [0, 0, 0]), Vector3.ZERO)
	var yaw := deg_to_rad(float(p.get("yaw", 0.0)))
	return pos + Basis(Vector3.UP, yaw) * Vector3(0, 0, PORTAL_STANDOFF)


## The steps `playtest --auto` plays (each from the spawn): swim in every swimmable water body
## (swim to its middle, dive, surface, get out back at the spawn), walk into every room of every
## house, up to every portal and NPC, and to the named objects (houses excluded, nearest first,
## at most MAX_OBJECTS). rooms_of: Callable(asset path) -> the rooms sidecar ({} for none).
static func auto_steps(scene: Dictionary, rooms_of: Callable, spawn: Vector3) -> Array:
	var steps: Array = []
	var wi := 0
	for w in scene.get("water", []):
		var wid := String(w.get("id", "")) if String(w.get("id", "")) != "" else str(wi)
		wi += 1
		if w.get("swimmable", true) == false:
			continue
		steps.append({"do": "swim_to", "water": wid, "from": "spawn", "auto": "water %s" % wid,
			"expect": [{"swimming": true}]})
		steps.append({"do": "dive", "depth": 1.5, "auto": "water %s" % wid,
			"expect": [{"head_under": true}, {"underwater": true}]})
		steps.append({"do": "surface", "auto": "water %s" % wid, "expect": [{"head_under": false}]})
		steps.append({"do": "walk_to", "spawn": true, "auto": "out of water %s" % wid, "expect": [{"swimming": false}]})
	var houses := {}
	for o in scene.get("objects", []):
		var oid := String(o.get("id", ""))
		var rooms: Dictionary = rooms_of.call(String(o.get("asset", "")))
		if oid == "" or rooms.is_empty():
			continue
		houses[oid] = true
		steps.append({"do": "enter", "object": oid, "from": "spawn", "auto": "house %s" % oid})
		for r in rooms.get("rooms", []):
			var room := "%s/%s" % [oid, r.get("name", "")]
			steps.append({"do": "enter", "room": room, "from": "spawn", "auto": "room " + room,
				"expect": [{"in_room": room}]})
	for p in scene.get("portals", []):
		steps.append({"do": "walk_to", "portal": String(p.get("id", "")), "from": "spawn",
			"auto": "portal %s" % p.get("id", "")})
	for n in scene.get("npcs", []):
		steps.append({"do": "walk_to", "npc": String(n.get("id", n.get("name", ""))), "from": "spawn",
			"auto": "npc %s" % n.get("id", n.get("name", ""))})
	var named: Array = []
	for o in scene.get("objects", []) + scene.get("primitives", []):
		var oid := String(o.get("id", ""))
		if oid == "" or houses.has(oid) or _big(o):
			continue
		named.append([_v3(o.get("position", [0, 0, 0]), Vector3.ZERO).distance_to(spawn), oid])
	named.sort_custom(func(a, b): return a[0] < b[0])
	for x in named.slice(0, MAX_OBJECTS):
		steps.append({"do": "walk_to", "object": x[1], "from": "spawn", "auto": "object %s" % x[1]})
	steps.append({"do": "look_at", "spawn_view": true, "auto": "back at the spawn"})
	return steps


## Ground, a level, a floor slab: walking "to" it means nothing. An object scaled 4 or more,
## a primitive over 8 m across, or one named like ground.
static func _big(o: Dictionary) -> bool:
	if String(o.get("id", "")).to_lower() in ["ground", "level", "terrain", "island", "floor"]:
		return true
	if o.has("shape"):
		var sz := _v3(o.get("size", [1, 1, 1]), Vector3.ONE)
		return maxf(sz.x, sz.z) > 8.0
	var s: Variant = o.get("scale", 1.0)
	return (s is float or s is int) and float(s) >= 4.0
