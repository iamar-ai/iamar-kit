extends RefCounted
## Validate checks for worlds that open fine but play or look wrong (an internal task):
## a spawn in the air, under water, inside a solid or over no ground; a terrain
## that eats the triangle budget; colours the linear tonemap clips to white; house
## rooms no light reaches (an internal task).
## Every line says what to change. world_view.gd prints them as WARN lines.
##
## The checks read plain scene data and two callables, so they run without a
## browser in tests/kit_world_checks:
##   height_at(x, z, from_y) -> float   highest ground at or below from_y, NAN if none
##   solid_at(feet: Vector3) -> String  name of a solid a standing visitor there touches, "" if none
##                                      (solids() + solid_hit() give one from a built world)

const TARGET_TRIS := 150000          ## the low tier's triangle target (kit/AGENT_KIT.md "Hard targets")
const TERRAIN_SHARE_MAX := 0.4       ## a terrain above this share of the budget gets a WARN
const TERRAIN_SHARE_SUGGEST := 0.25  ## the suggested resolution fits in this share
const SPAWN_AIR_M := 0.5             ## a spawn higher than this above its ground is "in the air"
const SPAWN_LIFT_M := 1.0            ## the browser drops a spawn onto ground found from this far above it (WorldGround.drop)
const WATER_FEET_M := 0.2            ## water deeper than this over a spawn's ground: visitors start in water
const WATER_HEAD_M := 1.5            ## deeper than this: they start under water
const CLIP := 0.95                   ## a lit channel above this clips to white under the linear tonemap
const CLIP_TARGET := 0.85            ## the suggested colour lights to this at most
const NAME_LIST := 3                 ## names shown per clipped colour before "+N more"
const VISITOR_R := 0.3               ## a standing visitor: radius, and knee to head above the feet
const VISITOR_KNEE := 0.35           ## (steps and slopes below the knee are fine)
const VISITOR_HEAD := 1.75


## The raw spawn positions as the package states them, before the builder drops
## them onto the ground: id -> Vector3. The manifest's own spawn is "spawn".
static func raw_spawns(manifest: Dictionary, scene: Dictionary) -> Dictionary:
	var out := {}
	for sp in scene.get("spawn_points", []):
		if sp is Dictionary and sp.get("position") is Array and (sp.position as Array).size() == 3:
			out[String(sp.get("id", "spawn_%d" % out.size()))] = _v3(sp.position)
	var want: Variant = manifest.get("spawn", null)
	if want is Dictionary and want.get("position") is Array and (want.position as Array).size() == 3:
		out["spawn"] = _v3(want.position)
	return out


## Spawn mistakes: no ground, under the ground, in the air, in or under water, inside a solid.
static func spawn_warnings(spawns: Dictionary, waters: Array, height_at: Callable, solid_at := Callable()) -> PackedStringArray:
	var out := PackedStringArray()
	for id in spawns:
		var p: Vector3 = spawns[id]
		var at := "spawn '%s' at %s" % [id, _xyz(p)]
		var g: float = height_at.call(p.x, p.z, p.y + SPAWN_LIFT_M)
		var top: float = height_at.call(p.x, p.z, 1e5)
		if is_nan(g):
			if is_nan(top):
				out.append("%s has no ground under it: visitors fall forever. Put terrain, a ground primitive with \"collision\" or a floor under it, or move the spawn over ground." % at)
			else:
				out.append("%s is %.2f m under the ground (surface y %.2f): visitors appear inside the ground and fall. Set its y to %.2f." % [at, top - p.y, top, top])
			continue
		if p.y - g > SPAWN_AIR_M:
			out.append("%s is %.2f m above the ground (ground y %.2f): visitors drop from the air and the spawn view looks from too high. Set its y to %.2f." % [at, p.y - g, g, g])
		for w in waters:
			if not (w is Dictionary) or not _over_water(w, p):
				continue
			var s := float(_v3(w.get("position", [0, 0, 0])).y)
			var deep := s - g
			if deep > WATER_HEAD_M:
				out.append("%s is under water: the surface (water '%s', y %.2f) is %.2f m above its ground (y %.2f). Move it onto the shore or raise the ground under it above y %.2f." % [at, _wid(w), s, deep, g, s])
			elif deep > WATER_FEET_M:
				out.append("%s stands in %.2f m of water (water '%s', surface y %.2f, ground y %.2f): visitors start wading. Move it onto the shore unless that is the point." % [at, deep, _wid(w), s, g])
		if solid_at.is_valid():
			var hit: String = solid_at.call(Vector3(p.x, g, p.z))
			if hit != "":
				out.append("%s is inside a solid (%s) where it lands (ground y %.2f): visitors start stuck. Move it into the open, at least 0.5 m from walls." % [at, hit, g])
	return out


