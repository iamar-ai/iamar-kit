extends RefCounted
## worst_frame_ms for `iamar-world preview` / `perf` (scripts/kit/world_view.gd).
##
## Each view is measured after its settle frames (the loading hitch of a camera jump is
## never counted). A view whose worst frame is over the limit is measured once more, and
## the lower of the two worst frames counts: a hitch the world causes (streaming, a script,
## a heavy material) comes back, while a one-off stall from a busy computer (another
## program, the GPU shared with a bake) does not. Both numbers are kept for the report.
##
##   frame(ms, index)  every counted frame of the current pass
##   end_pass(view)    at the end of a pass: true = measure this view again
##   worst             [ms, view, frame index, first-pass ms or -1.0]

var limit := 50.0
var worst := [0.0, "", -1, -1.0]
var _pass_max := 0.0
var _pass_at := -1
var first_pass_ms := -1.0      ## worst frame of the first pass when this view is being re-measured
var _first_at := -1


func _init(limit_ms := 50.0) -> void:
	limit = limit_ms


func frame(ms: float, index: int) -> void:
	if ms > _pass_max:
		_pass_max = ms
		_pass_at = index


## Ends the current pass of `view`. Returns true when the view went over the limit for
## the first time and should be measured again; after that pass the lower of the two
## worst frames counts.
func end_pass(view: String) -> bool:
	if first_pass_ms < 0.0 and _pass_max > limit:
		first_pass_ms = _pass_max
		_first_at = _pass_at
		_pass_max = 0.0
		_pass_at = -1
		return true
	var kept := [_pass_max, _pass_at]
	if first_pass_ms >= 0.0 and first_pass_ms < _pass_max:
		kept = [first_pass_ms, _first_at]
	if kept[0] > worst[0]:
		worst = [kept[0], view, kept[1], first_pass_ms]
	first_pass_ms = -1.0
	_first_at = -1
	_pass_max = 0.0
	_pass_at = -1
	return false


## One line for the report: where the worst frame was, and a spike that did not repeat.
func describe(frames: int) -> String:
	if worst[2] < 0:
		return "WORST_FRAME none measured (each view renders %d frames; the first 20 settle and are not counted)" % frames
	var s := "WORST_FRAME %.1f ms in view %s, frame %d of %d (frames 1-20 after each camera move settle and are not counted)" % [
		worst[0], worst[1], worst[2], frames]
	if float(worst[3]) >= 0.0:
		s += "; that view was measured twice because its first pass went over %.0f ms (first pass %.1f ms), the lower worst frame counts" % [limit, float(worst[3])]
	return s
