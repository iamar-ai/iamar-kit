extends SceneTree
## Writes the catalogue's harbour set as glTF (kit/catalog/assets/harbour/): a rowboat, a
## fishing boat, a mooring bollard, a harbour bell in its frame, a pile of fishing net and a
## herring gull, and a fish hall's dressing: a fishmonger's slab, a stack of fish crates and
## a net hung to dry on its rack. The city has no harbour (its water is the mill pond, the canals and
## fountains), so every one is made here, in the city's low-poly painted look: flat palette
## colours in a small texture (vertex colours render white through Godot's runtime glTF
## import, see export_insects.gd), bottoms that nobody sees left out.
##
##   godot --headless --path <the iamar browser source (not public) checkout> -s <iamar-kit>/kit/catalog/assets/export_harbour.gd
##   (then: python3 kit/catalog/assets/seal_props.py && python3 kit/catalog/assets/harbour.py record
##    && python3 kit/catalog/catalog.py build; seal_props.py backs the boat hull, net and slate sheets)
##   IAMAR_HARBOUR_ONLY=fish_stall,fish_crates writes only those files (the rest stay as they are)
##
## Clips (scene.json objects "animation" loops one; a world script plays any of them with
## entity_play_anim on an asset:<path>.glb entity):
##   rowboat, fishing boat  bob    rolling and heaving at a mooring; origin = the waterline
##   harbour bell           ring   the bell swinging on its headstock (play it from a script
##                                 when the bell is rung; the "Bell" node is the hinge)
##   gull                   perch  standing, looking about; fly: wings beating, legs tucked
##                                 (move it with entity_move_to, see kit/catalog/README.md)
## Front is -Z (the bow, the gull's bill), as everywhere in the catalogue.

const OUT_REL := "catalog/assets/harbour"

var _kit := ""
var _pal: Array = []
var _pending: Array = []   ## the model's palette meshes, waiting for its one material


func _init() -> void:
	# this file is <kit repo>/kit/catalog/assets/export_harbour.gd
	_kit = (get_script() as Script).resource_path.get_base_dir().get_base_dir().get_base_dir()
	if OS.get_environment("IAMAR_KIT_ROOT") != "":
		_kit = OS.get_environment("IAMAR_KIT_ROOT").path_join("kit")
	_run.call_deferred()


func _run() -> void:
	var out := _kit.path_join(OUT_REL)
	DirAccess.make_dir_recursive_absolute(out)
	var only := OS.get_environment("IAMAR_HARBOUR_ONLY").split(",", false)
	var ok := true
	for stem in ["rowboat", "fishing_boat", "bollard", "harbour_bell", "net_pile", "gull",
			"fish_stall", "fish_crates", "hanging_net"]:
		if only.is_empty() or stem in only:
			ok = _write(_model(stem), out.path_join(stem + ".glb")) and ok
	quit(0 if ok else 1)


func _model(stem: String) -> Node3D:
	match stem:
		"rowboat": return _rowboat()
		"fishing_boat": return _fishing_boat()
		"bollard": return _bollard()
		"harbour_bell": return _bell()
		"net_pile": return _net_pile()
		"gull": return _gull()
		"fish_stall": return _fish_stall()
		"fish_crates": return _fish_crates()
	return _hanging_net()


func _write(root: Node3D, path: String) -> bool:
	var mat := _pal_material()
	for m in _pending:
		(m as ArrayMesh).surface_set_material(0, mat)
	_pending = []
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_scene(root, state)
	if err == OK:
		err = doc.write_to_filesystem(state, path)
	print("%s %s" % ["wrote" if err == OK else "FAILED (%d)" % err, path])
	root.free()
	_pal = []
	return err == OK


# ------------------------------------------------------------------ colours

const OAK := Color(0.47, 0.33, 0.2)
const OAK_DARK := Color(0.36, 0.25, 0.15)
const PLANK := Color(0.58, 0.44, 0.29)
## tar and iron stay out of the lint's forbidden-black band (delta E 12 from #000000:
## 0.11 grey failed it, harbour a4 gap G8): dark, never black
const TAR := Color(0.19, 0.16, 0.13)
const IRON := Color(0.17, 0.17, 0.18)
const RUST := Color(0.38, 0.2, 0.11)
const BRONZE := Color(0.62, 0.45, 0.2)
const ROPE := Color(0.7, 0.6, 0.42)
const CANVAS := Color(0.73, 0.55, 0.38)    ## tanned (barked) sail, as working boats had
const STONE := Color(0.55, 0.53, 0.5)
const BLUE := Color(0.2, 0.36, 0.52)
const RED := Color(0.6, 0.2, 0.15)
const GREEN := Color(0.24, 0.4, 0.3)
const CREAM := Color(0.86, 0.82, 0.7)
const ICE := Color(0.78, 0.86, 0.88)
const SILVER := Color(0.68, 0.72, 0.74)   ## herring flanks
const FISH_BACK := Color(0.28, 0.4, 0.46)  ## blue-green herring backs, fins and tails
const SLATE := Color(0.24, 0.26, 0.28)


# ------------------------------------------------------------------ boats

## A clinker rowboat 3.8 m long: pointed bow, transom stern, three thwarts, two oars shipped
## along the thwarts. Strakes alternate two oak tones under a painted top strake.
func _rowboat() -> Node3D:
	var root := Node3D.new()
	root.name = "rowboat"
	var boat := Node3D.new()
	boat.name = "Boat"
	root.add_child(boat)
	var st := _begin()
	var hull := {"length": 3.8, "beam": 1.45, "depth": 0.62, "draft": 0.22, "transom": 0.62,
		"stations": 12, "strakes": 5, "top": BLUE}
	_hull(st, hull)
	# thwarts (seats) across the hull, a stern bench, the floor boards
	for z in [-0.75, 0.1, 0.85]:
		var w := _half_beam(hull, z) * 2.0 - 0.06
		_box(st, Vector3(0, 0.12, z), Vector3(w, 0.04, 0.24), PLANK, false)
	_box(st, Vector3(0, -0.12, 0.15), Vector3(0.5, 0.03, 2.6), OAK_DARK, false)
	# rowlocks and two oars resting along the thwarts
	for side in [1.0, -1.0]:
		var x := _half_beam(hull, 0.1)
		_box(st, Vector3(x * side, _sheer(hull, 0.1) + 0.06, 0.1), Vector3(0.04, 0.1, 0.04), IRON)
		_cyl(st, Vector3(0.28 * side, 0.18, -1.35), Vector3(0.36 * side, 0.18, 1.35), 0.025, 0.025, 6, PLANK, false)
		_box(st, Vector3(0.36 * side, 0.18, 1.5), Vector3(0.14, 0.02, 0.34), PLANK)
	# painter (bow rope) coiled on the bow seat
	_ring(st, Vector3(0, 0.15, -1.25), 0.14, 0.03, 10, ROPE)
	_mesh(boat, "Hull", st)
	_add_player(root, _bob_clip(4.0, 0.06, 0.025, 0.035))
	return root


