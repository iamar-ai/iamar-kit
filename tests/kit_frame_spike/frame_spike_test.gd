extends SceneTree
## FrameSpike (scripts/kit/frame_spike.gd): worst_frame_ms with one re-measure per view.
## Run with tests/kit_frame_spike/run.sh (headless, a throwaway stub project).

const FrameSpike = preload("res://frame_spike.gd")
var _fails := 0


func _check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ") + what)
	if not ok:
		_fails += 1


func _pass(fs, frames: Array, start := 21) -> void:
	for i in frames.size():
		fs.frame(float(frames[i]), start + i)


func _init() -> void:
	# 1. under the limit: one pass, the worst frame and where it was
	var a = FrameSpike.new(50.0)
	_pass(a, [5.0, 7.5, 6.0])
	_check(a.end_pass("spawn") == false, "under limit: no re-measure")
	_check(is_equal_approx(a.worst[0], 7.5) and a.worst[1] == "spawn" and a.worst[2] == 22 and a.worst[3] < 0.0,
		"under limit: worst 7.5 ms at frame 22, no first pass")

	# 2. a one-off spike (the harbour greybox case: 65.5 ms once): re-measured, does not repeat
	var b = FrameSpike.new(50.0)
	_pass(b, [5.0, 65.5, 6.0])
	_check(b.end_pass("custom3") == true, "spike: re-measure requested")
	_pass(b, [6.0, 8.0, 5.0])
	_check(b.end_pass("custom3") == false, "spike: second pass ends the view")
	_check(is_equal_approx(b.worst[0], 8.0) and b.worst[2] == 22 and is_equal_approx(b.worst[3], 65.5),
		"spike: second pass counts (8.0 ms), first pass 65.5 ms kept for the report")
	_check(b.describe(60).contains("first pass 65.5 ms"), "spike: report names the first pass")

	# 3. a hitch that repeats still fails; the lower of the two worst frames counts
	var c = FrameSpike.new(50.0)
	_pass(c, [5.0, 90.0])
	_check(c.end_pass("market") == true, "repeat: re-measure requested")
	_pass(c, [70.0, 5.0])
	_check(c.end_pass("market") == false, "repeat: only one re-measure per view")
	_check(is_equal_approx(c.worst[0], 70.0) and c.worst[0] > c.limit, "repeat: 70.0 ms counts, still over the limit")
	var c2 = FrameSpike.new(50.0)
	_pass(c2, [80.0])
	c2.end_pass("x")
	_pass(c2, [95.0, 5.0], 21)
	c2.end_pass("x")
	_check(is_equal_approx(c2.worst[0], 80.0) and c2.worst[2] == 21, "repeat: lower first pass (80.0) counts over a worse second (95.0)")

	# 4. across views: the worst view wins; a later re-measure of another view starts fresh
	var d = FrameSpike.new(50.0)
	_pass(d, [10.0, 12.0])
	d.end_pass("north")
	_pass(d, [60.0])
	_check(d.end_pass("south") == true, "views: second view re-measured")
	_pass(d, [9.0])
	d.end_pass("south")
	_pass(d, [3.0])
	_check(d.end_pass("east") == false, "views: third view not re-measured (state reset)")
	_check(is_equal_approx(d.worst[0], 12.0) and d.worst[1] == "north" and d.worst[3] < 0.0,
		"views: north 12.0 ms is the worst after south's spike did not repeat")

	# 5. nothing counted (--frames 20 or fewer)
	var e = FrameSpike.new(50.0)
	_check(e.end_pass("spawn") == false and e.describe(20).begins_with("WORST_FRAME none"), "no frames: none measured")

	# 6. world_view.gd uses it: one re-measure from settled state, the screenshot stall skipped
	var src := FileAccess.get_file_as_string("res://world_view.gd")
	_check(src.contains("_worst_frame.frame(delta * 1000.0, _wait)") and src.contains("_worst_frame.end_pass(")
		and src.contains("_wait = 19") and src.contains("_wait == _frames and not _remeasure")
		and src.contains("_worst_frame.describe(_frames)"), "world_view.gd wires FrameSpike")

	print("FRAME_SPIKE %s (%d failed)" % ["PASS" if _fails == 0 else "FAIL", _fails])
	quit(0 if _fails == 0 else 1)
