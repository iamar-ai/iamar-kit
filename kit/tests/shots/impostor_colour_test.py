#!/usr/bin/env python3
"""`iamar-world impostors` draws a vertex-painted model in its own colours (harbour a4 gap G19).

The city's elm and oak trees (kit/catalog/assets/trees) carry their colours in glTF COLOR_0;
the capture used to follow only the material's vertex_color_use_as_albedo, which GLTFDocument
leaves off, so their cards came out white. This builds the impostor of the catalogue elm and of
the textured harbour rowboat in a scratch world and checks each card's mean colour against the
model's own colours. Needs a renderer and IAMAR_KIT_PACK (a pack built by tools/build_pack.sh
from the revision under test), plus IAMAR_BROWSER (a browser binary or wrapper, e.g.
`mp-godot-slot offscreen <browser>`) or GODOT and IAMAR_PROJECT (a browser checkout, as
tools/run_tests.sh sets them); otherwise it prints SKIPPED.

    IAMAR_BROWSER=... IAMAR_KIT_PACK=... python3 kit/tests/shots/impostor_colour_test.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "lint"))
sys.path.insert(0, str(KIT / "style" / "materials"))
checks: list[bool] = []


def check(name: str, ok: bool, detail="") -> None:
    checks.append(bool(ok))
    print("%s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else ": %s" % detail))


def vertex_mean(glb: Path):
    """Mean sRGB 0-255 colour of the model's COLOR_0 (the elm is a Godot-made file: sRGB values)."""
    import numpy as np
    import materials
    import style_lint
    g = style_lint.Glb(glb)
    cols = [materials.accessor(g, p["attributes"]["COLOR_0"])[:, :3]
            for m in g.g["meshes"] for p in m["primitives"] if "COLOR_0" in p["attributes"]]
    return np.concatenate(cols).mean(0) * 255.0


def card_mean(png: Path):
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(png).convert("RGBA")).astype(float)
    return a[a[..., 3] > 128][:, :3].mean(0)


def main() -> int:
    pack = os.environ.get("IAMAR_KIT_PACK")
    if not pack or not (os.environ.get("IAMAR_BROWSER") or os.environ.get("IAMAR_PROJECT")):
        print("SKIPPED impostor colour test (set IAMAR_KIT_PACK and IAMAR_BROWSER or GODOT + IAMAR_PROJECT)")
        return 0
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        print("SKIPPED impostor colour test (numpy or Pillow missing)")
        return 0
    with tempfile.TemporaryDirectory(prefix="iamar-impostor-colour-") as tmp:
        w = Path(tmp) / "w"
        (w / "assets").mkdir(parents=True)
        shutil.copy(KIT / "catalog" / "assets" / "trees" / "elm_tree.glb", w / "assets" / "elm_tree.glb")
        shutil.copy(KIT / "catalog" / "assets" / "harbour" / "rowboat.glb", w / "assets" / "rowboat.glb")
        (w / "manifest.json").write_text(json.dumps({"format": 1, "id": "impostor_colour", "name": "impostor colour",
                                                     "scene": "scene.json"}), encoding="utf-8")
        (w / "scene.json").write_text(json.dumps({"objects": [
            {"id": "elm", "asset": "assets/elm_tree.glb", "position": [0, 0, 0], "impostor": 40},
            {"id": "boat", "asset": "assets/rowboat.glb", "position": [6, 0, 0], "impostor": 40}]}), encoding="utf-8")
        p = subprocess.run([str(KIT / "iamar-world"), "impostors", "."], cwd=w,
                           capture_output=True, text=True, timeout=900)
        out = p.stdout + p.stderr
        check("impostors builds both cards", p.returncode == 0 and out.count("IMPOSTOR assets/") == 2, out[-2000:])
        card = w / "impostors" / "assets" / "elm_tree.glb.albedo.png"
        if not card.is_file():
            check("elm card written", False, out[-2000:])
        else:
            got, want = card_mean(card), vertex_mean(w / "assets" / "elm_tree.glb")
            check("elm card is not white (G19)", got.max() < 200, got.round(1))
            check("elm card matches its vertex colours (mean within 25 per channel)",
                  float(abs(got - want).max()) < 25, "card %s, vertex colours %s" % (got.round(1), want.round(1)))
        boat = w / "impostors" / "assets" / "rowboat.glb.albedo.png"
        if boat.is_file():
            b = card_mean(boat)
            check("textured rowboat card keeps its wood colour (red over blue)", b[0] > b[2] + 10 and b.max() < 200, b.round(1))
        else:
            check("rowboat card written", False, out[-2000:])
    print("impostor colour tests: %d/%d" % (sum(checks), len(checks)))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
