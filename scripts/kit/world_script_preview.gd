extends RefCounted
## Playerless kit preview only. The live visitor PackageScriptHost is separate.
## Package bytes and existing WorldScript budgets/API remain the sandbox boundary.
## KV is memory-only; normal Wasm compilation may still use its compiled-code cache.


## Variant boundaries let stale/freed objects reach these checks instead of
## failing native-typed argument validation before the guard can run.
static func attach(pkg: Variant, world: Variant, host: Variant) -> Dictionary:
	var scripts: Array = []
	var source: Variant = pkg.source if is_instance_valid(pkg) and pkg is WorldPackage else null
	var current := func() -> bool:
		return is_instance_valid(pkg) and pkg is WorldPackage and pkg.ok \
			and is_instance_valid(source) and pkg.source == source \
			and is_instance_valid(host) and host is Node and host.is_inside_tree() and not host.is_queued_for_deletion() \
			and is_instance_valid(world) and world is Node3D and world.is_inside_tree() and not world.is_queued_for_deletion() \
			and pkg.root == world and world.get_parent() == host
	if not current.call():
		return _failed(scripts, "The preview package or world is no longer current.")
	var entries: Array = pkg.manifest.get("scripts", [])
	if entries.is_empty():
		return {"ok": true, "scripts": scripts, "current": current, "error": ""}
	if not WorldScript.available():
		return _failed(scripts, "The package declares scripts, but the WebAssembly runtime is unavailable.")
	for entry in entries:
		if not current.call():
			return _failed(scripts, "The preview package or world changed before script attachment.")
		var rel := String(entry.get("path", "")) if entry is Dictionary else String(entry)
		if rel == "" or not source.has(rel):
			return _failed(scripts, "A declared preview script is missing from the package.")
		var ws := WorldScript.new()
		scripts.append(ws)
		ws.world_id = pkg.id
		ws.script_path = pkg.id + "/" + rel
		ws.kv_path = ""
		ws.asset_root = "package:"
		ws.asset_reader = func(path: String) -> PackedByteArray:
			return source.read(path) if current.call() and source.has(path) else PackedByteArray()
		if pkg.ground:
			ws.ground = func(x: float, z: float) -> float:
				return pkg.ground.height_at(x, z, 500.0) if current.call() else 0.0
		# No players, Net bridge, notes or audio services are registered.
		# Default local is_authority() is unchanged; it grants no visitor identity.
		world.add_child(ws)
		if not current.call() or not is_instance_valid(ws) or ws.is_queued_for_deletion():
			return _failed(scripts, "The preview world changed during script attachment.")
		var bytes: PackedByteArray = source.read(rel)
		if not current.call():
			return _failed(scripts, "The preview package changed while reading a script.")
		var budgets: Dictionary = pkg.manifest.get("budgets", {})
		var api := String(pkg.manifest.get("api_version", WorldApi.VERSION))
		if not ws.load_bytes(bytes, budgets, api):
			return _failed(scripts, "A declared preview script could not load.")
		var problem := check(scripts, current, world)
		if problem != "":
			return _failed(scripts, problem)
		ws.start()
		problem = check(scripts, current, world)
		if problem != "":
			return _failed(scripts, problem)
	return {"ok": true, "scripts": scripts, "current": current, "error": ""}


## Called again before each preview/performance sample. A lost script is a
## failure, not an absent cost. Initialization uses start()'s void contract.
static func check(scripts: Array, current: Callable, world: Variant) -> String:
	if not current.is_valid() or not current.call():
		return "The preview package or world is no longer current."
	for ws in scripts:
		if not is_instance_valid(ws) or not ws is WorldScript:
			return "A declared preview script was removed."
		if ws.is_queued_for_deletion() or not ws.is_inside_tree() or ws.get_parent() != world:
			return "A declared preview script is no longer attached."
		if not ws.loaded or ws.loading or ws.disabled or not ws.errors.is_empty():
			return "A declared preview script failed, trapped or stopped."
	return ""


## Only the script instances created by this attachment are retired.
static func dispose(scripts: Array) -> void:
	for ws in scripts:
		if not is_instance_valid(ws) or not ws is WorldScript:
			continue
		ws.stop()
		if is_instance_valid(ws):
			ws.free()


static func _failed(scripts: Array, message: String) -> Dictionary:
	dispose(scripts)
	return {"ok": false, "scripts": [], "current": Callable(), "error": message}
