extends RefCounted
## A house from a room list (an internal task): walls with open doorways, glazed windows, floors,
## a stair for two floors, and a gable or flat roof, written as one binary glTF a world can
## place with "collision": "mesh" (the doorways, corridor and stair are walkable).
##
##   iamar-world assets building house <out.glb> --rooms bedroom:3,living,kitchen,bath:2
##       [--floors 1|2] [--style beach|modern|plaster|stone] [--roof gable|flat] [--furnish]
##
## Plan: rooms sit in two rows on either side of a corridor that runs the length of the
## house (x). The front door is at the corridor's west end (facing -x). With two floors the
## living rooms stay downstairs, the bedrooms go up, and a stair bay at the east end joins
## the corridors. Every room has a doorway onto the corridor and windows in its outside
## walls. Beside <out.glb> goes <out>.rooms.json: each room's type, floor and rectangle and
## its doorway and windows, the front door, the stair and the size. --furnish adds catalogue
## furniture per room (KitHouseFurnish, an internal task).
## Prints HOUSE <out> <bytes> bytes <triangles> triangles door <x,y,z> facing <x,y,z> ...
## Plain Godot only (no browser classes), so a throwaway project can test it.

const TYPES := {
	# width along the corridor (m); every room is ROOM_DEPTH deep
	"living": 5.0, "kitchen": 3.6, "dining": 3.6, "bedroom": 3.6, "bath": 2.4, "study": 3.0, "laundry": 2.4,
}
const ALIASES := {"bed": "bedroom", "bedrooms": "bedroom", "bathroom": "bath", "baths": "bath", "bathrooms": "bath",
	"lounge": "living", "living_room": "living", "livingroom": "living", "office": "study", "utility": "laundry"}
const UPSTAIRS := ["bedroom", "study"]
const ROOM_DEPTH := 4.2
const CORRIDOR := 1.4
const STAIR_BAY := 2.6          # stair 1.0 wide against the east wall + 1.6 walkway
const STAIR_WIDTH := 1.0
const STAIR_HOLE_OVERHANG := 0.3  # the stair opening runs this far past the stair onto the
                                  # walkway side, so a visitor's head clears the upper slab
                                  # without climbing on the exact centre line (an internal task)
const BASE := 0.15              # ground slab: its top is the ground floor
const STOREY := 3.0             # floor to floor
const SLAB := 0.2
const EXT := 0.2                # outside wall thickness
const INT := 0.12               # inside wall thickness
const DOOR_W := 0.9
const FRONT_DOOR_W := 1.1
const DOOR_H := 2.2
const RISERS := 16
const MAX_ROOMS := 16
const MAX_TRIANGLES := 20000
const STYLES := {
	# albedo kept at or below ~0.8 so the linear tonemap does not clip to white
	"beach": {"wall": Color(0.80, 0.77, 0.70), "trim": Color(0.74, 0.76, 0.76), "roof": Color(0.33, 0.43, 0.50),
		"floor": Color(0.58, 0.46, 0.33), "stair": Color(0.52, 0.40, 0.28), "roof_kind": "gable", "pitch": 25.0},
	"modern": {"wall": Color(0.72, 0.72, 0.70), "trim": Color(0.16, 0.16, 0.17), "roof": Color(0.26, 0.27, 0.28),
		"floor": Color(0.50, 0.44, 0.38), "stair": Color(0.30, 0.30, 0.31), "roof_kind": "flat", "pitch": 0.0},
	"plaster": {"wall": Color(0.78, 0.72, 0.60), "trim": Color(0.36, 0.25, 0.16), "roof": Color(0.45, 0.24, 0.17),
		"floor": Color(0.50, 0.38, 0.26), "stair": Color(0.42, 0.30, 0.20), "roof_kind": "gable", "pitch": 35.0},
	"stone": {"wall": Color(0.55, 0.53, 0.50), "trim": Color(0.34, 0.27, 0.20), "roof": Color(0.27, 0.29, 0.32),
		"floor": Color(0.47, 0.37, 0.27), "stair": Color(0.40, 0.31, 0.22), "roof_kind": "gable", "pitch": 35.0},
}
const GLASS := Color(0.55, 0.70, 0.78, 0.35)
# Lights (an internal task): the browser's renderer (gl_compatibility) lights one mesh with at most 8
# lights, and the house is one mesh, so a house gets at most 6 shadowless ceiling lights along
# its corridors, each reaching every room beside it (through the walls: no shadows).
const MAX_LIGHTS := 6
const LIGHT_SPACING := 5.0
const LIGHT_COLOR := "#ffdcb0"
const LIGHT_ENERGY := 1.2
const LIGHT_DROP := 0.35        # below the ceiling
const ROOM_EYE := 1.5           # a room counts as lit when a light reaches its centre at this height


