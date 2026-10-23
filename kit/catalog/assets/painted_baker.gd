extends RefCounted
## Bake the iamar city's painted look into a texture, so a MeshKit object exported as
## glTF keeps its wood grain, stone, plaster, iron, trim mouldings, cloth mottling,
## contact shade and glow instead of one flat colour per face (an internal task).
##
## In the city every MeshKit surface is drawn by shaders/mp_painted.gdshaderinc
## (the iamar browser source (not public)), which makes its own texture coordinates from the per-vertex look:
##   COLOR.rgb = the look's colour, COLOR.a = (pattern * 8 + glow) / 255,
##   UV = MeshKit's per-face 0..1 coordinates, UV2.x = contact shade,
## and samples the painted library assets/masterplan/textures/mp_library.png (13 layers
## of 4 m at 256 px per metre, the last one the trim sheet). A glTF cannot carry that
## shader, so this script runs the shader's colour logic on the CPU, texel by texel, into
## one atlas per object:
##   - every face (a MeshKit quad = two triangles sharing an edge, or one triangle) gets
##     its own chart in the atlas at `px_per_m`, with a 2 px gutter filled by the face's
##     own edge colour (no seams under mipmapping);
##   - the triangles are kept (same corners, same winding; grouped into a surface per
##     roughness class, in their order within it): only TEXCOORD_0 is replaced (vertices
##     shared between charts are split), COLOR_0 and the contact channel are dropped
##     (both are in the texture), so the file looks the same in every glTF viewer and on
##     browsers older than the iamar browser source (not public) d7d034da;
##   - faces of iron (pattern 8), iron strap trim (19) and glass (7) go to their own
##     surface with the city's roughness and metallic; glowing faces (glow codes 1-7)
##     get an emission texture at a dusk level (`night`, see EMISSION below).
## What is not baked, because it needs the city around the object: the light bake
## (sky visibility stains), the world maps (street wear, grass edges, wall-foot grime,
## ivy, painted framing), the paving breakup of large flagged floors, rain wetness and
## cloud shadow. The full list of patterns is in kit/catalog/assets/README.md.
##
##   var B = load("res://.../painted_baker.gd").new()
##   B.load_library("<iamar>/assets/masterplan/textures/mp_library.png")
##   var r: Dictionary = B.bake_mesh(array_mesh)   # {"mesh", "ok", "atlas", "patterns", ...}

const TILE_M := 4.0
const LAYERS := 13
const L_STONE := 0
const L_ASHLAR := 1
const L_GRANITE := 2
const L_PLASTER := 3
const L_TIMBER := 4
const L_SLATE := 5
const L_SLATE_DARK := 6
const L_GLAZED := 7
const L_SHINGLE := 8
const L_THATCH := 9
const L_COBBLE := 10
const L_IRON := 11
const L_TRIM := 12
const TRIM_STRIPS := 8.0
const GUTTER := 2

## texels per metre of the atlas (the city's library is 256; half of it keeps a chair's
## atlas at 256-512 px and still shows every board's grain at arm's length)
var px_per_m := 128.0
## largest atlas side; a bigger object is baked at a lower density to fit
var max_atlas := 1024
## the shader's uniforms for this object
var quarter := 0
var variant := 0
var indoor := false
var macro_strength := 0.16
var edge_highlight := 0.22
## EMISSION: the city drives glow by its day-night cycle (`night` 0..1); a glTF glow is
## fixed, so it is baked at this level (dusk: lamps and embers read lit by day, not
## blown out at night)
var night := 0.35

var _lib_img: Image
var _layer_px := 0
var _layers := {}       # [layer, side px] -> PackedFloat32Array (linear rgb)
var _texel_m := 0.01


func load_library(path: String) -> bool:
	var img := Image.load_from_file(path)
	if img == null or img.is_empty():
		push_error("painted_baker: cannot read %s" % path)
		return false
	img.convert(Image.FORMAT_RGB8)
	_lib_img = img
	_layer_px = img.get_width()
	if img.get_height() != _layer_px * LAYERS:
		push_error("painted_baker: %s is %dx%d, expected %d layers of %d" % [path, img.get_width(), img.get_height(), LAYERS, _layer_px])
		return false
	return true


## The layer at the bake's density (the library is 256 px/m; a smaller bake samples a
## filtered copy, as the GPU's mipmaps would), as linear floats.
func _layer(layer: int) -> Array:
	var side := mini(_layer_px, maxi(16, int(round(px_per_m * TILE_M))))
	var key := layer * 100000 + side
	if _layers.has(key):
		return [_layers[key], side]
	var img := _lib_img.get_region(Rect2i(0, layer * _layer_px, _layer_px, _layer_px))
	if side != _layer_px:
		img.resize(side, side, Image.INTERPOLATE_LANCZOS if layer != L_TRIM else Image.INTERPOLATE_BILINEAR)
	var data := img.get_data()
	var f := PackedFloat32Array()
	f.resize(side * side * 3)
	var lut := PackedFloat32Array()
	lut.resize(256)
	for i in 256:
		lut[i] = Color(i / 255.0, 0, 0).srgb_to_linear().r
	for i in side * side * 3:
		f[i] = lut[data[i]]
	_layers[key] = f
	return [f, side]


