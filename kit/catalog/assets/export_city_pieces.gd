extends SceneTree
## Export single pieces of the iamar city's furniture, crops and meadow flora as glTF
## files for the catalogue (kit/catalog/assets/{furniture,crops,flora}/), with their
## record in kit/catalog/sources/city_pieces.json (city_models.json's row format).
##
## The city never builds these as single objects: interiors are one mesh per room
## (MpInteriors, MpInteriorKits, MpInnWing, MpGuildhallInterior), crops and flowers are
## MultiMeshes of thousands of copies (MpCropBeds, MpFlora). This script calls the same
## builder functions the city calls, read-only, once per piece, on an empty room at
## the origin, and writes what they build (the export record is sources/pieces_export.json):
##   furniture  the room kit's painted look baked into a texture atlas per piece by
##              painted_baker.gd (wood grain, cloth, stone, iron, trims, contact shade
##              and the hearth's glow, as the city's mp_painted shader draws them;
##              an internal task); faces the city never builds (against the wall or the floor)
##              stay unbuilt, so shelves, dresser and hearth stand against a wall,
##              front toward +Z
##   crops      MpCropBeds' vertex-coloured plant meshes, two-sided
##   flora      MpFlora's crossed cards with their cell of the painted flora atlas
##              (tinted, root shade baked in, normals bent up as the flora shader does),
##              alpha-scissored, two-sided; the pond stone in vertex colour
## Run from an the iamar browser source (not public) checkout (headless; imported once with --import):
##   godot --headless --path <iamar checkout> -s <iamar-kit>/kit/catalog/assets/export_city_pieces.gd
## then  python3 kit/catalog/assets/import_city_models.py --pieces   (measure: city_pieces.json)
##       python3 kit/catalog/catalog.py build

const FLORA_ATLAS := "res://assets/masterplan/flora/mp_flora_atlas.png"
const LIBRARY := "res://assets/masterplan/textures/mp_library.png"   ## the painted library (MpMaterials)
const CARD_PX := 256   ## card texture width (0.8 m flower card: 320 px per metre)

## name -> [folder, category, collision, builder, description, synonyms]
const FURNITURE := {
	"armchair": ["furniture", "furniture", "box", "MpInnWing._armchair",
		"A deep upholstered fireside armchair in muted wine cloth with rolled arms and oak feet, from the inn's snug. Seats one (the city's sit spot is at its front).",
		["easy chair", "fireside chair", "upholstered chair", "inn", "seat"]],
	"oak chair": ["furniture", "furniture", "box", "MpGuildhallInterior._chair",
		"A plain oak chair with four square legs and a low back, from the guild hall's tables.",
		["chair", "wooden chair", "dining chair", "seat", "guild hall"]],
	"high chair": ["furniture", "furniture", "box", "MpGuildhallInterior._chair (high)",
		"A guild master's high-backed oak chair with a red cushion and a gilded crest on the back.",
		["throne", "master's chair", "high-backed chair", "seat", "guild hall"]],
	"trestle table": ["furniture", "furniture", "box", "MpInteriorKits.trestle",
		"A 2 m plank trestle table on oak end trestles with a plank bench along each side, set with pewter mugs and green bottles; the tavern and hall table.",
		["table", "dining table", "long table", "tavern table", "feast table", "benches"]],
	"hall bench": ["furniture", "furniture", "box", "MpInteriorKits.bench",
		"A 2.2 m plank bench on two oak end blocks that goes beside a trestle table; seats three.",
		["bench", "seat", "form", "tavern bench", "pew"]],
	"cot bed": ["furniture", "furniture", "box", "MpInteriors._cot",
		"A simple wooden cot bed with a cream mattress and a pillow, for barracks, healers and back rooms.",
		["bed", "cot", "bunk", "sleeping place", "infirmary bed"]],
	"shop shelf": ["furniture", "furniture", "box", "MpInteriors._shelf (goods jars)",
		"A tall open timber shelf, four boards, the two at hand height stocked with jars and pots; stands against a wall (no back panel).",
		["shelf", "shelves", "shelving", "rack", "apothecary shelf", "pantry shelf"]],
	"bookshelf": ["furniture", "furniture", "box", "MpInteriors._shelf (goods books)",
		"A tall open timber shelf with runs of coloured book spines on the two lower boards; stands against a wall (no back panel).",
		["bookcase", "shelf", "library", "books", "study"]],
	"kitchen dresser": ["furniture", "furniture", "box", "MpInnWing._build_dresser",
		"An oak kitchen dresser: a cupboard with two panelled doors and an open plate rack above, set with pewter jugs, bowls and mugs; stands against a wall.",
		["dresser", "cupboard", "sideboard", "hutch", "kitchen", "crockery"]],
	"hearth": ["furniture", "building-part", "box", "MpInteriors._hearth",
		"A stone hearth with glowing coals and a flame and a stone hood above (2.6 m tall); stands against a wall, the chimney is the building's.",
		["fireplace", "fire", "hearth fire", "stove", "kitchen"]],
	"iron-bound chest": ["furniture", "furniture", "box", "MpInteriors._chests",
		"A wooden storage chest bound with black iron and a brass lock plate.",
		["chest", "trunk", "coffer", "strongbox", "storage"]],
}

