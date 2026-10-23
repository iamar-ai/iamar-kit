extends SceneTree
## `iamar-world tiers` counts a world the way the browser does (an internal task, harbour a5 gap
## G13): a map two materials share is one image, NPC attachments and quest look models
## are models it places, and primitives, terrain, water, creatures and the heightmap are
## in the totals; and a lower tier cuts its models to what its budget leaves after those
## fixed triangles, so it ends under the budget (an internal task). Run through
## tests/kit_tiers_count/run.sh.

var _ok := 0
var _bad := 0


func _check(what: String, cond: bool, detail := "") -> void:
	if cond:
		_ok += 1
		print("PASS ", what)
	else:
		_bad += 1
		print("FAIL ", what, " ", detail)


func _initialize() -> void:
	var dir := OS.get_environment("TIER_TMP").path_join("world")
	var tris := _make_world(dir)
	var out := []
	var code := OS.execute(OS.get_executable_path(), ["--headless", "--path", ProjectSettings.globalize_path("res://"),
		"-s", "res://scripts/kit/world_tiers_build.gd", "--", dir, "--dry"], out, true)
	var log: String = "".join(out)
	print(log)
	_check("tiers --dry succeeds", code == 0, "exit %d" % code)
	var line := ""
	for l in log.split("\n"):
		if l.begins_with("TIER medium"):
			line = l
	# placements: shared x2 (objects), hat (attach), npc, tool (NPC attach), coin x3 (quest look)
	var want_tris: int = tris.shared * 2 + tris.small * 6 \
		+ 12 + 2 * 8 * 8 + 2 + 1200 * 2   # a box, a 9x9 heightmap terrain, one water, two ducks
	# shared.glb: one 256 px map on two materials; the five small models a 64 px map each; the
	# 32 x 32 heightmap
	var want_tex := 256 * 256 * 4 + 4 * 64 * 64 * 4 + 32 * 32 * 4
	_check("triangles as the browser counts them", line.contains("triangles=%d/" % want_tris), "%s (want %d)" % [line, want_tris])
	_check("texture bytes as the browser counts them", line.contains("texture_bytes=%d/" % want_tex), "%s (want %d)" % [line, want_tex])
	_fixed_case(OS.get_environment("TIER_TMP").path_join("world_fixed"))
	_fixed_case(OS.get_environment("TIER_TMP").path_join("world_solid"), true)
	print("KIT TIERS COUNT TEST %d passed, %d failed" % [_ok, _bad])
	quit(0 if _bad == 0 else 1)


## A world whose terrain alone takes 40 % of the low budget: the low tier must cut its models
## to the rest, not to the whole budget (an internal task: 4 x 4224 = 16896 fit 20000, so they
## stayed whole and the tier reported 8192 + 16896 = 25088, OVER).
## With `solid`, two of the four balls have mesh collision, so they keep every triangle and
## the other two must take the whole cut (an internal task: budget 12000, the cut ignored the kept
## 8448 and the tier reported 12674, OVER).
func _fixed_case(dir: String, solid := false) -> void:
	DirAccess.make_dir_recursive_absolute(dir.path_join("assets"))
	var root := Node3D.new()
	var mi := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radial_segments = 64
	sphere.rings = 32
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, sphere.get_mesh_arrays())
	var ball_tris := am.surface_get_array_index_len(0) / 3
	mi.mesh = am
	root.add_child(mi)
	mi.owner = root
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	doc.append_from_scene(root, st)
	doc.write_to_filesystem(st, dir.path_join("assets/ball.glb"))
	root.free()
	var budget := 12000 if solid else 20000
	var res := 2 if solid else 65
	var fixed := 2 * (res - 1) * (res - 1)   # the terrain
	var m := {"format": "iamar-world", "format_version": 0, "id": "tierfixed", "name": "Tier fixed",
		"author": {"name": "test"}, "version": "0.1.0", "api_version": "0.1", "scene": "scene.json",
		"budgets": {"triangles": budget, "objects": 50, "texture_size": 1024, "texture_bytes": 64 << 20,
			"lights": 4, "package_bytes": 64000000, "audio_bytes": 1000000, "script_bytes": 0},
		"tiers": {"medium": {"budgets": {"triangles": 200000}}}}
	var objs := []
	for i in 4:
		objs.append({"id": "b%d" % i, "asset": "assets/ball.glb", "position": [3 * i, 1, 0]})
		if solid and i >= 2:
			objs[i].asset = "assets/wall.glb"
			objs[i].collision = "mesh"
	if solid:
		DirAccess.copy_absolute(dir.path_join("assets/ball.glb"), dir.path_join("assets/wall.glb"))
	var s := {"format": "iamar-scene", "format_version": 0,
		"terrain": {"type": "heightmap", "resolution": res, "size": [64, 64], "min_height": 0, "max_height": 0},
		"objects": objs}
	FileAccess.open(dir.path_join("manifest.json"), FileAccess.WRITE).store_string(JSON.stringify(m, "\t"))
	FileAccess.open(dir.path_join("scene.json"), FileAccess.WRITE).store_string(JSON.stringify(s, "\t"))
	var out := []
	var code := OS.execute(OS.get_executable_path(), ["--headless", "--path", ProjectSettings.globalize_path("res://"),
		"-s", "res://scripts/kit/world_tiers_build.gd", "--", dir, "--dry"], out, true)
	var log: String = "".join(out)
	print(log)
	var tris := {}
	var re := RegEx.create_from_string("^TIER (\\w+) +triangles=(\\d+)/")
	for l in log.split("\n"):
		var mt := re.search(l)
		if mt:
			tris[mt.get_string(1)] = int(mt.get_string(2))
	var low := int(tris.get("low", -1))
	var top := int(tris.get("medium", -1))
	var whole := fixed + 4 * ball_tris
	var label := "solid tris: " if solid else "fixed tris: "
	_check(label + "the top tier keeps every model triangle and the whole world is over the low budget",
		top == whole and whole > budget, "medium=%d want %d" % [top, whole])
	_check(label + "the low tier ends at or under its budget, terrain counted",
		low > fixed and low <= budget, "low=%d budget=%d" % [low, budget])
	_check(label + "tiers exits 0 (no tier OVER)", code == 0, "exit %d" % code)
	if solid:
		_check(label + "the collision balls keep every triangle on the low tier",
			low >= fixed + 2 * ball_tris, "low=%d want >= %d" % [low, fixed + 2 * ball_tris])


