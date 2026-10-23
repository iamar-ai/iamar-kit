extends SceneTree
## Signing and packing for iamar world packages (docs/WORLD_FORMAT.md 9, 9a).
##
##   godot --headless --path . -s res://scripts/kit/world_sign.gd -- keygen <private.key>
##   godot --headless --path . -s res://scripts/kit/world_sign.gd -- sign <folder> <private.key> "<Signer Name>"
##   godot --headless --path . -s res://scripts/kit/world_sign.gd -- verify <folder or .iamar>
##   godot --headless --path . -s res://scripts/kit/world_sign.gd -- pack <folder> <out.iamar> [<private.key> "<Signer Name>"]
##   godot --headless --path . -s res://scripts/kit/world_sign.gd -- keyid <private.key or public.pem>
##
## keygen requires native private-pair API v1 and an existing private local parent.
## It writes an RSA-2048 private PEM and <key>.pub with no replacement of either.
## sign sets manifest.signer (editing only that member of manifest.json) and
## writes signature.json. The private key never goes into a package or a repo.


static func _abs(p: String) -> String:
	return KitLoop.absolute_path(p)


## Where bare key names live: the same folder keygen writes to (%APPDATA%\\iamar\\signing on
## Windows, $XDG_CONFIG_HOME/iamar/signing or ~/.config/iamar/signing elsewhere).
static func signing_dir() -> String:
	if OS.has_feature("windows"):
		var ad := OS.get_environment("APPDATA")
		if ad != "":
			return ad.replace("\\", "/").trim_suffix("/") + "/iamar/signing"
	var xdg := OS.get_environment("XDG_CONFIG_HOME")
	if xdg == "":
		xdg = OS.get_environment("HOME").trim_suffix("/") + "/.config"
	return xdg.trim_suffix("/") + "/iamar/signing"


## A bare name (no slash, no .key) is a key in the signing folder; anything else is a path.
static func key_arg(a: String) -> String:
	if a == "" or a.contains("/") or a.contains("\\") or a.ends_with(".key"):
		return _abs(a)
	return signing_dir() + "/" + a + ".key"


func _init() -> void:
	var a := KitLoop.user_args()
	var code := 2
	if a.size() >= 2:
		match a[0]:
			"keygen": code = _keygen(key_arg(a[1]))
			"sign": code = _sign(_abs(a[1]), key_arg(a[2]), a[3]) if a.size() >= 4 else 2
			"verify": code = _verify(_abs(a[1]))
			"pack": code = _pack(_abs(a[1]), _abs(a[2]), key_arg(a[3]) if a.size() >= 4 else "", a[4] if a.size() >= 5 else "") if a.size() >= 3 else 2
			"keyid": code = _keyid(key_arg(a[1]))
	if code == 2:
		printerr("usage: world_sign.gd -- keygen <key> | sign <folder> <key> <name> | verify <pkg> | pack <folder> <out.iamar> [<key> <name>] | keyid <key>")
	quit(code)


func _load_key(p: String) -> CryptoKey:
	var k := CryptoKey.new()
	if k.load(p) != OK:
		printerr("cannot read private key ", p, " (run keygen <name> first)")
		return null
	return k