## texture(lib, vec3(uv, layer)) with repeat and bilinear filtering (uv in tiles)
func _tex(uv: Vector2, layer: int) -> Vector3:
	var l := _layer(layer)
	var f: PackedFloat32Array = l[0]
	var s: int = l[1]
	var x := uv.x * s - 0.5
	var y := uv.y * s - 0.5
	var x0 := floori(x)
	var y0 := floori(y)
	var fx := x - x0
	var fy := y - y0
	var xa := posmod(x0, s)
	var xb := posmod(x0 + 1, s)
	var ya := posmod(y0, s)
	var yb := posmod(y0 + 1, s)
	var i00 := (ya * s + xa) * 3
	var i10 := (ya * s + xb) * 3
	var i01 := (yb * s + xa) * 3
	var i11 := (yb * s + xb) * 3
	var out := Vector3()
	for c in 3:
		var top := lerpf(f[i00 + c], f[i10 + c], fx)
		var bot := lerpf(f[i01 + c], f[i11 + c], fx)
		out[c] = lerpf(top, bot, fy)
	return out


func _lib_at(uv_m: Vector2, layer: int) -> Vector3:
	return _tex(uv_m / TILE_M, layer)


# --- the shader's helpers (shaders/common.gdshaderinc), ported 1:1 ----------------------

static func _fract(x: float) -> float:
	return x - floorf(x)


static func _hash21(p: Vector2) -> float:
	var q := Vector2(_fract(p.x * 123.34), _fract(p.y * 456.21))
	var d := q.dot(q + Vector2(45.32, 45.32))
	q += Vector2(d, d)
	return _fract(q.x * q.y)


static func _vnoise(p: Vector2) -> float:
	var i := Vector2(floorf(p.x), floorf(p.y))
	var f := p - i
	var u := f * f * (Vector2(3, 3) - 2.0 * f)
	var a := _hash21(i)
	var b := _hash21(i + Vector2(1, 0))
	var c := _hash21(i + Vector2(0, 1))
	var d := _hash21(i + Vector2(1, 1))
	return lerpf(lerpf(a, b, u.x), lerpf(c, d, u.x), u.y)


static func _fbm2(p: Vector2) -> float:
	return _vnoise(p) * 0.65 + _vnoise(p * 2.03 + Vector2(17, 17)) * 0.35


static func _sstep(e0: float, e1: float, x: float) -> float:
	var t := clampf((x - e0) / (e1 - e0), 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)


static func _glsl_hash(c: Vector2) -> float:
	return _fract(sin(c.dot(Vector2(12.9898, 78.233))) * 43758.5453)


## face-aligned planar coordinates (mp_painted planar())
static func _planar(p: Vector3, n: Vector3) -> Vector2:
	if absf(n.y) > 0.92:
		return Vector2(p.x, p.z)
	var t := Vector3(-n.z, 0.0, n.x).normalized()
	var d := n.cross(t).normalized()
	if d.y > 0.0:
		d = -d
	return Vector2(p.dot(t), p.dot(d))


func _roof_layer() -> int:
	if quarter == 1:
		return L_SLATE if variant == 2 else L_SLATE_DARK
	elif quarter == 2:
		return L_SLATE if variant == 2 else L_GLAZED
	elif quarter == 3:
		return L_THATCH if variant == 1 else L_SHINGLE
	return L_SLATE_DARK if variant == 1 else L_SLATE


func _variant_look() -> Color:
	if variant == 1:
		return Color(0.95, 0.93, 0.9, 0.62)
	elif variant == 2:
		return Color(1.04, 1.03, 1.0, 0.14)
	return Color(1.0, 1.0, 1.0, 0.35)


func _quarter_grade(c: Vector3) -> Vector3:
	if quarter == 1:
		return c * Vector3(0.9, 0.84, 0.77)
	elif quarter == 2:
		return c * Vector3(1.01, 0.99, 0.95)
	elif quarter == 3:
		return c * Vector3(1.04, 1.0, 0.9)
	return c


## Smoothstep anti-aliased joint as the shader does it, with fwidth = one bake texel.
static func _solid(edge: Vector2, half: Vector2, fw: Vector2) -> float:
	return _sstep(half.x - fw.x, half.x + fw.x, edge.x) * _sstep(half.y - fw.y, half.y + fw.y, edge.y)


