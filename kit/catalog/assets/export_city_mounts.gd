extends "res://tools/masterplan_export_creatures.gd"
## Export the iamar city's griffin (LOD0-2), the three stabled dragon breeds and the giant
## eagle for the catalogue (kit/catalog/assets/creatures/mounts/), with their record in
## kit/catalog/sources/mounts_export.json (import_city_models.py --mounts measures them).
##
## Why not the iamar-models copies: those embed the same 1024 px albedo and normal map in
## every file (2.6-3 MB each), and the breeds and the eagle wear a Hunyuan3D-generated head
## whose licence is unconfirmed (kit/inventory/licences.json generated-head-glb). Here
## MpGenHead is switched off before anything is built, so every creature keeps the city's own
## code-built skull (MpGriffinKit, MpBirdKit, MpDragonKit's DragonBuilder: what the city draws
## when the head asset is missing), and the textures are sized per LOD and stored as lossy
## WebP inside each .glb (package worlds accept only embedded images: MediaGuard.check_glb):
##   griffin  lod0: albedo 1024 + normal 512 / lod1: 512 + 256 / lod2: 256, no normal map
##   breeds, eagle  LOD0 only, albedo 512 (their bodies carry no baked normal map)
## Run from an the iamar browser source (not public) checkout (headless; imported once with --import):
##   godot --headless --path <iamar checkout> -s <iamar-kit>/kit/catalog/assets/export_city_mounts.gd
## then  python3 kit/catalog/assets/import_city_models.py --mounts   (measure: city_mounts.json)
##       python3 kit/catalog/catalog.py build

## [albedo edge, normal edge (0 = drop the normal map)] per griffin LOD
const GRIFFIN_TEX := [[1024, 512], [512, 256], [256, 0]]
const BODY_TEX := 512
const WEBP_QUALITY := 0.82

var _kit_dir := ""
var _rows := []
var _tex := [BODY_TEX, 0]
var _scissor := false


func _initialize() -> void:
	_kit_dir = (get_script() as Script).resource_path.get_base_dir().get_base_dir().get_base_dir()
	if OS.get_environment("IAMAR_KIT_ROOT") != "":
		_kit_dir = OS.get_environment("IAMAR_KIT_ROOT").path_join("kit")
	_repo = _kit_dir.path_join("catalog/assets")
	var out := []
	OS.execute("git", ["-C", ProjectSettings.globalize_path("res://"), "rev-parse", "--short=8", "HEAD"], out)
	_commit = str(out[0]).strip_edges() if not out.is_empty() else "unknown"
	MpGenHead.enabled = false   # the code-built heads (see above); set before any mesh is built
	DirAccess.make_dir_recursive_absolute(_repo.path_join("creatures/mounts"))
	var gm := MpGriffinKit.meshes()
	_scissor = true
	for l in gm.size():
		_tex = GRIFFIN_TEX[mini(l, GRIFFIN_TEX.size() - 1)]
		_mount(_rigged("Griffin", MpGriffinKit.make_skeleton(), gm[l], MpGriffinKit.skin()),
			"griffin" if l == 0 else "griffin lod%d" % l, l, "MpGriffinKit (LOD%d, code-built head)" % l)
	_scissor = false
	_tex = [BODY_TEX, 0]
	for b in MpDragonKit.BREEDS.size():
		var nm: String = MpDragonKit.BREEDS[b].name
		var sk := DragonKit.make_skeleton()
		MpDragonKit.extend_skeleton(sk)
		_mount(_rigged("StableDragon_" + nm.to_pascal_case(), sk, MpDragonKit.meshes_for(b)[0], MpDragonKit.skin()),
			nm.replace("_", " "), 0, "MpDragonKit breed %s (LOD0, code-built skull)" % nm)
	_mount(_rigged("GiantEagle", MpBirdKit.make_skeleton(), MpBirdKit.meshes()[0], MpBirdKit.skin()),
		"giant eagle", 0, "MpBirdKit (LOD0, code-built head)")
	var f := FileAccess.open(_kit_dir.path_join("catalog/sources/mounts_export.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({
		"format": "iamar-catalog-mounts-export", "version": 1,
		"note": "The city's griffin, dragon breeds and giant eagle exported with code-built heads and "
			+ "per-LOD WebP textures by kit/catalog/assets/export_city_mounts.gd (run against the iamar browser source (not public)). "
			+ "Never edit by hand: rerun the export, then import_city_models.py --mounts.",
		"iamar_commit": _commit, "mounts": _rows}, " ", false) + "\n")
	f.close()
	print("EXPORTED %d mounts from the iamar browser source (not public) %s (%d failed)" % [_rows.size(), _commit, _fails])
	quit(1 if _fails else 0)


