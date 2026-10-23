extends "export_harbour.gd"
## Writes the catalogue's coastal and home set as glTF (kit/catalog/assets/coastal/): for a beach
## a palm tree, a wooden dock, a beach umbrella, a sun lounger, a beach towel, a scatter of shells,
## a coral cluster and a bed of kelp; for a modern house a sofa, a kitchen counter, a bathtub, a
## wardrobe and a rug. The rowboat is the harbour set's (export_harbour.gd). Same low-poly painted
## look and helpers as the harbour set (one palette texture per model, bottoms nobody sees left
## out), in colours that stay below the linear tonemap's white (no channel above 0.85).
##
##   godot --headless --path <any Godot 4 project> -s <iamar-kit>/kit/catalog/assets/export_coastal.gd
##   (then: python3 kit/catalog/assets/coastal.py record && python3 kit/catalog/catalog.py build)
##   IAMAR_COASTAL_ONLY=sofa,rug writes only those files (the rest stay as they are)
##
## Clips: kelp  sway  the blades waving in the swell (scene.json objects "animation": "sway").
## The sofa, kitchen counter and wardrobe face +Z (seat and doors toward the catalogue's thumbnail
## camera, as the city's furniture does): they are drawn facing -Z and turned round in _mesh.
## The dock's origin is the water's surface; the kelp's and coral's the sea floor.

const COASTAL_REL := "catalog/assets/coastal"
const TURNED := ["sofa", "kitchen_counter", "wardrobe"]   ## drawn facing -Z, written facing +Z
const STEMS := ["palm_tree", "dock", "beach_umbrella", "sun_lounger", "beach_towel", "sea_shells",
	"coral", "kelp", "sofa", "kitchen_counter", "bathtub", "wardrobe", "rug"]


func _run() -> void:
	var out := _kit.path_join(COASTAL_REL)
	DirAccess.make_dir_recursive_absolute(out)
	var only := OS.get_environment("IAMAR_COASTAL_ONLY").split(",", false)
	var ok := true
	for stem in STEMS:
		if only.is_empty() or stem in only:
			ok = _write(_coastal(stem), out.path_join(stem + ".glb")) and ok
	quit(0 if ok else 1)


var _turn := false


func _coastal(stem: String) -> Node3D:
	_turn = stem in TURNED
	var root := Node3D.new()
	root.name = stem
	match stem:
		"palm_tree": _palm(root)
		"dock": _dock(root)
		"beach_umbrella": _umbrella(root)
		"sun_lounger": _lounger(root)
		"beach_towel": _towel(root)
		"sea_shells": _shells(root)
		"coral": _coral(root)
		"kelp": _kelp(root)
		"sofa": _sofa(root)
		"kitchen_counter": _kitchen(root)
		"bathtub": _bathtub(root)
		"wardrobe": _wardrobe(root)
		"rug": _rug(root)
	return root


## The harbour set's _mesh, turning the mesh half round Y first for the TURNED models (a rotation,
## so the winding stays front-facing).
func _mesh(parent: Node3D, mname: String, st: SurfaceTool) -> void:
	if not _turn:
		super._mesh(parent, mname, st)
		return
	var a := st.commit_to_arrays()
	var flip := Basis(Vector3.UP, PI)
	var v: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
	var n: PackedVector3Array = a[Mesh.ARRAY_NORMAL]
	for i in v.size():
		v[i] = flip * v[i]
		n[i] = flip * n[i]
	a[Mesh.ARRAY_VERTEX] = v
	a[Mesh.ARRAY_NORMAL] = n
	var m := ArrayMesh.new()
	m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, a)
	_pending.append(m)
	var mi := MeshInstance3D.new()
	mi.name = mname
	mi.mesh = m
	parent.add_child(mi)


# ------------------------------------------------------------------ colours

const PALM_BARK := Color(0.5, 0.4, 0.29)
const PALM_BARK_DARK := Color(0.4, 0.31, 0.22)
const FROND := Color(0.3, 0.5, 0.22)
const FROND_UNDER := Color(0.36, 0.55, 0.3)
const COCONUT := Color(0.42, 0.32, 0.16)
const DECK := Color(0.6, 0.5, 0.38)       ## weathered (silvered) deck boards
const DECK_DARK := Color(0.5, 0.42, 0.32)
const PILE := Color(0.33, 0.27, 0.2)
const SAND_WHITE := Color(0.84, 0.82, 0.76)  ## "white" that survives the tonemap
const TEAL := Color(0.15, 0.52, 0.58)
const CORAL_RED := Color(0.8, 0.36, 0.3)
const SUN_YELLOW := Color(0.85, 0.7, 0.25)
const CHROME := Color(0.62, 0.64, 0.66)
const TEAK := Color(0.55, 0.38, 0.22)
const SHELL_PINK := Color(0.85, 0.7, 0.62)
const SHELL_CREAM := Color(0.82, 0.76, 0.62)
const SHELL_BROWN := Color(0.6, 0.45, 0.32)
const CORAL_PINK := Color(0.82, 0.45, 0.5)
const CORAL_ORANGE := Color(0.85, 0.52, 0.25)
const CORAL_PURPLE := Color(0.5, 0.3, 0.55)
const CORAL_YELLOW := Color(0.78, 0.7, 0.3)
const REEF_ROCK := Color(0.45, 0.43, 0.38)
const KELP := Color(0.38, 0.4, 0.15)
const KELP_DARK := Color(0.28, 0.3, 0.12)
const FABRIC := Color(0.33, 0.45, 0.55)    ## slate-blue sofa
const FABRIC_DARK := Color(0.27, 0.37, 0.46)
const CUSHION := Color(0.8, 0.72, 0.55)
const WALNUT := Color(0.32, 0.22, 0.15)
const CABINET := Color(0.45, 0.55, 0.5)    ## sage-green fronts
const WORKTOP := Color(0.72, 0.7, 0.66)    ## pale stone
const STEEL := Color(0.55, 0.57, 0.6)
const HOB := Color(0.13, 0.13, 0.14)
const TILE := Color(0.7, 0.78, 0.8)
const ENAMEL := Color(0.84, 0.84, 0.82)
const ENAMEL_IN := Color(0.76, 0.8, 0.82)
const OAK_LIGHT := Color(0.66, 0.52, 0.36)
const RUG_RED := Color(0.55, 0.2, 0.18)
const RUG_BLUE := Color(0.2, 0.25, 0.42)
const RUG_CREAM := Color(0.8, 0.72, 0.56)
const RUG_GOLD := Color(0.72, 0.55, 0.25)