## A decked fishing boat 6.8 m long: a short mast with a furled tanned sail on its boom, a
## small cuddy forward, a tiller aft, lobster pots and a fish box on deck.
func _fishing_boat() -> Node3D:
	var root := Node3D.new()
	root.name = "fishing_boat"
	var boat := Node3D.new()
	boat.name = "Boat"
	root.add_child(boat)
	var st := _begin()
	var hull := {"length": 6.8, "beam": 2.3, "depth": 1.15, "draft": 0.55, "transom": 0.5,
		"stations": 16, "strakes": 7, "top": GREEN}
	_hull(st, hull)
	# deck a hand below the gunwale, from bow to stern
	var deck_y := 0.12
	var n := 10
	for i in n:
		var z0 := -3.2 + 6.3 * float(i) / n
		var z1 := -3.2 + 6.3 * float(i + 1) / n
		var w0 := _half_beam(hull, z0) - 0.06
		var w1 := _half_beam(hull, z1) - 0.06
		_quad(st, [Vector3(-w0, deck_y, z0), Vector3(w0, deck_y, z0), Vector3(w1, deck_y, z1), Vector3(-w1, deck_y, z1)], Vector3.UP, PLANK if i % 2 == 0 else Color(0.55, 0.41, 0.27))
	# cuddy (small cabin) forward of the mast, with a tarred roof and a dark door
	_box(st, Vector3(0, deck_y + 0.45, -1.7), Vector3(1.3, 0.9, 1.3), CREAM, false)
	_box(st, Vector3(0, deck_y + 0.94, -1.7), Vector3(1.42, 0.08, 1.42), TAR)
	_box(st, Vector3(0, deck_y + 0.38, -1.04), Vector3(0.5, 0.7, 0.02), OAK_DARK)
	# mast, boom with the furled sail, a gaff lowered on it, forestay and shrouds
	var mast_foot := Vector3(0, deck_y, -0.7)
	var mast_top := Vector3(0, 5.6, -0.7)
	_cyl(st, mast_foot, mast_top, 0.09, 0.06, 8, OAK)
	var boom_a := Vector3(0, 1.25, -0.6)
	var boom_b := Vector3(0, 1.1, 2.9)
	_cyl(st, boom_a, boom_b, 0.05, 0.045, 6, OAK)
	_cyl(st, boom_a + Vector3(0, 0.18, 0.1), boom_b + Vector3(0, 0.12, -0.3), 0.17, 0.08, 8, CANVAS, true)   # capped: its open end showed (G8)
	_cyl(st, boom_a + Vector3(0, 0.34, 0.15), boom_b + Vector3(0, 0.26, -0.6), 0.04, 0.035, 6, OAK)
	_line(st, mast_top + Vector3(0, -0.2, 0), Vector3(0, _sheer(hull, -3.35) + 0.05, -3.35), ROPE)
	for side in [1.0, -1.0]:
		var x := _half_beam(hull, -0.4) - 0.02
		_line(st, mast_top + Vector3(0, -0.5, 0), Vector3(x * side, _sheer(hull, -0.4), -0.4), ROPE)
		_line(st, mast_top + Vector3(0, -0.5, 0), Vector3(x * side, _sheer(hull, 0.3), 0.3), ROPE)
	# tiller, a fish box, two lobster pots, a coil of rope, fenders over the side
	_cyl(st, Vector3(0, deck_y + 0.5, 3.2), Vector3(0, deck_y + 0.55, 2.2), 0.04, 0.03, 6, OAK_DARK)
	_box(st, Vector3(0.45, deck_y + 0.15, 1.6), Vector3(0.7, 0.3, 0.5), PLANK, false)
	for k in 2:
		var c := Vector3(-0.5, deck_y, 1.1 + k * 0.7)
		_pot(st, c)
	_ring(st, Vector3(0.35, deck_y + 0.04, 0.4), 0.22, 0.04, 10, ROPE)
	for side in [1.0, -1.0]:
		for z in [-1.0, 1.2]:
			var x := _half_beam(hull, z) + 0.06
			_cyl(st, Vector3(x * side, _sheer(hull, z) - 0.25, z), Vector3(x * side, _sheer(hull, z) - 0.6, z), 0.08, 0.08, 6, CREAM, true)
	_mesh(boat, "Hull", st)
	_add_player(root, _bob_clip(5.0, 0.045, 0.018, 0.05))
	return root


## Half the beam at z (bow at -length/2, transom at +length/2).
static func _half_beam(h: Dictionary, z: float) -> float:
	var u := clampf(z / float(h.length) + 0.5, 0.0, 1.0)   # 0 bow .. 1 stern
	var b: float = float(h.beam) * 0.5
	var bow := sqrt(clampf(u / 0.45, 0.0, 1.0))           # fine entry, full by 45 %
	var stern := lerpf(1.0, float(h.transom), smoothstep(0.6, 1.0, u))
	return maxf(b * minf(bow, stern), 0.0)


## Height of the gunwale at z above the waterline: a sheer rising to the bow.
static func _sheer(h: Dictionary, z: float) -> float:
	var u := clampf(z / float(h.length) + 0.5, 0.0, 1.0)
	var free: float = float(h.depth) - float(h.draft)
	return free + 0.22 * float(h.depth) * pow(1.0 - u, 2.0) + 0.06 * float(h.depth) * pow(u, 2.0)