func _process(_d: float) -> bool:
	return false


func _mount(node: Node3D, name: String, lod: int, builder: String) -> void:
	var rel := "creatures/mounts/%s.glb" % name.replace(" ", "_")
	_strip(node)
	_own(node, node)
	var tris := _tris(node)
	var doc := GLTFDocument.new()
	doc.image_format = "Lossy WebP"
	doc.lossy_quality = WEBP_QUALITY
	var st := GLTFState.new()
	var err := doc.append_from_scene(node, st)
	if err == OK and tris > 0:
		err = doc.write_to_filesystem(st, _repo.path_join(rel))
	node.free()
	if err != OK or tris == 0:
		push_error("export_city_mounts: %s failed (%s, %d tris)" % [rel, error_string(err), tris])
		_fails += 1
		return
	_rows.append({"file": rel, "name": name, "lod": lod, "builder": builder, "builder_commit": _commit,
		"triangles": tris, "albedo_px": _tex[0], "normal_px": _tex[1]})
	print("EXPORT %s triangles=%d" % [rel, tris])


func _strip(n: Node) -> void:
	super(n)
	if _scissor and n is MeshInstance3D and (n as MeshInstance3D).mesh is ArrayMesh:
		(n as MeshInstance3D).mesh = _opaque_colours((n as MeshInstance3D).mesh)


## The griffin's COLOR alpha is the city shader's pattern code (0.0 on most vertices), but the
## portable material uses vertex colour as albedo with an alpha scissor, so that code would cut
## most of the body away (an internal task). The feather cut-outs live in the albedo texture's alpha;
## the vertex alpha is set to 1 so only the texture decides.
func _opaque_colours(src: ArrayMesh) -> ArrayMesh:
	var out := ArrayMesh.new()
	out.blend_shape_mode = src.blend_shape_mode
	for s in src.get_surface_count():
		var arr := src.surface_get_arrays(s)
		var cols: Variant = arr[Mesh.ARRAY_COLOR]
		if cols is PackedColorArray:
			var c := cols as PackedColorArray
			for i in c.size():
				c[i].a = 1.0
			arr[Mesh.ARRAY_COLOR] = c
		out.add_surface_from_arrays(src.surface_get_primitive_type(s), arr,
			src.surface_get_blend_shape_arrays(s), {}, src.surface_get_format(s) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS)
		out.surface_set_material(s, src.surface_get_material(s))
	return out


func _portable(m: Material) -> Material:
	var sm := StandardMaterial3D.new()
	sm.vertex_color_use_as_albedo = true
	sm.roughness = 0.86 if _scissor else 0.85
	if _scissor:   # the griffin's feather cards keep their cut-outs
		sm.cull_mode = BaseMaterial3D.CULL_DISABLED
		sm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		sm.alpha_scissor_threshold = 0.5
	var sh := m as ShaderMaterial
	if m is BaseMaterial3D:
		var bm := m as BaseMaterial3D
		if bm.albedo_texture:
			sm.albedo_texture = _sized(bm.albedo_texture, _tex[0])
		sm.albedo_color = bm.albedo_color
	elif sh:
		for p: String in ["albedo_tex", "albedo_texture", "texture_albedo", "tex"]:
			var t: Variant = sh.get_shader_parameter(p)
			if t is Texture2D:
				sm.albedo_texture = _sized(t, _tex[0])
				break
		var n: Variant = sh.get_shader_parameter("normal_tex")
		# the griffin's normal_tex is its baked atlas normal map; the dragons' is a scale
		# detail atlas the portable material cannot tile, so it stays behind
		if _scissor and n is Texture2D and int(_tex[1]) > 0:
			sm.normal_enabled = true
			sm.normal_texture = _sized(n, _tex[1])
	return sm


func _sized(t: Texture2D, edge: int) -> Texture2D:
	var img := t.get_image()
	if img == null:
		return t
	img = img.duplicate()
	if img.is_compressed():
		img.decompress()
	if img.has_mipmaps():
		img.clear_mipmaps()
	if maxi(img.get_width(), img.get_height()) > edge:
		var s := float(edge) / maxi(img.get_width(), img.get_height())
		img.resize(maxi(1, int(img.get_width() * s)), maxi(1, int(img.get_height() * s)), Image.INTERPOLATE_LANCZOS)
	return ImageTexture.create_from_image(img)