## The shader's fragment(), for one point of one face. `t` is the face record from
## _faces(); `w` the barycentric weights. Returns [albedo (linear), emission (linear),
## roughness, metallic].
func _shade(t: Dictionary, w: Vector3) -> Array:
	var pattern: int = t.pattern
	var glow: int = t.glow
	var ca: Vector3 = t.ca
	var p: Vector3 = t.p[0] * w.x + t.p[1] * w.y + t.p[2] * w.z
	var n: Vector3 = (t.n[0] * w.x + t.n[1] * w.y + t.n[2] * w.z).normalized()
	var uv: Vector2 = t.uv[0] * w.x + t.uv[1] * w.y + t.uv[2] * w.z
	var contact: float = t.contact[0] * w.x + t.contact[1] * w.y + t.contact[2] * w.z
	var tint := ca / 0.68
	var col := ca
	var emit_mask := 1.0
	var rough := 0.9
	var metal := 0.0
	var pm := _planar(p, n) + Vector2(variant * 1.37, variant * 0.61)
	var framed: bool = t.framed
	var du: Vector3 = t.du
	var dv: Vector3 = t.dv
	var lu: float = t.lu
	var lv: float = t.lv
	var u_long := lu >= lv
	var long_dir := du if u_long else dv
	var across01 := clampf(uv.y if u_long else uv.x, 0.0, 1.0)
	var short_len := lv if u_long else lu
	var swap := false
	if absf(n.y) > 0.92:
		swap = absf(long_dir.z) > absf(long_dir.x)
	else:
		swap = absf(long_dir.y) > 0.7
	var grain_uv := Vector2(pm.y, pm.x) if swap else pm
	var along := grain_uv.x
	if not framed:
		across01 = _fract(pm.y)
		short_len = 10.0
	var tm := _texel_m

	var painted := true
	if pattern == 1:
		col = _lib_at(pm, L_STONE) * tint
	elif pattern == 11:
		col = _lib_at(pm, L_GRANITE if quarter == 1 else L_ASHLAR) * tint
	elif pattern == 20:
		var bp := pm / Vector2(0.25, 0.085)
		var row := floorf(bp.y)
		bp.x += 0.5 * fmod(row, 2.0)
		var cell := Vector2(floorf(bp.x), floorf(bp.y))
		var f := bp - cell
		var fw := Vector2(maxf(tm / 0.25, 1e-4), maxf(tm / 0.085, 1e-4))
		var edge := Vector2(minf(f.x, 1.0 - f.x), minf(f.y, 1.0 - f.y))
		var body := _solid(edge, Vector2(0.035, 0.09), fw)
		var shade := _glsl_hash(cell)
		var grain := _lib_at(pm * 0.7, L_STONE) / 0.6
		var lo := Vector3(0.82, 0.82, 0.82).lerp(Vector3(1.12, 1.12, 1.12), shade)
		var brick := tint * 0.6 * lo * Vector3.ONE.lerp(grain, 0.45)
		var mortar := Vector3(0.66, 0.62, 0.56).lerp(tint * 0.6, 0.25)
		var far := clampf(maxf(fw.x, fw.y) * 2.0 - 0.5, 0.0, 1.0)
		col = mortar.lerp(brick, body).lerp(mortar.lerp(brick, 0.8), far)
	elif pattern == 21:
		col = _lib_at(pm, L_PLASTER) * tint
	elif pattern == 22:
		var lw := _lib_at(pm, L_PLASTER) * tint
		var ap := pm / Vector2(0.9, 0.42)
		var arow := floorf(ap.y)
		ap.x += 0.5 * fmod(arow, 2.0)
		var acell := Vector2(floorf(ap.x), floorf(ap.y))
		var af := ap - acell
		var afw := Vector2(maxf(tm / 0.9, 1e-4), maxf(tm / 0.42, 1e-4))
		var aedge := Vector2(minf(af.x, 1.0 - af.x), minf(af.y, 1.0 - af.y))
		var ajoint := 1.0 - _solid(aedge, Vector2(0.011 / 0.9, 0.011 / 0.42), afw)
		var ablock := _glsl_hash(acell)
		lw *= lerpf(0.92, 1.05, ablock)
		if ablock >= 0.7:
			lw *= Vector3(1.03, 1.0, 0.95)
		var afar := clampf(maxf(afw.x, afw.y) * 3.0 - 0.5, 0.0, 1.0)
		col = lw.lerp(lw * Vector3(0.76, 0.71, 0.64), ajoint * (1.0 - afar) * 0.85)
	elif pattern == 23:
		var lw := _lib_at(pm, L_PLASTER) * tint
		var ap := Vector2(0.0, pm.y / 0.42 + 0.22 * sin(pm.y * 2.3) + 0.13 * sin(pm.y * 5.7))
		var arow := floorf(ap.y)
		var row_seed := _fract(sin(arow * 78.233 + 19.17) * 43758.5453)
		var block_w := lerpf(0.72, 1.20, row_seed)
		ap.x = pm.x / block_w + row_seed * 3.7 + 0.18 * sin(pm.x * 2.7 + arow)
		var acell := Vector2(floorf(ap.x), floorf(ap.y))
		var af := ap - acell
		var rate := Vector2(1.0 / block_w + 0.486 * cos(pm.x * 2.7 + arow),
			1.0 / 0.42 + 0.506 * cos(pm.y * 2.3) + 0.741 * cos(pm.y * 5.7))
		var afw := Vector2(maxf(tm * absf(rate.x), 1e-4), maxf(tm * absf(rate.y), 1e-4))
		var aedge := Vector2(minf(af.x, 1.0 - af.x), minf(af.y, 1.0 - af.y))
		var ajoint := 1.0 - _solid(aedge, 0.03 * rate, afw)
		var ablock := _glsl_hash(acell)
		var wash := _vnoise(pm * 1.35)
		lw *= lerpf(0.96, 1.03, ablock)
		lw *= Vector3(0.94, 0.93, 0.90).lerp(Vector3(1.04, 1.025, 0.995), wash)
		var afar := clampf(maxf(afw.x, afw.y) * 1.2 - 0.5, 0.0, 1.0)
		col = lw.lerp(lw * Vector3(0.55, 0.48, 0.38), ajoint * (1.0 - afar) * 0.45)
	elif pattern == 4:
		col = _lib_at(pm, L_PLASTER) * tint
		if quarter == 2:
			col *= Vector3(0.9, 0.9, 1.08) if variant == 2 else Vector3(0.74, 0.76, 1.02)
	elif pattern == 2:
		col = _lib_at(grain_uv, L_TIMBER) * tint
	elif pattern == 3:
		col = _lib_at(pm, _roof_layer()) * tint * 1.08
		if quarter == 0 and variant == 2:
			col = _lib_at(pm, L_GLAZED) * Vector3(0.8, 0.42, 0.3) / 0.6
	elif pattern == 6:
		col = _lib_at(pm, L_THATCH) * tint
	elif pattern == 5:
		col = _lib_at(pm, L_COBBLE) * tint
	elif pattern == 8:
		col = _lib_at(pm * 0.5, L_IRON) * tint
		rough = 0.38
		metal = 0.45
	elif pattern >= 12 and pattern < 20:
		var strip := float(pattern - 12)
		var v := (strip + lerpf(0.03, 0.97, across01)) / TRIM_STRIPS
		col = _tex(Vector2(along / TILE_M, v), L_TRIM) * tint
		if pattern == 19:
			rough = 0.4
			metal = 0.4
	else:
		painted = false

	if not painted:
		if pattern == 7:
			var fw2 := lu if framed else 1.0
			var fh := lv if framed else 1.4
			var stained := glow == 4
			var cells := Vector2(maxf(1.0, floorf(fw2 / 0.24 + 0.5)), maxf(1.0, floorf(fh / 0.3 + 0.5)))
			var g := uv * cells
			var cell := Vector2(floorf(g.x), floorf(g.y))
			var gf := g - cell
			if stained:
				var dg := Vector2(g.x + g.y, g.x - g.y) * 0.75
				cell = Vector2(floorf(dg.x), floorf(dg.y))
				gf = dg - cell
			var pane_lead := 1.0 - _sstep(0.035, 0.08, minf(minf(gf.x, 1.0 - gf.x), minf(gf.y, 1.0 - gf.y)))
			var mull := maxf(1.0 - _sstep(0.02, 0.04, absf(uv.x - 0.5)), 1.0 - _sstep(0.02, 0.04, absf(uv.y - 0.45)))
			var border := 1.0 - _sstep(0.0, 0.06, minf(minf(uv.x, 1.0 - uv.x), minf(uv.y, 1.0 - uv.y)))
			var lead := maxf(maxf(mull, border), pane_lead * 0.85)
			var ph := _hash21(cell + Vector2(floorf(p.x * 0.5), floorf(p.z * 0.5)))
			var glass: Vector3
			if stained:
				var q := Vector3(0.62, 0.12, 0.1) if ph < 0.25 else (Vector3(0.12, 0.22, 0.62) if ph < 0.5 else (Vector3(0.85, 0.66, 0.18) if ph < 0.75 else Vector3(0.18, 0.48, 0.24)))
				glass = q * (0.75 + 0.5 * _vnoise(g * 3.0))
			else:
				var sky_c := Vector3(0.55, 0.66, 0.8)
				var room := Vector3(0.32, 0.22, 0.13)
				var refl := _sstep(1.0, 0.0, uv.y) * 0.75 + 0.25
				glass = room.lerp(sky_c, refl) * (0.78 + 0.35 * ph)
				var sheen := 1.0 - _sstep(0.0, 0.08, absf(_fract((uv.x + uv.y * 0.6) * 1.3) - 0.5))
				glass += Vector3(0.25, 0.25, 0.22) * sheen * 0.6   # (daylight: the bake's albedo is the day's)
				glass = glass.lerp(ca * 0.9, 0.25)
			col = glass.lerp(Vector3(0.12, 0.1, 0.09), lead)
			emit_mask = (1.0 - lead) * (0.75 + 0.5 * (1.0 - uv.y)) * (lerpf(0.35, 1.2, night) if stained else 1.0)
			rough = 0.18
		elif pattern == 9:
			col = ca * (0.9 + 0.12 * _vnoise(pm * 18.0))
			col = col.lerp(ca * 0.7, _sstep(0.6, 0.9, _fbm2(pm * 2.0)) * 0.3)
		elif pattern == 10:
			var st := 1.0 if _fract(pm.x * 1.4) >= 0.5 else 0.0
			col = ca.lerp(Vector3(0.94, 0.89, 0.78), st) * (0.92 + 0.1 * _vnoise(pm * 10.0))
		else:
			col = ca * (0.94 + 0.08 * _vnoise(pm * 5.0))
	else:
		var vl := _variant_look()
		var macro := _fbm2(pm * 0.11 + Vector2(quarter * 7.3 + variant * 3.1, quarter * 7.3 + variant * 3.1))
		var ms := macro_strength * 0.4 if pattern == 3 else macro_strength
		col *= 1.0 - ms * 0.5 + ms * macro
		var wall := absf(n.y) < 0.5
		var grime := _sstep(0.55, 0.9, _fbm2(pm * 0.35 + Vector2(3.1, 3.1))) * (1.0 if wall else 0.4)
		var streak := _sstep(0.6, 0.95, _vnoise(Vector2(pm.x * 3.0, pm.y * 0.15))) * (1.0 if variant == 1 else 0.0) * (1.0 if wall else 0.0)
		var grime_c := Vector3(0.8, 0.81, 0.85) if pattern == 3 else Vector3(0.72, 0.68, 0.62)
		var grime_k := 0.5 if pattern == 3 else 1.0
		col = col.lerp(col * grime_c, clampf(grime * vl.a * grime_k + streak * 0.25, 0.0, 1.0))
		col *= Vector3(vl.r, vl.g, vl.b)
		var plaster := pattern == 4 or pattern == 21 or pattern == 22 or pattern == 23
		if framed and short_len < 1.2 and not plaster:
			var eu := minf(uv.x, 1.0 - uv.x) * lu
			var ev := minf(uv.y, 1.0 - uv.y) * lv
			var rim := 1.0 - _sstep(0.0, 0.045, minf(eu, ev))
			col *= 1.0 + edge_highlight * rim
		var wall_like := wall and pattern in [1, 11, 4, 2, 20, 21, 22, 23]
		# rain streaks down from the top of each wall panel (outdoors; no bake = open sky)
		if framed and wall_like and not indoor:
			var dtop := -1.0
			var along_m := 0.0
			if absf(dv.y) > 0.7 and lv > 0.5:
				dtop = (clampf(uv.y, 0.0, 1.0) if dv.y < 0.0 else 1.0 - clampf(uv.y, 0.0, 1.0)) * lv
				along_m = uv.x * lu
			elif absf(du.y) > 0.7 and lu > 0.5:
				dtop = (clampf(uv.x, 0.0, 1.0) if du.y < 0.0 else 1.0 - clampf(uv.x, 0.0, 1.0)) * lu
				along_m = uv.y * lv
			if dtop >= 0.0:
				var rs := _sstep(0.38, 0.72, _vnoise(Vector2(along_m * 3.2 + variant * 5.1, 0.7)))
				var reach := 0.9 + 1.4 * _vnoise(Vector2(along_m * 0.9, 3.3))
				var fall := 1.0 - _sstep(0.0, reach, dtop)
				col = col.lerp(col * Vector3(0.7, 0.66, 0.6), rs * fall * 0.6)
		if framed and short_len < 1.2 and (pattern == 1 or pattern == 11):
			var eu := minf(uv.x, 1.0 - uv.x) * lu
			var ev := minf(uv.y, 1.0 - uv.y) * lv
			var edge := 1.0 - _sstep(0.0, 0.07, minf(eu, ev))
			var chip := _vnoise(pm * 11.0 + Vector2(2, 2))
			col *= 1.0 + 0.16 * edge * _sstep(0.4, 0.6, chip) - 0.22 * edge * _sstep(0.78, 0.86, chip)
		if pattern == 3 and quarter == 1:
			var sl := col.dot(Vector3(0.333, 0.333, 0.333))
			col = (Vector3(sl, sl, sl) * Vector3(0.93, 0.97, 1.06)).lerp(col, 0.45)
		else:
			col = _quarter_grade(col)

	var emission := Vector3.ZERO
	if glow == 1:
		emission = Vector3(1.0, 0.7, 0.35) * lerpf(0.05, 1.7, night)
	elif glow == 2:
		emission = ca * 1.35
	elif glow == 3:
		emission = Vector3(0.45, 1.0, 0.5) * lerpf(0.35, 1.8, night)
	elif glow == 4:
		emission = Vector3(1.0, 0.8, 0.45) * lerpf(0.25, 1.4, night)
	elif glow == 5:
		emission = ca * lerpf(0.15, 3.0, night)
	elif glow == 7:
		var dc := (uv - Vector2(0.5, 0.7)) * Vector2(2.2, 1.7)
		var core := exp(-dc.dot(dc) * 2.5)
		emission = (ca + Vector3(1.0, 0.6, 0.2) * core * 0.55) * lerpf(0.15, 3.0, night)
	return [col * contact, emission * emit_mask, rough, metal]


