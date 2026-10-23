extends SceneTree
## Renders the kit gallery's city views (views.json beside this file) from an the iamar browser source (not public)
## checkout: the stand-alone masterplan city (MpWalk) with the game's day/night clock
## (MpNight.attach_day_night: sky, sun, fog, windows, lamps) at views.json "hour", the Fast
## frame (no MSAA, no sun shadow) as tools/report_city_shot.gd draws it.
##   offscreen godot --path <iamar checkout> --resolution 1280x720 \
##       -s <kit>/kit/gallery/city/city_views.gd -- <views.json> <out dir> [view id,...]
## Writes <out dir>/<view id>.jpg (960x540, quality 0.82) and prints CV lines.


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var a := OS.get_cmdline_user_args()
	if a.size() < 2:
		push_error("usage: -- <views.json> <out dir> [view id,...]")
		quit(2)
		return
	var spec: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(a[0]))
	var out: String = a[1]
	var only: Array = Array(a[2].split(",")) if a.size() > 2 else []
	DirAccess.make_dir_recursive_absolute(out)
	var walk := MpWalk.new()
	walk.spawn_player = false
	root.add_child(walk)
	walk.sun.shadow_enabled = false               # the Fast preset
	root.msaa_3d = Viewport.MSAA_DISABLED
	var pool: LightPool = walk.city.ctx.get("light_pool")
	var hour := float(spec.get("hour", 16.5))
	var dn := MpNight.attach_day_night(walk, walk.sun, walk.env, pool, hour)
	var height: Callable = walk.city.ctx.height_at
	var cam := Camera3D.new()
	cam.far = 4000.0
	root.add_child(cam)
	cam.current = true
	dn.set_hour(hour)
	var n := 0
	for v: Dictionary in spec.views:
		if not only.is_empty() and not only.has(String(v.id)):
			continue
		var e: Array = v.eye
		var t: Array = v.target
		var eye := Vector3(e[0], float(height.call(e[0], e[1])) + float(v.get("eye_h", 1.7)), e[1])
		var at := Vector3(t[0], float(height.call(t[0], t[1])) + float(v.get("target_h", 0.0)), t[1])
		cam.fov = float(v.get("fov", spec.get("fov", 62.0)))
		cam.position = eye
		cam.look_at(at, Vector3.UP)
		for k in 60:
			await process_frame
		await RenderingServer.frame_post_draw
		var path := "%s/%s.jpg" % [out, v.id]
		var img := root.get_texture().get_image()
		img.resize(960, 540, Image.INTERPOLATE_LANCZOS)
		img.save_jpg(path, 0.82)
		print("CV %s eye=%s target=%s %s" % [v.id, eye, at, path])
		n += 1
	print("CV_DONE %d" % n)
	quit(0)