func _keygen(p: String) -> int:
	# Do not generate a credential, create directories, or fall back to path-based
	# save/chmod when the browser's native security facility is unavailable.
	if not ClassDB.class_exists("IamarPrivateKeyPair"):
		printerr("keygen requires a browser with native private-pair API v1; use an existing externally provisioned key for sign/package")
		return 1
	var transaction: Object = ClassDB.instantiate("IamarPrivateKeyPair")
	if transaction == null:
		printerr("cannot initialize native private key creation")
		return 1
	for method in ["get_api_version", "begin", "write_pair", "commit", "abort"]:
		if not transaction.has_method(method):
			printerr("incompatible native private key creation interface")
			return 1
	if transaction.call("get_api_version") != 1:
		printerr("keygen requires native private-pair API v1")
		return 1
	var started: Variant = transaction.call("begin", p)
	if not _keygen_result_ok(started):
		_keygen_report_failure(started)
		_keygen_cleanup(transaction)
		return 1
	var k := Crypto.new().generate_rsa(2048)
	if k == null or k.is_public_only():
		printerr("cannot generate RSA private key")
		_keygen_cleanup(transaction)
		return 1
	var private_pem := k.save_to_string(false)
	var public_pem := k.save_to_string(true)
	if private_pem.is_empty() or public_pem.is_empty():
		printerr("cannot serialize RSA key pair")
		_keygen_cleanup(transaction)
		return 1
	var written: Variant = transaction.call("write_pair", private_pem.to_utf8_buffer(), public_pem.to_utf8_buffer())
	private_pem = ""  # Do not retain an unnecessary copy; this is not secure erasure.
	if not _keygen_result_ok(written):
		_keygen_report_failure(written)
		_keygen_cleanup(transaction)
		return 1
	var committed: Variant = transaction.call("commit")
	if not _keygen_result_ok(committed) or not committed.get("public_published", false) \
			or not committed.get("private_published", false) or committed.get("uncertain", true):
		_keygen_report_failure(committed)
		_keygen_cleanup(transaction)
		return 1
	print("KEY ", p)
	print("PUBLIC ", p + ".pub")
	print("KEY_ID ", WorldSignature.key_id(public_pem))
	return 0


static func _keygen_result_ok(value: Variant) -> bool:
	return value is Dictionary and value.get("ok", false) == true


static func _keygen_report_failure(value: Variant) -> void:
	if not value is Dictionary:
		printerr("native private key creation returned an invalid result")
		return
	# Native result fields contain status and paths only, never key bytes.
	printerr("keygen failed: ", value.get("error", "unknown native error"))
	if value.get("public_published", false) or value.get("private_published", false):
		printerr("partial key output: public=%s private=%s; existing final files are preserved, do not blindly retry" % [value.get("public_published", false), value.get("private_published", false)])
	if value.get("uncertain", false):
		printerr("completion or cleanup is uncertain; inspect the reported paths before another attempt")
	for path in value.get("remaining_paths", []):
		printerr("keygen remaining path: ", path)


static func _keygen_cleanup(transaction: Object) -> void:
	var cleaned: Variant = transaction.call("abort")
	if not _keygen_result_ok(cleaned):
		_keygen_report_failure(cleaned)


func _keyid(p: String) -> int:
	var k := CryptoKey.new()
	if k.load(p) != OK and k.load(p, true) != OK:
		printerr("cannot read key ", p)
		return 1
	print("KEY_ID ", WorldSignature.key_id(k.save_to_string(true)))
	return 0