# --- faces and charts ------------------------------------------------------------------

## The face record of triangle (a, b, c) of a surface: its look, and its frame from the
## MeshKit UVs (what the shader gets from dFdx/dFdy), exact for a flat triangle.
func _face(arr: Array, a: int, b: int, c: int) -> Dictionary:
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var nr: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
	var cols: PackedColorArray = arr[Mesh.ARRAY_COLOR]
	var uvs = arr[Mesh.ARRAY_TEX_UV]
	var uv2s = arr[Mesh.ARRAY_TEX_UV2]
	var idx := [a, b, c]
	var t := {"i": idx, "p": [], "n": [], "uv": [], "contact": []}
	for k in idx:
		t.p.append(v[k])
		t.n.append(nr[k] if nr.size() > k else Vector3.UP)
		t.uv.append((uvs as PackedVector2Array)[k] if uvs != null and (uvs as PackedVector2Array).size() > k else Vector2.ZERO)
		t.contact.append((uv2s as PackedVector2Array)[k].x if uv2s != null and (uv2s as PackedVector2Array).size() > k else 1.0)
	var col: Color = cols[a]
	var code := int(round(col.a * 255.0))
	t.pattern = code / 8
	t.glow = code % 8
	# the shader's COLOR.rgb: Godot hands a spatial shader the vertex colour decoded from
	# sRGB (measured: the city's unshaded mp_painted output matches only with this; raw
	# values bake 1.4-4x too bright and washed out), the alpha (look code) as stored
	var lin := Color(col.r, col.g, col.b).srgb_to_linear()
	t.ca = Vector3(lin.r, lin.g, lin.b)
	# frame: dp/du and dp/dv from the triangle's two edges
	var e1: Vector3 = t.p[1] - t.p[0]
	var e2: Vector3 = t.p[2] - t.p[0]
	var s1: Vector2 = t.uv[1] - t.uv[0]
	var s2: Vector2 = t.uv[2] - t.uv[0]
	var det := s1.x * s2.y - s1.y * s2.x
	t.framed = false
	t.du = Vector3(1, 0, 0)
	t.dv = Vector3(0, -1, 0)
	t.lu = 1.0
	t.lv = 1.0
	if absf(det) > 1e-9:
		var dpdu := (e1 * s2.y - e2 * s1.y) / det
		var dpdv := (e2 * s1.x - e1 * s2.x) / det
		t.lu = dpdu.length()
		t.lv = dpdv.length()
		t.du = dpdu / maxf(t.lu, 1e-6)
		t.dv = dpdv / maxf(t.lv, 1e-6)
		t.framed = t.lu > 1e-4 and t.lv > 1e-4
	t.class = _class_of(t.pattern)
	return t


