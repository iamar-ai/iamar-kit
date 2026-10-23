#!/usr/bin/env python3
"""Agent-readable output for the kit commands: --json and the NEXT line (kit/agent_output/README.md).

The native kit commands (new, validate, preview, perf, techniques, package, verify, add-to-browser,
playtest, ...) print tagged text lines (STATS, VIEW, TARGET, WARN, ERROR ...). The launchers
(kit/iamar-world, kit/iamar-world.cmd) use this file in two ways:

  agent_output.py run <command> -- <launcher argv...>   run the command without --json, print ONE
                                                        JSON object (schema below), same exit code
  agent_output.py next <command> <exit code> [args...]  print the "NEXT: <command>" line that ends
                                                        every human-mode run
  agent_output.py activity <command> <exit code> [args...] append one line to <world>/.iamar/activity.jsonl
  agent_output.py parse <command> <exit code> [args...] read the command's output on stdin, print
                                                        the JSON object (tests, saved logs)

JSON object, schema "iamar-kit-output/1" (keys are stable; tests/kit_agent_output pins them):
  schema, command, args, exit_code, ok      ok is exit_code == 0
  errors   [{message, fix}]                 ERROR lines, failed TARGETs, stderr of a failed run
  warnings [{message, fix}]                 WARN lines; every entry has a fix hint
  notes    [text]                           NOTE lines
  next     {command, why, human_step}       the next command on the happy path (or the rerun after
                                            a fix); human_step names what only the user can do
  data     {...}                            what the command measured, by command (README.md)
  records  [{tag, text}]                    every tagged stdout line, in order
  other    [text]                           untagged lines (stdout, then stderr)
Activity log (an internal task): every run of a world command (new, validate, preview, perf, package, sign,
verify, playtest, play, ...) appends one JSON line to <world folder>/.iamar/activity.jsonl:
  {time, command, args, ok, exit_code, errors, warnings, next, human_step}
errors/warnings are lists in --json runs and null in human runs (the output went to the terminal).
The browser's Studio reads it. validate and package read only what scene.json/manifest.json list, so
.iamar/ is never validated or packed. IAMAR_KIT_NO_ACTIVITY=1 turns it off; the log is capped.
Pure standard library.
"""
import json
import os
import re
import subprocess
import sys
import time

SCHEMA = "iamar-kit-output/1"
TAG = re.compile(r"^([A-Z][A-Z0-9_]{1,})(?::|\b) ?(.*)$")
# options that take a value, so they are not mistaken for positional arguments
VALUE_OPTS = {"--id", "--title", "--author", "--template", "--view", "--npcs", "--tier", "--frames",
              "--size", "--quest-done", "--as", "--width", "--depth", "--floors", "--style", "--roof",
              "--rooms", "--out", "--steps", "--mode", "--package", "--cwd", "--limit", "--category",
              "--from-brief", "--port"}
# the sentence of a message that tells what to do starts with one of these
IMPERATIVE = re.compile(r"(?:^|(?<=[.:;] ))(Set|Use|Move|Put|Add|Remove|Rerun|Run|Fix|Lower|Raise|Give|Pick|"
                        r"Model|Download|Install|Re-sign|Resign|Keep|Shorten|Rename|Make|Replace|Delete|"
                        r"Declare|Drop|Split|Merge|Turn|Try|Retry|Update|Check|Place|Scale|Mark|List|Ask)\b")