## crop name -> [MpCropBeds mesh, description, synonyms]
const CROPS := {
	"cabbage": ["_dome(0.24, 0.22)", "A cabbage: a low dome of blue-green leaves in a seven-leaf skirt, about 0.5 m across.",
		["cabbage", "kale", "vegetable", "kitchen garden", "crop"]],
	"lettuce": ["_dome(0.17, 0.12)", "A lettuce: a small bright-green leafy dome.",
		["lettuce", "salad", "greens", "vegetable", "crop"]],
	"leek": ["_leek", "A leek: three crossed blades, white at the foot and dark green at the tips.",
		["leek", "allium", "vegetable", "crop"]],
	"carrot": ["_carrot", "A carrot: a feathery tuft of bright leaves over the orange shoulder of the root.",
		["carrot", "root vegetable", "vegetable", "crop"]],
	"onion": ["_onion", "An onion: a pale bulb with thin upright blue-green spikes.",
		["onion", "shallot", "allium", "vegetable", "crop"]],
	"squash": ["_squash", "A squash plant: a sprawling mound of big dark leaves with an orange fruit beside it.",
		["squash", "pumpkin", "gourd", "marrow", "vegetable", "crop"]],
	"runner beans": ["_beans", "Runner beans: a 1.5 m wigwam of three tied canes leafed up their length, with a few red flowers.",
		["beans", "bean poles", "cane wigwam", "climbing beans", "crop"]],
}

## flora name -> [MpFlora kind, atlas cell, category, description, synonyms]
const FLORA := {
	"daisies": ["flower", 2, "flower", "A clump of white daisies with yellow hearts on a painted card pair (two crossed quads, 4 triangles).",
		["daisy", "white flowers", "wildflowers", "meadow flowers"]],
	"buttercups": ["flower", 3, "flower", "A clump of yellow buttercups on a painted card pair (4 triangles).",
		["buttercup", "yellow flowers", "wildflowers", "meadow flowers"]],
	"pink campion": ["flower", 4, "flower", "A clump of pink meadow flowers on a painted card pair (4 triangles).",
		["pink flowers", "campion", "wildflowers", "meadow flowers"]],
	"grass tuft": ["tuft", 0, "ground-flora", "A tuft of meadow grass on a painted card pair (4 triangles); scatter it by the hundred.",
		["grass", "tuft", "meadow grass", "ground cover", "undergrowth"]],
	"tall grass": ["tuft", 1, "ground-flora", "A tuft of tall seeding grass on a painted card pair (4 triangles).",
		["long grass", "wild grass", "seed heads", "meadow grass", "ground cover"]],
	"reeds": ["reeds", 5, "ground-flora", "A clump of 1.9 m pond reeds and bulrushes on three crossed painted cards (6 triangles), for pond edges and moats.",
		["reeds", "bulrushes", "cattails", "rushes", "pond plants", "water plants"]],
	"lily pad": ["lily", 6, "ground-flora", "A flowering water-lily pad, one painted card that lies on the water (2 triangles).",
		["water lily", "lily pad", "pond plant", "lotus"]],
	"pond stone": ["stone", -1, "rock", "A chunky river stone (24 triangles), warm lit top to mossy foot, for pond edges and paths.",
		["stone", "rock", "pebble", "boulder", "river stone"]],
}

