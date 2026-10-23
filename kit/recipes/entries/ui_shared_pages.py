"""Recipe ui_shared_pages (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 350
r("ui_shared_pages", "Pages every visitor sees the same", "interface",
  "Scoreboards, shared notice boards and votes that show the same thing to everyone in the room, although every visitor's browser builds its own copy of the page.",
  "Any page whose content belongs to the room rather than to one visitor; a visitor's own coins, journal or settings stay local (kv).",
  ["Every visitor runs their own copy of the script and builds the pages once in on_init, as usual. Only the content is shared, never the page itself.",
   "One copy keeps the truth: the one where `is_authority()` is 1 (the visitor with the smallest player key). It alone changes the shared state.",
   "Other copies send requests, not results: `message_to(authority, {\"t\":\"ring\"})`, where the authority's id is the player with the smallest `player_key` (the same rule). The authority applies its own requests directly.",
   "The authority judges a request by its sender (the player id on_message_from gives it), never by a name or key inside the bytes; rate-limits each sender and cleans text (control and bidi characters out, length capped).",
   "After a change the authority broadcasts the whole state with `world_message`, at most every 0.25 s (a burst costs one message), kept under 1 KiB (drop the oldest rows to fit). Every copy patches it into its pages (`ui_page_patch` of the list `items` and the texts that changed).",
   "A copy accepts a state only from the player it counts as the authority, and from the same authority only a newer revision. A newcomer gets the state because the authority marks it dirty in on_enter.",
   "Every copy keeps the last state, so when the authority leaves, the next one (its own is_authority turns 1 in on_tick) bumps the revision and carries on. is_authority is coordination, not security: a hostile visitor can arrange to be it."],
  {"messages_per_s": 20, "message_bytes": 1024, "state_every_s": 0.25},
  "tests/typescript-world/ui_shared_sandbox.gd runs four visitors' copies wired like the net bridge: same pages everywhere, forged states and keys ignored, a late visitor and an authority handover.",
  "One message per change burst to each visitor; pages are only patched, never rebuilt.",
  "iamar-ui-pages U16; example examples/typescript-ui-shared/", "manual")