## "bedroom:3,living,kitchen,bath:2" -> ["bedroom", "bedroom", "bedroom", "living", ...]; error text on failure.
static func parse_rooms(spec: String) -> Variant:
	var out: Array[String] = []
	for part in spec.split(",", false):
		var bits := part.strip_edges().to_lower().split(":")
		var kind: String = ALIASES.get(bits[0].strip_edges(), bits[0].strip_edges())
		if not TYPES.has(kind):
			return "unknown room '%s' (use %s)" % [bits[0], ", ".join(TYPES.keys())]
		var n := 1
		if bits.size() > 1:
			if not bits[1].is_valid_int() or int(bits[1]) < 1:
				return "bad count in '%s' (e.g. bedroom:3)" % part
			n = int(bits[1])
		for i in n:
			out.append(kind)
	if out.is_empty():
		return "no rooms (e.g. --rooms bedroom:3,living,kitchen,bath:2)"
	if out.size() > MAX_ROOMS:
		return "%d rooms; at most %d per house" % [out.size(), MAX_ROOMS]
	return out


## Rooms per floor: with two floors, bedrooms and studies go up (one bath per floor when there are two).
static func split_floors(rooms: Array[String], floors: int) -> Array:
	if floors == 1:
		return [rooms.duplicate()]
	var down: Array[String] = []
	var up: Array[String] = []
	var baths := rooms.count("bath")
	var baths_down := 0
	for r in rooms:
		if r in UPSTAIRS:
			up.append(r)
		elif r == "bath" and baths > 1 and baths_down >= 1:
			up.append(r)
		else:
			if r == "bath":
				baths_down += 1
			down.append(r)
	if up.is_empty() and down.size() > 1:
		up.append(down.pop_back())
	if down.is_empty() and up.size() > 1:
		down.append(up.pop_front())
	return [down, up]


## Two rows (north, south) of room indices, longest first into the shorter row.
static func split_rows(rooms: Array) -> Array:
	var order := range(rooms.size())
	order.sort_custom(func(a, b): return TYPES[rooms[a]] > TYPES[rooms[b]] or (TYPES[rooms[a]] == TYPES[rooms[b]] and a < b))
	var rows := [[], []]
	var lens := [0.0, 0.0]
	for i in order:
		var r := 0 if lens[0] <= lens[1] else 1
		rows[r].append(i)
		lens[r] += TYPES[rooms[i]]
	for r in 2:
		rows[r].sort()
	return rows


static func row_length(rooms: Array, row: Array) -> float:
	var s := 0.0
	for i in row:
		s += TYPES[rooms[i]]
	return s