var _kit_dir := ""
var _commit := ""
var _rows := []
var _fails := 0
var _baker = null


func _initialize() -> void:
	_kit_dir = (get_script() as Script).resource_path.get_base_dir().get_base_dir().get_base_dir()
	if OS.get_environment("IAMAR_KIT_ROOT") != "":
		_kit_dir = OS.get_environment("IAMAR_KIT_ROOT").path_join("kit")
	_commit = _git_head()
	MeshKit.lods = false   # one LOD: the glTF carries LOD0 only
	_furniture()
	_crops()
	_flora()
	var f := FileAccess.open(_kit_dir.path_join("catalog/sources/pieces_export.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({
		"format": "iamar-catalog-pieces-export", "version": 1,
		"note": "Single pieces exported from the city's room, crop-bed and flora builders by "
			+ "kit/catalog/assets/export_city_pieces.gd (run against the iamar browser source (not public)). Never edit by hand: "
			+ "rerun the export, then import_city_models.py --pieces.",
		"iamar_commit": _commit, "pieces": _rows}, " ", false) + "\n")
	f.close()
	print("EXPORTED %d pieces from the iamar browser source (not public) %s (%d failed)" % [_rows.size(), _commit, _fails])
	quit(1 if _fails else 0)


# --- furniture ----------------------------------------------------------------------

func _room(goods := "curios", ceil_h := 3.2) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var big := PackedVector2Array([Vector2(-20, -20), Vector2(20, -20), Vector2(20, 20), Vector2(-20, 20)])
	return {"kit": MeshKit.new(), "inner": big, "grown": big, "y": 0.0, "ceil": ceil_h, "rects": [], "walks": [],
		"rng": rng, "goods": goods, "kind": "shop", "pal": "central", "lights": [], "cards": [], "shafts": [],
		"nodes": [], "labels": [], "cuts": [],
		"out": {"culled": 0, "pieces": 0, "seats": [], "lights": [], "cards": [], "shafts": [], "nodes": [], "labels": []}}


func _furniture() -> void:
	_baker = load(_kit_dir.path_join("catalog/assets/painted_baker.gd")).new()
	_baker.indoor = true   # the rooms' material (MpMaterials.live(.., indoor = true))
	if not _baker.load_library(ProjectSettings.globalize_path(LIBRARY)):
		_fails += 1
		return
	var t := Vector2(1, 0)    # the piece's length along +X
	var n := Vector2(0, 1)    # its front toward +Z (the wall behind it at -Z)
	for name: String in FURNITURE:
		var room := _room("books" if name == "bookshelf" else "jars", 2.6 if name == "hearth" else 3.2)
		match name:
			"armchair": MpInnWing._armchair(room, Vector2.ZERO, n)
			"oak chair": MpGuildhallInterior._chair(room, Vector2.ZERO, n, 0.0, false)
			"high chair": MpGuildhallInterior._chair(room, Vector2.ZERO, n, 0.0, true)
			"trestle table": MpInteriorKits.trestle(room, Vector2.ZERO, 2.0, t)
			"hall bench": MpInteriorKits.bench(room, Vector2.ZERO, t, 2.2, n)
			"cot bed": MpInteriors._cot(room, [-n * 0.25, t, n, 2.0])
			"shop shelf", "bookshelf": MpInteriors._shelf(room, [Vector2.ZERO, t, n, 1.6])
			"kitchen dresser": MpInnWing._build_dresser(room, -n * 0.29, t, n, 1.6)
			"hearth": MpInteriors._hearth(room, [-n * 0.2, t, n, 2.0])
			"iron-bound chest": MpInteriors._chests(room, [-n * (0.3 - MpInteriors.SHELF_D * 0.5), t, n, 0.7])
		var kit: MeshKit = room.kit
		if kit.is_empty():
			push_error("export_city_pieces: %s built nothing" % name)
			_fails += 1
			continue
		var baked: Dictionary = _baker.bake_mesh(kit.commit())
		if not baked.ok:
			push_error("export_city_pieces: %s: painted bake failed (%s)" % [name, baked.get("error", "")])
			_fails += 1
			continue
		var mesh: ArrayMesh = baked.mesh
		var spec: Array = FURNITURE[name]
		var seats := []
		for s: Dictionary in room.out.seats:
			var p: Vector3 = s.pos
			seats.append({"pos": [snappedf(p.x, 0.01), snappedf(p.y, 0.01), snappedf(p.z, 0.01)], "yaw": snappedf(float(s.yaw), 0.001), "kind": str(s.kind)})
		_write(spec[0], name, mesh, null, spec[1], spec[2], spec[3], spec[4], spec[5],
			{"culled_faces": int(room.out.culled), "seats": seats,
				"painted_bake": {"atlas": [baked.atlas.x, baked.atlas.y], "px_per_m": baked.px_per_m,
					"charts": baked.charts, "patterns": baked.patterns, "glow": baked.glow}})


