#!/usr/bin/env python3
"""Inert source/control-flow checks only. Does not parse/run GDScript or Wasm."""
from pathlib import Path
import hashlib
import os
import re
import unittest

def source_root_text(value, name, default=None):
    """Reject explicit blank roots before lookup; preserve nonblank path text."""
    if value is None and default is not None:
        return default
    if value is None or not value.strip():
        raise RuntimeError("Set " + name + " to a nonblank source checkout path")
    return value


# Test-source compatibility only: these pins do not approve execution/publication.
# The pending profile requires the complete atomic input/KV browser overlay.
BROWSER_TEST_PROFILES = {
    "published-baseline": "d8dcbb55b85f6860ee3a619c766de5b141ccb825",
    "reviewed-input-20261018": "566c5e38a8a356fb664b45622c5956500122baf8",
}


def browser_test_profile(value):
    """Omission alone selects baseline; exact named opt-in, never hash inference."""
    if value is None:
        return "published-baseline"
    if value not in BROWSER_TEST_PROFILES:
        raise RuntimeError("IAMAR_BROWSER_TEST_PROFILE must be published-baseline or "
                           "reviewed-input-20261018; omit it for the published baseline")
    return value


def runtime_matches_profile(source, profile):
    profile = browser_test_profile(profile)
    blob = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
    return blob == BROWSER_TEST_PROFILES[profile]


# Validate the selection before reading source files. Never auto-detect a profile.
BROWSER_TEST_PROFILE = browser_test_profile(os.environ.get("IAMAR_BROWSER_TEST_PROFILE"))

