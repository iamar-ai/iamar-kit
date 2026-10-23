#!/usr/bin/env python3
"""The Mission Hall example's scene and audio steps write a consistent package.

Runs hall_scene.py with non-default names and checks the manifest and scene: ids and the
city address come from the parameters, every quest giver is an NPC, every sound file is
written by hall_audio.py. The audio step is SKIPPED without numpy or ffmpeg.

The Blender step runs mission_hall.py with --quick and 4 samples (BLENDER=/path/to/blender,
on PATH or in ~/opt/blender-*; SKIPPED without it): it must write the five assets/*.glb the
scene names, the hall as baked unlit atlases, the collision mesh invisible-ready, the HALL
info with the eight booths and braziers, and a stand-in box for every prop (no --props).
Takes about a minute with a GPU for Cycles, a few minutes on a CPU.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

here = os.path.dirname(os.path.abspath(__file__))
ex = os.path.join(here, "..", "..", "examples", "mission_hall")
sys.path.insert(0, os.path.join(here, ".."))
from blender_tools_test import Glb, find_blender  # noqa: E402
tmp = tempfile.mkdtemp(prefix="mission_hall_test_")
pkg = os.path.join(tmp, "pkg")
try:
    city = "iamar://alice/town"
    out = subprocess.run([sys.executable, os.path.join(ex, "hall_scene.py"), pkg, "--city", city,
                          "--id", "guild_hall", "--owner", "alice", "--author", "Alice"],
                         check=True, capture_output=True, text=True).stdout
    assert out.startswith("SCENE 8 npcs"), out
    man = json.load(open(os.path.join(pkg, "manifest.json")))
    scene = json.load(open(os.path.join(pkg, "scene.json")))
    assert man["format"] == "iamar-world" and man["id"] == "guild_hall", man["id"]
    assert man["author"] == {"name": "Alice", "owner": "alice"}, man["author"]
    assert scene["format"] == "iamar-scene"
    text = open(os.path.join(pkg, "scene.json")).read() + open(os.path.join(pkg, "manifest.json")).read()
    addrs = set(re.findall(r'iamar://[A-Za-z0-9_./-]+', text))
    assert addrs == {city}, f"hard-coded world addresses: {addrs - {city}}"
    assert "iamar://local/oakhaven" not in text, "the default city leaked past --city"
    assert scene["portals"][0]["to"] == city + "#from_mission_hall"
    npc_ids = {n["id"] for n in scene["npcs"]}
    assert len(npc_ids) == 8
    for q in scene["quests"]:
        assert q["giver"] in npc_ids, q["id"]
    for o in scene["objects"]:
        assert o["asset"].startswith("assets/"), o
    assert len(scene["lights"]) <= man["budgets"]["lights"], len(scene["lights"])
    assert len(scene["objects"]) <= man["budgets"]["objects"]
    spawns = {s["id"] for s in scene["spawn_points"]}
    assert man["spawn"] in spawns
    sound_files = {s["file"] for s in scene["sounds"]}
    assert sound_files == {"audio/hall_ambience.ogg", "audio/brazier.ogg"}, sound_files

    if importlib.util.find_spec("numpy") is None or shutil.which("ffmpeg") is None:
        print("MISSION_HALL_AUDIO SKIPPED (needs numpy and ffmpeg)")
    else:
        subprocess.run([sys.executable, os.path.join(ex, "hall_audio.py"), pkg], check=True, capture_output=True)
        total = 0
        for f in sound_files:
            p = os.path.join(pkg, f)
            assert os.path.getsize(p) > 10000, p
            total += os.path.getsize(p)
        assert total <= man["budgets"]["audio_bytes"], total
    blender = find_blender()
    if blender is None:
        print("MISSION_HALL_BLENDER SKIPPED (no Blender: set BLENDER=/path/to/blender)")
    else:
        t0 = time.time()
        work = os.path.join(tmp, "work")
        r = subprocess.run([blender, "-b", "--factory-startup", "--python", os.path.join(ex, "mission_hall.py"),
                            "--", pkg, "4", "--quick", "--work", work],
                           capture_output=True, text=True, timeout=3600)
        log = r.stdout + r.stderr
        assert r.returncode == 0 and re.search(r"^HALL +[0-9.]+s done$", log, re.M), log[-3000:]
        assert "Traceback" not in log, log[-3000:]
        assets = {o["asset"] for o in scene["objects"]}
        for a in assets:
            assert os.path.getsize(os.path.join(pkg, a)) > 1000, a
        hall = Glb(os.path.join(pkg, "assets", "hall.glb"))
        mats = hall.js["materials"]
        assert len(hall.js["meshes"]) == 6 and len(mats) == 6, (len(hall.js["meshes"]), len(mats))
        assert all("KHR_materials_unlit" in m.get("extensions", {}) for m in mats), "hall not unlit"
        assert len(hall.js.get("images", [])) == 6, "one baked atlas per material"
        col = Glb(os.path.join(pkg, "assets", "hall_collision.glb"))
        assert sum(1 for _ in col.prims()) >= 1
        anims = {a["name"] for a in Glb(os.path.join(pkg, "assets", "flame.glb")).js.get("animations", [])}
        assert "flicker" in anims, anims
        anims = {a["name"] for a in Glb(os.path.join(pkg, "assets", "veil.glb")).js.get("animations", [])}
        assert "swirl" in anims, anims
        info = json.load(open(os.path.join(work, "hall_info.json")))
        assert len(info["braziers"]) == 8 and len(info["booths"]) == 8, info.keys()
        assert log.count("stand-in box") >= 20, "props without --props must become stand-in boxes"
        assert not os.path.exists(os.path.join(pkg, "build")), "scratch written into the package"
        print("MISSION_HALL_BLENDER ok %.0fs (%s)" % (time.time() - t0, os.path.basename(blender)))
    print("MISSION_HALL_TEST_OK")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