## The convex colliders under `world` (StaticBody3D boxes, spheres, cylinders, capsules) as
## [name, global Transform3D, Shape3D] for solid_hit. Trimesh colliders are surfaces, not solids.
static func solids(world: Node) -> Array:
	var out: Array = []
	for cs in world.find_children("*", "CollisionShape3D", true, false):
		var s: Shape3D = (cs as CollisionShape3D).shape
		if cs.get_parent() is StaticBody3D and (s is BoxShape3D or s is SphereShape3D or s is CylinderShape3D or s is CapsuleShape3D):
			out.append([String(cs.get_parent().name), _placed(cs, world), s])
	return out


## n's transform relative to `top` (the world root is not always inside the tree yet).
static func _placed(n: Node, top: Node) -> Transform3D:
	var xf := Transform3D.IDENTITY
	while n != null and n != top:
		if n is Node3D:
			xf = (n as Node3D).transform * xf
		n = n.get_parent()
	if top is Node3D:
		xf = (top as Node3D).transform * xf
	return xf


## The name of the first solid a standing visitor at `feet` touches (knee to head, radius
## VISITOR_R), "" if none. Points every 0.2 m up the body, each tested against the shape grown
## sideways by the radius (corners count a little wide: a near miss there is still too close to a
## wall). Not grown up or down: the floor under the feet and a ceiling over the head are no solid.
static func solid_hit(shapes: Array, feet: Vector3) -> String:
	for e in shapes:
		var inv: Transform3D = (e[1] as Transform3D).affine_inverse()
		var y := VISITOR_KNEE
		while y <= VISITOR_HEAD + 0.001:
			if _inside(e[2], inv * (feet + Vector3(0, y, 0)), VISITOR_R):
				return e[0]
			y += 0.2
	return ""


static func _inside(s: Shape3D, p: Vector3, r: float) -> bool:
	if s is BoxShape3D:
		var h := (s as BoxShape3D).size * 0.5 + Vector3(r, 0, r)
		return absf(p.x) < h.x and absf(p.y) < h.y and absf(p.z) < h.z
	if s is SphereShape3D:
		return p.length() < (s as SphereShape3D).radius + r
	if s is CylinderShape3D:
		var c := s as CylinderShape3D
		return absf(p.y) < c.height * 0.5 and Vector2(p.x, p.z).length() < c.radius + r
	if s is CapsuleShape3D:
		var k := s as CapsuleShape3D
		var a := maxf(k.height * 0.5 - k.radius, 0.0)
		return p.distance_to(Vector3(0, clampf(p.y, -a, a), 0)) < k.radius + r
	return false