## The hull: outside planking in strakes, the inside of the same planks (seen from a quay),
## a capping rail on the gunwale and a transom. Waterline at y = 0.
func _hull(st: SurfaceTool, h: Dictionary) -> void:
	var L: float = h.length
	var ns: int = h.stations
	var nk: int = h.strakes
	var keel: float = -float(h.draft)
	var secs := []   # per station: [points from gunwale (k = 0) to keel (k = nk)]
	for i in ns + 1:
		var z := -L * 0.5 + L * float(i) / ns
		var w := _half_beam(h, z)
		var top := _sheer(h, z)
		var bottom := lerpf(keel, top - 0.15, pow(1.0 - clampf(z / L + 0.5, 0.0, 1.0), 6.0))   # forefoot rises to the stem
		var pts := []
		for k in nk + 1:
			var t := float(k) / nk                       # 0 gunwale .. 1 keel
			var a := t * PI * 0.5
			pts.append(Vector3(w * cos(a) ** 0.7, lerpf(top, bottom, sin(a) ** 1.3), z))
		secs.append(pts)
	var thick := 0.04
	for side in [1.0, -1.0]:
		for i in ns:
			for k in nk:
				var p := [secs[i][k], secs[i + 1][k], secs[i + 1][k + 1], secs[i][k + 1]]
				for j in 4:
					p[j] = Vector3((p[j] as Vector3).x * side, (p[j] as Vector3).y, (p[j] as Vector3).z)
				var c: Color = h.top if k == 0 else (OAK if k % 2 == 1 else OAK_DARK)
				if k == nk - 1:
					c = TAR   # tarred bottom strake by the keel
				var out := Vector3(side, -0.3, 0).normalized()
				_quad(st, p, out, c)
				# the inside of the plank: offset inward, faces the boat's middle
				var q := []
				for v in p:
					q.append((v as Vector3) + Vector3(-thick * side, 0.0, 0.0))
				_quad(st, q, Vector3(-side, 0.5, 0).normalized(), PLANK if k > 0 else OAK)
			# capping rail on the gunwale between outside and inside
			var a: Vector3 = secs[i][0]
			var b: Vector3 = secs[i + 1][0]
			var r := [Vector3(a.x * side, a.y, a.z), Vector3(b.x * side, b.y, b.z),
				Vector3((b.x - thick) * side, b.y, b.z), Vector3((a.x - thick) * side, a.y, a.z)]
			_quad(st, r, Vector3.UP, OAK_DARK)
	# transom: the stern panel between the two sides, both faces
	var last: Array = secs[ns]
	for k in nk:
		var a: Vector3 = last[k]
		var b: Vector3 = last[k + 1]
		var p := [Vector3(-a.x, a.y, a.z), Vector3(a.x, a.y, a.z), Vector3(b.x, b.y, b.z), Vector3(-b.x, b.y, b.z)]
		_quad(st, p, Vector3.BACK, h.top if k == 0 else OAK)
		var q := []
		for v in p:
			q.append((v as Vector3) + Vector3(0, 0, -thick))
		_quad(st, q, Vector3.FORWARD, PLANK)
	# capping rail across the transom top, closing the slot between its two faces (audit
	# closure found it open from the quay, harbour a4 gap G8)
	var t0: Vector3 = last[0]
	_quad(st, [Vector3(t0.x, t0.y, t0.z), Vector3(-t0.x, t0.y, t0.z), Vector3(-t0.x, t0.y, t0.z - thick),
		Vector3(t0.x, t0.y, t0.z - thick)], Vector3.UP, OAK_DARK)
	# stem post at the bow
	var s0: Vector3 = secs[0][0]
	_box(st, Vector3(0, s0.y - 0.25, s0.z - 0.02), Vector3(0.07, 0.6, 0.08), OAK_DARK)


## Rolling, pitching and heaving on the "Boat" node over one loop of `length` s.
func _bob_clip(length: float, roll: float, pitch: float, heave: float) -> AnimationLibrary:
	var anim := Animation.new()
	anim.length = length
	anim.loop_mode = Animation.LOOP_LINEAR
	var rt := anim.add_track(Animation.TYPE_ROTATION_3D)
	anim.track_set_path(rt, NodePath("Boat"))
	var pt := anim.add_track(Animation.TYPE_POSITION_3D)
	anim.track_set_path(pt, NodePath("Boat"))
	var keys := 24
	for i in keys + 1:
		var t := length * float(i) / keys
		var ph := TAU * t / length
		var q := Quaternion(Vector3.BACK, roll * sin(ph)) * Quaternion(Vector3.RIGHT, pitch * sin(2.0 * ph + 0.8))
		anim.rotation_track_insert_key(rt, t, q)
		anim.position_track_insert_key(pt, t, Vector3(0, heave * sin(2.0 * ph + 0.3), 0))
	var lib := AnimationLibrary.new()
	lib.add_animation("bob", anim)
	return lib


## A lobster pot: a slatted half-round creel on a wooden base.
func _pot(st: SurfaceTool, c: Vector3) -> void:
	_box(st, c + Vector3(0, 0.03, 0), Vector3(0.45, 0.06, 0.6), OAK_DARK, false)
	for k in 5:
		var a := PI * float(k) / 4.0
		var p := c + Vector3(cos(a) * 0.21, 0.06 + sin(a) * 0.24, 0)
		_cyl(st, p + Vector3(0, 0, -0.29), p + Vector3(0, 0, 0.29), 0.014, 0.014, 4, PLANK, false)
	for z in [-0.28, 0.0, 0.28]:
		for k in 4:
			var a0 := PI * float(k) / 4.0
			var a1 := PI * float(k + 1) / 4.0
			_line(st, c + Vector3(cos(a0) * 0.22, 0.06 + sin(a0) * 0.25, z), c + Vector3(cos(a1) * 0.22, 0.06 + sin(a1) * 0.25, z), TAR)


# ------------------------------------------------------------------ bollard

## A cast-iron mooring bollard 0.62 m tall on a granite pad: waisted barrel, a mushroom cap,
## a little rust at the base, a mooring line made fast round it.
func _bollard() -> Node3D:
	var root := Node3D.new()
	root.name = "bollard"
	var st := _begin()
	_box(st, Vector3(0, 0.04, 0), Vector3(0.6, 0.08, 0.6), STONE, false)
	_lathe(st, Vector3(0, 0.08, 0), [[0.17, 0.0], [0.15, 0.08], [0.13, 0.25], [0.135, 0.4], [0.16, 0.46],
		[0.22, 0.5], [0.23, 0.53], [0.2, 0.56], [0.0, 0.58]], 14, [RUST, IRON, IRON, IRON, IRON, IRON, IRON, IRON])
	# a mooring line round the waist, running off along +Z down to the quay edge
	_ring(st, Vector3(0, 0.36, 0), 0.155, 0.025, 12, ROPE)
	_cyl(st, Vector3(0, 0.34, 0.15), Vector3(0, 0.1, 0.62), 0.025, 0.025, 6, ROPE)
	_mesh(root, "Bollard", st)
	return root


# ------------------------------------------------------------------ bell

