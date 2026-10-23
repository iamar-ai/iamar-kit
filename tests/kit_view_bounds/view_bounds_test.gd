extends SceneTree
## ViewBounds (scripts/kit/view_bounds.gd): the automatic preview/perf views frame
## the objects, not a big sea or terrain (harbour blind test gap G12).
## Run with tests/kit_view_bounds/run.sh (headless, a throwaway stub project).

const ViewBounds = preload("res://view_bounds.gd")
var _fails := 0


func _check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ") + what)
	if not ok:
		_fails += 1


func _mesh(parent: Node, name: String, mesh: Mesh, pos: Vector3) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = name
	mi.mesh = mesh
	mi.position = pos
	parent.add_child(mi)
	return mi


func _box(size: Vector3) -> BoxMesh:
	var b := BoxMesh.new()
	b.size = size
	return b


func _plane(size: Vector2) -> PlaneMesh:
	var p := PlaneMesh.new()
	p.size = size
	return p


func _world() -> Node3D:
	var w := Node3D.new()
	root.add_child(w)
	return w


func _process(_delta: float) -> bool:
	# first frame: the root is inside the tree, so global transforms are real
	_run()
	return true


func _run() -> void:
	var spawn := Vector3(-20, 0, 0)

	# 1. the harbour case: a 2400 x 2000 m sea, a 320 m terrain, two houses, a rug
	var w := _world()
	var water := Node3D.new()
	water.name = "Water"
	w.add_child(water)
	_mesh(water, "Water_harbour", _plane(Vector2(2400, 2000)), Vector3(0, -1, -340))
	_mesh(w, "Terrain", _box(Vector3(320, 30, 320)), Vector3(0, 10, -20))
	_mesh(w, "Sea", _box(Vector3(2000, 0.1, 2000)), Vector3(0, -1, 0))   # a sea modelled in a .glb
	_mesh(w, "Bay", _plane(Vector2(1500, 1500)), Vector3(0, 0, 400))   # a wide plane primitive
	_mesh(w, "Sign", _plane(Vector2(2, 1)), Vector3(-30, 0, 10))   # a small plane primitive: kept
	_mesh(w, "HouseA", _box(Vector3(10, 8, 10)), Vector3(0, 4, 0))
	_mesh(w, "HouseB", _box(Vector3(10, 8, 10)), Vector3(40, 4, 30))
	_mesh(w, "Rug", _box(Vector3(3, 0.05, 3)), Vector3(100, 0, 0))   # flat but small: kept
	var hidden := _mesh(w, "FarHidden", _box(Vector3(5, 5, 5)), Vector3(900, 0, 900))
	hidden.visible = false
	var box := ViewBounds.frame_box(w, spawn)
	_check(box.has_point(Vector3(0, 4, 0)) and box.has_point(Vector3(40, 4, 30)), "houses inside")
	_check(box.grow(0.01).has_point(spawn), "spawn inside")
	_check(box.has_point(Vector3(100, 0, 0)), "small flat rug kept")
	_check(box.grow(0.01).has_point(Vector3(-30, 0, 10)), "small plane primitive kept")
	_check(not box.has_point(Vector3(0, 0, 400)), "wide plane primitive left out")
	_check(not box.has_point(Vector3(0, -1, -340)), "sea plane centre left out")
	_check(box.size.x < 140.0 and box.size.z < 50.0, "box spans the objects (%s)" % box.size)
	var views := ViewBounds.ring_views(box)
	_check(views.size() == 5 and views[4][0] == "above", "four around views and one above")
	var near := true
	for v in views:
		var d: float = (v[1] as Vector3).distance_to(v[2])
		near = near and d < 200.0
	_check(near, "every automatic camera within 200 m of what it looks at")
	w.queue_free()

	# 2. only ground: keep the ground box (a terrain-only world still gets views)
	var g := _world()
	_mesh(g, "Terrain", _box(Vector3(200, 20, 200)), Vector3.ZERO)
	var gb := ViewBounds.frame_box(g, Vector3.ZERO)
	_check(gb.size.x >= 199.0 and gb.size.z >= 199.0, "terrain-only world frames the terrain")
	g.queue_free()

	# 3. only flat pieces (a floor plan): framed by the flat pieces, not the water
	var f := _world()
	_mesh(f, "Floor", _box(Vector3(30, 0.2, 20)), Vector3(5, 0, 5))
	_mesh(f, "Water_pool", _plane(Vector2(600, 600)), Vector3.ZERO)
	var fb := ViewBounds.frame_box(f, Vector3(5, 0, 5))
	_check(fb.size.x < 31.0 and fb.size.z < 21.0, "flat-only world frames the floor (%s)" % fb.size)
	f.queue_free()

	# 4. empty world: a zero box at the spawn point
	var e := _world()
	var eb := ViewBounds.frame_box(e, Vector3(1, 2, 3))
	_check(eb.position == Vector3(1, 2, 3) and eb.size == Vector3.ZERO, "empty world: box at spawn")
	e.queue_free()

	# 5. world_view.gd uses it for the automatic views
	var src := FileAccess.get_file_as_string("res://world_view.gd")
	_check(src.contains('preload("res://scripts/kit/view_bounds.gd")')
		and src.contains("ViewBounds.ring_views(ViewBounds.frame_box(world, sp.origin))"),
		"world_view.gd frames its automatic views with ViewBounds")

	print("VIEW_BOUNDS %s (%d failed)" % ["PASS" if _fails == 0 else "FAIL", _fails])
	quit(1 if _fails else 0)
