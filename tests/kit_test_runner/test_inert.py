#!/usr/bin/env python3
"""Exercise run_tests.sh result handling without executing browser or suite code."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
HISTORICAL = (
    "kit_cwd_argv", "kit_direct_cwd", "kit_view_argv", "kit_script_preview",
    "kit_perf_scripts", "tier_preflight",
)


@unittest.skipUnless(BASH, "Bash is required by the runner")
class RunnerClassification(unittest.TestCase):
    def run_fixture(self, suite, status, output="fixture failure", missing_timeout=False,
                    smoke_status=0, no_overlay=True, relative_ws=False, pack_mode=False,
                    setup_failure=""):
        with tempfile.TemporaryDirectory(prefix="kit-runner-fixture-") as tmp:
            root = Path(tmp)
            tools = root / "tools"
            bins = root / "bin"
            tools.mkdir()
            bins.mkdir()
            # Copy only reviewed runner text. Never copy or run repository tests,
            # build_pack.sh, smoke.sh, a Godot binary, or browser source code.
            shutil.copyfile(ROOT / "tools/run_tests.sh", tools / "run_tests.sh")

            def stub(path, body):
                path.write_text("#!" + BASH + "\n" + body + "\n")
                path.chmod(0o700)

            stub(tools / "smoke.sh", 'exit "$FIXTURE_SMOKE_STATUS"')
            stub(bins / "rsync", '\n'.join((
                'if [[ "$FIXTURE_SETUP_FAILURE" == browser-copy && "$*" == *--delete* ]]; then exit 31; fi',
                'if [[ "$FIXTURE_SETUP_FAILURE" == overlay-copy && "$*" != *--delete* ]]; then exit 32; fi',
                'exit 0',
            )))
            stub(bins / "cp", "exit 33")  # tool-copy failure only; no real copy
            if setup_failure == "tool-copy":
                (tools / "kit_bundle.sh").write_text("inert; never executed")
            stub(bins / "offscreen", "exit 99")  # discovered but never invoked
            capture = root / "child-env.txt"
            command_capture = root / "child-command.txt"
            if not missing_timeout:
                # This child records its environment without executing the real
                # timeout arguments (nice, renderer, interpreter or selected suite).
                stub(bins / "timeout", '\n'.join((
                    'printf "%s\\n" "$IAMAR_TEST_SOURCE_ROOT" "$IAMAR_BROWSER_SOURCE_ROOT" '
                    '"$IAMAR_PROJECT" "$PWD" "$FIXTURE_INHERITED_SENTINEL" > "$FIXTURE_CAPTURE"',
                    'printf "%s\\n" "$@" > "$FIXTURE_COMMAND_CAPTURE"',
                    'printf "%s\\n" "$FIXTURE_OUTPUT"; exit "$FIXTURE_STATUS"',
                )))
            # A closed PATH prevents accidental discovery/execution of an installed
            # timeout, renderer, nice, Godot, or suite interpreter. Only utilities
            # used for temporary workspace setup and summary rendering are allowed.
            for command in ("dirname", "basename", "mkdir", "mktemp", "rm", "tail", "sed", "grep"):
                executable = shutil.which(command)
                if executable is None:
                    self.skipTest("Required fixture utility missing: " + command)
                (bins / command).symlink_to(executable)
            if setup_failure == "resolution":
                (bins / "mkdir").unlink()
                stub(bins / "mkdir", 'exit 0')  # pretend success, leave WS absent
            browser = root / "browser"
            browser.mkdir()
            pack = root / "fixture.pck"
            pack.write_bytes(b"inert fixture; never opened")
            env = {
                "PATH": str(bins), "HOME": str(root / "home"), "TMPDIR": str(root),
                "LC_ALL": "C", "KIT_TEST_TIMEOUT": "1", "FIXTURE_STATUS": str(status),
                "FIXTURE_OUTPUT": output, "FIXTURE_SMOKE_STATUS": str(smoke_status),
                "FIXTURE_CAPTURE": str(capture), "FIXTURE_INHERITED_SENTINEL": "keep-me",
                "FIXTURE_COMMAND_CAPTURE": str(command_capture),
                "FIXTURE_SETUP_FAILURE": setup_failure,
                # Poison inherited roots: neither the kit host nor browser host may
                # leak into the workspace child, even under --no-overlay.
                "IAMAR_TEST_SOURCE_ROOT": str(ROOT),
                "IAMAR_BROWSER_SOURCE_ROOT": str(browser),
                "IAMAR_PROJECT": str(browser),
            }
            workspace = root / "workspace with spaces"
            if setup_failure == "workspace":
                workspace.write_text("file blocks directory creation")
            options = ["--ws", workspace.name if relative_ws else str(workspace)]
            if no_overlay:
                options.append("--no-overlay")
            if pack_mode:
                options.append("--pack-mode")
            result = subprocess.run(
                [BASH, str(tools / "run_tests.sh"), str(browser), "--pack", str(pack),
                 *options, suite],
                cwd=root, env=env, capture_output=True, text=True, timeout=10,
            )
            if setup_failure or missing_timeout or pack_mode and suite != "kit_page_check":
                self.assertFalse(capture.exists(), result.stdout + result.stderr)
            else:
                self.assertTrue(capture.exists(), result.stdout + result.stderr)
                self.assertEqual(capture.read_text().splitlines(),
                                 [str(workspace.resolve())] * 4 + ["keep-me"])
                self.assertNotEqual(workspace.resolve(), ROOT.resolve())
                self.assertNotEqual(workspace.resolve(), browser.resolve())
                if suite == "tier_preflight":
                    command = command_capture.read_text().splitlines()[-1]
                    self.assertIn('--dependency-root "$IAMAR_BROWSER_SOURCE_ROOT"', command)
                    self.assertNotIn(str(browser), command)
                    self.assertNotIn(str(ROOT), command)
            return result

    def assert_result(self, result, suite, classification, exit_code):
        self.assertEqual(result.returncode, exit_code, result.stdout + result.stderr)
        rows = [line.split() for line in result.stdout.splitlines()]
        self.assertIn([suite, classification], [row[:2] for row in rows])
        self.assertNotIn("XFAIL", result.stdout)

    def test_workspace_roots_override_host_roots(self):
        for no_overlay in (False, True):
            for relative_ws in (False, True):
                for suite in ("kit_cwd_argv", "kit_direct_cwd", "kit_script_preview", "tier_preflight"):
                    with self.subTest(no_overlay=no_overlay, relative_ws=relative_ws,
                                      suite=suite):
                        result = self.run_fixture(suite, 0, "ok", no_overlay=no_overlay,
                                                  relative_ws=relative_ws)
                        self.assert_result(result, suite, "PASS", 0)

    def test_pack_mode_source_suite_still_skips(self):
        result = self.run_fixture("kit_script_preview", 0, pack_mode=True)
        self.assert_result(result, "kit_script_preview", "SKIP", 0)

    def test_pack_mode_command_suite_receives_workspace_roots(self):
        result = self.run_fixture("kit_page_check", 0, pack_mode=True, relative_ws=True)
        self.assert_result(result, "kit_page_check", "PASS", 0)

    def test_workspace_setup_failures_never_start_suite(self):
        for failure, message in (
                ("workspace", "creating the workspace failed"),
                ("resolution", "resolving the workspace failed"),
                ("browser-copy", "copying the browser failed"),
                ("overlay-copy", "overlaying kit failed"),
                ("tool-copy", "overlaying tools/kit_bundle.sh failed")):
            with self.subTest(failure=failure):
                result = self.run_fixture("kit_script_preview", 0, no_overlay=False,
                                          setup_failure=failure)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(message, result.stderr)
                self.assertNotIn("--- kit_script_preview", result.stdout)

    def test_historical_failure_is_not_an_exemption(self):
        for suite in HISTORICAL:
            with self.subTest(suite=suite):
                result = self.run_fixture(suite, 1, "historical baseline assertion")
                self.assert_result(result, suite, "FAIL", 1)
                self.assertIn("historical baseline only; current failure unverified", result.stdout)
                self.assertIn("historical baseline assertion", result.stdout)

    def test_novel_failure_in_every_historical_suite(self):
        for suite in HISTORICAL:
            with self.subTest(suite=suite):
                result = self.run_fixture(suite, 1, "unexpected new regression")
                self.assert_result(result, suite, "FAIL", 1)
                self.assertIn("unexpected new regression", result.stdout)

    def test_mixed_historical_and_novel_output_fails(self):
        result = self.run_fixture("kit_cwd_argv", 1,
                                  "guard text check at test_inert.py:132\nnew regression")
        self.assert_result(result, "kit_cwd_argv", "FAIL", 1)

    def test_unlisted_failure(self):
        result = self.run_fixture("kit_new_argv", 1)
        self.assert_result(result, "kit_new_argv", "FAIL", 1)
        self.assertNotIn("historical baseline only", result.stdout)

    def test_success_for_historical_and_unlisted_suites(self):
        for suite in HISTORICAL + ("kit_new_argv",):
            with self.subTest(suite=suite):
                self.assert_result(self.run_fixture(suite, 0, "ok"), suite, "PASS", 0)

    def test_timeout(self):
        for suite in ("kit_cwd_argv", "kit_new_argv"):
            with self.subTest(suite=suite):
                self.assert_result(self.run_fixture(suite, 124), suite, "TIMEOUT", 1)

    def test_infrastructure_and_signal_statuses_fail(self):
        # timeout's internal failure, non-executable/missing command, SIGKILL,
        # SIGSEGV and SIGTERM are never historical expected failures.
        for status in (125, 126, 127, 137, 139, 143):
            for suite in ("kit_cwd_argv", "kit_new_argv"):
                with self.subTest(status=status, suite=suite):
                    self.assert_result(self.run_fixture(suite, status), suite, "FAIL", 1)

    def test_actual_missing_timeout_fails(self):
        result = self.run_fixture("kit_cwd_argv", 0, missing_timeout=True)
        self.assert_result(result, "kit_cwd_argv", "FAIL", 1)
        self.assertIn("timeout: command not found", result.stdout)

    def test_blender_skip_is_preserved(self):
        result = self.run_fixture("kit_blender_tools", 0, "SKIPPED")
        self.assert_result(result, "kit_blender_tools", "SKIP", 0)

    def test_smoke_failure_still_fails_aggregate(self):
        result = self.run_fixture("kit_cwd_argv", 0, "ok", smoke_status=1)
        self.assert_result(result, "kit_cwd_argv", "PASS", 1)
        self.assert_result(result, "smoke", "FAIL", 1)


if __name__ == "__main__":
    unittest.main()