## Sets only the root manifest.signer value, preserving all other source bytes.
## JSON strings and extension objects may contain braces or their own "signer".
## Reject duplicate root claims instead of choosing an ambiguous signing input.
static func _set_signer(text: String, signer_json: String) -> String:
	var manifest: Variant = JSON.parse_string(text)
	if not manifest is Dictionary or not JSON.parse_string(signer_json) is Dictionary:
		return ""
	var depth := 0
	var string_start := -1
	var escaped := false
	var value_start := -1
	var value_end := -1
	var root_end := -1
	for i in text.length():
		var c := text[i]
		if string_start >= 0:
			if escaped:
				escaped = false
			elif c == "\\":
				escaped = true
			elif c == "\"":
				if depth == 1:
					var colon := _skip_json_space(text, i + 1)
					if colon < text.length() and text[colon] == ":" \
							and JSON.parse_string(text.substr(string_start, i - string_start + 1)) == "signer":
						if value_start >= 0:
							return ""
						value_start = _skip_json_space(text, colon + 1)
						if value_start >= text.length() or text[value_start] != "{":
							return ""
				string_start = -1
			continue
		# Refuse non-JSON control whitespace (including NUL) outside strings.
		# The engine parser may accept it or treat it as an early end of input.
		if c.unicode_at(0) < 32 and not (c in ["\t", "\r", "\n"]):
			return ""
		if c == "\"":
			string_start = i
		elif c == "{" or c == "[":
			depth += 1
		elif c == "}" or c == "]":
			depth -= 1
			if value_start >= 0 and value_end < 0 and depth == 1:
				value_end = i + 1
			elif depth == 0:
				root_end = i
	if value_start >= 0:
		if value_end < value_start:
			return ""
		return text.substr(0, value_start) + signer_json + text.substr(value_end)
	if root_end < 0:
		return ""
	# Insert before existing trailing object whitespace; do not reserialize the
	# manifest, strip its final newline or normalize unrelated numeric values.
	var insert_at := root_end
	while insert_at > 0 and text[insert_at - 1] in [" ", "\t", "\r", "\n"]:
		insert_at -= 1
	var comma := "" if manifest.is_empty() else ","
	# Godot's JSON parser accepts trailing commas. Reuse one already present.
	if insert_at > 0 and text[insert_at - 1] == ",":
		comma = ""
	return text.substr(0, insert_at) + comma + "\n  \"signer\": " + signer_json + text.substr(insert_at)


static func _skip_json_space(text: String, start: int) -> int:
	while start < text.length() and text[start] in [" ", "\t", "\r", "\n"]:
		start += 1
	return start


func _sign(folder: String, key_path: String, signer: String) -> int:
	var key := _load_key(key_path)
	if key == null:
		return 1
	var output_dir := DirAccess.open(folder)
	if output_dir == null:
		printerr("cannot open signing folder ", folder)
		return 1
	if output_dir.is_link(WorldFormat.MANIFEST) or output_dir.is_link(WorldFormat.SIGNATURE):
		printerr("refusing to sign through a manifest.json or signature.json symlink")
		return 1
	# Admit the existing folder before changing either output. This is a byte
	# snapshot, not signature verification; an old signature may be replaced.
	var preflight := WorldSource.open(folder)
	if not preflight.ok():
		printerr(preflight.error)
		return 1
	var mpath := folder.path_join(WorldFormat.MANIFEST)
	var text := preflight.read(WorldFormat.MANIFEST).get_string_from_utf8()
	if text == "":
		printerr("no manifest.json in ", folder)
		return 1
	var kid := WorldSignature.key_id(key.save_to_string(true))
	var out := _set_signer(text, JSON.stringify({"name": signer, "key_id": kid}))
	if out == "":
		printerr("manifest.json must be a JSON object with at most one object-valued root signer")
		return 1
	preflight.close()
	preflight = null   # release the old folder snapshot before capturing new bytes
	# These are in-place writes, not a transaction. A later failure can leave
	# manifest.json changed, and signature.json missing or partial after removal.
	# Link checks are best effort; they cannot prevent concurrent path changes.
	if output_dir.is_link(WorldFormat.MANIFEST):
		printerr("refusing to write manifest.json through a symlink")
		return 1
	# Replacing signature.json needs entry create/remove rights in the folder.
	# Probe them now, so a folder that cannot take the new signature refuses
	# before manifest.json gets a signer the old signature does not cover.
	if not _folder_writable(folder):
		return 1
	var f := FileAccess.open(mpath, FileAccess.WRITE)
	if f == null:
		printerr("cannot open manifest.json for writing: ", FileAccess.get_open_error())
		return 1
	var stored := f.store_string(out)
	var store_error := f.get_error()
	f.flush()
	var flush_error := f.get_error()
	f.close()
	if not stored or store_error != OK or flush_error != OK:
		printerr("cannot write manifest.json (store error %d, flush error %d)" % [store_error, flush_error])
		return 1
	# Recapture the changed manifest. Some FileAccess backends do not surface
	# flush failures through get_error(), so compare the actual bytes as well.
	var sig_path := folder.path_join(WorldFormat.SIGNATURE)
	var src := WorldSource.open(folder)
	if not src.ok():
		printerr(src.error)
		return 1
	if src.read(WorldFormat.MANIFEST) != out.to_utf8_buffer():
		printerr("manifest.json readback does not match the requested write")
		return 1
	# WorldSignature.hash_files excludes signature.json, so defer replacing the
	# old signature until the source and new signature have passed these checks.
	var sig := WorldSignature.make(src, key, signer)
	src.close()
	src = null
	var sig_text := JSON.stringify(sig, "  ") + "\n"
	var sig_bytes := sig_text.to_utf8_buffer()
	if sig_bytes.size() > WorldSignature.MAX_SIGNATURE_JSON:
		printerr("signature.json exceeds the browser's signature size limit")
		return 1
	if output_dir.is_link(WorldFormat.SIGNATURE):
		printerr("refusing to write signature.json through a symlink")
		return 1
	# Retain unlink-before-create semantics: WRITE on an existing hard link
	# would otherwise truncate that shared inode. No rollback follows removal.
	if FileAccess.file_exists(sig_path):
		var remove_error := DirAccess.remove_absolute(sig_path)
		if remove_error != OK:
			printerr("cannot remove old signature.json: ", remove_error)
			return 1
	f = FileAccess.open(sig_path, FileAccess.WRITE)
	if f == null:
		printerr("cannot open signature.json for writing: ", FileAccess.get_open_error())
		return 1
	stored = f.store_string(sig_text)
	store_error = f.get_error()
	f.flush()
	flush_error = f.get_error()
	f.close()
	if not stored or store_error != OK or flush_error != OK:
		printerr("cannot write signature.json (store error %d, flush error %d)" % [store_error, flush_error])
		return 1
	f = FileAccess.open(sig_path, FileAccess.READ)
	if f == null:
		printerr("cannot read back signature.json: ", FileAccess.get_open_error())
		return 1
	var readback := PackedByteArray()
	if f.get_length() == sig_bytes.size():
		readback = f.get_buffer(sig_bytes.size())
	var read_error := f.get_error()
	var size_matches := f.get_length() == sig_bytes.size()
	f.close()
	if read_error != OK or not size_matches or readback != sig_bytes:
		printerr("signature.json readback does not match the requested write")
		return 1
	if _verify(folder) != 0:
		return 1
	print("SIGNED %s: %d files, key %s, signer %s" % [folder, (sig.files as Dictionary).size(), kid, signer])
	return 0


