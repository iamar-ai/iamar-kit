extends SceneTree
## Bake the city's painted look into the catalogue's props (kit/catalog/assets/props/),
## which import_city_models.py copies from the iamar-models mesh archive (not public) with only their look as
## vertex colour (pattern code in the vertex alpha). painted_baker.gd runs the city
## shader's colour logic into one texture atlas per file; triangles are unchanged
## (an internal task). The furniture is baked the same way by export_city_pieces.gd itself.
##
## Run after the import, from an the iamar browser source (not public) checkout (headless; it reads the painted
## library assets/masterplan/textures/mp_library.png from it):
##   godot --headless --path <iamar checkout> -s <iamar-kit>/kit/catalog/assets/bake_painted.gd
##   godot ... -s .../bake_painted.gd -- props/well.glb props/bench.glb   (only these)
##   godot ... -s .../bake_painted.gd -- --library <path to mp_library.png> ...
## It bakes every props/ file whose bytes are still the copy recorded in
## sources/city_models.json (sha256), leaves files it already baked, and writes the record
## sources/painted_bake.json (source and baked sha256, atlas, density, patterns per file).
## Then fold it into the rows and rebuild the catalogue:
##   python3 kit/catalog/assets/import_city_models.py --baked
##   python3 kit/catalog/catalog.py build
## (import_city_models.py --check fails while a prop is still flat vertex colour.)

const LIBRARY := "res://assets/masterplan/textures/mp_library.png"
const BAKER := "painted_baker.gd"

var _kit_dir := ""
var _fails := 0


func _initialize() -> void:
	var here := (get_script() as Script).resource_path.get_base_dir()
	_kit_dir = here.get_base_dir().get_base_dir()
	if OS.get_environment("IAMAR_KIT_ROOT") != "":
		_kit_dir = OS.get_environment("IAMAR_KIT_ROOT").path_join("kit")
	var args := OS.get_cmdline_user_args()
	var library := ProjectSettings.globalize_path(LIBRARY)
	var only := []
	var i := 0
	while i < args.size():
		if args[i] == "--library" and i + 1 < args.size():
			library = args[i + 1]
			i += 1
		else:
			only.append(args[i])
		i += 1
	var baker = load(_kit_dir.path_join("catalog/assets").path_join(BAKER)).new()
	if not baker.load_library(library):
		quit(2)
		return
	var models_path := _kit_dir.path_join("catalog/sources/city_models.json")
	var bake_path := _kit_dir.path_join("catalog/sources/painted_bake.json")
	var models: Array = JSON.parse_string(FileAccess.get_file_as_string(models_path)).models
	var record := {}
	if FileAccess.file_exists(bake_path):
		for r: Dictionary in JSON.parse_string(FileAccess.get_file_as_string(bake_path)).files:
			record[r.file] = r
	var commit := _git_head()
	for row: Dictionary in models:
		var rel: String = row.file
		if not rel.begins_with("props/") or (not only.is_empty() and not only.has(rel)):
			continue
		var path := _kit_dir.path_join("catalog/assets").path_join(rel)
		var sha := FileAccess.get_sha256(path)
		if record.has(rel) and record[rel].sha256 == sha:
			print("BAKED already %s" % rel)
			continue
		if row.has("painted_bake") or sha != row.sha256:
			push_error("bake_painted: %s is neither the imported copy nor its recorded bake (rerun import_city_models.py)" % rel)
			_fails += 1
			continue
		var r := _bake_file(baker, path)
		if not r.get("ok", false):
			push_error("bake_painted: %s: %s" % [rel, r.get("error", "failed")])
			_fails += 1
			continue
		var out := {"file": rel, "source_sha256": row.sha256, "sha256": FileAccess.get_sha256(path),
			"bytes": FileAccess.get_file_as_bytes(path).size(), "atlas": [r.atlas.x, r.atlas.y],
			"px_per_m": r.px_per_m, "charts": r.charts, "triangles": r.triangles,
			"patterns": r.patterns, "glow": r.glow, "baker_commit": commit}
		record[rel] = out
		print("BAKED %s atlas %dx%d at %.0f px/m, %d triangles, patterns %s" % [rel, r.atlas.x, r.atlas.y, r.px_per_m, r.triangles, str(r.patterns)])
	var files := record.values()
	files.sort_custom(func(a, b): return str(a.file) < str(b.file))
	var f := FileAccess.open(bake_path, FileAccess.WRITE)
	f.store_string(JSON.stringify({
		"format": "iamar-catalog-painted-bake", "version": 1,
		"note": "The city's painted look (shaders/mp_painted.gdshaderinc in the iamar browser source (not public)) baked into a texture per "
			+ "prop by kit/catalog/assets/bake_painted.gd (painted_baker.gd), after import_city_models.py copied the "
			+ "props from the iamar-models mesh archive (not public). source_sha256 = the copy recorded in city_models.json, sha256 = the "
			+ "baked file. Never edit by hand: rerun the import and the bake.",
		"files": files}, " ", false) + "\n")
	f.close()
	print("PAINTED BAKE %d files recorded (%d failed)" % [files.size(), _fails])
	quit(1 if _fails else 0)


## Load a GLB, bake every MeshInstance3D's painted surfaces, write it back in place
## (nodes, names, physics bodies kept).
func _bake_file(baker, path: String) -> Dictionary:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(path, state)
	if err != OK:
		return {"ok": false, "error": "cannot read (%s)" % error_string(err)}
	var root := doc.generate_scene(state)
	var total := {"ok": false, "error": "no painted mesh", "triangles": 0, "charts": 0, "patterns": {}, "glow": false}
	for mi: MeshInstance3D in _meshes(root):
		var mesh := mi.mesh as ArrayMesh
		if mesh == null:
			continue
		var mats := []
		for s in mesh.get_surface_count():
			mats.append(mi.get_surface_override_material(s) if mi.get_surface_override_material(s) != null else mesh.surface_get_material(s))
		var r: Dictionary = baker.bake_mesh(mesh, mats)
		if not r.ok:
			continue
		mi.mesh = r.mesh
		for s in mi.get_surface_override_material_count():
			mi.set_surface_override_material(s, null)
		if total.ok:
			return {"ok": false, "error": "more than one painted mesh (one atlas per file expected)"}
		total = r
	if not total.ok:
		root.free()
		return total
	_own(root, root)
	var out_doc := GLTFDocument.new()
	out_doc.image_format = "JPEG"
	out_doc.lossy_quality = 0.85
	var out_state := GLTFState.new()
	err = out_doc.append_from_scene(root, out_state)
	if err == OK:
		err = out_doc.write_to_filesystem(out_state, path)
	root.free()
	if err != OK:
		return {"ok": false, "error": "cannot write (%s)" % error_string(err)}
	return total


func _meshes(n: Node) -> Array:
	var out := []
	if n is MeshInstance3D:
		out.append(n)
	for c in n.get_children():
		out.append_array(_meshes(c))
	return out


func _own(n: Node, root: Node) -> void:
	for c in n.get_children():
		c.owner = root
		_own(c, root)


func _git_head() -> String:
	var out := []
	OS.execute("git", ["-C", ProjectSettings.globalize_path("res://"), "rev-parse", "--short=8", "HEAD"], out)
	return str(out[0]).strip_edges() if not out.is_empty() else "unknown"
