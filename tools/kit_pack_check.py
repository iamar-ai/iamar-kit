#!/usr/bin/env python3
"""Checks that a kit holds iamar-kit.pck built by the Godot minor the browser runs.

  kit_pack_check.py <kit .zip | iamar-kit.pck> --minor 4.7
  kit_pack_check.py <kit .zip | iamar-kit.pck> --browser <the iamar browser source (not public) checkout>

A Godot pack records the engine version that wrote it (header: GDPC, format, major, minor,
patch). A pack from another minor does not load in the browser, so the bundle, the release
build and the publish script all refuse it. Exit 0 ok, 1 refused, 2 usage.
"""
import argparse
import pathlib
import re
import struct
import sys
import zipfile

MAGIC = b"GDPC"


def pck_version(head):
    if head[:4] != MAGIC or len(head) < 20:
        sys.exit("kit_pack_check: iamar-kit.pck is not a Godot pack (no GDPC header)")
    major, minor, patch = struct.unpack("<III", head[8:20])
    return major, minor, patch


def browser_minor(browser):
    text = (pathlib.Path(browser) / "project.godot").read_text(encoding="utf-8")
    m = re.search(r'config/features=PackedStringArray\("(\d+\.\d+)"', text)
    if not m:
        sys.exit(f"kit_pack_check: no engine version in {browser}/project.godot")
    return m.group(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--minor")
    g.add_argument("--browser")
    a = ap.parse_args()
    want = a.minor or browser_minor(a.browser)
    path = pathlib.Path(a.target)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.rsplit("/", 1)[-1] == "iamar-kit.pck"]
            if not names:
                sys.exit(f"kit_pack_check: {path.name} has no iamar-kit.pck")
            with z.open(names[0]) as f:
                head = f.read(20)
    else:
        if not path.is_file():
            sys.exit(f"kit_pack_check: {path} is not a file")
        head = path.read_bytes()[:20]
    major, minor, patch = pck_version(head)
    if f"{major}.{minor}" != want:
        sys.exit(f"kit_pack_check: {path.name} was built by Godot {major}.{minor}.{patch}, "
                 f"the browser runs {want}: rebuild the pack with the browser's Godot")
    print(f"kit_pack_check: {path.name} ok (Godot {major}.{minor}.{patch})")


if __name__ == "__main__":
    main()