## A terrain that alone uses more than TERRAIN_SHARE_MAX of the triangle budget.
static func terrain_warnings(scene: Dictionary, budget_tris: int) -> PackedStringArray:
	var out := PackedStringArray()
	var t: Variant = scene.get("terrain", {})
	if not (t is Dictionary) or String(t.get("type", "none")) in ["none", "flat"]:
		return out
	var budget := budget_tris if budget_tris > 0 else TARGET_TRIS
	var res := int(t.get("resolution", 129))
	var tris := terrain_triangles(res)
	if tris <= budget * TERRAIN_SHARE_MAX:
		return out
	var best := suggested_resolution(budget)
	var sz: Array = t.get("size", [256, 256]) if t.get("size") is Array else [256, 256]
	var span := maxf(float(sz[0]), float(sz[1])) if sz.size() == 2 else 256.0
	out.append("terrain resolution %d draws %d triangles, %d%% of the %d triangle budget, before any object. Use \"resolution\": %d (%d triangles, %d%%, a vertex every %.1f m); shape detail belongs in the heightmap, not the grid." % [
		res, tris, roundi(100.0 * tris / budget), budget, best, terrain_triangles(best), roundi(100.0 * terrain_triangles(best) / budget), span / (best - 1)])
	return out


static func terrain_triangles(res: int) -> int:
	return 2 * (res - 1) * (res - 1) if res > 1 else 0


## The largest 2^n + 1 resolution whose terrain fits in TERRAIN_SHARE_SUGGEST of the budget (at least 17).
static func suggested_resolution(budget_tris: int) -> int:
	var r := 17
	while terrain_triangles((r - 1) * 2 + 1) <= budget_tris * TERRAIN_SHARE_SUGGEST:
		r = (r - 1) * 2 + 1
	return r


## Colours that light past white: albedo x (sun facing it + ambient) x exposure, per channel,
## against the linear tonemap the builder uses (white is 1.0, nothing rolls off).
static func tonemap_warnings(scene: Dictionary) -> PackedStringArray:
	var out := PackedStringArray()
	var light := scene_light(scene)
	if light.r <= 0.0 and light.g <= 0.0 and light.b <= 0.0:
		return out
	var seen := {}    # "where|#hex" -> [names]
	var order: Array = []
	var add := func(where: String, colour: Variant, name: String) -> void:
		if not (colour is String) or String(colour) == "" or not Color.html_is_valid(String(colour)):
			return
		var k := where + "|" + String(colour).to_lower()
		if not seen.has(k):
			seen[k] = []
			order.append(k)
		(seen[k] as Array).append(name)
	var t: Variant = scene.get("terrain", {})
	if t is Dictionary and String(t.get("type", "none")) != "none":
		var layers: Variant = t.get("materials", [])
		if layers is Array:
			for i in (layers as Array).size():
				var l: Variant = layers[i]
				if l is Dictionary and not l.has("texture"):
					add.call("terrain material", l.get("color"), String(l.get("name", "#%d" % i)))
	var water: Variant = scene.get("water", [])
	if water is Array:
		for i in (water as Array).size():
			var w: Variant = water[i]
			if w is Dictionary:
				add.call("water", w.get("color"), _wid(w, i))
	var prims: Variant = scene.get("primitives", [])
	if prims is Array:
		for i in (prims as Array).size():
			var p: Variant = prims[i]
			if p is Dictionary and not p.get("unlit", false) and not p.has("texture"):
				add.call("primitive", p.get("color"), String(p.get("id", "%s_%d" % [p.get("shape", "?"), i])))
	for k in order:
		var where := String(k).get_slice("|", 0)
		var hex := String(k).get_slice("|", 1)
		var c := Color(hex)
		var lit := Color(c.srgb_to_linear().r * light.r, c.srgb_to_linear().g * light.g, c.srgb_to_linear().b * light.b)
		var peak := maxf(lit.r, maxf(lit.g, lit.b))
		if peak <= CLIP:
			continue
		var names: Array = seen[k]
		var who := ", ".join(names.slice(0, NAME_LIST)) + (" (+%d more)" % (names.size() - NAME_LIST) if names.size() > NAME_LIST else "")
		out.append("%s %s colour %s lights to %.2f under this sun and ambient: the linear tonemap clips it to flat white. Use %s (same hue, darker) or lower the sun energy, ambient energy or exposure." % [
			where, who, hex, peak, darker(c, CLIP_TARGET / peak)])
	return out


