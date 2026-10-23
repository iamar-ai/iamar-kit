"""Inert regression for an internal task: a built-in object adds 0 bytes to a world's download.

Its index `bytes` is the hash input (glTF + the shared trim-sheet textures), e.g. 6 MB for the
twin bed, so `assets list/search/show/use` must not print it as the object's size. Reads the
source only; never executes repository code."""
from pathlib import Path
import unittest

SRC = (Path(__file__).resolve().parents[2] / "scripts/kit/world_assets.gd").read_text(encoding="utf-8")


class BuiltinSize(unittest.TestCase):
    def test_line_uses_size_note(self):
        self.assertIn("static func _size_note(e: Dictionary) -> String:", SRC)
        self.assertIn('return "built in (0 bytes download)"', SRC)
        self.assertNotIn("e.name, e.bytes, e.triangles", SRC)

    def test_use_says_built_in(self):
        self.assertIn('"built in, 0 bytes in your download" if e.kind == "builtin"', SRC)


if __name__ == "__main__":
    unittest.main()
