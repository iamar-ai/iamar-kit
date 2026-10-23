extends SceneTree
## Thumbnails and turntables for every catalogue entry (kit/catalog/catalog.json):
##   kit/thumbnails/<file id>.png   128 px three-quarter view (the built-in models' thumbnails
##                                  from `iamar-world assets thumbnails` use the same camera and light)
##   kit/turntables/<file id>.png   8 views in one 768x96 strip, the object turned 45 degrees
##                                  per frame, front first
## <file id> is the entry id with ':' as '_' (creature:bunny -> creature_bunny). Every kind renders
## through the browser's own code: built-in models load from the iamar project, the city's and the
## kit's glTF files from kit/, creatures are a one-animal WorldCreatures herd, generator buildings
## come from Buildings + kit_buildings.gd as `iamar-world assets building` makes them.
## Run from an imported the iamar browser source (not public) checkout on a private display (software rendering is fine):
##   offscreen godot --path <iamar checkout> -s <iamar-kit>/kit/catalog/render_previews.gd \
##       [-- --force] [-- --only id,id] [-- --thumbs-only|--turntables-only]
## Skips files that exist unless --force. IAMAR_KIT_ROOT=<iamar-kit> when the script is copied.
## Then `python3 kit/catalog/catalog.py build` records the paths; `check` fails on a missing file.

const THUMB := 128
const FRAME := 96
const FRAMES := 8

var _kit := ""
var _vp: SubViewport
var _cam: Camera3D
var _made := 0
var _failed: Array = []


func _init() -> void:
	_kit = (get_script() as Script).resource_path.get_base_dir().get_base_dir()
	if OS.get_environment("IAMAR_KIT_ROOT") != "":
		_kit = OS.get_environment("IAMAR_KIT_ROOT").path_join("kit")
	_run.call_deferred()


static func file_id(id: String) -> String:
	return id.replace(":", "_").replace("/", "_")


func _setup() -> void:
	_vp = SubViewport.new()
	_vp.transparent_bg = true
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_vp.own_world_3d = true
	_vp.msaa_3d = Viewport.MSAA_4X
	root.add_child(_vp)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.75, 0.78, 0.85)
	env.environment.ambient_light_energy = 0.6
	_vp.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 35, 0)
	_vp.add_child(sun)
	_cam = Camera3D.new()
	_cam.fov = 35
	_vp.add_child(_cam)


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	var force := "--force" in args
	var only := {}
	var i := args.find("--only")
	if i >= 0 and i + 1 < args.size():
		for s in String(args[i + 1]).split(","):
			only[s.strip_edges()] = true
	var want_thumb := not "--turntables-only" in args
	var want_turn := not "--thumbs-only" in args
	var cat: Variant = JSON.parse_string(FileAccess.get_file_as_string(_kit.path_join("catalog/catalog.json")))
	if typeof(cat) != TYPE_DICTIONARY:
		printerr("ERROR cannot read ", _kit.path_join("catalog/catalog.json"))
		quit(2)
		return
	DirAccess.make_dir_recursive_absolute(_kit.path_join("thumbnails"))
	DirAccess.make_dir_recursive_absolute(_kit.path_join("turntables"))
	_setup()
	for e: Dictionary in cat.entries:
		var id := String(e.id)
		if not only.is_empty() and not only.has(id):
			continue
		if String(e.get("kind", "")) == "audio":
			continue   # a sound's previews are its waveform, drawn by assets/harbour.py record
		var thumb := _kit.path_join("thumbnails/%s.png" % file_id(id))
		var turn := _kit.path_join("turntables/%s.png" % file_id(id))
		var do_thumb := want_thumb and (force or not FileAccess.file_exists(thumb))
		var do_turn := want_turn and (force or not FileAccess.file_exists(turn))
		if not do_thumb and not do_turn:
			continue
		var n := _build(e)
		if n == null:
			_failed.append(id)
			print("FAIL ", id, " could not be built")
			continue
		_vp.add_child(n)
		await process_frame
		var box := _aabb(n)
		if OS.get_environment("RENDER_PREVIEWS_DEBUG") != "":
			print("AABB ", id, " ", box)
			for v in n.find_children("*", "VisualInstance3D", true, false):
				print("  ", v.get_path(), " ", (v as VisualInstance3D).global_transform * (v as VisualInstance3D).get_aabb())
		if box.size.length() < 0.001:
			_failed.append(id)
			print("FAIL ", id, " has no visible geometry")
			n.queue_free()
			await process_frame
			continue
		if do_thumb:
			_vp.size = Vector2i(THUMB, THUMB)
			var img := await _shot(box, 0.0)
			img.save_png(thumb)
		if do_turn:
			_vp.size = Vector2i(FRAME, FRAME)
			var strip := Image.create_empty(FRAME * FRAMES, FRAME, false, Image.FORMAT_RGBA8)
			for f in FRAMES:
				var img := await _shot(box, TAU * f / FRAMES)
				img.convert(Image.FORMAT_RGBA8)
				strip.blit_rect(img, Rect2i(0, 0, FRAME, FRAME), Vector2i(f * FRAME, 0))
			strip.save_png(turn)
		n.queue_free()
		await process_frame
		_made += 1
		print("RENDERED ", id)
	print("PREVIEWS %d rendered, %d failed%s" % [_made, _failed.size(), (": " + ", ".join(_failed)) if _failed else ""])
	quit(1 if _failed else 0)


