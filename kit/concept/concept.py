#!/usr/bin/env python3
"""Concept targets: paint what a view SHOULD look like, from the same camera, and compare.

The iamar city's look was set by painted concept frames (docs/masterplan_targets in
the iamar browser source (not public), technique TD012): a fixed camera's screenshot is repainted by an image model
and every later pass is judged against the painting from that SAME camera. This packages
that workflow for any world. Steps (one concept set file drives all of them):

    concept.py check   SET.json                       the set is complete (cameras, prompts, blocks)
    concept.py cams    SET.json WORLD OUT [--run]     the 'now' frames: iamar-world preview, one
                                                      --view per camera -> OUT/<camera>_now.png
                                                      (--collect: rename frames you rendered with
                                                      the printed command yourself; --from-shots
                                                      DIR [--time day]: use iamar-world shots output)
    concept.py prompt  SET.json CAMERA                print the prompt sent for one camera
    concept.py paint   SET.json OUT [--only a,b] [--dry-run] [--provider openai|manual]
                                                      OUT/<camera>_now.png -> OUT/<camera>_target.png
    concept.py import  SET.json OUT CAMERA IMAGE      a painting made elsewhere (manual fallback)
                                                      -> OUT/<camera>_target.png, resized back
    concept.py compare SET.json OUT [--min-edge-corr X] [--now DIR]
                                                      OUT/<camera>_compare.png: now | target |
                                                      blend | now's edges over the target

Alignment (why the pixels line up): the image API only takes a few sizes (1536x1024,
1024x1536, 1024x1024). The now frame is STRETCHED (never cropped or padded) to the API size
of the nearest aspect ratio, painted, and stretched back to the camera size. Cropping or
padding shifts the layout and the painting no longer overlays the camera.

API key: the user supplies their own. It is read only from the environment variable named
by the set (default OPENAI_API_KEY), never from the command line, never written to any file
or log. No key -> paint stops with a message pointing at --provider manual (or --dry-run).

Needs Python 3.9+ and Pillow (numpy for compare). No other packages: the API call is plain
HTTPS with multipart/form-data.
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

SCHEMA = "iamar-concept/1"
API_SIZES = [(1536, 1024), (1024, 1536), (1024, 1024)]
DEFAULT_BLOCKS = {
    # Style-independent: keep the camera so the painting overlays the frame.
    "LAYOUT": ("Keep the camera, horizon, perspective and the layout of streets, buildings, walls, "
               "towers, water and open ground from the input screenshot; repaint every surface and "
               "replace placeholder blocks with the described objects at the same positions and sizes."),
    # Style-independent: originality and the things that ruin a target.
    "AVOID": ("Original design only: no copyrighted game assets, characters, logos, emblems or text "
              "from existing games or films; no readable lettering or signage text; no watermark, "
              "no frame or border, no UI."),
}
DEFAULT_MODEL = {"provider": "openai", "model": "gpt-image-1.5", "quality": "high",
                 "input_fidelity": "low", "key_env": "OPENAI_API_KEY",
                 "base_url_env": "IAMAR_CONCEPT_API_BASE", "base_url": "https://api.openai.com/v1",
                 "timeout_s": 300}
MIN_STD = 0.02   # a target this flat (0-1 grey std) is a blank or failed painting


def die(msg: str, code: int = 2):
    print("ERROR " + msg)
    sys.exit(code)


def pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        die("concept needs Pillow: python -m pip install pillow")


# ---------------------------------------------------------------- set file

def load_set(path) -> dict:
    p = Path(path)
    try:
        s = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die("cannot read concept set %s: %s" % (p, e))
    s["_path"] = str(p)
    return s


def check_set(s: dict) -> list:
    errs = []
    if s.get("schema") != SCHEMA:
        errs.append("schema must be %r" % SCHEMA)
    size = s.get("size")
    if not (isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and 64 <= v <= 4096 for v in size)):
        errs.append("size must be [width, height] in pixels (64-4096)")
    blocks = s.get("blocks") or {}
    if not str(blocks.get("STYLE", "")).strip():
        errs.append("blocks.STYLE is required: the look of THIS world (from its style profile / style bible)")
    for k in blocks:
        if k not in ("STYLE", "LAYOUT", "AVOID"):
            errs.append("blocks.%s unknown (STYLE, LAYOUT, AVOID; SCENE is per camera)" % k)
    model = s.get("image_model") or {}
    if model.get("provider", "openai") not in ("openai", "manual"):
        errs.append("image_model.provider must be openai or manual")
    for k in ("api_key", "key", "token"):
        if k in model:
            errs.append("image_model.%s: never put a key in the set; name the environment variable in key_env" % k)
    cams = s.get("cameras")
    if not isinstance(cams, list) or not cams:
        errs.append("cameras: at least one camera")
        cams = []
    seen = set()
    for i, c in enumerate(cams):
        name = str(c.get("name", ""))
        where = "cameras[%d] %s" % (i, name or "?")
        if not name or not all(ch.isalnum() or ch in "_-" for ch in name):
            errs.append(where + ": name must be letters, digits, _ or -")
        if name in seen:
            errs.append(where + ": duplicate name")
        seen.add(name)
        for k in ("eye", "at"):
            v = c.get(k)
            if not (isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v)):
                errs.append(where + ": %s must be [x, y, z] world metres" % k)
        if c.get("eye") == c.get("at"):
            errs.append(where + ": eye and at are the same point")
        if len(str(c.get("scene", "")).strip()) < 40:
            errs.append(where + ": scene must describe what this view should show (40+ characters)")
        if "fov" in c and not (20 <= float(c["fov"]) <= 120):
            errs.append(where + ": fov out of range 20-120")
    return errs


def cameras(s: dict, only=None) -> list:
    cams = s["cameras"]
    if only:
        want = [o for o in only.split(",") if o]
        unknown = [o for o in want if o not in [c["name"] for c in cams]]
        if unknown:
            die("unknown camera(s): " + ", ".join(unknown))
        cams = [c for c in cams if c["name"] in want]
    return cams


def model_cfg(s: dict) -> dict:
    m = dict(DEFAULT_MODEL)
    m.update(s.get("image_model") or {})
    return m


def build_prompt(s: dict, cam: dict) -> str:
    blocks = dict(DEFAULT_BLOCKS)
    blocks.update({k: v for k, v in (s.get("blocks") or {}).items() if str(v).strip()})
    return "\n\n".join(["SCENE: " + cam["scene"].strip(), "STYLE: " + blocks["STYLE"].strip(),
                        "LAYOUT: " + blocks["LAYOUT"].strip(), "AVOID: " + blocks["AVOID"].strip()])


def api_size(w: int, h: int):
    """The API size whose aspect ratio is nearest the camera's (stretch, never crop)."""
    r = w / h
    return min(API_SIZES, key=lambda wh: abs((wh[0] / wh[1]) / r - 1))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- cams