## A quad seen from both sides (leaves, canopies, kelp blades); the back can take its own colour.
func _quad2(st: SurfaceTool, p: Array, out: Vector3, c: Color, back := Color(-1, 0, 0)) -> void:
	_quad(st, p, out, c)
	_quad(st, p, -out, c if back.r < 0.0 else back)


# ------------------------------------------------------------------ beach

## A coconut palm 6.4 m tall: a ringed trunk curving away from the sea wind, nine drooping
## fronds folded along their midrib, a bunch of coconuts under the crown.
func _palm(root: Node3D) -> void:
	var st := _begin()
	var segs := 9
	var pts := []
	for i in segs + 1:
		var t := float(i) / segs
		pts.append(Vector3(1.1 * t * t, 6.0 * t, 0.25 * t * t))
	for i in segs:
		var r0 := lerpf(0.24, 0.13, float(i) / segs) + (0.08 if i == 0 else 0.0)
		var r1 := lerpf(0.24, 0.13, float(i + 1) / segs)
		_cyl(st, pts[i], pts[i + 1], r0, r1, 7, PALM_BARK if i % 2 == 0 else PALM_BARK_DARK)
	var top: Vector3 = pts[segs]
	_lathe(st, top + Vector3(0, -0.05, 0), [[0.15, 0.0], [0.2, 0.15], [0.12, 0.32], [0.0, 0.38]], 7, [PALM_BARK_DARK, FROND, FROND])
	_mesh(root, "Trunk", st)
	var cr := _begin()
	var nf := 9
	for f in nf:
		var a := TAU * float(f) / nf + 0.3 * sin(f * 2.3)
		var dir := Vector3(cos(a), 0, sin(a))
		var side := dir.cross(Vector3.UP).normalized()
		var length := 2.7 + 0.35 * sin(f * 1.7)
		var lift := 0.55 + 0.25 * cos(f * 2.9)
		var n := 6
		var spine := []
		for k in n + 1:
			var t := float(k) / n
			spine.append(top + Vector3(0, 0.25, 0) + dir * (length * t) + Vector3(0, lift * t - 1.9 * t * t, 0))
		for k in n:
			var t0 := float(k) / n
			var t1 := float(k + 1) / n
			var w0 := 0.5 * pow(sin(PI * clampf(t0 * 0.95 + 0.05, 0.0, 1.0)), 0.6)
			var w1 := 0.5 * pow(sin(PI * clampf(t1 * 0.95 + 0.05, 0.0, 1.0)), 0.6)
			if k == n - 1:
				w1 = 0.0
			var fold := Vector3(0, -0.12, 0)   # the blade's two halves hang below the midrib
			var s0: Vector3 = spine[k]
			var s1: Vector3 = spine[k + 1]
			for sg in [1.0, -1.0]:
				var p := [s0, s1, s1 + side * w1 * sg + fold * (w1 / 0.5), s0 + side * w0 * sg + fold * (w0 / 0.5)]
				_quad2(cr, p, Vector3.UP, FROND, FROND_UNDER)
	# coconuts under the crown
	for k in 4:
		var a := TAU * float(k) / 4.0 + 0.4
		var c := top + Vector3(cos(a) * 0.22, -0.12 - 0.08 * (k % 2), sin(a) * 0.22)
		_lathe(cr, c, [[0.0, -0.1], [0.08, -0.07], [0.11, 0.0], [0.08, 0.07], [0.0, 0.1]], 6, [COCONUT])
	_mesh(root, "Crown", cr)


## A wooden dock 2 m wide and 9 m long on two rows of piles: 22 deck boards with gaps, two
## stringers, a ladder down into the water at the far end and two mooring cleats. Origin = the
## water's surface at the shore end; the deck is 0.6 m above it and runs out along -Z.
func _dock(root: Node3D) -> void:
	var st := _begin()
	var deck_y := 0.6
	var length := 9.0
	var width := 2.0
	var n := 22
	var pitch := length / n
	for i in n:
		var z := -pitch * (i + 0.5)
		var jog := 0.03 * sin(i * 3.7)
		_box(st, Vector3(jog, deck_y - 0.03, z), Vector3(width + 0.02 * sin(i * 1.3), 0.06, pitch - 0.035), DECK if i % 3 else DECK_DARK, false)
	for sg in [1.0, -1.0]:
		_box(st, Vector3(sg * (width * 0.5 - 0.15), deck_y - 0.16, -length * 0.5), Vector3(0.1, 0.2, length), PILE, false)
		_box(st, Vector3(sg * (width * 0.5 + 0.03), deck_y - 0.1, -length * 0.5), Vector3(0.05, 0.16, length), DECK_DARK, false)
		for k in 4:
			var z := -0.4 - k * (length - 0.8) / 3.0
			_cyl(st, Vector3(sg * (width * 0.5 - 0.05), -2.2, z), Vector3(sg * (width * 0.5 - 0.05), deck_y + 0.15, z), 0.12, 0.11, 6, PILE, true)
		# a cleat on each side near the far end
		_box(st, Vector3(sg * (width * 0.5 - 0.25), deck_y + 0.04, -length + 0.8), Vector3(0.06, 0.08, 0.3), IRON)
	# ladder down from the end of the dock
	for sg in [1.0, -1.0]:
		_box(st, Vector3(sg * 0.25, deck_y - 0.8, -length - 0.05), Vector3(0.05, 2.0, 0.05), PILE)
	for k in 4:
		_box(st, Vector3(0, deck_y - 0.3 - k * 0.38, -length - 0.05), Vector3(0.5, 0.04, 0.06), DECK_DARK)
	_mesh(root, "Dock", st)


