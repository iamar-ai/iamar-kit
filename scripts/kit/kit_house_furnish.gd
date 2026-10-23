extends RefCounted
## Furniture for a house from rooms (an internal task): `--furnish` on
##   iamar-world assets building house <out.glb> --rooms bedroom:3,living,kitchen,bath:2 --furnish
## places catalogue furniture (kit/catalog/assets) in every room by its type, from the plan
## KitHouseRooms.build() returns: a bed, wardrobe and rug in a bedroom, a sofa, rug, armchair and
## bookshelf in the living room, a counter and dresser in the kitchen, a bath in a bathroom...
## Each piece stands on its room's floor with its back to a wall, facing into the room, clear of
## the doorway (a 1.3 m apron inside it), of the other pieces and, when it is taller than a
## window sill, of the windows in the wall behind it. The pieces go into the house's glTF as
## their own nodes (one object, "collision": "mesh" covers them) and each room in the sidecar
## lists what it got in "furniture" (and "unplaced" for what did not fit).
## Plain Godot only (no browser classes), so a throwaway project can test it.

## Per room type: [catalogue file under assets/, where it goes, optional]. "back": against the outside
## wall (else a side wall); "side": against a side wall (else the back wall); "middle": free
## standing, nearest the room's middle; "flat": a rug, centred (may run under other pieces).
## An optional piece that does not fit is left out quietly (the room lists it in "skipped");
## a missing main piece is listed in "unplaced" and the command WARNs.
const ITEMS := {
	"bedroom": [["furniture/cot_bed.glb", "back"], ["coastal/wardrobe.glb", "side"], ["coastal/rug.glb", "flat"]],
	"living": [["coastal/sofa.glb", "back"], ["coastal/rug.glb", "flat"], ["furniture/armchair.glb", "side", true],
		["furniture/bookshelf.glb", "side", true]],
	"kitchen": [["coastal/kitchen_counter.glb", "back"], ["furniture/kitchen_dresser.glb", "side", true]],
	"dining": [["furniture/trestle_table.glb", "middle"], ["furniture/kitchen_dresser.glb", "side", true]],
	"bath": [["coastal/bathtub.glb", "back"]],
	"study": [["furniture/bookshelf.glb", "side"], ["furniture/armchair.glb", "back", true], ["furniture/iron-bound_chest.glb", "side", true]],
	"laundry": [["furniture/iron-bound_chest.glb", "side"]],
}
const INSET := 0.25          # from a room's wall lines to where furniture may stand (walls are 0.12-0.2 m)
const GAP := 0.08            # between two pieces
const DOOR_APRON := 1.3      # kept clear inside a doorway, the doorway's width + 2 x DOOR_SIDE wide
const DOOR_SIDE := 0.35
const SILL := 0.95           # a piece taller than this keeps out of the windows behind it (sills are 0.9 m;
                             # a sofa back a little above one, 0.25 m off the wall, does not cover it)
const STEP := 0.05


## The catalogue folder (holding assets/): IAMAR_KIT_CATALOG, else catalog/ beside the kit
## pack (the kit zip's layout), else the checkout's kit/catalog. "" when none has the files.
static func catalog_dir() -> String:
	var tries := []
	if OS.get_environment("IAMAR_KIT_CATALOG") != "":
		tries.append(OS.get_environment("IAMAR_KIT_CATALOG"))
	if OS.get_environment("IAMAR_KIT_PACK") != "":
		tries.append(OS.get_environment("IAMAR_KIT_PACK").get_base_dir().path_join("catalog"))
	tries.append(ProjectSettings.globalize_path("res://kit/catalog"))
	tries.append(OS.get_executable_path().get_base_dir().path_join("kit/catalog"))
	for d: String in tries:
		if FileAccess.file_exists(d.path_join("assets/coastal/sofa.glb")):
			return d
	return ""