## One frame: camera at the thumbnail's three-quarter angle, turned `yaw` about the object's centre.
func _shot(box: AABB, yaw: float) -> Image:
	var c := box.get_center()
	var r := maxf(box.size.length() * 0.5, 0.002)
	var d := r / sin(deg_to_rad(_cam.fov * 0.5)) * 1.05
	var dir := Vector3(0.75, 0.55, 1.0).normalized().rotated(Vector3.UP, yaw)
	_cam.look_at_from_position(c + dir * d, c)
	_cam.near = maxf(d - r * 2.0, 0.0005)
	_cam.far = d + r * 2.0
	await process_frame
	await process_frame
	await RenderingServer.frame_post_draw
	return _vp.get_texture().get_image()


func _build(e: Dictionary) -> Node3D:
	var src: Dictionary = e.get("source", {})
	match String(src.get("origin", "")):
		"builtin":
			# straight from the file, so the project needs no import for these
			return _gltf(ProjectSettings.globalize_path("res://" + String(src.file)))
		"creature":
			return _creature(String(e.id).trim_prefix("creature:"))
		"generator":
			return _generator(String(e.id).trim_prefix("generator:"))
	var f := String(src.get("file", ""))
	if f == "":
		return null
	return _gltf(_kit.get_base_dir().path_join(f))


func _gltf(path: String) -> Node3D:
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	if doc.append_from_file(path, st) != OK:
		return null
	var n := doc.generate_scene(st) as Node3D
	if n == null:
		return null
	# vertex-painted models draw their colours as in a package world (WorldPackage._glb_decode)
	WorldPackage._glb_vertex_colours(n, WorldPackage._glb_vcol_srgb(st.json))
	# hold animated models (wing flaps, dragons) in their rest pose
	for ap in n.find_children("*", "AnimationPlayer", true, false):
		(ap as AnimationPlayer).active = false
	return n


func _creature(kind: String) -> Node3D:
	var c := WorldCreatures.new()
	c.setup({"kind": kind, "position": [0, 0, 0], "count": 1, "wander_radius": 0.0, "seed": 1}, null, 1)
	c.set_process(false)   # keep the first pose, do not wander off between frames
	return c


func _generator(kind: String) -> Node3D:
	var kb: GDScript = load(_kit.get_base_dir().path_join("scripts/kit/kit_buildings.gd"))
	var k := MeshKit.new()
	var info: Dictionary
	match kind:
		"house": info = Buildings.house(k, 8.0, 6.0, 2, kb.STYLES.plaster.duplicate())
		"inn": info = Buildings.inn(k)
		"chapel": info = Buildings.chapel(k)
		"blacksmith": info = Buildings.blacksmith(k)
		"alchemist": info = Buildings.alchemist(k)
		"general_store": info = Buildings.general_store(k)
		"stable": info = Buildings.stable(k)
		_: return null
	var n := Node3D.new()
	var mi := MeshInstance3D.new()
	mi.mesh = kb.by_colour(k.commit())
	n.add_child(mi)
	for p in info.get("props", []):
		var pn := _gltf(ProjectSettings.globalize_path(String(p[0])))
		if pn != null:
			pn.transform = p[1]
			n.add_child(pn)
	return n


func _aabb(n: Node) -> AABB:
	var box := AABB()
	var first := true
	for v in n.find_children("*", "VisualInstance3D", true, false):
		var vi := v as VisualInstance3D
		if not vi.visible or vi is Light3D:
			continue
		var b := vi.global_transform * vi.get_aabb()
		if b.size.length() < 0.0001:
			continue
		box = b if first else box.merge(b)
		first = false
	return box
