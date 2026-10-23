extends SceneTree
## `iamar-world tiers <folder>`: makes a world's lower hardware tiers from its top one
## (docs/WORLD_TIERS.md), so the agent only ever builds one high-quality version.
##
## manifest.tiers says which tiers the world has (medium/high/ultra; low is always
## there). The top tier's files are the source: tiers/<top>/<path> once this has run,
## or the package's own <path> the first time (it is then kept as tiers/<top>/<path>).
## For every model and image the scene uses, each lower tier gets a copy made to fit
## that tier's budgets:
##   - models: triangles cut to the tier's share of the top tier's triangle budget
##     (mesh simplification with Godot's meshoptimizer, the same as its import LODs;
##     vertices, UVs, skin weights and animations are kept, only the triangles go),
##   - textures (embedded in models, and the scene's images): halved until they fit
##     the tier's texture_size; normal maps dropped where the tier says normal_maps: false.
## The low tier is written to <path> itself, so a world opened by a browser that knows
## nothing of tiers still works, and a low-end visitor needs nothing under tiers/.
## Prints one TIER line per tier with its triangles and texture memory against its
## budgets, and exits 1 when a tier is over them. Both are counted the way the browser
## counts them when it opens the package (WorldPackage._measure, the STATS lines of
## `iamar-world validate`): every placement of a model (objects, attachments, NPCs and
## their attachments, quest look models), primitives, terrain, water and creatures for
## triangles; every image embedded in a model once, plus the scene's images (heightmap
## included) at width x height x 4 bytes for texture memory.
##   godot --headless --path <oakhaven> -s res://scripts/kit/world_tiers_build.gd -- <folder> [--dry]

var _dir := ""
var _reused := {}   ## package paths carried by hash (manifest.reused): not in this folder, not tiered
## Surfaces this small keep every triangle: cutting them saves little and wrecks the
## shape (an oak went from 468 to 58 triangles in the first agent-built world).
const MIN_SIMPLIFY_TRIS := 600
var _dry := false
var _fail := false


func _initialize() -> void:
	var args := KitLoop.user_args()
	if args.is_empty():
		printerr("usage: tiers <folder> [--dry]")
		quit(2)
		return
	_dir = KitLoop.absolute_path(args[0])
	_dry = "--dry" in args
	quit(_run())


func _read_json(rel: String) -> Variant:
	var f := FileAccess.open(_dir.path_join(rel), FileAccess.READ)
	return JSON.parse_string(f.get_as_text()) if f else null


