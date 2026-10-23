"""Shell setup only. Never starts Godot, exports, builds a pack or runs kit code."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).with_name("run.sh").read_text()


def section(start, end):
    return SOURCE[SOURCE.index(start):SOURCE.index(end)]


def shell(body, **env):
    return subprocess.run(
        ["bash", "-eu", "-o", "pipefail", "-c", body],
        env={"PATH": "/usr/bin:/bin", **{k: str(v) for k, v in env.items()}},
        text=True, capture_output=True, check=False,
    )


class SplitInstallSetup(unittest.TestCase):
    def test_native_gate_precedes_work(self):
        gate = section('if [[ "${KIT_TESTS_HEAVY:-0}"', 'PACK="${IAMAR_KIT_PACK:-}"')
        result = shell(gate + '\necho UNEXPECTED_WORK\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SKIP kit_release", result.stdout)
        self.assertNotIn("UNEXPECTED_WORK", result.stdout)

    def test_strip_real_shell_block_preserves_runtime_only(self):
        # An inert tree represents rsync's output; rsync itself is not mocked as
        # proof of a browser copy. The actual removal block runs on this fixture.
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            scripts = stage / "scripts/kit"
            scripts.mkdir(parents=True)
            keep = {"kit_loop", "world_scaffold", "world_techniques"}
            for name in keep | {"world_view", "world_sign", "future_tool"}:
                for suffix in (".gd", ".gd.uid"):
                    (scripts / (name + suffix)).write_text("inert source marker")
            (stage / ".godot/imported").mkdir(parents=True)
            (stage / ".godot/imported/texture.cache").write_text("inert cache")
            (stage / ".godot/exported").mkdir()
            (stage / ".godot/exported/old.gdc").write_text("stale tool")
            (stage / ".godot/global_script_class_cache.cfg").write_text("stale class")
            # A nested tool, direct link, and link inside a removed directory must
            # disappear without ever modifying the external marker they target.
            outside = stage / "outside-marker"
            outside.write_text("must survive")
            (scripts / "nested").mkdir()
            (scripts / "nested/deep.gd").write_text("nested tool")
            (scripts / "linked.gd").symlink_to(outside)
            (scripts / "nested/external").symlink_to(outside)
            (scripts / "broken").symlink_to(stage / "absent")
            body = section('confine_browser_tree() {', '# Never export') + '\nconfine_browser_tree "$STAGE" prune\n'
            result = shell(body, STAGE=stage)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({p.name for p in scripts.iterdir()},
                             {n + s for n in keep for s in (".gd", ".gd.uid")})
            self.assertEqual({p.name for p in (stage / ".godot").iterdir()}, {"imported"})
            self.assertEqual(outside.read_text(), "must survive")

    def test_rejects_symlink_ancestors_without_outside_mutation(self):
        helper = section('confine_browser_tree() {', '# Never export')
        for linked in ("parent", "root", "scripts", "scripts/kit", ".godot", ".godot/imported"):
            for mode in ("check", "prune"):
                with self.subTest(linked=linked, mode=mode), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    stage = base / "container/stage" if linked == "parent" else base / "stage"
                    scripts = stage / "scripts/kit"
                    scripts.mkdir(parents=True)
                    for name in ("kit_loop", "world_scaffold", "world_techniques"):
                        (scripts / (name + ".gd")).write_text("runtime fixture")
                    (stage / ".godot/imported").mkdir(parents=True)
                    victim = stage.parent if linked == "parent" else (stage if linked == "root" else stage / linked)
                    outside = base / "outside"
                    victim.rename(outside)
                    (outside / "must-survive").write_text("untouched")
                    victim.symlink_to(outside, target_is_directory=True)
                    before = sorted((str(p.relative_to(outside)), p.read_bytes())
                                    for p in outside.rglob("*") if p.is_file())
                    result = shell(helper + '\nconfine_browser_tree "$STAGE" "$MODE"\n',
                                   STAGE=stage, MODE=mode)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("directory must be real", result.stderr)
                    after = sorted((str(p.relative_to(outside)), p.read_bytes())
                                   for p in outside.rglob("*") if p.is_file())
                    self.assertEqual(after, before)

    def test_rejects_symlinked_allowlisted_script(self):
        helper = section('confine_browser_tree() {', '# Never export')
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            scripts = stage / "scripts/kit"
            scripts.mkdir(parents=True)
            outside = stage / "outside-marker"
            outside.write_text("unchanged")
            for name in ("kit_loop", "world_scaffold", "world_techniques"):
                (scripts / (name + ".gd")).write_text("runtime fixture")
            (scripts / "kit_loop.gd").unlink()
            (scripts / "kit_loop.gd").symlink_to(outside)
            result = shell(helper + '\nconfine_browser_tree "$STAGE" prune\n', STAGE=stage)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("runtime script must be a regular file", result.stderr)
            self.assertEqual(outside.read_text(), "unchanged")

    def test_missing_kit_requires_both_exact_status_and_diagnostic(self):
        # Only the assertion block is evaluated, with a shell stand-in for run.
        # It does not establish what a real exported browser would return.
        body = section('missing_rc=0', 'mkdir -p "$INSTALL/kit"')
        for status, diagnostic, accepted in [
            (3, "the developer kit is not installed", True),
            (0, "the developer kit is not installed", False),
            (2, "the developer kit is not installed", False),
            (124, "the developer kit is not installed", False),
            (3, "unrelated startup failure", False),
        ]:
            with self.subTest(status=status, diagnostic=diagnostic), tempfile.TemporaryDirectory() as tmp:
                prefix = 'cd "$WORK"; pass=0; run() { echo "$DIAGNOSTIC"; return "$STATUS"; };\n'
                result = shell(prefix + body, WORK=tmp, STATUS=status, DIAGNOSTIC=diagnostic)
                self.assertEqual(result.returncode == 0, accepted, result.stdout + result.stderr)

    def test_install_copies_exact_pack_and_only_requested_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            install = Path(tmp) / "runtime/linux/bin"
            (root / "kit").mkdir(parents=True)
            install.mkdir(parents=True)
            (root / "kit/AGENT_KIT.md").write_text("fixture guide")
            (root / "kit/iamar-world").write_text("inert wrapper, never executed")
            (install / "Oakhaven.x86_64").write_text("inert browser, never executed")
            pack = Path(tmp) / "matching.pck"
            pack.write_bytes(b"inert pack marker, not a Godot pack")
            body = section('mkdir -p "$INSTALL/kit"', 'must "built-in help"')
            result = shell(body, ROOT=root, INSTALL=install, PACK=pack)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((install / "kit/iamar-kit.pck").read_bytes(), pack.read_bytes())
            self.assertEqual(sorted(str(p.relative_to(install)) for p in install.rglob("*") if p.is_file()),
                             ["Oakhaven.x86_64", "kit/AGENT_KIT.md", "kit/iamar-kit.pck", "kit/iamar-world"])
            self.assertEqual(install.parents[2], Path(tmp))

    def test_exact_layout_rejects_all_extra_entry_types(self):
        body = section('# Compare the complete layout', 'must "where"')
        for extra in ("none", "file", "directory", "symlink", "fifo", "replace-file-with-link"):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as tmp:
                install = Path(tmp) / "install"
                (install / "kit").mkdir(parents=True)
                for name in ("Oakhaven.x86_64", "kit/AGENT_KIT.md", "kit/iamar-kit.pck", "kit/iamar-world"):
                    (install / name).write_text("inert")
                if extra == "file":
                    (install / "extra").write_text("inert")
                elif extra == "directory":
                    (install / "extra").mkdir()
                elif extra == "symlink":
                    (install / "extra").symlink_to("missing")
                elif extra == "fifo":
                    os.mkfifo(install / "extra")
                elif extra == "replace-file-with-link":
                    (install / "kit/AGENT_KIT.md").unlink()
                    (install / "kit/AGENT_KIT.md").symlink_to("missing")
                result = shell('cd "$WORK"; pass=0; fail=0;\n' + body + '\n[ "$fail" = 0 ]\n',
                               WORK=tmp, INSTALL=install)
                self.assertEqual(result.returncode == 0, extra == "none", result.stdout + result.stderr)

    def test_preview_requires_success_and_positive_geometry(self):
        helper = section('preview_result() {', 'if command -v offscreen')
        positive = "VIEW 0 custom draw=2 prims=12 objects=3 fps=60.0 -> fixture.png"
        for rc, log, accepted in ((0, positive, True), (124, positive, False),
                                  (1, positive, False), (0, "", False),
                                  (0, "VIEW 0 custom draw=0 prims=0 objects=0 fps=60.0", False),
                                  (0, "VIEW 0 custom draw=2 prims=0 objects=3 fps=60.0", False)):
            with self.subTest(rc=rc, log=log), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "preview.log"
                path.write_text(log + "\n")
                result = shell(helper + '\npass=0; fail=0; preview_result "$RC" "$LOG"; [ "$fail" = 0 ]\n',
                               RC=rc, LOG=path)
                self.assertEqual(result.returncode == 0, accepted, result.stdout + result.stderr)

    def test_templates_copy_privately_and_reject_links(self):
        helper = section('prepare_export_templates() {', 'TEMPLATES="${XDG_DATA_HOME')
        for linked in ("none", "root", "nested", "ancestor"):
            with self.subTest(linked=linked), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                source = base / "caller/godot/export_templates"
                source.mkdir(parents=True)
                (source / "template.marker").write_bytes(b"inert, never executed")
                outside = base / "outside.marker"
                outside.write_bytes(b"do not change")
                if linked == "nested":
                    (source / "escape").symlink_to(outside)
                elif linked in ("root", "ancestor"):
                    victim = source if linked == "root" else source.parent
                    moved = base / "original"
                    victim.rename(moved)
                    victim.symlink_to(moved, target_is_directory=True)
                target = base / "private/godot/export_templates"
                target.parent.mkdir(parents=True)
                result = shell(helper + '\nprepare_export_templates "$SOURCE" "$TARGET"\n',
                               SOURCE=source, TARGET=target)
                self.assertEqual(result.returncode == 0, linked == "none", result.stdout + result.stderr)
                self.assertEqual((source / "template.marker").read_bytes(), b"inert, never executed")
                self.assertEqual(outside.read_bytes(), b"do not change")
                if linked == "none":
                    self.assertEqual((target / "template.marker").read_bytes(), b"inert, never executed")
                    self.assertFalse(target.is_symlink())
                else:
                    self.assertFalse(target.exists())

    def test_source_routes_export_and_runtime_separately(self):
        self.assertIn('--path "$STAGE" --export-release', SOURCE)
        self.assertNotIn('--path "$ROOT" --export-release', SOURCE)
        self.assertIn('--exclude=/kit --exclude=/tests', SOURCE)
        self.assertLess(SOURCE.index('confine_browser_tree "$ROOT" check'), SOURCE.index('rsync -a'))
        self.assertLess(SOURCE.index('rsync -a'), SOURCE.index('confine_browser_tree "$STAGE" prune'))
        self.assertIn("--exclude='*.pck'", SOURCE)
        self.assertIn('E=(env -i HOME="$TMP/home" PATH=/usr/bin:/bin TERM=dumb)', SOURCE)
        self.assertIn('"${E[@]}" timeout 300 "$INSTALL/kit/iamar-world"', SOURCE)
        self.assertIn('grep -Fxq "$expected" w.log', SOURCE)
        self.assertLess(SOURCE.index('run validate missing-world'), SOURCE.index('cp "$PACK"'))
        self.assertIn('env HOME="$TMP/export-home" XDG_DATA_HOME="$EXPORT_DATA"', SOURCE)
        self.assertNotIn('ln -s', SOURCE)
        self.assertNotIn('|| true', SOURCE)
        self.assertIn('|| preview_rc=$?', SOURCE)


if __name__ == "__main__":
    unittest.main()
