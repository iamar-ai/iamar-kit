extends SceneTree
## Writes the insects of the catalogue as glTF (kit/catalog/assets/creatures/insects/), each
## with its wing motion as animation clips, so a world plays them with scene.json
## objects "animation" (WorldBuilder loops the clip).
##
##   godot --headless --path <the iamar browser source (not public) checkout> -s <iamar-kit>/kit/catalog/assets/export_insects.gd
##   (then: python3 kit/catalog/assets/insects.py record && python3 kit/catalog/catalog.py build)
##
## Butterflies: the city's own (the iamar browser source (not public) scripts/world/butterflies.gd, a025eeba). There the
## six species are one MultiMesh whose shader (shaders/butterfly.gdshader) hinges the wing
## quads on the body axis from per-instance custom data, and scripts/world/butterfly_motion.gd
## drives the angles. A glTF cannot carry that shader, so each wing here is its own node on
## the same hinge, the shader's two-sided atlas lookup becomes two windings with their own UVs,
## and butterfly_motion.gd's poses become clips sampled from the same formulas:
##   flap   powered wingbeat at the species' rate (fore 0.42 + 0.98 sin, hind 0.42 + 0.9 sin(-0.35))
##   glide  wings held at 0.30 / 0.33 rad
##   rest   perched: slow bask, wings opening by the species' bask share (closed at 1.48 rad)
## Size as drawn in the city (Butterflies.LEN 0.045 m wing x species size); texture: the
## species' row of assets/butterflies/atlas.png (tools/make_butterfly_atlas.py).
##
## Bumblebee and dragonfly: the city has none as models (bees are a sound in MpSoundscape,
## dragonflies glowing motes in Waterworks), so they are built here in the same way: octagonal
## tubes in vertex colour, two-sided flat wings on hinge nodes, clips fly / rest.

const OUT_REL := "catalog/assets/creatures/insects"
const LEN := 0.045   ## Butterflies.LEN
## Godot's glTF import (the browser's WorldPackage too) resamples clips at 30 frames a second,
## so a stroke faster than 15 Hz aliases away (a 15 Hz sine sampled at 30 fps is all zeros).
## Fast wings therefore flick between two poses on every clip frame (15 Hz, a buzz at any
## frame rate) and the clips last whole frames, so the loop has no seam.
const CLIP_FPS := 30.0
const BUZZ_HZ := 15.0
const BUZZ_LEN := 0.4    ## s: 12 frames, 6 strokes, one body bob

## [file, species name, size, wingbeat Hz, glide share, bask share, atlas row] (Butterflies.SPECIES)
const BUTTERFLIES := [
	["butterfly_small_white", "small white", 0.95, 3.8, 0.12, 0.25, 0],
	["butterfly_brimstone", "brimstone", 1.1, 3.2, 0.18, 0.0, 1],
	["butterfly_small_tortoiseshell", "small tortoiseshell", 0.95, 4.2, 0.35, 0.85, 2],
	["butterfly_common_blue", "common blue", 0.7, 4.4, 0.1, 0.6, 3],
	["butterfly_peacock", "peacock", 1.12, 3.6, 0.4, 0.9, 4],
	["butterfly_red_admiral", "red admiral", 1.18, 3.4, 0.45, 0.75, 5],
]

var _kit := ""
var _pal: Array = []   ## the body colours of the insect being built (see _pal_uv)


func _init() -> void:
	# this file is <kit repo>/kit/catalog/assets/export_insects.gd
	_kit = (get_script() as Script).resource_path.get_base_dir().get_base_dir().get_base_dir()
	if OS.get_environment("IAMAR_KIT_ROOT") != "":
		_kit = OS.get_environment("IAMAR_KIT_ROOT").path_join("kit")
	_run.call_deferred()


