"""Recipe physics_interp (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 270
r("physics_interp", "Physics interpolation", "loading",
  "Movement is smooth at any frame rate.", "Always.", ["Keep physics interpolation on (project setting)."], {}, "", "None.", "oakhaven project.godot physics_interpolation=true", "automatic")
