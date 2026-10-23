#!/usr/bin/env python3
"""iamar-world version: report the kit version and whether it is current.

  iamar-world version                 print the version (one line), exit 0
  iamar-world version --json          machine-readable: {kit_version, ...}
  iamar-world version --check         ask the published release whether this kit is current
  iamar-world version --check --latest 0.4.0|<file>|<url>   compare with a given latest instead

Exit codes: 0 current (or plain report), 1 a newer kit exists, 2 the check could not run
(offline, unreadable answer). A failed check never blocks any other kit command.
Pure standard library; the kit version is kit/VERSION.json (released kits also carry KIT_VERSION.json).
"""
import argparse, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def parse(v):
    if not SEMVER.match(str(v)):
        raise ValueError(f"not a N.N.N version: {v!r}")
    return tuple(int(p) for p in v.split("."))


def local():
    for path, key in ((os.path.join(KIT, "VERSION.json"), "kit_version"),
                      (os.path.join(os.path.dirname(KIT), "KIT_VERSION.json"), "kit_version"),
                      (os.path.join(KIT, "KIT_VERSION.json"), "kit_version")):
        if os.path.isfile(path):
            d = json.load(open(path))
            parse(d[key])
            return d
    raise SystemExit("version: no kit/VERSION.json next to this tool")


def fetch_latest(source, default_url):
    if source is None:
        source = os.environ.get("IAMAR_KIT_LATEST") or default_url
    if SEMVER.match(source):
        return source
    if source.startswith("https://"):
        req = urllib.request.Request(source, headers={"User-Agent": "iamar-kit-version"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read(1 << 20))
    elif os.path.isfile(source):
        data = json.load(open(source))
    else:
        raise ValueError(f"latest must be N.N.N, an https URL or a file: {source!r}")
    v = data.get("kit_version") or data.get("version")
    parse(v)
    return v


def main(argv=None):
    ap = argparse.ArgumentParser(prog="iamar-world version")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--latest")
    a = ap.parse_args(argv)
    info = local()
    out = {"kit_version": info["kit_version"]}
    code = 0
    if a.check or a.latest:
        try:
            latest = fetch_latest(a.latest, info.get("latest_url", ""))
            out["latest"] = latest
            out["current"] = parse(info["kit_version"]) >= parse(latest)
            code = 0 if out["current"] else 1
        except Exception as e:  # offline or bad answer: report, do not block
            out["check_error"] = f"{type(e).__name__}: {e}"
            code = 2
    if a.json:
        print(json.dumps(out))
    else:
        line = f"iamar kit {out['kit_version']}"
        if "current" in out:
            line += " (current)" if out["current"] else f" (newer kit {out['latest']} is available)"
        elif "check_error" in out:
            line += f" (could not check for updates: {out['check_error']})"
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
