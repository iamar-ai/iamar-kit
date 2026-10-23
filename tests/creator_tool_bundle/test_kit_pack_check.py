import struct, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "tools/kit_pack_check.py"


def pck(minor):
    return b"GDPC" + struct.pack("<IIII", 3, 4, minor, 2) + b"\0" * 8


def run(target, minor="7"):
    return subprocess.run([sys.executable, str(TOOL), str(target), "--minor", "4." + minor],
                          capture_output=True, text=True)


class PackCheck(unittest.TestCase):
    def test_zip_cases(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for name, member, data, ok in (("good", "kit/iamar-kit.pck", pck(7), True),
                                           ("old", "kit/iamar-kit.pck", pck(6), False),
                                           ("none", "kit/AGENT_KIT.md", b"x", False),
                                           ("junk", "kit/iamar-kit.pck", b"x" * 30, False)):
                z = d / (name + ".zip")
                with zipfile.ZipFile(z, "w") as f:
                    f.writestr(member, data)
                r = run(z)
                self.assertEqual(r.returncode == 0, ok, (name, r.stderr))
            (d / "a.pck").write_bytes(pck(7))
            self.assertEqual(run(d / "a.pck").returncode, 0)
            self.assertNotEqual(run(d / "a.pck", "8").returncode, 0)


if __name__ == "__main__":
    unittest.main()