# messages with no fix sentence of their own: (pattern, fix)
FIX_TABLE = [
    (r"pack needs your key and name|needs your key", "Your user creates their signing key once in their own terminal: "
     "`iamar-world doctor` prints the commands (decision #97); then rerun with the key path and \"<Your Name>\"."),
    (r"no manifest\.json|no readable manifest\.json", "Point the command at a world folder, or create "
     "one with `iamar-world new <folder>`."),
    (r"cannot read (private )?key|cannot read selected signing key", "Check the key path (keygen prints it "
     "on its KEY line); create a key with `iamar-world keygen <name>` after your user approves."),
    (r"no object .* in the library", "Search for it with `iamar-world assets search <words>` and use an id it prints."),
    (r"unknown template", "Use one of the templates the message lists, e.g. --template beach."),
    (r"no world geometry", "Update the browser (`iamar-world doctor` shows how), then rerun preview."),
    (r"did not answer a kit command|TIMED OUT", "Retry with IAMAR_KIT_PROBE_TENTHS=3000 set."),
    (r"too old|cannot run the developer kit", "Download the latest iamar browser (https://iamar.ai/download) "
     "or set IAMAR_BROWSER; `iamar-world doctor` checks it."),
    (r"iamar-kit\.pck|kit not installed|developer kit and this browser do not match",
     "Run `iamar-world doctor`: it names the kit download and where iamar-kit.pck goes."),
    (r"must end in lowercase \.iamar", "Name the output file <name>.iamar."),
    (r"signing key outside the world folder|contains the selected signing key",
     "Move the key out of the world folder (keys live in ~/.config/iamar/signing)."),
    (r"is not writable|cannot open .* for writing|refusing to write", "Make the folder writable, or copy the "
     "world to a folder you own, then rerun."),
    (r"script preview failed|trapped|stopped", "Fix the world script error shown, then rerun "
     "(docs/WORLD_API.md lists the fuel and time budgets)."),
    (r"does not open|FAILED|refused|invalid|not in the package", "Fix this entry in the world folder "
     "(docs/WORLD_FORMAT.md describes every field), then rerun validate."),
    (r"^usage:|needs a|must be|Unknown option|missing its value|Provide a", "Rerun with the arguments the usage line shows."),
]
GENERIC_FIX = "Search kit/AGENT_KIT.md and docs/WORLD_FORMAT.md for the first words of this message, fix it, then rerun."


def fix_for(message):
    """The fix hint for an ERROR/WARN message: its own advice when it has some, else the table."""
    m = message.strip()
    if " -> recipes: " in m:              # TARGET ... FAIL ... -> recipes: lod_chain, ...
        return "Apply the recipes " + m.split(" -> recipes: ", 1)[1].strip() + " (kit/AGENT_KIT.md names each recipe)"
    if " -> a script" in m:               # TARGET world_scripts_ok FAIL ... -> a script trapped ...: stay inside ...
        return m.split(" -> ", 1)[1].strip()
    hit = IMPERATIVE.search(m)
    if hit:
        return m[hit.start():].strip()
    for pattern, fix in FIX_TABLE:
        if re.search(pattern, m, re.I):
            return fix
    return GENERIC_FIX


def _num(text):
    try:
        f = float(text)
    except (TypeError, ValueError):
        return text
    return int(f) if f.is_integer() and "." not in str(text) else f


def positionals(args):
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a in VALUE_OPTS:
            i += 2
            continue
        if not a.startswith("--") and a != "":
            out.append(a)
        i += 1
    return out


def q(path):
    """Quote an argument for a suggested command line (sh and cmd both accept double quotes)."""
    return '"%s"' % path if (not path or re.search(r"[\s&|<>^()'\"]", path)) else path


def _stem(folder):
    return os.path.basename(os.path.normpath(folder)) or "world"


def _step(cmd, why, human=None):
    return {"command": cmd, "why": why, "human_step": human, "after_failure": False}


def next_step(command, exit_code, args, data=None):
    """{command, why, human_step, after_failure} for the next step, or None when there is none."""
    data = data or {}
    if command in ("help", "doctor", "serve", "host", "publish", "blender", "blender-run", "version"):
        return None
    if exit_code != 0:
        rerun = "iamar-world %s %s" % (command, " ".join(q(a) for a in args)) if args else "iamar-world " + command
        if command == "playtest":
            failed = _step(rerun, "fix the failed steps (the STEP/EXPECT lines and playtest.json), then rerun the playtest")
        elif command in ("preview", "perf") and data.get("targets_result", "").startswith("FAIL"):
            failed = _step(rerun, "apply the recipes named on the FAIL lines, then measure again")
        else:
            failed = _step(rerun, "fix the ERROR lines above, then rerun")
        failed["after_failure"] = True
        return failed
    return _success_step(command, args, data)


