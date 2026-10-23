extends SceneTree
## The kit's asset library commands (kit/AGENT_KIT.md "Reuse first"):
##
##   iamar-world assets list [--all]               reusable objects on this machine (--all: locked ones too)
##   iamar-world assets search <words...>          by name, file, world or author
##   iamar-world assets show <hash|name>           one object: size, triangles, licence, source, why (not) reusable
##   iamar-world assets use <world folder> <hash|name> [--as assets/<name>.glb]
##                                                 reference it from your world instead of copying it
##   iamar-world assets building <kind> <out.glb> [--width ..]  an Oakhaven house, inn, chapel, ... as a .glb (KitBuildings)
##   iamar-world assets building house <out.glb> --rooms bedroom:3,living,kitchen,bath:2 [--floors 1|2]
##       [--style beach|modern|plaster|stone] [--roof gable|flat]   a house planned from its rooms (KitHouseRooms)
##   iamar-world assets builtin-index              (maintainers) rebuild scripts/worlds/builtin_assets.json
##
## IAMAR_CACHE is where downloaded worlds are (the browser's cache). Worlds signed
## with your own keys (~/.config/iamar/signing/*.key) are always reusable to you.
## Objects from OTHER players' worlds are reusable only when their creator allowed
## it in the world's signed manifest (manifest.reuse); `use` refuses the others.

const LICENSES := "res://manifests/progressive-download/oakhaven-linux-x86_64-v1.json"
const AUTHORS := {"kenney-cc0": "Kenney (kenney.nl)", "quaternius-cc0": "Quaternius (quaternius.com)"}
## Not a global class in the kit pack (a pack carries no class cache): reached by path.
const KitBuildings = preload("res://scripts/kit/kit_buildings.gd")
const KitHouseRooms = preload("res://scripts/kit/kit_house_rooms.gd")


func _init() -> void:
	var args := KitLoop.user_args()
	var cmd := args[0] if args.size() > 0 else "help"
	var rest := args.slice(1)
	var code := 0
	match cmd:
		"list": code = _list(rest)
		"search": code = _search(" ".join(rest))
		"show": code = _show(rest[0] if rest.size() > 0 else "")
		"use": code = _use(rest)
		"builtin-index": code = _builtin_index()
		"building":
			if rest.size() < 2 or not String(rest[0]) in KitBuildings.KINDS:
				print("usage: iamar-world assets building <%s> <out.glb> [--width 8] [--depth 6] [--floors 2] [--style plaster|stone|brick]" % "|".join(KitBuildings.KINDS))
				print("       iamar-world assets building house <out.glb> --rooms bedroom:3,living,kitchen,bath:2 [--floors 1|2] [--style beach|modern|plaster|stone] [--roof gable|flat]")
				code = 2
			elif String(rest[0]) == "house" and KitBuildings.opts(rest.slice(2)).has("rooms"):
				# relative to where the creator ran the kit, like `new`, not the browser's folder
				code = KitHouseRooms.export(_abs(String(rest[1])), KitBuildings.opts(rest.slice(2)))
			else:
				code = KitBuildings.export(String(rest[0]), _abs(String(rest[1])), KitBuildings.opts(rest.slice(2)))
		"thumbnails":
			_thumbnails.call_deferred(rest)
			return
		_:
			print("usage: iamar-world assets list [--all] | search <words> | show <hash|name> | use <world folder> <hash|name> [--as assets/<name>.glb] | builtin-index")
			code = 2
	quit(code)


## A world folder given on the command line: relative to where the kit was run.
static func _abs(p: String) -> String:
	return KitLoop.absolute_path(p)


## JSON numbers come back as floats; write whole numbers as integers again, so
## `"format_version": 0` stays 0 (not 0.0) and budgets stay integers.
static func _ints(v: Variant) -> Variant:
	if v is float and is_finite(v) and v == floorf(v) and absf(v) < 9.0e15:
		return int(v)
	if v is Dictionary:
		var d := {}
		for k in v:
			d[k] = _ints(v[k])
		return d
	if v is Array:
		return (v as Array).map(func(x): return _ints(x))
	return v