## A harbour bell in a timber frame 2.6 m tall on a stone plinth: two posts, a cross beam,
## a bronze bell 0.5 m across on a headstock (node "Bell", its hinge), a clapper and a rope.
func _bell() -> Node3D:
	var root := Node3D.new()
	root.name = "harbour_bell"
	var st := _begin()
	_box(st, Vector3(0, 0.15, 0), Vector3(1.6, 0.3, 0.7), STONE, false)
	for side in [1.0, -1.0]:
		_box(st, Vector3(0.62 * side, 1.4, 0), Vector3(0.16, 2.2, 0.16), OAK, false)
		# braces from the posts to the beam
		_cyl(st, Vector3(0.62 * side, 2.0, 0), Vector3(0.3 * side, 2.42, 0), 0.04, 0.04, 4, OAK_DARK)
		# raking struts down to the plinth, front and back
		for z in [-1.0, 1.0]:
			_cyl(st, Vector3(0.62 * side, 1.1, 0), Vector3(0.62 * side, 0.3, 0.32 * z), 0.045, 0.045, 4, OAK_DARK)
	_box(st, Vector3(0, 2.56, 0), Vector3(1.6, 0.18, 0.2), OAK)
	_box(st, Vector3(0, 2.68, 0), Vector3(1.75, 0.06, 0.32), TAR)   # a little roof board over the bell
	_mesh(root, "Frame", st)
	# the bell hangs from the headstock axle at y 2.38: rotating "Bell" swings it
	var bell := Node3D.new()
	bell.name = "Bell"
	bell.position = Vector3(0, 2.38, 0)
	root.add_child(bell)
	var bs := _begin()
	_box(bs, Vector3(0, 0.02, 0), Vector3(1.1, 0.12, 0.14), OAK_DARK)
	# 10 sides (was 16: 578 triangles, over the lint's prop budget, harbour a4 gap G8)
	_lathe(bs, Vector3(0, -0.6, 0), [[0.25, 0.0], [0.24, 0.05], [0.19, 0.16], [0.15, 0.3], [0.14, 0.42],
		[0.11, 0.5], [0.05, 0.53], [0.0, 0.535]], 10, [BRONZE, BRONZE, BRONZE, BRONZE, BRONZE, BRONZE, BRONZE], true)
	_cyl(bs, Vector3(0, -0.1, 0), Vector3(0, -0.52, 0), 0.02, 0.02, 4, IRON)
	_lathe(bs, Vector3(0, -0.6, 0), [[0.0, -0.04], [0.045, 0.0], [0.035, 0.05], [0.0, 0.08]], 6, [IRON, IRON, IRON])
	# the bell rope from the headstock's wheel arm down to hand height
	_cyl(bs, Vector3(0.52, 0.0, 0), Vector3(0.52, -1.3, 0.05), 0.018, 0.018, 4, ROPE)
	_mesh(bell, "BellMesh", bs)
	var anim := Animation.new()
	anim.length = 2.4
	anim.loop_mode = Animation.LOOP_LINEAR
	var t := anim.add_track(Animation.TYPE_ROTATION_3D)
	anim.track_set_path(t, NodePath("Bell"))
	for i in 25:
		var tt := anim.length * float(i) / 24.0
		anim.rotation_track_insert_key(t, tt, Quaternion(Vector3.RIGHT, 0.65 * sin(TAU * tt / anim.length)))
	var lib := AnimationLibrary.new()
	lib.add_animation("ring", anim)
	_add_player(root, lib)
	return root


# ------------------------------------------------------------------ net pile

## A heap of brown fishing net 1.6 m across with a string of cork floats round its edge and
## a few glass floats, on a quay or a deck. The net's mesh is painted in its texture.
func _net_pile() -> Node3D:
	var root := Node3D.new()
	root.name = "net_pile"
	var ns := SurfaceTool.new()
	ns.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	# a lumpy low dome: rings of points, height falling to the rim, bumps from three folds
	# (5 x 14, fewer floats, one coil: the pile was 832 triangles, over the lint's prop
	# budget, harbour a4 gap G8)
	var rings := 5
	var seg := 14
	var pts := []
	for r in rings + 1:
		var row := []
		var u := float(r) / rings
		for s in seg:
			var a := TAU * float(s) / seg
			var rad := u * (0.8 + 0.08 * sin(3.0 * a) + rng.randf_range(-0.04, 0.04))
			var y := 0.42 * (1.0 - u * u) * (1.0 + 0.18 * sin(2.0 * a + 1.0))
			if r > 0 and r < rings:
				y += rng.randf_range(-0.03, 0.04)
			row.append(Vector3(cos(a) * rad * 1.1, maxf(y, 0.0), sin(a) * rad))
		pts.append(row)
	for r in rings:
		for s in seg:
			var s1 := (s + 1) % seg
			var p := [pts[r][s], pts[r][s1], pts[r + 1][s1], pts[r + 1][s]]
			var uv := []
			for v in p:
				uv.append(Vector2((v as Vector3).x, (v as Vector3).z) * 4.5)   # 4.5 repeats of the 64 px mesh texture a metre: the texel rule's 256 px/m (2.5 was 140, G8)
			var nrm := (((p[1] as Vector3) - (p[0] as Vector3)).cross((p[3] as Vector3) - (p[0] as Vector3))).normalized()
			if nrm.y < 0.0:
				nrm = -nrm
			for tri in [[0, 1, 2], [0, 2, 3]]:
				_face(ns, [p[tri[0]], p[tri[1]], p[tri[2]]], [nrm, nrm, nrm], Vector3.UP, [uv[tri[0]], uv[tri[1]], uv[tri[2]]])
	var nm := ns.commit()
	nm.surface_set_material(0, _net_material())
	var net := MeshInstance3D.new()
	net.name = "Net"
	net.mesh = nm
	root.add_child(net)
	var st := _begin()
	# cork floats along the rim, a few glass floats on top, a coil of rope beside it
	for k in 10:
		var a := TAU * float(k) / 10.0 + 0.2
		var p: Vector3 = pts[rings][k * seg / 10]
		var c := Vector3(p.x, 0.05, p.z) * 0.97
		var d := Vector3(-sin(a), 0, cos(a)) * 0.07
		_cyl(st, c - d, c + d, 0.045, 0.045, 4, Color(0.78, 0.55, 0.3), true)
	for g in [[Vector3(0.15, 0.4, 0.1), Color(0.3, 0.55, 0.5)], [Vector3(-0.3, 0.3, -0.2), Color(0.25, 0.45, 0.55)]]:
		_lathe(st, g[0] + Vector3(0, -0.09, 0), [[0.0, 0.0], [0.07, 0.03], [0.1, 0.09], [0.07, 0.15], [0.0, 0.18]], 6, [g[1], g[1], g[1], g[1]])
	_ring(st, Vector3(1.05, 0.06, 0.35), 0.19, 0.05, 8, ROPE)
	_mesh(root, "Floats", st)
	return root


## Brown net mesh: lighter cords on a dark gap colour, tiling (opaque: a heap shows no holes).
func _net_material() -> StandardMaterial3D:
	var img := Image.create(64, 64, true, Image.FORMAT_RGB8)
	img.fill(Color(0.17, 0.13, 0.09))
	var cord := Color(0.5, 0.38, 0.24)
	for i in 64:
		for k in 2:
			var j := (i + 32 * k) % 64     # two diagonal cords cross each 32 px tile
			for w in 3:
				img.set_pixel(i, (j + w) % 64, cord)
				img.set_pixel(i, (64 - j + w) % 64, cord.darkened(0.1))
	img.generate_mipmaps()
	var m := StandardMaterial3D.new()
	m.resource_name = "net"
	m.albedo_texture = ImageTexture.create_from_image(img)
	m.roughness = 1.0
	return m


# ------------------------------------------------------------------ fish hall