def _success_step(command, args, data):
    step = _step
    pos = positionals(args)
    a1 = pos[0] if pos else "<world folder>"
    shots = q("shots/%s/view" % _stem(a1))
    world = a1
    if command == "new":
        return step("iamar-world validate %s" % q(world), "edit scene.json, then check it")
    if command == "validate":
        if a1.endswith(".json"):
            return step("iamar-world preview %s %s" % (q(a1), q("shots/" + _stem(a1).split(".")[0])), "look at the page")
        return step("iamar-world preview %s %s" % (q(world), shots), "render the views, then LOOK AT the screenshots")
    if command in ("preview", "perf"):
        if len(pos) < 2:                  # no output prefix: preview/perf ran the validate checks only
            return step("iamar-world preview %s %s" % (q(world), shots), "render the views, then LOOK AT the screenshots")
        if command == "preview":
            return step("iamar-world perf %s %s" % (q(world), q(pos[1])), "LOOK AT the screenshots, then check the hard targets")
        return step("iamar-world playtest %s" % q(world), "walk the world as a visitor; then the review gate (kit/review/REVIEWER.md)")
    if command == "playtest":
        return step("iamar-world package %s out/%s.iamar <key> \"<Your Name>\"" % (q(world), _stem(world)),
                    "after the independent review gate passes", "approve the signing key (and its name) before packaging")
    if command == "techniques":
        return step("iamar-world validate %s" % q(world), "check the world again after any change the ADVICE lines suggest")
    if command in ("tiers", "impostors"):
        return step("iamar-world validate %s" % q(world), "check every tier still opens and fits")
    if command == "keygen":
        key = data.get("key") or (pos[0] if pos else "<key>")
        return step("iamar-world sign <world folder> %s \"<Your Name>\"" % q(key), "sign the world with the new key")
    if command == "sign":
        key = pos[1] if len(pos) > 1 else "<key>"
        name = pos[2] if len(pos) > 2 else "<Your Name>"
        return step("iamar-world package %s out/%s.iamar %s %s" % (q(world), _stem(world), q(key), q(name)), "pack the signed world")
    if command in ("package", "pack"):
        out = (data.get("packed") or {}).get("path") or (pos[1] if len(pos) > 1 else "<out.iamar>")
        return step("iamar-world verify %s" % q(out), "check the package opens signed")
    if command == "verify":
        return step("iamar-world add-to-browser %s" % q(a1), "install it in the iamar browser")
    if command == "add-to-browser":
        return step("(none: hosting is the user's step)", "the world is installed",
                    data.get("human_step") or "in iamar: Esc menu -> Host My World -> pick the world -> Start Hosting")
    if command == "where":
        return step("iamar-world new worlds/my_world --id my_world --title \"My World\" --author \"<user's name>\"",
                    "start a world (after the user approved the brief)")
    if command == "assets":
        sub = args[0] if args else ""
        if sub in ("search", "list"):
            return step("iamar-world assets use <world folder> <id> --as assets/<name>.glb", "reuse an object it listed")
        if sub == "show":
            return step("iamar-world assets use <world folder> %s --as assets/<name>.glb" % q(pos[1] if len(pos) > 1 else "<id>"),
                        "reuse it in your world")
        if sub == "use":
            return step("iamar-world validate %s" % q(pos[1] if len(pos) > 1 else "<world folder>"),
                        "place it in scene.json objects, then check the world")
        if sub == "building":
            return step("iamar-world validate <world folder>", "place the .glb in scene.json objects, then check the world")
        return None
    return None