## A beach umbrella 2.4 m tall: a white pole with a tilt joint, an eight-panel canopy in
## alternating teal and off-white with a scalloped valance, ribs underneath.
func _umbrella(root: Node3D) -> void:
	var st := _begin()
	_cyl(st, Vector3(0, -0.35, 0), Vector3(0, 2.35, 0), 0.025, 0.022, 6, SAND_WHITE, true)
	_cyl(st, Vector3(0, 1.4, 0), Vector3(0, 1.48, 0), 0.04, 0.04, 6, CHROME, true)
	var nseg := 8
	var r := 1.15
	var rim_y := 1.95
	var apex := Vector3(0, 2.32, 0)
	for i in nseg:
		var a0 := TAU * float(i) / nseg
		var a1 := TAU * float(i + 1) / nseg
		var p0 := Vector3(cos(a0) * r, rim_y, sin(a0) * r)
		var p1 := Vector3(cos(a1) * r, rim_y, sin(a1) * r)
		var c := TEAL if i % 2 == 0 else SAND_WHITE
		var out := ((p0 + p1) * 0.5 - apex).cross(p1 - p0).normalized()
		if out.y < 0.0:
			out = -out
		_face(st, [apex, p0, p1], [out, out, out], out, [], c)
		_face(st, [apex, p0, p1], [-out, -out, -out], -out, [], c.darkened(0.25))
		# valance flap below the rim
		var d := Vector3(0, -0.12, 0)
		var m := (p0 + p1) * 0.5 * 1.0
		_quad2(st, [p0, p1, p1 + d, p0 + d], m.normalized(), c)
		_line(st, Vector3(0, 1.62, 0), p0 * Vector3(0.85, 1, 0.85) + Vector3(0, -0.04, 0), SAND_WHITE)
	_mesh(root, "Umbrella", st)


## A teak sun lounger 1.95 m long: four legs, side rails, slats, the backrest raised at the +Z
## end, and a striped cushion pad on top.
func _lounger(root: Node3D) -> void:
	var st := _begin()
	var w := 0.66
	var y := 0.34
	for sx in [1.0, -1.0]:
		for z in [-0.85, 0.75]:
			_box(st, Vector3(sx * (w * 0.5 - 0.03), y * 0.5, z), Vector3(0.05, y, 0.05), TEAK, false)
		_box(st, Vector3(sx * (w * 0.5 - 0.02), y - 0.02, -0.15), Vector3(0.04, 0.08, 1.4), TEAK)
	for k in 8:
		_box(st, Vector3(0, y + 0.03, -0.8 + k * 0.17), Vector3(w - 0.04, 0.02, 0.12), TEAK)
	# backrest: a hinged slatted panel at 40 degrees
	var hinge := Vector3(0, y + 0.03, 0.55)
	var up := Vector3(0, sin(deg_to_rad(40.0)), cos(deg_to_rad(40.0)))
	var back_len := 0.75
	var across := Vector3(w * 0.5 - 0.02, 0, 0)
	for sx in [1.0, -1.0]:
		_cyl(st, hinge + Vector3(sx * (w * 0.5 - 0.02), 0, 0), hinge + Vector3(sx * (w * 0.5 - 0.02), 0, 0) + up * back_len, 0.025, 0.025, 4, TEAK)
	_cyl(st, hinge + up * 0.3 + Vector3(0, -0.05, 0.05), Vector3(0, y - 0.02, 0.85), 0.015, 0.015, 4, TEAK)
	# cushion pad: flat part and back part, three stripes along it
	var pad_y := y + 0.065
	var bands := [CUSHION, TEAL, CUSHION]
	for b in 3:
		var x0 := -across.x + 2.0 * across.x * b / 3.0
		var x1 := -across.x + 2.0 * across.x * (b + 1) / 3.0
		_quad(st, [Vector3(x0, pad_y, -0.92), Vector3(x1, pad_y, -0.92), Vector3(x1, pad_y, 0.55), Vector3(x0, pad_y, 0.55)], Vector3.UP, bands[b])
		var h0 := hinge + Vector3(0, 0.035, -0.02)
		var nrm := up.cross(Vector3.RIGHT).normalized()
		if nrm.y < 0.0:
			nrm = -nrm
		_quad(st, [h0 + Vector3(x0, 0, 0), h0 + Vector3(x1, 0, 0), h0 + Vector3(x1, 0, 0) + up * back_len, h0 + Vector3(x0, 0, 0) + up * back_len], nrm, bands[b])
	# pad edges
	_quad(st, [Vector3(-across.x, pad_y, -0.92), Vector3(across.x, pad_y, -0.92), Vector3(across.x, y + 0.04, -0.92), Vector3(-across.x, y + 0.04, -0.92)], Vector3.FORWARD, CUSHION)
	for sx in [1.0, -1.0]:
		_quad(st, [Vector3(sx * across.x, pad_y, -0.92), Vector3(sx * across.x, pad_y, 0.55), Vector3(sx * across.x, y + 0.04, 0.55), Vector3(sx * across.x, y + 0.04, -0.92)], Vector3(sx, 0, 0), CUSHION)
	_mesh(root, "Lounger", st)