## A herring lying on its side, 0.26 m long by default, nose along `dir` (flat in XZ): a
## raised spine, silver flanks, a forked tail. 6 triangles, top side only (it lies on something).
func _fish(st: SurfaceTool, c: Vector3, dir: Vector3, length := 0.26) -> void:
	var f := dir.normalized() * length
	var s := Vector3(-f.z, 0, f.x) * 0.2
	var up := Vector3(0, 0.035 * length / 0.26, 0)
	var nose := c + f * 0.5
	var mid := c + f * 0.05 + up
	var root := c - f * 0.32
	var l := c + f * 0.08 + s
	var r := c + f * 0.08 - s
	_face(st, [nose, l, mid], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], SILVER)
	_face(st, [nose, mid, r], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], SILVER)
	_face(st, [mid, l, root], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], FISH_BACK)
	_face(st, [mid, root, r], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], FISH_BACK)
	var tip := c - f * 0.5
	_face(st, [root, tip + s * 0.9, tip + s * 0.2], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], FISH_BACK)
	_face(st, [root, tip - s * 0.2, tip - s * 0.9], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], FISH_BACK)


## A fish hung by its tail from a hook (both faces: seen from either side).
func _hung_fish(st: SurfaceTool, top: Vector3, length := 0.32) -> void:
	var w := Vector3(length * 0.11, 0, 0)
	var tail := top + Vector3(0, -0.06, 0)
	var body := top + Vector3(0, -length * 0.35, 0)
	var nose := top + Vector3(0, -length, 0)
	for out in [Vector3.BACK, Vector3.FORWARD]:
		_face(st, [top + w * 0.8, top - w * 0.8, tail], [out, out, out], out, [], FISH_BACK)
		_face(st, [tail, body - w, body + w], [out, out, out], out, [], FISH_BACK)
		_face(st, [body + w, body - w, nose], [out, out, out], out, [], SILVER)


## A fishmonger's slab 2.2 m long on two trestles: a board tilted toward the buyer (-Z) and
## covered in ice with three rows of herring, two posts behind it with a hanging rail and
## three fish on hooks, a chalk price slate at the front and a chopping block at one end.
func _fish_stall() -> Node3D:
	var root := Node3D.new()
	root.name = "fish_stall"
	var st := _begin()
	# trestles: an A of two splayed legs and a cross bar at each end
	for x in [-0.85, 0.85]:
		for z in [-0.32, 0.32]:
			_cyl(st, Vector3(x, 0.0, z * 1.25), Vector3(x, 0.8, z * 0.7), 0.04, 0.04, 4, OAK_DARK)
		_box(st, Vector3(x, 0.8, 0), Vector3(0.1, 0.08, 0.9), OAK_DARK)
	# the slab: a board tilted 8 degrees down to the front, its ice bed and a lip at the front
	var tilt := Basis(Vector3.RIGHT, deg_to_rad(-8.0))
	var top := Vector3(0, 0.88, 0)
	var hx := 1.1
	var corners := []
	for p in [Vector3(-hx, 0, -0.45), Vector3(hx, 0, -0.45), Vector3(hx, 0, 0.45), Vector3(-hx, 0, 0.45)]:
		corners.append(top + tilt * p)
	var n := tilt * Vector3.UP
	_quad(st, corners, n, ICE)
	# the board's edges (front, back, ends) and the lip that keeps the ice on
	var drop := Vector3(0, -0.06, 0)
	for e in [[0, 1, Vector3.FORWARD], [1, 2, Vector3.RIGHT], [3, 0, Vector3.LEFT], [2, 3, Vector3.BACK]]:
		_quad(st, [corners[e[0]], corners[e[1]], corners[e[1]] + drop, corners[e[0]] + drop], e[2], PLANK)
	# the board's underside: the slab stands at hip height, so a player sees under it (an internal task)
	_quad(st, [corners[0] + drop, corners[1] + drop, corners[2] + drop, corners[3] + drop], -n, PLANK)
	var lip := top + tilt * Vector3(0, 0.03, -0.46)
	_box(st, lip, Vector3(2.22, 0.07, 0.03), PLANK, false)
	# three rows of herring on the ice, heads alternating
	for row in 3:
		var z := -0.28 + 0.27 * row
		for k in 6:
			var x := -0.9 + 0.36 * k + (0.08 if row == 1 else 0.0)
			var d := Vector3(0.3, 0, 1.0) if (k + row) % 2 == 0 else Vector3(-0.3, 0, -1.0)
			_fish(st, top + tilt * Vector3(x, 0.01, z), d)
	# two posts behind the slab with a hanging rail and three fish on hooks
	for x in [-1.0, 1.0]:
		_box(st, Vector3(x, 0.95, 0.5), Vector3(0.08, 1.9, 0.08), OAK, false)
	_box(st, Vector3(0, 1.75, 0.5), Vector3(2.1, 0.06, 0.06), OAK_DARK)
	for x in [-0.5, 0.05, 0.6]:
		_hung_fish(st, Vector3(x, 1.7, 0.46))
	# a chalk price slate at the front and a chopping block at the right end
	_quad(st, [Vector3(-0.25, 0.56, -0.47), Vector3(0.25, 0.56, -0.47), Vector3(0.25, 0.8, -0.47), Vector3(-0.25, 0.8, -0.47)], Vector3.FORWARD, SLATE)
	_box(st, Vector3(0.75, 0.98, 0.18), Vector3(0.36, 0.1, 0.3), OAK, false)
	_mesh(root, "Stall", st)
	return root


## Three open wooden fish crates, two side by side and one on top, each packed with herring
## on ice; 0.7 x 0.45 x 0.26 m each, a stencilled band on the side. Stack them on a hall
## floor, a quay or a cart.
func _fish_crates() -> Node3D:
	var root := Node3D.new()
	root.name = "fish_crates"
	var st := _begin()
	for c in [[Vector3(-0.37, 0, 0), 0.0], [Vector3(0.37, 0, 0.03), 0.06], [Vector3(-0.05, 0.26, 0.02), -0.12]]:
		_crate(st, c[0], c[1])
	_mesh(root, "Crates", st)
	return root


func _crate(st: SurfaceTool, base: Vector3, yaw: float) -> void:
	var b := Basis(Vector3.UP, yaw)
	var hx := 0.35
	var hz := 0.225
	var h := 0.26
	var t := 0.02
	var outer := [Vector3(-hx, 0, -hz), Vector3(hx, 0, -hz), Vector3(hx, 0, hz), Vector3(-hx, 0, hz)]
	for i in 4:
		var p0: Vector3 = outer[i]
		var p1: Vector3 = outer[(i + 1) % 4]
		var out: Vector3 = b * ((p0 + p1) * 0.5).normalized()
		var q0 := base + b * p0
		var q1 := base + b * p1
		var up := Vector3(0, h, 0)
		_quad(st, [q0, q1, q1 + up, q0 + up], out, PLANK)
		# the gap between the two side boards (a slatted crate) as a dark band
		var g := Vector3(0, h * 0.5, 0)
		var gd := (q1 - q0).normalized() * 0.002
		_quad(st, [q0 + g - Vector3(0, 0.012, 0) + out * 0.003 + gd, q1 + g - Vector3(0, 0.012, 0) + out * 0.003 - gd,
			q1 + g + Vector3(0, 0.012, 0) + out * 0.003 - gd, q0 + g + Vector3(0, 0.012, 0) + out * 0.003 + gd], out, OAK_DARK)
		# the rim's top edge and the inside of the board above the ice
		var i0 := base + b * (p0 - p0.sign() * t)
		var i1 := base + b * (p1 - p1.sign() * t)
		_quad(st, [q0 + up, q1 + up, i1 + up, i0 + up], Vector3.UP, PLANK)
		_quad(st, [i0 + Vector3(0, h - 0.05, 0), i1 + Vector3(0, h - 0.05, 0), i1 + up, i0 + up], -out, OAK_DARK)
	# the ice bed 5 cm below the rim and the herring packed on it
	var inner := []
	for p in outer:
		inner.append(base + b * ((p as Vector3) - (p as Vector3).sign() * t) + Vector3(0, h - 0.05, 0))
	_quad(st, inner, Vector3.UP, ICE)
	for k in 4:
		var x := -0.24 + 0.16 * k
		var d := Vector3(0.15, 0, 1.0) if k % 2 == 0 else Vector3(-0.15, 0, -1.0)
		_fish(st, base + b * Vector3(x, h - 0.045, 0.0), b * d, 0.3)


