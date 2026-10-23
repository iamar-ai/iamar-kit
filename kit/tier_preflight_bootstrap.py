"""Generate a pinned data-only sidecar, then exec the configured source Godot.

Not a process runner: timeout, signals, limits and settlement remain with the
existing owned supervisor. Downloaded KitLoop builds are deliberately refused.
No editor/import pass, package archive, decoder or full project is launched.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

CLASSES = {
    "scripts/kit/kit_loop.gd": ("KitLoop", "SceneTree"),
    "scripts/security/media_guard.gd": ("MediaGuard", "RefCounted"),
    "scripts/security/safe_text.gd": ("SafeText", "RefCounted"),
    "scripts/security/zip_guard.gd": ("ZipGuard", "RefCounted"),
    "scripts/worlds/json_schema.gd": ("JsonSchema", "RefCounted"),
    "scripts/worlds/world_format.gd": ("WorldFormat", "RefCounted"),
    "scripts/worlds/world_source.gd": ("WorldSource", "RefCounted"),
    "scripts/worlds/world_archive_byte_budget.gd": ("WorldArchiveByteBudget", "RefCounted"),
    "scripts/worlds/world_zip_bytes.gd": ("WorldZipBytes", "ZipGuard.ArchiveInput"),
    "scripts/worlds/world_tiers.gd": ("WorldTiers", "RefCounted"),
    # Referenced by world_format.gd (WorldApi.VERSION, WorldExperiencePolicy).
    # PackagePrewarm is compiled for kit_loop.gd's reference, never started:
    # world_tier_preflight.gd, not KitLoop, is the sidecar's main loop.
    "scripts/sandbox/world_api.gd": ("WorldApi", "RefCounted"),
    "scripts/worlds/world_experience_policy.gd": ("WorldExperiencePolicy", "RefCounted"),
    "scripts/world/package_prewarm.gd": ("PackagePrewarm", "RefCounted"),
}
FILES = tuple(CLASSES) + ("scripts/kit/world_tier_preflight.gd", "schemas/manifest.schema.json", "schemas/scene.schema.json", "scripts/worlds/validation_report.gd", "scripts/worlds/validation_report_catalog.json")
PROJECT = ('config_version=5\n\n[application]\nconfig/name="iamar-tier-source-preflight"\n'
           '\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
           '\n[debug]\nfile_logging/enable_file_logging=false\nfile_logging/enable_file_logging.pc=false\n')
MAX_CLOSURE_BYTES = 512 * 1024
MANIFEST = "tier_preflight_manifest.json"


def refuse():
    raise ValueError("data-only preflight configuration is unavailable")


def checked(path, directory):
    raw = os.fspath(path)
    path = Path(raw)
    if not path.is_absolute() or raw != os.path.normpath(raw):
        refuse()
    for part in (path, *path.parents):
        st = part.lstat()
        if stat.S_ISLNK(st.st_mode):
            refuse()
        if part != path and not stat.S_ISDIR(st.st_mode):
            refuse()
    st = path.lstat()
    if (directory and not stat.S_ISDIR(st.st_mode)) or (not directory and (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1)):
        refuse()
    return path


def source_bytes(root):
    result = {}
    total = 0
    for name in FILES:
        path = checked(root / name, False)
        size = path.stat().st_size
        total += size
        if size > 256 * 1024 or total > MAX_CLOSURE_BYTES:
            refuse()
        with path.open("rb") as stream:
            data = stream.read(size + 1)
        if len(data) != size:
            refuse()
        result[name] = data
    return result


def inventory(content):
    return {"version": 1, "files": {name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in content.items()}}


def registry(content):
    records = []
    for name, expected in CLASSES.items():
        text = content[name].decode("utf-8")
        classes = re.findall(r"^class_name ([A-Za-z0-9_]+)\s*$", text, re.M)
        bases = re.findall(r"^extends ([A-Za-z0-9_]+)\s*$", text, re.M)
        if name == "scripts/worlds/world_zip_bytes.gd":
            bases = re.findall(r"^extends (ZipGuard\.ArchiveInput)\s*$", text, re.M)
        if classes != [expected[0]] or bases != [expected[1]]:
            refuse()
        # Pinned Godot leaves global base metadata empty for this nested extends.
        registry_base = "" if name == "scripts/worlds/world_zip_bytes.gd" else bases[0]
        records.append('{\n"base": &"%s",\n"class": &"%s",\n"icon": "",\n"is_abstract": false,\n"is_tool": false,\n"language": &"GDScript",\n"path": "res://%s"\n}' % (registry_base, classes[0], name))
    return "list=[" + ", ".join(records) + "]\n"


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)


def main():
    # Build-time, read-only manifest generation. Writing the returned bytes is
    # an explicit repository build action, never a runtime fallback on drift.
    if len(sys.argv) == 3 and sys.argv[1] == "--manifest":
        root = checked(sys.argv[2], True)
        print(json.dumps(inventory(source_bytes(root)), indent=2, sort_keys=True))
        return
    if len(sys.argv) != 4 or os.environ.get("IAMAR_BROWSER"):
        refuse()
    root, source, runtime = [checked(arg, True) for arg in sys.argv[1:]]
    if any(a == b or a in b.parents or b in a.parents for a, b in [(root, source), (root, runtime), (source, runtime)]):
        refuse()
    st = runtime.stat()
    if st.st_uid != os.geteuid() or st.st_mode & 0o077 or any(runtime.iterdir()):
        refuse()
    godot = checked(os.environ.get("GODOT", ""), False)
    if not os.access(godot, os.X_OK) or source in godot.parents or runtime in godot.parents:
        refuse()
    content = source_bytes(root)
    manifest_path = checked(root / "kit" / MANIFEST, False)
    if manifest_path.stat().st_size > 16384:
        refuse()
    expected = json.loads(manifest_path.read_text(encoding="utf-8"))
    if expected != inventory(content):
        refuse()
    project = runtime / "project"
    project.mkdir(mode=0o700)
    for name, data in content.items():
        write_new(project / name, data)
    write_new(project / "project.godot", PROJECT.encode())
    write_new(project / ".godot/global_script_class_cache.cfg", registry(content).encode())
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    for key, name in [("HOME", "home"), ("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("XDG_CACHE_HOME", "cache")]:
        path = runtime / name
        path.mkdir(mode=0o700)
        env[key] = str(path)
    os.chdir(runtime)
    os.execve(str(godot), [str(godot), "--headless", "--audio-driver", "Dummy", "--path", str(project), "--script", "res://scripts/kit/world_tier_preflight.gd", "--", str(source)], env)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("ERROR data-only tier preflight requires a verified source-Godot sidecar and private runtime", file=sys.stderr)
        sys.exit(2)
