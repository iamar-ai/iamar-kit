extends SceneTree
## kit/catalog/assets/painted_baker.gd (an internal task): the city's painted look baked into a
## texture keeps the mesh and draws the pattern, not a flat colour.
##   - a MeshKit box in oak (timber, pattern 2) and an iron strap (pattern 8): triangles,
##     corners and winding unchanged; COLOR_0 and UV2 gone, one UV set into the atlas;
##   - the iron gets its own surface with the city's roughness and metallic;
##   - the timber texels vary (grain), their mean is the city shader's colour: vertex colour
##     decoded from sRGB, times the library, over 0.68 (within 25 %);
##   - a glowing face gets an emission texture; a surface without UV2 passes untouched;
##   - every baked catalogue file (props, furniture) has a texture and no COLOR_0.
## Run from an the iamar browser source (not public) checkout (it reads assets/masterplan/textures/mp_library.png):
##   godot --headless --path <iamar checkout> -s <iamar-kit>/kit/tests/catalog/painted_bake_test.gd

var _checks := 0
var _failures := 0


func _check(what: String, cond: bool, detail := "") -> void:
	_checks += 1
	if cond:
		print("PASS ", what)
	else:
		_failures += 1
		print("FAIL ", what, " ", detail)


func _initialize() -> void:
	var kit_dir := (get_script() as Script).resource_path.get_base_dir().get_base_dir().get_base_dir()
	if OS.get_environment("IAMAR_KIT_ROOT") != "":
		kit_dir = OS.get_environment("IAMAR_KIT_ROOT").path_join("kit")
	var baker = load(kit_dir.path_join("catalog/assets/painted_baker.gd")).new()
	_check("library loads", baker.load_library(ProjectSettings.globalize_path("res://assets/masterplan/textures/mp_library.png")))

	var kit := MeshKit.new()
	kit.box(Vector3(0, 0.4, 0), Vector3(1.2, 0.8, 0.5), "#8a5a32/2")      # oak
	kit.box(Vector3(0, 0.82, 0), Vector3(1.22, 0.04, 0.52), "#4d5157/8")  # iron strap
	kit.box(Vector3(0, 1.0, 0), Vector3(0.2, 0.2, 0.2), "lamp_glow")        # glowing (Mats look: glow 5)
	var src := kit.commit()
	var src_tris := []
	for s in src.get_surface_count():
		var arr := src.surface_get_arrays(s)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var ix = arr[Mesh.ARRAY_INDEX]
		var n: int = (ix as PackedInt32Array).size() if ix != null else v.size()
		for k in range(0, n, 3):
			src_tris.append(_tri_key(v, ix, k))
	var r: Dictionary = baker.bake_mesh(src)
	_check("bake succeeds", r.ok, str(r.get("error", "")))
	if not r.ok:
		_finish()
		return
	var out: ArrayMesh = r.mesh
	var out_tris := []
	var has_metal := false
	var tex: Texture2D = null
	var emissive := false
	for s in out.get_surface_count():
		var arr := out.surface_get_arrays(s)
		_check("surface %d has no COLOR_0 and no UV2" % s, arr[Mesh.ARRAY_COLOR] == null and arr[Mesh.ARRAY_TEX_UV2] == null)
		var uv: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV]
		var inside := true
		for q in uv:
			inside = inside and q.x >= 0.0 and q.x <= 1.0 and q.y >= 0.0 and q.y <= 1.0
		_check("surface %d UVs inside the atlas" % s, inside)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var ix = arr[Mesh.ARRAY_INDEX]
		for k in range(0, (ix as PackedInt32Array).size(), 3):
			out_tris.append(_tri_key(v, ix, k))
		var m := out.surface_get_material(s) as StandardMaterial3D
		tex = m.albedo_texture
		if m.metallic > 0.3 and absf(m.roughness - 0.38) < 0.01:
			has_metal = true
		if m.emission_enabled and m.emission_texture != null:
			emissive = true
	src_tris.sort()
	out_tris.sort()
	_check("same triangles, corners and winding", src_tris == out_tris, "%d vs %d" % [src_tris.size(), out_tris.size()])
	_check("iron on its own metallic surface", has_metal)
	_check("glow baked into an emission texture", emissive and r.glow)
	_check("patterns recorded", r.patterns.has(2) and r.patterns.has(8) and r.patterns.has(0))

	# the timber's texels: not flat, and the city's colour on average
	var img := tex.get_image()
	if img.is_compressed():
		img.decompress()
	var lib_mean := _layer_mean(baker, 4)
	var ca := Color("#8a5a32").srgb_to_linear()
	var want := Vector3(ca.r, ca.g, ca.b) / 0.68 * lib_mean
	var stats := _timber_stats(out, img)
	_check("timber texels vary (grain, not a flat colour)", stats.sd > 0.01, "sd %.4f" % stats.sd)
	var mean: Vector3 = stats.mean
	var ok := true
	for c in 3:
		ok = ok and absf(mean[c] - want[c]) <= 0.25 * want[c] + 0.01
	_check("timber mean is the city shader's colour (+-25 %)", ok, "got %s want %s" % [mean, want])

	# an effect surface (no UV2: a fountain's water) passes untouched
	var arr2 := src.surface_get_arrays(0)
	arr2[Mesh.ARRAY_TEX_UV2] = null
	var fx := ArrayMesh.new()
	fx.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr2)
	_check("surface without UV2 is not baked", not (baker.bake_mesh(fx) as Dictionary).ok)

	# the shipped files
	var src_json = JSON.parse_string(FileAccess.get_file_as_string(kit_dir.path_join("catalog/sources/city_models.json")))
	var pieces = JSON.parse_string(FileAccess.get_file_as_string(kit_dir.path_join("catalog/sources/city_pieces.json")))
	var rows: Array = (src_json.models as Array) + (pieces.models as Array)
	var n_baked := 0
	for row: Dictionary in rows:
		var folder := String(row.file).split("/")[0]
		if folder != "props" and folder != "furniture":
			continue
		var j = _glb_json(kit_dir.path_join("catalog/assets").path_join(row.file))
		var textured := j is Dictionary and (j.get("images", []) as Array).size() > 0
		var no_vcol := true
		if j is Dictionary:
			for m: Dictionary in j.meshes:
				for p: Dictionary in m.primitives:
					if (p.attributes as Dictionary).has("COLOR_0") and (p.attributes as Dictionary).has("TEXCOORD_1"):
						no_vcol = false
		_check("%s textured, no painted vertex colour left" % row.file, textured and no_vcol and row.has("painted_bake"))
		n_baked += 1
	_check("56 props and furniture checked", n_baked == 56, str(n_baked))
	_finish()