func _run() -> void:
	var out := _kit.path_join(OUT_REL)
	DirAccess.make_dir_recursive_absolute(out)
	var atlas := Image.load_from_file(ProjectSettings.globalize_path("res://assets/butterflies/atlas.png"))
	if atlas == null or atlas.is_empty():
		push_error("export_insects: res://assets/butterflies/atlas.png not found: run from an the iamar browser source (not public) checkout (--path)")
		quit(1)
		return
	var ok := true
	for sp in BUTTERFLIES:
		ok = _write(_butterfly(sp, atlas), out.path_join(String(sp[0]) + ".glb")) and ok
	ok = _write(_bumblebee(), out.path_join("bumblebee.glb")) and ok
	ok = _write(_dragonfly(), out.path_join("dragonfly.glb")) and ok
	quit(0 if ok else 1)


func _write(root: Node3D, path: String) -> bool:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_scene(root, state)
	if err == OK:
		err = doc.write_to_filesystem(state, path)
	print("%s %s" % ["wrote" if err == OK else "FAILED (%d)" % err, path])
	root.free()
	_pal = []
	return err == OK


# ------------------------------------------------------------------ butterflies

func _butterfly(sp: Array, atlas: Image) -> Node3D:
	var s: float = LEN * float(sp[2])
	var row: int = sp[6]
	var cell := atlas.get_width() / 4
	var tex := atlas.get_region(Rect2i(0, row * cell, atlas.get_width(), cell))
	var wing_mat := StandardMaterial3D.new()
	wing_mat.resource_name = "wings"
	wing_mat.albedo_texture = ImageTexture.create_from_image(tex)
	wing_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	wing_mat.alpha_scissor_threshold = 0.5
	wing_mat.roughness = 0.75
	var root := Node3D.new()
	root.name = String(sp[0])
	var rig := Node3D.new()
	rig.name = "Rig"
	rig.position.y = 0.08 * s   # the body's belly sits on the origin (a perch or the ground)
	root.add_child(rig)
	var body := MeshInstance3D.new()
	body.name = "Body"
	body.mesh = _butterfly_body(s)
	rig.add_child(body)
	# forewing cell: v 0..1 -> z -0.62..+0.42; hindwing: z -0.12..+0.78 (Butterflies._build_mesh)
	for side in [1.0, -1.0]:
		for fore in [true, false]:
			var w := MeshInstance3D.new()
			w.name = "Wing%s%s" % ["F" if fore else "H", "R" if side > 0.0 else "L"]
			if fore:
				w.mesh = _butterfly_wing(s, side, 1.0, -0.62, 1.04, 0, 0.0, wing_mat)
			else:
				w.mesh = _butterfly_wing(s, side, 0.86, -0.12, 0.9, 1, -0.004, wing_mat)
			rig.add_child(w)
	var hz: float = sp[3]
	var bask: float = sp[5]
	var lib := AnimationLibrary.new()
	# flap: one wingbeat (butterfly_motion.gd powered stroke)
	var period := 1.0 / hz
	var at := rig.position
	lib.add_animation("flap", _wing_clip(period, 16, func(t: float) -> Array:
		var ph := TAU * t / period
		return [Vector2(0.42 + 0.98 * sin(ph), 0.42 + 0.9 * sin(ph - 0.35)), at]))
	lib.add_animation("glide", _wing_clip(1.0, 1, func(_t: float) -> Array: return [Vector2(0.3, 0.33), at]))
	# rest: perched; basks open and closed over one 0.7 rad/s cycle (closed when bask is 0)
	var rest_len := TAU / 0.7
	lib.add_animation("rest", _wing_clip(rest_len, 24, func(t: float) -> Array:
		var c := sin(t * 0.7) * 0.5 + 0.5
		var open := smoothstep(1.0 - bask, 1.0, c) if bask > 0.0 else 0.0
		var f := lerpf(1.48, 0.06, open)
		return [Vector2(f, f - 0.05), at]))
	_add_player(root, lib)
	return root


