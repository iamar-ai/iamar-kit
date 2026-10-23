#!/usr/bin/env python3
"""Catalogue release packs (kit/catalog/packs.py, PUB7 an internal task): `build` packs every referenceable
catalogue object exactly once under its sha256, and `fetch` gets a world's catalogue references from a
release URL (a local fake server here) once per pack into the shared cache, keeping only entries that
hash to their names; tampered, misnamed, path-traversal and oversized packs, names off the fixed
patterns, off-host redirects and an offline server all fail with a reason."""

from __future__ import annotations

import contextlib
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "catalog"))
import packs  # noqa: E402
import refs  # noqa: E402

RELEASE = "v9.9.9"


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a, **k)
    return rc, buf.getvalue()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def entry(root: Path, name: str, data: bytes, pack: str = "iamar city", licence: str = "CC0-1.0",
          ext: str = "glb") -> dict:
    rel = "kit/catalog/assets/props/%s.%s" % (name, ext)
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_bytes(data)
    h = sha(data)
    return {"id": h[:16], "name": name, "kind": "model", "reuse": "reusable", "licence": licence,
            "attribution": "iamar", "bytes": len(data), "use": "",
            "source": {"origin": "city", "pack": pack, "file": rel, "sha256": h}}


def world(root: Path, name: str, recs: list[dict]) -> Path:
    w = root / name
    w.mkdir(parents=True)
    (w / "manifest.json").write_text(json.dumps({"id": name, "features": ["objects", refs.FEATURE],
                                                 "reused": recs}), encoding="utf-8")
    return w