func _finish() -> void:
	print("%d checks, %d failures" % [_checks, _failures])
	quit(1 if _failures else 0)


func _tri_key(v: PackedVector3Array, ix, k: int) -> String:
	var c := []
	for o in 3:
		var i: int = ix[k + o] if ix != null else k + o
		c.append("%.4f,%.4f,%.4f" % [v[i].x, v[i].y, v[i].z])
	# rotate so the smallest corner leads (same winding, any start)
	var best := 0
	for o in 3:
		if c[o] < c[best]:
			best = o
	return "%s|%s|%s" % [c[best], c[(best + 1) % 3], c[(best + 2) % 3]]


func _layer_mean(baker, layer: int) -> Vector3:
	var l: Array = baker._layer(layer)
	var f: PackedFloat32Array = l[0]
	var s := Vector3()
	for i in range(0, f.size(), 3):
		s += Vector3(f[i], f[i + 1], f[i + 2])
	return s / (f.size() / 3)


## Mean and spread (linear) of the atlas texels under the timber faces (surface 0's
## triangle centroids-to-corners, sampled at many interior points).
func _timber_stats(mesh: ArrayMesh, img: Image) -> Dictionary:
	var arr := mesh.surface_get_arrays(0)   # class 0: painted (timber + glow box)
	var uv: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV]
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var ix: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
	var vals := []
	for k in range(0, ix.size(), 3):
		var cy := (v[ix[k]].y + v[ix[k + 1]].y + v[ix[k + 2]].y) / 3.0
		if cy > 0.85:
			continue   # the glowing box
		for a in 5:
			for b in 5:
				var wa := (a + 1) / 7.0
				var wb := (b + 1) / 7.0 * (1.0 - wa)
				var q := uv[ix[k]] * (1.0 - wa - wb) + uv[ix[k + 1]] * wa + uv[ix[k + 2]] * wb
				var c := img.get_pixel(clampi(int(q.x * img.get_width()), 0, img.get_width() - 1), clampi(int(q.y * img.get_height()), 0, img.get_height() - 1)).srgb_to_linear()
				vals.append(Vector3(c.r, c.g, c.b))
	var mean := Vector3()
	for x: Vector3 in vals:
		mean += x
	mean /= maxi(vals.size(), 1)
	var var_sum := 0.0
	for x: Vector3 in vals:
		var_sum += (x - mean).length_squared()
	return {"mean": mean, "sd": sqrt(var_sum / maxi(vals.size(), 1))}


func _glb_json(path: String) -> Variant:
	var b := FileAccess.get_file_as_bytes(path)
	if b.size() < 20:
		return null
	var n := b.decode_u32(12)
	return JSON.parse_string(b.slice(20, 20 + n).get_string_from_utf8())