## Adds the furniture under `root` (the house node) and records it in info.rooms. Returns the
## furniture's triangle count, or an error String.
static func furnish(root: Node3D, info: Dictionary, catalog := "") -> Variant:
	if catalog == "":
		catalog = catalog_dir()
	if catalog == "":
		return "--furnish needs the kit's catalogue (catalog/assets beside iamar-world in the kit download); set IAMAR_KIT_CATALOG to that catalog folder"
	var models := {}
	var tris := 0
	var group := Node3D.new()
	group.name = "Furniture"
	root.add_child(group)
	group.owner = root
	for room: Dictionary in info.rooms:
		var placed := []      # [Rect2 footprint, solid]
		var got := []
		var missing := []
		var skipped := []
		for spec: Array in ITEMS.get(room.type, []):
			var file: String = spec[0]
			if not models.has(file):
				models[file] = _load(catalog.path_join("assets").path_join(file))
			var m: Variant = models[file]
			if m == null:
				missing.append(file.get_file().get_basename())
				continue
			var spot: Variant = place(room, m.aabb, String(spec[1]), placed)
			if spot == null:
				(skipped if spec.size() > 2 and spec[2] else missing).append(file.get_file().get_basename())
				continue
			var n := (m.node as Node3D).duplicate() as Node3D
			n.name = "%s_%s" % [room.name, file.get_file().get_basename().replace("-", "_")]
			n.transform = spot.xf
			group.add_child(n)
			_own(n, root)
			tris += int(m.triangles)
			placed.append([spot.rect, spot.solid])
			var p: Vector3 = spot.xf.origin
			got.append({"item": file.get_file().get_basename(), "asset": file, "position": [snappedf(p.x, 0.01), snappedf(p.y, 0.01), snappedf(p.z, 0.01)],
				"yaw": spot.yaw, "footprint": [snappedf(spot.rect.position.x, 0.01), snappedf(spot.rect.position.y, 0.01),
					snappedf(spot.rect.end.x, 0.01), snappedf(spot.rect.end.y, 0.01)]})
		room["furniture"] = got
		if not missing.is_empty():
			room["unplaced"] = missing
		if not skipped.is_empty():
			room["skipped"] = skipped
	for f in models:
		if models[f] != null:
			(models[f].node as Node).free()
	info["furniture_triangles"] = tris
	return tris


## Where a piece with model-space bounds `aabb` goes in `room`: {xf, rect (x, z footprint),
## yaw, solid} or null when no spot is free. `placed`: [[Rect2, solid], ...] already in the room.
static func place(room: Dictionary, aabb: AABB, how: String, placed: Array) -> Variant:
	var r: Array = room.rect
	var inner := Rect2(r[0] + INSET, r[1] + INSET, r[2] - r[0] - 2.0 * INSET, r[3] - r[1] - 2.0 * INSET)
	var door: Array = room.door
	# the outside (back) wall is the one away from the corridor doorway
	var back_low: bool = absf(float(door[2]) - float(r[3])) < absf(float(door[2]) - float(r[1]))
	var apron := Rect2(float(door[0]) - 0.45 - DOOR_SIDE, 0, 0.9 + 2.0 * DOOR_SIDE, DOOR_APRON)
	apron.position.y = float(r[3]) - DOOR_APRON if back_low else float(r[1])
	var floor_y := float(door[1])
	var solid := aabb.size.y > 0.05
	var tall := aabb.size.y > SILL
	var tries := []
	match how:
		"back": tries = ["back", "side"]
		"side": tries = ["side", "back"]
		"middle": tries = ["middle"]
		_: tries = ["flat"]
	for t: String in tries:
		for c: Dictionary in _candidates(t, inner, aabb, back_low):
			var rect: Rect2 = c.rect
			if not inner.grow(0.001).encloses(rect):
				continue
			if solid and rect.intersects(apron):
				continue
			if solid and _hits(rect, placed):
				continue
			if tall and c.has("wall") and _blocks_window(room, String(c.wall), rect):
				continue
			var yaw: float = c.yaw
			var basis := Basis(Vector3.UP, deg_to_rad(yaw))
			var centre := aabb.get_center()
			var o := Vector3(rect.get_center().x, 0, rect.get_center().y) - basis * Vector3(centre.x, 0, centre.z)
			o.y = floor_y - aabb.position.y
			return {"xf": Transform3D(basis, o), "rect": rect, "yaw": yaw, "solid": solid}
	return null


