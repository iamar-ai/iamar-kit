# UI look and feel: fonts, panels and pages that match the world

How a world's text and panels should look so they match the world instead of looking like a
browser dialog. Two ways to show UI exist; this guide covers both:

1. **Elements** (live today): `ui_text`, `ui_button`, `ui_bar`, `ui_color`, `ui_remove`, `ui_note`,
   at most 32 fixed-position elements. Good for a score, a prompt, a button.
2. **Pages** (world API 0.4): a script hands the browser a page as data (`ui_page_set`, then
   `ui_page_show` as an overlay, modal or surface). Good for a shop, a journal, a notice board.
   The schema is `api/ui_page.schema.json` in the iamar checkout; the builder is
   `scripts/sandbox/world_ui/ui_page_builder.gd`; the host call is wired in
   `scripts/sandbox/world_api.gd`. `docs/WORLD_UI_PAGES_DRAFT.md` still says "nothing is
   implemented"; that line is out of date, and the code is the reference.

Check a page before you ship it:

```
python3 kit/recipes/ui/check_ui.py kit/recipes/ui/examples/shop_page.ui_page.json <iamar-checkout>
```

It prints `UI_OK` when the page passes the schema and the host limits (512 nodes, 32 levels of
nesting, unique ids, 64 KiB, no URLs in text), otherwise one `FAIL` line per problem.

## 1. Typography

- **One typeface for the world's text.** Game text is Fondamento (Regular and Italic, bundled in
  `assets/fonts/fondamento/`; `docs/FONTS.md`). Any new text renderer uses the game font, not an OS
  font: a world that asks for a system font looks different on every machine.
- **Page font families** are `serif`, `sans`, `mono`, `display`, `hand` (schema). `serif` is the default
  and maps to the game font; `display` is the same face with heavier strokes for titles. Use `sans` or
  `mono` only for data that must read as data (prices in a table, a code snippet).
- **Sizes:** body 16 to 18 px, `font_size` between 8 and 64 (schema). Headings scale from the body size:
  level 1 about 1.6x, level 2 about 1.3x, level 3 about 1.1x (`ui_page_theme.gd`). Do not go below 14 px
  for anything a player must read at a distance.
- **Rich text is a small subset:** `**bold**`, `*italic*`, `[color=#hex]`, `[size=n]` and line breaks.
  Nothing else is rendered. Keep it to one emphasis per sentence.
- **Glyphs outside Fondamento** fall back to the bundled Noto subsets, then the OS fonts. Latin text and
  digits need no fallback.

## 2. Panels and framing

- **Page defaults** (`ui_page_theme.gd`): `radius 8`, `padding 14`, `border_width 1`, `shadow soft`.
  A world's theme keeps the same proportions; it changes colour, not structure.
- **A world page is framed as the world's.** The browser never lets a page imitate its own dialogs, so
  a world page must not reuse the browser's leather-and-gold dialog box (`scripts/ui/ui_theme.gd`:
  oxblood buttons, gold borders). Use the world's palette for the panel instead, and a thin border in
  a colour from that palette. The page default is slate-and-teal for this reason.
- **Padding and gaps** on a `column` or `row`: gap 8 to 12 between related controls, 16 or more between
  sections. Keep one spacing step per page.
- **Contrast:** text on a panel must be readable at its size. The example page uses parchment
  (`#efe3c2`) on a dark brown panel (`#2b2118`); check the ratio before you ship a new colour pair.

## 3. Colour

The iamar look uses a warm palette (from `scripts/ui/ui_theme.gd` and the city's style profile):

| Role | Value | Use |
|---|---|---|
| Parchment (text on dark) | `#efe3c2` | body text, labels |
| Gold (accent) | `#f2c75c` | headings, progress, the one call to action |
| Dim gold (border) | `#b8923e` | panel borders, dividers |
| Ink (text on light) | `#1a120a` | text on parchment panels |
| Dark panel | `#2b2118` (with alpha `f0`) | page background |
| Oxblood (button fill) | `#5a1d12` | the browser's button colour; fine as a button fill with a gold label, never for a panel |

Use one accent per page. Warm and cool light contrast comes from the world's lighting, not from extra
colours in the UI.

## 4. Layout and performance

- **Build once, patch many.** A page is built one time; a price or a timer changes through
  `ui_page_patch` on one node, at most 60 patches a second per page. Never rebuild a page to change a
  value.
- **Long lists** use the `list` node: rows outside the view are not built, and rows do not count toward
  the 512-node limit (up to 16 nodes per row).
- **Scroll** a long page with `scroll` and a `max_height`, not with a page that runs off the screen.
- **Surfaces** (a page drawn on a shop counter or a notice board) cost more. The draft sets at most 4 per
  world, up to 1024 by 1024, and no updates beyond 40 m (`WORLD_UI_PAGES_DRAFT.md`; check the host for the
  limits it enforces).

## 5. Safety and trust

- No URLs and no network in pages. A `link` node fires an event; the script decides what it means.
- Page text is sanitised: control and bidi characters are removed.
- A world input shows a one-time hint that the box belongs to the world and that the player must never
  type their iamar password there. Do not ask for passwords or payment details in a world page.

## Worked example

`examples/shop_page.ui_page.json` is a shop page in the world's palette: a heading, a picture from the
world's package (`asset:img/lantern.webp`, which must be in the world's package), rich text, a quantity
input and a buy button, a progress bar and a link. It passes `check_ui.py`. Run it in the real preview
world before you call the look done.

## What is not verified

- The checker validates the page as data (schema, limits, ids, URLs). It does not build the page or show
  it on screen. A rendered check (a modal or overlay shot in the preview world, read from the usual 1.7 m
  view) is what proves the page reads well; that run is not done here.
- The contrast figures above are the palette values, not a measured ratio on screen.