## surface class by roughness/metallic: 0 painted, 1 iron, 2 iron strap trim, 3 glass
static func _class_of(pattern: int) -> int:
	if pattern == 8:
		return 1
	if pattern == 19:
		return 2
	if pattern == 7:
		return 3
	return 0


const CLASS_RM := [[0.9, 0.0], [0.38, 0.45], [0.4, 0.4], [0.18, 0.0]]


## Charts: a MeshKit quad (two triangles sharing an edge with the same UVs on it, same
## look) is one chart parametrised by its UVs; any other triangle with usable UVs is a
## chart of its own; a triangle without usable UVs is laid flat in its own plane.
## Each chart: {"tris": [face...], "pc": [[Vector2 x3] per tri], "lo", "hi", "scale"}
func _charts(faces: Array) -> Array:
	var charts := []
	var used := {}
	for i in faces.size():
		if used.has(i):
			continue
		var t: Dictionary = faces[i]
		used[i] = true
		var ch := {"tris": [t], "pc": []}
		if t.framed:
			# a partner sharing two corners (same position and UV) and the same look
			for j in [i + 1, i - 1]:
				if j < 0 or j >= faces.size() or used.has(j):
					continue
				var o: Dictionary = faces[j]
				if not o.framed or o.pattern != t.pattern or o.glow != t.glow or not o.ca.is_equal_approx(t.ca) or o.class != t.class:
					continue
				var shared := 0
				for a in 3:
					for b in 3:
						if (t.p[a] as Vector3).distance_squared_to(o.p[b]) < 1e-10 and (t.uv[a] as Vector2).distance_squared_to(o.uv[b]) < 1e-10:
							shared += 1
				if shared == 2:
					ch.tris.append(o)
					used[j] = true
					break
			for f: Dictionary in ch.tris:
				ch.pc.append(f.uv.duplicate())
			ch.scale = Vector2(maxf(t.lu, (ch.tris[-1] as Dictionary).lu), maxf(t.lv, (ch.tris[-1] as Dictionary).lv))
		else:
			# flat in its own plane, metres: x along the longest edge
			var p0: Vector3 = t.p[0]
			var e := [(t.p[1] as Vector3) - p0, (t.p[2] as Vector3) - p0]
			var ax: Vector3 = (e[0] as Vector3).normalized() if (e[0] as Vector3).length() >= (e[1] as Vector3).length() else (e[1] as Vector3).normalized()
			var nrm: Vector3 = (e[0] as Vector3).cross(e[1]).normalized()
			var ay := nrm.cross(ax).normalized()
			var pc := []
			for q: Vector3 in t.p:
				pc.append(Vector2((q - p0).dot(ax), (q - p0).dot(ay)))
			ch.pc.append(pc)
			ch.scale = Vector2.ONE
		var lo := Vector2(INF, INF)
		var hi := Vector2(-INF, -INF)
		for pc: Array in ch.pc:
			for q: Vector2 in pc:
				lo = Vector2(minf(lo.x, q.x), minf(lo.y, q.y))
				hi = Vector2(maxf(hi.x, q.x), maxf(hi.y, q.y))
		ch.lo = lo
		ch.hi = hi
		charts.append(ch)
	return charts


