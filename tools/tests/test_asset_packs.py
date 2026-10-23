#!/usr/bin/env python3
"""Tests for tools/asset_packs.py: build release packs, fetch one object by sha256 from a fake release.

Run: python3 tools/tests/test_asset_packs.py   (no network, no Godot)
A throwaway kit-shaped folder holds a small catalogue; `build` packs it, a local HTTP server
on 127.0.0.1 serves the output as the release, and `fetch` must get objects by hash, store
the whole pack once, and refuse tampered packs, unknown hashes and non-https hosts.
"""
import functools, hashlib, http.server, importlib.util, io, json, pathlib, tempfile, threading, unittest, zipfile
from contextlib import redirect_stderr, redirect_stdout

HERE = pathlib.Path(__file__).resolve()
KIT = HERE.parents[2]
SPEC = importlib.util.spec_from_file_location("asset_packs", KIT / "tools" / "asset_packs.py")
AP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AP)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def entry(eid, rel, data, pack="iamar city", **kw):
    e = {"id": eid, "name": eid, "kind": "model", "reuse": "reusable", "licence": "CC0-1.0",
         "attribution": "iamar", "bytes": len(data),
         "source": {"origin": "city", "pack": pack, "file": rel, "sha256": sha(data)}}
    e.update(kw)
    return e


class Release:
    """Serves a folder on 127.0.0.1 and counts the requests per file."""

    def __init__(self, root):
        hits = self.hits = {}

        class H(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                name = self.path.rsplit("/", 1)[-1]
                hits[name] = hits.get(name, 0) + 1
                super().do_GET()

            def log_message(self, *a):
                pass

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=str(root)))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d/" % self.srv.server_address[1]

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


class AssetPacksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = pathlib.Path(self.tmp.name)
        self.kit, self.out, self.lib = t / "kit", t / "release", t / "library"
        self.files = {
            "kit/catalog/assets/fountain.glb": b"glTF fountain" * 20,
            "kit/catalog/assets/crate.glb": b"glTF crate" * 25,
            "kit/catalog/assets/well.glb": b"glTF well" * 30,
            "kit/catalog/assets/boat.glb": b"glTF boat" * 20,
            "kit/catalog/assets/ai_statue.glb": b"glTF generated statue",
            "kit/catalog/assets/frog.glb": b"glTF frog",
        }
        for rel, data in self.files.items():
            (self.kit / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.kit / rel).write_bytes(data)
        f = self.files
        self.cat = {"entries": [
            entry("fountain", "kit/catalog/assets/fountain.glb", f["kit/catalog/assets/fountain.glb"]),
            entry("crate", "kit/catalog/assets/crate.glb", f["kit/catalog/assets/crate.glb"]),
            entry("crate-copy", "kit/catalog/assets/crate.glb", f["kit/catalog/assets/crate.glb"], pack="harbour set"),
            entry("well", "kit/catalog/assets/well.glb", f["kit/catalog/assets/well.glb"], pack="harbour set"),
            entry("boat", "kit/catalog/assets/boat.glb", f["kit/catalog/assets/boat.glb"], pack="harbour set"),
            entry("statue", "kit/catalog/assets/ai_statue.glb", f["kit/catalog/assets/ai_statue.glb"]),
            entry("frog", "kit/catalog/assets/frog.glb", f["kit/catalog/assets/frog.glb"],
                  licence="iamar original work (licence pending)"),
            entry("locked", "kit/catalog/assets/well.glb", f["kit/catalog/assets/well.glb"], reuse="locked: owner"),
            {"id": "creature:bunny", "name": "bunny", "kind": "creature", "reuse": "reusable", "licence": "CC0-1.0",
             "bytes": 0, "source": {"origin": "creature"}},
        ]}
        self.prov = {"kit/catalog/assets/ai_statue.glb": {"made_by": "generative:hunyuan3d"}}
        self.srv = None

    def tearDown(self):
        if self.srv:
            self.srv.close()
        self.tmp.cleanup()

    def build(self, **kw):
        return AP.build(self.cat, self.out, "v1.2.3", prov=self.prov, kit_root=self.kit, **kw)

    def serve(self):
        self.srv = Release(self.out)
        return self.srv.base

    def obj(self, name):
        return sha(self.files["kit/catalog/assets/%s.glb" % name])

    # ------------------------------------------------------------ build

    def test_build_packs_only_accepted_objects_once_under_their_hash(self):
        index = self.build()
        self.assertEqual([p["pack"] for p in index["packs"]], ["harbour-set", "iamar-city"])
        names = {}
        for p in index["packs"]:
            data = (self.out / p["file"]).read_bytes()
            self.assertEqual((sha(data), len(data)), (p["sha256"], p["bytes"]))
            meta = json.loads((self.out / p["index"]).read_text())
            self.assertEqual((meta["format"], meta["pack"], meta["release"]), ("iamar-catalog-pack", p["pack"], "v1.2.3"))
            with zipfile.ZipFile(self.out / p["file"]) as z:
                for info in z.infolist():
                    m = AP.OBJECT_RE.match(info.filename)
                    self.assertTrue(m, info.filename)
                    self.assertEqual(sha(z.read(info)), m.group(1))
                    names[m.group(1)] = names.get(m.group(1), 0) + 1
                self.assertEqual(sorted(o["sha256"] for o in meta["objects"]),
                                 sorted(AP.OBJECT_RE.match(n).group(1) for n in z.namelist()))
        # fountain, crate, well, boat; not the generative, licence-pending, locked or creature entries.
        # crate is in both packs, once each: its two entries name different packs and each
        # reference must resolve in the pack it names
        self.assertEqual(sorted(names), sorted(self.obj(n) for n in ("fountain", "crate", "well", "boat")))
        self.assertEqual(names, {**{self.obj(n): 1 for n in ("fountain", "well", "boat")}, self.obj("crate"): 2})
        self.assertTrue(all(p["index"] == "pack-%s.json" % p["pack"] for p in index["packs"]))
        on_disk = json.loads((self.out / "packs.json").read_text())
        self.assertEqual(on_disk, index)

    def test_build_is_reproducible(self):
        first = self.build()
        for p in self.out.iterdir():
            p.unlink()
        self.assertEqual(self.build(), first)

    def test_build_splits_a_pack_over_the_limit(self):
        index = self.build(max_bytes=800)
        names = [p["pack"] for p in index["packs"]]
        self.assertEqual(names, ["harbour-set-1", "harbour-set-2", "harbour-set-3", "iamar-city-1", "iamar-city-2"])
        self.assertEqual([p["objects"] for p in index["packs"]], [1, 1, 1, 1, 1])

    def test_build_keeps_every_zip_within_the_limit_fetch_accepts(self):
        # incompressible data grows under deflate and zip headers add more: the zip, not the raw
        # bytes, must stay within the limit, or fetch refuses the pack
        data = b"".join(hashlib.sha256(b"noise %d" % i).digest() for i in range(200))
        (self.kit / "kit/catalog/assets/noise.glb").write_bytes(data)
        self.cat = {"entries": [entry("noise", "kit/catalog/assets/noise.glb", data)]}
        limit = len(data) + 600
        index = self.build(max_bytes=limit)
        self.assertTrue(all(p["bytes"] <= limit for p in index["packs"]), index["packs"])
        with self.assertRaisesRegex(AP.PackError, "pack limit"):
            self.build(max_bytes=len(data))
        with self.assertRaisesRegex(AP.PackError, "fetch accepts"):
            self.build(max_bytes=AP.MAX_PACK_BYTES + 1)

    def test_build_refuses_an_object_that_changed_on_disk(self):
        (self.kit / "kit/catalog/assets/well.glb").write_bytes(b"edited")
        with self.assertRaisesRegex(AP.PackError, "no longer matches"):
            self.build()

    def test_build_refuses_a_bad_release_tag(self):
        with self.assertRaisesRegex(AP.PackError, "release"):
            AP.build(self.cat, self.out, "latest", prov=self.prov, kit_root=self.kit)

    # ------------------------------------------------------------ fetch

    def test_fetch_by_hash_downloads_the_pack_once(self):
        self.build()
        base = self.serve()
        path = AP.fetch(self.obj("well"), base, self.lib)
        self.assertEqual(path.read_bytes(), self.files["kit/catalog/assets/well.glb"])
        self.assertEqual(path.name, self.obj("well") + ".glb")
        # the whole pack is local now: its neighbour costs no download
        hits = dict(self.srv.hits)
        self.assertEqual(hits.get("pack-harbour-set.zip"), 1)
        boat = AP.fetch(self.obj("boat"), base, self.lib, pack="harbour-set")
        self.assertEqual(boat.read_bytes(), self.files["kit/catalog/assets/boat.glb"])
        self.assertEqual(self.srv.hits, hits)
        self.assertNotIn("pack-iamar-city.zip", self.srv.hits)

    def test_fetch_replaces_a_corrupt_library_file(self):
        self.build()
        base = self.serve()
        bad = self.lib / "objects" / (self.obj("well") + ".glb")
        bad.parent.mkdir(parents=True)
        bad.write_bytes(b"truncated")
        path = AP.fetch(self.obj("well"), base, self.lib)
        self.assertEqual(path.read_bytes(), self.files["kit/catalog/assets/well.glb"])

    def test_fetch_finds_the_part_of_a_split_pack(self):
        self.build(max_bytes=800)
        base = self.serve()
        for n, pack in (("well", "harbour-set"), ("boat", "harbour-set"), ("crate", None), ("fountain", None)):
            self.assertEqual(AP.fetch(self.obj(n), base, self.lib, pack=pack).read_bytes(),
                             self.files["kit/catalog/assets/%s.glb" % n])
        with self.assertRaisesRegex(AP.PackError, "no pack harbour-set"):
            AP.fetch(sha(b"absent"), base, self.lib, pack="harbour-set")

    def test_fetch_refuses_a_tampered_pack(self):
        index = self.build()
        zpath = self.out / "pack-iamar-city.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(zpath) as src, zipfile.ZipFile(buf, "w") as dst:
            for info in src.infolist():
                dst.writestr(info.filename, b"evil" if self.obj("fountain") in info.filename else src.read(info))
        zpath.write_bytes(buf.getvalue())
        base = self.serve()
        with self.assertRaisesRegex(AP.PackError, "does not match packs.json"):
            AP.fetch(self.obj("fountain"), base, self.lib)
        # a pack that matches packs.json but holds a wrong object stores nothing under that name
        row = next(p for p in index["packs"] if p["pack"] == "iamar-city")
        row.update(sha256=sha(buf.getvalue()), bytes=len(buf.getvalue()))
        (self.out / "packs.json").write_text(json.dumps(index))
        with self.assertRaisesRegex(AP.PackError, "holds no object"):
            AP.fetch(self.obj("fountain"), base, self.lib)
        self.assertFalse((self.lib / "objects" / (self.obj("fountain") + ".glb")).exists())
        self.assertTrue((self.lib / "objects" / (self.obj("crate") + ".glb")).exists())

    def test_fetch_refuses_unknown_hash_bad_input_and_plain_http_hosts(self):
        self.build()
        base = self.serve()
        with self.assertRaisesRegex(AP.PackError, "no pack"):
            AP.fetch(self.obj("frog"), base, self.lib)
        with self.assertRaisesRegex(AP.PackError, "not a sha256"):
            AP.fetch("../../etc/passwd", base, self.lib)
        with self.assertRaisesRegex(AP.PackError, "bad pack"):
            AP.fetch(self.obj("well"), base, self.lib, pack="../x")
        with self.assertRaisesRegex(AP.PackError, "https"):
            AP.fetch(self.obj("well"), "http://example.com/release/", self.lib)

    def test_cli(self):
        self.build()
        base = self.serve()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(AP.main(["fetch", self.obj("crate"), "--base", base, "--library", str(self.lib)]), 0)
            self.assertEqual(AP.main(["fetch", "0" * 64, "--base", base, "--library", str(self.lib)]), 1)
            self.assertEqual(AP.main(["nope"]), 2)
        self.assertTrue(out.getvalue().strip().endswith(self.obj("crate") + ".glb"))
        self.assertIn("ERROR", err.getvalue())

    def test_default_base_is_the_public_release(self):
        self.assertEqual(AP.default_base("v0.3.3"),
                         "https://github.com/iamar-ai/iamar-kit/releases/download/v0.3.3/")


if __name__ == "__main__":
    unittest.main(verbosity=2)
