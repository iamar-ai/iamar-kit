#!/usr/bin/env python3
"""iamar-world publish: step order, key gate, version bump only on change, reuse when unchanged.

Runs against a stub launcher (IAMAR_WORLD_LAUNCHER) that records each kit command and fakes
package's output, so no browser is needed. The real flow was checked by hand against iamar 31.
On Windows the stub is an iamar-world.cmd in a folder whose name has a space, and the last part
checks that names with spaces, & | > ^ ! % = , ; reach it unchanged and run nothing (an internal task).
"""
import importlib.util, json, os, stat, subprocess, sys, tempfile

PUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "publish", "publish.py")

STUB = r'''#!/usr/bin/env python3
import json, os, sys
log = os.environ["STUB_LOG"]
open(log, "a").write(" ".join(sys.argv[1:2]) + "\n")
cmd, args = sys.argv[1], sys.argv[2:]
if cmd == "validate" and os.environ.get("STUB_FAIL") == "validate":
    print("ERROR budget triangles")
    if not os.environ.get("IAMAR_KIT_NO_NEXT"): print("NEXT: iamar-world validate x (fix the ERROR lines above, then rerun)")
    sys.exit(1)
if cmd == "keygen":
    print("keygen requires a browser with native private-pair API v1; use an existing externally provisioned key"); sys.exit(1)
if cmd == "package":
    world, out = args[0], args[1]
    assert not os.path.exists(out), "package must never overwrite"
    open(out, "w").write("pkg")
    m = json.load(open(os.path.join(world, "manifest.json")))
    m["signer"] = {"key_id": "rsa:x", "name": args[3]}          # like the real package
    json.dump(m, open(os.path.join(world, "manifest.json"), "w"))
    open(os.path.join(world, "signature.json"), "w").write("{}")
print("OK")
'''


def run(world, *extra, env):
    r = subprocess.run([sys.executable, "-I", PUB, world, "--key", "k", "--json", *extra],
                       capture_output=True, text=True, env=env)
    return r.returncode, json.loads(r.stdout)


