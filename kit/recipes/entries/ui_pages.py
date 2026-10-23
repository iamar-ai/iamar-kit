"""Recipe ui_pages (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

# ---- interface (world UI pages, world API 0.4)
ORDER = 320
r("ui_pages", "Build a page once, then patch it", "interface",
  "Shops, journals, notice boards and menus as world UI pages: JSON the browser builds from its own controls, kept cheap by building once and changing single nodes.",
  "Any world UI beyond a line of text or one button (ui_text / ui_button / ui_bar stay for those).",
  ["Describe the page as data with the typed builders in api/typescript/iamar-world.d.ts (UiPage, UiNode): column/row/grid/panel for layout, text/heading/image, button/link/input/textarea/checkbox/slider/select for input, list for long lists. No HTML, no URLs.",
   "Give every node the script will patch, read or hear from its own `id` (1-65535, unique in the page).",
   "Call `ui_page_set` for every page in on_init (they start hidden), then `ui_page_show` when needed. After that send only `ui_page_patch(page, node, {...})` for what changed; never re-set a page to change one label.",
   "Handle `on_ui_event(page, node, kind)`: 1 click, 2 change, 3 submit, 4 link, 5 the player closed a modal. Read an input with `ui_value` when you need it.",
   "Style with a page `theme` (bg, fg, accent, border, font) and per-node `style`; colours are #rrggbb[aa], sizes px or \"50%\".",
   "Lower the manifest UI budgets to what the world uses (max_pages, max_page_nodes, page_nodes_total, max_surfaces, max_page_images) and declare api_version 0.4."],
  {"max_pages": 8, "max_page_nodes": 512, "page_nodes_total": 2000, "page_bytes": 65536, "patch_bytes": 8192, "patches_per_s": 60},
  "`iamar-world validate` checks the manifest budgets; tests/typescript-world/ui_shop_sandbox.gd shows the pattern under test.",
  "A built page costs nothing while idle; a full re-set rebuilds every control (sliced over frames for big pages).",
  "iamar-ui-pages U1-U4 (docs/WORLD_UI_PAGES_DRAFT.md, api/ui_page.schema.json); example examples/typescript-ui-shop/", "manual")