## Size of an object: [width, height, depth] in metres and its triangles, from the
## index when it has them, else by loading the model (built-in or from a downloaded
## package). {} when it cannot be read.
static func measure(e: Dictionary) -> Dictionary:
	if e.get("size") is Array and (e.size as Array).size() == 3:
		return {"size": e.size, "triangles": int(e.get("triangles", 0))}
	var node: Node = null
	if e.kind == "builtin":
		var ps := load("res://" + String(e.file)) as PackedScene
		if ps:
			node = ps.instantiate()
	elif e.kind == "world" and String(e.get("package", "")) != "":
		var s := WorldSource.open(e.package)
		var b := s.read(e.file) if s.ok() else PackedByteArray()
		s.close()
		var doc := GLTFDocument.new()
		var st := GLTFState.new()
		if b.size() > 0 and doc.append_from_buffer(b, "", st) == OK:
			node = doc.generate_scene(st)
	if node == null or not node is Node3D:
		if node:
			node.free()
		return {}
	var box := WorldPackage._aabb(node as Node3D)
	var tris := WorldPackage._triangles(node)
	node.free()
	return {"size": [snappedf(box.size.x, 0.01), snappedf(box.size.y, 0.01), snappedf(box.size.z, 0.01)],
		"triangles": tris, "bottom": snappedf(box.position.y, 0.01)}


static func library() -> AssetLibrary:
	return AssetLibrary.scan({"own_keys": AssetLibrary.own_keys()})


## Text from downloaded worlds is untrusted (a stranger wrote it): one line, control
## characters removed, length capped, so it cannot fake output lines or carry instructions
## into the creator's agent (audit kit-1).
static func _t(v, cap: int = 80) -> String:
	var out := ""
	for ch in String(v):
		var c := ch.unicode_at(0)
		out += " " if (c < 32 or c == 127 or (c >= 0x80 and c < 0xA0) or c == 0x2028 or c == 0x2029) else ch
	out = " ".join(out.split(" ", false))
	return out if out.length() <= cap else out.left(cap - 3) + "..."


static func _clean_entry(e: Dictionary) -> Dictionary:
	var c := e.duplicate()
	for k in ["name", "file", "world", "license", "author", "why", "version", "key_id"]:
		if c.has(k):
			c[k] = _t(c[k], 200 if k == "why" else 80)
	return c


static func _line(raw: Dictionary) -> String:
	var e := _clean_entry(raw)
	if e.kind == "creature":
		return "CREATURE %s  (%s)" % [e.name, e.why]
	var sz := ""
	if e.get("size") is Array and (e.size as Array).size() == 3:
		sz = " %sx%sx%s m" % [e.size[0], e.size[1], e.size[2]]
	return "%s %s %s %s %s tris%s %s %s%s" % ["ASSET" if e.reusable else "LOCKED", String(e.sha256).left(12),
		e.name, _size_note(e), e.triangles if e.triangles > 0 else "?", sz, e.license, e.world,
		"" if e.reusable else "  (" + e.why + ")"]


## What an object adds to a world's download. A built-in is referenced by hash and the
## browser loads its own copy, so it adds nothing; its index bytes (glTF + the shared
## trim-sheet textures it hashes) are not a download (an internal task: the bed read as 6 MB).
static func _size_note(e: Dictionary) -> String:
	if e.kind == "builtin":
		return "built in (0 bytes download)"
	return "%d bytes" % int(e.bytes)


func _list(rest: Array) -> int:
	var lib := library()
	var all := "--all" in rest
	var n := 0
	for e in lib.entries:
		if e.kind == "creature":
			print(_line(e))
			n += 1
		elif e.reusable or all:
			print(_line(e))
			n += 1
	for err in lib.errors:
		print("SKIPPED ", _t(err, 200))
	print("COUNT %d" % n)
	return 0


func _search(q: String) -> int:
	var hits := library().search(q)
	for e in hits:
		print(_line(e))
	print("COUNT %d" % hits.size())
	return 0


func _show(key: String) -> int:
	var e := library().find(key)
	if e.is_empty():
		print("ERROR no object %s in the library (try: iamar-world assets search <words>)" % key)
		return 1
	if e.kind != "creature":
		var ms := measure(e)
		if not ms.is_empty():
			e = e.duplicate()
			e.triangles = ms.triangles
			# width (x), height (y), depth (z) at scale 1, glTF axes (+Y up, -Z forward)
			print("SIZE %s x %s x %s m (width x height x depth at scale 1; scale it in scene.json objects)" % [ms.size[0], ms.size[1], ms.size[2]])
			if ms.has("bottom"):
				print("BOTTOM %s m (its lowest point relative to its origin)" % ms.bottom)
	e = _clean_entry(e)
	for k in ["sha256", "name", "file", "bytes", "triangles", "world", "kind", "version", "key_id", "license", "author", "reusable", "why"]:
		print("%s %s" % [k.to_upper(), e.get(k, "")])
	if String(e.get("thumbnail", "")) != "":
		print("THUMBNAIL ", ProjectSettings.globalize_path(e.thumbnail))
	if e.kind == "creature":
		print("USE add to scene.json creatures: {\"kind\": \"%s\", \"position\": [x, 0, z], \"count\": 3, \"wander_radius\": 8}" % e.name)
	return 0