def view_arg(cam: dict) -> str:
    e, a = cam["eye"], cam["at"]
    return "%g,%g,%g>%g,%g,%g" % (e[0], e[1], e[2], a[0], a[1], a[2])


def cams_cmd(s: dict, world: str, out: Path, frames: int, iamar_world: str) -> list:
    cmd = [iamar_world, "preview", world, str(out / "raw" / "now"), "--size", "%dx%d" % tuple(s["size"]),
           "--frames", str(frames)]
    for c in s["cameras"]:
        cmd += ["--view", view_arg(c)]
    return cmd


def from_shots(s: dict, out: Path, shots: Path, time: str) -> list:
    """Use iamar-world shots output (A1: <out>/shots/<camera>_<time>.png) as the now frames.
    Name the concept cameras like the shots.json cameras."""
    done = []
    for c in s["cameras"]:
        for d in (shots / "shots", shots):
            src = d / ("%s_%s.png" % (c["name"], time))
            if src.is_file():
                dst = out / ("%s_now.png" % c["name"])
                dst.write_bytes(src.read_bytes())
                done.append(dst)
                break
        else:
            print("MISSING %s: no %s_%s.png in %s" % (c["name"], c["name"], time, shots))
    return done


def default_launcher() -> str:
    kit = Path(__file__).resolve().parents[1]
    return str(kit / ("iamar-world.cmd" if os.name == "nt" else "iamar-world"))


def run_launcher(cmd: list) -> int:
    """Windows runs kit/iamar-world.cmd through cmd.exe, where an unquoted '>' (in every --view)
    is a redirect: quote each argument there. Elsewhere run the list as is."""
    if os.name == "nt" and cmd[0].lower().endswith((".cmd", ".bat")):
        return subprocess.call(" ".join('"%s"' % c for c in cmd))
    return subprocess.call(cmd)


