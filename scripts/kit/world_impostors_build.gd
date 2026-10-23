extends SceneTree
## `iamar-world impostors <folder> [--px 128]`: renders the impostor pictures for
## every model a scene object asks a card for ("impostor": <metres>), see
## WorldImpostors and docs/WORLD_TIERS.md. Renders, so it needs a display (on a
## server: `offscreen iamar-world impostors <folder>`). It draws the top hardware
## tier's model (tiers/<top>/<path> when there is one) and writes the pictures at
## the package's own paths; run `iamar-world tiers` afterwards so each lower tier
## gets smaller copies.
##   godot --path <oakhaven> -s res://scripts/kit/world_impostors_build.gd -- <folder> [--px 128]

const SS := 2            ## supersampling while rendering
const CAPTURE := preload("res://shaders/world_impostor_capture.gdshader")

var _dir := ""
var _px := 128


func _initialize() -> void:
	var args := KitLoop.user_args()
	if args.is_empty():
		printerr("usage: impostors <folder> [--px 128]")
		quit(2)
		return
	_dir = KitLoop.absolute_path(args[0])
	var i := args.find("--px")
	if i >= 0 and i + 1 < args.size():
		_px = clampi(int(args[i + 1]), 16, 512)
	_run.call_deferred()


func _frames(n: int) -> void:
	for i in n:
		await process_frame
	await RenderingServer.frame_post_draw


## The albedo picture draws each surface as the browser does, unlit: its own colour,
## texture and alpha cut, and, like WorldPackage._glb_vertex_colours (an internal task), the
## vertex colours of any surface that has them (glTF COLOR_0 multiplies baseColor;
## GLTFDocument leaves that off, so the city's vertex-painted elm and oak cards came
## out white, G19), read as sRGB for a Godot-made file.
static func _albedo_material(srcm: BaseMaterial3D, vcol: bool, srgb: bool) -> StandardMaterial3D:
	var u := StandardMaterial3D.new()
	u.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	u.cull_mode = BaseMaterial3D.CULL_DISABLED
	u.disable_fog = true
	if srcm:
		u.albedo_texture = srcm.albedo_texture
		u.albedo_color = srcm.albedo_color
		u.texture_filter = srcm.texture_filter
		u.vertex_color_use_as_albedo = srcm.vertex_color_use_as_albedo
		u.vertex_color_is_srgb = srcm.vertex_color_is_srgb
		if srcm.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
			u.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
			u.alpha_scissor_threshold = srcm.alpha_scissor_threshold
	if vcol:
		u.vertex_color_use_as_albedo = true
		u.vertex_color_is_srgb = srgb
	return u


## Whether a glTF's COLOR_0 holds sRGB values, WorldPackage._glb_vcol_srgb's rule:
## asset.extras.iamar_vertex_colour ("srgb" or "linear") wins; otherwise a Godot-made
## file is sRGB and any other is linear (the glTF spec).
static func vcol_srgb(json: Dictionary) -> bool:
	var asset: Dictionary = json.get("asset", {}) if json.get("asset") is Dictionary else {}
	var extras: Dictionary = asset.get("extras", {}) if asset.get("extras") is Dictionary else {}
	var said := String(extras.get("iamar_vertex_colour", "")).to_lower()
	if said == "srgb" or said == "linear":
		return said == "srgb"
	return String(asset.get("generator", "")).begins_with("Godot Engine")


func _read_json(rel: String) -> Variant:
	var f := FileAccess.open(_dir.path_join(rel), FileAccess.READ)
	return JSON.parse_string(f.get_as_text()) if f else null


