"""kit-3: publish must not leak the builder key (argv, plain http, curlrc, hub body)."""
import os, re, subprocess, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def publish_block():
    text = (ROOT / "kit/iamar-world").read_text().replace("\r\n", "\n")
    return text.split('if [[ "$cmd" == publish ]]; then', 1)[1].split("\nfi\n", 1)[0]


class PublishSecret(unittest.TestCase):
    def test_bash_source(self):
        b = publish_block()
        self.assertNotIn('-H "Authorization', b)
        self.assertIn("curl -q ", b)
        self.assertIn("-K -", b)
        self.assertIn("https required", b)

    def test_cmd_source(self):
        t = (ROOT / "kit/iamar-world.cmd").read_text()
        pub = t.split("\n:publish\n", 1)[1].split("\n:cmd_compile_typescript\n", 1)[0]
        self.assertNotIn('-H "Authorization', pub)
        self.assertIn("-q -sS -K", pub)
        self.assertIn("https required", pub)

    def run_hub(self, hub):
        """Run the bash publish URL guard with a stub curl; return (rc, stderr, curl_ran)."""
        b = publish_block()
        guard = b.split("hub=", 1)[1].split("  bkey=", 1)[0]
        script = "hub=" + guard + "\necho GUARD_PASSED\n"
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                           env={**os.environ, "IAMAR_HUB": hub}, timeout=30)
        return r.returncode, r.stderr, "GUARD_PASSED" in r.stdout

    def test_guard(self):
        for bad in ("http://hub.example.com", "ws://hub.example.com/signal", "ftp://x", "http://localhost.evil.com"):
            rc, err, ok = self.run_hub(bad)
            self.assertFalse(ok, bad)
        for good in ("https://hub.vessences.com", "wss://hub.vessences.com/signal",
                     "http://localhost:8791", "http://127.0.0.1:8791"):
            rc, err, ok = self.run_hub(good)
            self.assertTrue(ok, good + err)


if __name__ == "__main__":
    unittest.main()