## Texel size of each chart at the density, and a shelf packing into a power-of-two
## atlas; returns the atlas size or 0 when it would exceed max_atlas.
func _pack(charts: Array, dens: float) -> Vector2i:
	for ch: Dictionary in charts:
		var ext: Vector2 = (ch.hi - ch.lo) * (ch.scale as Vector2)
		ch.w = maxi(2, ceili(ext.x * dens))
		ch.h = maxi(2, ceili(ext.y * dens))
	var order := range(charts.size())
	order.sort_custom(func(a, b): return charts[a].h > charts[b].h or (charts[a].h == charts[b].h and a < b))
	# every power-of-two width; the height is the packing's, rounded up to a power of
	# two; the smallest area wins (then the squarer)
	var best := Vector2i.ZERO
	var side := 32
	while side <= max_atlas:
		var used := _shelves(charts, order, side, false)
		if used > 0:
			var hgt := 32
			while hgt < used:
				hgt *= 2
			if hgt <= max_atlas:
				var cand := Vector2i(side, hgt)
				if best == Vector2i.ZERO or cand.x * cand.y < best.x * best.y \
						or (cand.x * cand.y == best.x * best.y and absi(cand.x - cand.y) < absi(best.x - best.y)):
					best = cand
		side *= 2
	if best != Vector2i.ZERO:
		_shelves(charts, order, best.x, true)
	return best