func _butterfly_body(s: float) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	# Butterflies._build_mesh's body; its shader shades it (r, 0.85 r, 0.72 r) from the colour
	var dark := _shade(0.09)
	var furry := _shade(0.16)
	_tube(st, s, [[-0.36, 0.0], [-0.34, 0.045], [-0.3, 0.06], [-0.26, 0.05]], dark)
	_tube(st, s, [[-0.27, 0.05], [-0.22, 0.075], [-0.08, 0.08], [0.06, 0.065], [0.1, 0.05]], furry)
	_tube(st, s, [[0.09, 0.05], [0.18, 0.052], [0.36, 0.042], [0.52, 0.026], [0.6, 0.0]], dark)
	for side in [1.0, -1.0]:
		var a := Vector3(0.02 * side, 0.03, -0.35)
		var b := Vector3(0.16 * side, 0.13, -0.78)
		_stick(st, s, a, b, 0.008, dark)
		_stick(st, s, b - (b - a).normalized() * 0.06, b + (b - a).normalized() * 0.01, 0.02, dark)
	var m := st.commit()
	m.surface_set_material(0, _pal_material())
	return m


static func _shade(r: float) -> Color:
	return Color(r, r * 0.85, r * 0.72)


## One wing, both faces. butterfly.gdshader picks atlas columns 0/1 (forewing, hindwing top)
## or 2/3 (underside) by FRONT_FACING with culling off; here each face is its own winding:
## seen from above the top columns, from below the underside.
func _butterfly_wing(s: float, side: float, w: float, z0: float, d: float, col: int, y: float, mat: Material) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n := 4
	for face in [0, 1]:
		var c := col + (0 if face == 0 else 2)
		var up := Vector3.UP if face == 0 else Vector3.DOWN
		for i in n:
			var u0 := float(i) / n
			var u1 := float(i + 1) / n
			var q := [Vector3(u0 * w * side, y, z0), Vector3(u1 * w * side, y, z0), Vector3(u1 * w * side, y, z0 + d), Vector3(u0 * w * side, y, z0 + d)]
			var uv := [Vector2(u0, 0), Vector2(u1, 0), Vector2(u1, 1), Vector2(u0, 1)]
			for tri in [[0, 1, 2], [0, 2, 3]]:
				var vs := []
				var us := []
				for k in tri:
					vs.append((q[k] as Vector3) * s)
					var p: Vector2 = uv[k]
					us.append(Vector2((c + clampf(p.x, 0.01, 0.99)) / 4.0, clampf(p.y, 0.01, 0.99)))
				_face(st, vs, [up, up, up], up, us)
	var m := st.commit()
	m.surface_set_material(0, mat)
	return m


# ------------------------------------------------------------------ bumblebee

