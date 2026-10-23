extends SceneTree
## `iamar-world techniques <folder|file.iamar> [--strict]`: what the kit's recipe book
## (kit/recipes/techniques.json) does for this world, and what it cannot do for it.
##   TECHNIQUE <id> <count> ...   the automatic recipes (WorldTechniques) every visitor's
##                                browser applies to this world, measured on a real build
##   ADVICE <id> ...              recipes the kit cannot apply by itself, where this world
##                                would gain from them (with the objects to fix)
##   OFF <id>                     an automatic recipe the manifest turned off
## Exit 0, or 1 with --strict when there is any ADVICE (`pack` and `publish` print the
## report; they stop only on budgets). Headless: no screenshots.
##   godot --headless --path <oakhaven> -s res://scripts/kit/world_techniques_check.gd -- <folder> [--strict] [--tier t]

const IMPOSTOR_SIZE := 6.0        ## m: models this big seen from far away want a card
const IMPOSTOR_FAR := 60.0        ## m from every spawn point
const MESH_COLLISION_TRIS := 3000 ## a "mesh" collider over this many triangles
const SHADOW_LIGHTS := 2          ## shadowed point/spot lights before it gets expensive
const CLUTTER := 150              ## small objects with no min_tier before low GPUs suffer
const SMALL := 0.6                ## m radius of a "small" object
const BIG_TEXTURE := 2048         ## px on a model under 1 m


func _initialize() -> void:
	var args := KitLoop.user_args()
	if args.is_empty():
		printerr("usage: techniques <folder|file.iamar> [--strict] [--tier t]")
		quit(2)
		return
	var path := KitLoop.absolute_path(args[0])
	var opt := {"tier": "low"}   # (the hard targets are the low tier's)
	var i := args.find("--tier")
	if i >= 0 and i + 1 < args.size():
		opt["tier"] = args[i + 1]
	var pkg := WorldPackage.open(path, opt)
	if not pkg.ok:
		for e in pkg.errors:
			print("ERROR ", e)
		quit(1)
		return
	var advice := _advice(pkg)
	for id in WorldTechniques.RECIPES:
		if not WorldTechniques.enabled(pkg.manifest, id):
			print("OFF %s (manifest.techniques.%s is false)" % [id, id])
	var root := WorldBuilder.new(pkg, {"npcs": "none", "sounds": false, "creatures": false}).build()
	var rep: Dictionary = WorldTechniques.apply(root, pkg.manifest)
	print("TECHNIQUE lod_chain %d meshes got a distance LOD chain" % int(rep.get("lod_chain", 0)))
	print("TECHNIQUE instancing %d groups, %d copies drawn as MultiMesh" % [int(rep.get("instancing", 0)), int(rep.get("instanced_copies", 0))])
	print("TECHNIQUE tiny_no_shadow %d small objects cast no live shadow" % int(rep.get("tiny_no_shadow", 0)))
	print("TECHNIQUE foliage_thinning %d small objects stop drawing far away" % int(rep.get("foliage_thinning", 0)))
	print("TECHNIQUE invisible_proxy %d fully transparent walk/collision meshes are not drawn" % int(rep.get("invisible_proxy", 0)))
	print("TECHNIQUE light_pool %d lights wait until they are among the %d nearest" % [int(rep.get("light_pool", 0)), WorldTechniques.POOL])
	for a in advice:
		print("ADVICE ", a)
	print("TECHNIQUES tier=%s advice=%d" % [pkg.tier, advice.size()])
	root.free()
	quit(1 if "--strict" in args and not advice.is_empty() else 0)


## Recipes the kit cannot apply for the builder, where this world would gain.
static func _advice(pkg: WorldPackage) -> PackedStringArray:
	var out := PackedStringArray()
	var s := pkg.scene
	var spawns: Array = []
	for t in pkg.spawn_points.values():
		spawns.append((t as Transform3D).origin)
	if spawns.is_empty():
		spawns.append(pkg.spawn_point.origin)
	var far_big := PackedStringArray()
	var mesh_coll := PackedStringArray()
	var big_tex := PackedStringArray()
	var small_plain := 0
	for o in s.get("objects", []):
		var a: Dictionary = pkg.assets.get(o.asset, {})
		if a.is_empty():
			continue
		var sc: Variant = o.get("scale", 1.0)
		var k := float(sc) if (sc is float or sc is int) else maxf(float(sc[0]), maxf(float(sc[1]), float(sc[2])))
		var box: AABB = a.aabb
		var size := box.size.length() * k
		var pos := WorldPackage.vec3(o.get("position", [0, 0, 0]))
		var near := INF
		for sp in spawns:
			near = minf(near, pos.distance_to(sp))
		var label := String(o.get("id", o.asset))
		if size >= IMPOSTOR_SIZE and near >= IMPOSTOR_FAR and not o.has("impostor"):
			far_big.append(label)
		# (ground, floors and docks people walk on are flat and rightly "mesh": not advice)
		var flat := box.size.y * k < 0.25 * maxf(box.size.x, box.size.z) * k
		if String(o.get("collision", "none")) == "mesh" and int(a.triangles) > MESH_COLLISION_TRIS and not flat:
			mesh_coll.append("%s (%d triangles)" % [label, int(a.triangles)])
		if size * 0.5 < 1.0 and int(a.texture_size) >= BIG_TEXTURE:
			big_tex.append("%s (%d px)" % [label, int(a.texture_size)])
		if size * 0.5 < SMALL and not o.has("min_tier"):
			small_plain += 1
	if not far_big.is_empty():
		out.append("impostor: %d big models stand %d m or more from every spawn; give them \"impostor\": <m> and run iamar-world impostors (%s)" % [far_big.size(), int(IMPOSTOR_FAR), _list(far_big)])
	if not mesh_coll.is_empty():
		out.append("collision_proxy: mesh colliders on detailed models over %d triangles that are not walk surfaces; use \"box\" or a simple invisible proxy (%s)" % [MESH_COLLISION_TRIS, _list(mesh_coll)])
	if not big_tex.is_empty():
		out.append("texture_sizes: small models with large textures; 512-1024 px is plenty under 1 m (%s)" % _list(big_tex))
	if small_plain > CLUTTER and WorldTiers.declared(pkg.manifest).size() > 1:
		out.append("min_tier: %d small objects all draw on the low tier; mark the clutter \"min_tier\": \"medium\"" % small_plain)
	var shadowed := 0
	for l in s.get("lights", []):
		if l.get("shadows", false):
			shadowed += 1
	if shadowed > SHADOW_LIGHTS:
		out.append("live_only_moving: %d point/spot lights cast shadows; keep it to %d (each is another shadow pass)" % [shadowed, SHADOW_LIGHTS])
	if WorldTiers.declared(pkg.manifest).size() == 1 and int(pkg.stats.get("triangles", 0)) > 100000:
		out.append("tiers: one tier only at %d triangles; declare manifest.tiers so weak GPUs get a lighter world (docs/WORLD_TIERS.md)" % int(pkg.stats.triangles))
	return out


static func _list(a: PackedStringArray) -> String:
	var shown := a.slice(0, 6)
	return ", ".join(shown) + (" and %d more" % (a.size() - 6) if a.size() > 6 else "")