## Builds the house; returns {"mesh": ArrayMesh, "info": Dictionary} or {"error": String}.
static func build(o: Dictionary) -> Dictionary:
	var parsed: Variant = parse_rooms(String(o.get("rooms", "")))
	if parsed is String:
		return {"error": parsed}
	var rooms: Array[String] = parsed
	var floors := clampi(int(String(o.get("floors", "2" if rooms.size() > 6 else "1"))), 1, 2)
	var style_name := String(o.get("style", "beach"))
	if not STYLES.has(style_name):
		return {"error": "unknown style '%s' (use %s)" % [style_name, ", ".join(STYLES.keys())]}
	var style: Dictionary = STYLES[style_name]
	var roof := String(o.get("roof", style.roof_kind))
	if not roof in ["gable", "flat"]:
		return {"error": "unknown roof '%s' (gable or flat)" % roof}
	var per_floor := split_floors(rooms, floors)
	floors = per_floor.size()
	var layouts := []
	var lr := 0.0
	for f in floors:
		var rws := split_rows(per_floor[f])
		layouts.append(rws)
		lr = maxf(lr, maxf(row_length(per_floor[f], rws[0]), row_length(per_floor[f], rws[1])))
	lr = maxf(lr, 4.0)
	var length := lr + (STAIR_BAY if floors == 2 else 0.0)
	var depth := 2.0 * ROOM_DEPTH + CORRIDOR
	var b := Builder.new(style)
	var x0 := -length / 2.0
	var z0 := -depth / 2.0
	var zc0 := z0 + ROOM_DEPTH                 # corridor north edge
	var zc1 := zc0 + CORRIDOR                  # corridor south edge
	var xr := x0 + lr                          # east end of the room rows (stair bay beyond)
	var top := BASE + floors * STOREY
	var info := {"floors": floors, "style": style_name, "roof": roof, "size": [snappedf(length, 0.01), snappedf(depth, 0.01)],
		"storey": STOREY, "rooms": [], "front_door": [], "facing": [-1, 0, 0], "stair": {}}
	# ground slab and a porch at the front door
	b.box("floor", Vector3(x0, 0, z0), Vector3(x0 + length, BASE, z0 + depth))
	b.box("floor", Vector3(x0 - 1.4, 0, zc0 - 0.3), Vector3(x0, BASE, zc1 + 0.3))
	info.front_door = [snappedf(x0, 0.01), BASE, snappedf((zc0 + zc1) / 2.0, 0.01)]
	var stair_x0 := x0 + length - EXT - STAIR_WIDTH
	var run := RISERS * 0.28
	var stair_z1 := z0 + depth - EXT - 0.1
	var stair_z0 := stair_z1 - run
	for f in floors:
		var y := BASE + f * STOREY
		var yt := y + STOREY - SLAB            # ceiling under the next slab
		var rows: Array = layouts[f]
		var names: Array = per_floor[f]
		# outside walls: north (z0) and south (z1) span the full length; west and east fit between
		var north := []
		var south := []
		var west := []
		var east := []
		if f == 0:
			west.append({"c": (zc0 + zc1) / 2.0, "w": FRONT_DOOR_W, "y0": y, "y1": y + DOOR_H, "door": true})
		else:
			west.append(_window(y, (zc0 + zc1) / 2.0, 0.8, false))
		for r in 2:
			var row: Array = rows[r]
			var x := x0
			var rz0 := z0 if r == 0 else zc1
			var rz1 := zc0 if r == 0 else z0 + depth
			for k in row.size():
				var i: int = row[k]
				var kind: String = names[i]
				var w: float = TYPES[kind]
				if k == row.size() - 1:
					w = xr - x                     # the last room fills the row
				var cx := x + w / 2.0
				var wins := 2 if w >= 4.6 else 1
				var room_wins := []          # for the sidecar: furniture keeps out of them (an internal task)
				for j in wins:
					var wc := x + w * (j + 1) / (wins + 1)
					(north if r == 0 else south).append(_window(y, wc, 0.6 if kind == "bath" else 1.2, kind == "bath"))
					room_wins.append(_side_window("north" if r == 0 else "south", wc, 0.6 if kind == "bath" else 1.2, kind == "bath"))
				if k == 0:
					west.append(_window(y, (rz0 + rz1) / 2.0, 0.6 if kind == "bath" else 1.0, kind == "bath"))
					room_wins.append(_side_window("west", (rz0 + rz1) / 2.0, 0.6 if kind == "bath" else 1.0, kind == "bath"))
				if k == row.size() - 1 and floors == 1:
					east.append(_window(y, (rz0 + rz1) / 2.0, 0.6 if kind == "bath" else 1.0, kind == "bath"))
					room_wins.append(_side_window("east", (rz0 + rz1) / 2.0, 0.6 if kind == "bath" else 1.0, kind == "bath"))
				# partition to the next room (along z), from the outside wall to the corridor wall
				if k < row.size() - 1:
					var zi0 := (rz0 + EXT) if r == 0 else (zc1 + INT / 2.0)
					var zi1 := (zc0 - INT / 2.0) if r == 0 else (rz1 - EXT)
					b.wall_z("wall", x + w, zi0, zi1, INT, y, yt, [])
				var door_z := zc0 if r == 0 else zc1
				var dc := clampf(cx, x + DOOR_W / 2.0 + 0.25, x + w - DOOR_W / 2.0 - 0.25)
				info.rooms.append({"name": "%s_%d" % [kind, info.rooms.size() + 1], "type": kind, "floor": f,
					"rect": [snappedf(x, 0.01), snappedf(rz0, 0.01), snappedf(x + w, 0.01), snappedf(rz1, 0.01)],
					"door": [snappedf(dc, 0.01), snappedf(y, 0.01), snappedf(door_z, 0.01)], "windows": room_wins})
				x += w
			# the rows' east ends: a wall to the stair bay
			if floors == 2:
				var ze0 := (rz0 + EXT) if r == 0 else (zc1 + INT / 2.0)
				var ze1 := (zc0 - INT / 2.0) if r == 0 else (rz1 - EXT)
				b.wall_z("wall", xr, ze0, ze1, INT, y, yt, [])
		# corridor walls (along x) with one doorway per room
		for r in 2:
			var openings := []
			for room in info.rooms:
				if room.floor == f and is_equal_approx(room.door[2], zc0 if r == 0 else zc1):
					openings.append({"c": room.door[0], "w": DOOR_W, "y0": y, "y1": y + DOOR_H, "door": true})
			b.wall_x("wall", zc0 if r == 0 else zc1, x0 + EXT, xr + (INT / 2.0 if floors == 2 else -EXT), INT, y, yt, openings)
		# stair bay windows
		if floors == 2:
			south.append(_window(y, xr + STAIR_BAY / 2.0 - 0.5, 1.0, false))
			east.append(_window(y, (zc0 + z0) / 2.0, 1.0, false))
		# outside walls, floor height to the next floor (slab edge included)
		var y_hi := y + STOREY if f < floors - 1 else top
		b.wall_x("wall", z0 + EXT / 2.0, x0, x0 + length, EXT, y, y_hi, north)
		b.wall_x("wall", z0 + depth - EXT / 2.0, x0, x0 + length, EXT, y, y_hi, south)
		b.wall_z("wall", x0 + EXT / 2.0, z0 + EXT, z0 + depth - EXT, EXT, y, y_hi, west)
		b.wall_z("wall", x0 + length - EXT / 2.0, z0 + EXT, z0 + depth - EXT, EXT, y, y_hi, east)
		# the slab above this floor (with the stair opening when a floor follows)
		var inner_min := Vector3(x0 + EXT, yt, z0 + EXT)
		var inner_max := Vector3(x0 + length - EXT, yt + SLAB, z0 + depth - EXT)
		if f < floors - 1:
			b.slab_with_hole("floor", inner_min, inner_max,
				Rect2(stair_x0 - STAIR_HOLE_OVERHANG, stair_z0, STAIR_WIDTH + STAIR_HOLE_OVERHANG, run))
		elif roof == "gable":
			b.box("floor", inner_min, inner_max)          # ceiling under the roof
	# stair: solid steps up the east wall, south to north
	if floors == 2:
		var rise := STOREY / RISERS
		for s in RISERS:
			var za := stair_z1 - (s + 1) * 0.28
			b.box("stair", Vector3(stair_x0, BASE, za), Vector3(stair_x0 + STAIR_WIDTH, BASE + (s + 1) * rise, za + 0.28))
		# rail along the opening's west side upstairs (moved with the widened opening)
		var yr := BASE + STOREY
		var rail_x1 := stair_x0 - STAIR_HOLE_OVERHANG
		b.box("trim", Vector3(rail_x1 - 0.05, yr, stair_z0 + 0.3), Vector3(rail_x1, yr + 1.0, stair_z1 - 0.1))
		info.stair = {"rect": [snappedf(stair_x0, 0.01), snappedf(stair_z0, 0.01), snappedf(stair_x0 + STAIR_WIDTH, 0.01), snappedf(stair_z1, 0.01)],
			"bottom": [snappedf(stair_x0 + STAIR_WIDTH / 2.0, 0.01), BASE, snappedf(stair_z1, 0.01)],
			"top": [snappedf(stair_x0 + STAIR_WIDTH / 2.0, 0.01), BASE + STOREY, snappedf(stair_z0, 0.01)]}
	# roof
	if roof == "flat":
		b.box("roof", Vector3(x0, top, z0), Vector3(x0 + length, top + 0.25, z0 + depth))
		b.box("trim", Vector3(x0, top + 0.25, z0), Vector3(x0 + length, top + 0.6, z0 + 0.15))
		b.box("trim", Vector3(x0, top + 0.25, z0 + depth - 0.15), Vector3(x0 + length, top + 0.6, z0 + depth))
		b.box("trim", Vector3(x0, top + 0.25, z0 + 0.15), Vector3(x0 + 0.15, top + 0.6, z0 + depth - 0.15))
		b.box("trim", Vector3(x0 + length - 0.15, top + 0.25, z0 + 0.15), Vector3(x0 + length, top + 0.6, z0 + depth - 0.15))
	else:
		b.gable_roof(x0, x0 + length, z0, z0 + depth, top, float(style.pitch))
	_lights(info, x0, lr, (zc0 + zc1) / 2.0, floors)
	info["triangles"] = b.triangles()
	if info.triangles > MAX_TRIANGLES:
		return {"error": "house has %d triangles (limit %d): use fewer rooms" % [info.triangles, MAX_TRIANGLES]}
	return {"mesh": b.commit(), "info": info}


