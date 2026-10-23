#!/usr/bin/env python3
"""<world>/.iamar/activity.jsonl: one line per world command (kit/agent_output/agent_output.py, an internal task).

Drives the bash launcher against an inert browser stub (no browser, Godot, network or real world).

  python3 tests/kit_activity/test_activity.py
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "agent_output"))
import agent_output as ao  # noqa: E402

GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = GIT_BASH if os.name == "nt" and os.path.isfile(GIT_BASH) else shutil.which("bash")
KEYS = ["time", "command", "args", "ok", "exit_code", "errors", "warnings", "next", "human_step"]


def lines(world):
    return [json.loads(x) for x in (world / ".iamar" / "activity.jsonl").read_text(encoding="utf-8").splitlines()]


class LogActivity(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="iamar activity "))
        (self.tmp / "w").mkdir()
        os.environ.pop("IAMAR_KIT_NO_ACTIVITY", None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_line_has_the_documented_keys(self):
        path = ao.log_activity("validate", 0, ["w", "--tier", "low"], cwd=str(self.tmp))
        self.assertTrue(path)
        (row,) = lines(self.tmp / "w")
        self.assertEqual(list(row), KEYS)
        self.assertTrue(row["ok"])
        self.assertEqual(row["args"], ["w", "--tier", "low"])
        self.assertIn("iamar-world preview", row["next"])
        self.assertIsNone(row["errors"])

    def test_json_run_records_errors_and_warnings(self):
        res = ao.parse("validate", 1, ["w"], "ERROR scene.json: bad\nWARN odd thing\nFAILED\n")
        ao.log_activity("validate", 1, ["w"], res, cwd=str(self.tmp))
        (row,) = lines(self.tmp / "w")
        self.assertFalse(row["ok"])
        self.assertEqual(row["errors"][0]["message"], "scene.json: bad")
        self.assertEqual(len(row["warnings"]), 1)

    def test_appends_and_skips_non_world_runs(self):
        ao.log_activity("validate", 0, ["w"], cwd=str(self.tmp))
        ao.log_activity("package", 0, ["w", "out/w.iamar"], cwd=str(self.tmp))
        self.assertEqual([r["command"] for r in lines(self.tmp / "w")], ["validate", "package"])
        self.assertIsNone(ao.log_activity("doctor", 0, ["w"], cwd=str(self.tmp)))
        self.assertIsNone(ao.log_activity("validate", 0, ["missing"], cwd=str(self.tmp)))
        self.assertIsNone(ao.log_activity("validate", 0, [], cwd=str(self.tmp)))

    def test_off_switch_and_cap(self):
        os.environ["IAMAR_KIT_NO_ACTIVITY"] = "1"
        try:
            self.assertIsNone(ao.log_activity("validate", 0, ["w"], cwd=str(self.tmp)))
        finally:
            del os.environ["IAMAR_KIT_NO_ACTIVITY"]
        log = self.tmp / "w" / ".iamar" / "activity.jsonl"
        log.parent.mkdir()
        log.write_text(("x" * 99 + "\n") * 4000, encoding="utf-8")
        ao.log_activity("validate", 0, ["w"], cwd=str(self.tmp))
        self.assertLess(log.stat().st_size, ao.ACTIVITY_MAX_BYTES)
        self.assertEqual(json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["command"], "validate")


@unittest.skipUnless(BASH and not (os.name == "nt" and BASH != GIT_BASH), "needs bash (Git Bash on Windows)")
class Launcher(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="iamar activity "))
        kit = self.tmp / "kit"
        kit.mkdir()
        shutil.copy2(ROOT / "kit/iamar-world", kit / "iamar-world")
        shutil.copytree(ROOT / "kit/agent_output", kit / "agent_output")
        (self.tmp / "w").mkdir()
        stub = self.tmp / "stub"
        stub.write_text('#!/usr/bin/env bash\n[[ "${*: -2}" == "--kit where" ]] && exit 0\n'
                        'echo "ERROR scene.json: broken"; echo FAILED; exit 1\n', newline="\n")
        stub.chmod(0o755)
        self.env = dict(os.environ, IAMAR_BROWSER=self.bp(stub), PYTHON=self.bp(pathlib.Path(sys.executable)))
        for k in ("IAMAR_KIT_OUTPUT_CHILD", "IAMAR_KIT_NO_NEXT", "IAMAR_KIT_NO_ACTIVITY", "IAMAR_PROJECT"):
            self.env.pop(k, None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def bp(p):
        if os.name != "nt":
            return str(p)
        return subprocess.run([BASH, "-c", 'cygpath -u "$1"', "_", str(p)], capture_output=True, text=True).stdout.strip()

    def run_kit(self, *args, **env):
        return subprocess.run([BASH, self.bp(self.tmp / "kit/iamar-world"), *args], cwd=self.tmp,
                              env=dict(self.env, **env), capture_output=True, text=True, timeout=60)

    def test_human_and_json_runs_each_append_one_line(self):
        self.assertEqual(self.run_kit("validate", "w").returncode, 1)
        (row,) = lines(self.tmp / "w")
        self.assertEqual((row["command"], row["ok"], row["exit_code"], row["errors"]), ("validate", False, 1, None))
        self.assertEqual(self.run_kit("validate", "w", "--json").returncode, 1)
        row = lines(self.tmp / "w")[-1]
        self.assertEqual(len(lines(self.tmp / "w")), 2)
        self.assertEqual(row["errors"][0]["message"], "scene.json: broken")

    def test_no_next_still_logs_and_off_switch_does_not(self):
        self.run_kit("validate", "w", IAMAR_KIT_NO_NEXT="1")
        self.assertEqual(len(lines(self.tmp / "w")), 1)
        self.run_kit("validate", "w", IAMAR_KIT_NO_ACTIVITY="1")
        self.assertEqual(len(lines(self.tmp / "w")), 1)


if __name__ == "__main__":
    unittest.main()
