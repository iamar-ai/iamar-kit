"""Recipe ui_page_lists (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 340
r("ui_page_lists", "Long lists and pictures in pages", "interface",
  "Inventories, logs and notice boards with hundreds of rows stay smooth, and pages can show the world's own pictures.",
  "Any list longer than about 20 rows; any icon or picture in a page.",
  ["Use a `list` node (items + max_height): only the rows in view are built, up to 1000 items. Replace its rows with one patch of `items`; do not patch rows one by one.",
   "Keep rows simple and alike (a panel with a text and a button); give rows ids only when the script needs their events.",
   "Images are `asset:<path>.png|jpg|webp` inside the signed package, decoded off the main thread: at most 32 per script, 2048 px a side, 16 MiB decoded in all. Use small icons (64-256 px), not photos."],
  {"list_items": 1000, "max_page_images": 32, "image_px": 2048},
  "Scroll the longest list in the preview; images that break a limit show an empty frame and one log line.",
  "Rows outside the view cost nothing; each image costs its decoded size in memory.",
  "iamar-ui-pages U6 (scripts/sandbox/world_ui/ui_page_list.gd, ui_page_images.gd)", "manual")
