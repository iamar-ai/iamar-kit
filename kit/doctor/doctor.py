#!/usr/bin/env python3
"""iamar-world doctor: check every prerequisite of the kit and print the one-line fix for each.

  iamar-world doctor            human list: OK / MISSING / OPTIONAL, fix, and which steps need it
  iamar-world doctor --json     the same as {"checks": [...], "ok": bool}

Exit 0 when nothing REQUIRED is missing, 1 otherwise. OPTIONAL items never fail the run.
Pure standard library; the Python-only extras (numpy, Pillow) are probed, not imported.
"""
import argparse, glob, importlib.util, json, os, platform, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "publish"))
from signing_key import privacy, provision_commands, signing_dir as signing_dir_of  # noqa: E402
KIT = os.path.dirname(HERE)
WIN = os.name == "nt"
HOME = os.path.expanduser("~")


def first_file(paths):
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return ""


def run_version(cmd, rx):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        m = re.search(rx, (out.stdout or "") + (out.stderr or ""))
        return tuple(int(x) for x in m.groups()) if m else None
    except Exception:
        return None


def kit_pack():
    local = os.environ.get("LOCALAPPDATA", os.path.join(HOME, "AppData", "Local"))
    return first_file([os.environ.get("IAMAR_KIT_PACK", ""), os.path.join(KIT, "iamar-kit.pck"),
                       os.path.join(local, "iamar", "kit", "iamar-kit.pck") if WIN else "",
                       os.path.join(HOME, ".iamar", "kit", "iamar-kit.pck")])


def browser():
    exe = ["iamar.exe", "Oakhaven.exe"] if WIN else ["Oakhaven.x86_64", "iamar"]
    cands = [os.environ.get("IAMAR_BROWSER", "")]
    for n in exe:
        cands += [os.path.join(KIT, "..", n)]
    cands += glob.glob(os.path.join(KIT, "..", "*.AppImage")) + glob.glob(os.path.join(KIT, "runtime", "**", "*.AppImage"), recursive=True)
    cands += glob.glob(os.path.join(KIT, "runtime", "**", "iamar.exe"), recursive=True)
    return first_file([os.path.normpath(c) for c in cands if c])


def signing_key():
    base = os.environ.get("APPDATA") if WIN else os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config"))
    d = os.path.join(base or HOME, "iamar", "signing")
    return d if os.path.isdir(d) and os.listdir(d) else ""


def logged_in():
    for base in ([os.environ.get("APPDATA", "")] if WIN else [os.environ.get("XDG_DATA_HOME", os.path.join(HOME, ".local", "share")), os.path.join(HOME, ".config")]):
        for p in glob.glob(os.path.join(base, "**", "settings.cfg"), recursive=True)[:20] if base else []:
            try:
                if re.search(r"^token\s*=\s*\"[^\"]+\"", open(p, encoding="utf-8", errors="replace").read(), re.M):
                    return True
            except OSError:
                pass
    return False