# Kit and browser sources have separate owners after the repository split.
ROOT = Path(source_root_text(os.environ.get("IAMAR_TEST_SOURCE_ROOT"),
                             "IAMAR_TEST_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
BROWSER_ROOT = Path(source_root_text(os.environ.get("IAMAR_BROWSER_SOURCE_ROOT"),
                                     "IAMAR_BROWSER_SOURCE_ROOT"))
VIEW = (ROOT / "scripts/kit/world_view.gd").read_text()
HELPER = (ROOT / "scripts/kit/world_script_preview.gd").read_text()
HOST = (BROWSER_ROOT / "scripts/sandbox/package_script_host.gd").read_bytes()
RUNTIME = (BROWSER_ROOT / "scripts/sandbox/world_script.gd").read_bytes()


def fn(text, name):
    return re.split(r"\n(?:static )?func ", text.split("func " + name + "(", 1)[1], maxsplit=1)[0]


class SourceContract(unittest.TestCase):
    def test_source_root_selection_rejects_missing_or_blank_overrides(self):
        default = Path("kit-default")
        self.assertEqual(source_root_text(None, "IAMAR_TEST_SOURCE_ROOT", default), default)
        with self.assertRaisesRegex(RuntimeError, "IAMAR_BROWSER_SOURCE_ROOT"):
            source_root_text(None, "IAMAR_BROWSER_SOURCE_ROOT")
        for name, fallback in [("IAMAR_TEST_SOURCE_ROOT", default),
                               ("IAMAR_BROWSER_SOURCE_ROOT", None)]:
            for value in ["", " ", "\t\n"]:
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(RuntimeError, name):
                        source_root_text(value, name, fallback)
            for value in ["source checkout", " source checkout "]:
                self.assertEqual(source_root_text(value, name, fallback), value)

    def test_live_host_untouched(self):
        self.assertEqual(hashlib.sha1(b"blob " + str(len(HOST)).encode() + b"\0" + HOST).hexdigest(),
                         "3a7706bc3e086b9a4c967319cb914d789221135c")
        self.assertIn(b'and is_instance_valid(player) and main.get("player") == player', HOST)

    def test_browser_profile_selection_is_exact_and_fail_closed(self):
        self.assertEqual(browser_test_profile(None), "published-baseline")
        self.assertEqual(BROWSER_TEST_PROFILES, {
            "published-baseline": "d8dcbb55b85f6860ee3a619c766de5b141ccb825",
            "reviewed-input-20261018": "566c5e38a8a356fb664b45622c5956500122baf8",
        })
        for name in BROWSER_TEST_PROFILES:
            self.assertEqual(browser_test_profile(name), name)
        for value in ["", " ", "\t\n", "unknown", "auto", "reviewed-input",
                      " reviewed-input-20261018", "reviewed-input-20261018 ",
                      *BROWSER_TEST_PROFILES.values(),
                      "890e203383a2218aa74aef00d40e0fb16d5c7139e46cc2bb6bd0ee8a0aea2ae5"]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "IAMAR_BROWSER_TEST_PROFILE"):
                    browser_test_profile(value)

    def test_runtime_matches_explicit_reviewed_source_profile(self):
        self.assertTrue(runtime_matches_profile(RUNTIME, BROWSER_TEST_PROFILE),
                        "WorldScript differs from selected profile " + BROWSER_TEST_PROFILE)

    def test_wrong_source_cannot_cross_profiles_or_mutate(self):
        # Whichever exact source is selected, the other profile must reject it.
        for name in BROWSER_TEST_PROFILES:
            with self.subTest(profile=name):
                if name != BROWSER_TEST_PROFILE:
                    self.assertFalse(runtime_matches_profile(RUNTIME, name))
                self.assertFalse(runtime_matches_profile(RUNTIME + b"\n# drift\n", name))
                self.assertFalse(runtime_matches_profile(b"", name))
        # Omission must still reject the integrated candidate even when opted in.
        self.assertEqual(runtime_matches_profile(RUNTIME, None),
                         BROWSER_TEST_PROFILE == "published-baseline")

    def test_no_init_activation(self):
        init = fn(VIEW, "_init")
        self.assertNotIn("ScriptPreview.attach", init)
        self.assertNotIn("PackageScriptHost.attach", VIEW)
        self.assertLess(init.index("if validate or pos.size() < 2:"), init.index("_pkg.build"))
        self.assertIn('if world == null:', init)

    def test_tree_entered_start_before_sampling(self):
        process = fn(VIEW, "_process")
        for before, after in [
            ("ScriptPreview.attach", "_script_us_seen = _script_us()"),
            ("_script_us_seen = _script_us()", "_cam = Camera3D.new()"),
            ("_cam = Camera3D.new()", "_auto_views(_world)"),
            ("ScriptPreview.check", "_wait += 1"),
            ("ScriptPreview.check", "var us := _script_us()"),
        ]:
            self.assertLess(process.index(before), process.index(after))

    def test_exact_package_root_source_custody(self):
        attach = fn(HELPER, "attach")
        for fence in ['pkg.ok', 'pkg.source == source', 'is_instance_valid(source)',
                      'host.is_inside_tree()', 'not host.is_queued_for_deletion()',
                      'world.is_inside_tree()', 'not world.is_queued_for_deletion()',
                      'pkg.root == world', 'world.get_parent() == host']:
            self.assertIn(fence, attach)
        self.assertGreaterEqual(attach.count("current.call()"), 5)
        self.assertIn('ws.get_parent() != world', fn(HELPER, "check"))

    def test_freed_references_reach_validation(self):
        self.assertIn('attach(pkg: Variant, world: Variant, host: Variant)', HELPER)
        self.assertIn('check(scripts: Array, current: Callable, world: Variant)', HELPER)
        for fence in ['is_instance_valid(pkg) and pkg is WorldPackage',
                      'is_instance_valid(world) and world is Node3D',
                      'is_instance_valid(host) and host is Node']:
            self.assertIn(fence, HELPER)

    def test_unrequested_and_freed_worlds_are_distinct(self):
        process = fn(VIEW, "_process")
        self.assertIn('if not _preview_requested:', process)
        self.assertNotIn('if _world == null', process)
        self.assertIn('_world = world\n\t_preview_requested = true', fn(VIEW, "_init"))

    def test_late_freed_root_precedes_script_inspection(self):
        check = fn(HELPER, "check")
        self.assertLess(check.index('not current.call()'), check.index('for ws in scripts:'))

    def test_data_only_before_runtime_requirement(self):
        attach = fn(HELPER, "attach")
        self.assertLess(attach.index("entries.is_empty()"), attach.index("WorldScript.available()"))
        self.assertLess(attach.index("WorldScript.available()"), attach.index("WorldScript.new()"))

    def test_package_bytes_and_existing_limits_only(self):
        attach = fn(HELPER, "attach")
        for exact in ['ws.asset_root = "package:"',
                      'source.read(path) if current.call() and source.has(path)',
                      'var bytes: PackedByteArray = source.read(rel)',
                      'pkg.manifest.get("budgets", {})',
                      'pkg.manifest.get("api_version", WorldApi.VERSION)',
                      'ws.load_bytes(bytes, budgets, api)']:
            self.assertIn(exact, attach)
        self.assertNotIn("load_file(", HELPER)
        self.assertNotIn("FileAccess", HELPER)

    def test_no_visitor_or_external_service_registration(self):
        executable = "\n".join(line.split("#", 1)[0] for line in HELPER.splitlines())
        for forbidden in ["add_player(", "ScriptNetBridge", 'get_node_or_null("Net")',
                          "local_key(", "ws.note =", "ws.sound =", "ws.play_stream =",
                          "ws.authority =", "load_bytes_async", "load(", "OS.execute"]:
            self.assertNotIn(forbidden, executable)
        self.assertIn('ws.kv_path = ""', executable)

    def test_void_start_and_health_after_both_boundaries(self):
        attach = fn(HELPER, "attach")
        self.assertIn("ws.start()\n\t\tproblem = check(scripts, current, world)", attach)
        self.assertNotIn("if not ws.start()", attach)
        self.assertEqual(attach.count("check(scripts, current, world)"), 2)
        check = fn(HELPER, "check")
        for fence in ["not is_instance_valid(ws)", "ws.is_queued_for_deletion()",
                      "not ws.is_inside_tree()", "not ws.loaded", "ws.loading",
                      "ws.disabled", "not ws.errors.is_empty()"]:
            self.assertIn(fence, check)

    def test_owned_partial_cleanup_and_explicit_failure(self):
        failed = fn(HELPER, "_failed")
        self.assertIn("dispose(scripts)", failed)
        self.assertIn('"ok": false', failed)
        dispose = fn(HELPER, "dispose")
        self.assertLess(dispose.index("ws.stop()"), dispose.index("ws.free()"))
        self.assertNotIn("world.free()", HELPER)
        self.assertNotIn("host.free()", HELPER)
        process = fn(VIEW, "_process")
        self.assertEqual(process.count("quit(1)"), 3)
        self.assertGreaterEqual(process.count("ScriptPreview.dispose(_scripts)"), 2)
        self.assertIn("world script preview failed", process)


class AttachmentModel(unittest.TestCase):
    """Small ordering model; source checks above bind its boundaries to the code."""
    @staticmethod
    def simulate(count=1, runtime=True, fail_at=None):
        events = []
        owned = []
        def fail():
            events.extend(("stop", n) for n in owned)
            events.extend(("free", n) for n in owned)
            return False, events
        events.append("custody")
        if fail_at == "custody":
            return fail()
        if count == 0:
            return True, events
        events.append("runtime")
        if not runtime:
            return fail()
        for n in range(count):
            for stage in ("before", "source"):
                events.append((stage, n))
                if fail_at == (stage, n):
                    return fail()
            owned.append(n)
            for stage in ("attach", "read", "load", "loaded", "start", "started"):
                events.append((stage, n))
                if fail_at == (stage, n):
                    return fail()
        return True, events

    def test_data_only_needs_no_runtime(self):
        self.assertEqual(self.simulate(count=0, runtime=False), (True, ["custody"]))

    def test_declared_script_needs_runtime(self):
        ok, events = self.simulate(runtime=False)
        self.assertFalse(ok)
        self.assertNotIn(("attach", 0), events)

    def test_initial_stale_owner_has_no_side_effects(self):
        self.assertEqual(self.simulate(fail_at="custody"), (False, ["custody"]))

    def test_partial_failures_dispose_only_created_scripts(self):
        for n in range(3):
            for stage in ("before", "source", "attach", "read", "load", "loaded", "start", "started"):
                with self.subTest(script=n, stage=stage):
                    ok, events = self.simulate(count=3, fail_at=(stage, n))
                    self.assertFalse(ok)
                    expected = list(range(n + int(stage not in ("before", "source"))))
                    self.assertEqual([e[1] for e in events if isinstance(e, tuple) and e[0] == "free"], expected)
                    self.assertNotIn(("start", n + 1), events)

    def test_success_orders_real_boundaries(self):
        ok, events = self.simulate(count=2)
        self.assertTrue(ok)
        for n in range(2):
            self.assertLess(events.index(("load", n)), events.index(("start", n)))
            self.assertLess(events.index(("start", n)), events.index(("started", n)))


if __name__ == "__main__":
    unittest.main()