func _bumblebee() -> Node3D:
	var root := Node3D.new()
	root.name = "bumblebee"
	var rig := Node3D.new()
	rig.name = "Rig"
	rig.position.y = 0.0062   # standing on its legs
	root.add_child(rig)
	var black := Color(0.06, 0.055, 0.05)
	var yellow := Color(0.93, 0.72, 0.16)
	var white := Color(0.92, 0.9, 0.82)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	# metres; head at -Z. A bumblebee about 2 cm long, fur bands in vertex colour.
	_tube(st, 1.0, [[-0.0105, 0.0], [-0.0098, 0.0026], [-0.0085, 0.0034], [-0.0068, 0.0028]], black)
	_tube(st, 1.0, [[-0.0072, 0.0032], [-0.0058, 0.0048], [-0.0036, 0.0054]], yellow)
	_tube(st, 1.0, [[-0.0036, 0.0054], [-0.0012, 0.0052], [0.0004, 0.0044]], black)
	_tube(st, 1.0, [[0.0, 0.0046], [0.0022, 0.006], [0.0042, 0.0063]], yellow)
	_tube(st, 1.0, [[0.0042, 0.0063], [0.0068, 0.006]], black)
	_tube(st, 1.0, [[0.0068, 0.006], [0.0088, 0.0048], [0.0102, 0.0024], [0.0108, 0.0]], white)
	for side in [1.0, -1.0]:
		_stick(st, 1.0, Vector3(0.001 * side, 0.0012, -0.0098), Vector3(0.0028 * side, 0.0048, -0.0132), 0.0003, black)
		for k in 3:
			var z := -0.0052 + k * 0.0026
			var hip := Vector3(0.0022 * side, -0.003, z)
			var knee := Vector3(0.0056 * side, -0.0035, z + 0.0006 * (k - 1))
			_stick(st, 1.0, hip, knee, 0.00035, black)
			_stick(st, 1.0, knee, Vector3(0.0068 * side, -0.0062, z + 0.0012 * (k - 1)), 0.0003, black)
	var body := MeshInstance3D.new()
	body.name = "Body"
	var bm := st.commit()
	bm.surface_set_material(0, _pal_material())
	body.mesh = bm
	rig.add_child(body)
	var wm := _glass_material(Color(0.82, 0.86, 0.92, 0.38))
	# wings on hinges at the thorax top, swept back over the abdomen
	for side in [1.0, -1.0]:
		_add_wing(rig, "WingF" + ("R" if side > 0.0 else "L"), Vector3(0.0016 * side, 0.0048, -0.0046), side, 0.0115, 0.0042, 0.5, wm)
		_add_wing(rig, "WingH" + ("R" if side > 0.0 else "L"), Vector3(0.0014 * side, 0.0046, -0.0026), side, 0.0075, 0.003, 0.7, wm)
	var lib := AnimationLibrary.new()
	# fly: hovering, the wings flicking up and down on every clip frame (BUZZ_HZ), the body
	# bobbing 6 mm two and a half times a second
	var at := rig.position
	lib.add_animation("fly", _wing_clip(BUZZ_LEN, roundi(BUZZ_LEN * CLIP_FPS), func(t: float) -> Array:
		var a := 0.15 + 0.7 * cos(TAU * BUZZ_HZ * t)
		return [Vector2(a, a), at + Vector3(0, 0.012 + 0.003 * sin(TAU * t / BUZZ_LEN), 0)]))
	lib.add_animation("rest", _wing_clip(1.0, 1, func(_t: float) -> Array: return [Vector2(0.02, 0.0), at]))
	_add_player(root, lib)
	return root


# ------------------------------------------------------------------ dragonfly

func _dragonfly() -> Node3D:
	var root := Node3D.new()
	root.name = "dragonfly"
	var rig := Node3D.new()
	rig.name = "Rig"
	rig.position.y = 0.006
	root.add_child(rig)
	var eye := Color(0.16, 0.42, 0.36)
	var thorax := Color(0.36, 0.52, 0.16)
	var blue := Color(0.16, 0.42, 0.78)
	var black := Color(0.05, 0.05, 0.06)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	# an emperor-like dragonfly about 7.5 cm long: big eyes, green thorax, a long blue abdomen
	# ringed in black. Metres, head at -Z.
	_tube(st, 1.0, [[-0.0255, 0.0], [-0.0245, 0.0032], [-0.0222, 0.0046], [-0.0196, 0.0036]], eye)
	_tube(st, 1.0, [[-0.02, 0.0028], [-0.0165, 0.0042], [-0.01, 0.0045], [-0.0055, 0.0034]], thorax)
	var z := -0.0055
	var r := 0.0024
	for k in 8:
		var z1 := z + 0.0058
		var r1 := 0.0016 if k < 6 else 0.0012
		_tube(st, 1.0, [[z, r], [z1 - 0.0012, r1]], blue)
		_tube(st, 1.0, [[z1 - 0.0012, r1], [z1, r1 * 0.9]], black)
		z = z1
		r = r1 * 0.9
	for side in [1.0, -1.0]:
		for k in 3:
			var hip := Vector3(0.0018 * side, -0.003, -0.016 + k * 0.0035)
			var knee := Vector3(0.0048 * side, -0.003, hip.z - 0.0016)
			_stick(st, 1.0, hip, knee, 0.0003, black)
			_stick(st, 1.0, knee, Vector3(0.0058 * side, -0.006, hip.z - 0.0008), 0.00025, black)
	var body := MeshInstance3D.new()
	body.name = "Body"
	var bm := st.commit()
	bm.surface_set_material(0, _pal_material())
	body.mesh = bm
	rig.add_child(body)
	var wm := _glass_material(Color(0.86, 0.88, 0.8, 0.3))
	# four long clear wings held straight out, the hind pair a little broader
	for side in [1.0, -1.0]:
		_add_wing(rig, "WingF" + ("R" if side > 0.0 else "L"), Vector3(0.0016 * side, 0.0042, -0.0145), side, 0.047, 0.0085, -0.08, wm)
		_add_wing(rig, "WingH" + ("R" if side > 0.0 else "L"), Vector3(0.0016 * side, 0.0042, -0.0085), side, 0.045, 0.0105, 0.1, wm)
	var lib := AnimationLibrary.new()
	# fly: fore and hind pairs beat against each other (BUZZ_HZ, one flick per clip frame)
	var at := rig.position
	lib.add_animation("fly", _wing_clip(BUZZ_LEN, roundi(BUZZ_LEN * CLIP_FPS), func(t: float) -> Array:
		var c := cos(TAU * BUZZ_HZ * t)
		return [Vector2(0.45 * c, -0.4 * c), at + Vector3(0, 0.02 + 0.002 * sin(TAU * t / BUZZ_LEN), 0)]))
	lib.add_animation("rest", _wing_clip(1.0, 1, func(_t: float) -> Array: return [Vector2(-0.04, -0.04), at]))
	_add_player(root, lib)
	return root


