extends SceneTree
## Places raw village-kit pieces around a test footprint to learn their conventions.
## godot --path . -s res://tools/kit_test.gd -- /tmp/out yaw_deg dist
## A probe, not a test: it renders shots, so it needs a display (offscreen; never DISPLAY=:0).

const V := "res://assets/village/"
var _frames := 0
var _out := ""
var _yaw := 0.0
var _dist := 16.0


func _init() -> void:
	pass


func _piece(w: Node3D, name: String, pos: Vector3, rot_deg: float) -> void:
	var ps := load(V + name + ".gltf") as PackedScene
	if ps == null:
		print("MISSING ", name)
		return
	var n := ps.instantiate() as Node3D
	n.position = pos
	n.rotation_degrees.y = rot_deg
	w.add_child(n)


func _build() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 3:
		printerr("usage: -- <out dir> <yaw deg> <dist>")
		quit(2)
		return
	_out = args[0]
	_yaw = deg_to_rad(float(args[1]))
	_dist = float(args[2])
	var w := Node3D.new()
	root.add_child(w)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.5, 0.62, 0.8)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.7, 0.7, 0.75)
	w.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, 35, 0)
	sun.shadow_enabled = true
	w.add_child(sun)
	var g := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(40, 40)
	g.mesh = pm
	w.add_child(g)
	# 3 x 2 cells (6 m x 4 m), front = +Z
	var cw := 3
	var cd := 2
	var G := 2.0
	var hx := cw * G * 0.5
	var hz := cd * G * 0.5
	for i in cw:
		var x := -hx + G * (i + 0.5)
		_piece(w, "Wall_UnevenBrick_Door_Round" if i == 1 else "Wall_UnevenBrick_Window_Wide_Round", Vector3(x, 0, hz), 0)
		if i != 1:
			_piece(w, "Window_Wide_Round1", Vector3(x, 0, hz), 0)
		_piece(w, "Wall_UnevenBrick_Straight", Vector3(x, 0, -hz), 180)
		_piece(w, "Wall_Plaster_Window_Wide_Round" if i != 1 else "Wall_Plaster_Straight", Vector3(x, 3.12, hz), 0)
		if i != 1:
			_piece(w, "Window_Wide_Round1", Vector3(x, 3.12, hz), 0)
		_piece(w, "Wall_Plaster_Window_Wide_Round", Vector3(x, 3.12, -hz), 180)
	_piece(w, "DoorFrame_Round_WoodDark", Vector3(0, 0, hz), 0)
	_piece(w, "Door_1_Round", Vector3(0, 0, hz), 0)
	for j in cd:
		var z := -hz + G * (j + 0.5)
		_piece(w, "Wall_UnevenBrick_Straight", Vector3(hx, 0, z), 90)
		_piece(w, "Wall_UnevenBrick_Window_Wide_Round", Vector3(-hx, 0, z), -90)
		_piece(w, "Wall_Plaster_Straight", Vector3(hx, 3.12, z), 90)
		_piece(w, "Wall_Plaster_Straight", Vector3(-hx, 3.12, z), -90)
	var corners := [[Vector3(hx, 0, hz), 0.0], [Vector3(-hx, 0, hz), -90.0], [Vector3(-hx, 0, -hz), 180.0], [Vector3(hx, 0, -hz), 90.0]]
	for c in corners:
		_piece(w, "Corner_Exterior_Brick", c[0], c[1])
		_piece(w, "Corner_Exterior_Wood", (c[0] as Vector3) + Vector3(0, 3.12, 0), c[1])
	_piece(w, "Roof_RoundTiles_4x6", Vector3(0, 6.24, 0), 90)
	_piece(w, "Roof_Front_Brick4", Vector3(hx, 6.24, 0), 90)
	_piece(w, "Roof_Front_Brick4", Vector3(-hx, 6.24, 0), -90)
	_piece(w, "Prop_Chimney", Vector3(hx - 1.0, 6.24, -1.0), 0)
	for i in cw:
		_piece(w, "Wall_BottomCover", Vector3(-hx + G * (i + 0.5), 3.12, hz), 0)
		_piece(w, "Wall_BottomCover", Vector3(-hx + G * (i + 0.5), 3.12, -hz), 180)
	_piece(w, "Stairs_Exterior_Straight", Vector3(0, 0, hz + 1.0), 0)
	var cam := Camera3D.new()
	w.add_child(cam)
	cam.fov = 50
	var cp := Vector3(sin(_yaw) * _dist, 6.0, cos(_yaw) * _dist)
	cam.look_at_from_position(cp, Vector3(0, 3.5, 0))


func _process(_d: float) -> bool:
	_frames += 1
	if _frames == 2:
		_build()
	if _frames == 30:
		root.get_texture().get_image().save_png(_out + ".png")
		return true
	return false
