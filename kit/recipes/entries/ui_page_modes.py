"""Recipe ui_page_modes (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 330
r("ui_page_modes", "Overlay, modal or surface", "interface",
  "Pick where a page appears: a corner panel, a centred dialog that takes the keys, or a sign drawn on an object in the world.",
  "Overlay (mode 1) for small always-on panels (coins, objectives); modal (2) for things the player reads or fills in (journal, dialogue choices, a form); surface (3) for things that belong to a place (shop counter, notice board, a screen).",
  ["Overlay: keep it small; overlays share one column drawn under the browser's own UI, so they never cover it.",
   "Modal: open it on a key (`input_bind`) or a button. Esc and the frame's close button always close it and send kind 5: save what the player typed then. For 1.5 s after the player closes a modal, a new one is refused (E_LIMIT); do not retry in a loop.",
   "Surface: spawn a box (the page fills its +Z face) or a plane (its top), `ui_page_surface(page, w, h)` with the face's aspect (128-1024 px a side), then `ui_page_show(page, 3, entity)`. At most 4 surfaces; past 40 m they stop updating, the player clicks them within 15 m.",
   "Game keys are muted while the player types in a page field; do not bind letters you need while a modal is open."],
  {"max_surfaces": 4, "surface_px": [512, 512], "surface_update_m": 40, "surface_click_m": 15, "modal_reopen_s": 1.5},
  "Walk up to every surface and open every modal in the preview; Esc closes each modal.",
  "A surface renders only after a change (patch, input); idle surfaces cost no GPU time.",
  "iamar-ui-pages U4/U5 (scripts/sandbox/world_ui/ui_page_host.gd, ui_page_surface.gd); example examples/typescript-ui-shop/", "manual")