## Adds (or replaces) a manifest.reused entry; the world's scene.json then places
## the object by that path like any asset. Built-ins are referenced, nothing is copied;
## another world's object is copied into the folder with its credit (browsers refuse
## world-sourced reused records).
func _use(rest: Array) -> int:
	if rest.size() < 2:
		print("usage: iamar-world assets use <world folder> <hash|name> [--as assets/<name>.glb]")
		return 2
	var folder := _abs(String(rest[0]))
	var raw := library().find(String(rest[1]))
	if raw.is_empty():
		print("ERROR no object %s in the library" % _t(rest[1]))
		return 1
	# print the cleaned copy; the manifest record keeps the raw fields, which
	# AssetLibrary.resolve() matches exactly against the downloaded package
	var e := _clean_entry(raw)
	if not e.reusable:
		print("ERROR %s from %s is locked: %s. Model your own, or ask its creator to allow reuse." % [e.name, e.world, e.why])
		return 1
	if e.kind == "creature":
		print("CREATURE %s needs no file: add {\"kind\": \"%s\", \"position\": [x, 0, z], \"count\": 3, \"wander_radius\": 8} to scene.json creatures (and \"creatures\" to manifest features). It keeps its behaviour: %s" % [e.name, e.name, e.why])
		return 0
	var as_path := "assets/%s.glb" % String(e.name).to_lower().replace(" ", "_")
	var i := rest.find("--as")
	if i >= 0 and i + 1 < rest.size():
		as_path = String(rest[i + 1])
	if not as_path.begins_with("assets/") or not as_path.ends_with(".glb") or as_path.contains("..") or as_path.contains("//") \
			or not RegEx.create_from_string("^[A-Za-z0-9_./-]{1,200}$").search(as_path):
		print("ERROR --as must be a path like assets/<name>.glb (letters, digits, _ . / - only)")
		return 2
	var mp := folder.path_join(WorldFormat.MANIFEST)
	var m = JSON.parse_string(FileAccess.get_file_as_string(mp))
	if not m is Dictionary:
		print("ERROR no readable manifest.json in %s" % folder)
		return 1
	if FileAccess.file_exists(folder.path_join(as_path)):
		print("ERROR %s is already a file in the world; pick another --as path" % as_path)
		return 1
	if e.kind == "world":
		# Browsers refuse a reused record whose source is another world (an internal task): carry
		# the bytes, with licence and credit, so the package stands alone.
		var s := WorldSource.open(String(raw.get("package", "")))
		var b := s.read(String(raw.file)) if s.ok() else PackedByteArray()
		s.close()
		if b.is_empty() or _sha256_hex(b) != String(raw.sha256):
			print("ERROR %s could not be read from its downloaded package (or its hash differs); visit the world again" % e.name)
			return 1
		DirAccess.make_dir_recursive_absolute(folder.path_join(as_path).get_base_dir())
		var out := FileAccess.open(folder.path_join(as_path), FileAccess.WRITE)
		if out == null:
			print("ERROR cannot write %s" % as_path)
			return 1
		out.store_buffer(b)
		out.close()
		var credits: Array = m.get("credits", [])
		credits = credits.filter(func(c) -> bool: return not (c is Dictionary and (c.get("files", []) as Array).has(as_path)))
		credits.append({"files": [as_path], "author": String(e.author), "license": String(e.license),
			"source": "%s %s" % [e.world, e.file]})
		m.credits = credits
		var f2 := FileAccess.open(mp, FileAccess.WRITE)
		f2.store_string(JSON.stringify(_ints(m), "  ", false) + "\n")
		f2.close()
		print("USED %s as %s (copied %d bytes into the world; %s, from %s %s). Place it in scene.json objects with \"asset\": \"%s\"; re-sign before publishing." % [
			e.name, as_path, b.size(), e.license, e.world, e.file, as_path])
		return 0
	var list: Array = m.get("reused", [])
	list = list.filter(func(r) -> bool: return String(r.path) != as_path)
	list.append(AssetLibrary.reused_record(raw, as_path))
	m.reused = list
	var f := FileAccess.open(mp, FileAccess.WRITE)
	f.store_string(JSON.stringify(_ints(m), "  ", false) + "\n")
	f.close()
	print("USED %s as %s (%s, %s, from %s %s). Place it in scene.json objects with \"asset\": \"%s\"; re-sign before publishing." % [
		e.name, as_path, "built in, 0 bytes in your download" if e.kind == "builtin" else "%d bytes reused" % int(e.bytes),
		e.license, e.world, e.file, as_path])
	return 0