## A net hung to dry over a rack 2.6 m long: two A-frame ends and a pole 2.1 m up, the brown
## net draped over it to about 0.5 m above the floor on both sides with a sag between the
## ends, cork floats along its lower edges. Inside a fish hall, a net shed or on a quay.
func _hanging_net() -> Node3D:
	var root := Node3D.new()
	root.name = "hanging_net"
	var st := _begin()
	var top := 2.1
	for x in [-1.25, 1.25]:
		for z in [-1.0, 1.0]:
			_cyl(st, Vector3(x, 0.0, 0.55 * z), Vector3(x, top + 0.05, 0.0), 0.045, 0.045, 4, OAK_DARK)
		_box(st, Vector3(x, 0.6, 0), Vector3(0.06, 0.06, 0.82), OAK_DARK)
	_cyl(st, Vector3(-1.38, top + 0.05, 0), Vector3(1.38, top + 0.05, 0), 0.04, 0.04, 6, OAK, true)
	# cork floats along both lower edges (box corks: 10 triangles each, no bottoms seen)
	var cols := 7
	var hx := 1.1
	var floats := []
	for side in [-1.0, 1.0]:
		for i in cols + 1:
			var x := -hx + 2.0 * hx * float(i) / cols
			var u := x / hx
			floats.append(Vector3(x, 0.5 + 0.22 * u * u, 0.32 * side))
	for k in floats.size():
		if k % 2 == 0:
			_box(st, floats[k] + Vector3(0, -0.03, 0), Vector3(0.1, 0.06, 0.06), Color(0.78, 0.55, 0.3), true)
	_mesh(root, "Rack", st)
	# the net: from the pole down each side, falling a little outward, the hem sagging between
	# the ends; the fold's two ends are closed by triangles so no side shows a gap
	var ns := SurfaceTool.new()
	ns.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rows := 3
	for side in [-1.0, 1.0]:
		var grid := []
		for r in rows + 1:
			var v := float(r) / rows
			var line := []
			for i in cols + 1:
				var x := -hx + 2.0 * hx * float(i) / cols
				var u := x / hx
				var hem_y := 0.5 + 0.22 * u * u
				var y := lerpf(top, hem_y, v)
				var z: float = side * (0.05 + 0.27 * pow(v, 0.8) + 0.03 * sin(5.0 * u + side))
				line.append(Vector3(x, y, z))
			grid.append(line)
		for r in rows:
			for i in cols:
				var p := [grid[r][i], grid[r][i + 1], grid[r + 1][i + 1], grid[r + 1][i]]
				var nrm := Vector3(0, 0.15, side).normalized()
				var uv := []
				for q in p:
					uv.append(Vector2((q as Vector3).x, (q as Vector3).y) * 4.5)   # the net texture's 256 px/m, as the pile
				for tri in [[0, 1, 2], [0, 2, 3]]:
					_face(ns, [p[tri[0]], p[tri[1]], p[tri[2]]], [nrm, nrm, nrm], Vector3(0, 0, side), [uv[tri[0]], uv[tri[1]], uv[tri[2]]])
	for x: float in [-hx, hx]:
		var hem_y := 0.72
		var e := [Vector3(x, top, 0), Vector3(x, hem_y, -0.32), Vector3(x, hem_y, 0.32)]
		var out := Vector3(signf(x), 0, 0)
		var uv2 := [Vector2(0, top) * 4.5, Vector2(-0.32, hem_y) * 4.5, Vector2(0.32, hem_y) * 4.5]
		_face(ns, e, [out, out, out], out, uv2)
	var nm := ns.commit()
	nm.surface_set_material(0, _net_material())
	var net := MeshInstance3D.new()
	net.name = "Net"
	net.mesh = nm
	root.add_child(net)
	return root


# ------------------------------------------------------------------ gull