func _vertex_material(two_sided: bool) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.roughness = 0.85
	if two_sided:
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m


# --- crops ----------------------------------------------------------------------------

func _crops() -> void:
	for name: String in CROPS:
		var mesh: ArrayMesh
		match name:
			"cabbage": mesh = MpCropBeds._dome(0.24, 0.22, Color(0.36, 0.52, 0.42), Color(0.62, 0.76, 0.58))
			"lettuce": mesh = MpCropBeds._dome(0.17, 0.12, Color(0.38, 0.6, 0.22), Color(0.66, 0.86, 0.36))
			"leek": mesh = MpCropBeds._leek()
			"carrot": mesh = MpCropBeds._carrot()
			"onion": mesh = MpCropBeds._onion()
			"squash": mesh = MpCropBeds._squash()
			"runner beans": mesh = MpCropBeds._beans()
		var spec: Array = CROPS[name]
		_write("crops", name, mesh, _vertex_material(true), "crop", "none", "MpCropBeds." + str(spec[0]), spec[1], spec[2], {})


# --- flora ----------------------------------------------------------------------------

func _flora() -> void:
	var atlas := Image.load_from_file(ProjectSettings.globalize_path(FLORA_ATLAS))
	if atlas == null or atlas.is_empty():
		push_error("export_city_pieces: cannot read %s" % FLORA_ATLAS)
		_fails += 1
		return
	atlas.convert(Image.FORMAT_RGBA8)
	for name: String in FLORA:
		var spec: Array = FLORA[name]
		var kind: String = spec[0]
		var shape: String = MpFlora.KINDS[kind][0]
		var size: Vector2 = MpFlora.KINDS[kind][1]
		var src := MpFlora._mesh(shape)
		var arr := src.surface_get_arrays(0)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var nr: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		for i in v.size():
			v[i] = v[i] * Vector3(size.x, size.y, size.x)
			if shape.begins_with("cross"):
				nr[i] = nr[i].lerp(Vector3.UP, 0.75).normalized()   # as mp_flora.gdshader mode 0
		arr[Mesh.ARRAY_VERTEX] = v
		arr[Mesh.ARRAY_NORMAL] = nr
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		var mat: StandardMaterial3D
		if shape == "stone":
			mat = _vertex_material(true)   # the city draws it two-sided (mp_flora.gdshader cull_disabled)
			mat.roughness = 0.9
		else:
			mat = StandardMaterial3D.new()
			mat.albedo_texture = ImageTexture.create_from_image(_card(atlas, int(spec[1]), kind, shape))
			mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
			mat.alpha_scissor_threshold = 0.5
			mat.cull_mode = BaseMaterial3D.CULL_DISABLED
			mat.roughness = 1.0
			mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		_write("flora", name, mesh, mat, spec[2], "none", "MpFlora %s (atlas cell %d)" % [kind, spec[1]] if spec[1] >= 0 else "MpFlora._stone",
			spec[3], spec[4], {})


