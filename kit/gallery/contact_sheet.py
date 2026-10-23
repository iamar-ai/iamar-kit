#!/usr/bin/env python3
"""One picture instead of six: contact sheets for the design interview (needs Pillow).

    python3 kit/gallery/contact_sheet.py images  OUT.png a.jpg dir/ ...        [--cols 3 --cell 480]
    python3 kit/gallery/contact_sheet.py city    OUT.png [--quarter civic]     the city gallery (street/landmark/skyline)
    python3 kit/gallery/contact_sheet.py catalogue OUT.png --query "boat" [--limit 12 --cell 256]
    python3 kit/gallery/contact_sheet.py styles  OUT.png [profile.style.json ...]   palette cards, default: the contrasting set

`catalogue` picks entries whose name, description or category contains every query word
(or --ids), and enlarges the stored 128 px thumbnail to --cell (default 256) so a user can judge it.
`styles` draws one card per style profile (name, mood, palette swatches); the default set is the
iamar city plus the custom examples in kit/style/schema/examples, so "three contrasting looks"
for the track question (interview/PROTOCOL.md section 5) is one command.  The cards are palettes,
not renders: say so when you show them.
"""
import argparse
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
BG = (24, 26, 30)
FG = (235, 235, 235)


def font(size, bold=False):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),
              "C:/Windows/Fonts/%s.ttf" % ("arialbd" if bold else "arial"),
              "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def sheet(items, cols, cell, out, title=None, label_h=None, aspect=0.75):
    """items: list of (PIL image or None, label). Cells keep aspect ratio, never crop."""
    if not items:
        sys.exit("contact_sheet: nothing to draw")
    cols = max(1, min(cols, len(items)))
    rows = -(-len(items) // cols)
    label_h = label_h if label_h is not None else min(30, max(18, cell // 14))
    pad, head = 8, (36 if title else 0)
    cw, ch = cell, int(cell * aspect) + label_h
    img = Image.new("RGB", (cols * (cw + pad) + pad, rows * (ch + pad) + pad + head), BG)
    d = ImageDraw.Draw(img)
    if title:
        d.text((pad, 8), title, fill=FG, font=font(18, True))
    f = font(max(11, label_h - 6))
    for i, (pic, label) in enumerate(items):
        x, y = pad + (i % cols) * (cw + pad), head + pad + (i // cols) * (ch + pad)
        if pic is not None:
            pic = pic.convert("RGB")
            pic.thumbnail((cw, ch - label_h), Image.LANCZOS)
            img.paste(pic, (x + (cw - pic.width) // 2, y + (ch - label_h - pic.height) // 2))
        if label:
            d.text((x + 2, y + ch - label_h + 2), label[:max(8, cw // 8)], fill=FG, font=f)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out)
    print("wrote %s (%dx%d, %d pictures)" % (out, img.width, img.height, len(items)))


def expand(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += sorted(f for f in glob.glob(os.path.join(p, "*")) if f.lower().endswith(IMG_EXT))
        else:
            files += sorted(glob.glob(p)) or [p]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        sys.exit("contact_sheet: not found: %s" % ", ".join(missing))
    return files


def cmd_images(a):
    files = expand(a.inputs)
    sheet([(Image.open(f), os.path.splitext(os.path.basename(f))[0]) for f in files], a.cols, a.cell, a.out, a.title)


def cmd_city(a):
    d = os.path.join(HERE, "city")
    files = [f for f in expand([d]) if not a.quarter or os.path.basename(f).startswith(a.quarter + "_")]
    if not files:
        sys.exit("contact_sheet: no city pictures for quarter %r in %s" % (a.quarter, d))
    sheet([(Image.open(f), os.path.splitext(os.path.basename(f))[0]) for f in files], a.cols, a.cell, a.out,
          a.title or "iamar city")


def cmd_catalogue(a):
    cat = json.load(open(os.path.join(KIT, "catalog", "catalog.json"), encoding="utf-8"))["entries"]
    words = [w.lower() for w in (a.query or "").split()]
    ids = set(a.ids or [])
    hits = []
    for e in cat:
        hay = " ".join(str(e.get(k, "")) for k in ("name", "description", "category")).lower()
        if (ids and e["id"] in ids) or (not ids and words and all(w in hay for w in words)):
            hits.append(e)
    if not hits:
        sys.exit("contact_sheet: no catalogue entry matches (try fewer words; `iamar-world assets search`)")
    items = []
    for e in hits[:a.limit]:
        t = os.path.join(KIT, e["thumbnail"]) if e.get("thumbnail") else None
        items.append((Image.open(t) if t and os.path.isfile(t) else None, "%s [%s]" % (e["name"], e["id"][:6])))
    note = "" if len(hits) <= a.limit else " (%d more, raise --limit)" % (len(hits) - a.limit)
    sheet(items, a.cols, a.cell, a.out, a.title or ("catalogue: " + (a.query or ", ".join(ids))) + note)


def default_profiles():
    ex = os.path.join(KIT, "style", "schema", "examples")
    return [os.path.join(KIT, "style", "iamar", "style.json")] + sorted(glob.glob(os.path.join(ex, "*.style.json")))


def draw_card(profile):
    w, h = 560, 380
    img = Image.new("RGB", (w, h), (36, 38, 44))
    d = ImageDraw.Draw(img)
    d.text((14, 12), profile.get("name", profile["id"]).split(" (")[0], fill=FG, font=font(19, True))
    desc = profile.get("description", "").split(". ")[0][:150]
    words, line, y = desc.split(), "", 44
    for wd in words:
        if len(line) + len(wd) > 62:
            d.text((14, y), line, fill=(190, 190, 190), font=font(13)); y += 17; line = ""
        line += wd + " "
    d.text((14, y), line, fill=(190, 190, 190), font=font(13))
    swatches = [(k, v["hex"]) for k, v in profile.get("palette", {}).items() if "hex" in v][:8]
    if not swatches:  # an extension profile keeps its own colours in its regions
        for rn, r in profile.get("regions", {}).items():
            for k, v in r.items():
                for hx in ([v] if isinstance(v, str) else v if isinstance(v, list) else []):
                    if isinstance(hx, str) and hx.startswith("#") and (k, hx) not in swatches:
                        swatches.append(("%s %s" % (rn, k), hx))
        swatches = swatches[:8]
    sw, top = 124, 140
    for i, (k, hx) in enumerate(swatches):
        x, yy = 14 + (i % 4) * (sw + 8), top + (i // 4) * 78
        d.rectangle([x, yy, x + sw, yy + 52], fill=hx, outline=(90, 90, 90))
        d.text((x, yy + 55), k[:18], fill=FG, font=font(12))
    moods = [r.get("mood") for r in profile.get("regions", {}).values() if r.get("mood")][:1]
    d.text((14, h - 22), ("mood: " + "; ".join(moods))[:70], fill=(170, 170, 170), font=font(12))
    return img


def cmd_styles(a):
    paths = a.profiles or default_profiles()
    items = []
    for p in paths:
        prof = json.load(open(p, encoding="utf-8"))
        items.append((draw_card(prof), ""))
    sheet(items, a.cols, 560, a.out, a.title or "style palettes (palette cards, not renders)", label_h=0, aspect=380 / 560)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def common(p, cols, cell):
        p.add_argument("out")
        p.add_argument("--cols", type=int, default=cols)
        p.add_argument("--cell", type=int, default=cell, help="cell width in px")
        p.add_argument("--title")
    p = sp.add_parser("images"); common(p, 3, 480); p.add_argument("inputs", nargs="+"); p.set_defaults(fn=cmd_images)
    p = sp.add_parser("city"); common(p, 3, 480); p.add_argument("--quarter"); p.set_defaults(fn=cmd_city)
    p = sp.add_parser("catalogue"); common(p, 4, 256)
    p.add_argument("--query"); p.add_argument("--ids", nargs="*"); p.add_argument("--limit", type=int, default=12)
    p.set_defaults(fn=cmd_catalogue)
    p = sp.add_parser("styles"); common(p, 2, 560); p.add_argument("profiles", nargs="*"); p.set_defaults(fn=cmd_styles)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
