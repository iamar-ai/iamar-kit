#!/usr/bin/env python3
"""Concept targets (kit/concept): set check, prompt, alignment, the image API call against a local
mock server (no network, no real key), the manual fallback, and the layout check. Needs Pillow + numpy.

    python kit/tests/concept/concept_test.py      prints concept_test OK
"""
from __future__ import annotations

import base64
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "concept"))
import concept  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

EXAMPLES = KIT / "concept" / "examples"
KEY = "sk-test-NEVER-WRITTEN-0123456789"


def scene(seed: int, size=(1536, 864)) -> Image.Image:
    """A greybox-like frame: sky, ground and blocks whose placement depends on the seed."""
    import random
    r = random.Random(seed)
    w, h = size
    im = Image.new("RGB", size, (150, 180, 215))
    d = ImageDraw.Draw(im)
    hz = int(h * r.uniform(0.35, 0.6))
    d.rectangle([0, hz, w, h], fill=(110, 105, 95))
    for _ in range(7):
        x = r.randint(0, w - 200)
        bw, bh = r.randint(90, 320), r.randint(120, 420)
        g = r.randint(60, 200)
        d.rectangle([x, hz - bh, x + bw, hz + r.randint(5, 60)], fill=(g, g - 10, g - 20))
        d.polygon([(x - 10, hz - bh), (x + bw + 10, hz - bh), (x + bw // 2, hz - bh - r.randint(40, 140))],
                  fill=(r.randint(60, 160), 70, 60))
    return im


def painted(im: Image.Image) -> Image.Image:
    """What a repaint that keeps the layout does: new colours and texture, same masses."""
    a = im.filter(ImageFilter.GaussianBlur(2)).convert("RGB")
    r, g, b = a.split()
    out = Image.merge("RGB", (r.point(lambda v: min(255, int(v * 1.15 + 20))), g, b.point(lambda v: int(v * 0.8))))
    noise = Image.effect_noise(out.size, 24).convert("RGB")
    return Image.blend(out, noise, 0.12)


class Mock(BaseHTTPRequestHandler):
    calls: list = []
    mode = "ok"

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        ctype = self.headers["Content-Type"]
        boundary = ctype.split("boundary=")[1].encode()
        parts = {}
        for chunk in body.split(b"--" + boundary):
            if b"Content-Disposition" not in chunk:
                continue
            head, _, data = chunk.partition(b"\r\n\r\n")
            name = head.split(b'name="')[1].split(b'"')[0].decode()
            parts[name] = data[:-2]
        Mock.calls.append({"path": self.path, "auth": self.headers.get("Authorization"), "parts": parts})
        if Mock.mode == "error":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": {"message": "Incorrect API key provided: " + KEY}}).encode())
            return
        src = Image.open(io.BytesIO(parts["image"])).convert("RGB")
        buf = io.BytesIO()
        painted(src).save(buf, "PNG")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"data": [{"b64_json": base64.b64encode(buf.getvalue()).decode()}]}).encode())


@contextlib.contextmanager
def mock_api():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    old = {k: os.environ.get(k) for k in ("IAMAR_CONCEPT_API_BASE", "OPENAI_API_KEY")}
    os.environ["IAMAR_CONCEPT_API_BASE"] = "http://127.0.0.1:%d/v1" % srv.server_address[1]
    os.environ["OPENAI_API_KEY"] = KEY
    try:
        yield
    finally:
        srv.shutdown()
        for k, v in old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def run(args) -> tuple:
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            code = concept.main([str(a) for a in args])
        except SystemExit as e:
            code = e.code
    return code, buf.getvalue()


def no_key_anywhere(d: Path):
    for p in d.rglob("*"):
        if p.is_file():
            assert KEY.encode() not in p.read_bytes(), "key written to %s" % p