def next_line(step):
    if step is None:
        return ""
    line = "NEXT: " + step["command"]
    if step.get("after_failure"):
        line += "   (%s)" % step["why"]
    if step.get("human_step"):
        line += "   (your user: %s)" % step["human_step"]
    return line


def _views(text):
    m = re.match(r"(\d+) (\S+) draw=(\d+) prims=(\d+)(?: objects=(\d+))? fps=(.+?)(?: -> (.*))?$", text)
    if not m:
        return None
    fps = m.group(6)
    return {"index": int(m.group(1)), "name": m.group(2), "draw_calls": int(m.group(3)), "primitives": int(m.group(4)),
            "objects": int(m.group(5)) if m.group(5) else None,
            "fps": None if fps == "not measured" else _num(fps), "file": m.group(7)}


def _target(text):
    m = re.match(r"(\S+)\s+(PASS|FAIL|INFO|NOT MEASURED)\s*(.*)$", text)
    if not m:
        return None
    rest = m.group(3)
    t = {"name": m.group(1), "status": m.group(2).replace(" ", "_"), "value": None, "limit": None, "recipes": None, "text": rest}
    v = re.match(r"(\S+) \(limit ([^)]+)\)(?:\s+-> recipes: (.*))?", rest)
    if v and t["status"] in ("PASS", "FAIL"):
        t["value"], t["limit"] = _num(v.group(1)), _num(v.group(2))
        t["recipes"] = [r.strip() for r in v.group(3).split(",")] if v.group(3) else None
    return t


