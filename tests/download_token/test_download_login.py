"""iamar-world download-login end to end (an internal task): a scripted agent gets a download pass that a
person approved, saves it, and the runtime fetch sends it.

    python3 -I tests/download_token/test_download_login.py -v
    IAMAR_SITE_SERVER=/path/to/iamar.ai/site/iamar_site_server.py python3 -I tests/download_token/test_download_login.py -v

By default a small fake of the iamar.ai agent routes runs on 127.0.0.1 (same protocol as
iamar.ai site/iamar_site_server.py). With IAMAR_SITE_SERVER the real server module is loaded and
served instead. The person's approval is an HTTP form post with a synthetic password. No real
credential, no network beyond 127.0.0.1. On Windows the .cmd launcher is tested too.
"""
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import types
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "kit"
PASSWORD = "synthetic test password"
REV = "0123abcd"
WINDOWS = os.name == "nt"


def find_bash():
    if not WINDOWS:
        return shutil.which("bash")
    for c in (r"C:\Program Files\Git\bin\bash.exe", shutil.which("bash")):
        if c and Path(c).is_file() and "System32" not in c:
            return c
    return None


class FakeSite(BaseHTTPRequestHandler):
    """The /download/agent protocol of iamar.ai, without the gate's cookie page details."""
    codes = {}
    tokens = set()
    files = {}

    def log_message(self, *a):
        pass

    def _reply(self, status, obj=None, body=b""):
        data = json.dumps(obj).encode() if obj is not None else body
        self.send_response(status)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path == "/download/agent/start":
            code = "BCDF-" + hashlib.sha256(os.urandom(8)).hexdigest()[:4].upper().translate(str.maketrans("0123456789ABCDEF", "23456789BCDFGHJK"))
            secret = hashlib.sha256(os.urandom(16)).hexdigest()
            self.codes[code] = {"secret": secret, "approved": False}
            return self._reply(200, {"code": code, "device_secret": secret, "expires_in": 600, "interval": 3,
                                     "verify_url": f"https://iamar.ai/download/agent?code={code}"})
        if self.path == "/download/agent/approve":
            form = urllib.parse.parse_qs(raw.decode())
            code = (form.get("code") or [""])[0].upper()
            if (form.get("password") or [""])[0] != PASSWORD or code not in self.codes:
                return self._reply(401, body=b"no")
            self.codes[code]["approved"] = True
            return self._reply(200, body=b"Your agent may download")
        if self.path == "/download/agent/poll":
            req = json.loads(raw)
            e = self.codes.get(req["code"])
            if not e or e["secret"] != req["device_secret"]:
                return self._reply(410, {"status": "expired"})
            if not e["approved"]:
                return self._reply(200, {"status": "pending"})
            del self.codes[req["code"]]
            token = "iamar-dl1.9999999999." + hashlib.sha256(os.urandom(8)).hexdigest()
            self.tokens.add(token)
            return self._reply(200, {"status": "approved", "token": token, "expires": 9999999999})
        self._reply(404, body=b"")

    def do_GET(self):
        auth = self.headers.get("Authorization") or ""
        name = self.path.removeprefix(f"/download/city/{REV}/")
        if name in self.files and auth.startswith("Bearer ") and auth[7:] in self.tokens:
            return self._reply(200, body=self.files[name])
        self._reply(401, body=b"")


