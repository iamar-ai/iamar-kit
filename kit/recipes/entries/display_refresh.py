"""Recipe display_refresh (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 400
r("display_refresh", "Check the display before blaming vsync", "measurement",
  "A game pinned at exactly 30 fps with an idle GPU is often the monitor: vsync can only show as many frames as the display refreshes.",
  "Whenever frame time sits at exactly 33.3 ms (or 16.7 ms) while the GPU and script times are far below it.",
  ["Read the display mode first (Linux: `xrandr`; Windows: display settings / DisplayServer.screen_get_refresh_rate()).",
   "4K offered only at 30/25/24 Hz with a 297 MHz pixel clock means an HDMI 1.4 link (TV input, cable or DP-to-HDMI adapter): fix it in hardware or run a 60 Hz mode.",
   "On the Compatibility renderer, adaptive vsync acts as plain vsync on OpenGL, so changing it buys nothing."],
  {}, "display mode listed in the perf report.", "None.",
  "iamar-fps F1 (the GPU host 3840x2160 at 29.97 Hz; 2560x1440@60 and 1080p@120 available)", "manual")
