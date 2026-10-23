#!/usr/bin/env python3
"""kit/gallery/city: every quarter of the iamar style profile has a street, landmark and skyline
view; every view has a small 960x540 JPEG; the interview's B3 docs link the folder; the export
rules give the pictures a licence row.  python3 kit/tests/gallery/city_views_test.py"""
import json, os, struct, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CITY = os.path.join(ROOT, "kit", "gallery", "city")
fails, n = [], 0


def ok(cond, msg):
    global n
    n += 1
    if not cond:
        fails.append(msg)


def jpeg_size(path):
    with open(path, "rb") as f:
        b = f.read()
    if b[:2] != b"\xff\xd8":
        return None
    i = 2
    while i < len(b) - 9:
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None


spec = json.load(open(os.path.join(CITY, "views.json")))
style = json.load(open(os.path.join(ROOT, "kit", "style", "iamar", "style.json")))
quarters = set(style["regions"].keys())
seen = {}
for v in spec["views"]:
    for k in ("id", "quarter", "kind", "title", "eye", "target"):
        ok(k in v, "%s: missing %s" % (v.get("id"), k))
    ok(v["id"] == "%s_%s" % (v["quarter"], v["kind"]), "%s: id is not <quarter>_<kind>" % v["id"])
    ok(v["quarter"] in quarters, "%s: quarter not in style.json regions" % v["id"])
    seen.setdefault(v["quarter"], set()).add(v["kind"])
    p = os.path.join(CITY, v["id"] + ".jpg")
    ok(os.path.exists(p), "%s.jpg missing" % v["id"])
    if os.path.exists(p):
        ok(jpeg_size(p) == (960, 540), "%s.jpg is not a 960x540 JPEG" % v["id"])
        ok(os.path.getsize(p) <= 250_000, "%s.jpg over 250 KB" % v["id"])
for q in quarters:
    ok(seen.get(q) == {"street", "landmark", "skyline"}, "quarter %s lacks street/landmark/skyline" % q)
readme = open(os.path.join(CITY, "README.md")).read()
for v in spec["views"]:
    ok(v["id"] + ".jpg" in readme, "README does not list %s.jpg" % v["id"])
for doc in ("kit/interview/common.md", "kit/interview/tracks/README.md", "kit/interview/PROTOCOL.md"):
    ok("gallery/city/" in open(os.path.join(ROOT, doc)).read(), "%s does not link kit/gallery/city" % doc)
rules = json.load(open(os.path.join(ROOT, "kit", "export", "rules.json")))
ok(any(r["glob"].startswith("kit/gallery/city") for r in rules["asset_licences"]), "export rules: no licence row for kit/gallery/city")
if fails:
    print("\n".join("FAIL " + f for f in fails))
    print("city_views_test: %d/%d passed" % (n - len(fails), n))
    sys.exit(1)
print("city_views_test: %d/%d passed" % (n, n))