# ------------------------------------------------------------------ parts

## A flat wing on its own hinge node: an elliptic outline from the hinge outward along the
## side, narrowing to the tip, swept by `sweep` rad (positive towards the tail), both faces.
func _add_wing(rig: Node3D, wname: String, hinge: Vector3, side: float, length: float, width: float, sweep: float, mat: Material) -> void:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n := 8
	var rot := Basis(Vector3.UP, -sweep * side)
	var rim := []
	for i in 2 * n + 1:
		var a := PI * float(i) / n                     # round the outline from the hinge
		var u := (1.0 - cos(a)) * 0.5                  # 0 at the hinge .. 1 at the tip
		rim.append(rot * Vector3(u * length * side, 0, sin(a) * width * 0.5 * (1.0 - 0.3 * u)))
	for face in [Vector3.UP, Vector3.DOWN]:
		for i in range(1, 2 * n - 1):
			_face(st, [rim[0], rim[i], rim[i + 1]], [face, face, face], face)
	var mi := MeshInstance3D.new()
	mi.name = wname
	var m := st.commit()
	m.surface_set_material(0, mat)
	mi.mesh = m
	mi.position = hinge
	rig.add_child(mi)


## Octagonal rings [z, radius] along the body axis (Butterflies._tube), scaled by s.
func _tube(st: SurfaceTool, s: float, rings: Array, c: Color) -> void:
	var seg := 8
	for r in rings.size() - 1:
		var z0: float = rings[r][0]
		var r0: float = rings[r][1]
		var z1: float = rings[r + 1][0]
		var r1: float = rings[r + 1][1]
		for i in seg:
			var a0 := TAU * i / seg
			var a1 := TAU * (i + 1) / seg
			var p := [Vector3(cos(a0) * r0, sin(a0) * r0 * 0.9, z0), Vector3(cos(a1) * r0, sin(a1) * r0 * 0.9, z0),
				Vector3(cos(a1) * r1, sin(a1) * r1 * 0.9, z1), Vector3(cos(a0) * r1, sin(a0) * r1 * 0.9, z1)]
			var nm := [Vector3(cos(a0), sin(a0), 0), Vector3(cos(a1), sin(a1), 0), Vector3(cos(a1), sin(a1), 0), Vector3(cos(a0), sin(a0), 0)]
			var out: Vector3 = nm[0] + nm[1]
			for tri in [[0, 1, 2], [0, 2, 3]]:
				_face(st, [(p[tri[0]] as Vector3) * s, (p[tri[1]] as Vector3) * s, (p[tri[2]] as Vector3) * s], [nm[tri[0]], nm[tri[1]], nm[tri[2]]], out, [], c)