WIN = os.name == "nt"
with tempfile.TemporaryDirectory(prefix="iamar publish ") as t:
    if WIN:   # the real launcher is a .cmd: publish must reach it through cmd.exe intact
        open(os.path.join(t, "stub.py"), "w").write(STUB)
        stub = os.path.join(t, "iamar-world.cmd")
        open(stub, "w").write('@"%s" "%s" %%*\n' % (sys.executable, os.path.join(t, "stub.py")))
    else:
        stub = os.path.join(t, "iamar-world")
        open(stub, "w").write(STUB)
        os.chmod(stub, os.stat(stub).st_mode | stat.S_IEXEC)
    log = os.path.join(t, "log")
    cfg = os.path.join(t, "cfg")
    env = dict(os.environ, IAMAR_WORLD_LAUNCHER=stub, STUB_LOG=log, XDG_CONFIG_HOME=cfg, APPDATA=cfg)
    w = os.path.join(t, "w")
    os.makedirs(w)
    json.dump({"id": "w", "version": "0.1.0", "author": {"name": "A"}}, open(os.path.join(w, "manifest.json"), "w"))
    open(os.path.join(w, "scene.json"), "w").write("{}")

    def steps():
        s = open(log).read().split(); open(log, "w").close(); return s

    # a failed child step must not leak its own NEXT: line (an internal task)
    r = subprocess.run([sys.executable, "-I", PUB, w, "--key", "k"], capture_output=True, text=True,
                       env=dict(env, STUB_FAIL="validate"))
    assert r.returncode != 0 and "ERROR budget triangles" in r.stdout and "NEXT: iamar-world" not in r.stdout.split("ERROR budget")[1], r.stdout
    steps()
    # no key: stops after validate, exit 2, and gives the commands the user runs (decision #97);
    # the kit itself never writes a key
    code, d = run(w, env=env)
    assert code == 2 and "commands" in d["error"] and d["key_commands"] and "--approve-keygen" not in d["next"], d
    assert any("genpkey" in c and "k.key" in c for c in d["key_commands"]), d
    assert steps() == ["validate"]
    assert not os.path.exists(os.path.join(cfg, "iamar", "signing", "k.key"))
    # --approve-keygen on a browser that cannot make keys: the same commands, nothing written
    code, d = run(w, "--approve-keygen", env=env)
    assert code == 2 and d["key_commands"], d
    assert steps() == ["validate", "keygen"]
    # the key the user made: full flow in order
    os.makedirs(os.path.join(cfg, "iamar", "signing"))
    open(os.path.join(cfg, "iamar", "signing", "k.key"), "w").write("x")
    if os.name != "nt":
        os.chmod(os.path.join(cfg, "iamar", "signing", "k.key"), 0o644)
        code, d = run(w, "--dry-run", env=env)
        assert d.get("key_warning") and "chmod 600" in d["key_warning"]["fix"], d   # readable by others: warned
        steps()
        os.chmod(os.path.join(cfg, "iamar", "signing", "k.key"), 0o600)
    code, d = run(w, env=env)
    assert code == 0 and d["ok"] and d["version"] == "0.1.0", d
    assert steps() == ["validate", "package", "verify", "add-to-browser"]
    # unchanged: no bump, the existing package is reused (package is never asked to overwrite)
    code, d = run(w, env=env)
    assert code == 0 and d["version"] == "0.1.0", d
    assert steps() == ["validate", "verify", "add-to-browser"]
    # an edit after signing: validate runs on an unsigned copy, version bumps, new package
    open(os.path.join(w, "scene.json"), "w").write('{"x-edit": 1}')
    code, d = run(w, env=env)
    assert code == 0 and d["version"] == "0.1.1", d
    assert json.load(open(os.path.join(w, "manifest.json")))["version"] == "0.1.1"
    assert steps() == ["validate", "package", "verify", "add-to-browser"]
    # validate failure stops everything
    open(os.path.join(w, "scene.json"), "w").write('{"x-edit": 2}')
    code, d = run(w, env=dict(env, STUB_FAIL="validate"))
    assert code == 1 and steps() == ["validate"], d
    # dry run changes nothing
    before = open(os.path.join(w, "manifest.json")).read()
    r = subprocess.run([sys.executable, "-I", PUB, w, "--key", "k", "--dry-run"], capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "DRY RUN" in r.stdout, r.stdout
    assert open(os.path.join(w, "manifest.json")).read() == before

if WIN:
    # every argument reaches iamar-world.cmd unchanged and nothing in it runs as a command
    # (["cmd", "/c", kit.cmd] + args failed under "C:\Users\John Doe" and ran "D" for "R&D")
    ECHO = "@echo off\r\nsetlocal DisableDelayedExpansion\r\n:next\r\nif [%1]==[] goto :eof\r\n" \
           ">>\"%STUB_LOG%\" echo(%1\r\nshift\r\ngoto next\r\n"
    ARGS = ["package", "C:/my world/w", "C:/out dir/x.iamar", "my key", "Maya Lee", "World builder", "R&D",
            "a|b", "x>y", "x<y", "100%", "%PATH%", "caret^", "bang!", "--to=C:/inst dir", "--to=C:/x",
            "semi;colon", "a,b", "C:\\plain\\path", "C:\\dir with space\\", "x&echo PWNED>canary.txt", "beach_house"]
    spec = importlib.util.spec_from_file_location("publish", PUB)
    pub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pub)
    with tempfile.TemporaryDirectory(prefix="iamar publish ") as t:
        kit = os.path.join(t, "kit dir")
        os.makedirs(kit)
        stub, log = os.path.join(kit, "iamar-world.cmd"), os.path.join(t, "args.log")
        open(stub, "w", newline="").write(ECHO)
        os.environ.update(IAMAR_WORLD_LAUNCHER=stub, STUB_LOG=log)

        def received():
            lines = open(log, encoding="mbcs").read().splitlines() if os.path.exists(log) else []
            os.path.exists(log) and os.remove(log)
            return [l[1:-1] if len(l) >= 2 and l[0] == l[-1] == '"' else l for l in lines]

        r = subprocess.run(pub.command(ARGS), capture_output=True, text=True, cwd=t)
        assert r.returncode == 0 and not r.stderr.strip(), (r.returncode, r.stderr)
        got = received()
        assert got == ARGS, (ARGS, got)
        assert not [f for _, _, fs in os.walk(t) for f in fs if f == "canary.txt"], "& ran a command"
        for bad in ('say "hi"', "two\nlines"):
            try:
                pub.cmd_line(stub, ["validate", bad])
                raise AssertionError("no ValueError for %r" % bad)
            except ValueError:
                pass
        steps_run = pub.Run(True, False)
        assert steps_run.step("validate", ["validate", "C:/my world"]) and received() == ["validate", "C:/my world"]
        assert steps_run.step("package", ["package", 'C:/a"b']) is False and steps_run.steps[-1]["exit"] == 2
print("publish_test OK")