## A herring gull 0.58 m long, standing: white head and body, grey mantle, wings with black
## tips and white mirrors, yellow bill with the red spot, pink legs. Nodes: Rig/Body,
## Rig/Head (turns), Rig/WingR + WingL (fold along the back, spread to fly), Rig/Legs.
func _gull() -> Node3D:
	var root := Node3D.new()
	root.name = "gull"
	var rig := Node3D.new()
	rig.name = "Rig"
	rig.position.y = 0.17   # the belly above the feet
	root.add_child(rig)
	var white := Color(0.94, 0.94, 0.92)
	var grey := Color(0.62, 0.66, 0.7)
	var black := Color(0.17, 0.17, 0.18)   # the wing tips: dark, out of the lint's forbidden-black band (G8)
	var yellow := Color(0.93, 0.78, 0.25)
	var red := Color(0.8, 0.2, 0.12)
	var pink := Color(0.86, 0.62, 0.55)
	var st := _begin()
	# body along Z (head end -Z), a touch fuller at the breast; grey back as a flat saddle
	_tube(st, Vector3(0, 0, 0), [[-0.17, 0.0], [-0.15, 0.06], [-0.08, 0.095], [0.04, 0.09], [0.14, 0.06], [0.24, 0.025], [0.3, 0.0]], white, 8)
	_quad(st, [Vector3(-0.07, 0.085, -0.08), Vector3(0.07, 0.085, -0.08), Vector3(0.05, 0.06, 0.17), Vector3(-0.05, 0.06, 0.17)], Vector3.UP, grey)
	# tail feathers: grey over white, black-free (an adult)
	_quad(st, [Vector3(-0.06, 0.025, 0.23), Vector3(0.06, 0.025, 0.23), Vector3(0.05, 0.03, 0.34), Vector3(-0.05, 0.03, 0.34)], Vector3.UP, white)
	_mesh(rig, "Body", st)
	# head on the neck, with the bill and its red spot, a yellow eye
	var head := Node3D.new()
	head.name = "Head"
	head.position = Vector3(0, 0.07, -0.13)
	rig.add_child(head)
	var hs := _begin()
	_tube(hs, Vector3(0, 0.07, 0), [[-0.1, 0.0], [-0.085, 0.04], [-0.04, 0.055], [0.01, 0.045], [0.04, 0.0]], white, 8)
	_cyl(hs, Vector3(0, 0.0, 0.0), Vector3(0, 0.06, -0.02), 0.045, 0.04, 6, white)   # neck
	_cyl(hs, Vector3(0, 0.065, -0.09), Vector3(0, 0.058, -0.155), 0.016, 0.006, 6, yellow)
	_box(hs, Vector3(0, 0.05, -0.135), Vector3(0.012, 0.012, 0.016), red)
	for side in [1.0, -1.0]:
		_box(hs, Vector3(0.042 * side, 0.085, -0.06), Vector3(0.006, 0.012, 0.012), black)
	_mesh(head, "HeadMesh", hs)
	# wings: hinge at the shoulder, laid along the back at rest (the perch pose), spread for flight
	for side in [1.0, -1.0]:
		var wing := Node3D.new()
		wing.name = "Wing" + ("R" if side > 0.0 else "L")
		wing.position = Vector3(0.07 * side, 0.08, -0.06)
		wing.quaternion = _gull_fold(side)   # the rest pose is the perch pose: a gull placed without a clip stands
		rig.add_child(wing)
		var ws := _begin()
		# spans +X (or -X) from the hinge; chord along Z; grey inner, black tip with a white mirror
		var span := [[0.0, 0.0, 0.15], [0.2, -0.01, 0.15], [0.38, 0.01, 0.12], [0.52, 0.03, 0.08], [0.64, 0.05, 0.03]]
		for i in span.size() - 1:
			var a: Array = span[i]
			var b: Array = span[i + 1]
			var c := grey if i < 2 else black
			var p := [Vector3(a[0] * side, 0, a[1]), Vector3(b[0] * side, 0, b[1]), Vector3(b[0] * side, 0, b[1] + b[2]), Vector3(a[0] * side, 0, a[1] + a[2])]
			for face in [Vector3.UP, Vector3.DOWN]:
				_quad(ws, p, face, c if face == Vector3.UP else (white if i < 2 else Color(0.2, 0.2, 0.22)))
		_box(ws, Vector3(0.56 * side, 0.004, 0.06), Vector3(0.05, 0.004, 0.03), white)   # the mirror spot
		_mesh(wing, "WingMesh", ws)
	# legs and webbed feet (tucked back in flight)
	var legs := Node3D.new()
	legs.name = "Legs"
	legs.position = Vector3(0, -0.03, 0.02)
	rig.add_child(legs)
	var ls := _begin()
	for side in [1.0, -1.0]:
		_cyl(ls, Vector3(0.03 * side, 0.0, 0.0), Vector3(0.035 * side, -0.14, 0.01), 0.008, 0.007, 4, pink)
		_quad(ls, [Vector3(0.035 * side - 0.03, -0.138, -0.04), Vector3(0.035 * side + 0.03, -0.138, -0.04), Vector3(0.035 * side + 0.012, -0.138, 0.02), Vector3(0.035 * side - 0.012, -0.138, 0.02)], Vector3.UP, pink)
	_mesh(legs, "LegsMesh", ls)
	var lib := AnimationLibrary.new()
	lib.add_animation("perch", _gull_clip(6.0, 36, false))
	lib.add_animation("fly", _gull_clip(0.6, 18, true))
	_add_player(root, lib)
	return root


## A gull's folded wing: swung back along the body and dropped a little to lie on the flank.
static func _gull_fold(side: float) -> Quaternion:
	return Quaternion(Vector3.UP, -1.45 * side) * Quaternion(Vector3.BACK, -0.25 * side)


## perch: wings folded, the head turning to look about and dipping once; fly: wings spread
## and beating 1.7 times a second, legs tucked, the head still.
func _gull_clip(length: float, keys: int, flying: bool) -> Animation:
	var anim := Animation.new()
	anim.length = length
	anim.loop_mode = Animation.LOOP_LINEAR
	var tr := {}
	for n in ["Rig/Head", "Rig/WingR", "Rig/WingL", "Rig/Legs"]:
		var t := anim.add_track(Animation.TYPE_ROTATION_3D)
		anim.track_set_path(t, NodePath(n))
		tr[n] = t
	for i in keys + 1:
		var t := length * float(i) / keys
		var ph := TAU * t / length
		var head := Quaternion.IDENTITY
		var legs := Quaternion.IDENTITY
		var flap := 0.0
		if flying:
			flap = 0.55 * sin(ph)
			legs = Quaternion(Vector3.RIGHT, -1.3)
		else:
			# hold, look right, hold, look left, a dip to the ground
			var yaw := 0.8 * smoothstep(0.1, 0.2, t / length) - 1.6 * smoothstep(0.4, 0.5, t / length) + 0.8 * smoothstep(0.7, 0.8, t / length)
			var dip := 0.5 * sin(PI * clampf((t / length - 0.82) / 0.14, 0.0, 1.0))
			head = Quaternion(Vector3.UP, yaw) * Quaternion(Vector3.RIGHT, -dip)
		anim.rotation_track_insert_key(tr["Rig/Head"], t, head)
		anim.rotation_track_insert_key(tr["Rig/Legs"], t, legs)
		for side in [1.0, -1.0]:
			var q: Quaternion
			if flying:
				q = Quaternion(Vector3.BACK, flap * side)
			else:
				q = _gull_fold(side)
			anim.rotation_track_insert_key(tr["Rig/Wing" + ("R" if side > 0.0 else "L")], t, q)
	return anim


# ------------------------------------------------------------------ parts

func _begin() -> SurfaceTool:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	return st


## A mesh in the model's shared palette (the material is set in _write, once every colour is in).
func _mesh(parent: Node3D, mname: String, st: SurfaceTool) -> void:
	var m := st.commit()
	_pending.append(m)
	var mi := MeshInstance3D.new()
	mi.name = mname
	mi.mesh = m
	parent.add_child(mi)


## A flat quad (4 points in order), front face along `out`.
func _quad(st: SurfaceTool, p: Array, out: Vector3, c: Color) -> void:
	var n := ((p[1] as Vector3) - (p[0] as Vector3)).cross((p[3] as Vector3) - (p[0] as Vector3)).normalized()
	if n.dot(out) < 0.0:
		n = -n
	_face(st, [p[0], p[1], p[2]], [n, n, n], n, [], c)
	_face(st, [p[0], p[2], p[3]], [n, n, n], n, [], c)