def collect_now(s: dict, out: Path) -> list:
    """preview writes <prefix>_<i>_custom<i>.png in camera order: rename to <camera>_now.png."""
    done = []
    for i, c in enumerate(s["cameras"]):
        src = out / "raw" / ("now_%d_custom%d.png" % (i, i))
        if src.is_file():
            dst = out / ("%s_now.png" % c["name"])
            dst.write_bytes(src.read_bytes())
            done.append(dst)
    return done


# ---------------------------------------------------------------- paint

def stretch(Image, src: Path, size) -> bytes:
    import io
    im = Image.open(src).convert("RGB")
    if im.size != tuple(size):
        im = im.resize(tuple(size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def multipart(fields: dict, files: dict):
    boundary = "iamar-concept-" + uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, k, v)).encode("utf-8")
    for k, (fname, data, ctype) in files.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
                % (boundary, k, fname, ctype)).encode("utf-8")
        out += data + b"\r\n"
    out += ("--%s--\r\n" % boundary).encode("utf-8")
    return bytes(out), "multipart/form-data; boundary=" + boundary


def openai_edit(m: dict, key: str, prompt: str, png: bytes, size) -> bytes:
    base = os.environ.get(m["base_url_env"], "") or m["base_url"]
    fields = {"model": m["model"], "prompt": prompt, "size": "%dx%d" % tuple(size), "n": "1",
              "quality": m["quality"]}
    if m.get("input_fidelity"):
        fields["input_fidelity"] = m["input_fidelity"]
    body, ctype = multipart(fields, {"image": ("now.png", png, "image/png")})
    req = urllib.request.Request(base.rstrip("/") + "/images/edits", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=float(m["timeout_s"])) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400].replace(key, "<key>")
        raise RuntimeError("image API HTTP %d: %s" % (e.code, detail)) from None
    except urllib.error.URLError as e:
        raise RuntimeError("image API unreachable: %s" % e.reason) from None
    item = (data.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    raise RuntimeError("image API answered without b64_json image data")


def save_target(Image, img_bytes: bytes, size, dst: Path):
    import io
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    if im.size != tuple(size):
        im = im.resize(tuple(size), Image.Resampling.LANCZOS)
    im.save(dst, "PNG")


def record(out: Path, cam: dict, info: dict):
    p = out / ("%s_target.json" % cam["name"])
    info = dict(info, camera=cam["name"], eye=cam["eye"], at=cam["at"],
                date=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    p.write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")


def cmd_paint(s: dict, out: Path, only, dry: bool, provider) -> int:
    Image = pil()
    m = model_cfg(s)
    provider = provider or m["provider"]
    W, H = s["size"]
    asz = api_size(W, H)
    key = ""
    if provider == "openai" and not dry:
        key = os.environ.get(m["key_env"], "").strip()
        if not key:
            die("no image API key: set the environment variable %s to YOUR key (it is never stored), "
                "or run with --provider manual (paint by hand / another tool, then concept import) "
                "or --dry-run" % m["key_env"])
    fails = 0
    for cam in cameras(s, only):
        now = out / ("%s_now.png" % cam["name"])
        if not now.is_file():
            print("FAIL %s: no now frame %s (run concept cams first)" % (cam["name"], now))
            fails += 1
            continue
        with Image.open(now) as im:
            got = im.size
        if got != (W, H):
            print("FAIL %s: now frame is %dx%d, the set says %dx%d: the painting would not overlay the camera "
                  "(windowed preview needs --size honoured: re-shoot)" % (cam["name"], got[0], got[1], W, H))
            fails += 1
            continue
        png = stretch(Image, now, asz)
        prompt = build_prompt(s, cam)
        if dry or provider == "manual":
            (out / "paint").mkdir(exist_ok=True)
            (out / "paint" / ("%s_input_%dx%d.png" % (cam["name"], *asz))).write_bytes(png)
            (out / "paint" / ("%s_prompt.txt" % cam["name"])).write_text(prompt + "\n", encoding="utf-8")
            print("PREPARED %s input=%dx%d prompt=%d chars -> %s" % (cam["name"], asz[0], asz[1], len(prompt),
                                                                    out / "paint"))
            continue
        try:
            img = openai_edit(m, key, prompt, png, asz)
        except RuntimeError as e:
            print("FAIL %s: %s" % (cam["name"], e))
            fails += 1
            continue
        dst = out / ("%s_target.png" % cam["name"])
        save_target(Image, img, (W, H), dst)
        record(out, cam, {"provider": "openai", "model": m["model"], "quality": m["quality"],
                          "input_fidelity": m.get("input_fidelity"), "api_size": "%dx%d" % asz,
                          "prompt": prompt, "now_sha256": sha(now.read_bytes()),
                          "target_sha256": sha(dst.read_bytes())})
        print("TARGET %s -> %s" % (cam["name"], dst))
    print("PAINT_%s" % ("OK" if not fails else "FAIL %d" % fails))
    return 1 if fails else 0


def cmd_import(s: dict, out: Path, name: str, image: Path) -> int:
    Image = pil()
    cam = cameras(s, name)[0]
    data = Path(image).read_bytes()
    dst = out / ("%s_target.png" % cam["name"])
    with Image.open(image) as im:
        src_size = im.size
    W, H = s["size"]
    r_src, r_cam = src_size[0] / src_size[1], W / H
    asz = api_size(W, H)
    if abs(r_src / r_cam - 1) > 0.02 and abs(r_src / (asz[0] / asz[1]) - 1) > 0.02:
        print("WARN %s: painting is %dx%d, neither the camera's aspect nor the stretched input's (%dx%d): "
              "it will not overlay the frame" % (name, src_size[0], src_size[1], asz[0], asz[1]))
    save_target(Image, data, (W, H), dst)
    record(out, cam, {"provider": "manual", "source": Path(image).name, "source_size": list(src_size),
                      "prompt": build_prompt(s, cam), "target_sha256": sha(dst.read_bytes())})
    print("TARGET %s -> %s" % (name, dst))
    return 0


# ---------------------------------------------------------------- compare

def edges(np, Image, path: Path, width=320):
    im = Image.open(path).convert("L")
    h = max(1, round(im.size[1] * width / im.size[0]))
    a = np.asarray(im.resize((width, h), Image.Resampling.BILINEAR), dtype=np.float64) / 255.0
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    g = np.hypot(gx, gy)
    # blur 5x5 box: a painting moves edges by a few pixels; that is still the same layout
    k = 2
    p = np.pad(g, k, mode="edge")
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    n = 2 * k + 1
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]) / (n * n)


