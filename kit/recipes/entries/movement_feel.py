"""Recipe movement_feel (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- feel
ORDER = 300
r("movement_feel", "Responsive movement", "feel",
  "Jump grace (coyote time and a jump buffer), step-up only on steep collisions, floor snap, an eased camera that never clips into walls and fits rooms indoors.",
  "Built into the browser; keep walkable slopes and doorways reasonable.", ["Keep doorways at least 2.2 m high, stairs shallow, walkable slopes under 40 degrees."],
  {"jump_grace_s": 0.15, "floor_snap_m": 0.9}, "walk every path and portal.", "None.", "oakhaven player.gd JUMP_GRACE, floor_snap_length, c17e70d", "automatic")
