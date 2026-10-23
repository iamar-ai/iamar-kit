#!/usr/bin/env python3
"""--json and the NEXT line of the kit commands (kit/agent_output/agent_output.py, an internal task).

Pins the JSON schema keys, the fix hint on every ERROR/WARN, the happy-path NEXT chain, and the
launcher wiring. The bash launcher is driven end to end against an inert browser stub (a bash
script that prints canned kit output); no browser, Godot, network or world is used.

  python3 tests/kit_agent_output/test_agent_output.py
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "agent_output"))
import agent_output as ao  # noqa: E402

TOP_KEYS = ["schema", "command", "args", "exit_code", "ok", "errors", "warnings", "notes", "next", "data", "records", "other"]
NEXT_KEYS = ["command", "why", "human_step", "after_failure"]
# Git Bash on Windows (System32\bash.exe is WSL, a different machine); bash elsewhere
GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = GIT_BASH if os.name == "nt" and os.path.isfile(GIT_BASH) else shutil.which("bash")
WRAPPED = "new validate preview perf techniques tiers impostors assets package pack sign verify keygen add-to-browser playtest where".split()

PERF = """OPEN_MS 120
PACKAGE /w/beach
WORLD beach "Beach House" 0.1.0 by Ann
SIGNER unsigned
WARN spawn is 2.00 m above the ground (ground y 0.00): visitors drop from the air. Set its y to 0.00.
WARN odd thing nobody explained
STATS triangles          115000 / 150000
STATS draw_calls             12 / -
NPCS 0  QUESTS 0  SPAWN (0.0, 2.0, 0.0)
REUSE new 100 bytes (0.0 MB), reused 0 bytes (0.0 MB) in 0 objects
OK
BUILD_MS 900
VIEW 0 spawn draw=10 prims=2000 objects=5 fps=not measured -> /s/beach_0_spawn.png
VIEW 1 ring0 draw=40 prims=160000 objects=9 fps=31.5 -> /s/beach_1_ring0.png
PREVIEW_MS total=5000 views=2 (spawn 2000, ring0 3000)
TARGET triangles         FAIL  160000 (limit 150000)  -> recipes: lod_chain, impostor, merge_static
TARGET draw_calls        PASS  40 (limit 150)
TARGET worst_frame_ms   NOT MEASURED  no frame was timed: each view needs more than 20 frames
TARGET world_scripts_ms INFO  no world scripts
TARGETS FAIL (1)
"""


class Schema(unittest.TestCase):
    def check_shape(self, out):
        self.assertEqual(list(out), TOP_KEYS)
        self.assertEqual(out["schema"], "iamar-kit-output/1")
        self.assertEqual(out["ok"], out["exit_code"] == 0)
        for item in out["errors"] + out["warnings"]:
            self.assertEqual(sorted(item), ["fix", "message"])
            self.assertTrue(item["fix"].strip(), item)
        if out["next"] is not None:
            self.assertEqual(list(out["next"]), NEXT_KEYS)
        json.dumps(out)

    def test_perf_measurements(self):
        out = ao.parse("perf", 1, ["worlds/beach", "shots/beach/view"], PERF)
        self.check_shape(out)
        d = out["data"]
        self.assertEqual(d["world"], {"id": "beach", "title": "Beach House", "version": "0.1.0", "author": "Ann"})
        self.assertEqual(d["stats"]["triangles"], {"used": 115000, "budget": 150000})
        self.assertIsNone(d["stats"]["draw_calls"]["budget"])
        self.assertEqual([sorted(v) for v in d["views"]][0], sorted(["index", "name", "draw_calls", "primitives", "objects", "fps", "file"]))
        self.assertIsNone(d["views"][0]["fps"])
        self.assertEqual(d["views"][1]["fps"], 31.5)
        t = {x["name"]: x for x in d["targets"]}
        self.assertEqual(t["triangles"]["status"], "FAIL")
        self.assertEqual(t["triangles"]["recipes"], ["lod_chain", "impostor", "merge_static"])
        self.assertEqual(t["draw_calls"], dict(t["draw_calls"], status="PASS", value=40, limit=150))
        self.assertEqual(t["worst_frame_ms"]["status"], "NOT_MEASURED")   # never PASS 0.0
        self.assertEqual(d["targets_result"], "FAIL (1)")
        self.assertEqual(d["timings_ms"], {"open": 120, "build": 900, "preview": 5000})
        self.assertEqual(d["reuse"], {"new_bytes": 100, "reused_bytes": 0, "objects": 0})
        # a failed target is an error whose fix names the recipes
        self.assertIn("lod_chain", out["errors"][0]["fix"])
        # the message's own advice is the fix; a message without advice still gets one
        self.assertEqual(out["warnings"][0]["fix"], "Set its y to 0.00.")
        self.assertEqual(out["warnings"][1]["fix"], ao.GENERIC_FIX)
        self.assertTrue(out["next"]["after_failure"])
        self.assertIn("recipes", out["next"]["why"])

    def test_every_wrapped_command_has_the_shape(self):
        samples = {
            "new": ("NEW beach (Beach) in /w/beach - next: edit scene.json, then `iamar-world validate worlds/beach`\n", ["worlds/beach"]),
            "validate": ("PACKAGE /w\nOK\n", ["worlds/beach"]),
            "techniques": ("TECHNIQUE lod_chain 3 meshes got a distance LOD chain\nADVICE merge the fences\nTECHNIQUES tier=low advice=1\n", ["worlds/beach"]),
            "package": ("PACKED out/b.iamar (1234 bytes, 2 pieces, sha256 abc123)\nPIECES out/b.pieces.json (signed)\n", ["worlds/beach", "out/b.iamar", "k.key", "Ann"]),
            "sign": ("SIGNED worlds/beach: 12 files, key k1, signer Ann\n", ["worlds/beach", "k.key", "Ann"]),
            "verify": ("SIGNER Ann (k1)\nSTATUS valid\nOK\n", ["out/b.iamar"]),
            "keygen": ("KEY /k/ann.key\nPUBLIC /k/ann.key.pub\nKEY_ID k1\n", ["ann"]),
            "add-to-browser": ("ADDED b (Beach, Ann) to /data/worlds\nNow in iamar: Esc menu -> Host My World -> pick beach -> Start Hosting.\n", ["out/b.iamar"]),
            "playtest": ("STEP 1 walk\nPLAYTEST PASS: 3 step(s), 0 failed -> /o/playtest.json\n", ["worlds/beach", "steps.json"]),
            "assets": ("USED oak as assets/oak.glb (10 bytes reused)\n", ["use", "worlds/beach", "oak"]),
            "where": ("KIT /k\nDOCS /k/docs\nBROWSER /b/iamar\n", []),
        }
        for command in WRAPPED:
            text, args = samples.get(command, ("OK\n", ["worlds/beach"]))
            out = ao.parse(command, 0, args, text)
            self.check_shape(out)
            self.assertIsNotNone(out["next"], command)
            self.assertFalse(out["next"]["after_failure"])
        self.assertEqual(ao.parse("package", 0, samples["package"][1], samples["package"][0])["data"]["packed"],
                         {"path": "out/b.iamar", "bytes": 1234, "pieces": 2, "sha256": "abc123"})
        self.assertEqual(ao.parse("playtest", 0, [], samples["playtest"][0])["data"]["playtest"]["result"], "PASS")
        self.assertIn("Host My World", ao.parse("add-to-browser", 0, ["b.iamar"], samples["add-to-browser"][0])["next"]["human_step"])

    def test_usage_failure_on_stderr_is_an_error_with_a_fix(self):
        out = ao.parse("package", 2, ["worlds/beach"], "", "usage: package <folder> <out.iamar> <key> <signer name>\n")
        self.check_shape(out)
        self.assertFalse(out["ok"])
        self.assertIn("usage", out["errors"][0]["message"])
        self.assertIn("usage line", out["errors"][0]["fix"])
        self.assertEqual(out["next"]["command"], "iamar-world package worlds/beach")

    def test_known_messages_without_advice_get_specific_fixes(self):
        self.assertIn("iamar-world doctor", ao.fix_for("pack needs your key and name: visitors refuse unsigned worlds (see `keygen`)"))
        self.assertIn("assets search", ao.fix_for("no object oak in the library"))
        self.assertIn("WORLD_FORMAT", ao.fix_for("scene.json: objects[0].asset 'x.glb' is not in the package"))
        self.assertIn("doctor", ao.fix_for("preview rendered no world geometry (every VIEW had draw=0 prims=0 objects=0)."))

    def test_report_v1_json_line_lands_in_data(self):
        out = ao.parse("validate", 0, ["w", "--report-v1"], '{"valid": true, "issues": []}\n')
        self.assertEqual(out["data"]["report"], {"valid": True, "issues": []})


class Next(unittest.TestCase):
    def nxt(self, command, args, code=0, data=None):
        return ao.next_step(command, code, args, data)["command"]

    def test_happy_path_chain(self):
        self.assertEqual(self.nxt("new", ["worlds/beach", "--title", "Beach"]), "iamar-world validate worlds/beach")
        self.assertEqual(self.nxt("validate", ["worlds/beach"]), "iamar-world preview worlds/beach shots/beach/view")
        self.assertEqual(self.nxt("preview", ["worlds/beach", "/tmp/b", "--quick"]), "iamar-world perf worlds/beach /tmp/b")
        self.assertEqual(self.nxt("perf", ["worlds/beach", "/tmp/b"]), "iamar-world playtest worlds/beach")
        self.assertTrue(self.nxt("playtest", ["worlds/beach"]).startswith("iamar-world package worlds/beach out/beach.iamar"))
        self.assertTrue(ao.next_step("playtest", 0, ["worlds/beach"])["human_step"])   # the key needs the user
        self.assertEqual(self.nxt("package", ["worlds/beach", "out/b.iamar", "k.key", "Ann"]), "iamar-world verify out/b.iamar")
        self.assertEqual(self.nxt("verify", ["out/b.iamar"]), "iamar-world add-to-browser out/b.iamar")
        self.assertTrue(ao.next_step("add-to-browser", 0, ["out/b.iamar"])["human_step"])

    def test_paths_with_spaces_are_quoted_and_options_skipped(self):
        self.assertEqual(self.nxt("validate", ["my world", "--tier", "low"]), 'iamar-world preview "my world" "shots/my world/view"')
        self.assertEqual(self.nxt("keygen", ["ann"], data={"key": "/k/ann.key"}), 'iamar-world sign <world folder> /k/ann.key "<Your Name>"')

    def test_failure_reruns_the_same_command(self):
        step = ao.next_step("validate", 1, ["worlds/beach"])
        self.assertEqual(step["command"], "iamar-world validate worlds/beach")
        self.assertTrue(step["after_failure"])
        self.assertIn("fix the ERROR", ao.next_line(step))

    def test_commands_without_next(self):
        for command in ("help", "doctor", "serve", "host", "publish"):
            self.assertIsNone(ao.next_step(command, 0, []))
        self.assertEqual(ao.next_line(None), "")

    def test_cli_next_prints_one_line(self):
        p = subprocess.run([sys.executable, str(ROOT / "kit/agent_output/agent_output.py"), "next", "new", "0", "worlds/a"],
                           capture_output=True, text=True)
        self.assertEqual(p.stdout, "NEXT: iamar-world validate worlds/a\n")


class LauncherSource(unittest.TestCase):
    BASH = (ROOT / "kit/iamar-world").read_text(encoding="utf-8")
    CMD = (ROOT / "kit/iamar-world.cmd").read_text(encoding="utf-8")

    def test_same_wrapped_commands_in_both_launchers(self):
        bash = re.search(r'case " ([a-z -]+) " in\n  \*" \$cmd "\*\)', self.BASH).group(1).split()
        cmd = re.search(r"for %%C in \(([a-z -]+)\) do if /i \"%~1\"==\"%%C\" set \"WANT_JSON=%%C\"", self.CMD).group(1).split()
        self.assertEqual(bash, WRAPPED)
        self.assertEqual(cmd, WRAPPED)

    def test_human_runs_end_with_next(self):
        self.assertEqual(self.BASH.count('next_hint "$rc"'), 3)            # playtest, preview retry, every other native command
        self.assertNotIn('exec "$browser" --audio-driver', self.BASH)       # the final run returns so NEXT can print
        self.assertIn(':end\nset "END_RC=%ERRORLEVEL%"\ncall :next_hint %END_RC%\nendlocal & exit /b %END_RC%', self.CMD.replace("\r\n", "\n"))
        self.assertIn("call :next_hint %PT_RC%\nexit /b %PT_RC%", self.CMD.replace("\r\n", "\n"))

    def test_child_never_wraps_again(self):
        self.assertIn('IAMAR_KIT_OUTPUT_CHILD="1"', (ROOT / "kit/agent_output/agent_output.py").read_text())
        self.assertIn('if not defined IAMAR_KIT_OUTPUT_CHILD call :want_json %*', self.CMD)
        self.assertIn('[[ -z "${IAMAR_KIT_OUTPUT_CHILD:-}" && $want_json == 1', self.BASH)


@unittest.skipUnless(BASH and not (os.name == "nt" and BASH != GIT_BASH), "needs bash (Git Bash on Windows)")
class BashLauncher(unittest.TestCase):
    """kit/iamar-world against an inert browser stub."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="iamar agent output "))
        kit = self.tmp / "kit"
        kit.mkdir()
        shutil.copy2(ROOT / "kit/iamar-world", kit / "iamar-world")
        shutil.copytree(ROOT / "kit/agent_output", kit / "agent_output")
        (self.tmp / "my world").mkdir()
        stub = self.tmp / "stub"
        stub.write_text('#!/usr/bin/env bash\n[[ "${*: -2}" == "--kit where" ]] && exit 0\n'
                        'echo "ARGS $*"\n'
                        'if [[ "${STUB_MODE:-}" == fail ]]; then echo "ERROR scene.json: objects[0].asset x.glb is not in the package"; echo FAILED; exit 1; fi\n'
                        'echo "WARN spawn is 3.00 m above the ground (ground y 0.00): visitors drop. Set its y to 0.00."\necho OK\n',
                        newline="\n")
        stub.chmod(0o755)
        self.env = dict(os.environ, IAMAR_BROWSER=self.bash_path(stub), PYTHON=self.bash_path(pathlib.Path(sys.executable)))
        for k in ("IAMAR_KIT_OUTPUT_CHILD", "IAMAR_KIT_NO_NEXT", "IAMAR_PROJECT", "STUB_MODE"):
            self.env.pop(k, None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def bash_path(p):
        if os.name != "nt":
            return str(p)
        return subprocess.run([BASH, "-c", 'cygpath -u "$1"', "_", str(p)], capture_output=True, text=True).stdout.strip()

    def run_kit(self, *args, **env):
        e = dict(self.env, **env)
        return subprocess.run([BASH, self.bash_path(self.tmp / "kit/iamar-world"), *args], cwd=self.tmp, env=e,
                              capture_output=True, text=True, timeout=60)

    def test_human_mode_ends_with_next(self):
        p = self.run_kit("validate", "my world")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.splitlines()[-1], 'NEXT: iamar-world preview "my world" "shots/my world/view"')
        p = self.run_kit("validate", "my world", STUB_MODE="fail")
        self.assertEqual(p.returncode, 1)
        self.assertTrue(p.stdout.splitlines()[-1].startswith('NEXT: iamar-world validate "my world"   (fix the ERROR'))
        p = self.run_kit("validate", "my world", IAMAR_KIT_NO_NEXT="1")
        self.assertNotIn("NEXT:", p.stdout)

    def test_json_mode_prints_one_object_and_keeps_the_exit_code(self):
        p = self.run_kit("validate", "my world", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(list(out), TOP_KEYS)
        self.assertEqual(out["args"], ["my world"])
        self.assertEqual(out["warnings"][0]["fix"], "Set its y to 0.00.")
        self.assertNotIn("--json", out["records"][0]["text"])      # the browser never sees --json
        self.assertNotIn("NEXT:", p.stdout)
        p = self.run_kit("validate", "my world", "--json", STUB_MODE="fail")
        self.assertEqual(p.returncode, 1)
        out = json.loads(p.stdout)
        self.assertFalse(out["ok"])
        self.assertTrue(out["errors"][0]["fix"])

    def test_json_without_python_is_still_json(self):
        p = self.run_kit("validate", "my world", "--json", PYTHON="/nonexistent/python3", PATH="/usr/bin:/bin")
        if p.returncode != 2:                       # a system python3 on /usr/bin answered instead
            self.assertEqual(json.loads(p.stdout)["schema"], "iamar-kit-output/1")
            return
        out = json.loads(p.stdout)
        self.assertFalse(out["ok"])
        self.assertIn("Python", out["errors"][0]["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