## A striped beach towel 1.7 x 0.85 m laid flat on the sand, one corner folded back.
func _towel(root: Node3D) -> void:
	var st := _begin()
	var cols := [CORAL_RED, SAND_WHITE, SUN_YELLOW, SAND_WHITE, TEAL, SAND_WHITE, CORAL_RED]
	var hw := 0.425
	var tl := 1.7
	var y := 0.012
	var nb := cols.size()
	for b in nb:
		var z0 := -tl * 0.5 + tl * b / nb
		var z1 := -tl * 0.5 + tl * (b + 1) / nb
		var xr := hw if b < nb - 1 else hw - 0.25   # the last band's corner is folded
		_quad(st, [Vector3(-hw, y, z0), Vector3(xr, y, z0), Vector3(xr, y, z1), Vector3(-hw, y, z1)], Vector3.UP, cols[b])
	var z0b := tl * 0.5 - tl / nb
	_face(st, [Vector3(hw - 0.25, y, z0b), Vector3(hw, y, z0b), Vector3(hw - 0.25, y, tl * 0.5)], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], CORAL_RED)
	# the folded flap lies back on the towel, showing its paler underside
	_face(st, [Vector3(hw - 0.25, y + 0.01, tl * 0.5), Vector3(hw, y + 0.01, z0b), Vector3(hw - 0.25, y + 0.01, z0b - 0.25)], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], SHELL_CREAM)
	# thin hem along the edges so it reads from low angles
	for sx in [1.0, -1.0]:
		_quad(st, [Vector3(sx * hw, y, -tl * 0.5), Vector3(sx * hw, y, tl * 0.5 - (0.25 if sx > 0 else 0.0)), Vector3(sx * hw, 0.0, tl * 0.5 - (0.25 if sx > 0 else 0.0)), Vector3(sx * hw, 0.0, -tl * 0.5)], Vector3(sx, 0, 0), SAND_WHITE)
	_mesh(root, "Towel", st)


## A scatter of sea shells over about 1 x 0.8 m: scallops, cone-shaped whelks, clams and a
## starfish, lying on the sand at the tide line.
func _shells(root: Node3D) -> void:
	var st := _begin()
	var spots := [[-0.35, -0.2, 0.0, SHELL_PINK], [0.22, -0.28, 1.2, SHELL_CREAM], [0.05, 0.25, 2.6, SHELL_PINK],
		[-0.4, 0.3, 4.0, SHELL_CREAM]]
	for s in spots:
		_scallop(st, Vector3(s[0], 0, s[1]), float(s[2]), 0.07, s[3])
	for s in [[0.4, 0.1, 0.4], [-0.1, -0.05, 2.0], [0.3, 0.35, 5.0]]:
		_whelk(st, Vector3(s[0], 0, s[1]), float(s[2]))
	for s in [[-0.18, 0.1], [0.45, -0.3], [-0.5, -0.05]]:
		_lathe(st, Vector3(s[0], 0, s[1]), [[0.045, 0.0], [0.04, 0.012], [0.025, 0.02], [0.0, 0.024]], 7, [SHELL_BROWN, SHELL_CREAM])
	_starfish(st, Vector3(0.15, 0.0, 0.0), 0.09)
	_mesh(root, "Shells", st)


func _scallop(st: SurfaceTool, c: Vector3, yaw: float, r: float, col: Color) -> void:
	var ribs := 7
	var hinge := c + Vector3(sin(yaw), 0, cos(yaw)) * r * 0.5
	for i in ribs:
		var a0 := yaw + PI + lerpf(-1.1, 1.1, float(i) / ribs)
		var a1 := yaw + PI + lerpf(-1.1, 1.1, float(i + 1) / ribs)
		var p0 := hinge + Vector3(sin(a0), 0, cos(a0)) * r
		var p1 := hinge + Vector3(sin(a1), 0, cos(a1)) * r
		var mid := (p0 + p1) * 0.5 + Vector3(0, 0.02, 0)
		var top := hinge + Vector3(0, 0.025, 0)
		_face(st, [top, p0 + Vector3(0, 0.004, 0), mid], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], col)
		_face(st, [top, mid, p1 + Vector3(0, 0.004, 0)], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], col.darkened(0.12))


func _whelk(st: SurfaceTool, c: Vector3, yaw: float) -> void:
	# a cone lying on its side: a lathe along +Y, then turned flat by building it in place
	var ax := Vector3(sin(yaw), 0.15, cos(yaw)).normalized()
	var prof := [[0.0, 0.0], [0.03, 0.02], [0.035, 0.05], [0.025, 0.08], [0.012, 0.11], [0.0, 0.13]]
	var cols := [SHELL_CREAM, SHELL_BROWN, SHELL_CREAM, SHELL_BROWN, SHELL_CREAM]
	for k in prof.size() - 1:
		var a := c + Vector3(0, 0.03, 0) + ax * float(prof[k][1])
		var b := c + Vector3(0, 0.03, 0) + ax * float(prof[k + 1][1])
		_cyl(st, a, b, maxf(float(prof[k][0]), 0.002), maxf(float(prof[k + 1][0]), 0.002), 6, cols[k])


func _starfish(st: SurfaceTool, c: Vector3, r: float) -> void:
	var top := c + Vector3(0, 0.02, 0)
	for i in 5:
		var a := TAU * float(i) / 5.0
		var tip := c + Vector3(cos(a), 0, sin(a)) * r + Vector3(0, 0.005, 0)
		var l := c + Vector3(cos(a - 0.6), 0, sin(a - 0.6)) * r * 0.3
		var rr := c + Vector3(cos(a + 0.6), 0, sin(a + 0.6)) * r * 0.3
		_face(st, [top, l, tip], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], CORAL_ORANGE)
		_face(st, [top, tip, rr], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], CORAL_ORANGE.darkened(0.15))


