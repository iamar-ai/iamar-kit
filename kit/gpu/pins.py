"""Pinned upstream versions of the GPU tier (kit/gpu/pins.json): hf(repo) and git_sha(name)."""
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pins.json")
with open(_PATH, encoding="utf-8") as _f:
    PINS = json.load(_f)


def hf(repo_id):
    """The Hugging Face commit to pass as revision= for repo_id."""
    return PINS["hf"][repo_id]


def snapshot(repo_id, patterns):
    """Local folder of repo_id at its pinned revision (downloads only `patterns` on first use). The
    Hunyuan3D pipelines take a local folder as model_path and cannot be given revision= themselves."""
    from huggingface_hub import snapshot_download
    return snapshot_download(repo_id, revision=hf(repo_id), allow_patterns=patterns)


def git_sha(name):
    """The commit a git clone of `name` (a key of pins.json "git") must be at."""
    return PINS["git"][name]["sha"]


def git_head(clone):
    """HEAD commit of a git clone read from its .git folder (no git needed), else None."""
    g = os.path.join(clone or "", ".git")
    try:
        with open(os.path.join(g, "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
        if not head.startswith("ref:"):
            return head
        ref = head.split(None, 1)[1]
        p = os.path.join(g, *ref.split("/"))
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
        with open(os.path.join(g, "packed-refs"), encoding="utf-8") as f:
            for line in f:
                if line.strip().endswith(" " + ref):
                    return line.split()[0]
    except OSError:
        pass
    return None


def file_problem(path, key, full=False):
    """A sentence when `path` is not the pinned file `key` (pins.json "files"): size always, sha256 when full."""
    want = PINS["files"][key]
    size = os.path.getsize(path)
    if size != want["size"]:
        return "%s is %d bytes, pinned %d (download %s at revision %s)" % (path, size, want["size"], key.rsplit("/", 1)[0], hf(key.rsplit("/", 1)[0]))
    if full:
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for blk in iter(lambda: f.read(1 << 24), b""):
                h.update(blk)
        if h.hexdigest() != want["sha256"]:
            return "%s sha256 %s differs from the pinned %s" % (path, h.hexdigest()[:12], want["sha256"][:12])
    return None


def clone_problem(clone, name):
    """A sentence when the clone is not at the pinned commit (None when it is, or is no git clone)."""
    want, have = git_sha(name), git_head(clone)
    if have is None:
        return None if not os.path.isdir(os.path.join(clone or "", ".git")) else "%s clone HEAD unreadable" % name
    if have != want:
        return "%s clone is at %s, pinned %s: git -C %s checkout %s" % (name, have[:8], want[:8], clone, want)
    return None