## Ceiling lights along each floor's corridor (model space, scene.json "lights" entries) into
## info.lights; each room lists the lights that reach its centre in "lit_by".
static func _lights(info: Dictionary, x0: float, lr: float, zc: float, floors: int) -> void:
	var n := clampi(ceili(lr / LIGHT_SPACING), 1, MAX_LIGHTS / floors)
	var spacing := lr / n
	# reach the far corner of a room beside the corridor, halfway to the next light
	var reach := Vector2(spacing / 2.0, ROOM_DEPTH + CORRIDOR / 2.0).length() + 1.0
	var lights := []
	for f in floors:
		var y := BASE + f * STOREY + STOREY - SLAB - LIGHT_DROP
		for k in n:
			lights.append({"id": "light_%d" % (lights.size() + 1), "type": "point",
				"position": [snappedf(x0 + spacing * (k + 0.5), 0.01), snappedf(y, 0.01), snappedf(zc, 0.01)],
				"color": LIGHT_COLOR, "energy": LIGHT_ENERGY, "range": snappedf(reach, 0.1)})
	for room in info.rooms:
		var r: Array = room.rect
		var c := Vector3((r[0] + r[2]) / 2.0, BASE + room.floor * STOREY + ROOM_EYE, (r[1] + r[3]) / 2.0)
		var by := []
		for l in lights:
			var ly: float = l.position[1]
			if ly < c.y - ROOM_EYE or ly > c.y - ROOM_EYE + STOREY:
				continue   # a light on another floor: the slab between faces away from it
			if c.distance_to(Vector3(l.position[0], l.position[1], l.position[2])) <= float(l.range):
				by.append(l.id)
		room["lit_by"] = by
	info["lights"] = lights


