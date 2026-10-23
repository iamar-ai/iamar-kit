#!/usr/bin/env python3
"""Inert unit fixtures: no Godot, Git process, downloads, signing, or publication.

Run explicitly after review: python3 -m unittest discover -s tools -p test_snapshot_pack_inputs.py
This file has NOT been executed while preparing the candidate.
"""
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "snapshot_pack_inputs", pathlib.Path(__file__).with_name("snapshot_pack_inputs.py"))
PACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACK)
COMMIT = "1" * 40
PATHS = ["pack/project.godot", "tools/build_pack.gd", "tools/list_pack.gd",
         "scripts/kit/world_a.gd", "scripts/kit/world_b.gd"]
BLOBS = {path: str(i) * 40 for i, path in enumerate(PATHS, start=2)}
BYTES = {oid: ("# inert committed fixture: " + path + "\n").encode()
         for path, oid in BLOBS.items()}


def record(path, mode="100644", kind="blob", oid=None):
    return (mode + " " + kind + " " + (oid or BLOBS.get(path, "f" * 40))
            + "\t" + path + "\0").encode()


TREE = b"".join(record(path) for path in PATHS)


class SnapshotTests(unittest.TestCase):
    def fake_git(self, root, *args):
        if args == ("cat-file", "-t", COMMIT):
            return b"commit\n"
        if args == ("ls-tree", "-r", "-z", COMMIT, "--", "scripts/kit", *PACK.DRIVERS):
            return TREE + record("scripts/kit/world_a.gd.uid")
        if args[:2] == ("cat-file", "blob"):
            return BYTES[args[2]]
        self.fail("unexpected or moving Git reference: " + repr(args))

    def test_snapshot_uses_blobs_not_dirty_untracked_or_ignored_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "repo"
            scripts = root / "scripts/kit"
            scripts.mkdir(parents=True)
            (scripts / "world_a.gd").write_text("dirty tracked fixture\n")
            (scripts / "untracked.gd").write_text("untracked fixture\n")
            (scripts / "ignored.gd").write_text("ignored fixture\n")
            (root / ".gitignore").write_text("ignored.gd\n")
            destination = pathlib.Path(tmp) / "snapshot"
            with mock.patch.object(PACK, "git", side_effect=self.fake_git):
                PACK.snapshot(root, COMMIT, destination)
            self.assertEqual(sorted(p.name for p in (destination / "scripts").iterdir()),
                             ["world_a.gd", "world_b.gd"])
            for path, oid in BLOBS.items():
                target = PACK.DRIVERS.get(path, "scripts/" + pathlib.PurePosixPath(path).name)
                self.assertEqual((destination / target).read_bytes(), BYTES[oid])
            manifest = json.loads((destination / "inputs.json").read_text())
            self.assertEqual(manifest["commit"], COMMIT)
            self.assertEqual(manifest["paths"], ["res://scripts/kit/world_a.gd", "res://scripts/kit/world_b.gd"])
            self.assertEqual(manifest["blobs"], BLOBS)

    def test_snapshot_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(PACK, "git", side_effect=self.fake_git):
            with self.assertRaises(FileExistsError):
                PACK.snapshot(tmp, COMMIT, tmp)

    def test_moving_ref_rejected_before_git(self):
        with mock.patch.object(PACK, "git") as git:
            for revision in ("HEAD", "main", "1" * 39, "--help", COMMIT + "^{tree}"):
                with self.subTest(revision=revision), self.assertRaises(ValueError):
                    PACK.snapshot("unused", revision, "unused")
            git.assert_not_called()

    def test_tag_or_tree_oid_is_not_a_commit(self):
        with mock.patch.object(PACK, "git", return_value=b"tag\n"):
            with self.assertRaises(ValueError):
                PACK.snapshot("unused", COMMIT, "unused")

    def test_invalid_inputs_fail_closed(self):
        driver_tree = b"".join(record(path) for path in PACK.DRIVERS)
        cases = {
            "no scripts": driver_tree,
            "missing driver": record("scripts/kit/world_a.gd"),
            "symlink script": driver_tree + record("scripts/kit/world_a.gd", "120000"),
            "symlink driver": TREE.replace(record("tools/build_pack.gd"), record("tools/build_pack.gd", "120000")),
            "nested script": TREE + record("scripts/kit/cache/injected.gd"),
            "unsafe name": TREE + record("scripts/kit/bad name.gd"),
            "duplicate": TREE + record("scripts/kit/world_a.gd"),
            "submodule": driver_tree + record("scripts/kit/world_a.gd", "160000", "commit"),
        }
        for label, tree in cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                PACK.selected_entries(tree)

    def test_uid_and_non_script_inputs_are_excluded(self):
        tree = TREE + record("scripts/kit/world_a.gd.uid") + record("scripts/kit/notes.txt")
        self.assertEqual(PACK.selected_entries(tree), BLOBS)

    def test_listing_requires_exact_names_and_multiplicity(self):
        expected = ["res://scripts/kit/world_a.gd", "res://scripts/kit/world_b.gd"]
        with tempfile.TemporaryDirectory() as tmp:
            manifest, listing = pathlib.Path(tmp) / "inputs.json", pathlib.Path(tmp) / "listing"
            manifest.write_text(json.dumps({"paths": expected}))
            listing.write_text("Godot inert banner\n" + "".join("PACK " + p + "\n" for p in reversed(expected)))
            self.assertEqual(PACK.verify_listing(manifest, listing), 2)
            for actual in ([], expected[:1], [expected[0], expected[0]],
                           [expected[0], "res://scripts/kit/injected.gd"],
                           expected + ["res://project.binary"],
                           expected + ["res://.godot/uid_cache.bin"],
                           expected + ["res://scripts/kit/account.gd"]):
                with self.subTest(actual=actual):
                    listing.write_text("".join("PACK " + p + "\n" for p in actual))
                    with self.assertRaises(ValueError):
                        PACK.verify_listing(manifest, listing)


if __name__ == "__main__":
    unittest.main()