func _run() -> int:
	var m = _read_json("manifest.json")
	if not m is Dictionary:
		printerr("ERROR %s: no readable manifest.json" % _dir)
		return 2
	var errs := WorldTiers.validate(m)
	if not errs.is_empty():
		for e in errs:
			printerr("ERROR " + e)
		return 2
	var tiers := WorldTiers.declared(m)
	if tiers.size() == 1:
		print("TIERS only low: add manifest.tiers (see docs/WORLD_TIERS.md) to build richer tiers")
		return 0
	var s = _read_json(String(m.get("scene", "scene.json")))
	if not s is Dictionary:
		printerr("ERROR no readable scene")
		return 2
	var top: String = tiers[tiers.size() - 1]
	var top_b := WorldTiers.budgets(m, top)
	for r in m.get("reused", []):
		if r is Dictionary and r.has("path"):
			_reused[String(r.path)] = true
	var report := {}
	for t in tiers:
		report[t] = {"triangles": 0, "texture_bytes": 0, "texture_size": 0}
	# models, by how many times the scene places each
	var uses := {}
	# a model people collide with keeps its triangles on every tier (its collider is
	# made from them: a cut dock lost one of its two walk surfaces)
	var solid := {}
	for o in s.get("objects", []):
		uses[o.asset] = int(uses.get(o.asset, 0)) + 1
		if String(o.get("collision", "none")) in ["mesh", "convex"]:
			solid[o.asset] = true
		for a in o.get("attach", []):
			uses[a.asset] = int(uses.get(a.asset, 0)) + 1
	for n in s.get("npcs", []):
		if n.has("model"):
			uses[n.model] = int(uses.get(n.model, 0)) + 1
			for a in n.get("attach", []):
				uses[a.asset] = int(uses.get(a.asset, 0)) + 1
	var looks := quest_look_models(s.get("quests", []))
	for p in looks:
		uses[p] = int(uses.get(p, 0)) + int(looks[p])
	# the same on every tier: primitives, terrain, water, creatures (triangles) and the
	# heightmap (data, but an image the browser loads and counts)
	var fixed_tris := scene_fixed_triangles(s)
	var hm_bytes := 0
	var hm := String(s.get("terrain", {}).get("heightmap", ""))
	if hm != "" and FileAccess.file_exists(_dir.path_join(hm)):
		var img := Image.load_from_file(_dir.path_join(hm))
		if img != null:
			hm_bytes = img.get_width() * img.get_height() * 4
	for t in tiers:
		report[t].triangles = fixed_tris
		report[t].texture_bytes = hm_bytes
	# the top tier's real triangle count (every placement): a lower tier is cut only as
	# far as its own budget needs, so a world already under it keeps every triangle
	var srcs := {}
	var top_tris := 0
	var solid_tris := 0   # kept whole on every tier, so not what a cut can save
	for p in uses:
		var src := _source(p, top)
		if src == "":
			continue
		srcs[p] = src
		var r := _model(src, "", 1.0, 1 << 20, true)
		if r.is_empty():
			return 2
		top_tris += int(r.triangles) * int(uses[p])
		if solid.has(p):
			solid_tris += int(r.triangles) * int(uses[p])
	for p in srcs:
		var src: String = srcs[p]
		for t in tiers:
			var b := WorldTiers.budgets(m, t)
			var ratio := 1.0
			# the models get what the budget leaves after the fixed triangles and the
			# collision models, which are never cut (an internal task)
			if t != top and b.has("triangles") and top_tris > solid_tris and not solid.has(p):
				ratio = clampf(float(maxi(int(b.triangles) - fixed_tris - solid_tris, 0)) / float(top_tris - solid_tris), 0.02, 1.0)
			var r := _model(src, WorldTiers.variant_path(p, t), ratio, int(b.get("texture_size", 4096)), t == top,
				WorldTiers.switch(m, t, "normal_maps"))
			if r.is_empty():
				return 2
			report[t].triangles += int(r.triangles) * int(uses[p])
			report[t].texture_bytes += int(r.texture_bytes)
			report[t].texture_size = maxi(int(report[t].texture_size), int(r.texture_size))
	for p in _images(s):
		var src := _source(p, top)
		if src == "":
			continue
		for t in tiers:
			var b := WorldTiers.budgets(m, t)
			var r := _image(src, WorldTiers.variant_path(p, t), int(b.get("texture_size", 4096)), t == top)
			report[t].texture_bytes += int(r.texture_bytes)
			report[t].texture_size = maxi(int(report[t].texture_size), int(r.texture_size))
	if not _dry:
		var dropped := 0
		for p in srcs.keys() + Array(_images(s)):
			dropped += _dedupe(String(p), tiers)
		if dropped > 0:
			print("TIERS %d variant files dropped: they were the same as the tier below (that file serves both)" % dropped)
	for t in tiers:
		var b := WorldTiers.budgets(m, t)
		var over := PackedStringArray()
		for k in ["triangles", "texture_bytes", "texture_size"]:
			if b.has(k) and int(report[t][k]) > int(b[k]):
				over.append(k)
		print("TIER %-6s triangles=%d/%d texture_size=%d/%d texture_bytes=%d/%d %s" % [t,
			report[t].triangles, int(b.get("triangles", 0)), report[t].texture_size, int(b.get("texture_size", 0)),
			report[t].texture_bytes, int(b.get("texture_bytes", 0)), ("OVER " + ",".join(over)) if not over.is_empty() else "OK"])
		if not over.is_empty():
			_fail = true
	if not _dry and FileAccess.file_exists(_dir.path_join("signature.json")):
		print("NOTE the folder was signed before and its files changed: sign it again (iamar-world sign, or pack) before validate or preview accept it")
	return 1 if _fail else 0


func _images(s: Dictionary) -> PackedStringArray:
	var out := {}
	var sky: Dictionary = s.get("environment", {}).get("sky", {})
	if sky.get("type", "") == "cubemap":
		for f in sky.faces:
			out[sky.faces[f]] = true
	var t: Dictionary = s.get("terrain", {})
	for l in t.get("materials", []):
		if l.has("texture"):
			out[l.texture] = true
	for p in s.get("primitives", []):
		if p.has("texture"):
			out[p.texture] = true
	# far-model card pictures (WorldImpostors), when they have been rendered
	for p in WorldImpostors.image_paths(s, func(q: String) -> bool: return FileAccess.file_exists(_dir.path_join(q))):
		out[p] = true
	# (a heightmap is data, not a picture: every tier keeps it as it is)
	return PackedStringArray(out.keys())


