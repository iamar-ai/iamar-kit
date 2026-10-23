#!/usr/bin/env python3
"""iamar-world doctor: JSON shape, required/optional split, exit code, fix text on every gap."""
import json, os, shutil, subprocess, sys, tempfile

DOC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "doctor", "doctor.py")


def run(*args, env=None):
    e = dict(os.environ); e.update(env or {})
    return subprocess.run([sys.executable, "-I", DOC, *args], capture_output=True, text=True, env=e)


with tempfile.TemporaryDirectory() as t:
    pack = os.path.join(t, "iamar-kit.pck"); open(pack, "wb").close()
    brw = os.path.join(t, "iamar"); open(brw, "w").close()
    r = run("--json", env={"IAMAR_KIT_PACK": pack, "IAMAR_BROWSER": brw})
    d = json.loads(r.stdout)
    by = {c["id"]: c for c in d["checks"]}
    assert by["kit_pack"]["status"] == "OK" and by["browser"]["status"] == "OK", by
    assert d["ok"] and r.returncode == 0, r
    r = run("--json", env={"IAMAR_KIT_PACK": os.path.join(t, "none.pck"), "IAMAR_BROWSER": os.path.join(t, "none")})
    d = json.loads(r.stdout)
    by = {c["id"]: c for c in d["checks"]}
    assert not d["ok"] and r.returncode == 1
    assert by["browser"]["status"] == "MISSING" and by["browser"]["fix"] and by["browser"]["needed_for"]
    for c in d["checks"]:
        assert c["status"] in ("OK", "MISSING", "OPTIONAL")
        assert c["status"] == "OK" or c["fix"], c
    h = run(env={"IAMAR_BROWSER": os.path.join(t, "none"), "IAMAR_KIT_PACK": pack})
    assert "DOCTOR FAILED" in h.stdout and "NEXT:" in h.stdout and "fix:" in h.stdout
    # The launcher must route `doctor` to doctor.py (it once fell through to style_lint.py).
    sh = shutil.which("bash")
    if sh:
        e = dict(os.environ, PYTHON=sys.executable, IAMAR_KIT_PACK=pack, IAMAR_BROWSER=brw)
        w = subprocess.run([sh, os.path.join(os.path.dirname(DOC), "..", "iamar-world"), "doctor", "--json"],
                           capture_output=True, text=True, env=e)
        assert '"checks"' in w.stdout, (w.stdout, w.stderr)
    # signing key (decision #97): none -> the commands to make it; one others can read -> a required fix
    cfg = os.path.join(t, "cfg")
    keyenv = {"IAMAR_KIT_PACK": pack, "IAMAR_BROWSER": brw, "XDG_CONFIG_HOME": cfg, "APPDATA": cfg}
    d = json.loads(run("--json", env=keyenv).stdout)
    by = {c["id"]: c for c in d["checks"]}
    assert by["signing_key"]["status"] == "OPTIONAL" and "genpkey" in by["signing_key"]["fix"], by["signing_key"]
    if os.name != "nt":
        kd = os.path.join(cfg, "iamar", "signing"); os.makedirs(kd)
        k = os.path.join(kd, "me.key"); open(k, "w").write("x"); os.chmod(k, 0o644)
        d = json.loads(run("--json", env=keyenv).stdout)
        c = {c["id"]: c for c in d["checks"]}["signing_key_private"]
        assert c["status"] == "MISSING" and "chmod 600" in c["fix"] and not d["ok"], c
        os.chmod(k, 0o600)
        d = json.loads(run("--json", env=keyenv).stdout)
        assert {c["id"]: c for c in d["checks"]}["signing_key_private"]["status"] == "OK" and d["ok"], d
print("doctor_test OK")