## Light reaching a surface that faces the sun: sun x energy + ambient, times exposure (linear RGB).
static func scene_light(scene: Dictionary) -> Color:
	var e: Dictionary = scene.get("environment", {}) if scene.get("environment") is Dictionary else {}
	var light := Color(0, 0, 0)
	var sun: Dictionary = e.get("sun", {}) if e.get("sun") is Dictionary else {}
	if sun.get("enabled", true):
		var up := 1.0
		if not sun.has("direction"):
			# the builder dims a sun below the horizon; at noon it is fully on
			var h := float(e.get("time_of_day", 12.0))
			var t := (h - 6.0) / 12.0 * PI
			up = clampf(sin(t) * sin(deg_to_rad(62.0)) * 4.0, 0.0, 1.0)
		var sc := _colour(sun.get("color"), Color("#fff4e0")).srgb_to_linear()
		var se := float(sun.get("energy", 1.0)) * up
		light = Color(sc.r * se, sc.g * se, sc.b * se)
	var amb: Dictionary = e.get("ambient", {}) if e.get("ambient") is Dictionary else {}
	var ae := float(amb.get("energy", 1.0))
	var ac: Color
	var sky: Dictionary = e.get("sky", {}) if e.get("sky") is Dictionary else {}
	var st := String(sky.get("type", "procedural"))
	if String(amb.get("source", "color")) == "sky" and st != "color":
		if st == "cubemap":
			ac = Color(0.5, 0.5, 0.5).srgb_to_linear() * float(sky.get("energy", 1.0))
		else:
			var top := _colour(sky.get("top_color"), Color("#3d6ea8")).srgb_to_linear()
			var hor := _colour(sky.get("horizon_color"), Color("#a9c3dc")).srgb_to_linear()
			ac = (top + hor) * 0.5 * float(sky.get("energy", 1.0))
	else:
		ac = _colour(amb.get("color"), Color("#808080")).srgb_to_linear()
	var x := float(e.get("exposure", 1.0))
	return Color((light.r + ac.r * ae) * x, (light.g + ac.g * ae) * x, (light.b + ac.b * ae) * x)


## Rooms nobody lit (an internal task): for each scene object whose model has a rooms sidecar
## (`assets building house` writes <model>.rooms.json beside the .glb), each room needs a
## point or spot light on its floor that reaches its centre at eye height; the sun and the
## ambient leave a room under a roof flat and dark. rooms_of(asset) -> the sidecar, {} if none.
static func room_light_warnings(scene: Dictionary, rooms_of: Callable) -> PackedStringArray:
	var out := PackedStringArray()
	var objs: Variant = scene.get("objects", [])
	if not (objs is Array):
		return out
	var lights: Array = []
	var ls: Variant = scene.get("lights", [])
	if ls is Array:
		for l in ls:
			if l is Dictionary and String(l.get("type", "")) in ["point", "spot"] and l.get("position") is Array:
				lights.append(l)
	for i in (objs as Array).size():
		var o: Variant = objs[i]
		if not (o is Dictionary) or not (o.get("asset") is String):
			continue
		var info: Variant = rooms_of.call(String(o.asset))
		if not (info is Dictionary) or not ((info as Dictionary).get("rooms") is Array):
			continue
		var xf := _placed_object(o)
		var storey := float(info.get("storey", 3.0))
		var dark: Array = []
		var fix := ""
		for room in info.rooms:
			if not (room is Dictionary) or not (room.get("rect") is Array) or (room.rect as Array).size() != 4:
				continue
			var r: Array = room.rect
			var fy := 0.15 + float(room.get("floor", 0)) * storey   # the generator's ground slab is 0.15 m
			var eye := xf * Vector3((float(r[0]) + float(r[2])) / 2.0, fy + 1.5, (float(r[1]) + float(r[3])) / 2.0)
			var lo := (xf * Vector3(0, fy, 0)).y
			var hi := (xf * Vector3(0, fy + storey, 0)).y
			var lit := false
			for l in lights:
				var p := _v3(l.position)
				if p.y >= lo and p.y <= hi and p.distance_to(eye) <= float(l.get("range", 10.0)):
					lit = true
					break
			if not lit:
				dark.append(String(room.get("name", "?")))
				if fix == "":
					var top := xf * Vector3((float(r[0]) + float(r[2])) / 2.0, fy + storey - 0.55, (float(r[1]) + float(r[3])) / 2.0)
					fix = "{\"type\": \"point\", \"position\": [%.2f, %.2f, %.2f], \"color\": \"#ffdcb0\", \"energy\": 1.2, \"range\": 6}" % [top.x, top.y, top.z]
		if dark.is_empty():
			continue
		var who := ", ".join(dark.slice(0, NAME_LIST)) + (" (+%d more)" % (dark.size() - NAME_LIST) if dark.size() > NAME_LIST else "")
		var hint := ""
		if info.get("lights") is Array and not (info.lights as Array).is_empty():
			hint = " The house's %d lights are in %s (\"lights\", in the model's own space: add the object's position and turn them with its rotation)." % [(info.lights as Array).size(), String(o.asset).get_basename() + ".rooms.json"]
		out.append("objects[%d] %s: %d of %d rooms have no light on their floor reaching them (%s); under a roof they render flat and dark. Add a light per dark room to scene.lights, e.g. %s.%s" % [
			i, String(o.asset), dark.size(), (info.rooms as Array).size(), who, fix, hint])
	return out