## A coral cluster 1.4 m across on a reef rock: a brain coral dome, branching staghorn coral,
## a sea fan and a clump of tube sponges, in muted reef colours. Origin = the sea floor.
func _coral(root: Node3D) -> void:
	var st := _begin()
	_lathe(st, Vector3(0, -0.05, 0), [[0.7, 0.0], [0.62, 0.12], [0.4, 0.22], [0.0, 0.26]], 9, [REEF_ROCK])
	# brain coral: a ribbed dome
	_lathe(st, Vector3(-0.3, 0.12, 0.15), [[0.32, 0.0], [0.3, 0.1], [0.24, 0.2], [0.13, 0.27], [0.0, 0.3]], 10,
		[CORAL_YELLOW, CORAL_YELLOW.darkened(0.12), CORAL_YELLOW, CORAL_YELLOW.darkened(0.12)])
	# staghorn: branches forking twice
	_branch(st, Vector3(0.28, 0.15, -0.1), Vector3(0.1, 1.0, -0.15).normalized(), 0.32, 0.045, 3, CORAL_PINK)
	_branch(st, Vector3(0.1, 0.18, -0.35), Vector3(-0.2, 1.0, -0.3).normalized(), 0.28, 0.04, 3, CORAL_ORANGE)
	# sea fan: a flat lattice standing across the current
	var fan_c := Vector3(-0.15, 0.2, -0.3)
	var fan_n := Vector3(0.3, 0, 1).normalized()
	var fan_u := Vector3.UP.cross(fan_n).normalized()
	for i in 6:
		var a0 := lerpf(-1.2, 1.2, float(i) / 6.0)
		var a1 := lerpf(-1.2, 1.2, float(i + 1) / 6.0)
		var d0 := fan_u * sin(a0) + Vector3.UP * cos(a0)
		var d1 := fan_u * sin(a1) + Vector3.UP * cos(a1)
		_quad2(st, [fan_c, fan_c + d0 * 0.15, fan_c + (d0 + d1).normalized() * 0.62, fan_c + d1 * 0.15], fan_n, CORAL_PURPLE)
		_face(st, [fan_c + d0 * 0.15, fan_c + d0 * 0.55, fan_c + (d0 + d1).normalized() * 0.62], [fan_n, fan_n, fan_n], fan_n, [], CORAL_PURPLE.darkened(0.1))
		_face(st, [fan_c + d0 * 0.15, fan_c + d0 * 0.55, fan_c + (d0 + d1).normalized() * 0.62], [-fan_n, -fan_n, -fan_n], -fan_n, [], CORAL_PURPLE.darkened(0.1))
	# tube sponges: open cylinders, dark inside
	for t in [[0.35, 0.3, 0.38], [0.48, 0.18, 0.28], [0.25, 0.42, 0.22]]:
		var b := Vector3(t[0], 0.14, t[1])
		_lathe(st, b, [[0.06, 0.0], [0.065, float(t[2])], [0.05, float(t[2])]], 7, [CORAL_ORANGE, CORAL_ORANGE.darkened(0.3)], true)
	_mesh(root, "Coral", st)


func _branch(st: SurfaceTool, a: Vector3, dir: Vector3, length: float, r: float, depth: int, c: Color) -> void:
	var b := a + dir * length
	_cyl(st, a, b, r, r * 0.75, 5, c, depth == 1)
	if depth <= 1:
		return
	var side := dir.cross(Vector3.FORWARD if absf(dir.z) < 0.9 else Vector3.RIGHT).normalized()
	for sg in [1.0, -1.0]:
		var nd: Vector3 = (dir + side * 0.7 * sg + Vector3(0, 0.15, 0)).normalized().rotated(dir, 0.6 * sg * depth)
		_branch(st, b, nd, length * 0.75, r * 0.72, depth - 1, c)


## A bed of giant kelp: eight blades 1.4 to 2.6 m tall rising from a rocky holdfast, each its own
## node so clip "sway" waves them in the swell (out of phase). Origin = the sea floor.
func _kelp(root: Node3D) -> void:
	var base := _begin()
	_lathe(base, Vector3.ZERO, [[0.45, 0.0], [0.38, 0.1], [0.2, 0.18], [0.0, 0.2]], 8, [REEF_ROCK])
	_mesh(root, "Holdfast", base)
	var lib := AnimationLibrary.new()
	var anim := Animation.new()
	anim.length = 6.0
	anim.loop_mode = Animation.LOOP_LINEAR
	var nb := 8
	for i in nb:
		var a := TAU * float(i) / nb + 0.4 * sin(i * 3.1)
		var foot := Vector3(cos(a) * 0.22, 0.12, sin(a) * 0.22)
		var blade := Node3D.new()
		blade.name = "Blade%d" % i
		blade.position = foot
		root.add_child(blade)
		var st := _begin()
		var h := 1.4 + 1.2 * fmod(i * 0.618, 1.0)
		var n := 8
		var face_dir := Vector3(-sin(a), 0, cos(a))
		var width_dir := face_dir.cross(Vector3.UP).normalized()
		for k in n:
			var t0 := float(k) / n
			var t1 := float(k + 1) / n
			var c0 := Vector3(cos(a), 0, sin(a)) * 0.12 * sin(t0 * 5.0 + i) + Vector3(0, h * t0, 0)
			var c1 := Vector3(cos(a), 0, sin(a)) * 0.12 * sin(t1 * 5.0 + i) + Vector3(0, h * t1, 0)
			var w0 := 0.03 + 0.09 * sin(PI * minf(t0 * 1.2, 1.0))
			var w1 := 0.03 + 0.09 * sin(PI * minf(t1 * 1.2, 1.0))
			if k == n - 1:
				w1 = 0.01
			var ripple := width_dir * 0.03 * sin(k * 2.0)
			_quad2(st, [c0 - width_dir * w0 + ripple, c0 + width_dir * w0 - ripple, c1 + width_dir * w1 + ripple, c1 - width_dir * w1 - ripple],
				face_dir, KELP if k % 2 == 0 else KELP_DARK)
		_mesh(blade, "Mesh", st)
		var tr := anim.add_track(Animation.TYPE_ROTATION_3D)
		anim.track_set_path(tr, NodePath(blade.name))
		for key in 13:
			var t := 6.0 * key / 12.0
			var ph := TAU * t / 6.0 + i * 0.9
			var q := Quaternion(Vector3.RIGHT, 0.14 * sin(ph)) * Quaternion(Vector3.BACK, 0.09 * sin(ph * 2.0 + 0.5))
			anim.rotation_track_insert_key(tr, t, q)
	lib.add_animation("sway", anim)
	_add_player(root, lib)


# ------------------------------------------------------------------ home