def parse(command, exit_code, args, stdout, stderr=""):
    rec, other, errors, warnings, notes = [], [], [], [], []
    data = {}
    for raw in stdout.splitlines():
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        m = TAG.match(line)
        if not m:
            if line.startswith("{") and "report" not in data:   # validate --report-v1: its JSON report
                try:
                    data["report"] = json.loads(line)
                    continue
                except ValueError:
                    pass
            other.append(line)
            continue
        tag, text = m.group(1), m.group(2).strip()
        rec.append({"tag": tag, "text": text})
        if tag in ("OK", "FAILED") and not text:
            data["result"] = tag
        if tag == "ERROR":
            errors.append({"message": text, "fix": fix_for(text)})
        elif tag == "WARN":
            warnings.append({"message": text, "fix": fix_for(text)})
        elif tag == "NOTE":
            notes.append(text)
        elif tag == "STATS":
            s = re.match(r"(\S+)\s+(\d+) / (\S+)", text)
            if s:
                data.setdefault("stats", {})[s.group(1)] = {"used": int(s.group(2)), "budget": _num(s.group(3)) if s.group(3) != "-" else None}
        elif tag == "VIEW":
            v = _views(text)
            if v:
                data.setdefault("views", []).append(v)
        elif tag == "TARGET":
            t = _target(text)
            if t:
                data.setdefault("targets", []).append(t)
                if t["status"] == "FAIL":
                    msg = "target %s FAIL: %s" % (t["name"], t["text"])
                    errors.append({"message": msg, "fix": fix_for(msg)})
        elif tag == "TARGETS":
            data["targets_result"] = text
        elif tag == "TIER":
            t = re.match(r"(\S+)\s+(OK|FAILED) triangles=(\d+) texture_size=(\d+) texture_bytes=(\d+)\s*(.*)", text)
            if t:
                data.setdefault("tiers", []).append({"tier": t.group(1), "ok": t.group(2) == "OK", "triangles": int(t.group(3)),
                                                     "texture_size": int(t.group(4)), "texture_bytes": int(t.group(5)), "errors": t.group(6) or None})
        elif tag == "WORLD":
            w = re.match(r'(\S+) "(.*)" (\S+) by (.*)', text)
            if w:
                data["world"] = {"id": w.group(1), "title": w.group(2), "version": w.group(3), "author": w.group(4)}
        elif tag == "NPCS":
            n = re.match(r"(\d+)\s+QUESTS (\d+)\s+SPAWN (.*)", text)
            if n:
                data.update({"npcs": int(n.group(1)), "quests": int(n.group(2)), "spawn": n.group(3)})
        elif tag == "REUSE":
            r = re.match(r"new (\d+) bytes .*reused (\d+) bytes .* in (\d+) objects", text)
            if r:
                data["reuse"] = {"new_bytes": int(r.group(1)), "reused_bytes": int(r.group(2)), "objects": int(r.group(3))}
        elif tag in ("OPEN_MS", "BUILD_MS"):
            data.setdefault("timings_ms", {})[tag[:-3].lower()] = _num(text)
        elif tag == "PREVIEW_MS":
            t = re.match(r"total=(\d+)", text)
            if t:
                data.setdefault("timings_ms", {})["preview"] = int(t.group(1))
        elif tag == "NEW":
            n = re.match(r"(\S+) \((.*)\) in (.*?) - next:", text)
            if n:
                data["new"] = {"id": n.group(1), "title": n.group(2), "folder": n.group(3)}
        elif tag == "TECHNIQUE":
            t = re.match(r"(\S+) (\d+) (.*)", text)
            if t:
                data.setdefault("techniques", {})[t.group(1)] = {"count": int(t.group(2)), "text": t.group(3)}
        elif tag == "ADVICE":
            data.setdefault("advice", []).append(text)
        elif tag == "OFF":
            data.setdefault("off", []).append(text)
        elif tag == "PACKED":
            p = re.match(r"(.*) \((\d+) bytes, (\d+) pieces, sha256 (\w+)\)", text)
            if p:
                data["packed"] = {"path": p.group(1), "bytes": int(p.group(2)), "pieces": int(p.group(3)), "sha256": p.group(4)}
        elif tag == "PIECES":
            p = re.match(r"(.*) \((signed|unsigned)\)", text)
            if p:
                data["pieces"] = {"path": p.group(1), "signed": p.group(2) == "signed"}
        elif tag == "SIGNED":
            s = re.match(r"(.*): (\d+) files, key (\S+), signer (.*)", text)
            if s:
                data["signed"] = {"folder": s.group(1), "files": int(s.group(2)), "key_id": s.group(3), "signer": s.group(4)}
        elif tag == "PLAYTEST":
            p = re.match(r"(PASS|FAIL): (\d+) step\(s\), (\d+) failed(?: -> (.*))?", text)
            if p:
                data["playtest"] = {"result": p.group(1), "steps": int(p.group(2)), "failed": int(p.group(3)), "report": p.group(4)}
        elif tag == "ADDED":
            data["added"] = text
        elif tag == "COUNT":
            data["count"] = _num(text)
        elif tag in ("PACKAGE", "SIGNER", "STATUS", "KEY", "PUBLIC", "KEY_ID", "KIT", "PACK", "DOCS", "AGENT_KIT",
                     "BROWSER", "TEMPLATE", "USED", "QUESTS", "SCRIPTS", "WORST", "MAXDRAWS", "QUICK", "THUMBNAIL", "SIZE"):
            data[tag.lower()] = text
    if command == "add-to-browser":
        for line in other:
            if line.startswith("Now in iamar"):
                data["human_step"] = line[len("Now in iamar:"):].strip() if ":" in line else line
    stderr_other = []
    for raw in stderr.splitlines():
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        m = TAG.match(line)
        if m and m.group(1) == "ERROR":
            text = m.group(2).strip()
            if not any(e["message"] == text for e in errors):
                errors.append({"message": text, "fix": fix_for(text)})
        elif m and m.group(1) == "WARN":
            warnings.append({"message": m.group(2).strip(), "fix": fix_for(m.group(2))})
        else:
            stderr_other.append(line)
    if exit_code != 0 and not errors:
        # a usage or setup failure printed on stderr: its first line is the error, the rest its detail
        msg = " ".join(s.strip() for s in stderr_other[:4]) or "%s failed with exit code %d" % (command, exit_code)
        errors.append({"message": msg, "fix": fix_for(msg)})
    nxt = next_step(command, exit_code, args, data)
    return {"schema": SCHEMA, "command": command, "args": list(args), "exit_code": exit_code, "ok": exit_code == 0,
            "errors": errors, "warnings": warnings, "notes": notes, "next": nxt, "data": data,
            "records": rec, "other": other + stderr_other}