## An axis-aligned box; `bottom` false leaves out the face that sits on something.
func _box(st: SurfaceTool, c: Vector3, s: Vector3, col: Color, bottom := true) -> void:
	var h := s * 0.5
	for ax in 3:
		for sg in [1.0, -1.0]:
			if ax == 1 and sg < 0.0 and not bottom:
				continue
			var n := Vector3.ZERO
			n[ax] = sg
			var u := Vector3.ZERO
			u[(ax + 1) % 3] = h[(ax + 1) % 3]
			var v := Vector3.ZERO
			v[(ax + 2) % 3] = h[(ax + 2) % 3]
			var o := c + n * h[ax]
			_quad(st, [o - u - v, o + u - v, o + u + v, o - u + v], n, col)


## A tapered cylinder from a to b, `seg` sides; `caps` closes both ends.
func _cyl(st: SurfaceTool, a: Vector3, b: Vector3, r0: float, r1: float, seg: int, c: Color, caps := false) -> void:
	var ax := (b - a).normalized()
	var ref := Vector3.UP if absf(ax.dot(Vector3.UP)) < 0.9 else Vector3.RIGHT
	var u := ax.cross(ref).normalized()
	var v := ax.cross(u).normalized()
	for i in seg:
		var a0 := TAU * i / seg
		var a1 := TAU * (i + 1) / seg
		var d0 := u * cos(a0) + v * sin(a0)
		var d1 := u * cos(a1) + v * sin(a1)
		var p := [a + d0 * r0, a + d1 * r0, b + d1 * r1, b + d0 * r1]
		var out := (d0 + d1).normalized()
		_face(st, [p[0], p[1], p[2]], [d0, d1, d1], out, [], c)
		_face(st, [p[0], p[2], p[3]], [d0, d1, d0], out, [], c)
		if caps:
			_face(st, [a, a + d0 * r0, a + d1 * r0], [-ax, -ax, -ax], -ax, [], c)
			_face(st, [b, b + d1 * r1, b + d0 * r1], [ax, ax, ax], ax, [], c)


## A thin line (rope, stay): a 3-sided strand.
func _line(st: SurfaceTool, a: Vector3, b: Vector3, c: Color) -> void:
	_cyl(st, a, b, 0.012, 0.012, 3, c)


## A torus lying flat (a coil of rope, a line made fast).
func _ring(st: SurfaceTool, c: Vector3, r: float, thick: float, seg: int, col: Color) -> void:
	for i in seg:
		var a0 := TAU * i / seg
		var a1 := TAU * (i + 1) / seg
		_cyl(st, c + Vector3(cos(a0), 0, sin(a0)) * r, c + Vector3(cos(a1), 0, sin(a1)) * r, thick, thick, 4, col)


## A turned profile [[radius, height], ...] round the Y axis from `base`; colours per band.
## `inside` also draws the inner face (a bell's mouth, seen from below).
func _lathe(st: SurfaceTool, base: Vector3, prof: Array, seg: int, cols: Array, inside := false) -> void:
	for k in prof.size() - 1:
		var r0: float = prof[k][0]
		var y0: float = prof[k][1]
		var r1: float = prof[k + 1][0]
		var y1: float = prof[k + 1][1]
		var c: Color = cols[mini(k, cols.size() - 1)]
		for i in seg:
			var a0 := TAU * i / seg
			var a1 := TAU * (i + 1) / seg
			var d0 := Vector3(cos(a0), 0, sin(a0))
			var d1 := Vector3(cos(a1), 0, sin(a1))
			var p := [base + d0 * r0 + Vector3(0, y0, 0), base + d1 * r0 + Vector3(0, y0, 0),
				base + d1 * r1 + Vector3(0, y1, 0), base + d0 * r1 + Vector3(0, y1, 0)]
			var slope := Vector2(y1 - y0, -(r1 - r0)).normalized()   # outward normal in the profile plane
			var n0 := (d0 * slope.x + Vector3(0, slope.y, 0)).normalized()
			var n1 := (d1 * slope.x + Vector3(0, slope.y, 0)).normalized()
			var out := (n0 + n1).normalized()
			_face(st, [p[0], p[1], p[2]], [n0, n1, n1], out, [], c)
			_face(st, [p[0], p[2], p[3]], [n0, n1, n0], out, [], c)
			if inside:
				_face(st, [p[0], p[1], p[2]], [-n0, -n1, -n1], -out, [], c.darkened(0.35))
				_face(st, [p[0], p[2], p[3]], [-n0, -n1, -n0], -out, [], c.darkened(0.35))


## Octagonal rings [z, radius] along Z from `o` (a bird's body), `seg` sides.
func _tube(st: SurfaceTool, o: Vector3, rings: Array, c: Color, seg := 8) -> void:
	for r in rings.size() - 1:
		var z0: float = rings[r][0]
		var r0: float = rings[r][1]
		var z1: float = rings[r + 1][0]
		var r1: float = rings[r + 1][1]
		for i in seg:
			var a0 := TAU * i / seg
			var a1 := TAU * (i + 1) / seg
			var p := [o + Vector3(cos(a0) * r0, sin(a0) * r0 * 0.9, z0), o + Vector3(cos(a1) * r0, sin(a1) * r0 * 0.9, z0),
				o + Vector3(cos(a1) * r1, sin(a1) * r1 * 0.9, z1), o + Vector3(cos(a0) * r1, sin(a0) * r1 * 0.9, z1)]
			var nm := [Vector3(cos(a0), sin(a0), 0), Vector3(cos(a1), sin(a1), 0), Vector3(cos(a1), sin(a1), 0), Vector3(cos(a0), sin(a0), 0)]
			var out: Vector3 = nm[0] + nm[1]
			_face(st, [p[0], p[1], p[2]], [nm[0], nm[1], nm[2]], out, [], c)
			_face(st, [p[0], p[2], p[3]], [nm[0], nm[2], nm[3]], out, [], c)


## One triangle, wound so its front face (Godot: clockwise as seen) looks along `out`;
## degenerate ones are dropped (export_insects.gd).
func _face(st: SurfaceTool, v: Array, nm: Array, out: Vector3, uv := [], c := Color.WHITE) -> void:
	var g := ((v[2] as Vector3) - (v[0] as Vector3)).cross((v[1] as Vector3) - (v[0] as Vector3))
	if g.length_squared() < 1e-24:
		return
	var order := [0, 1, 2] if g.dot(out) > 0.0 else [0, 2, 1]
	for k in order:
		st.set_normal(nm[k])
		st.set_uv(uv[k] if not uv.is_empty() else _pal_uv(c))
		st.add_vertex(v[k])


## Colours as a palette texture (8 px blocks, so far mips keep them), as export_insects.gd.
const PAL_BLOCK := 8
const PAL_MAX := 32


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
	var m := StandardMaterial3D.new()
	m.resource_name = "paint"
	m.albedo_texture = ImageTexture.create_from_image(img)
	m.roughness = 0.9
	return m


func _add_player(root: Node3D, lib: AnimationLibrary) -> void:
	var ap := AnimationPlayer.new()
	ap.name = "AnimationPlayer"
	root.add_child(ap)
	ap.add_animation_library("", lib)
