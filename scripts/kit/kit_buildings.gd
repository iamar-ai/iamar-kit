extends RefCounted
## Oakhaven's procedural buildings as reusable kit assets (kit/AGENT_KIT.md "Reuse
## first"): builds one with the town's own builder (scripts/world/buildings.gd,
## read only) and writes it as a binary glTF a world can ship and place.
##
##   iamar-world assets building <kind> <out.glb> [--width 8] [--depth 6] [--floors 2] [--style plaster|stone|brick]
##     kind: house, inn, chapel, blacksmith, alchemist, general_store, stable
##
## The building keeps what makes it a building in a world: open doorways you walk
## through, furnished, walkable interiors (place it with "collision": "mesh"),
## and Oakhaven's colours (one plain glTF material per look colour: browsers do not
## apply glTF vertex colours to runtime-loaded models). The furniture props (Kenney CC0 models) are included. Prints
## BUILDING <out> <bytes> bytes <triangles> triangles door <x,y,z> facing <x,y,z>.

const KINDS := ["house", "inn", "chapel", "blacksmith", "alchemist", "general_store", "stable"]
const STYLES := {
	"plaster": {"base": "plaster", "upper": "plaster", "timber": "timber"},
	"stone": {"base": "stone", "upper": "plaster_warm", "timber": "timber"},
	"brick": {"base": "stone_dark", "upper": "plaster", "timber": "wood"},
}


## "--width 8 --furnish" -> {"width": "8", "furnish": "true"}: an option followed by another
## option (or by nothing) is a flag.
static func opts(a: Array) -> Dictionary:
	var o := {}
	var i := 0
	while i < a.size():
		var k := String(a[i]).trim_prefix("--")
		if i + 1 >= a.size() or String(a[i + 1]).begins_with("--"):
			o[k] = "true"
			i += 1
		else:
			o[k] = String(a[i + 1])
			i += 2
	return o


## Builds `kind` and writes it to `out` (.glb). Returns 0 on success.
static func export(kind: String, out: String, o: Dictionary) -> int:
	var k := MeshKit.new()
	var info: Dictionary
	match kind:
		"house":
			var s: Dictionary = STYLES.get(String(o.get("style", "plaster")), STYLES.plaster).duplicate()
			info = Buildings.house(k, clampf(float(o.get("width", 8)), 5.0, 16.0), clampf(float(o.get("depth", 6)), 4.0, 12.0),
				clampi(int(o.get("floors", 2)), 1, 3), s)
		"inn": info = Buildings.inn(k)
		"chapel": info = Buildings.chapel(k)
		"blacksmith": info = Buildings.blacksmith(k)
		"alchemist": info = Buildings.alchemist(k)
		"general_store": info = Buildings.general_store(k)
		"stable": info = Buildings.stable(k)
	var mesh := by_colour(k.commit())
	var root := Node3D.new()
	root.name = kind.capitalize().replace(" ", "")
	var mi := MeshInstance3D.new()
	mi.name = "Building"
	mi.mesh = mesh
	root.add_child(mi)
	mi.owner = root
	for p in info.get("props", []):
		var ps := load(String(p[0])) as PackedScene
		if ps == null:
			continue
		var n := ps.instantiate() as Node3D
		if n == null:
			continue
		n.transform = p[1]
		root.add_child(n)
		_own(n, root)
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	if doc.append_from_scene(root, st) != OK:
		printerr("ERROR could not convert the building")
		root.free()
		return 1
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out).get_base_dir())
	var err := doc.write_to_filesystem(st, out)
	var tris := WorldPackage._triangles(root)
	root.free()
	if err != OK:
		printerr("ERROR could not write ", out)
		return 1
	var front: Vector3 = info.get("front", Vector3.BACK)
	print("BUILDING %s %d bytes %d triangles door-side %s size %s" % [out, FileAccess.get_file_as_bytes(out).size(), tris, front, info.get("size", Vector2.ZERO)])
	return 0


## The town's mesh carries each look's colour per vertex (alpha: its pattern). glTF
## readers may ignore vertex colours, so split it into one surface per colour,
## each with a plain material of that colour (a dozen or so per building).
static func by_colour(src: ArrayMesh) -> ArrayMesh:
	var out := ArrayMesh.new()
	var tools := {}
	var mats := {}
	for si in src.get_surface_count():
		var arr := src.surface_get_arrays(si)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var nrm: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		var col: PackedColorArray = arr[Mesh.ARRAY_COLOR]
		var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX] if arr[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
		var n := idx.size() if idx.size() > 0 else v.size()
		for t in range(0, n - 2, 3):
			var ia := idx[t] if idx.size() > 0 else t
			var c := col[ia] if col.size() > ia else Color.WHITE
			var key := Color(snappedf(c.r, 1.0 / 255.0), snappedf(c.g, 1.0 / 255.0), snappedf(c.b, 1.0 / 255.0)).to_html(false)
			if not tools.has(key):
				var st := SurfaceTool.new()
				st.begin(Mesh.PRIMITIVE_TRIANGLES)
				tools[key] = st
				var m := StandardMaterial3D.new()
				m.albedo_color = Color(c.r, c.g, c.b)
				m.roughness = 0.9
				mats[key] = m
			var st2: SurfaceTool = tools[key]
			for j in 3:
				var vi := idx[t + j] if idx.size() > 0 else t + j
				st2.set_normal(nrm[vi])
				st2.add_vertex(v[vi])
	for key in tools:
		(tools[key] as SurfaceTool).commit(out)
		out.surface_set_material(out.get_surface_count() - 1, mats[key])
	return out


static func _own(n: Node, owner: Node) -> void:
	n.owner = owner
	for c in n.get_children():
		_own(c, owner)