## Candidate spots, best first. A piece's front is its model's +Z (the catalogue convention).
static func _candidates(t: String, inner: Rect2, aabb: AABB, back_low: bool) -> Array:
	var out := []
	var w := aabb.size.x
	var d := aabb.size.z
	var mid := inner.get_center()
	match t:
		"back":
			# facing the corridor; centred first, then sliding out to either side
			var z := inner.position.y if back_low else inner.end.y - d
			for x in _slide(inner.position.x, inner.end.x - w, mid.x - w / 2.0):
				out.append({"rect": Rect2(x, z, w, d), "yaw": 0.0 if back_low else 180.0, "wall": "back"})
		"side":
			# against the west or east wall, facing into the room; nearest the back wall first
			var start := inner.position.y if back_low else inner.end.y - w
			for z in _slide(inner.position.y, inner.end.y - w, start):
				out.append({"rect": Rect2(inner.position.x, z, d, w), "yaw": 90.0, "wall": "west"})
				out.append({"rect": Rect2(inner.end.x - d, z, d, w), "yaw": -90.0, "wall": "east"})
		"middle":
			for z in _slide(inner.position.y, inner.end.y - d, mid.y - d / 2.0):
				for x in _slide(inner.position.x, inner.end.x - w, mid.x - w / 2.0):
					out.append({"rect": Rect2(x, z, w, d), "yaw": 0.0})
		"flat":
			out.append({"rect": Rect2(mid.x - w / 2.0, mid.y - d / 2.0, w, d), "yaw": 0.0})
			out.append({"rect": Rect2(mid.x - d / 2.0, mid.y - w / 2.0, d, w), "yaw": 90.0})
	return out


## Positions from lo to hi in STEP, nearest `best` first.
static func _slide(lo: float, hi: float, best: float) -> Array:
	if hi < lo - 0.001:
		return []
	var out := []
	var n := int(floor((hi - lo) / STEP + 0.001))
	for i in n + 1:
		out.append(lo + i * STEP)
	if hi - (lo + n * STEP) > 0.001:
		out.append(hi)
	out.sort_custom(func(a, b): return absf(a - best) < absf(b - best))
	return out


static func _hits(rect: Rect2, placed: Array) -> bool:
	for p in placed:
		if p[1] and rect.grow(GAP).intersects(p[0]):
			return true
	return false


## A tall piece against `wall` (back, west, east) covering one of the room's windows there.
static func _blocks_window(room: Dictionary, wall: String, rect: Rect2) -> bool:
	for win: Dictionary in room.get("windows", []):
		if win.get("high", false):
			continue   # a small high window (baths) clears furniture
		var on := String(win.wall)
		if wall == "back" and on in ["north", "south"]:
			if rect.position.x < float(win.c) + float(win.w) / 2.0 + 0.05 and rect.end.x > float(win.c) - float(win.w) / 2.0 - 0.05:
				return true
		elif wall == on:
			if rect.position.y < float(win.c) + float(win.w) / 2.0 + 0.05 and rect.end.y > float(win.c) - float(win.w) / 2.0 - 0.05:
				return true
	return false


## A catalogue .glb: {node, aabb (model space), triangles}, or null when it cannot be read.
static func _load(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		return null
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	if doc.append_from_file(path, st) != OK:
		return null
	var n := doc.generate_scene(st) as Node3D
	if n == null:
		return null
	n.transform = Transform3D.IDENTITY   # placement sets it; bounds are in the model's own space
	var acc := {"aabb": AABB(), "first": true, "tris": 0}
	_measure(n, Transform3D.IDENTITY, acc)
	if acc.first:
		n.free()
		return null
	return {"node": n, "aabb": acc.aabb, "triangles": acc.tris}


static func _measure(n: Node, xf: Transform3D, acc: Dictionary) -> void:
	var here := xf * (n as Node3D).transform if n is Node3D else xf
	if n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
		var mesh := (n as MeshInstance3D).mesh
		var box := here * mesh.get_aabb()
		acc.aabb = box if acc.first else (acc.aabb as AABB).merge(box)
		acc.first = false
		for s in mesh.get_surface_count():
			var arr := mesh.surface_get_arrays(s)
			var idx: Variant = arr[Mesh.ARRAY_INDEX]
			acc.tris += (idx as PackedInt32Array).size() / 3 if idx != null else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	for c in n.get_children():
		_measure(c, here, acc)


static func _own(n: Node, owner: Node) -> void:
	n.owner = owner
	for c in n.get_children():
		_own(c, owner)
