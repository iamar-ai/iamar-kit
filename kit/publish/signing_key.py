"""Signing keys a creator makes themselves (decision #97, the maintainer 2026-10-23).

No released browser can run `keygen` yet (it needs the unqualified native private-pair API), so the
kit never writes a private key. It prints the commands the user runs once, in their own terminal,
and sign/package use the result through the existing-key workflow (docs/PRIVATE_KEY_CREATION.md).
Shared by `publish-local` (prints the commands when the key is missing) and `doctor` (checks that
an existing key is private). Pure standard library.
"""
import os, re, shutil, stat, subprocess

WIN = os.name == "nt"
HOME = os.path.expanduser("~")


def signing_dir():
    base = os.environ.get("APPDATA") if WIN else os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config"))
    return os.path.join(base or HOME, "iamar", "signing")


def key_path(key):
    """A key name (in the signing folder) or a path to a .key file."""
    if key.endswith(".key") or os.sep in key or "/" in key:
        return os.path.abspath(os.path.expanduser(key))
    return os.path.join(signing_dir(), key + ".key")


def _git_openssl():
    for p in (r"C:\Program Files\Git\usr\bin\openssl.exe", r"C:\Program Files\Git\mingw64\bin\openssl.exe"):
        if os.path.isfile(p):
            return p
    return ""


def provision_commands(path, windows=None):
    """The commands the user runs once to create a private RSA key at `path` (owner-only)."""
    windows = WIN if windows is None else windows
    d = os.path.dirname(path)
    if windows:
        ossl = shutil.which("openssl") or _git_openssl() or r"C:\Program Files\Git\usr\bin\openssl.exe"
        return [
            "# PowerShell (openssl comes with Git for Windows)",
            f'New-Item -ItemType Directory -Force "{d}" | Out-Null',
            f'& "{ossl}" genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "{path}"',
            f'icacls "{path}" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"',
        ]
    return [
        f'mkdir -p "{d}" && chmod 700 "{d}"',
        f'(umask 077 && openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "{path}")',
        f'chmod 600 "{path}"',
    ]


def privacy(path):
    """(ok, detail, fix): only the owner may read the key file."""
    if WIN:
        try:
            out = subprocess.run(["icacls", path], capture_output=True, text=True, timeout=15).stdout
        except (OSError, subprocess.SubprocessError):
            return True, "permissions not checked (icacls unavailable)", ""
        wide = [g for g in ("Everyone", "BUILTIN\\Users", "Authenticated Users") if re.search(re.escape(g) + r":", out, re.I)]
        if wide:
            return False, f"{path} is readable by {', '.join(wide)}", f'icacls "{path}" /inheritance:r /grant:r "%USERNAME%:(R,W)"'
        return True, f"{path} (owner only)", ""
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        return False, f"{path} is readable by others (mode {mode:o})", f'chmod 600 "{path}"'
    return True, f"{path} (mode {mode:o})", ""