ACTIVITY_MAX_BYTES = 256 * 1024
# commands that work on a world folder (their first positional argument)
ACTIVITY_COMMANDS = {"new", "validate", "preview", "perf", "techniques", "tiers", "impostors", "package", "pack",
                     "sign", "verify", "add-to-browser", "playtest", "play", "lint", "audit", "shots"}


def log_activity(command, exit_code, args, result=None, cwd=None):
    """Append one line to <world>/.iamar/activity.jsonl. Best effort: never raises, never fails the command."""
    if os.environ.get("IAMAR_KIT_NO_ACTIVITY") or command not in ACTIVITY_COMMANDS:
        return None
    try:
        pos = positionals(args)
        if not pos:
            return None
        folder = os.path.join(cwd or os.getcwd(), pos[0])
        if not os.path.isdir(folder):
            return None
        nxt = (result or {}).get("next") or next_step(command, exit_code, args)
        line = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "command": command, "args": list(args),
                "ok": exit_code == 0, "exit_code": exit_code,
                "errors": result["errors"] if result else None, "warnings": result["warnings"] if result else None,
                "next": nxt["command"] if nxt else None, "human_step": nxt.get("human_step") if nxt else None}
        d = os.path.join(folder, ".iamar")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "activity.jsonl")
        if os.path.isfile(path) and os.path.getsize(path) > ACTIVITY_MAX_BYTES:
            with open(path, encoding="utf-8", errors="replace") as f:
                keep = f.read().splitlines()[-200:]
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(keep) + "\n")
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return path
    except (OSError, ValueError):
        return None


def _strip_json(argv):
    return [a for a in argv if a != "--json"]


def main(argv):
    if len(argv) < 2 or argv[0] not in ("run", "next", "parse", "activity"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    mode, command = argv[0], argv[1]
    if mode == "next":
        try:
            code = int(argv[2])
        except (IndexError, ValueError):
            return 2
        line = next_line(next_step(command, code, argv[3:]))
        if line:
            print(line)
        return 0
    if mode == "activity":
        try:
            code = int(argv[2])
        except (IndexError, ValueError):
            return 2
        log_activity(command, code, argv[3:])
        return 0
    if mode == "parse":
        try:
            code = int(argv[2])
        except (IndexError, ValueError):
            return 2
        text = sys.stdin.read()
        print(json.dumps(parse(command, code, _strip_json(argv[3:]), text), indent=1))
        return 0
    # run <command> -- <launcher argv...>: the launcher argv is the launcher (or interpreter + launcher),
    # the command and its arguments; --json is removed and the child neither wraps nor prints NEXT.
    if len(argv) < 4 or argv[2] != "--":
        print("usage: agent_output.py run <command> -- <launcher argv...>", file=sys.stderr)
        return 2
    child = _strip_json(argv[3:])
    try:
        ci = child.index(command)
        args = child[ci + 1:]
    except ValueError:
        args = []
    env = dict(os.environ, IAMAR_KIT_OUTPUT_CHILD="1")
    try:
        p = subprocess.run(child, capture_output=True, env=env)
        out, err, code = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace"), p.returncode
    except OSError as e:
        out, err, code = "", "ERROR could not start %s: %s" % (child[0] if child else "?", e), 2
    result = parse(command, code, args, out, err)
    log_activity(command, code, args, result)
    print(json.dumps(result, indent=1))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
