#!/usr/bin/env python3
"""iamar-world publish-local: one step from a reviewed world folder to a package the browser can host.

  iamar-world publish-local <world> --key <name|path.key> [--signer "<Name>"] [--out <dir>]
                      [--approve-keygen] [--no-bump] [--install-to <dir>] [--dry-run] [--json]

Runs, in order: validate, (keygen only with --approve-keygen), version bump when the folder changed
since the last publish, package (tiers, sign, pieces), verify, add-to-browser. It stops at the first
failure and says which step failed. It never creates a signing key unless --approve-keygen is given,
never registers or starts hosting: Start Hosting stays the owner's own choice in the browser.

Exit 0 published, 1 a step failed, 2 the user must act first (missing key, bad arguments).
Pure standard library.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signing_key import key_path, privacy, provision_commands  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
WIN = os.name == "nt"
HOME = os.path.expanduser("~")
# Written by package/sign or rebuilt by tiers: not part of the creator's edits.
GENERATED = {"signature.json", "tiers"}

HOST_STEPS = [
    "Open iamar and sign in (your account owns the address).",
    "Press Esc, choose Host My World, and pick this world with the World button.",
    "Choose who may visit: Everyone, My buddies, or Only me (for testing).",
    "Press Start Hosting, then Copy link to share iamar://<13 characters>.",
]


def launcher():
    env = os.environ.get("IAMAR_WORLD_LAUNCHER")
    if env:
        return env
    return os.path.join(KIT, "iamar-world.cmd" if WIN else "iamar-world")


# An argument cmd.exe reads the same quoted or not (no space, = , ; or cmd syntax); anything else is quoted.
CMD_SAFE = re.compile(r"[A-Za-z0-9_./:+@\\-]+")


def cmd_line(script, args):
    """One cmd.exe command line that runs a .cmd/.bat with exactly these arguments.

    subprocess's list quoting is for C programs, not cmd: with ["cmd", "/c", script, ...] cmd strips
    the line's first and last quote once any argument is quoted (a kit under "C:\\Users\\John Doe"
    then fails), and & | < > in an unquoted name run as commands. Here every argument that is not
    plainly safe is quoted (& | < > ^ are literal inside quotes), % is neutralised (%cd:~,% expands to
    nothing, so "100%" stays "100%" and "%PATH%" is not expanded), /v:off keeps ! literal and /s
    keeps the inner quotes. A double quote or a line break cannot be passed safely: ValueError."""
    parts = []
    for a in [script] + list(args):
        if any(c in a for c in '"\r\n\0'):
            raise ValueError("argument %r contains a double quote or a line break; rename it" % a)
        parts.append(a if CMD_SAFE.fullmatch(a) else '"%s"' % a.replace("%", "%%cd:~,%"))
    cmd = os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "cmd.exe")
    return '"%s" /d /v:off /s /c "%s"' % (cmd, " ".join(parts))


def command(args):
    """What subprocess runs for `iamar-world <args>`: a cmd.exe line for a Windows .cmd launcher."""
    script = launcher()
    if WIN and script.lower().endswith((".cmd", ".bat")):
        return cmd_line(script, args)
    return [script] + list(args)


def folder_hash(world):
    h = hashlib.sha256()
    for root, dirs, files in os.walk(world):
        rel_root = os.path.relpath(root, world)
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (rel_root == "." and d in GENERATED))
        for f in sorted(files):
            if f.startswith(".") or (rel_root == "." and f in GENERATED) or f.endswith(".pieces.json"):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, world).replace(os.sep, "/")
            if rel == "manifest.json":
                # the version field is what we bump; hash the rest of the manifest only
                try:
                    m = json.load(open(p, encoding="utf-8"))
                    m.pop("version", None)
                    m.pop("signer", None)
                    data = json.dumps(m, sort_keys=True).encode()
                except ValueError:
                    data = open(p, "rb").read()
            else:
                data = open(p, "rb").read()
            h.update(rel.encode() + b"\0" + hashlib.sha256(data).digest())
    return h.hexdigest()


def bump_patch(version):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(.*)", version or "")
    if not m:
        return None
    return f"{m.group(1)}.{m.group(2)}.{int(m.group(3)) + 1}"


class Run:
    def __init__(self, as_json, dry):
        self.as_json, self.dry, self.steps = as_json, dry, []

    def say(self, line):
        if not self.as_json:
            print(line, flush=True)

    def step(self, name, args):
        rec = {"step": name, "command": " ".join(["iamar-world"] + args)}
        self.steps.append(rec)
        try:
            cmd = command(args)
        except ValueError as e:
            rec.update(status="failed", exit=2, output_tail=[f"ERROR {e}"])
            self.say(f"ERROR {name}: {e}")
            return False
        if self.dry:
            rec["status"] = "planned"
            self.say(f"PLAN  {rec['command']}")
            return True
        self.say(f"STEP  {name}: {rec['command']}")
        out = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, IAMAR_KIT_NO_NEXT="1"))
        text = (out.stdout or "") + (out.stderr or "")
        rec["exit"] = out.returncode
        rec["status"] = "ok" if out.returncode == 0 else "failed"
        lines = [l for l in text.splitlines() if l.strip() and not l.startswith(("Godot Engine", "GpuTier"))]
        rec["output_tail"] = lines[-15:]
        if not self.as_json:
            for l in (lines if out.returncode else [l for l in lines if re.match(r"(ERROR|WARN|OK|FAILED|PACKAGED|VERIFIED|INSTALLED|SIGNED|SIGNER|WROTE|KEY)\b", l)]):
                print("      " + l)
        return out.returncode == 0


def main(argv):
    ap = argparse.ArgumentParser(prog="iamar-world publish-local", description=__doc__.split("\n\n")[0])
    ap.add_argument("world")
    ap.add_argument("--key", required=True, help="signing key name (in the iamar signing folder) or a .key path")
    ap.add_argument("--signer", help="signer name shown to visitors (default: manifest author.name)")
    ap.add_argument("--out", help="output folder for the .iamar (default: <world>/../out)")
    ap.add_argument("--approve-keygen", action="store_true", help="the user approved creating this key if it is missing")
    ap.add_argument("--no-bump", action="store_true", help="never change manifest version")
    ap.add_argument("--install-to", help="install into this folder instead of the browser's my_worlds (add-to-browser --to)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    world = os.path.abspath(a.world)
    run = Run(a.json, a.dry_run)
    result = {"world": world, "ok": False, "steps": run.steps}

    def finish(code, **extra):
        result.update(extra)
        if a.json:
            print(json.dumps(result, indent=1))
        return code

    mpath = os.path.join(world, "manifest.json")
    try:
        manifest = json.load(open(mpath, encoding="utf-8"))
    except (OSError, ValueError) as e:
        run.say(f"ERROR {mpath}: {e}")
        return finish(2, error=f"cannot read manifest.json: {e}", next=f"iamar-world new {a.world}")
    wid, version = manifest.get("id", ""), manifest.get("version", "0.1.0")
    signer = a.signer or (manifest.get("author") or {}).get("name") or ""
    if not signer:
        run.say("ERROR no signer name: pass --signer \"<Name>\" or set author.name in manifest.json")
        return finish(2, error="no signer name")
    out_dir = os.path.abspath(a.out or os.path.join(os.path.dirname(world), "out"))
    key = key_path(a.key)
    result.update(id=wid, signer=signer, key=key, version=version)

    # 1. validate the content. A folder packaged before carries signature.json and manifest.signer,
    # which go stale on every edit ("changed since it was signed"); package signs again, so validate
    # an unsigned temporary copy and leave the folder itself untouched.
    target, tmp = world, None
    if os.path.isfile(os.path.join(world, "signature.json")) or "signer" in manifest:
        tmp = tempfile.mkdtemp(prefix="iamar-publish-")
        target = os.path.join(tmp, os.path.basename(world))
        shutil.copytree(world, target, ignore=shutil.ignore_patterns("signature.json", ".*"))
        m2 = dict(manifest)
        m2.pop("signer", None)
        with open(os.path.join(target, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(m2, f, indent=2)
    try:
        ok = run.step("validate", ["validate", target])
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    if not ok:
        return finish(1, error="validate failed: fix every ERROR above", next=f"iamar-world validate {a.world}")

    # 2. the signing key. The user makes it, once, in their own terminal (decision #97): released
    # browsers cannot run keygen yet, and the kit never writes a private key itself.
    def need_key(why):
        cmds = provision_commands(key)
        run.say(f"STOP  {why}")
        run.say("      Ask your user to create their signing key once. It identifies them to visitors and")
        run.say("      stays private on this computer; they run, in their own terminal:")
        for c in cmds:
            run.say("        " + c)
        run.say(f"NEXT: iamar-world publish-local {a.world} --key {a.key}")
        return finish(2, error="signing key missing: the user creates it with the commands shown",
                      key_commands=cmds, next=f"iamar-world publish-local {a.world} --key {a.key}")

    if not os.path.isfile(key):
        if not a.approve_keygen:
            return need_key(f"no signing key at {key}.")
        # a browser with native keygen makes the key itself; released ones cannot yet
        if not run.step("keygen", ["keygen", a.key]):
            tail = " ".join(run.steps[-1].get("output_tail", []))
            if "private-pair" in tail:
                return need_key("this browser cannot create signing keys yet (no native private-pair API).")
            return finish(1, error="keygen failed")
    if os.path.isfile(key):
        private, detail, fix = privacy(key)
        if not private:
            run.say(f"WARN  {detail}: anyone who can read it can sign worlds as your user. Fix: {fix}")
            result["key_warning"] = {"detail": detail, "fix": fix}

    # 3. version: bump the patch when the folder changed since the last publish of this version
    stamp = os.path.join(out_dir, f".{wid}.last-publish.json")
    digest = folder_hash(world)
    last = {}
    try:
        last = json.load(open(stamp, encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if last.get("version") == version and last.get("hash") != digest:
        if a.no_bump:
            run.say(f"WARN  the world changed since {version} was published; --no-bump keeps {version}")
        else:
            new = bump_patch(version)
            if not new:
                run.say(f"ERROR cannot bump version {version!r}: set a semver x.y.z in manifest.json")
                return finish(2, error="unbumpable version")
            run.say(f"BUMP  version {version} -> {new} (the folder changed since {version} was published)")
            if not a.dry_run:
                manifest["version"] = new
                with open(mpath, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)
                    f.write("\n")
                digest = folder_hash(world)
            version = new
    result["version"] = version
    pkg = os.path.join(out_dir, f"{wid}-{version}.iamar")
    result["package"] = pkg
    if not a.dry_run:
        os.makedirs(out_dir, exist_ok=True)

    # 4-6. package, verify, install into the browser's worlds
    unchanged = last.get("version") == version and last.get("hash") == digest and os.path.isfile(pkg)
    if unchanged:
        run.say(f"SAME  nothing changed since {os.path.basename(pkg)}; reusing it")
    elif os.path.exists(pkg):
        run.say(f"ERROR {pkg} exists but does not match this folder: bump version in manifest.json or remove --no-bump")
        return finish(1, error="package for this version already exists with different content")
    elif not run.step("package", ["package", world, pkg, key, signer]):
        return finish(1, error="package failed", next=f"iamar-world validate {a.world}")
    if not run.step("verify", ["verify", pkg]):
        return finish(1, error="verify failed: the package does not match its signature")
    if not run.step("add-to-browser", ["add-to-browser", pkg] + ([f"--to={os.path.abspath(a.install_to)}"] if a.install_to else [])):
        return finish(1, error="add-to-browser failed", next=f"iamar-world add-to-browser {pkg}")

    if not a.dry_run:
        digest = folder_hash(world)  # package rewrites files in the folder; stamp what it left
        with open(stamp, "w", encoding="utf-8") as f:
            json.dump({"version": version, "hash": digest, "package": pkg}, f)
    if a.dry_run:
        run.say(f"DRY RUN: nothing was changed; this would publish {wid} {version} to {pkg}")
        return finish(0, ok=True, dry_run=True)
    run.say(f"PUBLISHED {wid} {version} signed by {signer}: {pkg}")
    run.say("Tell your user (they press these themselves; nothing is hosted yet):")
    for i, s in enumerate(HOST_STEPS, 1):
        run.say(f"  {i}. {s}")
    run.say("NEXT: the user presses Start Hosting; then report the address the panel shows")
    return finish(0, ok=True, host_steps=HOST_STEPS, next="user: Esc > Host My World > Start Hosting")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
