"""Recipe native_gl_windows (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 290
r("native_gl_windows", "Native OpenGL on Windows", "quality",
  "On Windows x86 the GL Compatibility renderer runs straight on the driver's OpenGL; ANGLE (OpenGL over Direct3D) is only for devices known to need it. Faster and it draws correctly.",
  "Every project on the Compatibility renderer that ships for Windows.",
  ["project.godot: `rendering/gl_compatibility/driver.windows=\"opengl3\"`.",
   "`force_angle_on_devices`: Godot's default list (old Radeon HD/R, Intel HD, old Iris) plus `{vendor: Microsoft, name: *}` (OpenGL-on-D3D12, the only GL on Windows ARM64/Snapdragon) and `{vendor: Qualcomm, name: *}`; setting the key replaces the defaults, so write them out.",
   "Leave `fallback_to_angle` on: a PC whose native GL fails to start gets ANGLE.",
   "Do not use a two-feature key such as `driver.windows.arm64`: Godot 4.7 ignores it silently."],
  {}, "frame time A/B with `--rendering-driver opengl3` vs `opengl3_angle` at fixed views (tests/masterplan_city/render_time_probe.gd); shots compared.",
  "None.",
  "iamar-fps F5 ef84861d (Intel Arc 140V: mean frame -26 %, p95 -40 %, render CPU -25 %; ANGLE drew torn cloud bands and wall dither; docs/perf/fps_f5_windows_driver.md)", "manual")