## A three-seat sofa 2.1 m wide, seat at 0.45 m: an upholstered base, three seat and three back
## cushions, rounded arms, walnut legs. Drawn facing -Z, written facing +Z (TURNED).
func _sofa(root: Node3D) -> void:
	var st := _begin()
	var w := 2.1
	var d := 0.9
	_box(st, Vector3(0, 0.25, 0), Vector3(w - 0.3, 0.24, d - 0.05), FABRIC_DARK, false)
	for sx in [1.0, -1.0]:
		for z in [-0.35, 0.35]:
			_cyl(st, Vector3(sx * (w * 0.5 - 0.12), 0.0, z), Vector3(sx * (w * 0.5 - 0.12), 0.13, z), 0.025, 0.03, 5, WALNUT, true)
		# arm: a box topped by a half-round roll
		_box(st, Vector3(sx * (w * 0.5 - 0.08), 0.37, 0), Vector3(0.16, 0.48, d), FABRIC, false)
		_cyl(st, Vector3(sx * (w * 0.5 - 0.08), 0.61, -d * 0.5), Vector3(sx * (w * 0.5 - 0.08), 0.61, d * 0.5), 0.08, 0.08, 6, FABRIC, true)
	var sw := (w - 0.32) / 3.0
	for i in 3:
		var x := -w * 0.5 + 0.16 + sw * (i + 0.5)
		_box(st, Vector3(x, 0.43, -0.07), Vector3(sw - 0.02, 0.13, d - 0.2), FABRIC, false)
		# back cushion, leaning back
		var bc := Vector3(x, 0.68, 0.3)
		var tilt := Basis(Vector3.RIGHT, deg_to_rad(-12.0))
		var hs := Vector3((sw - 0.03) * 0.5, 0.24, 0.09)
		var corners := []
		for cy in [-1.0, 1.0]:
			for cz in [-1.0, 1.0]:
				for cx in [-1.0, 1.0]:
					corners.append(bc + tilt * Vector3(hs.x * cx, hs.y * cy, hs.z * cz))
		# faces of the tilted box (front, top, back, sides)
		_quad(st, [corners[0], corners[1], corners[5], corners[4]], tilt * Vector3.FORWARD, FABRIC)
		_quad(st, [corners[4], corners[5], corners[7], corners[6]], tilt * Vector3.UP, FABRIC)
		_quad(st, [corners[2], corners[3], corners[7], corners[6]], tilt * Vector3.BACK, FABRIC_DARK)
		_quad(st, [corners[0], corners[2], corners[6], corners[4]], tilt * Vector3.LEFT, FABRIC_DARK)
		_quad(st, [corners[1], corners[3], corners[7], corners[5]], tilt * Vector3.RIGHT, FABRIC_DARK)
	# the back frame behind the cushions
	_box(st, Vector3(0, 0.55, d * 0.5 - 0.06), Vector3(w - 0.3, 0.5, 0.12), FABRIC_DARK, false)
	# a scatter cushion in the corner
	_box(st, Vector3(-w * 0.5 + 0.35, 0.62, 0.12), Vector3(0.38, 0.36, 0.12), CUSHION)
	_mesh(root, "Sofa", st)


## A fitted kitchen counter 2.4 m long and 0.9 m high: base cabinets with doors and a drawer
## row, a pale stone worktop, an inset steel sink with a swan-neck tap, a four-ring hob and a
## tiled splashback. Drawn facing -Z, written facing +Z (TURNED).
func _kitchen(root: Node3D) -> void:
	var st := _begin()
	var L := 2.4
	var D := 0.62
	var H := 0.9
	var top_t := 0.04
	# plinth set back, carcass, the back panel
	_box(st, Vector3(0, 0.05, 0.05), Vector3(L, 0.1, D - 0.1), WALNUT, false)
	_box(st, Vector3(0, 0.1 + (H - 0.1 - top_t) * 0.5, 0.01), Vector3(L, H - 0.1 - top_t, D - 0.02), CABINET.darkened(0.15), false)
	# door and drawer fronts on the -Z face, with handles
	var n := 4
	var dw := L / n
	for i in n:
		var x := -L * 0.5 + dw * (i + 0.5)
		_box(st, Vector3(x, 0.42, -D * 0.5 - 0.005), Vector3(dw - 0.02, 0.58, 0.02), CABINET)
		_box(st, Vector3(x, 0.79, -D * 0.5 - 0.005), Vector3(dw - 0.02, 0.13, 0.02), CABINET)
		_box(st, Vector3(x, 0.79, -D * 0.5 - 0.03), Vector3(0.16, 0.015, 0.015), STEEL)
		_box(st, Vector3(x + (dw * 0.5 - 0.07) * (1.0 if i % 2 == 0 else -1.0), 0.6, -D * 0.5 - 0.03), Vector3(0.015, 0.14, 0.015), STEEL)
	# worktop with a hole for the sink (x in [-0.85, -0.35], z in [-0.15, 0.15])
	var ty := H - top_t * 0.5
	var sx0 := -0.85
	var sx1 := -0.35
	var sz0 := -0.17
	var sz1 := 0.13
	var z_front := -D * 0.5 - 0.03
	var z_back := D * 0.5
	var x_l := -L * 0.5
	var x_r := L * 0.5
	_box(st, Vector3((x_l + sx0) * 0.5, ty, (z_front + z_back) * 0.5), Vector3(sx0 - x_l, top_t, z_back - z_front), WORKTOP, false)
	_box(st, Vector3((sx1 + x_r) * 0.5, ty, (z_front + z_back) * 0.5), Vector3(x_r - sx1, top_t, z_back - z_front), WORKTOP, false)
	_box(st, Vector3((sx0 + sx1) * 0.5, ty, (z_front + sz0) * 0.5), Vector3(sx1 - sx0, top_t, sz0 - z_front), WORKTOP, false)
	_box(st, Vector3((sx0 + sx1) * 0.5, ty, (sz1 + z_back) * 0.5), Vector3(sx1 - sx0, top_t, z_back - sz1), WORKTOP, false)
	# sink basin: inner walls and floor, seen from above
	var by := H - 0.2
	var tyt := H
	_quad(st, [Vector3(sx0, by, sz0), Vector3(sx1, by, sz0), Vector3(sx1, by, sz1), Vector3(sx0, by, sz1)], Vector3.UP, STEEL.darkened(0.15))
	_quad(st, [Vector3(sx0, by, sz0), Vector3(sx1, by, sz0), Vector3(sx1, tyt, sz0), Vector3(sx0, tyt, sz0)], Vector3.BACK, STEEL)
	_quad(st, [Vector3(sx0, by, sz1), Vector3(sx1, by, sz1), Vector3(sx1, tyt, sz1), Vector3(sx0, tyt, sz1)], Vector3.FORWARD, STEEL)
	_quad(st, [Vector3(sx0, by, sz0), Vector3(sx0, by, sz1), Vector3(sx0, tyt, sz1), Vector3(sx0, tyt, sz0)], Vector3.RIGHT, STEEL)
	_quad(st, [Vector3(sx1, by, sz0), Vector3(sx1, by, sz1), Vector3(sx1, tyt, sz1), Vector3(sx1, tyt, sz0)], Vector3.LEFT, STEEL)
	# swan-neck tap behind the sink
	var tb := Vector3(-0.6, H, 0.22)
	_cyl(st, tb, tb + Vector3(0, 0.3, 0), 0.018, 0.016, 6, STEEL)
	_cyl(st, tb + Vector3(0, 0.3, 0), tb + Vector3(0, 0.32, -0.16), 0.016, 0.014, 6, STEEL)
	_cyl(st, tb + Vector3(0, 0.32, -0.16), tb + Vector3(0, 0.24, -0.2), 0.014, 0.012, 6, STEEL, true)
	# hob: a black glass panel with four rings
	var hx := 0.55
	_box(st, Vector3(hx, H + 0.004, -0.02), Vector3(0.58, 0.008, 0.5), HOB, false)
	for k in 4:
		var rc := Vector3(hx + (-0.14 if k % 2 == 0 else 0.14), H + 0.009, -0.02 + (-0.12 if k < 2 else 0.12))
		_ring(st, rc, 0.08 if k % 3 == 0 else 0.06, 0.006, 8, Color(0.3, 0.3, 0.32))
	# tiled splashback against the wall
	_box(st, Vector3(0, H + 0.25, z_back - 0.01), Vector3(L, 0.5, 0.02), TILE, false)
	_mesh(root, "Counter", st)