## The top tier's copy of `p` (made from the package's own file the first time).
func _source(p: String, top: String) -> String:
	var v := _dir.path_join(WorldTiers.variant_path(p, top))
	if FileAccess.file_exists(v):
		return v
	var own := _dir.path_join(p)
	if not FileAccess.file_exists(own):
		if _reused.has(p):
			print("INFO %s: reused by hash (not in this folder), the same on every tier" % p)
		else:
			printerr("WARN %s: missing, skipped" % p)
		return ""
	if not _dry:
		DirAccess.make_dir_recursive_absolute(v.get_base_dir())
		DirAccess.copy_absolute(own, v)
		print("SOURCE %s -> %s" % [p, WorldTiers.variant_path(p, top)])
		return v
	return own


## A tier's variant that is byte-for-byte the file the tier below uses adds nothing
## (resolution falls back to it): remove it. That includes the top tier's kept
## source when every tier came out the same: the package's own file is then the
## source. Returns how many files went.
func _dedupe(p: String, tiers: PackedStringArray) -> int:
	var n := 0
	var below := _dir.path_join(p)
	for i in range(1, tiers.size()):
		var v := _dir.path_join(WorldTiers.variant_path(p, tiers[i]))
		if not FileAccess.file_exists(v):
			continue
		if FileAccess.file_exists(below) and FileAccess.get_file_as_bytes(v) == FileAccess.get_file_as_bytes(below):
			DirAccess.remove_absolute(v)
			n += 1
		else:
			below = v
	return n


# ------------------------------------------------------------------ models

func _model(src: String, rel_out: String, ratio: float, max_edge: int, is_top: bool, normals := true) -> Dictionary:
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	if doc.append_from_file(src, st) != OK:
		printerr("ERROR %s: not a readable glTF binary" % src)
		return {}
	var root := doc.generate_scene(st)
	if root == null:
		printerr("ERROR %s: no scene" % src)
		return {}
	var tris := 0
	var changed := false
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var mesh := (mi as MeshInstance3D).mesh
		if mesh == null:
			continue
		if not is_top and ratio < 0.999:
			mesh = simplify(mesh, ratio)
			(mi as MeshInstance3D).mesh = mesh
			changed = true
		tris += triangles(mesh)
	var tex := _fit_textures(root, max_edge, normals or is_top)
	changed = changed or tex.z > 0
	if is_top or not changed:
		# the file is kept as it is: images no material uses are still in it, and the
		# browser counts every embedded image
		tex.x += _unused_image_bytes(st, root)
	if not is_top and not _dry:
		var out := _dir.path_join(rel_out)
		DirAccess.make_dir_recursive_absolute(out.get_base_dir())
		if not changed:
			# nothing to cut: the same bytes (re-encoding would only grow the file)
			if src != out:
				DirAccess.copy_absolute(src, out)
			root.free()
			return {"triangles": tris, "texture_bytes": tex.x, "texture_size": tex.y}
		var d2 := GLTFDocument.new()
		var s2 := GLTFState.new()
		# JPEG unless a texture needs its alpha (cut-out leaves, hair)
		d2.image_format = "PNG" if tex.w > 0 else "JPEG"
		d2.lossy_quality = 0.88
		if d2.append_from_scene(root, s2) != OK or d2.write_to_filesystem(s2, out) != OK:
			printerr("ERROR %s: could not write" % out)
			root.free()
			return {}
	root.free()
	return {"triangles": tris, "texture_bytes": tex.x, "texture_size": tex.y}


## Triangles of a mesh (the way WorldPackage counts them for the budgets).
static func triangles(m: Mesh) -> int:
	var t := 0
	for s in m.get_surface_count():
		var arr: Array = m.surface_get_arrays(s)
		var n: int = (arr[Mesh.ARRAY_INDEX] as PackedInt32Array).size() if arr[Mesh.ARRAY_INDEX] != null else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
		t += n / 3
	return t