## One cell of the 4 x 3 flora atlas, with what mp_flora.gdshader does to it at a
## neutral copy (hue drift 0.5, value 0.5): the kind's tint, and for upright cards the
## root shade (x0.78 at the foot up to x1 at 40 % height). Worked in linear colour.
func _card(atlas: Image, cell: int, kind: String, shape: String) -> Image:
	var cw := atlas.get_width() / 4
	var ch := atlas.get_height() / 3
	var img := atlas.get_region(Rect2i((cell % 4) * cw, (cell / 4) * ch, cw, ch))
	var tint: Vector3 = Vector3(0.98, 1.0, 0.93) * (MpFlora.TINT.get(kind, Vector3.ONE) as Vector3)
	var upright := shape.begins_with("cross")
	for y in ch:
		var shade := 1.0
		if upright:
			shade = lerpf(0.78, 1.0, smoothstep(0.0, 0.4, 1.0 - float(y) / float(ch - 1)))
		for x in cw:
			var c := img.get_pixel(x, y)
			var l := c.srgb_to_linear()
			l.r = minf(l.r * tint.x * shade, 1.0)
			l.g = minf(l.g * tint.y * shade, 1.0)
			l.b = minf(l.b * tint.z * shade, 1.0)
			var o := l.linear_to_srgb()
			o.a = c.a
			img.set_pixel(x, y, o)
	if cw > CARD_PX:
		img.resize(CARD_PX, int(round(float(ch) * CARD_PX / cw)), Image.INTERPOLATE_LANCZOS)
	return img


# --- writing --------------------------------------------------------------------------

func _write(folder: String, name: String, mesh: ArrayMesh, mat: Material, category: String, collision: String,
		builder: String, description: String, synonyms: Array, extra: Dictionary) -> void:
	if mat != null:   # (null: the mesh carries its own, e.g. the painted bake's)
		for s in mesh.get_surface_count():
			mesh.surface_set_material(s, mat)
	var root := Node3D.new()
	root.name = name.replace(" ", "_")
	var mi := MeshInstance3D.new()
	mi.name = root.name + "_mesh"
	mi.mesh = mesh
	root.add_child(mi)
	mi.owner = root
	var rel := folder.path_join(name.replace("'", "").replace(" ", "_") + ".glb")
	var path := _kit_dir.path_join("catalog/assets").path_join(rel)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var doc := GLTFDocument.new()
	if folder == "furniture":   # the painted bake's atlas: opaque, so JPEG (a tenth of the PNG)
		doc.image_format = "JPEG"
		doc.lossy_quality = 0.85
	var state := GLTFState.new()
	var err := doc.append_from_scene(root, state)
	if err == OK:
		err = doc.write_to_filesystem(state, path)
	root.free()
	if err != OK:
		push_error("export_city_pieces: %s failed (%s)" % [rel, error_string(err)])
		_fails += 1
		return
	var tris := 0
	for s in mesh.get_surface_count():
		tris += mesh.surface_get_array_index_len(s) / 3 if mesh.surface_get_array_index_len(s) > 0 else mesh.surface_get_array_len(s) / 3
	var row := {"file": rel, "name": name, "category": category, "description": description,
		"synonyms": synonyms, "collision": collision, "builder": builder, "builder_commit": _commit, "triangles": tris}
	row.merge(extra)
	_rows.append(row)
	print("EXPORT %s triangles=%d" % [rel, tris])


func _git_head() -> String:
	var out := []
	OS.execute("git", ["-C", ProjectSettings.globalize_path("res://"), "rev-parse", "--short=8", "HEAD"], out)
	return str(out[0]).strip_edges() if not out.is_empty() else "unknown"