## A freestanding bath 1.7 x 0.78 m: an off-white enamel shell with a rolled rim and a deep
## basin, a plinth, a chrome mixer tap and an overflow. Long side along X, tap end at +X.
func _bathtub(root: Node3D) -> void:
	var st := _begin()
	var L := 1.7
	var W := 0.78
	var H := 0.58
	var rim := 0.07
	_box(st, Vector3(0, 0.04, 0), Vector3(L - 0.2, 0.08, W - 0.18), WALNUT, false)
	# outer shell, slightly flared to the rim
	var ob := [Vector3(-L * 0.5 + 0.06, 0.08, -W * 0.5 + 0.05), Vector3(L * 0.5 - 0.06, 0.08, -W * 0.5 + 0.05),
		Vector3(L * 0.5 - 0.06, 0.08, W * 0.5 - 0.05), Vector3(-L * 0.5 + 0.06, 0.08, W * 0.5 - 0.05)]
	var ot := [Vector3(-L * 0.5, H, -W * 0.5), Vector3(L * 0.5, H, -W * 0.5), Vector3(L * 0.5, H, W * 0.5), Vector3(-L * 0.5, H, W * 0.5)]
	var outs := [Vector3.FORWARD, Vector3.RIGHT, Vector3.BACK, Vector3.LEFT]
	for i in 4:
		var j := (i + 1) % 4
		_quad(st, [ob[i], ob[j], ot[j], ot[i]], outs[i], ENAMEL)
	# inner basin: narrower at the bottom, sloped back at the -X end
	var it := []
	for p in ot:
		it.append(Vector3((p as Vector3).x - signf((p as Vector3).x) * rim, H, (p as Vector3).z - signf((p as Vector3).z) * rim))
	var ib := [Vector3(-L * 0.5 + 0.38, 0.14, -W * 0.5 + 0.17), Vector3(L * 0.5 - 0.2, 0.14, -W * 0.5 + 0.17),
		Vector3(L * 0.5 - 0.2, 0.14, W * 0.5 - 0.17), Vector3(-L * 0.5 + 0.38, 0.14, W * 0.5 - 0.17)]
	for i in 4:
		var j := (i + 1) % 4
		_quad(st, [ib[i], ib[j], it[j], it[i]], -outs[i] + Vector3.UP * 0.2, ENAMEL_IN)
		# rolled rim between the outer and inner top edges
		_quad(st, [ot[i], ot[j], it[j], it[i]], Vector3.UP, ENAMEL)
	_quad(st, ib, Vector3.UP, ENAMEL_IN.darkened(0.05))
	_lathe(st, Vector3(L * 0.5 - 0.3, 0.141, 0), [[0.03, 0.0], [0.0, 0.002]], 6, [CHROME])
	# mixer tap on the rim at +X, an overflow disc on the inside wall
	var tp := Vector3(L * 0.5 - rim * 0.5, H, 0)
	_cyl(st, tp, tp + Vector3(0, 0.16, 0), 0.02, 0.02, 6, CHROME)
	_cyl(st, tp + Vector3(0, 0.16, 0), tp + Vector3(-0.17, 0.14, 0), 0.016, 0.014, 6, CHROME, true)
	for sz in [1.0, -1.0]:
		_cyl(st, tp + Vector3(0, 0.07, 0.06 * sz), tp + Vector3(0, 0.09, 0.1 * sz), 0.018, 0.018, 6, CHROME, true)
	_mesh(root, "Bath", st)