## info.lights placed with the house: a scene.json object at `position` turned `yaw_deg` about y
## (its "rotation": [0, yaw, 0]). Ids become <prefix>_light_N. Ready for scene.json "lights".
static func scene_lights(info: Dictionary, position: Vector3, yaw_deg := 0.0, prefix := "house") -> Array:
	var xf := Transform3D(Basis(Vector3.UP, deg_to_rad(yaw_deg)), position)
	var out := []
	for l in info.get("lights", []):
		var p: Vector3 = xf * Vector3(l.position[0], l.position[1], l.position[2])
		var e: Dictionary = l.duplicate(true)
		e.id = "%s_%s" % [prefix, l.id]
		e.position = [snappedf(p.x, 0.01), snappedf(p.y, 0.01), snappedf(p.z, 0.01)]
		out.append(e)
	return out


static func _window(y: float, c: float, w: float, small: bool) -> Dictionary:
	return {"c": c, "w": w, "y0": y + (1.5 if small else 0.9), "y1": y + 2.1, "door": false}


## A room's window for the sidecar: its wall, centre along that wall (x for north/south, z for
## west/east), width, and whether it is a small high one (its sill at 1.5 m, not 0.9 m).
static func _side_window(wall: String, c: float, w: float, high: bool) -> Dictionary:
	return {"wall": wall, "c": snappedf(c, 0.01), "w": w, "high": high}