## rooms_of for room_light_warnings: reads <folder>/<model without .glb>.rooms.json.
static func rooms_reader(folder: String) -> Callable:
	return func(asset: String) -> Variant:
		if folder == "" or asset.contains(".."):
			return {}
		var side := folder.path_join(asset.get_basename() + ".rooms.json")
		if not FileAccess.file_exists(side):
			return {}
		return JSON.parse_string(FileAccess.get_file_as_string(side))


## An object's placement as the builder makes it: rotation in degrees (YXZ), scale a number or [x, y, z].
static func _placed_object(o: Dictionary) -> Transform3D:
	var r := _v3(o.get("rotation", [0, 0, 0]))
	var s: Variant = o.get("scale", 1.0)
	var sv := _v3(s) if s is Array else Vector3.ONE * float(s)
	var b := Basis.from_euler(Vector3(deg_to_rad(r.x), deg_to_rad(r.y), deg_to_rad(r.z)), EULER_ORDER_YXZ).scaled_local(sv)
	return Transform3D(b, _v3(o.get("position", [0, 0, 0])))


## c with its linear channels scaled by k, as #rrggbb.
static func darker(c: Color, k: float) -> String:
	var l := c.srgb_to_linear()
	return "#" + Color(l.r * k, l.g * k, l.b * k).linear_to_srgb().to_html(false)


static func _over_water(w: Dictionary, p: Vector3) -> bool:
	var sz: Variant = w.get("size")
	if not (sz is Array) or (sz as Array).size() != 2:
		return false
	var c := _v3(w.get("position", [0, 0, 0]))
	return absf(p.x - c.x) <= float(sz[0]) * 0.5 and absf(p.z - c.z) <= float(sz[1]) * 0.5


static func _wid(w: Dictionary, i := -1) -> String:
	return String(w.get("id", str(i) if i >= 0 else "?"))


static func _colour(s: Variant, def: Color) -> Color:
	return Color(String(s)) if s is String and Color.html_is_valid(String(s)) else def


static func _v3(a: Variant) -> Vector3:
	if a is Array and (a as Array).size() == 3:
		return Vector3(float(a[0]), float(a[1]), float(a[2]))
	return Vector3.ZERO


static func _xyz(p: Vector3) -> String:
	return "(%.2f, %.2f, %.2f)" % [p.x, p.y, p.z]
