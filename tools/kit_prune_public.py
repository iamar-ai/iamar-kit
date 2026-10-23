#!/usr/bin/env python3
"""Apply the public export rules to an assembled kit/ folder (tools/kit_bundle.sh runs this).

  kit_prune_public.py <kit_dir> <rules.json>

The kit zip and the public page are built from kit/, not through tools/export_public.py, so the
same rules are applied here: a file under kit/ that rules.json excludes is deleted, a file that
include does not list is deleted, and a leak-scan finding (secret, private host, email ...) that
allow_findings does not cover fails the build. Fails closed: unreadable rules, a symlink, or
any finding exits non-zero and the caller removes the output.
"""
import importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_exporter():
    spec = importlib.util.spec_from_file_location("export_public", os.path.join(HERE, "export_public.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv):
    if len(argv) != 3:
        sys.exit("usage: kit_prune_public.py <kit_dir> <rules.json>")
    kit, rules_path = os.path.abspath(argv[1]), os.path.abspath(argv[2])
    ep = load_exporter()
    rules = ep.load_rules(os.path.dirname(rules_path), rules_path)
    removed, findings = [], []
    for dirpath, dirnames, filenames in os.walk(kit):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                sys.exit(f"kit_prune_public: refusing symlink {full}")
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = "kit/" + os.path.relpath(full, kit).replace(os.sep, "/")
            if ep.first_match(rel, rules["exclude"]) or not ep.first_match(rel, rules["include"]):
                os.remove(full)
                removed.append(rel)
    for dirpath, _dirs, _files in os.walk(kit, topdown=False):
        if dirpath != kit and not os.listdir(dirpath):
            os.rmdir(dirpath)
    for dirpath, _dirs, filenames in os.walk(kit):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = "kit/" + os.path.relpath(full, kit).replace(os.sep, "/")
            with open(full, "rb") as f:
                data = f.read()
            data, n = ep.rewrite(rel, data, rules)  # private names -> neutral ones, as the exporter does
            if n:
                with open(full, "wb") as f:
                    f.write(data)
            for rid, cat, line, shown in ep.scan(rel, data, rules):
                findings.append(f"{rel}:{line}: {cat}/{rid}: {shown}")
    print(f"kit_prune_public: removed {len(removed)} excluded files", file=sys.stderr)
    if findings:
        for f_ in findings:
            print("FAIL leak " + f_, file=sys.stderr)
        sys.exit(f"kit_prune_public: {len(findings)} leak finding(s); nothing may ship")


main(sys.argv)