## Shelf packing of the charts (tallest first) into rows `width` texels wide; returns
## the height used (0 when a chart is wider than the atlas). `place` stores x, y.
func _shelves(charts: Array, order: Array, width: int, place: bool) -> int:
	var x := 0
	var y := 0
	var row_h := 0
	for k: int in order:
		var ch: Dictionary = charts[k]
		var cw: int = ch.w + 2 * GUTTER
		if cw > width:
			return 0
		if x + cw > width:
			x = 0
			y += row_h
			row_h = 0
		if place:
			ch.x = x
			ch.y = y
		x += cw
		row_h = maxi(row_h, ch.h + 2 * GUTTER)
	return y + row_h


## Barycentric weights of q in the 2D triangle (a, b, c).
static func _bary(q: Vector2, a: Vector2, b: Vector2, c: Vector2) -> Vector3:
	var v0 := b - a
	var v1 := c - a
	var v2 := q - a
	var d := v0.x * v1.y - v1.x * v0.y
	if absf(d) < 1e-14:
		return Vector3(1, 0, 0)
	var wb := (v2.x * v1.y - v1.x * v2.y) / d
	var wc := (v0.x * v2.y - v2.x * v0.y) / d
	return Vector3(1.0 - wb - wc, wb, wc)


## Clamp barycentric weights into the triangle (texels in the gutter and outside the
## triangle take the colour of its nearest edge).
static func _clamp_bary(w: Vector3) -> Vector3:
	var c := Vector3(maxf(w.x, 0.0), maxf(w.y, 0.0), maxf(w.z, 0.0))
	var s := c.x + c.y + c.z
	return c / s if s > 1e-9 else Vector3(1, 0, 0)


## True when the surface carries MeshKit's painted look: opaque, vertex colours with look
## codes, MeshKit's face UVs and its contact channel (UV2). Effect surfaces (a fountain's
## water and splash) have no UV2 and pass through untouched.
static func is_painted_surface(arr: Array, mat: Material) -> bool:
	if arr[Mesh.ARRAY_COLOR] == null or arr[Mesh.ARRAY_TEX_UV] == null or arr[Mesh.ARRAY_TEX_UV2] == null:
		return false
	if mat is BaseMaterial3D:
		var bm := mat as BaseMaterial3D
		if bm.albedo_texture != null or bm.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
			return false
	return true


