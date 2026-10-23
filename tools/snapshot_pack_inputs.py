#!/usr/bin/env python3
"""Snapshot plain pack inputs from one immutable Git commit; never read the worktree.

The destination must not exist. It is created inside build_pack.sh's private
temporary directory. Only direct scripts/kit/*.gd and the three pack driver
files are extracted; Git filters, export attributes, symlinks, caches, browser
scripts and project state cannot add payloads.
"""
import json
import pathlib
import re
import subprocess
import sys


DRIVERS = {
    "pack/project.godot": "project.godot",
    "tools/build_pack.gd": "build_pack.gd",
    "tools/list_pack.gd": "list_pack.gd",
}
SCRIPT = re.compile(r"scripts/kit/[a-z_0-9]+\.gd\Z")
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def git(root, *args):
    # Do not honor local replacement objects when interpreting the recorded OID.
    return subprocess.check_output(["git", "--no-replace-objects", "-C", str(root), *args])


def selected_entries(raw):
    entries = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        header, path_raw = record.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split(" ")
        path = path_raw.decode("utf-8")
        if path not in DRIVERS:
            if not path.startswith("scripts/kit/") or not path.endswith(".gd"):
                continue
            if not SCRIPT.fullmatch(path):
                raise ValueError("unsupported pack script path: " + repr(path))
        if mode not in ("100644", "100755") or kind != "blob" or not OID.fullmatch(oid):
            raise ValueError("pack inputs must be regular Git blobs: " + repr(path))
        if path in entries:
            raise ValueError("duplicate pack input: " + repr(path))
        entries[path] = oid
    if not set(DRIVERS).issubset(entries):
        raise ValueError("commit is missing a pack driver")
    if not any(SCRIPT.fullmatch(path) for path in entries):
        raise ValueError("commit has no direct scripts/kit/*.gd")
    return entries


def snapshot(root, commit, destination):
    if not OID.fullmatch(commit):
        raise ValueError("expected a full commit OID, not a moving ref")
    if git(root, "cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("pack revision is not a commit")
    entries = selected_entries(git(root, "ls-tree", "-r", "-z", commit, "--",
                                  "scripts/kit", *DRIVERS))
    destination = pathlib.Path(destination)
    destination.mkdir(mode=0o700)  # Never reuse or merge with an existing snapshot.
    (destination / "scripts").mkdir()
    names = []
    for path, oid in sorted(entries.items()):
        target = DRIVERS.get(path)
        if target is None:
            target = "scripts/" + pathlib.PurePosixPath(path).name
            names.append("res://" + path)
        (destination / target).write_bytes(git(root, "cat-file", "blob", oid))
    (destination / "inputs.json").write_text(
        json.dumps({"commit": commit, "paths": names, "blobs": entries}, sort_keys=True) + "\n",
        encoding="utf-8")


def verify_listing(manifest_path, listing_path):
    expected = json.loads(pathlib.Path(manifest_path).read_text(encoding="utf-8"))["paths"]
    actual = [line[5:] for line in pathlib.Path(listing_path).read_text(encoding="utf-8").splitlines()
              if line.startswith("PACK ")]
    # Lists, not sets: duplicate entries or a same-count substitution also fail.
    if sorted(actual) != expected:
        raise ValueError("pack entries do not match the committed input manifest")
    return len(expected)


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "snapshot":
        snapshot(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 4 and sys.argv[1] == "verify":
        print(verify_listing(sys.argv[2], sys.argv[3]))
    else:
        raise ValueError("usage: snapshot_pack_inputs.py snapshot ROOT COMMIT DEST | verify MANIFEST LISTING")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        sys.exit("build_pack: " + str(exc))
