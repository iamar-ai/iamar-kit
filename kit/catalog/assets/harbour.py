#!/usr/bin/env python3
"""Record the catalogue's harbour set (kit/catalog/assets/harbour/) in kit/catalog/sources/harbour.json,
which catalog.py turns into entries: nine models written by export_harbour.gd (two boats, a
bollard, a harbour bell, a net pile, a gull, and the fish hall's slab, crates and drying net) and three sounds made here (sea, bell, gulls).

  python3 kit/catalog/assets/harbour.py sounds     synthesise harbour/sounds/*.ogg (needs ffmpeg with libvorbis)
  python3 kit/catalog/assets/harbour.py record     measure every file, draw the sounds' previews, write the source
  python3 kit/catalog/assets/harbour.py --check    fail if a file, preview or record is off

The models are made, not copied: run export_harbour.gd from an the iamar browser source (not public) checkout first
(see its header). The sounds are synthesised from a fixed seed (no recordings, nothing to
license): `sounds` writes WAV and has ffmpeg encode it to mono Ogg Vorbis, the only audio a
world takes. A sound's catalogue thumbnail is its waveform (kit/thumbnails/<id>.png) and its
"turntable" the waveform in eight slices of time (kit/turntables/<id>.png), drawn by `record`
(it decodes the Ogg with ffmpeg). Python 3.8+, standard library only (plus ffmpeg for sounds/record).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import subprocess
import sys
import tempfile
import wave
import zlib
from pathlib import Path

from import_city_models import HERE, LICENCE, measure

FOLDER = "harbour"
SOUNDS = "harbour/sounds"
SOURCE = HERE.parent / "sources" / "harbour.json"
KIT = HERE.parent.parent
RATE = 22050
CITE = ("made for the kit by kit/catalog/assets/export_harbour.gd in the city's low-poly painted look "
        "(the city has no harbour: its water is the mill pond, the canals and the fountains)")
SOUND_CITE = "synthesised for the kit by kit/catalog/assets/harbour.py sounds (seeded noise and partials, no recording)"

# file stem -> (name, category, description, synonyms, behaviours, clip to loop, collision,
#               {clip: [node it moves, least swing in radians or metres]})
MODELS = {
    "rowboat": ("rowboat", "vehicle",
        "A small clinker-built wooden rowboat, 3.8 m long, its top strake painted blue, with three thwarts, "
        "floor boards, iron rowlocks, two oars resting along the seats and the painter coiled in the bow. The origin is the waterline: "
        "place it at the water's height.",
        ["boat", "row boat", "dinghy", "skiff", "tender", "rowing boat", "harbour", "harbor", "quay", "jetty", "moored boat", "oars"],
        ["bobbing at its mooring (clip bob)"], "bob", "box", {"bob": ["Boat", 0.03]}),
    "fishing_boat": ("fishing boat", "vehicle",
        "A 6.8 m decked wooden fishing boat, green above the waterline, with a short mast and its tanned sail "
        "furled on the boom, a small cream cuddy forward, a tiller aft, two lobster pots, a fish box, a coil "
        "of rope and fenders over the side. The origin is the waterline: "
        "place it at the water's height, beside a quay.",
        ["boat", "fishing smack", "trawler", "sailing boat", "sailboat", "ship", "vessel", "harbour", "harbor",
         "fishing", "fisherman", "mast", "sail", "moored boat"],
        ["bobbing at its mooring (clip bob)"], "bob", "box", {"bob": ["Boat", 0.02]}),
    "bollard": ("mooring bollard", "prop",
        "A cast-iron mooring bollard, dark iron-grey and rust-streaked, 0.6 m tall on a granite pad, with a rope "
        "made fast round its neck and trailing to the water. Line a quay with them, 4-6 m apart.",
        ["bollard", "mooring post", "quay", "quayside", "dock", "wharf", "pier", "harbour", "harbor", "rope"],
        [], None, "box", {}),
    "harbour_bell": ("harbour bell", "prop",
        "A bronze harbour bell 0.5 m across hung in a timber frame 2.7 m tall on a stone plinth, with a pull rope; it swings on its "
        "headstock when rung. Play its ring clip with the bell sound from a script when the bell is rung.",
        ["bell", "ship's bell", "ships bell", "harbor bell", "fog bell", "alarm bell", "bell frame", "harbour",
         "harbor", "quay", "ring"],
        ["swinging when rung (clip ring)"], "ring", "box", {"ring": ["Bell", 0.3]}),
    "net_pile": ("pile of fishing net", "prop",
        "A heap of brown fishing net, 2.2 x 1.7 m, in three folds with a string of cork floats round its edge, "
        "two glass floats on top and a coil of rope beside it; lay it on a quay, a deck or beside a net shed.",
        ["net", "fishing net", "nets", "net pile", "floats", "glass floats", "fishing", "harbour", "harbor", "quay", "fisherman"],
        [], None, "none", {}),
    "fish_stall": ("fishmonger's slab", "furniture",
        "A fishmonger's slab 2.2 m long on two oak trestles: a board tilted toward the buyer and covered in "
        "ice with three rows of silver herring, two posts behind it with a rail and three fish hung by the tail "
        "from it, a chalk price slate on the front and a chopping block at one end. Front (the buyer's "
        "side) is -Z. Line a fish hall with them, 3-4 m apart, or set one on a quay.",
        ["fish stall", "fish slab", "fishmonger", "fish monger", "fish market", "market stall", "stall",
         "counter", "fish", "herring", "ice", "fish hall", "harbour", "harbor", "quay", "market"],
        [], None, "box", {}),
    "fish_crates": ("stack of fish crates", "prop",
        "Three open wooden fish crates, 0.7 x 0.45 x 0.26 m each, two side by side and one across them, "
        "each packed with herring on ice. Stack a few by a fish hall's stalls, on a quay beside a boat or on a cart.",
        ["crate", "crates", "fish crate", "fish box", "fish boxes", "box of fish", "herring", "fish", "catch",
         "fish hall", "fish market", "harbour", "harbor", "quay", "dock"],
        [], None, "box", {}),
    "hanging_net": ("net hung to dry", "prop",
        "A brown fishing net hung to dry over a rack 2.6 m long: two A-frame ends and a pole 2.1 m up, the net "
        "falling to about half a metre above the floor on both sides and sagging between the ends, with cork "
        "floats along its hems. Stand it in a fish hall or a net shed, or along a quay.",
        ["hanging net", "drying net", "net hung to dry", "net rack", "drying rack", "net loft",
         "fish hall", "net shed", "fishing", "harbour", "harbor", "quay", "fisherman"],
        [], None, "box", {}),
    "gull": ("herring gull", "bird",
        "An adult herring gull 0.58 m long: white with a pale grey back, black wing tips with white mirrors, "
        "a yellow bill with its red spot and pink legs. It stands on a bollard, a roof or a quay looking about (clip perch; the file's rest pose "
        "is the same, wings folded); its fly clip beats the wings with the legs tucked, for a gull "
        "a script moves through the air (entity_move_to, see kit/catalog/README.md).",
        ["gull", "seagull", "sea gull", "seabird", "sea bird", "herring gull", "bird", "coast", "harbour", "harbor", "seaside"],
        ["perched, looking about (clip perch)", "wingbeat in flight (clip fly)"], "perch", "none",
        {"perch": ["Head", 0.2], "fly": ["WingR", 0.4]}),
}

# file stem -> (name, description, synonyms, behaviours, scene.json sounds entry (file filled in))
SOUND_SET = {
    "sea_waves": ("sea waves (ambient loop)",
        "Waves washing against a harbour wall: a low swell of surf with a hiss as each wave breaks, "
        "about two waves every ten seconds. 16 s, mono, loops seamlessly; the bed under a harbour or a beach.",
        ["sea", "waves", "surf", "ocean", "sea sound", "wave sound", "water", "shore", "beach", "coast",
         "harbour", "harbor", "ambient", "ambience", "loop"],
        ["ambient loop"], {"id": "sea", "loop": True, "volume_db": -14}),
    "harbour_bell": ("harbour bell strike",
        "One strike of a bronze bell (G4 with its hum, tierce and nominal partials), ringing out over about "
        "five seconds. Mono; play it at the bell's position, once, from a quest's play or a script.",
        ["bell", "bell sound", "bell ring", "ring", "chime", "ship's bell", "harbor bell", "church bell",
         "fog bell", "alarm", "harbour", "harbor"],
        ["positional, once"], {"id": "bell", "position": [0, 2, 0], "radius": 60, "loop": False, "autoplay": False}),
    "gull_calls": ("gull calls",
        "A herring gull calling: two long mewing cries and a run of short laughing kyow-kyow notes, 3.6 s, mono. "
        "Loop it at a position on a roof or the quay, or play it now and then from a script.",
        ["gull", "gulls", "seagull", "seagulls", "gull call", "bird call", "seabird", "sea bird", "cry",
         "harbour", "harbor", "coast", "seaside"],
        ["positional loop"], {"id": "gulls", "position": [0, 6, 0], "radius": 40, "loop": True, "volume_db": -6}),
}


# ------------------------------------------------------------------ synthesis

def _lowpass(x: list, a: float, passes: int = 2) -> list:
    """One-pole low-pass run around the loop `passes` times, so the start already has the end's
    state and the buffer loops without a click."""
    y = [0.0] * len(x)
    s = 0.0
    for _ in range(passes):
        for i, v in enumerate(x):
            s += a * (v - s)
            y[i] = s
    return y


def _norm(x: list, peak: float) -> list:
    m = max(abs(v) for v in x) or 1.0
    return [v * peak / m for v in x]


def synth_sea(rng: random.Random) -> list:
    n = RATE * 16
    noise = [rng.uniform(-1, 1) for _ in range(n)]
    body = _lowpass(_lowpass(noise, 0.02), 0.04)          # the rumble of the swell
    hiss = [a - b for a, b in zip(noise, _lowpass(noise, 0.25))]   # high-passed: spray as a wave breaks
    hiss = _lowpass(hiss, 0.5)
    out = []
    for i in range(n):
        t = i / n                                         # every period divides 16 s: seamless
        swell = 0.35 + 0.65 * max(0.0, math.sin(2 * math.pi * 3 * t)) ** 2 + 0.25 * math.sin(2 * math.pi * 5 * t + 1.0) ** 2
        brk = max(0.0, math.sin(2 * math.pi * 3 * t - 0.6)) ** 6     # the break just after each crest
        out.append(body[i] * swell * 14.0 + hiss[i] * (0.08 + 0.9 * brk))
    return _norm(out, 0.7)


def synth_bell(rng: random.Random) -> list:
    n = int(RATE * 5.0)
    f0 = 392.0
    # (ratio, amplitude, decay seconds, beat Hz): a bell's hum, prime, tierce, quint, nominal and upper partials
    parts = [(0.5, 0.45, 4.2, 0.6), (1.0, 0.8, 3.2, 0.9), (1.2, 0.5, 2.4, 0.0), (1.5, 0.28, 1.7, 0.0),
             (2.0, 0.6, 1.9, 1.3), (2.5, 0.22, 1.0, 0.0), (3.0, 0.18, 0.8, 0.0), (4.2, 0.12, 0.45, 0.0)]
    out = [0.0] * n
    for ratio, amp, dec, beat in parts:
        f = f0 * ratio
        ph = rng.uniform(0, 2 * math.pi)
        for i in range(n):
            t = i / RATE
            e = amp * math.exp(-t / dec) * (1.0 - 0.3 * beat / 2 * (1 - math.cos(2 * math.pi * beat * t)))
            out[i] += e * math.sin(2 * math.pi * f * t + ph)
    for i in range(int(RATE * 0.006)):                    # the clapper's knock
        out[i] += rng.uniform(-1, 1) * 0.6 * (1 - i / (RATE * 0.006))
    for i in range(int(RATE * 0.003)):                    # no click at the start
        out[i] *= i / (RATE * 0.003)
    return _norm(out, 0.85)


def _call(out: list, start: float, dur: float, f_hi: float, f_lo: float, rng: random.Random, amp: float) -> None:
    """One gull note: a nasal harmonic tone that leaps up then glides down, a little rough."""
    i0, n = int(start * RATE), int(dur * RATE)
    harm = [1.0, 0.9, 0.7, 0.45, 0.3, 0.18, 0.1]
    ph = 0.0
    for k in range(n):
        u = k / n
        f = f_lo + (f_hi - f_lo) * (min(1.0, u / 0.12) if u < 0.12 else 1.0 - (u - 0.12) / 0.88 * 0.9)
        f *= 1.0 + 0.012 * math.sin(2 * math.pi * 31 * k / RATE)
        ph += 2 * math.pi * f / RATE
        env = min(1.0, u / 0.06) * (1.0 - u) ** 0.7
        s = sum(a * math.sin((h + 1) * ph) for h, a in enumerate(harm))
        s *= 1.0 + 0.25 * rng.uniform(-1, 1)
        out[i0 + k] += amp * env * s


def synth_gulls(rng: random.Random) -> list:
    out = [0.0] * int(RATE * 3.6)
    _call(out, 0.05, 0.55, 1250, 760, rng, 1.0)          # two long mews
    _call(out, 0.75, 0.6, 1300, 740, rng, 1.0)
    t = 1.55
    for j in range(6):                                    # the laugh: kyow-kyow-kyow
        _call(out, t, 0.2, 1150 - 25 * j, 820, rng, 0.85 - 0.06 * j)
        t += 0.28
    return _norm(out, 0.8)


SYNTH = {"sea_waves": (synth_sea, 11), "harbour_bell": (synth_bell, 12), "gull_calls": (synth_gulls, 13)}


def make_sounds() -> int:
    out = HERE / SOUNDS
    out.mkdir(parents=True, exist_ok=True)
    for stem, (fn, seed) in SYNTH.items():
        pcm = fn(random.Random(seed))
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / (stem + ".wav")
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767)) for v in pcm))
            ogg = out / (stem + ".ogg")
            # bitexact: fixed stream serial and no encoder tag, so the same samples give the same file
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-c:a", "libvorbis", "-q:a", "3",
                            "-ac", "1", "-fflags", "+bitexact", "-flags:a", "+bitexact", "-map_metadata", "-1",
                            str(ogg)], check=True)
        print("wrote %s (%.1f s, %d bytes)" % (ogg, len(pcm) / RATE, ogg.stat().st_size))
    return 0


# ------------------------------------------------------------------ measuring and previews

def ogg_info(b: bytes) -> dict:
    """Channels, sample rate and length of an Ogg Vorbis file (the last page's granule position)."""
    p = 27 + b[26]
    channels, rate = b[p + 11], struct.unpack_from("<I", b, p + 12)[0]
    last = b.rfind(b"OggS")
    granule = struct.unpack_from("<q", b, last + 6)[0]
    return {"channels": channels, "rate": rate, "seconds": round(granule / rate, 3)}


def _decode(p: Path) -> list:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
                         check=True, capture_output=True).stdout
    return [v / 32768.0 for v in struct.unpack("<%dh" % (len(raw) // 2), raw)]


def _png(path: Path, w: int, h: int, px: bytearray) -> None:
    rows = b"".join(b"\x00" + bytes(px[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def _wave_img(samples: list, w: int, h: int, x0: int, px: bytearray, stride: int) -> None:
    """Draw min..max of each column of `samples` into a w x h box at x0 of a stride-wide RGBA image."""
    mid = h / 2
    for x in range(w):
        a, b = int(len(samples) * x / w), max(int(len(samples) * (x + 1) / w), int(len(samples) * x / w) + 1)
        col = samples[a:b] or [0.0]
        lo, hi = min(col), max(col)
        for y in range(int(mid - hi * mid * 0.9), int(mid - lo * mid * 0.9) + 1):
            if 0 <= y < h:
                i = (y * stride + x0 + x) * 4
                px[i:i + 4] = bytes((70, 120, 170, 255))
        i = (int(mid) * stride + x0 + x) * 4
        px[i:i + 4] = bytes((40, 70, 100, 255))


def draw_previews(ogg: Path, fid: str) -> None:
    s = _decode(ogg)
    thumb = bytearray(128 * 128 * 4)
    _wave_img(s, 128, 128, 0, thumb, 128)
    (KIT / "thumbnails").mkdir(exist_ok=True)
    _png(KIT / "thumbnails" / (fid + ".png"), 128, 128, thumb)
    strip = bytearray(768 * 96 * 4)
    for f in range(8):
        _wave_img(s[len(s) * f // 8:len(s) * (f + 1) // 8], 96, 96, f * 96, strip, 768)
    (KIT / "turntables").mkdir(exist_ok=True)
    _png(KIT / "turntables" / (fid + ".png"), 768, 96, strip)


def rows() -> list:
    out = []
    for stem, (name, cat, desc, syn, beh, play, coll, moves) in MODELS.items():
        rel = "%s/%s.glb" % (FOLDER, stem)
        b = (HERE / rel).read_bytes()
        m = measure(b)
        r = {"models_id": "harbour_" + stem, "file": rel, "name": name, "category": cat, "description": desc,
             "synonyms": syn, "collision": coll, "origin": "kit",
             "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b), "place_scale": 1.0,
             "triangles": m["triangles"], "size": m["size"], "skinned": m["skinned"],
             "animations": m["animations"], "images": m["images"], "physics_body": m["physics_body"],
             "behaviours": beh, "builder": "kit/catalog/assets/export_harbour.gd", "cite": CITE}
        if play:
            r["play"] = play
        if moves:
            r["moves"] = moves
        out.append(r)
    for stem, (name, desc, syn, beh, snd) in SOUND_SET.items():
        rel = "%s/%s.ogg" % (SOUNDS, stem)
        p = HERE / rel
        b = p.read_bytes()
        sha = hashlib.sha256(b).hexdigest()
        draw_previews(p, sha[:16])
        out.append({"kind": "audio", "models_id": "sound_" + stem, "file": rel, "name": name, "category": "audio",
                    "description": desc, "synonyms": syn, "origin": "kit", "sha256": sha, "bytes": len(b),
                    "audio": ogg_info(b), "behaviours": beh, "sound": snd,
                    "builder": "kit/catalog/assets/harbour.py", "cite": SOUND_CITE})
    return out


def record() -> int:
    rs = rows()
    SOURCE.write_text(json.dumps({
        "format": "iamar-catalog-harbour", "version": 1,
        "note": "The harbour set in kit/catalog/assets/harbour/: models made by export_harbour.gd, sounds by "
                "harbour.py sounds, all measured by harbour.py record. Never edit by hand.",
        "licence": LICENCE, "models": rs}, indent=1) + "\n", encoding="utf-8")
    print("recorded %d models and %d sounds (%d bytes)" % (
        sum(1 for r in rs if r.get("kind") != "audio"), sum(1 for r in rs if r.get("kind") == "audio"),
        sum(r["bytes"] for r in rs)))
    return 0


def check() -> int:
    errs = []
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    for r in src["models"]:
        p = HERE / r["file"]
        if not p.is_file():
            errs.append("%s: file missing" % r["file"])
            continue
        b = p.read_bytes()
        if hashlib.sha256(b).hexdigest() != r["sha256"]:
            errs.append("%s: sha256 differs from harbour.json (rerun harbour.py record)" % r["file"])
        if r.get("kind") == "audio":
            info = ogg_info(b)
            if info != r["audio"] or info["channels"] != 1:
                errs.append("%s: %s, record says %s (mono expected)" % (r["file"], info, r["audio"]))
            for folder in ("thumbnails", "turntables"):
                if not (KIT / folder / (r["sha256"][:16] + ".png")).is_file():
                    errs.append("%s: no %s preview (rerun harbour.py record)" % (r["file"], folder))
            continue
        m = measure(b)
        if m["triangles"] != r["triangles"]:
            errs.append("%s: %d triangles, record says %d" % (r["file"], m["triangles"], r["triangles"]))
        for clip in [r.get("play")] + list(r.get("moves", {})):
            if clip and clip not in m["animations"]:
                errs.append("%s: no clip %r (has %s)" % (r["file"], clip, m["animations"]))
    named = {r["file"] for r in src["models"]}
    for pat in ("*.glb", "sounds/*.ogg"):
        for p in (HERE / FOLDER).glob(pat):
            rel = p.relative_to(HERE).as_posix()
            if rel not in named:
                errs.append("%s: file with no record in sources/harbour.json" % rel)
    for e in errs:
        print("CHECK " + e)
    print("harbour: %d records, %s" % (len(src["models"]), "OK" if not errs else "%d problems" % len(errs)))
    return 1 if errs else 0


def main(argv: list) -> int:
    if argv[:1] == ["--check"]:
        return check()
    if argv[:1] == ["record"]:
        return record()
    if argv[:1] == ["sounds"]:
        return make_sounds()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