def edge_corr(np, Image, a: Path, b: Path) -> float:
    ea, eb = edges(np, Image, a), edges(np, Image, b)
    if ea.shape != eb.shape:
        return -1.0
    ea, eb = ea - ea.mean(), eb - eb.mean()
    d = float(np.sqrt((ea * ea).sum() * (eb * eb).sum()))
    return float((ea * eb).sum() / d) if d else 0.0


def sheet(np, Image, now: Path, target: Path, dst: Path, width=480):
    a = Image.open(now).convert("RGB")
    b = Image.open(target).convert("RGB").resize(a.size, Image.Resampling.LANCZOS)
    blend = Image.blend(a, b, 0.5)
    ea = edges(np, Image, now, width=a.size[0])
    # the strongest edges only, and never sky banding or ground noise (absolute floor)
    m = (ea > max(float(np.percentile(ea, 92)), 0.03)).astype(np.uint8) * 255
    over = np.asarray(b).copy()
    over[m > 0] = (255, 40, 40)
    tiles = [a, b, blend, Image.fromarray(over)]
    h = round(a.size[1] * width / a.size[0])
    out = Image.new("RGB", (width * 4, h))
    for i, t in enumerate(tiles):
        out.paste(t.resize((width, h), Image.Resampling.LANCZOS), (i * width, 0))
    out.save(dst, "PNG")


