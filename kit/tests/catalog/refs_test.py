#!/usr/bin/env python3
"""Catalogue references by hash (kit/catalog/refs.py, PUB16 an internal task): `ref` writes a reused record
from the public release and the feature, refuses what the public release cannot carry, and `check`
(run by `iamar-world package`) fails every seeded mistake in a reference or a catalogue copy."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "catalog"))
import catalog  # noqa: E402
import refs  # noqa: E402


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a, **k)
    return rc, buf.getvalue()


def new_world(root: Path, name: str) -> Path:
    w = root / name
    (w / "assets").mkdir(parents=True)
    (w / "manifest.json").write_text(json.dumps({"id": name, "features": ["objects"]}), encoding="utf-8")
    return w


def man(w: Path) -> dict:
    return json.loads((w / "manifest.json").read_text(encoding="utf-8"))


def put(w: Path, m: dict) -> None:
    (w / "manifest.json").write_text(json.dumps(m), encoding="utf-8")


def has(errs: list[str], words: str) -> bool:
    return any(words in e for e in errs)


def main() -> None:
    real = catalog.load(catalog.CATALOG)
    prov = refs.provenance_rows()
    models = [e for e in real["entries"] if e["kind"] == "model" and e["source"].get("file")
              and e["source"].get("origin") != "builtin"]
    assert models, "no kit catalogue models"
    # The copy check relies on this: every shipped kit object hashes to its catalogue sha256.
    for e in models:
        f = KIT.parent / e["source"]["file"]
        assert f.is_file(), f
        assert refs.sha256_file(f) == e["source"]["sha256"], "%s does not hash to its entry" % e["id"]
    single = next(e for e in models if "(manifest.json tiers lists" not in e["use"])
    tiered = next((e for e in models if "(manifest.json tiers lists" in e["use"]), None)

    # A fixture catalogue whose object has a cleared licence (PUB2 clears the real ones).
    cat = copy.deepcopy(real)
    fx = next(e for e in cat["entries"] if e["id"] == single["id"])
    fx["licence"] = "CC0-1.0"
    # And one whose licence is still pending (an internal task cleared the real catalogue, 7f3d45b).
    pending = copy.deepcopy(real)
    next(e for e in pending["entries"] if e["id"] == single["id"])["licence"] = "licence pending (test)"
    builtin = next(e for e in cat["entries"] if e["source"].get("origin") == "builtin")
    assert refs.pack_slug(fx) == refs.pack_slug(single) and refs.pack_slug(fx), refs.pack_slug(fx)
    rel = refs.release_tag()   # check pins references to this kit's own release
    assert refs.RELEASE_RE.match(rel), rel

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # 1. A pending licence is refused: nothing written.
        w = new_world(root, "pending")
        before = (w / "manifest.json").read_text(encoding="utf-8")
        rc, out = quiet(refs.ref, w, single["id"], None, pending, prov, rel)
        assert rc == 1 and "not cleared" in out, out
        assert (w / "manifest.json").read_text(encoding="utf-8") == before

        # 2. A cleared object: one reused record, the feature, and a clean check.
        w = new_world(root, "ok")
        rc, out = quiet(refs.ref, w, fx["id"], "assets/thing.glb", cat, prov, rel)
        assert rc == 0 and "REFERENCED" in out, out
        m = man(w)
        assert refs.FEATURE in m["features"] and "objects" in m["features"], m
        assert len(m["reused"]) == 1, m
        r = m["reused"][0]
        assert r["path"] == "assets/thing.glb" and r["sha256"] == fx["source"]["sha256"] and r["bytes"] == fx["bytes"]
        assert r["source"] == {"kind": "catalog", "repo": "iamar-ai/iamar-kit", "release": rel,
                               "pack": refs.pack_slug(fx), "id": fx["id"], "file": fx["source"]["file"]}, r
        assert r["license"] == "CC0-1.0" and r["author"] == (fx.get("attribution") or "iamar"), r
        assert not (w / "assets/thing.glb").exists(), "a reference must not copy the file"
        assert refs.check(w, cat, prov) == [], refs.check(w, cat, prov)
        # Running it again replaces the record, never duplicates it.
        quiet(refs.ref, w, fx["id"], "assets/thing.glb", cat, prov, rel)
        assert len(man(w)["reused"]) == 1 and man(w)["features"].count(refs.FEATURE) == 1

        # 3. Seeded mistakes fail the package-step check.
        good = man(w)

        def broken(edit) -> list[str]:
            m = copy.deepcopy(good)
            edit(m)
            put(w, m)
            return refs.check(w, cat, prov)

        assert has(broken(lambda m: m["reused"][0].update(sha256="0" * 64)), "sha256 differs")
        assert has(broken(lambda m: m["reused"][0].update(bytes=1)), "bytes")
        assert has(broken(lambda m: m["reused"][0].update(license="MIT")), "license must be")
        assert has(broken(lambda m: m["reused"][0].update(author="someone")), "author must be")
        assert has(broken(lambda m: m["reused"][0]["source"].update(repo="evil/kit")), "source.repo")
        assert has(broken(lambda m: m["reused"][0]["source"].update(release="main")), "source.release")
        # A well-formed tag of a release that does not exist (or another release) is refused too.
        nope = broken(lambda m: m["reused"][0]["source"].update(release="v9.9.9"))
        assert has(nope, "source.release must be this kit's release " + rel) and has(nope, "assets ref"), nope
        put(w, good)
        assert refs.check(w, cat, prov, "v9.9.9") and not refs.check(w, cat, prov, rel)
        assert has(broken(lambda m: m["reused"][0]["source"].update(pack="other")), "source.pack")
        assert has(broken(lambda m: m["reused"][0]["source"].update(id="nope")), "not in this kit's catalogue")
        assert has(broken(lambda m: m["reused"][0].update(path="../x.glb")), "relative path")
        # An absolute path is reported once and never probed on the host disk ("also carries").
        absp = broken(lambda m: m["reused"][0].update(path=str(KIT / "VERSION.json")))
        assert has(absp, "relative path") and not has(absp, "also carries"), absp
        assert has(broken(lambda m: m["reused"].append(copy.deepcopy(m["reused"][0]))), "listed twice")
        assert has(broken(lambda m: m.update(features=["objects"])), "catalog-packs")
        put(w, good)
        (w / "assets/thing.glb").write_bytes(b"x")
        assert has(refs.check(w, cat, prov), "also carries")
        (w / "assets/thing.glb").unlink()
        # The reference survives only while the catalogue still allows it.
        assert has(refs.check(w, pending, prov), "not cleared"), "a pending licence must fail the gate"
        gen = {fx["source"]["file"]: {"made_by": "generative:hunyuan3d", "evidence": "x"}}
        assert has(refs.check(w, cat, gen), "generative")
        locked = copy.deepcopy(cat)
        next(e for e in locked["entries"] if e["id"] == fx["id"])["reuse"] = "locked (test)"
        assert has(refs.check(w, locked, prov), "locked")
        assert refs.check(w, cat, prov) == []

        # 4. What a release pack cannot hold is refused by `ref`.
        w = new_world(root, "refused")
        rc, out = quiet(refs.ref, w, builtin["id"], None, cat, prov, rel)
        assert rc == 1 and "built-in" in out, out
        rc, out = quiet(refs.ref, w, fx["id"], None, cat, gen, rel)
        assert rc == 1 and "generative" in out, out
        rc, out = quiet(refs.ref, w, "no such thing", None, cat, prov, rel)
        assert rc == 1, out
        rc, out = quiet(refs.ref, w, fx["id"], "assets/../x.glb", cat, prov, rel)
        assert rc == 2, out
        if tiered:
            tc = copy.deepcopy(cat)
            next(e for e in tc["entries"] if e["id"] == tiered["id"])["licence"] = "CC0-1.0"
            rc, out = quiet(refs.ref, w, tiered["id"], None, tc, prov, rel)
            assert rc == 1 and "tier" in out, out
        assert "reused" not in man(w)

        # 5. A copy made by `assets use` keeps its credit honest: clean, then an edited copy fails.
        w = new_world(root, "copied")
        rc, out = quiet(catalog.use, w, single["id"], None)
        assert rc == 0, out
        assert refs.check(w, real, prov) == [], refs.check(w, real, prov)
        credit = next(c for c in man(w)["credits"] if c["source"].endswith(single["id"]))
        (w / credit["files"][0]).write_bytes(b"edited")
        assert has(refs.check(w, real, prov), "no longer hashes")
        m = man(w)
        m["credits"][-1]["license"] = "MIT"
        put(w, m)
        assert has(refs.check(w, real, prov), "license must be")

        # 6. A world without catalogue objects is clean; a broken manifest is reported, not a crash.
        w = new_world(root, "plain")
        assert refs.check(w, real, prov) == []
        (w / "manifest.json").write_text("{", encoding="utf-8")
        assert has(refs.check(w, real, prov), "not JSON")

        # 7. The launcher runs the gate before packaging (no browser needed to fail).
        bad = new_world(root, "bad")
        m = man(bad)
        m["features"].append(refs.FEATURE)
        m["reused"] = [dict(good["reused"][0], sha256="0" * 64)]
        put(bad, m)
        env = dict(os.environ, IAMAR_BROWSER=str(root / "no-browser"), IAMAR_KIT_NO_FETCH="1",
                   IAMAR_KIT_NO_NEXT="1", IAMAR_KIT_NO_ACTIVITY="1", PYTHON=sys.executable)
        bash = shutil.which("bash") if os.name != "nt" else next(
            (b for b in (os.environ.get("GIT_BASH", ""), r"C:\Program Files\Git\bin\bash.exe") if b and Path(b).is_file()), None)
        if bash:
            p = subprocess.run([bash, str(KIT / "iamar-world"), "package", str(bad), str(root / "o.iamar"), "k", "n"],
                               capture_output=True, text=True, env=env, timeout=120)
            assert p.returncode == 1 and "REFS_FAILED" in p.stdout, (p.returncode, p.stdout, p.stderr)
        if os.name == "nt":
            p = subprocess.run(["cmd", "/c", str(KIT / "iamar-world.cmd"), "package", str(bad), str(root / "o.iamar"),
                                "k", "n"], capture_output=True, text=True, env=env, timeout=120)
            assert p.returncode == 1 and "REFS_FAILED" in p.stdout, (p.returncode, p.stdout, p.stderr)
    print("REFS_TEST_OK")


if __name__ == "__main__":
    main()
