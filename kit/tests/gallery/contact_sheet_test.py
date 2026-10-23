#!/usr/bin/env python3
"""kit/gallery/contact_sheet.py: city, catalogue and style-card sheets build; the shipped
style_cards.png shows >= 3 contrasting looks; the interview docs name the command.
python3 kit/tests/gallery/contact_sheet_test.py"""
import glob, json, os, subprocess, sys, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TOOL = os.path.join(ROOT, "kit", "gallery", "contact_sheet.py")
fails, n = [], 0


def ok(cond, msg):
    global n
    n += 1
    if not cond:
        fails.append(msg)


def run(*a):
    return subprocess.run([sys.executable, TOOL] + list(a), capture_output=True, text=True)


try:
    from PIL import Image
except ImportError:
    print("SKIP: Pillow not installed")
    sys.exit(0)

with tempfile.TemporaryDirectory() as t:
    out = os.path.join(t, "c.png")
    r = run("city", out, "--quarter", "civic")
    ok(r.returncode == 0 and "3 pictures" in r.stdout, "city sheet for one quarter: %s%s" % (r.stdout, r.stderr))
    r = run("styles", out)
    n_styles = len(glob.glob(os.path.join(ROOT, "kit/style/schema/examples/*.style.json"))) + 1
    ok(r.returncode == 0 and ("%d pictures" % n_styles) in r.stdout, "styles sheet: %s%s" % (r.stdout, r.stderr))
    ok(n_styles >= 4, "need the iamar profile plus >= 3 examples for contrast, got %d" % n_styles)
    cat = json.load(open(os.path.join(ROOT, "kit/catalog/catalog.json")))["entries"]
    name = next(e["name"] for e in cat if e.get("thumbnail") and os.path.isfile(os.path.join(ROOT, "kit", e["thumbnail"])))
    r = run("catalogue", out, "--query", name, "--cell", "256")
    ok(r.returncode == 0, "catalogue sheet for %r: %s" % (name, r.stderr))
    ok(Image.open(out).width >= 256, "catalogue sheet cell is enlarged to --cell")
    ok(run("catalogue", out, "--query", "zzzznomatch").returncode != 0, "no match exits non-zero")
    ok(run("images", out, os.path.join(t, "missing.png")).returncode != 0, "missing image exits non-zero")

cards = os.path.join(ROOT, "kit", "gallery", "styles", "style_cards.png")
ok(os.path.isfile(cards) and Image.open(cards).width >= 1000, "kit/gallery/styles/style_cards.png shipped")
for doc in ("kit/interview/PROTOCOL.md", "kit/interview/tracks/README.md"):
    ok("contact_sheet.py styles" in open(os.path.join(ROOT, doc), encoding="utf-8").read(), doc + " names the styles command")

print("%d checks, %d failed" % (n, len(fails)))
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