func _glb(path: String, surfaces: int, px: int) -> int:
	var root := Node3D.new()
	var mi := MeshInstance3D.new()
	var am := ArrayMesh.new()
	var img := Image.create(px, px, false, Image.FORMAT_RGB8)
	img.fill(Color(0.6, 0.3, 0.2))
	var tex := ImageTexture.create_from_image(img)
	var box := BoxMesh.new()
	for i in surfaces:
		am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, box.get_mesh_arrays())
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(1, 1 - 0.5 * i, 1)
		mat.albedo_texture = tex   # every material shares one map
		am.surface_set_material(i, mat)
	mi.mesh = am
	root.add_child(mi)
	mi.owner = root
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	doc.append_from_scene(root, st)
	doc.write_to_filesystem(st, path)
	root.free()
	return 12 * surfaces


func _make_world(dir: String) -> Dictionary:
	DirAccess.make_dir_recursive_absolute(dir.path_join("assets"))
	DirAccess.make_dir_recursive_absolute(dir.path_join("textures"))
	var shared := _glb(dir.path_join("assets/shared.glb"), 2, 256)
	var small := 0
	for n in ["hat", "npc", "tool", "coin"]:
		small = _glb(dir.path_join("assets/%s.glb" % n), 1, 64)
	var hm := Image.create(32, 32, false, Image.FORMAT_L8)
	hm.fill(Color(0.5, 0.5, 0.5))
	hm.save_png(dir.path_join("textures/height.png"))
	var m := {"format": "iamar-world", "format_version": 0, "id": "tiercount", "name": "Tier count",
		"author": {"name": "test"}, "version": "0.1.0", "api_version": "0.1", "scene": "scene.json",
		"budgets": {"triangles": 100000, "objects": 50, "texture_size": 1024, "texture_bytes": 64 << 20,
			"lights": 4, "package_bytes": 64000000, "audio_bytes": 1000000, "script_bytes": 0},
		"tiers": {"medium": {"budgets": {"triangles": 200000}}}}
	var s := {"format": "iamar-scene", "format_version": 0,
		"terrain": {"type": "heightmap", "heightmap": "textures/height.png", "resolution": 9, "size": [16, 16], "min_height": 0, "max_height": 2},
		"water": [{"id": "w", "position": [0, 0, 0], "size": [4, 4]}],
		"creatures": [{"kind": "duck", "count": 2, "position": [0, 0, 0]}],
		"objects": [{"id": "a", "asset": "assets/shared.glb", "position": [0, 1, 0], "attach": [{"asset": "assets/hat.glb", "bone": "head"}]},
			{"id": "b", "asset": "assets/shared.glb", "position": [3, 1, 0]}],
		"npcs": [{"id": "n", "model": "assets/npc.glb", "position": [0, 0, 3], "attach": [{"asset": "assets/tool.glb", "bone": "head"}]}],
		"quests": [{"id": "q", "title": "Coins", "giver": "n", "offer": "Find my coins.", "thanks": "Thank you.",
			"steps": [{"kind": "pickup", "item": "Coin", "look": "assets/coin.glb", "spots": [[1, 1], [2, 2], [3, 3]], "text": "Coins found"}]}],
		"primitives": [{"id": "p", "shape": "box", "size": [1, 1, 1], "position": [0, 0, 5]}]}
	FileAccess.open(dir.path_join("manifest.json"), FileAccess.WRITE).store_string(JSON.stringify(m, "\t"))
	FileAccess.open(dir.path_join("scene.json"), FileAccess.WRITE).store_string(JSON.stringify(s, "\t"))
	return {"shared": shared, "small": small}