## A double wardrobe 1.2 m wide, 0.6 m deep and 2.1 m tall in light oak: two doors with a
## shadow gap, long steel bar handles, a plinth and a top cornice. Drawn facing -Z, written facing +Z.
func _wardrobe(root: Node3D) -> void:
	var st := _begin()
	var W := 1.2
	var D := 0.6
	var H := 2.1
	_box(st, Vector3(0, 0.04, 0.02), Vector3(W - 0.04, 0.08, D - 0.04), WALNUT, false)
	_box(st, Vector3(0, 0.08 + (H - 0.12) * 0.5, 0), Vector3(W, H - 0.12, D), OAK_LIGHT.darkened(0.1), false)
	_box(st, Vector3(0, H - 0.02, -0.01), Vector3(W + 0.04, 0.04, D + 0.04), OAK_LIGHT)
	for sx in [1.0, -1.0]:
		var dx: float = sx * (W * 0.25)
		_box(st, Vector3(dx, 0.08 + (H - 0.14) * 0.5, -D * 0.5 - 0.01), Vector3(W * 0.5 - 0.012, H - 0.16, 0.02), OAK_LIGHT)
		_box(st, Vector3(sx * 0.06, 1.05, -D * 0.5 - 0.045), Vector3(0.018, 0.5, 0.018), STEEL)
		for y in [0.82, 1.28]:
			_box(st, Vector3(sx * 0.06, y, -D * 0.5 - 0.03), Vector3(0.012, 0.012, 0.03), STEEL)
	_mesh(root, "Wardrobe", st)


## A woven rug 2.4 x 1.7 m: a red field with a central blue-and-gold medallion, a cream inner
## border, a deep blue outer border and a fringe at both short ends.
func _rug(root: Node3D) -> void:
	var st := _begin()
	var y := 0.012
	var bands := [[1.2, 0.85, RUG_BLUE], [1.08, 0.73, RUG_CREAM], [1.02, 0.67, RUG_GOLD], [0.96, 0.61, RUG_RED]]
	for b in bands.size():
		var ox: float = bands[b][0]
		var oz: float = bands[b][1]
		var c: Color = bands[b][2]
		if b == bands.size() - 1:
			_rug_field(st, ox, oz, y, c)
			continue
		var ix: float = bands[b + 1][0]
		var iz: float = bands[b + 1][1]
		# a frame: four quads between the outer and inner rectangle
		_quad(st, [Vector3(-ox, y, -oz), Vector3(ox, y, -oz), Vector3(ix, y, -iz), Vector3(-ix, y, -iz)], Vector3.UP, c)
		_quad(st, [Vector3(ox, y, -oz), Vector3(ox, y, oz), Vector3(ix, y, iz), Vector3(ix, y, -iz)], Vector3.UP, c)
		_quad(st, [Vector3(ox, y, oz), Vector3(-ox, y, oz), Vector3(-ix, y, iz), Vector3(ix, y, iz)], Vector3.UP, c)
		_quad(st, [Vector3(-ox, y, oz), Vector3(-ox, y, -oz), Vector3(-ix, y, -iz), Vector3(-ix, y, iz)], Vector3.UP, c)
	# edges, so it has a little thickness from low angles
	_quad(st, [Vector3(-1.2, y, -0.85), Vector3(1.2, y, -0.85), Vector3(1.2, 0, -0.85), Vector3(-1.2, 0, -0.85)], Vector3.FORWARD, RUG_BLUE)
	_quad(st, [Vector3(-1.2, y, 0.85), Vector3(1.2, y, 0.85), Vector3(1.2, 0, 0.85), Vector3(-1.2, 0, 0.85)], Vector3.BACK, RUG_BLUE)
	for sx in [1.0, -1.0]:
		_quad(st, [Vector3(sx * 1.2, y, -0.85), Vector3(sx * 1.2, y, 0.85), Vector3(sx * 1.2, 0, 0.85), Vector3(sx * 1.2, 0, -0.85)], Vector3(sx, 0, 0), RUG_BLUE)
		# fringe: short tassels along the short ends
		for k in 9:
			var z := -0.8 + 1.6 * k / 8.0
			_quad(st, [Vector3(sx * 1.2, 0.004, z - 0.04), Vector3(sx * 1.2, 0.004, z + 0.04), Vector3(sx * 1.3, 0.003, z + 0.03), Vector3(sx * 1.3, 0.003, z - 0.03)], Vector3.UP, RUG_CREAM)
	_mesh(root, "Rug", st)


## The rug's field: red, with a diamond medallion (blue, a gold centre) cut into it.
func _rug_field(st: SurfaceTool, fx: float, fz: float, y: float, c: Color) -> void:
	var dx := 0.55
	var dz := 0.42
	var dia := [Vector3(-dx, y, 0), Vector3(0, y, -dz), Vector3(dx, y, 0), Vector3(0, y, dz)]
	var corners := [Vector3(-fx, y, -fz), Vector3(fx, y, -fz), Vector3(fx, y, fz), Vector3(-fx, y, fz)]
	# the field around the diamond: four quads from each field corner to the diamond's edge
	_quad(st, [corners[0], Vector3(0, y, -fz), dia[1], dia[0]], Vector3.UP, c)
	_quad(st, [Vector3(0, y, -fz), corners[1], dia[2], dia[1]], Vector3.UP, c)
	_quad(st, [corners[2], Vector3(0, y, fz), dia[3], dia[2]], Vector3.UP, c)
	_quad(st, [Vector3(0, y, fz), corners[3], dia[0], dia[3]], Vector3.UP, c)
	_face(st, [corners[0], dia[0], corners[3]], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], c)
	_face(st, [corners[1], corners[2], dia[2]], [Vector3.UP, Vector3.UP, Vector3.UP], Vector3.UP, [], c)
	# medallion: the blue diamond with a smaller gold one inside
	var s := 0.45
	var inner := []
	for d in dia:
		inner.append(Vector3((d as Vector3).x * s, y, (d as Vector3).z * s))
	for i in 4:
		var j := (i + 1) % 4
		_quad(st, [dia[i], dia[j], inner[j], inner[i]], Vector3.UP, RUG_BLUE)
	_quad(st, inner, Vector3.UP, RUG_GOLD)
