extends RefCounted
## The box the automatic preview/perf views frame (scripts/kit/world_view.gd).
## Ground-like meshes are left out, so a 2 km sea or a big terrain does not push
## the cameras so far away that the views show only water or a tiny far tile
## (harbour blind test gap G12): the heightmap Terrain, the Water_* planes, and
## any flat mesh (thinner than FLAT_M, plane primitives included) more than
## WIDE_FACTOR times wider than the solid objects. The spawn point is always inside. A world with
## nothing but ground keeps the whole ground box.

const FLAT_M := 0.5        ## a mesh thinner than this (metres) is a plane
const WIDE_FACTOR := 3.0   ## a plane this many times wider than the objects is ground
const MIN_SPAN_M := 10.0   ## the objects' span never counts as less than this


static func is_ground(mi: MeshInstance3D) -> bool:
	var n := String(mi.name)
	return n == "Terrain" or n.begins_with("Water_")


static func frame_box(world: Node3D, spawn: Vector3) -> AABB:
	var solid: Array[AABB] = []
	var flat: Array[AABB] = []
	var ground: Array[AABB] = []
	for c in world.find_children("*", "MeshInstance3D", true, false):
		var mi := c as MeshInstance3D
		if mi.mesh == null or not mi.is_visible_in_tree():
			continue
		var b := mi.global_transform * mi.mesh.get_aabb()
		if is_ground(mi):
			ground.append(b)
		elif b.size.y < FLAT_M:
			flat.append(b)
		else:
			solid.append(b)
	if solid.is_empty() and flat.is_empty() and ground.is_empty():
		return AABB(spawn, Vector3.ZERO)
	var box := _merge(solid)
	if not solid.is_empty():
		var span := maxf(maxf(box.size.x, box.size.z), MIN_SPAN_M) * WIDE_FACTOR
		for b in flat:
			if maxf(b.size.x, b.size.z) <= span:
				box = box.merge(b)
	elif not flat.is_empty():
		box = _merge(flat)
	else:
		box = _merge(ground)
	return box.expand(spawn)


## The four views around the box and the one from above: [name, eye, target].
static func ring_views(box: AABB) -> Array:
	var views := []
	var c := box.get_center()
	var r := maxf(box.size.x, box.size.z) * 0.55
	for k in 4:
		var a := PI * 0.25 + k * PI * 0.5
		views.append(["around%d" % k, c + Vector3(cos(a) * r, box.size.y * 0.35 + r * 0.25, sin(a) * r), c])
	views.append(["above", c + Vector3(0.01, maxf(r * 1.6, box.size.y + 10.0), 0), c])
	return views


static func _merge(boxes: Array[AABB]) -> AABB:
	var box := AABB()
	for i in boxes.size():
		box = boxes[i] if i == 0 else box.merge(boxes[i])
	return box