def cmd_compare(s: dict, out: Path, min_corr: float, now_dir) -> int:
    Image = pil()
    try:
        import numpy as np
    except ImportError:
        die("concept compare needs numpy: python -m pip install numpy")
    now_dir = Path(now_dir) if now_dir else out
    fails, rows = 0, []
    W, H = s["size"]
    for cam in s["cameras"]:
        now = now_dir / ("%s_now.png" % cam["name"])
        tgt = out / ("%s_target.png" % cam["name"])
        if not now.is_file() or not tgt.is_file():
            print("FAIL %s: missing %s" % (cam["name"], "now frame" if not now.is_file() else "target"))
            fails += 1
            continue
        with Image.open(now) as a, Image.open(tgt) as b:
            sizes = (a.size, b.size)
        if sizes[0] != sizes[1] or sizes[1] != (W, H):
            print("FAIL %s: sizes now %s target %s, set %dx%d (not aligned)" % (cam["name"], sizes[0], sizes[1], W, H))
            fails += 1
            continue
        corr = edge_corr(np, Image, now, tgt)
        dst = out / ("%s_compare.png" % cam["name"])
        sheet(np, Image, now, tgt, dst)
        std = float(np.asarray(Image.open(tgt).convert("L"), dtype=np.float64).std() / 255.0)
        why = ""
        if std < MIN_STD:
            why = " (target is blank: grey std %.3f)" % std
        elif min_corr is not None and corr < min_corr:
            why = " (edge_corr < --min-edge-corr %.2f)" % min_corr
        fails += 1 if why else 0
        rows.append({"camera": cam["name"], "edge_corr": round(corr, 3), "target_std": round(std, 3),
                     "ok": not why, "sheet": dst.name})
        # edge_corr is information, not a verdict: on the city's 14 real targets it does not
        # separate a painting of this view from a painting of another (README, FAILED technique).
        print("%s %s edge_corr=%.3f%s -> %s" % ("FAIL" if why else "OK  ", cam["name"], corr, why, dst))
    (out / "compare.json").write_text(json.dumps({"min_edge_corr": min_corr, "views": rows}, indent=1) + "\n",
                                      encoding="utf-8")
    print("COMPARE_%s %d views" % ("OK" if not fails else "FAIL", len(rows)))
    return 1 if fails else 0


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="concept", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check"); p.add_argument("set")
    p = sub.add_parser("prompt"); p.add_argument("set"); p.add_argument("camera")
    p = sub.add_parser("cams"); p.add_argument("set"); p.add_argument("world"); p.add_argument("out")
    p.add_argument("--run", action="store_true", help="run iamar-world preview (default: print the command)")
    p.add_argument("--collect", action="store_true", help="only rename frames the printed command already wrote")
    p.add_argument("--from-shots", metavar="DIR", help="take the now frames from iamar-world shots output")
    p.add_argument("--time", default="day", help="with --from-shots: which time of day (default day)")
    p.add_argument("--frames", type=int, default=60)
    p.add_argument("--iamar-world", default=default_launcher())
    p = sub.add_parser("paint"); p.add_argument("set"); p.add_argument("out")
    p.add_argument("--only"); p.add_argument("--dry-run", action="store_true")
    p.add_argument("--provider", choices=["openai", "manual"])
    p = sub.add_parser("import"); p.add_argument("set"); p.add_argument("out"); p.add_argument("camera")
    p.add_argument("image")
    p = sub.add_parser("compare"); p.add_argument("set"); p.add_argument("out")
    p.add_argument("--min-edge-corr", type=float, default=None, help="optional; off by default (README)"); p.add_argument("--now")
    a = ap.parse_args(argv)
    s = load_set(a.set)
    errs = check_set(s)
    if errs:
        for e in errs:
            print("ERROR " + e)
        return 1
    if a.cmd == "check":
        print("CONCEPT_SET_OK %d cameras %dx%d" % (len(s["cameras"]), *s["size"]))
        return 0
    if a.cmd == "prompt":
        print(build_prompt(s, cameras(s, a.camera)[0]))
        return 0
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "cams":
        (out / "raw").mkdir(exist_ok=True)
        cmd = cams_cmd(s, a.world, out, a.frames, a.iamar_world)
        print("CAMS " + " ".join(shlex.quote(c) for c in cmd))
        if a.from_shots or a.collect:
            got = from_shots(s, out, Path(a.from_shots), a.time) if a.from_shots else collect_now(s, out)
            print("NOW %d/%d frames" % (len(got), len(s["cameras"])))
            return 0 if len(got) == len(s["cameras"]) else 1
        if a.run:
            rc = run_launcher(cmd)
            got = collect_now(s, out)
            print("NOW %d/%d frames" % (len(got), len(s["cameras"])))
            return 0 if rc == 0 and len(got) == len(s["cameras"]) else 1
        return 0
    if a.cmd == "paint":
        return cmd_paint(s, out, a.only, a.dry_run, a.provider)
    if a.cmd == "import":
        return cmd_import(s, out, a.camera, Path(a.image))
    return cmd_compare(s, out, a.min_edge_corr, a.now)


if __name__ == "__main__":
    sys.exit(main())