## Rebuilds the built-in index from res://assets: hash, bytes, triangles and the
## licence the progressive-download manifest assigns to each file (CREDITS.md).
func _builtin_index() -> int:
	var lic := {}
	var cat := {}
	if FileAccess.file_exists(LICENSES):
		var d = JSON.parse_string(FileAccess.get_file_as_string(LICENSES))
		for c in d.get("license_catalog", []):
			cat[c.id] = c
		for a in d.get("assets", []):
			lic[a.path] = a.get("license_refs", [])
	var files: Array = []
	_glbs("res://assets", files)
	files.sort()
	var objects: Array = []
	for res in files:
		var rel := String(res).trim_prefix("res://")
		var refs: Array = lic.get(rel, [])
		var license := "CC0-1.0"
		var author := ""
		for r in refs:
			if cat.has(r):
				license = String(cat[r].license)
				author = AUTHORS.get(r, "")
		if license != "CC0-1.0":
			continue   # only third-party CC0 art is offered; original Oakhaven work has no licence statement yet
		var id := AssetLibrary.builtin_hash(res)
		if id.is_empty():
			continue
		var tris := 0
		var size := []
		var ps := load(res) as PackedScene
		if ps:
			var n := ps.instantiate()
			tris = WorldPackage._triangles(n)
			if n is Node3D:
				var box := WorldPackage._aabb(n as Node3D)
				size = [snappedf(box.size.x, 0.01), snappedf(box.size.y, 0.01), snappedf(box.size.z, 0.01)]
			n.free()
		objects.append({"file": rel, "sha256": id.sha256, "bytes": id.bytes,
			"triangles": tris, "size": size, "license": license, "author": author})
	var out := {"format": "iamar-builtin-assets", "version": 1, "objects": objects}
	var f := FileAccess.open(AssetLibrary.BUILTIN_INDEX, FileAccess.WRITE)
	f.store_string(JSON.stringify(out, " ") + "\n")
	f.close()
	print("BUILTIN %d objects -> %s" % [objects.size(), AssetLibrary.BUILTIN_INDEX])
	return 0


## 128 px previews of every built-in object into kit/thumbnails/<sha16>.png (needs a
## display: run under offscreen). Skips ones already there.
func _thumbnails(rest: Array) -> void:
	var size := 128
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(AssetLibrary.THUMBS))
	var vp := SubViewport.new()
	vp.size = Vector2i(size, size)
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.75, 0.78, 0.85)
	env.environment.ambient_light_energy = 0.6
	vp.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 35, 0)
	vp.add_child(sun)
	var cam := Camera3D.new()
	cam.fov = 35
	vp.add_child(cam)
	var made := 0
	for o in AssetLibrary.builtin_index():
		var out := AssetLibrary.THUMBS + String(o.sha256).left(16) + ".png"
		if FileAccess.file_exists(out) and not "--force" in rest:
			continue
		var ps := load("res://" + String(o.file)) as PackedScene
		if ps == null:
			continue
		var n := ps.instantiate() as Node3D
		if n == null:
			continue
		vp.add_child(n)
		var box := WorldPackage._aabb(n)
		var c := box.get_center()
		var r := maxf(box.size.length() * 0.5, 0.05)
		var d := r / sin(deg_to_rad(cam.fov * 0.5)) * 1.05
		cam.look_at_from_position(c + Vector3(0.75, 0.55, 1.0).normalized() * d, c)
		cam.near = maxf(d - r * 2.0, 0.01)
		cam.far = d + r * 2.0
		await process_frame
		await process_frame
		await RenderingServer.frame_post_draw
		var img := vp.get_texture().get_image()
		img.save_png(ProjectSettings.globalize_path(out))
		n.queue_free()
		await process_frame
		made += 1
	print("THUMBNAILS %d new in %s" % [made, AssetLibrary.THUMBS])
	quit(0)


func _glbs(dir: String, out: Array) -> void:
	var d := DirAccess.open(dir)
	if d == null:
		return
	for f in d.get_files():
		if f.ends_with(".glb") or f.ends_with(".gltf"):
			out.append(dir.path_join(f))
	for s in d.get_directories():
		_glbs(dir.path_join(s), out)


## Lowercase hex sha256 of `b` (PackedByteArray has no sha256_text in Godot 4.7).
static func _sha256_hex(b: PackedByteArray) -> String:
	var h := HashingContext.new()
	h.start(HashingContext.HASH_SHA256)
	h.update(b)
	return h.finish().hex_encode()