## Two crossed thin strips, both faces (Butterflies._stick drew them with culling off).
func _stick(st: SurfaceTool, s: float, a: Vector3, b: Vector3, r: float, c: Color) -> void:
	var along := (b - a).normalized()
	for off in [Vector3(r, 0, 0), Vector3(0, r, 0)]:
		var p := [(a - off) * s, (a + off) * s, (b + off) * s, (b - off) * s]
		var n := (off as Vector3).cross(along).normalized()
		for face in [n, -n]:
			for tri in [[0, 1, 2], [0, 2, 3]]:
				_face(st, [p[tri[0]], p[tri[1]], p[tri[2]]], [face, face, face], face, [], c)


## One triangle, wound so its front face (Godot: clockwise as seen) looks along `out`;
## degenerate ones (a ring closing to a point) are dropped.
func _face(st: SurfaceTool, v: Array, nm: Array, out: Vector3, uv := [], c := Color.WHITE) -> void:
	var g := ((v[2] as Vector3) - (v[0] as Vector3)).cross((v[1] as Vector3) - (v[0] as Vector3))
	if g.length_squared() < 1e-24:
		return
	var order := [0, 1, 2] if g.dot(out) > 0.0 else [0, 2, 1]
	for k in order:
		st.set_normal(nm[k])
		st.set_uv(uv[k] if not uv.is_empty() else _pal_uv(c))
		st.add_vertex(v[k])


## Body colours as a palette texture, not vertex colours: Godot's runtime glTF import (the
## browser's WorldPackage) leaves vertex_color_use_as_albedo off, so COLOR_0 renders white.
## Each colour is an 8 px block, so the small mip levels of a far insect keep their colours.
const PAL_BLOCK := 8
const PAL_MAX := 16


func _pal_uv(c: Color) -> Vector2:
	var i := _pal.find(c)
	if i < 0:
		_pal.append(c)
		i = _pal.size() - 1
	assert(i < PAL_MAX)
	return Vector2((i + 0.5) / PAL_MAX, 0.5)


func _pal_material() -> StandardMaterial3D:
	var img := Image.create(PAL_MAX * PAL_BLOCK, PAL_BLOCK, false, Image.FORMAT_RGB8)
	for i in _pal.size():
		img.fill_rect(Rect2i(i * PAL_BLOCK, 0, PAL_BLOCK, PAL_BLOCK), _pal[i])
	_pal = []
	var m := StandardMaterial3D.new()
	m.resource_name = "body"
	m.albedo_texture = ImageTexture.create_from_image(img)
	m.roughness = 0.9
	return m


func _glass_material(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.resource_name = "wings"
	m.albedo_color = c
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.roughness = 0.3
	return m


# ------------------------------------------------------------------ clips

## A clip of `keys` + 1 samples over `length` s. pose(t) returns [Vector2(fore lift, hind
## lift) in rad (0 flat out, positive up), Vector3 rig position].
func _wing_clip(length: float, keys: int, pose: Callable) -> Animation:
	var anim := Animation.new()
	anim.length = length
	anim.loop_mode = Animation.LOOP_LINEAR
	var tracks := {}
	for w in ["WingFR", "WingHR", "WingFL", "WingHL"]:
		var t := anim.add_track(Animation.TYPE_ROTATION_3D)
		anim.track_set_path(t, NodePath("Rig/" + w))
		tracks[w] = t
	var rig_t := anim.add_track(Animation.TYPE_POSITION_3D)
	anim.track_set_path(rig_t, NodePath("Rig"))
	for i in keys + 1:
		var tt := length * float(i) / keys
		var got: Array = pose.call(tt)
		var lift: Vector2 = got[0]
		anim.position_track_insert_key(rig_t, tt, got[1])
		for w in tracks:
			var side := 1.0 if String(w).ends_with("R") else -1.0
			var a: float = lift.x if String(w).begins_with("WingF") else lift.y
			anim.rotation_track_insert_key(tracks[w], tt, Quaternion(Vector3.BACK, a * side))
	return anim


func _add_player(root: Node3D, lib: AnimationLibrary) -> void:
	var ap := AnimationPlayer.new()
	ap.name = "AnimationPlayer"
	root.add_child(ap)
	ap.add_animation_library("", lib)