@contextlib.contextmanager
def site(tls=None, files=None):
    """The iamar.ai agent routes on 127.0.0.1; tls=(cert, key) serves HTTPS. files: name -> bytes
    under /download/city/<REV>/ (browser.zip is always there)."""
    files = {"browser.zip": b"zipbytes", **(files or {})}
    path = os.environ.get("IAMAR_SITE_SERVER")
    tmp = tempfile.TemporaryDirectory()
    if path:
        if "fcntl" not in sys.modules:
            try:
                import fcntl  # noqa: F401
            except ImportError:
                sys.modules["fcntl"] = types.ModuleType("fcntl")
        spec = importlib.util.spec_from_file_location("iamar_site_e2e", path)
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)
        dl = Path(tmp.name)
        (dl / "city" / REV).mkdir(parents=True)
        for name, data in files.items():
            (dl / "city" / REV / name).write_bytes(data)
        (dl / ".password_sha256").write_text(hashlib.sha256(PASSWORD.encode()).hexdigest())
        (dl / ".cookie_secret").write_text("t" * 40)
        server.DOWNLOADS_DIR = dl
        server.publication_read = contextlib.nullcontext   # no deployment record on a test machine
        handler = server.Handler
    else:
        FakeSite.files = files
        handler = FakeSite
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(*tls)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"{'https' if tls else 'http'}://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        tmp.cleanup()


def approve(base, url, context=None):
    """The person: opens the link, types the password, presses Allow."""
    code = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["code"][0]
    req = urllib.request.Request(base + "/download/agent/approve", method="POST",
                                 data=urllib.parse.urlencode({"code": code, "password": PASSWORD}).encode(),
                                 headers={"Origin": base, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10, context=context) as r:
        assert b"Your agent may download" in r.read()


def fetch(base, token):
    req = urllib.request.Request(f"{base}/download/city/{REV}/browser.zip", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


class DownloadLoginTests(unittest.TestCase):
    def run_login(self, launcher, base, mode, token_file):
        env = {k: v for k, v in os.environ.items() if not k.startswith("IAMAR_")}
        env.update(IAMAR_SITE=base, IAMAR_DOWNLOAD_TOKEN_FILE=Path(token_file).as_posix())
        return subprocess.run(launcher + [mode], env=env, capture_output=True, text=True, timeout=60)

    def flow(self, launcher):
        with site() as base, tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "iamar" / "download_token"
            started = self.run_login(launcher, base, "start", token_file)
            self.assertEqual(started.returncode, 0, started.stderr)
            m = re.search(r"HUMAN STEP: open (\S+) in your web browser, check that it shows the code ([A-Z0-9-]{9})", started.stdout)
            self.assertIsNotNone(m, started.stdout)
            self.assertTrue(m.group(1).endswith("/download/agent?code=" + m.group(2)))
            approve(base, m.group(1))
            waited = self.run_login(launcher, base, "wait", token_file)
            self.assertEqual(waited.returncode, 0, waited.stderr)
            self.assertIn("DOWNLOAD PASS saved", waited.stdout)
            token = token_file.read_text().strip()
            self.assertRegex(token, r"^iamar-dl1\.\d+\.[0-9a-f]{64}$")
            self.assertNotIn(token, started.stdout + started.stderr + waited.stdout + waited.stderr)
            self.assertEqual(fetch(base, token), b"zipbytes")
            again = self.run_login(launcher, base, "wait", token_file)
            self.assertEqual(again.returncode, 2)        # the pending code is used up

    @unittest.skipUnless(find_bash(), "needs bash")
    def test_bash_launcher(self):
        self.flow([find_bash(), "--noprofile", "--norc", str(KIT / "download_login.sh")])

    @unittest.skipUnless(WINDOWS, "Windows only")
    def test_cmd_launcher(self):
        self.flow(["cmd.exe", "/d", "/c", str(KIT / "download_login.cmd")])

    def test_unapproved_code_times_out_cleanly_on_expiry(self):
        if not find_bash():
            self.skipTest("needs bash")
        with site() as base, tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "download_token"
            launcher = [find_bash(), "--noprofile", "--norc", str(KIT / "download_login.sh")]
            self.assertEqual(self.run_login(launcher, base, "start", token_file).returncode, 0)
            pending = Path(str(token_file) + ".pending")
            code, secret, _ = pending.read_text().split()
            pending.write_bytes(f"{code} {secret} 1\n".encode())   # deadline long past
            done = self.run_login(launcher, base, "wait", token_file)
            self.assertEqual(done.returncode, 4)
            self.assertIn("nobody approved", done.stderr)
            self.assertFalse(token_file.exists())

    def test_non_https_site_is_refused(self):
        if not find_bash():
            self.skipTest("needs bash")
        launcher = [find_bash(), "--noprofile", "--norc", str(KIT / "download_login.sh")]
        done = self.run_login(launcher, "http://example.com", "start", Path(tempfile.gettempdir()) / "unused_token")
        self.assertEqual(done.returncode, 2)


class RuntimeFetchSendsThePass(unittest.TestCase):
    """runtime_fetch.sh gives curl the pass as a Bearer header on stdin, never on its command line."""

    @unittest.skipUnless(find_bash() and not WINDOWS, "needs a POSIX bash (the fake curl is a bash script)")
    def test_bearer_goes_through_curl_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bin_dir = tmp / "bin"; bin_dir.mkdir()
            (bin_dir / "curl").write_text('#!/bin/bash\nprintf "%s\\n" "$*" > "$CAPTURE.args"; cat > "$CAPTURE.stdin"; exit 22\n')
            (bin_dir / "curl").chmod(0o755)
            token = "iamar-dl1.9999999999." + "a" * 64
            (tmp / "tok").write_text(token + "\n")
            env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp), "CAPTURE": str(tmp / "cap"),
                   "IAMAR_DOWNLOAD_TOKEN_FILE": str(tmp / "tok"), "IAMAR_KIT_RUNTIME": str(tmp / "rt")}
            done = subprocess.run([find_bash(), "--noprofile", "--norc", str(KIT / "runtime_fetch.sh"), "browser"],
                                  env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 3, done.stderr)
            self.assertIn("refused the download pass", done.stderr)
            self.assertEqual((tmp / "cap.stdin").read_text(), f'header = "Authorization: Bearer {token}"\n')
            self.assertNotIn(token, (tmp / "cap.args").read_text())
            self.assertIn("-K -", (tmp / "cap.args").read_text())

    @unittest.skipUnless(find_bash() and not WINDOWS, "needs a POSIX bash")
    def test_no_pass_and_no_code_names_the_human_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "IAMAR_KIT_RUNTIME": str(Path(tmp) / "rt")}
            done = subprocess.run([find_bash(), "--noprofile", "--norc", str(KIT / "runtime_fetch.sh"), "browser"],
                                  env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 3)
            self.assertIn("HUMAN STEP: run iamar-world download-login", done.stderr)


