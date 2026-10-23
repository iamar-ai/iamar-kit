extends SceneTree
## Data-only admission for the disabled prepared-tree adapter candidate.
## The trusted Node helper has already captured a bounded non-symlink tree,
## checked canonical schemas and rejected all external GLB resource forms.
## Never calls WorldPackage.open, an archive API, a decoder or a renderer.
## This is an additional gate, not a substitute for ordinary all-tier validation.

const MAX_MANIFEST_BYTES := 1 << 20
const MAX_PACKAGE_BYTES := 50 << 20


func _initialize() -> void:
	var args := KitLoop.user_args()
	if args.size() != 1 or not args[0].is_absolute_path() or not DirAccess.dir_exists_absolute(args[0]):
		printerr("ERROR tier-preflight requires one existing private absolute folder")
		quit(2)
		return
	# Deliberately use the folder-only scanner, never WorldSource.open's
	# folder/archive dispatch. The parent owns this private captured directory.
	var source := WorldSource.new()
	source.path = args[0]
	source._open_folder(args[0])
	var errors := _check(source)
	for error in errors:
		printerr("ERROR " + error)
	if errors.is_empty():
		print("TIER_PREFLIGHT_V1 OK")
	quit(0 if errors.is_empty() else 1)


static func _check(source: WorldSource) -> PackedStringArray:
	var errors := PackedStringArray()
	if not source.ok():
		return PackedStringArray([source.error])
	if source.total_bytes() > MAX_PACKAGE_BYTES:
		return PackedStringArray(["tier source exceeds the prepared-tree byte ceiling"])
	var manifest = WorldFormat.parse_json(source.read(WorldFormat.MANIFEST), "manifest", errors, MAX_MANIFEST_BYTES)
	if not errors.is_empty():
		return errors
	errors.append_array(WorldFormat.validate_manifest(manifest))
	if not errors.is_empty():
		return errors
	if not manifest.has("tiers") or not (manifest.tiers is Dictionary):
		return PackedStringArray(["tier source needs an explicit valid tiers declaration"])
	if not manifest.get("scripts", []).is_empty() or not manifest.get("reused", []).is_empty():
		return PackedStringArray(["scripts and external reused assets are not in the prepared-tree lane"])
	var scene_path := String(manifest.get("scene", "scene.json"))
	if not WorldFormat.is_safe_path(scene_path) or not source.has(scene_path):
		return PackedStringArray(["tier source scene is missing or unsafe"])
	var scene = WorldFormat.parse_json(source.read(scene_path), "scene", errors)
	if not errors.is_empty():
		return errors
	errors.append_array(WorldFormat.validate_scene(scene))
	if not errors.is_empty():
		return errors
	# These APIs are the ordinary native semantic rules, not a parallel subset.
	errors.append_array(WorldFormat.check_features(manifest)[0])
	errors.append_array(WorldFormat.check_references(manifest, scene, source.has)[0])
	for tier in WorldTiers.declared(manifest):
		var budgets := WorldTiers.budgets(manifest, tier)
		errors.append_array(WorldFormat.check_declared(budgets))
		var visible: Dictionary = scene.duplicate(true)
		for section in ["objects", "primitives"]:
			if visible.has(section):
				visible[section] = (visible[section] as Array).filter(func(entry: Dictionary) -> bool: return WorldTiers.shows(entry, tier))
		errors.append_array(WorldFormat.check_actual(budgets, {"objects": WorldFormat.count_objects(visible), "lights": WorldFormat.count_lights(visible)}))
	if not errors.is_empty():
		return errors
	# Check all carried variants, including shadowed/unreferenced top sources.
	# Header/index/buffer/embedded-image checks happen before any Godot decoder.
	var media_texture_bytes := 0
	for path in source.list():
		if path.ends_with(".glb"):
			var result := MediaGuard.check_glb(source.read(path), {"max_edge": int(WorldFormat.LIMITS.texture_size), "max_texture_bytes": int(WorldFormat.LIMITS.texture_bytes)})
			if not result.ok:
				errors.append("%s: %s" % [path, result.error])
			else:
				media_texture_bytes += int(result.texture_bytes)
		elif path.ends_with(".png") or path.ends_with(".jpg") or path.ends_with(".jpeg"):
			var bytes := source.read(path)
			var problem := MediaGuard.check_image(bytes, int(WorldFormat.LIMITS.texture_size))
			if problem != "":
				errors.append("%s: %s" % [path, problem])
			else:
				var info := MediaGuard.image_info(bytes)
				media_texture_bytes += int(info.width) * int(info.height) * 4
		elif path.ends_with(".ogg"):
			var problem := MediaGuard.check_ogg(source.read(path))
			if problem != "":
				errors.append("%s: %s" % [path, problem])
		elif path.ends_with(".gltf"):
			errors.append("text glTF is outside the prepared-tree lane")
		if media_texture_bytes > int(WorldFormat.LIMITS.texture_bytes):
			errors.append("all carried tier media exceed the texture-memory ceiling")
			break
		if errors.size() >= 50:
			break
	return errors