## Bake every painted surface of `mesh` into one atlas. Returns
## {"ok", "mesh" (new ArrayMesh, triangles and their order kept), "atlas" (Vector2i),
##  "px_per_m", "patterns" {pattern: triangles}, "glow" (bool), "untouched" (surfaces kept)}.
## `materials` (optional): the source material per surface, to pass non-painted surfaces on.
func bake_mesh(mesh: ArrayMesh, materials: Array = []) -> Dictionary:
	var faces := []
	var painted := []
	var kept := []
	for s in mesh.get_surface_count():
		var arr := mesh.surface_get_arrays(s)
		var mat: Material = materials[s] if s < materials.size() else mesh.surface_get_material(s)
		if not is_painted_surface(arr, mat):
			kept.append([arr, mat])
			continue
		painted.append(arr)
		var ix = arr[Mesh.ARRAY_INDEX]
		var n: int = (ix as PackedInt32Array).size() if ix != null else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
		for k in range(0, n, 3):
			var a: int = ix[k] if ix != null else k
			var b: int = ix[k + 1] if ix != null else k + 1
			var c: int = ix[k + 2] if ix != null else k + 2
			var f := _face(arr, a, b, c)
			f.surface = painted.size() - 1
			f.order = faces.size()
			faces.append(f)
	if faces.is_empty():
		return {"ok": false, "error": "no painted surface"}
	var charts := _charts(faces)
	var dens := px_per_m
	var size := _pack(charts, dens)
	while size == Vector2i.ZERO and dens > 8.0:
		dens *= 0.8
		size = _pack(charts, dens)
	if size == Vector2i.ZERO:
		return {"ok": false, "error": "does not fit a %d px atlas" % max_atlas}
	_texel_m = 1.0 / dens
	var saved := px_per_m
	px_per_m = dens
	var alb := PackedByteArray()
	alb.resize(size.x * size.y * 3)
	var emi := PackedFloat32Array()
	emi.resize(size.x * size.y * 3)
	var any_glow := false
	var patterns := {}
	for ch: Dictionary in charts:
		for f: Dictionary in ch.tris:
			patterns[f.pattern] = int(patterns.get(f.pattern, 0)) + 1
			if f.glow != 0:
				any_glow = true
		var lo: Vector2 = ch.lo
		var span: Vector2 = ch.hi - ch.lo
		var w: int = ch.w
		var h: int = ch.h
		for ty in range(-GUTTER, h + GUTTER):
			for tx in range(-GUTTER, w + GUTTER):
				var fr := Vector2(clampf((tx + 0.5) / w, 0.0, 1.0), clampf((ty + 0.5) / h, 0.0, 1.0))
				var q := lo + fr * span
				var best := 0
				var best_w := Vector3(1, 0, 0)
				var best_min := -INF
				for k in ch.tris.size():
					var pc: Array = ch.pc[k]
					var bw := _bary(q, pc[0], pc[1], pc[2])
					var m := minf(bw.x, minf(bw.y, bw.z))
					if m > best_min:
						best_min = m
						best = k
						best_w = bw
				var r := _shade(ch.tris[best], _clamp_bary(best_w))
				var o: int = ((ch.y + GUTTER + ty) * size.x + (ch.x + GUTTER + tx)) * 3
				var c: Vector3 = r[0]
				var lc := Color(clampf(c.x, 0, 1), clampf(c.y, 0, 1), clampf(c.z, 0, 1)).linear_to_srgb()
				alb[o] = clampi(int(round(lc.r * 255.0)), 0, 255)
				alb[o + 1] = clampi(int(round(lc.g * 255.0)), 0, 255)
				alb[o + 2] = clampi(int(round(lc.b * 255.0)), 0, 255)
				var e: Vector3 = r[1]
				emi[o] = e.x
				emi[o + 1] = e.y
				emi[o + 2] = e.z
	px_per_m = saved
	var albedo := Image.create_from_data(size.x, size.y, false, Image.FORMAT_RGB8, alb)
	albedo.generate_mipmaps()
	var emission: Image = null
	var emission_energy := 1.0
	if any_glow:
		var peak := 0.0
		for v in emi:
			peak = maxf(peak, v)
		emission_energy = maxf(peak, 1e-3) if peak > 1.0 else 1.0
		var eb := PackedByteArray()
		eb.resize(emi.size())
		for i in emi.size() / 3:
			var lc := Color(emi[i * 3] / emission_energy, emi[i * 3 + 1] / emission_energy, emi[i * 3 + 2] / emission_energy).linear_to_srgb()
			eb[i * 3] = clampi(int(round(lc.r * 255.0)), 0, 255)
			eb[i * 3 + 1] = clampi(int(round(lc.g * 255.0)), 0, 255)
			eb[i * 3 + 2] = clampi(int(round(lc.b * 255.0)), 0, 255)
		emission = Image.create_from_data(size.x, size.y, false, Image.FORMAT_RGB8, eb)
		emission.generate_mipmaps()

	# new surfaces: one per class, triangles in their original order, vertices split
	# where a corner sits in two charts
	var atlas_uv := {}   # [face order, corner] -> Vector2
	for ch: Dictionary in charts:
		var lo: Vector2 = ch.lo
		var span: Vector2 = ch.hi - ch.lo
		for k in ch.tris.size():
			var f: Dictionary = ch.tris[k]
			for corner in 3:
				var q: Vector2 = ch.pc[k][corner]
				var fr := Vector2((q.x - lo.x) / span.x if span.x > 1e-12 else 0.5, (q.y - lo.y) / span.y if span.y > 1e-12 else 0.5)
				atlas_uv[f.order * 3 + corner] = Vector2((ch.x + GUTTER + fr.x * ch.w) / float(size.x), (ch.y + GUTTER + fr.y * ch.h) / float(size.y))
	var tex := ImageTexture.create_from_image(albedo)
	var etex: ImageTexture = ImageTexture.create_from_image(emission) if emission != null else null
	var out := ArrayMesh.new()
	for cls in CLASS_RM.size():
		var pos := PackedVector3Array()
		var nrm := PackedVector3Array()
		var uvo := PackedVector2Array()
		var idx := PackedInt32Array()
		var seen := {}
		for f: Dictionary in faces:
			if f.class != cls:
				continue
			for corner in 3:
				var src_i: int = f.i[corner]
				var uvn: Vector2 = atlas_uv[f.order * 3 + corner]
				var key := "%d:%d:%.6f:%.6f" % [f.surface, src_i, uvn.x, uvn.y]
				if not seen.has(key):
					seen[key] = pos.size()
					pos.append(f.p[corner])
					nrm.append(f.n[corner])
					uvo.append(uvn)
				idx.append(seen[key])
		if idx.is_empty():
			continue
		var arr := []
		arr.resize(Mesh.ARRAY_MAX)
		arr[Mesh.ARRAY_VERTEX] = pos
		arr[Mesh.ARRAY_NORMAL] = nrm
		arr[Mesh.ARRAY_TEX_UV] = uvo
		arr[Mesh.ARRAY_INDEX] = idx
		out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		var m := StandardMaterial3D.new()
		m.albedo_texture = tex
		m.roughness = CLASS_RM[cls][0]
		m.metallic = CLASS_RM[cls][1]
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		if etex != null:
			m.emission_enabled = true
			m.emission = Color(1, 1, 1)
			m.emission_texture = etex
			m.emission_energy_multiplier = emission_energy
		out.surface_set_material(out.get_surface_count() - 1, m)
	for k: Array in kept:
		out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, k[0])
		out.surface_set_material(out.get_surface_count() - 1, k[1])
	return {"ok": true, "mesh": out, "atlas": size, "px_per_m": snappedf(dens, 0.1), "charts": charts.size(),
		"patterns": patterns, "glow": any_glow, "emission_energy": snappedf(emission_energy, 0.01),
		"untouched": kept.size(), "triangles": faces.size()}