## A copy of `mesh` with about `ratio` of its triangles (per surface), using the LOD
## simplifier Godot imports models with. Vertex data is untouched, so skinning, UVs and
## materials still match; surfaces with blend shapes are left whole.
static func simplify(mesh: Mesh, ratio: float) -> ArrayMesh:
	var out := ArrayMesh.new()
	for i in mesh.get_surface_count():
		var arr: Array = mesh.surface_get_arrays(i)
		var mat := mesh.surface_get_material(i)
		var prim: int = mesh.surface_get_primitive_type(i) if mesh is ArrayMesh else Mesh.PRIMITIVE_TRIANGLES
		var flags: int = ((mesh as ArrayMesh).surface_get_format(i) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS) if mesh is ArrayMesh else 0
		var has_bs := mesh is ArrayMesh and (mesh as ArrayMesh).get_blend_shape_count() > 0
		var n_tris := ((arr[Mesh.ARRAY_INDEX] as PackedInt32Array).size() if arr[Mesh.ARRAY_INDEX] != null else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()) / 3
		if prim == Mesh.PRIMITIVE_TRIANGLES and not has_bs and n_tris >= MIN_SIMPLIFY_TRIS:
			if arr[Mesh.ARRAY_INDEX] == null:
				var idx := PackedInt32Array()
				for v in (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size():
					idx.append(v)
				arr[Mesh.ARRAY_INDEX] = idx
			var want := int((arr[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3.0 * ratio)
			var im := ImporterMesh.new()
			im.add_surface(prim, arr, [], {}, mat)
			im.generate_lods(25.0, 60.0, [])
			var best := arr[Mesh.ARRAY_INDEX] as PackedInt32Array
			for l in im.get_surface_lod_count(0):
				var li := im.get_surface_lod_indices(0, l)
				# the first level at or under the target (levels get coarser); keep at least 4 triangles
				if li.size() >= 12 and li.size() / 3 <= maxi(want, 4) * 1.15:
					best = li
					break
				if li.size() >= 12:
					best = li
			arr[Mesh.ARRAY_INDEX] = best
		out.add_surface_from_arrays(prim, arr, [], {}, flags)
		out.surface_set_material(i, mat)
	return out


## Halves every texture of the scene's materials until it fits max_edge. Returns
## Vector4i(bytes as w*h*4 summed, largest edge, textures resized, textures with alpha).
## A texture several materials share (one glTF image) is counted and resized once, and
## stays shared, as the browser counts it.
func _fit_textures(root: Node, max_edge: int, normals := true) -> Vector4i:
	var seen := {}
	var fitted := {}   ## the model's texture -> the one this tier uses for it
	var bytes := 0
	var edge := 0
	var resized := 0
	var alpha := 0
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var mesh := (mi as MeshInstance3D).mesh
		if mesh == null:
			continue
		for i in mesh.get_surface_count():
			var mat := mesh.surface_get_material(i) as BaseMaterial3D
			if mat == null or seen.has(mat):
				continue
			seen[mat] = true
			if not normals and mat.normal_enabled:
				# this tier draws no normal maps (manifest.tiers.<tier>.normal_maps: false)
				mat.normal_enabled = false
				mat.normal_texture = null
				resized += 1
			for slot in [BaseMaterial3D.TEXTURE_ALBEDO, BaseMaterial3D.TEXTURE_NORMAL, BaseMaterial3D.TEXTURE_ORM,
					BaseMaterial3D.TEXTURE_ROUGHNESS, BaseMaterial3D.TEXTURE_METALLIC, BaseMaterial3D.TEXTURE_EMISSION,
					BaseMaterial3D.TEXTURE_AMBIENT_OCCLUSION]:
				var t := mat.get_texture(slot)
				if t == null:
					continue
				if fitted.has(t):
					if fitted[t] != t:
						mat.set_texture(slot, fitted[t])
					continue
				fitted[t] = t
				var img := t.get_image()
				if img == null:
					continue
				if img.is_compressed():
					img.decompress()
				if img.detect_alpha() != Image.ALPHA_NONE:
					alpha += 1
				var w := img.get_width()
				var h := img.get_height()
				if maxi(w, h) > max_edge:
					var k := 1
					while maxi(w, h) / k > max_edge:
						k *= 2
					img.resize(maxi(1, w / k), maxi(1, h / k), Image.INTERPOLATE_LANCZOS)
					fitted[t] = ImageTexture.create_from_image(img)
					mat.set_texture(slot, fitted[t])
					resized += 1
				bytes += img.get_width() * img.get_height() * 4
				edge = maxi(edge, maxi(img.get_width(), img.get_height()))
	return Vector4i(bytes, edge, resized, alpha)


## Bytes (w*h*4) of the images embedded in a glTF that no material of its scene uses.
func _unused_image_bytes(st: GLTFState, root: Node) -> int:
	var used := {}
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var mesh := (mi as MeshInstance3D).mesh
		if mesh == null:
			continue
		for i in mesh.get_surface_count():
			var mat := mesh.surface_get_material(i) as BaseMaterial3D
			if mat == null:
				continue
			for slot in BaseMaterial3D.TEXTURE_MAX:
				var t := mat.get_texture(slot)
				if t != null:
					used[t] = true
	var n := 0
	for t in st.get_images():
		if t != null and not used.has(t):
			n += t.get_width() * t.get_height() * 4
	return n


## Quest look models and how many of each the quests place (WorldFormat.quest_look_models).
static func quest_look_models(quests: Array) -> Dictionary:
	var out := {}
	for q in quests:
		if not q is Dictionary:
			continue
		for st in q.get("steps", []):
			for o in (st if st is Array else [st]):
				if not o is Dictionary:
					continue
				var p := String(o.get("look", ""))
				if p.ends_with(".glb"):
					var n: int = o.get("spots", []).size() if o.has("spots") else int(o.get("count", 1))
					out[p] = int(out.get(p, 0)) + maxi(n, 1)
	return out


const _CREATURES := ["chicken", "bunny", "cow", "horse", "deer", "wolf", "duck", "duckling", "fish", "frog", "turtle"]

## Triangles of the scene parts that are the same on every tier, counted as
## WorldPackage._measure does: primitives, terrain, water, creatures.
static func scene_fixed_triangles(s: Dictionary) -> int:
	var tri := 0
	var builder := _global_class("WorldBuilder")
	for p in s.get("primitives", []):
		var m: Mesh = builder.primitive_mesh(p) if builder != null else _primitive_mesh(p)
		tri += triangles(m)
	var t: Dictionary = s.get("terrain", {})
	match String(t.get("type", "none")):
		"flat": tri += 2
		"heightmap", "procedural":
			var r := int(t.get("resolution", 129))
			tri += 2 * (r - 1) * (r - 1)
	tri += 2 * s.get("water", []).size()
	var fmt := _global_class("WorldFormat")
	var kinds: Array = fmt.CREATURES if fmt != null else _CREATURES
	for c in s.get("creatures", []):
		if String(c.get("kind", "")) in kinds:
			tri += 1200 * int(c.get("count", 1))   # AnimalKit animals are ~0.5-2k triangles
	return tri


## A browser class by name, or null where it is not loaded (a test's small project).
static func _global_class(name: String) -> Script:
	for c in ProjectSettings.get_global_class_list():
		if String(c.get("class", "")) == name:
			return load(String(c.path)) as Script
	return null


## WorldBuilder.primitive_mesh's shapes, for the triangle count only.
static func _primitive_mesh(p: Dictionary) -> Mesh:
	match String(p.get("shape", "")):
		"box":
			return BoxMesh.new()
		"sphere":
			var s := SphereMesh.new()
			s.radial_segments = 32
			s.rings = 16
			return s
		"cylinder":
			var c := CylinderMesh.new()
			c.radial_segments = 24
			return c
		"capsule":
			return CapsuleMesh.new()
	return PlaneMesh.new()


# ------------------------------------------------------------------ images

func _image(src: String, rel_out: String, max_edge: int, is_top: bool) -> Dictionary:
	var img := Image.load_from_file(src)
	if img == null:
		printerr("WARN %s: not a readable image, skipped" % src)
		return {"texture_bytes": 0, "texture_size": 0}
	var w := img.get_width()
	var h := img.get_height()
	if not is_top and maxi(w, h) > max_edge:
		var k := 1
		while maxi(w, h) / k > max_edge:
			k *= 2
		img.resize(maxi(1, w / k), maxi(1, h / k), Image.INTERPOLATE_LANCZOS)
	if not is_top and not _dry:
		var out := _dir.path_join(rel_out)
		DirAccess.make_dir_recursive_absolute(out.get_base_dir())
		if img.get_width() == w and img.get_height() == h:
			DirAccess.copy_absolute(src, out)   # fits already: the same bytes
		elif src.to_lower().ends_with(".png"):
			img.save_png(out)
		else:
			img.save_jpg(out, 0.88)
	return {"texture_bytes": img.get_width() * img.get_height() * 4, "texture_size": maxi(img.get_width(), img.get_height())}