class AgentFetchesTheBrowser(unittest.TestCase):
    """The whole agent path against https://iamar.ai: download-login start, the person approves,
    download-login wait, then runtime_fetch.sh browser downloads the pinned browser with the pass,
    checks its sha256 against runtime.lock and installs it. The real curl talks TLS to the local
    site through --connect-to, so the URL, the iamar.ai-only Bearer rule and --proto =https are
    exactly the shipped ones. The pass must never appear on a command line."""

    @unittest.skipUnless(find_bash() and not WINDOWS and sys.platform.startswith("linux")
                         and shutil.which("curl") and shutil.which("openssl") and shutil.which("sha256sum"),
                         "needs Linux bash, curl, openssl and sha256sum")
    def test_login_then_runtime_fetch_installs_the_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            cert, key = tmp / "iamar.ai.pem", tmp / "iamar.ai.key"
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                            "-subj", "/CN=iamar.ai", "-addext", "subjectAltName=DNS:iamar.ai",
                            "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)
            appimage = b"\x7fELF fake iamar browser " + os.urandom(64)
            name = f"iamar-29-linux-x86_64-{REV}.AppImage"
            with site(tls=(str(cert), str(key)), files={name: appimage}) as base:
                port = base.rsplit(":", 1)[1]
                kit = tmp / "kit"; kit.mkdir()
                for f in ("runtime_fetch.sh", "download_login.sh"):
                    shutil.copy(KIT / f, kit / f)
                arch = "arm64" if os.uname().machine in ("aarch64", "arm64") else "x64"
                (kit / "runtime.lock").write_text(
                    f"browser linux-{arch} {REV} https://iamar.ai/download/city/{REV}/{name} "
                    f"{hashlib.sha256(appimage).hexdigest()} .\n")
                bin_dir = tmp / "bin"; bin_dir.mkdir()
                real_curl = shutil.which("curl")
                # The shipped scripts put -q first; keep it first, then route iamar.ai:443 to the test site.
                (bin_dir / "curl").write_text(
                    "#!/bin/bash\n"
                    'printf "%s\\n" "$*" >> "$CURL_ARGS"\n'
                    '[[ "$1" == -q ]] && shift\n'
                    f'exec {real_curl} -q --connect-to iamar.ai:443:127.0.0.1:{port} --cacert {cert} "$@"\n')
                (bin_dir / "curl").chmod(0o755)
                token_file = tmp / "cfg" / "iamar" / "download_token"
                env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp), "CURL_ARGS": str(tmp / "curl.args"),
                       "IAMAR_SITE": "https://iamar.ai", "IAMAR_DOWNLOAD_TOKEN_FILE": str(token_file),
                       "IAMAR_KIT_RUNTIME": str(tmp / "rt")}
                bash = [find_bash(), "--noprofile", "--norc"]

                def run(*argv):
                    return subprocess.run(bash + [str(kit / argv[0]), *argv[1:]], env=env,
                                          capture_output=True, text=True, timeout=60)

                before = run("runtime_fetch.sh", "browser")       # no pass yet: names the human step
                self.assertEqual(before.returncode, 3, before.stderr)
                self.assertIn("HUMAN STEP: run iamar-world download-login", before.stderr)
                started = run("download_login.sh", "start")
                self.assertEqual(started.returncode, 0, started.stderr)
                m = re.search(r"HUMAN STEP: open (https://iamar\.ai/download/agent\?code=[A-Z0-9-]{9}) ", started.stdout)
                self.assertIsNotNone(m, started.stdout)
                person = ssl.create_default_context(cafile=str(cert))
                person.check_hostname = False   # the person's browser reaches the test site as 127.0.0.1
                approve(base, m.group(1), person)
                waited = run("download_login.sh", "wait")
                self.assertEqual(waited.returncode, 0, waited.stderr)
                token = token_file.read_text().strip()
                self.assertEqual(token_file.stat().st_mode & 0o777, 0o600)
                got = run("runtime_fetch.sh", "browser")
                self.assertEqual(got.returncode, 0, got.stderr)
                exe = Path(got.stdout.strip())
                self.assertEqual(exe, tmp / "rt" / "browser" / "iamar.AppImage")
                self.assertEqual(exe.read_bytes(), appimage)
                self.assertTrue(os.access(exe, os.X_OK))
                self.assertEqual((exe.parent / ".runtime").read_text().split(),
                                 [REV, hashlib.sha256(appimage).hexdigest()])
                again = run("runtime_fetch.sh", "browser")         # installed: no second download
                self.assertEqual((again.returncode, again.stdout.strip()), (0, str(exe)))
                args = (tmp / "curl.args").read_text()
                self.assertEqual(args.count(f"/download/city/{REV}/{name}"), 1)
                for out in (started.stdout, started.stderr, waited.stdout, waited.stderr, got.stdout, got.stderr, args):
                    self.assertNotIn(token, out)
                # A damaged download is refused, not installed.
                (kit / "runtime.lock").write_text(
                    f"browser linux-{arch} other https://iamar.ai/download/city/{REV}/{name} {'0' * 64} .\n")
                bad = run("runtime_fetch.sh", "browser")
                self.assertEqual(bad.returncode, 4, bad.stderr)
                self.assertIn("does not match kit/runtime.lock", bad.stderr)
                self.assertEqual(exe.read_bytes(), appimage)


if __name__ == "__main__":
    unittest.main()
