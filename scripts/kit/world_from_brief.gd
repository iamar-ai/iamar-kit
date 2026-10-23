extends RefCounted
## `iamar-world new <folder> --from-brief brief.json` (an internal task): turns an interview brief
## (kit/interview/PROTOCOL.md section 6) into a blocked-out scene on one of the starter
## templates: a house from its room list (KitHouseRooms) on dry, level ground with a
## foundation and front steps, garden beds, a plaza, the spawn a few metres in front of the
## front door facing the house, the portal home beside it and a path from the door, with
## the brief's time of day and budgets. Docs: docs/WORLD_FROM_BRIEF.md.
##
## plan(brief) reads the brief; apply(scene, manifest, plan, house, ground) changes the
## scaffolded scene.json/manifest.json dictionaries in place. Plain Godot only (no browser
## classes), so a throwaway project can test it (tests/kit_from_brief/run.sh).

## Zones the planner knows. house/garden/plaza are placed here; beach/sea/forest/town pick
## the template; lake/river/island are left to `iamar-world terrain` (a NOTE says so).
const ZONES := ["house", "beach", "sea", "garden", "plaza", "forest", "town", "interior", "lake", "river", "island"]
const WORDS := {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
const HOUSE_STYLES := ["beach", "modern", "plaster", "stone"]
## Where the house stands per template: the front door faces `door` (world xz), the
## door's line sits at `front` metres on the axis it faces, and `dry` is the lowest
## ground height the whole footprint must clear (beach: off the sand, onto the dunes).
const SITES := {
	"beach": {"door": Vector2(0, -1), "front": 0.0, "dry": 1.45},
	"meadow": {"door": Vector2(0, 1), "front": -6.0, "dry": -100.0},
	"forest": {"door": Vector2(0, 1), "front": -1.0, "dry": -100.0},
	"town": {"door": Vector2(0, 1), "front": -14.5, "dry": -100.0},
}
const CLEAR := 2.0        # template entries this close to the house footprint are removed
const SPAWN_AHEAD := 8.0  # metres in front of the door
const SPAWN_SIDE := 3.0   # and to one side, for a three-quarter view of the house


static func _count(text: String, noun: String) -> int:
	var re := RegEx.create_from_string("\\b(\\d+|a|an|one|two|three|four|five|six)[\\s-]*" + noun)
	var m := re.search(text)
	if m == null:
		return 0
	var w := m.get_string(1)
	return int(w) if w.is_valid_int() else int(WORDS.get(w, 0))


static func _has(text: String, words: Array) -> bool:
	for w in words:
		if RegEx.create_from_string("\\b" + w + "\\b").search(text) != null:
			return true
	return false


## The brief -> {template, zones, house: {rooms, style, floors?, roof?} or {}, time_of_day
## (-1 = keep the template's), budgets, id, title, notes} or {error}.
static func plan(brief: Variant, template_override := "") -> Dictionary:
	if not brief is Dictionary:
		return {"error": "the brief must be a JSON object (kit/interview/PROTOCOL.md section 6)"}
	var b: Dictionary = brief
	var vision := String(b.get("vision", "")).to_lower()
	var kind := String(b.get("type", ""))
	var extra: Array = b.get("extra_types", []) if b.get("extra_types") is Array else []
	var notes := PackedStringArray()
	var zones: Array[String] = []
	var house := {}
	var layout: Variant = b.get("layout", {})
	if not layout is Dictionary:
		return {"error": "brief.layout must be an object with a \"zones\" list"}
	if (layout as Dictionary).has("zones"):
		var listed: Variant = layout.zones
		if not listed is Array or (listed as Array).is_empty():
			return {"error": "brief.layout.zones must be a non-empty list, e.g. [\"house\", \"beach\", \"sea\"]"}
		for z in listed:
			var zd: Dictionary = z if z is Dictionary else {"kind": z}
			var k := String(zd.get("kind", "")).to_lower()
			if not k in ZONES:
				return {"error": "brief.layout.zones: unknown zone \"%s\" (use %s)" % [k, ", ".join(ZONES)]}
			if not k in zones:
				zones.append(k)
			if k == "house":
				for key in ["rooms", "style", "floors", "roof"]:
					if zd.has(key):
						house[key] = String(zd[key])
				house["_listed"] = true
	elif vision == "":
		return {"error": "the brief has no vision and no layout.zones: nothing to lay out"}
	else:
		# No layout: read the zones from the one-sentence vision and the world type.
		if _has(vision, ["beach", "beaches", "shore", "seaside", "coast", "coastal"]):
			zones.append_array(["beach", "sea"])
		elif _has(vision, ["sea", "ocean", "bay", "harbour", "harbor"]):
			zones.append("sea")
		if _has(vision, ["house", "home", "cottage", "villa", "cabin", "bungalow", "bedroom", "bedrooms"]):
			zones.append("house")
		if _has(vision, ["garden", "gardens", "yard", "backyard", "orchard"]):
			zones.append("garden")
		if _has(vision, ["plaza", "square", "market", "marketplace"]):
			zones.append("plaza")
		if kind == "nature" or "nature" in extra or _has(vision, ["forest", "woods", "woodland", "grove"]):
			zones.append("forest")
		if kind in ["town", "shop", "social", "event"]:
			zones.append("town")
		if kind == "interior" and not "house" in zones:
			zones.append("interior")
		for k in ["lake", "river", "island"]:
			if _has(vision, [k]):
				zones.append(k)
		if zones.is_empty():
			notes.append("no zones found in the vision; starting from the meadow (add brief.layout.zones to choose)")
	# The template: water first, then the world type.
	var template := "meadow"
	if "beach" in zones or "sea" in zones:
		template = "beach"
	elif "forest" in zones:
		template = "forest"
	elif "town" in zones or "plaza" in zones:
		template = "town"
	elif "interior" in zones:
		template = "interior"
	if template_override != "":
		template = template_override
	if "house" in zones:
		if template == "interior":
			notes.append("the interior template is one room; the house was not built (drop --template interior or the house zone)")
			house = {}
		else:
			if not house.has("rooms"):
				var beds := _count(vision, "bed(room)?s?\\b")
				var baths := _count(vision, "bath(room)?s?\\b")
				beds = clampi(beds if beds > 0 else 2, 1, 8)
				baths = clampi(baths if baths > 0 else (2 if beds >= 3 else 1), 1, 4)
				var rooms := "bedroom:%d,living,kitchen" % beds
				if _has(vision, ["dining"]):
					rooms += ",dining"
				if _has(vision, ["study", "office"]):
					rooms += ",study"
				if _has(vision, ["laundry", "utility"]):
					rooms += ",laundry"
				house.rooms = rooms + ",bath:%d" % baths
			if not house.has("style"):
				if _has(vision, ["modern", "contemporary", "minimalist"]):
					house.style = "modern"
				else:
					house.style = {"beach": "beach", "forest": "stone"}.get(template, "plaster")
			if not String(house.style) in HOUSE_STYLES:
				return {"error": "house style \"%s\" (use %s)" % [house.style, ", ".join(HOUSE_STYLES)]}
	else:
		house = {}
	house.erase("_listed")
	for k in ["lake", "river", "island"]:
		if k in zones:
			notes.append("%s: not blocked out here; run `iamar-world terrain %s <folder>` first on a fresh copy, then place the house by hand (the terrain helper moves the spawn)" % [k, k])
	if ("sea" in zones or "beach" in zones) and template != "beach":
		notes.append("sea/beach asked for on the %s template: run `iamar-world terrain coast <folder>` for water" % template)
	if "plaza" in zones and template in ["beach", "forest"]:
		notes.append("plaza: the %s has no level ground beside the house for a paved square; add one by hand" % template)
	var feats: Array = b.get("features", []) if b.get("features") is Array else []
	for f in feats:
		if f is Dictionary and String(f.get("kind", "")) in ["npc", "quest", "script", "ui"]:
			notes.append("feature %s (%s): not blocked out; add it after the greybox (kit/AGENT_KIT.md)" % [f.get("id", "?"), f.kind])
	if not b.get("approval") is Dictionary:
		notes.append("the brief has no approval yet: show the user the greybox before building further")
	var tod := -1.0
	var mood: Dictionary = b.get("mood", {}) if b.get("mood") is Dictionary else {}
	var t := String(mood.get("time", "")).to_lower()
	if _has(t, ["golden", "sunset", "evening", "dusk"]):
		tod = 17.5
	elif _has(t, ["morning", "dawn", "sunrise"]):
		tod = 9.0
	elif _has(t, ["noon", "midday"]):
		tod = 12.5
	elif _has(t, ["afternoon"]):
		tod = 15.0
	elif _has(t, ["night", "midnight"]):
		notes.append("night: kept the template's daylight; a night world needs its own lights (add them, then set environment.time_of_day)")
	var budgets := {}
	var bb: Dictionary = b.get("budgets", {}) if b.get("budgets") is Dictionary else {}
	for k in ["triangles", "texture_size", "texture_bytes"]:
		if (bb.get(k) is int or bb.get(k) is float) and int(bb[k]) > 0:
			budgets[k] = int(bb[k])
	var id := ""
	var title := ""
	var conn: Dictionary = b.get("connections", {}) if b.get("connections") is Dictionary else {}
	var name := String(conn.get("name", "")).trim_prefix("iamar://").get_slice("/", 0)
	if name != "":
		var clean := ""
		for ch in name.to_lower().replace("-", "_").replace(" ", "_"):
			if (ch >= "a" and ch <= "z") or (ch >= "0" and ch <= "9") or ch == "_":
				clean += ch
		id = clean.substr(0, 64)
		title = name.replace("-", " ").replace("_", " ").capitalize()
	return {"template": template, "zones": zones, "house": house, "time_of_day": tod,
		"budgets": budgets, "id": id, "title": title, "notes": notes}


static func _r(v: float) -> float:
	return snappedf(v, 0.01)


static func _xz(a: Variant) -> Vector2:
	if a is Array and (a as Array).size() >= 3:
		return Vector2(float(a[0]), float(a[2]))
	if a is Array and (a as Array).size() == 2:
		return Vector2(float(a[0]), float(a[1]))
	return Vector2(INF, INF)


static func _box(id: String, size: Vector3, pos: Vector3, color: String, collide := true, yaw := 0.0) -> Dictionary:
	var p := {"id": id, "shape": "box", "size": [_r(size.x), _r(size.y), _r(size.z)],
		"position": [_r(pos.x), _r(pos.y), _r(pos.z)], "color": color, "collision": "box" if collide else "none"}
	if yaw != 0.0:
		p.rotation = [0, _r(yaw), 0]
	return p


## Changes scene and manifest in place. house = {} or {"asset": "assets/house.glb",
## "info": <KitHouseRooms info>}; ground = Callable(x: float, z: float) -> float (the
## template's terrain height). Returns the report lines (PLACED ... / NOTE ...).
static func apply(scene: Dictionary, manifest: Dictionary, p: Dictionary, house: Dictionary, ground: Callable) -> PackedStringArray:
	var lines := PackedStringArray()
	var env: Dictionary = scene.get("environment", {})
	if float(p.get("time_of_day", -1.0)) >= 0.0:
		env.time_of_day = p.time_of_day
		scene.environment = env
	var budgets: Dictionary = manifest.get("budgets", {})
	for k in p.get("budgets", {}):
		# never raise a scaffold budget: the starter's are the ones known to validate
		if budgets.has(k):
			budgets[k] = mini(int(budgets[k]), int(p.budgets[k]))
	var features: Variant = manifest.get("features", [])
	var template := String(p.template)
	if house.is_empty() or not SITES.has(template):
		if not house.is_empty():
			lines.append("NOTE the %s template has no site for a house; place assets/house.glb by hand" % template)
		return lines
	var info: Dictionary = house.info
	var length := float(info.size[0])
	var depth := float(info.size[1])
	var site: Dictionary = SITES[template]
	var face: Vector2 = site.door
	# the model's front door faces -x; turn it to face the site's door direction
	var yaw := rad_to_deg(atan2(face.x, face.y)) + 90.0
	yaw = wrapf(yaw, -180.0, 180.0)
	var basis := Basis(Vector3.UP, deg_to_rad(yaw))
	var fwd := Vector3(face.x, 0, face.y)
	var side := fwd.cross(Vector3.UP)
	# the door line sits at `front` on the facing axis; then the house slides back (away
	# from where the door faces) until its whole footprint clears the site's dry height
	var centre := fwd * float(site.front) - fwd * (length * 0.5)
	var ys := _ground_range(ground, centre, basis, length, depth)
	var slid := 0
	while ys.x < float(site.dry) and slid < 200:
		centre -= fwd * 0.5
		slid += 1
		ys = _ground_range(ground, centre, basis, length, depth)
	if slid > 0:
		centre -= fwd * 2.0   # a strip of dry ground in front of the door
		ys = _ground_range(ground, centre, basis, length, depth)
	var y := ys.y + 0.02
	var pos := Vector3(centre.x, y, centre.z)
	var objects: Array = scene.get("objects", [])
	objects.append({"id": "house", "asset": String(house.asset), "position": [_r(pos.x), _r(pos.y), _r(pos.z)],
		"rotation": [0, _r(yaw), 0], "collision": "mesh"})
	scene.objects = objects
	if features is Array and not "objects" in features:
		features.append("objects")
	var door_m: Array = info.front_door
	var door := pos + basis * Vector3(float(door_m[0]), 0, float(door_m[2]))
	door.y = y + 0.15
	# remove starter shapes and portals the house now stands on
	var half := Vector2(depth * 0.5 if absf(face.y) > 0.5 else length * 0.5, length * 0.5 if absf(face.y) > 0.5 else depth * 0.5)
	var removed := PackedStringArray()
	for sec in ["primitives", "portals", "creatures"]:
		var keep: Array = []
		for e in scene.get(sec, []):
			var at := _xz(e.get("position"))
			if absf(at.x - pos.x) < half.x + CLEAR and absf(at.y - pos.z) < half.y + CLEAR:
				removed.append(String(e.get("id", sec)))
				if sec == "portals":
					keep.append(e)   # moved below, never dropped
				continue
			keep.append(e)
		if scene.has(sec):
			scene[sec] = keep
	var prims: Array = scene.get("primitives", [])
	# a foundation under the slab where the ground falls away, and front steps
	if ys.y - ys.x > 0.05:
		var fh := ys.y - ys.x + 0.4
		var size := Vector3(half.x * 2.0 + 0.3, fh, half.y * 2.0 + 0.3)
		prims.append(_box("house_foundation", size, Vector3(pos.x, y + 0.1 - fh * 0.5, pos.z), "#6e665a"))
	var step_ground := float(ground.call(door.x + fwd.x * 1.6, door.z + fwd.z * 1.6))
	var drop := door.y - step_ground
	if drop > 0.2:
		var n := clampi(ceili(drop / 0.18), 1, 8)
		for i in n:
			var top := door.y - (i + 1) * drop / (n + 1)
			var c := door + fwd * (1.0 + 0.3 * i + 0.15)
			var h := top - (step_ground - 0.2)
			prims.append(_box("front_step_%d" % i, Vector3(1.6, h, 0.3) if absf(face.y) > 0.5 else Vector3(0.3, h, 1.6),
				Vector3(c.x, top - h * 0.5, c.z), "#8a7f70"))
	if "garden" in p.zones:
		for s: float in [-1.0, 1.0]:
			var g := pos + side * s * (half.x + 2.5) + fwd * (half.y * 0.2)
			var gy := float(ground.call(g.x, g.z))
			prims.append(_box("garden_bed_%d" % int(s + 1), Vector3(1.6, 0.35, 4.0) if absf(face.y) > 0.5 else Vector3(4.0, 0.35, 1.6),
				Vector3(g.x, gy + 0.12, g.z), "#4f3a2a", false))
			for k in 3:
				var f := g + fwd * (k - 1) * 1.2
				prims.append({"id": "flowers_%d_%d" % [int(s + 1), k], "shape": "sphere", "radius": 0.45,
					"position": [_r(f.x), _r(gy + 0.55), _r(f.z)], "scale": [1.0, 0.7, 1.0],
					"color": ["#a8484e", "#c8a040", "#7a5aa0"][k], "collision": "none"})
	if "plaza" in p.zones and template == "meadow":
		var c := pos + side * (half.x + 12.0)
		prims.append(_box("plaza", Vector3(12, 0.12, 12), Vector3(c.x, float(ground.call(c.x, c.z)) + 0.06, c.z), "#8a8274"))
		prims.append({"id": "plaza_fountain", "shape": "cylinder", "radius": 1.2, "height": 0.7,
			"position": [_r(c.x), _r(float(ground.call(c.x, c.z)) + 0.47), _r(c.z)], "color": "#7e786e", "collision": "box"})
		lines.append("PLACED plaza at %s" % [[_r(c.x), _r(c.z)]])
	scene.primitives = prims
	# the spawn in front of the door, facing the house
	var sp := door + fwd * SPAWN_AHEAD + side * SPAWN_SIDE
	var sy := float(ground.call(sp.x, sp.z)) + 0.2
	var look := pos - sp
	var spawn_yaw := _r(rad_to_deg(atan2(-look.x, -look.z)))
	var spawns: Array = scene.get("spawn_points", [])
	var spawn_id := String(manifest.get("spawn", "spawn"))
	var placed := false
	for sp_e in spawns:
		if String(sp_e.get("id", "")) == spawn_id:
			sp_e.position = [_r(sp.x), _r(sy), _r(sp.z)]
			sp_e.yaw = spawn_yaw
			placed = true
	if not placed:
		spawns.append({"id": spawn_id, "position": [_r(sp.x), _r(sy), _r(sp.z)], "yaw": spawn_yaw})
	scene.spawn_points = spawns
	# the portal home: kept where the template put it unless the house took its place
	for portal in scene.get("portals", []):
		if String(portal.get("id", "")) in removed:
			var pp := door + fwd * (SPAWN_AHEAD + 2.0) - side * 5.0
			portal.position = [_r(pp.x), _r(float(ground.call(pp.x, pp.z))), _r(pp.z)]
			portal.yaw = spawn_yaw
			removed.remove_at(removed.find(String(portal.id)))
			lines.append("PLACED portal %s at %s (moved off the house site)" % [portal.id, portal.position])
	# a path from the front door out to the spawn and on (NPCs walk paths)
	var out := door + fwd * (SPAWN_AHEAD + 6.0)
	var paths: Array = scene.get("paths", [])
	paths.append({"id": "front_path", "points": [[_r(door.x), _r(door.z)], [_r(sp.x - side.x * SPAWN_SIDE), _r(sp.z - side.z * SPAWN_SIDE)], [_r(out.x), _r(out.z)]]})
	scene.paths = paths
	if features is Array and not "paths" in features:
		features.append("paths")
	lines.append("PLACED house %s at %s yaw %s, front door %s, %d floor(s), %d rooms, %d triangles" % [house.asset,
		[_r(pos.x), _r(pos.y), _r(pos.z)], _r(yaw), [_r(door.x), _r(door.y), _r(door.z)], int(info.floors),
		(info.rooms as Array).size(), int(info.triangles)])
	lines.append("PLACED spawn %s at %s yaw %s facing the house" % [spawn_id, [_r(sp.x), _r(sy), _r(sp.z)], spawn_yaw])
	if not removed.is_empty():
		lines.append("NOTE removed starter shapes on the house site: %s" % ", ".join(removed))
	lines.append("NOTE the house is unfurnished and unlit inside: furnish it from %s (catalogue, an internal task) and add room lights" % (String(house.asset).get_basename() + ".rooms.json"))
	return lines


## Lowest and highest ground under the rotated footprint (x = min, y = max), 1 m grid.
static func _ground_range(ground: Callable, centre: Vector3, basis: Basis, length: float, depth: float) -> Vector2:
	var lo := INF
	var hi := -INF
	var nx := ceili(length) + 1
	var nz := ceili(depth) + 1
	for i in nx + 1:
		for j in nz + 1:
			var m := Vector3(-length * 0.5 + length * i / nx, 0, -depth * 0.5 + depth * j / nz)
			var w := centre + basis * m
			var h := float(ground.call(w.x, w.z))
			lo = minf(lo, h)
			hi = maxf(hi, h)
	return Vector2(lo, hi)