def main() -> None:
    sets = sorted(EXAMPLES.glob("*.concept.json"))
    assert len(sets) >= 2, sets
    for p in sets:
        code, out = run(["check", p])
        assert code == 0 and "CONCEPT_SET_OK" in out, (p, out)
    good = json.loads(sets[0].read_text(encoding="utf-8"))

    def seeded(fn, word):
        s = copy.deepcopy(good)
        fn(s)
        errs = concept.check_set(s)
        assert any(word in e for e in errs), (word, errs)

    seeded(lambda s: s["blocks"].pop("STYLE"), "STYLE is required")
    seeded(lambda s: s["image_model"].update(api_key="sk-x"), "never put a key")
    seeded(lambda s: s["cameras"].append(copy.deepcopy(s["cameras"][0])), "duplicate")
    seeded(lambda s: s["cameras"][0].update(scene="a street"), "40+ characters")
    seeded(lambda s: s["cameras"][0].update(at=s["cameras"][0]["eye"]), "same point")
    seeded(lambda s: s["cameras"][0].update(eye=[1, 2]), "eye must be")
    seeded(lambda s: s.update(schema="x"), "schema")

    # prompt: SCENE, STYLE, LAYOUT, AVOID in that order; default LAYOUT/AVOID when a set omits them
    cam = good["cameras"][0]
    p = concept.build_prompt(good, cam)
    idx = [p.index(k + ": ") for k in ("SCENE", "STYLE", "LAYOUT", "AVOID")]
    assert idx == sorted(idx) and cam["scene"].strip() in p, p
    bare = copy.deepcopy(good)
    bare["blocks"] = {"STYLE": "Flat test style."}
    assert concept.DEFAULT_BLOCKS["AVOID"] in concept.build_prompt(bare, cam)

    # alignment: stretch to the API size of the nearest aspect, never crop
    assert concept.api_size(1536, 864) == (1536, 1024)
    assert concept.api_size(864, 1536) == (1024, 1536)
    assert concept.api_size(1000, 1000) == (1024, 1024)

    tmp = Path(tempfile.mkdtemp(prefix="concept_test_"))
    try:
        s = copy.deepcopy(good)
        s["_path"] = "x"
        W, H = s["size"]
        # cams: one --view per camera at the set's size; preview's files are renamed in camera order
        cmd = concept.cams_cmd(s, "worlds/w", tmp, 30, "iamar-world")
        assert cmd[:3] == ["iamar-world", "preview", "worlds/w"] and cmd.count("--view") == len(s["cameras"])
        assert cmd[cmd.index("--size") + 1] == "%dx%d" % (W, H)
        assert cmd[cmd.index("--view") + 1] == concept.view_arg(s["cameras"][0])
        (tmp / "raw").mkdir()
        for i, c in enumerate(s["cameras"]):
            scene(i, (W, H)).save(tmp / "raw" / ("now_%d_custom%d.png" % (i, i)))
        assert len(concept.collect_now(s, tmp)) == len(s["cameras"])
        # iamar-world shots output (A1) as the now frames: <out>/shots/<camera>_<time>.png
        sh = tmp / "a1" / "shots"
        sh.mkdir(parents=True)
        for i, c in enumerate(s["cameras"]):
            scene(i, (W, H)).save(sh / ("%s_dusk.png" % c["name"]))
        code, out = run(["cams", sets[0], "w", tmp / "a1_now", "--from-shots", tmp / "a1", "--time", "dusk"])
        assert code == 0 and ("NOW %d/%d" % (len(s["cameras"]), len(s["cameras"]))) in out, out
        code, out = run(["cams", sets[0], "w", tmp / "a1_now", "--from-shots", tmp / "a1"])
        assert code == 1 and "MISSING" in out, out

        # a now frame not at the set's size is refused before any API call
        wrong = tmp / "wrong"
        wrong.mkdir()
        scene(0, (1280, 720)).save(wrong / ("%s_now.png" % s["cameras"][0]["name"]))
        code, out = run(["paint", sets[0], wrong, "--dry-run", "--only", s["cameras"][0]["name"]])
        assert code == 1 and "1280x720" in out and not (wrong / "paint").exists(), out

        # no key: stops, says how to continue without one
        os.environ.pop("OPENAI_API_KEY", None)
        code, out = run(["paint", sets[0], tmp])
        assert code == 2 and "--provider manual" in out, out

        # the real HTTP path against the mock: auth header, fields, stretched input, aligned output
        with mock_api():
            code, out = run(["paint", sets[0], tmp])
            assert code == 0 and "PAINT_OK" in out, out
            assert len(Mock.calls) == len(s["cameras"])
            c0 = Mock.calls[0]
            assert c0["path"] == "/v1/images/edits" and c0["auth"] == "Bearer " + KEY
            assert c0["parts"]["model"].decode() == s["image_model"]["model"]
            assert c0["parts"]["size"].decode() == "1536x1024"
            assert c0["parts"]["prompt"].decode().startswith("SCENE: ")
            assert Image.open(io.BytesIO(c0["parts"]["image"])).size == (1536, 1024)
            for c in s["cameras"]:
                assert Image.open(tmp / ("%s_target.png" % c["name"])).size == (W, H)
                rec = json.loads((tmp / ("%s_target.json" % c["name"])).read_text(encoding="utf-8"))
                assert rec["model"] == s["image_model"]["model"] and rec["now_sha256"] and rec["prompt"]
            # an API error that echoes the key is reported with the key redacted
            Mock.mode = "error"
            (tmp / "err").mkdir()
            shutil.copy(tmp / ("%s_now.png" % s["cameras"][0]["name"]), tmp / "err")
            code, out = run(["paint", sets[0], tmp / "err", "--only", s["cameras"][0]["name"]])
            Mock.mode = "ok"
            assert code == 1 and "HTTP 401" in out and KEY not in out and "<key>" in out, out
        no_key_anywhere(tmp)

        # compare: aligned sheets for the reviewer
        code, out = run(["compare", sets[0], tmp])
        assert code == 0 and "COMPARE_OK" in out, out
        assert Image.open(tmp / ("%s_compare.png" % s["cameras"][0]["name"])).size[0] == 4 * 480
        first = s["cameras"][0]["name"]
        # a blank painting (failed generation) fails; so does a target not at the camera's size
        Image.new("RGB", (W, H), (128, 128, 128)).save(tmp / ("%s_target.png" % first))
        code, out = run(["compare", sets[0], tmp])
        assert code == 1 and ("FAIL %s" % first) in out and "blank" in out, out
        painted(scene(0, (W, H))).resize((1536, 1024)).save(tmp / ("%s_target.png" % first))
        code, out = run(["compare", sets[0], tmp])
        assert code == 1 and "not aligned" in out, out
        # the optional edge threshold: off by default, enforced when given
        painted(scene(99, (W, H))).save(tmp / ("%s_target.png" % first))
        code, out = run(["compare", sets[0], tmp])
        assert code == 0, out
        code, out = run(["compare", sets[0], tmp, "--min-edge-corr", "0.99"])
        assert code == 1 and "min-edge-corr" in out, out

        # manual fallback: prepared input + prompt, then import a painting made elsewhere
        man = tmp / "manual"
        man.mkdir()
        shutil.copy(tmp / ("%s_now.png" % first), man / ("%s_now.png" % first))
        code, out = run(["paint", sets[0], man, "--provider", "manual", "--only", first])
        assert code == 0 and "PREPARED" in out, out
        inp = man / "paint" / ("%s_input_1536x1024.png" % first)
        assert Image.open(inp).size == (1536, 1024)
        assert (man / "paint" / ("%s_prompt.txt" % first)).read_text(encoding="utf-8").startswith("SCENE: ")
        painted(Image.open(inp)).save(man / "by_hand.png")
        code, out = run(["import", sets[0], man, first, man / "by_hand.png"])
        assert code == 0 and Image.open(man / ("%s_target.png" % first)).size == (W, H), out
        code, out = run(["compare", sets[0], man, "--now", man])
        assert ("OK   %s" % first) in out, out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("concept_test OK")


if __name__ == "__main__":
    main()