class Server:
    """Serves <dir>/<release>/pack-<pack>.zip on 127.0.0.1 and counts the requests."""

    def __init__(self, root: Path):
        hits = self.hits = []
        redirects = self.redirects = {}

        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(s, *a, **k):
                super().__init__(*a, directory=str(root), **k)

            def do_GET(s):
                hits.append(s.path)
                if s.path in redirects:
                    s.send_response(302)
                    s.send_header("Location", redirects[s.path])
                    s.end_headers()
                    return
                super().do_GET()

            def log_message(s, *a):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def zip_of(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, b in entries.items():
            z.writestr(n, b)
    return buf.getvalue()


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        src = tmp / "src"
        a, b, c = b"glTF-a" * 50, b"glTF-b" * 70, b"glTF-c" * 30
        ea = entry(src, "fountain", a)
        eb = entry(src, "bench", b)
        ec = entry(src, "lamp", c, pack="harbour set")
        pending = entry(src, "statue", b"glTF-p" * 9, licence="licence pending")
        broken = entry(src, "crate", b"glTF-x" * 9)
        (src / broken["source"]["file"]).write_bytes(b"edited")
        cat = {"entries": [ea, eb, ec, pending]}

        # 1. build: every referenceable entry in exactly one pack under its sha256; packs.json matches.
        out = tmp / "srv" / RELEASE
        rc, log = quiet(packs.build, out, RELEASE, cat=cat, prov={}, root=src)
        assert rc == 0, log
        idx = json.loads((out / "packs.json").read_text(encoding="utf-8"))
        assert idx["release"] == RELEASE and idx["repo"] == refs.PUBLIC_REPO, idx
        assert sorted(p["pack"] for p in idx["packs"]) == ["harbour-set", "iamar-city"], idx
        seen = []
        for p in idx["packs"]:
            data = (out / p["file"]).read_bytes()
            assert sha(data) == p["sha256"] and len(data) == p["bytes"], p
            with zipfile.ZipFile(out / p["file"]) as z:
                for n in z.namelist():
                    m = packs.ENTRY_RE.match(n)
                    assert m and sha(z.read(n)) == m.group(1), n
                    seen.append(m.group(1))
            pj = json.loads((out / ("pack-%s.json" % p["pack"])).read_text(encoding="utf-8"))
            assert pj["format"] == "iamar-catalog-pack" and len(pj["objects"]) == p["objects"], pj
        assert sorted(seen) == sorted([sha(a), sha(b), sha(c)]), "pending licence must stay out, each once"
        # 1b. the public export's gate (an internal task): a licence outside shippable_licences, an excluded path
        # or a path off the include list never ships in a pack, as tools/export_public.py withholds them.
        rules = {"include": ["kit/**"], "exclude": [{"glob": "kit/inventory/", "reason": "internal"}],
                 "shippable_licences": ["CC0-1.0"], "asset_licences": []}
        ccby = entry(src, "cart", b"glTF-y" * 11, licence="CC-BY-4.0")
        hidden = entry(src, "chest", b"glTF-h" * 13)
        hidden["source"]["file"] = "kit/inventory/chest.glb"
        offlist = entry(src, "barrel", b"glTF-o" * 15)
        offlist["source"]["file"] = "private/barrel.glb"
        for e in (hidden, offlist):
            (src / e["source"]["file"]).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src / ("kit/catalog/assets/props/%s.glb" % e["name"]), src / e["source"]["file"])
        assert "CC-BY-4.0" in refs.refusal(ccby, {}, rules), refs.refusal(ccby, {}, rules)
        assert "excludes" in refs.refusal(hidden, {}, rules) and "allow-list" in refs.refusal(offlist, {}, rules)
        assert refs.refusal(ea, {}, rules) is None
        rc, log = quiet(packs.build, tmp / "gate", RELEASE, cat={"entries": [ea, ccby, hidden, offlist]}, prov={},
                        root=src, rules=rules)
        gate = json.loads((tmp / "gate" / "packs.json").read_text(encoding="utf-8"))
        assert rc == 0 and [(p["pack"], p["objects"]) for p in gate["packs"]] == [("iamar-city", 1)], (log, gate)
        if refs.export_rules() is not None:  # the private kit: its real rules.json gates by default
            assert refs.refusal(ccby, {}) and refs.refusal(hidden, {}) and refs.refusal(offlist, {})
        rc, log = quiet(packs.build, tmp / "bad", RELEASE, cat={"entries": [ea, broken]}, prov={}, root=src)
        assert rc == 1 and "no longer matches" in log, log
        # split by what each object can cost in the zip (headers + deflate growth), not raw bytes
        cap = packs.zip_cost(len(b)) + 8
        rc, log = quiet(packs.build, tmp / "split", RELEASE, max_bytes=cap, cat={"entries": [ea, eb]}, prov={}, root=src)
        split = json.loads((tmp / "split" / "packs.json").read_text(encoding="utf-8"))
        assert rc == 0 and [p["pack"] for p in split["packs"]] == ["iamar-city-1", "iamar-city-2"], split
        assert all(p["bytes"] <= cap and p["index"] == "pack-%s.json" % p["pack"] for p in split["packs"]), split
        assert "NOTE iamar-city split into 2 parts" in log, log
        rc, log = quiet(packs.build, tmp / "tiny", RELEASE, max_bytes=len(b), cat={"entries": [eb]}, prov={}, root=src)
        assert rc == 1 and "pack limit" in log and not (tmp / "tiny" / "packs.json").exists(), log
        assert quiet(packs.build, tmp / "big", RELEASE, max_bytes=packs.MAX_PACK_BYTES + 1, cat=cat, prov={},
                     root=src)[0] == 2
        assert quiet(packs.build, tmp / "x", "latest", cat=cat, prov={}, root=src)[0] == 2
        # a limit over what fetch accepts is refused; incompressible objects whose raw sizes just fit
        # the limit go to two parts, because zip headers and deflate growth count (review 20c81403).
        rc, log = quiet(packs.build, tmp / "x", RELEASE, max_bytes=packs.MAX_PACK_BYTES + 1, cat=cat, prov={}, root=src)
        assert rc == 2 and "fetch accepts" in log, log
        er1, er2 = entry(src, "noise1", os.urandom(3000)), entry(src, "noise2", os.urandom(3000))
        rc, log = quiet(packs.build, tmp / "tight", RELEASE, max_bytes=6000, cat={"entries": [er1, er2]}, prov={}, root=src)
        tight = json.loads((tmp / "tight" / "packs.json").read_text(encoding="utf-8"))
        assert rc == 0 and len(tight["packs"]) == 2 and all(p["bytes"] <= 6000 for p in tight["packs"]), tight

        # 2. fetch: two worlds share a pack -> one download; the kit tree has none of the files.
        srv = Server(tmp / "srv")
        os.environ["IAMAR_CATALOG_BASE"] = srv.base
        empty = tmp / "kit-without-objects"
        empty.mkdir()
        cache = tmp / "cache"
        w1 = world(tmp, "w1", [refs.record(ea, "assets/fountain.glb", RELEASE), refs.record(eb, "assets/bench.glb", RELEASE)])
        w2 = world(tmp, "w2", [refs.record(eb, "assets/b2.glb", RELEASE)])
        rc, log = quiet(packs.fetch_world, w1, cache, cat=cat, root=empty)
        assert rc == 0 and "FETCHED 2" in log, log
        assert srv.hits == ["/%s/pack-iamar-city.zip" % RELEASE], srv.hits
        rc, log = quiet(packs.fetch_world, w2, cache, cat=cat, root=empty)
        assert rc == 0 and "PRESENT 1" in log and len(srv.hits) == 1, (log, srv.hits)
        assert (cache / "objects" / ("%s.glb" % sha(a))).read_bytes() == a
        # a cache file that no longer hashes to its name is replaced by the next download
        (cache / "objects" / ("%s.glb" % sha(a))).write_bytes(b"corrupt")
        rc, log = quiet(packs.fetch_world, w1, cache, cat=cat, root=empty)
        assert rc == 0 and "FETCHED 1" in log and len(srv.hits) == 2, (log, srv.hits)
        assert (cache / "objects" / ("%s.glb" % sha(a))).read_bytes() == a
        srv.hits.pop()
        # found in the kit's own tree without any download
        rc, log = quiet(packs.fetch_world, world(tmp, "w3", [refs.record(ec, "assets/l.glb", RELEASE)]),
                        tmp / "cache-tree", cat=cat, root=src)
        assert rc == 0 and "PRESENT 1" in log and len(srv.hits) == 1, log
        rc, log = quiet(packs.fetch_world, w1, cache, cat=cat, root=empty, as_json=True)
        assert json.loads(log)["ok"] is True, log

        # 3. hostile packs: tampered, wrong name, path traversal; only good entries are kept, nothing outside.
        good = b"glTF-good" * 20
        evil_dir = tmp / "srv" / "v1.0.0"
        evil_dir.mkdir(parents=True)
        (evil_dir / "pack-evil.zip").write_bytes(zip_of({
            "objects/%s.glb" % sha(good): good,
            "objects/%s.glb" % sha(b"real"): b"tampered",
            "objects/%s.glb" % ("ab" * 32): b"wrong name",
            "objects/../../escaped.glb": good,
            "../escaped2.glb": good,
            "objects/sub/%s.glb" % sha(good): good,
            "objects/%s.exe" % sha(b"x"): b"x",
        }))
        c2 = tmp / "cache2"
        rc, log = quiet(packs.fetch_pack, "v1.0.0", "evil", c2)
        kept, why = rc
        assert why == "" and kept == [sha(good)], (kept, why, log)
        assert log.count("WARN") == 6, log
        assert sorted(p.name for p in (c2 / "objects").iterdir()) == ["%s.glb" % sha(good)]
        assert not list(tmp.rglob("escaped*.glb")), "path traversal wrote a file"
        # a tampered object in the pack a world needs: refused with the reason
        bad_rec = dict(refs.record(ea, "assets/f.glb", "v1.0.0"))
        bad_rec["source"] = dict(bad_rec["source"], pack="evil")
        bad_rec["sha256"] = sha(b"real")
        rc, log = quiet(packs.fetch_world, world(tmp, "w4", [bad_rec]), c2, cat=cat, root=empty)
        assert rc == 1 and "does not hold an object" in log, log
        # not a zip
        (evil_dir / "pack-junk.zip").write_bytes(b"junk")
        (kept, why), log = quiet(packs.fetch_pack, "v1.0.0", "junk", c2)
        assert kept == [] and "not a zip" in log, log

        # 4. oversized pack: refused before it is stored.
        cap = packs.MAX_PACK_BYTES
        packs.MAX_PACK_BYTES = 1000
        try:
            (evil_dir / "pack-big.zip").write_bytes(zip_of({"objects/%s.glb" % sha(b"z" * 5000): b"z" * 5000}) + b"\0" * 2000)
            (kept, why), log = quiet(packs.fetch_pack, "v1.0.0", "big", tmp / "cache3")
            assert kept == [] and "cap" in why, (why, log)
            assert not (tmp / "cache3" / "objects").exists() or not list((tmp / "cache3" / "objects").iterdir())
        finally:
            packs.MAX_PACK_BYTES = cap

        # 5. names off the fixed patterns: refused without any request.
        n = len(srv.hits)
        for repo, rel, pk in [("evil/repo", RELEASE, "iamar-city"), (refs.PUBLIC_REPO, "latest", "iamar-city"),
                              (refs.PUBLIC_REPO, "v1.0.0/../../x", "iamar-city"),
                              (refs.PUBLIC_REPO, "v1.0.0\n", "iamar-city"), (refs.PUBLIC_REPO, RELEASE, "../x"),
                              (refs.PUBLIC_REPO, RELEASE, "Iamar City"), (refs.PUBLIC_REPO, RELEASE, "a" * 65),
                              (refs.PUBLIC_REPO, RELEASE, "x?y=https://evil")]:
            kept, why = packs.fetch_pack(rel, pk, tmp / "c5", repo)
            assert kept == [] and why.startswith("refused"), (repo, rel, pk, why)
        assert len(srv.hits) == n, srv.hits[n:]
        r = dict(refs.record(ec, "assets/l.glb", RELEASE))
        r["source"] = dict(r["source"], repo="evil/repo")
        rc, log = quiet(packs.fetch_world, world(tmp, "w5", [r]), tmp / "c5", cat=cat, root=empty)
        assert rc == 1 and "refused" in log and len(srv.hits) == n, log

        # 6. a redirect off the allowed hosts is refused.
        srv.redirects["/%s/pack-harbour-set.zip" % RELEASE] = "http://example.com/pack.zip"
        (kept, why), log = quiet(packs.fetch_pack, RELEASE, "harbour-set", tmp / "c6")
        assert kept == [] and "redirect" in why, why
        del srv.redirects["/%s/pack-harbour-set.zip" % RELEASE]

        # 7. only a loopback server may replace the release URL; real URLs are HTTPS on fixed hosts.
        os.environ["IAMAR_CATALOG_BASE"] = "https://evil.example"
        urls, log = quiet(packs.pack_urls, RELEASE, "iamar-city")
        assert urls == [packs.GITHUB % (refs.PUBLIC_REPO, RELEASE, "iamar-city"),
                        packs.MIRROR % (RELEASE, "iamar-city")] and "ignored" in log, (urls, log)
        assert all(u.startswith("https://") for u in urls)
        os.environ["IAMAR_CATALOG_BASE"] = srv.base

        # 8. offline: the world is refused with the pack it needs.
        srv.stop()
        rc, log = quiet(packs.fetch_world, world(tmp, "w6", [refs.record(ec, "assets/l.glb", RELEASE)]),
                        tmp / "c8", cat=cat, root=empty)
        assert rc == 1 and "ERROR assets/l.glb" in log and "127.0.0.1" in log, log

        # 9. `iamar-world assets fetch` reaches packs.py from the launchers (the kit's own catalogue).
        real = refs.load(refs.CATALOG)
        prov = refs.provenance_rows()
        ok = [e for e in real["entries"] if not refs.refusal(e, prov) and (KIT.parent / e["source"]["file"]).is_file()]
        recs = [refs.record(ok[0], "assets/x" + Path(ok[0]["source"]["file"]).suffix, RELEASE)] if ok else []
        w7 = world(tmp, "w7", recs)
        env = dict(os.environ, IAMAR_CATALOG_CACHE=str(tmp / "c9"), IAMAR_BROWSER=str(tmp / "no-browser"),
                   IAMAR_KIT_NO_FETCH="1", IAMAR_KIT_NO_NEXT="1", IAMAR_KIT_NO_ACTIVITY="1", PYTHON=sys.executable)
        want = "PRESENT %d" % len(recs)
        bash = shutil.which("bash") if os.name != "nt" else next(
            (x for x in (os.environ.get("GIT_BASH", ""), r"C:\Program Files\Git\bin\bash.exe") if x and Path(x).is_file()), None)
        if bash:
            p = subprocess.run([bash, str(KIT / "iamar-world"), "assets", "fetch", str(w7)],
                               capture_output=True, text=True, env=env, timeout=120)
            assert p.returncode == 0 and want in p.stdout, (p.returncode, p.stdout, p.stderr)
        if os.name == "nt":
            p = subprocess.run(["cmd", "/c", str(KIT / "iamar-world.cmd"), "assets", "fetch", str(w7)],
                               capture_output=True, text=True, env=env, timeout=120)
            assert p.returncode == 0 and want in p.stdout, (p.returncode, p.stdout, p.stderr)
    print("PACKS_TEST_OK")


if __name__ == "__main__":
    main()