def checks():
    out = []

    def add(cid, level, ok, detail, fix, needed):
        out.append({"id": cid, "level": level, "status": "OK" if ok else ("MISSING" if level == "required" else "OPTIONAL"),
                    "detail": detail, "fix": "" if ok else fix, "needed_for": needed})

    pack = kit_pack()
    add("kit_pack", "required", bool(pack), pack or "iamar-kit.pck not found",
        "turn on Developer mode in the iamar browser (Esc menu), or download the kit from https://downloads.vessences.com/kit and put iamar-kit.pck beside kit/ (or set IAMAR_KIT_PACK)",
        "validate, preview, package, every browser-run command")
    b = browser()
    add("browser", "required", bool(b), b or "no iamar browser beside kit/",
        "put kit/ beside the downloaded iamar browser, set IAMAR_BROWSER=/path/to/iamar, or run kit/runtime_fetch" + (".cmd" if WIN else ".sh") + " browser",
        "validate, preview, perf, package, playtest")
    py = sys.version_info
    add("python", "required", py >= (3, 8), f"Python {py.major}.{py.minor}.{py.micro}", "install Python 3.8 or newer from https://www.python.org", "lint, audit, shots, assets search, this doctor")
    for mod, pipname in (("numpy", "numpy"), ("PIL", "Pillow")):
        add(f"python_{pipname.lower()}", "optional", importlib.util.find_spec(mod) is not None, pipname,
            f"{os.path.basename(sys.executable) or 'python'} -m pip install {pipname}", "audit, materials, shots, compare-shots (texture and screenshot checks)")
    nbin = os.environ.get("IAMAR_TS_NODE") or shutil.which("node") or ""
    nv = run_version([nbin, "--version"], r"v(\d+)\.(\d+)") if nbin else None
    add("node", "optional", bool(nv and nv[0] >= 20), f"Node {'.'.join(map(str, nv))}" if nv else "Node not found",
        "install Node 20 or newer (https://nodejs.org), or let the kit fetch its own: kit/runtime_fetch" + (".cmd" if WIN else ".sh") + " node",
        "compile-typescript (TypeScript world scripts)")
    bl = os.environ.get("BLENDER") or shutil.which("blender") or first_file(glob.glob(os.path.join(HOME, "opt", "blender-*", "blender")) + ["/usr/bin/blender", "/snap/bin/blender"]
                                                                          + glob.glob("C:/Program Files/Blender Foundation/Blender */blender.exe"))
    bv = run_version([bl, "--version"], r"Blender (\d+)\.(\d+)") if bl else None
    add("blender", "optional", bool(bv and bv >= (4, 2)), f"Blender {'.'.join(map(str, bv))}" if bv else "Blender not found",
        "install Blender 4.2 or newer (https://www.blender.org) or set BLENDER=/path/to/blender", "blender, blender-run, own meshes")
    disp = WIN or platform.system() == "Darwin" or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    add("display", "optional", disp, "a display is available" if disp else "no DISPLAY (headless)",
        "run preview under a virtual display: xvfb-run -a iamar-world preview ... (never your real :0 desktop)", "preview, perf, shots")
    key = signing_key()
    if not key:
        cmds = provision_commands(os.path.join(signing_dir_of(), "<your-name>.key"))
        add("signing_key", "optional", False, "no signing key yet",
            "create it once in your own terminal (the kit never writes it; it stays on this computer, never commit it): "
            + " ; ".join(c for c in cmds if not c.startswith("#")), "package, publish-local, signed worlds")
    else:
        keys = sorted(f for f in os.listdir(key) if f.endswith(".key"))
        bad = [privacy(os.path.join(key, f)) for f in keys]
        bad = [b for b in bad if not b[0]]
        add("signing_key_private", "required" if bad else "optional", not bad,
            bad[0][1] if bad else f"{len(keys)} key(s) in {key}, owner only",
            (bad[0][2] + " (anyone who can read a key can sign worlds as you)") if bad else "", "package, publish-local")
    add("hub_login", "optional", logged_in(), "signed in to the hub" if logged_in() else "no sign-in token found",
        "open the iamar browser, sign in with your iamar account (Esc menu > Account), then Start Hosting", "register and host a world")
    return out


def main(argv):
    ap = argparse.ArgumentParser(prog="iamar-world doctor")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = checks()
    ok = not any(c["status"] == "MISSING" for c in res)
    if a.json:
        print(json.dumps({"checks": res, "ok": ok}, indent=2))
    else:
        for c in res:
            print(f"{c['status']:<8} {c['id']}: {c['detail']}")
            if c["fix"]:
                print(f"         fix: {c['fix']}")
                print(f"         needed for: {c['needed_for']}")
        print("DOCTOR " + ("OK" if ok else "FAILED: fix the MISSING items above") )
        print("NEXT: " + ("iamar-world new <folder>" if ok else "fix the first MISSING item, then run iamar-world doctor again"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