func _folder_writable(folder: String) -> bool:
	var probe := ""
	for i in 8:
		var name := ".iamar-sign-probe-%d-%d" % [OS.get_process_id(), Time.get_ticks_usec() + i]
		if not FileAccess.file_exists(folder.path_join(name)):
			probe = folder.path_join(name)
			break
	if probe == "":
		printerr("cannot pick a probe name in ", folder)
		return false
	var f := FileAccess.open(probe, FileAccess.WRITE)
	if f == null:
		printerr("signing folder is not writable (cannot create entries): ", FileAccess.get_open_error())
		return false
	f.close()
	var remove_error := DirAccess.remove_absolute(probe)
	if remove_error != OK:
		printerr("signing folder is not writable (cannot remove entries, left %s): %d" % [probe, remove_error])
		return false
	return true


func _verify(p: String) -> int:
	var pkg := WorldPackage.open(p, {"require_signature": true})
	print("SIGNER ", pkg.signer_text())
	print("STATUS ", pkg.signature.get("status", "?"))
	for e in pkg.errors:
		print("ERROR ", e)
	if not pkg.ok:
		return 1
	print("OK")
	return 0


## Conservative native-path check: do not follow any detected link in either
## input's ancestry. This is not realpath(), inode identity, or an atomic open.
static func _pack_path_without_links(path: String) -> bool:
	if not path.is_absolute_path() or path.begins_with("res://") or path.begins_with("user://"):
		return false
	var current := path
	for _i in 256:
		var parent := current.get_base_dir()
		if parent == current or current == "/" or current.ends_with(":/"):
			return DirAccess.open(current) != null
		if parent == "":
			return false
		var directory := DirAccess.open(parent)
		if directory == null or directory.is_link(current.get_file()):
			return false
		current = parent
	return false