func _run() -> void:
	var m = _read_json("manifest.json")
	var s = _read_json(String(m.get("scene", "scene.json")) if m is Dictionary else "scene.json")
	if not m is Dictionary or not s is Dictionary:
		printerr("ERROR %s: no readable manifest.json / scene" % _dir)
		quit(2)
		return
	var wanted := WorldImpostors.assets_wanting(s)
	if wanted.is_empty():
		print("IMPOSTORS none: give far objects \"impostor\": <metres> in scene.json (docs/WORLD_TIERS.md)")
		quit(0)
		return
	var tiers := WorldTiers.declared(m)
	var top: String = tiers[tiers.size() - 1]
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var vp := SubViewport.new()
	vp.size = Vector2i(_px * SS, _px * SS)
	vp.transparent_bg = true
	vp.own_world_3d = true
	vp.mesh_lod_threshold = 0.0
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	vp.add_child(cam)
	var failed := false
	var reused := {}   ## package paths carried by hash (manifest.reused): not in this folder (an internal task)
	for r in m.get("reused", []):
		if r is Dictionary and r.has("path"):
			reused[String(r.path)] = true
	for asset in wanted:
		if reused.has(asset):
			print("INFO %s: reused by hash (not in this folder), no impostor made; model your own copy to get one" % asset)
			continue
		var src := _dir.path_join(WorldTiers.variant_path(asset, top))
		if not FileAccess.file_exists(src):
			src = _dir.path_join(asset)
		var doc := GLTFDocument.new()
		var st := GLTFState.new()
		if doc.append_from_file(src, st) != OK:
			printerr("ERROR %s: not a readable glTF binary" % asset)
			failed = true
			continue
		var model := doc.generate_scene(st)
		# its extent about its own up axis, through the centre of its footprint
		var lo := Vector3(INF, INF, INF)
		var hi := -lo
		var meshes := model.find_children("*", "MeshInstance3D", true, false)
		for mi in meshes:
			var xf := _to_model(mi as Node3D, model)
			var mesh := (mi as MeshInstance3D).mesh
			for k in mesh.get_surface_count():
				for v in (mesh.surface_get_arrays(k)[Mesh.ARRAY_VERTEX] as PackedVector3Array):
					var w := xf * v
					lo = lo.min(w)
					hi = hi.max(w)
		if meshes.is_empty() or lo.x == INF:
			printerr("WARN %s: no meshes, no impostor" % asset)
			model.free()
			continue
		var cx := (lo.x + hi.x) * 0.5
		var cz := (lo.z + hi.z) * 0.5
		var r := Vector2(hi.x - cx, hi.z - cz).length()
		var size := maxf(hi.y - lo.y, 2.0 * r) * 1.03
		var foot := (lo.y + hi.y) * 0.5 - size * 0.5
		# per surface [mesh instance, surface, albedo material (mode 0), normal material (mode 1)]
		var mats := []
		var srgb := vcol_srgb(st.json)
		for mi in meshes:
			var mesh := (mi as MeshInstance3D).mesh
			for k in mesh.get_surface_count():
				var srcm := mesh.surface_get_material(k) as BaseMaterial3D
				var vcol: bool = mesh.surface_get_format(k) & Mesh.ARRAY_FORMAT_COLOR != 0
				var c := ShaderMaterial.new()
				c.shader = CAPTURE
				c.set_shader_parameter("mode", 1)
				c.set_shader_parameter("use_vcol", vcol or (srcm != null and srcm.vertex_color_use_as_albedo))
				if srcm:
					c.set_shader_parameter("tex", srcm.albedo_texture)
					c.set_shader_parameter("albedo", srcm.albedo_color)
					c.set_shader_parameter("scissor", srcm.alpha_scissor_threshold if srcm.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR else 0.0)
				mats.append([mi, k, _albedo_material(srcm, vcol, srgb), c])
		vp.add_child(model)
		var mid := Vector3(cx, foot + size * 0.5, cz)
		cam.size = size
		cam.near = 0.05
		cam.far = size * 4.0 + 10.0
		var atlas := [Image.create(WorldImpostors.VIEWS * _px, _px, false, Image.FORMAT_RGBA8),
			Image.create(WorldImpostors.VIEWS * _px, _px, false, Image.FORMAT_RGBA8)]
		for mode in 2:
			for e in mats:
				(e[0] as MeshInstance3D).set_surface_override_material(e[1], e[2 + mode])
			for k in WorldImpostors.VIEWS:
				var a := k * TAU / WorldImpostors.VIEWS
				cam.look_at_from_position(mid + Vector3(sin(a), 0.0, cos(a)) * (size * 2.0 + 2.0), mid)
				await _frames(4)
				var img := vp.get_texture().get_image()
				img.convert(Image.FORMAT_RGBA8)
				img.resize(_px, _px, Image.INTERPOLATE_LANCZOS)
				(atlas[mode] as Image).blit_rect(img, Rect2i(0, 0, _px, _px), Vector2i(k * _px, 0))
		model.free()
		var cover := 0
		var al: Image = atlas[0]
		for y in range(0, al.get_height(), 4):
			for x in range(0, al.get_width(), 4):
				if al.get_pixel(x, y).a > 0.5:
					cover += 1
		for mode in 2:
			(atlas[mode] as Image).fix_alpha_edges()
		DirAccess.make_dir_recursive_absolute(_dir.path_join(WorldImpostors.albedo_path(asset)).get_base_dir())
		(atlas[0] as Image).save_png(_dir.path_join(WorldImpostors.albedo_path(asset)))
		(atlas[1] as Image).save_png(_dir.path_join(WorldImpostors.normal_path(asset)))
		var meta := {"views": WorldImpostors.VIEWS, "size": snappedf(size, 0.001), "foot": snappedf(foot, 0.001),
			"center": [snappedf(cx, 0.001), snappedf(cz, 0.001)]}
		FileAccess.open(_dir.path_join(WorldImpostors.meta_path(asset)), FileAccess.WRITE).store_string(JSON.stringify(meta))
		print("IMPOSTOR %s size=%.2f foot=%.2f views=%d px=%d coverage=%d" % [asset, size, foot, WorldImpostors.VIEWS, _px, cover])
		if cover == 0:
			printerr("WARN %s: the pictures came out empty (is there a display?)" % asset)
			failed = true
	quit(1 if failed else 0)


## A node's transform relative to the model's root.
static func _to_model(n: Node3D, model: Node) -> Transform3D:
	var xf := Transform3D.IDENTITY
	var p: Node = n
	while p != null and p != model:
		if p is Node3D:
			xf = (p as Node3D).transform * xf
		p = p.get_parent()
	return xf