## Builds and writes <out>.glb and <out>.rooms.json. Returns 0 on success.
static func export(out: String, o: Dictionary) -> int:
	var got := build(o)
	if got.has("error"):
		printerr("ERROR ", got.error)
		return 2
	var root := Node3D.new()
	root.name = "House"
	var mi := MeshInstance3D.new()
	mi.name = "Building"
	mi.mesh = got.mesh
	root.add_child(mi)
	mi.owner = root
	var info: Dictionary = got.info
	if String(o.get("furnish", "false")) != "false":
		# loaded only when asked for, so tests of the bare house need no catalogue (an internal task)
		var furn: Variant = load("res://scripts/kit/kit_house_furnish.gd").furnish(root, info)
		if furn is String:
			printerr("ERROR ", furn)
			root.free()
			return 2
		info["furnished"] = true
		info.triangles = int(info.triangles) + int(furn)
		if info.triangles > MAX_TRIANGLES:
			printerr("ERROR furnished house has %d triangles (limit %d): use fewer rooms" % [info.triangles, MAX_TRIANGLES])
			root.free()
			return 2
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	if doc.append_from_scene(root, st) != OK:
		printerr("ERROR could not convert the house")
		root.free()
		return 1
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out).get_base_dir())
	var err := doc.write_to_filesystem(st, out)
	root.free()
	if err != OK:
		printerr("ERROR could not write ", out)
		return 1
	var side := out.get_basename() + ".rooms.json"
	var fa := FileAccess.open(side, FileAccess.WRITE)
	if fa == null:
		printerr("ERROR could not write ", side)
		return 1
	fa.store_string(JSON.stringify(info, " ") + "\n")
	fa.close()
	print("HOUSE %s %d bytes %d triangles door %s facing %s floors %d rooms %d size %sx%s lights %d (rooms and lights: %s)" % [out,
		FileAccess.get_file_as_bytes(out).size(), info.triangles, info.front_door, info.facing, info.floors,
		info.rooms.size(), info.size[0], info.size[1], info.lights.size(), side.get_file()])
	for room: Dictionary in info.rooms:
		if room.has("unplaced"):
			print("WARN %s: no room for %s (it stays unfurnished there; place it yourself or use a bigger room)" % [room.name, ", ".join(room.unplaced)])
	return 0


