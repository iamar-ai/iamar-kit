# Gallery: good and bad examples

`gallery.json` holds annotated outcomes from the iamar build: what went wrong or right, the lesson, the recipe it feeds, and the source document that records it. `gallery.md` is generated from it.

Use it to calibrate before you build. Failures are as useful as successes: each FAILED entry is a trap that a new world would otherwise walk into again.

- `WORKS` / `PARTIAL` / `FAILED` is the outcome the source records, not a judgement of this file.
- Pictures are not copied here. The `source` path says where the before/after shots or the verdict live in the iamar browser source (not public).
- A `layer` of `engineering` applies to every world; `style` applies to the iamar look only.

## Commands

```
python gallery.py check                          # validate the JSON (exit 1 on error)
python gallery.py check --sources <iamar repo>   # also confirm every source file exists
python gallery.py build                          # regenerate gallery.md
```

## Adding an entry

1. Take the outcome from a source file you have read, with its line.
2. Give it a category from `categories` in `gallery.json`, a status, a layer, and the recipe id it teaches.
3. Run `check --sources`, then `build`, and commit both files.

Do not add an entry you could not verify in its source.

## Contact sheets for the interview

`contact_sheet.py` (Pillow) turns pictures into one file, so the user sees one image instead of six:

```
python contact_sheet.py city OUT.png [--quarter civic]          # street, landmark, skyline
python contact_sheet.py catalogue OUT.png --query "boat" --cell 256   # catalogue thumbnails, enlarged from 128 px
python contact_sheet.py styles OUT.png [profile.style.json ...] # palette cards: iamar city + the custom examples
python contact_sheet.py images OUT.png a.jpg dir/                # any pictures
```

`styles/style_cards.png` is the ready-made contrasting-looks sheet (city, harbour, desert, station). It shows palettes, not renders.