## The selected key must live outside the world, even under an ignored name.
## Compare captured bytes too: spelling checks cannot identify hard links,
## short-name aliases, mount aliases, or a copy of the selected key.
## This preflight and WorldPieces' later capture require a stable local tree.
static func _pack_key_is_external(folder: String, key_path: String) -> bool:
	if not (OS.has_feature("linux") or OS.has_feature("macos") or OS.has_feature("windows")):
		printerr("pack key-path checks require a supported native filesystem")
		return false
	# Case-fold conservatively on every filesystem: false positives are safer
	# than assuming a particular volume is case-sensitive.
	var root := folder.to_lower().trim_suffix("/")
	var selected := key_path.to_lower()
	if selected == root or selected.begins_with(root + "/"):
		printerr("refusing to pack: keep the selected signing key outside the world folder")
		return false
	if not _pack_path_without_links(folder) or not _pack_path_without_links(key_path):
		printerr("refusing to pack: world and key paths must have readable, link-free ancestors")
		return false
	var f := FileAccess.open(key_path, FileAccess.READ)
	if f == null:
		printerr("cannot read selected signing key for package preflight: ", key_path, " (a bare name lives in ", signing_dir(), "; run keygen <name> first)")
		return false
	var n := f.get_length()
	if n <= 0 or n > ZipGuard.MAX_ENTRY_BYTES:
		f.close()
		printerr("selected signing key is empty or exceeds the package file limit")
		return false
	var key_bytes := f.get_buffer(n)
	var complete := key_bytes.size() == n and f.get_length() == n and f.get_error() == OK
	f.close()
	if not complete:
		printerr("cannot completely read selected signing key for package preflight")
		return false
	var src := WorldSource.open(folder)
	if not src.ok() or src.is_zip:
		printerr("cannot inspect world folder before packing: ", src.error)
		src.close()
		return false
	for rel in src.list():
		if src.size_of(rel) == n:
			var entry := src.read(rel)
			if not src.ok() or entry.size() != n:
				src.close()
				printerr("cannot completely inspect captured world entry before packing")
				return false
			if entry == key_bytes:
				src.close()
				printerr("refusing to pack: world contains the selected signing key bytes")
				return false
	var complete_source := src.ok()
	src.close()
	if not complete_source:
		printerr("cannot completely inspect world folder before packing")
	return complete_source


func _pack(folder: String, out: String, key_path: String, signer: String) -> int:
	var key: CryptoKey = null
	if key_path == "" or signer == "":
		printerr("pack needs your key and name: visitors refuse unsigned worlds (see `keygen`)")
		return 2
	# Use the same normalized inputs for preflight, key loading, signing and
	# packing. Do not let the check inspect a different spelling from the use.
	folder = ProjectSettings.globalize_path(folder).replace("\\", "/").simplify_path()
	key_path = ProjectSettings.globalize_path(key_path).replace("\\", "/").simplify_path()
	if not _pack_key_is_external(folder, key_path):
		return 1
	key = _load_key(key_path)
	if key == null:
		return 1
	# sign the folder itself (signature.json inside the package), then pack it
	if _sign(folder, key_path, signer) != 0:
		return 1
	var r := WorldPieces.pack(folder, out, key, signer)
	for e in r.errors:
		print("ERROR ", e)
	if not r.ok:
		return 1
	print("PACKED %s (%d bytes, %d pieces, sha256 %s)" % [r.path, int(r.list["size"]), (r.list.pieces as Array).size(), r.list.sha256])
	print("PIECES ", r.pieces_path, " (", "signed" if r.list.has("signature") else "unsigned", ")")
	return _verify(out)