## Boxes and quads into one surface per material, Godot winding (clockwise front faces).
class Builder:
	var tools := {}
	var mats := {}
	var tris := 0
	var style: Dictionary

	func _init(s: Dictionary) -> void:
		style = s

	func _tool(mat: String) -> SurfaceTool:
		if not tools.has(mat):
			var t := SurfaceTool.new()
			t.begin(Mesh.PRIMITIVE_TRIANGLES)
			var m := StandardMaterial3D.new()
			m.resource_name = "house_" + mat
			if mat == "glass":
				m.albedo_color = GLASS
				m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
				m.roughness = 0.1
			else:
				m.albedo_color = style[mat]
				m.roughness = 0.85
			t.set_material(m)
			tools[mat] = t
		return tools[mat]

	## a, b, c, d counter-clockwise seen from the side the normal points to.
	func quad(mat: String, a: Vector3, b: Vector3, c: Vector3, d: Vector3, n: Vector3) -> void:
		tri(mat, a, b, c, n)
		tri(mat, a, c, d, n)

	## a, b, c counter-clockwise seen from outside; emitted clockwise for Godot.
	func tri(mat: String, a: Vector3, b: Vector3, c: Vector3, n: Vector3) -> void:
		var t := _tool(mat)
		var u := n.cross(Vector3.UP if absf(n.y) < 0.9 else Vector3.RIGHT).normalized()
		var v := n.cross(u)
		for p in [a, c, b]:
			t.set_normal(n)
			t.set_uv(Vector2(p.dot(u), p.dot(v)))
			t.add_vertex(p)
		tris += 1

	func box(mat: String, lo: Vector3, hi: Vector3) -> void:
		if hi.x - lo.x < 0.001 or hi.y - lo.y < 0.001 or hi.z - lo.z < 0.001:
			return
		var p := [Vector3(lo.x, lo.y, lo.z), Vector3(hi.x, lo.y, lo.z), Vector3(hi.x, hi.y, lo.z), Vector3(lo.x, hi.y, lo.z),
			Vector3(lo.x, lo.y, hi.z), Vector3(hi.x, lo.y, hi.z), Vector3(hi.x, hi.y, hi.z), Vector3(lo.x, hi.y, hi.z)]
		quad(mat, p[1], p[0], p[3], p[2], Vector3.FORWARD)   # -z
		quad(mat, p[4], p[5], p[6], p[7], Vector3.BACK)      # +z
		quad(mat, p[0], p[4], p[7], p[3], Vector3.LEFT)      # -x
		quad(mat, p[5], p[1], p[2], p[6], Vector3.RIGHT)     # +x
		quad(mat, p[3], p[7], p[6], p[2], Vector3.UP)        # +y
		if lo.y > 0.001:
			quad(mat, p[0], p[1], p[5], p[4], Vector3.DOWN)  # -y (not under the ground slab)

	## A wall along x at z (centre line), from xa to xb, thickness t, y0..y1, with openings
	## [{c, w, y0, y1, door}] centred along x. Windows get glass and a sill.
	func wall_x(mat: String, z: float, xa: float, xb: float, t: float, y0: float, y1: float, openings: Array) -> void:
		_wall(mat, true, z, xa, xb, t, y0, y1, openings)

	func wall_z(mat: String, x: float, za: float, zb: float, t: float, y0: float, y1: float, openings: Array) -> void:
		_wall(mat, false, x, za, zb, t, y0, y1, openings)

	func _wall(mat: String, along_x: bool, at: float, a: float, b: float, t: float, y0: float, y1: float, openings: Array) -> void:
		var ops := openings.duplicate()
		ops.sort_custom(func(p, q): return p.c < q.c)
		var cur := a
		for o in ops:
			var oa: float = maxf(o.c - o.w / 2.0, a)
			var ob: float = minf(o.c + o.w / 2.0, b)
			if ob <= oa:
				continue
			_piece(mat, along_x, at, t, cur, oa, y0, y1)
			_piece(mat, along_x, at, t, oa, ob, y0, o.y0)
			_piece(mat, along_x, at, t, oa, ob, o.y1, y1)
			if not o.door:
				_piece("glass", along_x, at, 0.03, oa, ob, o.y0, o.y1)
				_piece("trim", along_x, at, t + 0.08, oa - 0.05, ob + 0.05, o.y0 - 0.06, o.y0)
			cur = ob
		_piece(mat, along_x, at, t, cur, b, y0, y1)

	func _piece(mat: String, along_x: bool, at: float, t: float, a: float, b: float, y0: float, y1: float) -> void:
		if b - a < 0.001 or y1 - y0 < 0.001:
			return
		if along_x:
			box(mat, Vector3(a, y0, at - t / 2.0), Vector3(b, y1, at + t / 2.0))
		else:
			box(mat, Vector3(at - t / 2.0, y0, a), Vector3(at + t / 2.0, y1, b))

	## A slab with one rectangular hole (x, z in the rect), as up to four boxes.
	func slab_with_hole(mat: String, lo: Vector3, hi: Vector3, hole: Rect2) -> void:
		var hx0 := clampf(hole.position.x, lo.x, hi.x)
		var hx1 := clampf(hole.end.x, lo.x, hi.x)
		var hz0 := clampf(hole.position.y, lo.z, hi.z)
		var hz1 := clampf(hole.end.y, lo.z, hi.z)
		box(mat, lo, Vector3(hi.x, hi.y, hz0))
		box(mat, Vector3(lo.x, lo.y, hz1), hi)
		box(mat, Vector3(lo.x, lo.y, hz0), Vector3(hx0, hi.y, hz1))
		box(mat, Vector3(hx1, lo.y, hz0), Vector3(hi.x, hi.y, hz1))

	## Ridge along x; eaves overhang 0.4 m; gable ends in the wall material.
	func gable_roof(xa: float, xb: float, za: float, zb: float, y: float, pitch: float) -> void:
		var o := 0.4
		var th := 0.12
		var half := (zb - za) / 2.0
		var zm := (za + zb) / 2.0
		var k := tan(deg_to_rad(pitch))
		var ridge := y + half * k
		var eave := y - o * k
		# gable triangles flush with the end walls
		tri("wall", Vector3(xa, y, za), Vector3(xa, y, zb), Vector3(xa, ridge, zm), Vector3.LEFT)
		tri("wall", Vector3(xb, y, zb), Vector3(xb, y, za), Vector3(xb, ridge, zm), Vector3.RIGHT)
		for side: float in [-1.0, 1.0]:
			var ze := zm + side * (half + o)
			var n := Vector3(0, 1, side * k).normalized()
			var lift := Vector3(0, th, 0)
			var r0 := Vector3(xa - o, ridge, zm)
			var r1 := Vector3(xb + o, ridge, zm)
			var e0 := Vector3(xa - o, eave, ze)
			var e1 := Vector3(xb + o, eave, ze)
			if side > 0:
				quad("roof", e0 + lift, e1 + lift, r1 + lift, r0 + lift, n)          # top
				quad("roof", e0, r0, r1, e1, -n)                                      # underside
				quad("roof", e0, e1, e1 + lift, e0 + lift, Vector3.BACK)               # eave edge
			else:
				quad("roof", e1 + lift, e0 + lift, r0 + lift, r1 + lift, n)
				quad("roof", e1, r1, r0, e0, -n)
				quad("roof", e1, e0, e0 + lift, e1 + lift, Vector3.FORWARD)
			var sx := Vector3(1, 0, 0)
			if side > 0:
				quad("roof", e0, e0 + lift, r0 + lift, r0, -sx)
				quad("roof", r1, r1 + lift, e1 + lift, e1, sx)
			else:
				quad("roof", r0, r0 + lift, e0 + lift, e0, -sx)
				quad("roof", e1, e1 + lift, r1 + lift, r1, sx)

	func triangles() -> int:
		return tris

	func commit() -> ArrayMesh:
		var mesh := ArrayMesh.new()
		for mat in ["floor", "wall", "trim", "stair", "roof", "glass"]:
			if tools.has(mat):
				var t: SurfaceTool = tools[mat]
				t.index()
				t.commit(mesh)
		return mesh
