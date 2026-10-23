#!/usr/bin/env python3
"""Checks kit/shots (iamar-world shots): fixed eye-height cameras, day/dusk/night patches of a
temporary world copy, review sheets with triangle and draw counts, budgets, failures and bad
input. The renderer is a stand-in (fake_preview.py), so no browser is needed:

    python3 kit/tests/shots/shots_test.py

With IAMAR_BROWSER (or GODOT and IAMAR_PROJECT) and IAMAR_KIT_PACK set it also renders the
desert trading post sample for real (kit/shots/samples/desert_post.shots.json); otherwise that
part reports SKIPPED. Review sheets need Pillow; without it those checks report SKIPPED.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
SHOTS = KIT / "shots" / "shots.py"
FAKE = HERE / "fake_preview.py"
DESERT = KIT / "lint" / "samples" / "desert_post"
CAMS = KIT / "shots" / "samples" / "desert_post.shots.json"
sys.path.insert(0, str(KIT / "shots"))
import shots  # noqa: E402


def tree_hash(d):
    h = hashlib.sha256()
    for p in sorted(Path(d).rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(d)).encode() + p.read_bytes())
    return h.hexdigest()


def main() -> int:
    checks = []

    try:
        import numpy  # noqa: F401
        have_np = True
    except ImportError:
        have_np = False

    def check(name, cond, detail=""):
        checks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (("  " + str(detail).strip()[-900:]) if detail and not cond else ""), flush=True)

    def check_np(name, cond, detail=""):
        """A check that needs numpy (what the edge cameras see): SKIPPED without it, as the tool itself skips."""
        if have_np:
            check(name, cond, detail)
        else:
            print("SKIPPED " + name + " (numpy missing)")

    try:
        import PIL  # noqa: F401
        have_pil = True
    except ImportError:
        have_pil = False

    tmp = Path(tempfile.mkdtemp(prefix="shots_test_"))
    log = tmp / "calls.jsonl"
    env = dict(os.environ, FAKE_PREVIEW_LOG=str(log))
    for k in ("FAKE_PREVIEW_PRIMS", "FAKE_PREVIEW_FAIL", "FAKE_PREVIEW_DROP"):
        env.pop(k, None)
    runner = json.dumps([sys.executable, str(FAKE)])

    def run(*args, extra=None):
        e = dict(env, **(extra or {}))
        return subprocess.run([sys.executable, str(SHOTS), *map(str, args), "--runner", runner],
                              capture_output=True, text=True, env=e)

    try:
        # a world with a cubemap-free procedural sky and a fixed sun direction
        world = tmp / "world"
        shutil.copytree(DESERT, world)
        scene = json.loads((world / "scene.json").read_text(encoding="utf-8"))
        scene["environment"] = {"time_of_day": 9.0, "sun": {"direction": [0.3, -1, 0.2], "energy": 1.2},
                                "ambient": {"color": "#666666", "energy": 0.8}, "exposure": 1.0}
        (world / "scene.json").write_text(json.dumps(scene), encoding="utf-8")
        before = tree_hash(world)

        # 1. the sample camera set: 3 cameras x day/dusk/night
        out = tmp / "out"
        p = run(world, out, "--cameras", CAMS)
        check("sample run exits 0", p.returncode == 0, p.stdout + p.stderr)
        rep = json.loads((out / "shots.json").read_text(encoding="utf-8")) if (out / "shots.json").is_file() else {}
        got = {(s["camera"], s["time"]) for s in rep.get("shots", [])}
        want = {(c, t) for c in ("arrival", "street", "house_a") for t in ("day", "dusk", "night")}
        check("9 shots, one per camera and time", got == want, sorted(got))
        check("raw shots named <camera>_<time>.png (compare-shots pairs them)",
              all((out / "shots" / ("%s_%s.png" % k)).is_file() for k in want))
        check("triangles, draws and objects recorded per shot",
              all(isinstance(s.get(k), int) for s in rep.get("shots", []) for k in ("triangles", "draws", "objects")))
        check("budget from the manifest (150000 triangles) and the camera file (150 draws)",
              all(s["budget"] == {"triangles": 150000, "draws": 150} for s in rep.get("shots", [])), rep.get("shots", [{}])[0].get("budget"))
        md = (out / "SHOTS.md").read_text(encoding="utf-8") if (out / "SHOTS.md").is_file() else ""
        check("SHOTS.md table lists every shot", md.count("\n| arrival |") == 3 and "| triangles |" in md, md[:400])
        if have_pil:
            from PIL import Image
            check("one review sheet per camera and time", all((out / "sheets" / ("%s_%s.png" % k)).is_file() for k in want))
            sh = Image.open(out / "sheets" / "street_dusk.png")
            check("a sheet is the shot plus a numbers band", sh.width == 960 and sh.height > 960 * 90 // 160, sh.size)
            cs = Image.open(out / "contact_sheet.png")
            check("contact sheet: 3 time columns x 3 camera rows", cs.width == 3 * 400 and cs.height > 3 * 200, cs.size)
        else:
            print("SKIPPED review sheets (Pillow missing)")

        # 2. eye height and aim: what the renderer was asked for
        calls = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
        check("one preview per time of day", len(calls) == 3, len(calls))
        v0 = calls[0]["views"][0]
        pos, look = (list(map(float, x.split(","))) for x in v0.split(">"))
        check("camera sits eye_height (1.7) above `at` [0, 0.1, 14]", math.isclose(pos[1], 1.8) and pos[0] == 0 and pos[2] == 14, v0)
        check("yaw 0 looks toward -Z", look[2] < pos[2] and abs(look[0] - pos[0]) < 1e-6, v0)
        v1 = calls[0]["views"][1]
        check("`look` is passed as the look-at point", v1.endswith(">-6.000,2.000,-18.000"), v1)
        check("tier high and the size are passed", calls[0]["opts"].get("--tier") == "high" and calls[0]["opts"].get("--size") == "1280x720", calls[0]["opts"])
        check("the launcher's whole-preview retry is off (shots retries missing views itself)",
              all(c.get("retry") == "0" for c in calls), [c.get("retry") for c in calls])
        check("no --quest-done unless asked (quests start as a visitor first sees them)", "--quest-done" not in calls[0]["opts"], calls[0]["opts"])

        # 3. the environment patches
        day, dusk, night = (c["environment"] for c in calls)
        check("day: time_of_day 13 and the fixed sun direction removed (time places the sun)",
              day["time_of_day"] == 13.0 and "direction" not in day["sun"] and day["sun"]["energy"] == 1.2, day)
        check("dusk: 17.6 h, warm sun, ambient scaled from the world's own 0.8",
              dusk["time_of_day"] == 17.6 and dusk["sun"]["color"] == "#ffb27a" and math.isclose(dusk["ambient"]["energy"], 0.56), dusk)
        check("night: 22.5 h, ambient 0.3 x 0.8, exposure 0.9, dark procedural sky",
              night["time_of_day"] == 22.5 and math.isclose(night["ambient"]["energy"], 0.24) and math.isclose(night["exposure"], 0.9)
              and night.get("sky", {}).get("top_color") == "#070b1c", night)
        check("the world folder itself is unchanged", tree_hash(world) == before)

        # a cubemap sky is the world's choice: not recoloured at night
        cube = tmp / "cube"
        shutil.copytree(world, cube)
        sc = json.loads((cube / "scene.json").read_text(encoding="utf-8"))
        sc["environment"]["sky"] = {"type": "cubemap", "faces": {}}
        (cube / "scene.json").write_text(json.dumps(sc), encoding="utf-8")
        log.write_text("", encoding="utf-8")
        p = run(cube, tmp / "out_cube", "--cameras", CAMS, "--times", "night")
        env_n = json.loads(log.read_text(encoding="utf-8").splitlines()[0])["environment"] if p.returncode == 0 else {}
        check("--times night renders only night; a cubemap sky keeps its own colours",
              p.returncode == 0 and env_n.get("sky") == {"type": "cubemap", "faces": {}}, p.stdout + p.stderr)

        check("night: a world with no fog gets no fog", "fog" not in night, night)

        # night fog: a light day fog is blended toward the night sky (an internal task)
        foggy = tmp / "foggy"
        shutil.copytree(world, foggy)
        sc = json.loads((foggy / "scene.json").read_text(encoding="utf-8"))
        sc["environment"]["fog"] = {"enabled": True, "color": "#dfe2e4", "density": 0.0022}
        (foggy / "scene.json").write_text(json.dumps(sc), encoding="utf-8")
        log.write_text("", encoding="utf-8")
        p = run(foggy, tmp / "out_fog", "--cameras", CAMS, "--times", "day,night")
        envs = [json.loads(l)["environment"] for l in log.read_text(encoding="utf-8").splitlines()] if p.returncode == 0 else [{}, {}]
        fd, fn = envs[0].get("fog", {}), envs[1].get("fog", {})
        lum = lambda h: sum(int(h[i:i + 2], 16) for i in (1, 3, 5)) / 3
        check("night fog is tinted toward the night sky (#dfe2e4 -> #383e59), day fog unchanged, density kept",
              fd.get("color") == "#dfe2e4" and fn.get("color") == "#383e59" and lum(fn["color"]) < 100
              and fn.get("density") == 0.0022, p.stdout + p.stderr + str(envs))
        sc["environment"]["fog"] = {"density": 0.01}   # on by presence, browser default colour
        (foggy / "scene.json").write_text(json.dumps(sc), encoding="utf-8")
        cams3 = json.loads(CAMS.read_text(encoding="utf-8"))
        cams3["times"] = ["night", "moon"]
        cams3["time_presets"] = {"moon": {"time_of_day": 23, "fog_tint": {"color": "#000000", "amount": 0.5}}}
        (tmp / "c3.json").write_text(json.dumps(cams3), encoding="utf-8")
        log.write_text("", encoding="utf-8")
        p = run(foggy, tmp / "out_fog2", "--cameras", tmp / "c3.json")
        envs = [json.loads(l)["environment"] for l in log.read_text(encoding="utf-8").splitlines()] if p.returncode == 0 else [{}, {}]
        check("fog with no colour is tinted from the browser default; a time_presets fog_tint works",
              envs[0].get("fog", {}).get("color") == "#343c58" and envs[1].get("fog", {}).get("color") == "#646a70",
              p.stdout + p.stderr + str(envs))
        sc["environment"]["fog"] = {"enabled": False, "color": "#dfe2e4"}
        (foggy / "scene.json").write_text(json.dumps(sc), encoding="utf-8")
        cams3["time_presets"] = {"moon": {"time_of_day": 23}, "night": {"fog_tint": None}}
        (tmp / "c3.json").write_text(json.dumps(cams3), encoding="utf-8")
        log.write_text("", encoding="utf-8")
        p = run(foggy, tmp / "out_fog3", "--cameras", tmp / "c3.json", "--times", "night")
        envs = [json.loads(l)["environment"] for l in log.read_text(encoding="utf-8").splitlines()] if p.returncode == 0 else [{}]
        check("disabled fog is left alone (and fog_tint: null drops the tint)", envs[0].get("fog", {}).get("color") == "#dfe2e4", p.stdout + p.stderr + str(envs))
        # every html form the browser's Color(String) reads is tinted; alpha stays (an internal task)
        night_tint = shots.PRESETS["night"]["fog_tint"]
        forms = {c: shots.tint_fog({"fog": {"enabled": True, "color": c}}, night_tint)["fog"]["color"]
                 for c in ("#dfe2e4", "dfe2e4", "#ddd", "#dfe2e480")}
        check("fog_tint reads #rgb, #rrggbbaa and no-# hex like the browser (alpha kept)",
              forms == {"#dfe2e4": "#383e59", "dfe2e4": "#383e59", "#ddd": "#373d58", "#dfe2e480": "#383e5980"}, forms)
        named = subprocess.run([sys.executable, "-c", "import shots; print(shots.tint_fog("
                                "{'fog': {'enabled': True, 'color': 'lightgray'}}, shots.PRESETS['night']['fog_tint']))"],
                               cwd=KIT / "shots", capture_output=True, text=True)
        check("a named fog colour is left as it is, with a NOTE", "lightgray" in named.stdout
              and "NOTE shots: fog_tint not applied" in named.stderr, named.stdout + named.stderr)

        # own presets from the camera file
        cams2 = json.loads(CAMS.read_text(encoding="utf-8"))
        cams2["times"] = ["day", "rain"]
        cams2["time_presets"] = {"rain": {"time_of_day": 15, "fog": {"enabled": True, "density": 0.03}}, "day": {"time_of_day": 11}}
        (tmp / "c2.json").write_text(json.dumps(cams2), encoding="utf-8")
        log.write_text("", encoding="utf-8")
        p = run(world, tmp / "out2", "--cameras", tmp / "c2.json")
        envs = [json.loads(l)["environment"] for l in log.read_text(encoding="utf-8").splitlines()]
        check("time_presets add a time and refine a built-in one",
              p.returncode == 0 and envs[0]["time_of_day"] == 11 and "direction" not in envs[0]["sun"]
              and envs[1]["fog"]["density"] == 0.03, p.stdout + p.stderr + str(envs))

        # 4. budgets
        n = len(log.read_text(encoding="utf-8").splitlines())
        p = run(world, tmp / "out_qd", "--cameras", CAMS, "--times", "night", "--quest-done", "water_for_the_driver")
        qd = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()][n:]
        check("--quest-done is passed to the preview", p.returncode == 0 and len(qd) == 1
              and qd[0]["opts"].get("--quest-done") == "water_for_the_driver", (p.stderr[-300:], qd))
        p = run(world, tmp / "out3", "--cameras", CAMS, "--times", "day", extra={"FAKE_PREVIEW_PRIMS": "200000"})
        check("over the triangle budget: reported OVER, exit 0 without --strict", p.returncode == 0 and "OVER triangles" in p.stdout, p.stdout)
        p = run(world, tmp / "out3", "--cameras", CAMS, "--times", "day", "--strict", extra={"FAKE_PREVIEW_PRIMS": "200000"})
        check("--strict fails a shot over budget", p.returncode == 1, p.stdout)

        # 5. render failures are errors, never silent gaps
        p = run(world, tmp / "out4", "--cameras", CAMS, "--times", "day", extra={"FAKE_PREVIEW_FAIL": "1"})
        r4 = json.loads((tmp / "out4" / "shots.json").read_text(encoding="utf-8"))
        check("a failed preview exits 1 and is recorded", p.returncode == 1 and "day" in r4["errors"], p.stdout + p.stderr)
        p = run(world, tmp / "out5", "--cameras", CAMS, "--times", "day", "--retries", "0", extra={"FAKE_PREVIEW_DROP": "1"})
        check("a missing view exits 1 (2 of 3 rendered)", p.returncode == 1 and "2 of 3 views" in p.stderr, p.stderr)
        log.write_text("", encoding="utf-8")
        p = run(world, tmp / "out5r", "--cameras", CAMS, "--times", "day", extra={"FAKE_PREVIEW_DROP": "1"})
        calls = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
        check("a missing view is rendered again, alone, and the run passes",
              p.returncode == 0 and [len(c["views"]) for c in calls] == [3, 1] and calls[1]["views"][0] == calls[0]["views"][1]
              and len(list((tmp / "out5r" / "shots").glob("*_day.png"))) == 3, p.stdout + p.stderr)
        p = run(world, tmp / "out6", "--cameras", CAMS, "--times", "day", extra={"FAKE_PREVIEW_EXIT": "139"})
        r6 = json.loads((tmp / "out6" / "shots.json").read_text(encoding="utf-8"))
        check("a crash on exit after every view was written keeps the shots (exit 0, NOTE)",
              p.returncode == 0 and len(r6["shots"]) == 3 and not r6["errors"] and "crash on exit" in p.stderr, p.stdout + p.stderr)
        log.write_text("", encoding="utf-8")
        p = run(world, tmp / "out7", "--cameras", CAMS, "--times", "day,dusk,night", extra={"FAKE_PREVIEW_CRASH_ONCE": str(tmp / "crashed")})
        r7 = json.loads((tmp / "out7" / "shots.json").read_text(encoding="utf-8"))
        check("a time of day whose renderer crashed is rendered again: 9 of 9, exit 0",
              p.returncode == 0 and len(r7["shots"]) == 9 and len(log.read_text(encoding="utf-8").splitlines()) == 4, p.stdout + p.stderr)
        p = run(world, tmp / "out8", "--cameras", CAMS, "--times", "day", "--retries", "0", extra={"FAKE_PREVIEW_EXIT": "1", "FAKE_PREVIEW_DROP": "0"})
        check("a crash that lost a view still fails", p.returncode == 1 and "2 of 3 views" in p.stderr, p.stderr)
        if have_pil:
            check("the contact sheet marks the missing shot", (tmp / "out5" / "contact_sheet.png").is_file())

        # 6. bad input
        bad = json.loads(CAMS.read_text(encoding="utf-8"))
        bad["cameras"].append(dict(bad["cameras"][0]))
        (tmp / "dup.json").write_text(json.dumps(bad), encoding="utf-8")
        p = run(world, tmp / "o", "--cameras", tmp / "dup.json")
        check("duplicate camera names: exit 2", p.returncode == 2 and "unique" in p.stderr, p.stderr)
        for label, cam in (("no at", {"name": "x", "yaw": 0}), ("bad name", {"name": "a b", "at": [0, 0, 0]}),
                           ("looks at itself", {"name": "x", "at": [0, 0, 0], "look": [0, 1.7, 0]}),
                           ("pitch 90", {"name": "x", "at": [0, 0, 0], "pitch": 90})):
            (tmp / "b.json").write_text(json.dumps({"cameras": [cam]}), encoding="utf-8")
            p = run(world, tmp / "o", "--cameras", tmp / "b.json")
            check("bad camera (%s): exit 2" % label, p.returncode == 2, p.stderr)
        p = run(world, tmp / "o", "--cameras", CAMS, "--times", "day,teatime")
        check("unknown time name: exit 2", p.returncode == 2 and "teatime" in p.stderr, p.stderr)
        p = run(world, tmp / "o")
        check("no camera set: exit 2 and points to --init", p.returncode == 2 and "--init" in p.stderr, p.stderr)
        p = run(world, world / "shots_out", "--cameras", CAMS)
        check("output inside the world folder: exit 2", p.returncode == 2 and not (world / "shots_out").exists(), p.stderr)

        # 7. --init writes a starter camera set from the spawn points
        p = run(world, "--init")
        sj = json.loads((world / "shots.json").read_text(encoding="utf-8")) if (world / "shots.json").is_file() else {}
        names = [c["name"] for c in sj.get("cameras", [])]
        check("--init: one camera per spawn point plus the view back, then one edge_* camera per side",
              p.returncode == 0 and names == ["default", "default_back", "edge_north", "edge_south", "edge_west", "edge_east"],
              p.stdout + p.stderr)
        p = run(world, "--init")
        check("--init never overwrites", p.returncode == 2, p.stderr)
        p = run(world, tmp / "out6", "--times", "day")
        check("the world's own shots.json is the default camera set", p.returncode == 0 and "6 of 6 rendered" in p.stdout, p.stdout + p.stderr)

        # 7b. temp dir: --tmp is used; an unwritable one is one ERROR line, exit 1
        bad_tmp = tmp / "not_a_dir"
        bad_tmp.write_text("x", encoding="utf-8")   # a file, so nothing can be made inside it
        p = run(world, tmp / "out_bad_tmp", "--times", "day", "--tmp", bad_tmp)
        check("unwritable --tmp: exit 1, one ERROR line, no traceback",
              p.returncode == 1 and "ERROR shots" in p.stderr and "Traceback" not in p.stderr, p.stdout + p.stderr)
        good_tmp = tmp / "mytmp"
        good_tmp.mkdir()
        p = run(world, tmp / "out_good_tmp", "--times", "day", "--tmp", good_tmp)
        check("--tmp folder works and is cleaned up", p.returncode == 0 and not any(good_tmp.iterdir()), p.stdout + p.stderr)

        # 7c. --edges: every side of the playable area needs an outward eye-height camera
        ew = tmp / "edgeworld"
        ew.mkdir()
        (ew / "manifest.json").write_text(json.dumps({"name": "edges", "scene": "scene.json"}), encoding="utf-8")
        esc = {"terrain": {"type": "flat", "position": [0, 0.5, 0], "materials": [{"color": "#6b8c40"},
                                                                               {"texture": "t.jpg", "min_height": 2}]},
               "spawn_points": [{"id": "s", "position": [0, 0, 0], "yaw": 0}],
               "objects": [{"id": "a", "asset": "a.glb", "position": [-30, 0, -20]},
                           {"id": "b", "asset": "b.glb", "position": [30, 0, 20]}],
               "primitives": [{"id": "sea", "shape": "box", "size": [400, 1, 400], "position": [0, -1, 0]},
                              {"id": "wall_n", "shape": "box", "size": [90, 4, 1], "position": [0, 2, -24]},
                              {"id": "wall_s", "shape": "box", "size": [90, 4, 1], "position": [0, 2, 24]},
                              {"id": "wall_w", "shape": "box", "size": [1, 4, 60], "position": [-34, 2, 0]},
                              {"id": "wall_e", "shape": "box", "size": [1, 4, 60], "position": [34, 2, 0]}]}
        (ew / "scene.json").write_text(json.dumps(esc), encoding="utf-8")
        ecams = {"cameras": [{"name": "in", "at": [0, 0, 0], "yaw": 0},
                             {"name": "high_east", "at": [28, 0, 0], "yaw": 270, "eye_height": 40},
                             {"name": "mid_east", "at": [0, 0, 0], "look": [100, 2, 0]}]}
        (ew / "shots.json").write_text(json.dumps(ecams), encoding="utf-8")
        p = run(ew, "--edges")
        check("--edges: inward, aerial and far-inside cameras do not count; exit 1 naming all four sides",
              p.returncode == 1 and "edges: MISSING north,south,west,east" in p.stdout, p.stdout + p.stderr)
        check("--edges: the sea plane is not part of the playable area", "x -30.0..30.0, z -20.0..20.0" in p.stdout, p.stdout)
        check("--edges: a flat-colour terrain band is a NOTE, a textured one is not",
              p.stdout.count("NOTE edge: terrain band") == 1 and "#6b8c40" in p.stdout, p.stdout)
        ecams["cameras"].append({"name": "east_look", "at": [26, 0, 3], "look": [80, 3, 20]})
        (ew / "shots.json").write_text(json.dumps(ecams), encoding="utf-8")
        p = run(ew, "--edges")
        check("--edges: a camera near the east side looking out covers it", "EDGE east  ok      east_look" in p.stdout
              and "edges: MISSING north,south,west\n" in p.stdout, p.stdout + p.stderr)
        p = run(ew, "--edges", "--add")
        sj = json.loads((ew / "shots.json").read_text(encoding="utf-8"))
        added = {c["name"]: c for c in sj["cameras"] if c["name"].startswith("edge_")}
        check("--edges --add: appends edge_north/south/west at a placed thing, on the ground, looking out; exit 0",
              p.returncode == 0 and sorted(added) == ["edge_north", "edge_south", "edge_west"]
              and added["edge_west"]["at"] == [-30.0, 0.5, -20.0] and added["edge_west"]["yaw"] == 90.0
              and added["edge_north"]["yaw"] == 0.0 and added["edge_south"]["yaw"] == 180.0, p.stdout + p.stderr + json.dumps(added))
        p = run(ew, "--edges")
        check("--edges after --add: exit 0, edges: ok", p.returncode == 0 and "edges: ok" in p.stdout, p.stdout + p.stderr)
        # what the edge cameras see: a bare view fails, at the judged tier; water is not bare
        walls = esc["primitives"]
        esc["primitives"] = [walls[0], walls[1], walls[2], walls[3]]   # no east wall: open ground
        (ew / "scene.json").write_text(json.dumps(esc), encoding="utf-8")
        p = run(ew, "--edges")
        check_np("--edges: a side whose cameras see mostly open ground is BARE (exit 1)",
              p.returncode == 1 and "EDGE east  BARE    east_look sees" in p.stdout and "edges: BARE east\n" in p.stdout,
              p.stdout + p.stderr)
        esc["primitives"] = walls[:4] + [dict(walls[4], min_tier="medium")]
        (ew / "scene.json").write_text(json.dumps(esc), encoding="utf-8")
        p = run(ew, "--edges")
        check_np("--edges: a wall with min_tier medium is not there at tier low (BARE east)",
              p.returncode == 1 and "edges: BARE east\n" in p.stdout, p.stdout + p.stderr)
        p = run(ew, "--edges", "--tier", "medium")
        check_np("--edges --tier medium: the same wall closes the view (exit 0)",
              p.returncode == 0 and "EDGE east  view    east_look" in p.stdout and "edges: ok" in p.stdout, p.stdout + p.stderr)
        esc["primitives"] = walls[:4]
        esc["water"] = [{"id": "bay", "position": [100, 0.6, 0], "size": [140, 200]}]
        (ew / "scene.json").write_text(json.dumps(esc), encoding="utf-8")
        p = run(ew, "--edges")
        check("--edges: a view over water is not bare ground (exit 0)", p.returncode == 0 and "edges: ok" in p.stdout,
              p.stdout + p.stderr)
        esc.pop("water")
        esc["primitives"] = walls
        a4 = KIT / "blindtest" / "harbour"
        if (a4 / "world" / "scene.json").is_file() and (a4 / "review-a4" / "cams.json").is_file():
            p = run(a4 / "world", "--edges", "--cameras", a4 / "review-a4" / "cams.json")
            check_np("--edges on harbour a4 with the reviewer's cameras (review: bare north, dressed east): north BARE, "
                  "east not", p.returncode == 1 and "EDGE north BARE    r_edge_north sees 97%" in p.stdout
                  and "EDGE east  view    r_edge_east sees 16%" in p.stdout, p.stdout + p.stderr)
        esc["objects"] = []   # the spawn point alone
        (ew / "scene.json").write_text(json.dumps(esc), encoding="utf-8")
        p = run(ew, "--edges")
        check("--edges: a world of one place is bad input (exit 2)", p.returncode == 2 and "ERROR shots" in p.stderr, p.stdout + p.stderr)
        harbour = KIT / "blindtest" / "harbour" / "attempt-3" / "world"
        if harbour.is_dir():
            hb = tree_hash(harbour)
            p = run(harbour, "--edges")
            check_np("--edges on harbour attempt 3 (review FAIL: bare east edge) fails on east and south, world unchanged",
                  p.returncode == 1 and "edges: MISSING south,east" in p.stdout and tree_hash(harbour) == hb, p.stdout + p.stderr)

        # 8. merge rules
        m = shots.merge({"a": 1, "b": {"c": 2, "d": 3}, "e": 2.0}, {"a": None, "b": {"d": None, "f": 4}, "e_scale": 0.5, "g_scale": 2})
        check("merge: null removes, nested merge, _scale multiplies (default 1)", m == {"b": {"c": 2, "f": 4}, "e": 1.0, "g": 2}, m)

        # washed-out frames: near-white ground WARNs (day, dusk) and is recorded; normal shots do not
        if have_pil:
            p = run(world, tmp / "out_white", "--cameras", CAMS, "--times", "day,night", extra={"FAKE_PREVIEW_WHITE": "1"})
            rw = json.loads((tmp / "out_white" / "shots.json").read_text(encoding="utf-8"))["shots"]
            check("near-white day shots are flagged washed_out, night is not measured",
                  p.returncode == 0 and all(s["washed_out"] for s in rw if s["time"] == "day")
                  and all("washed_out" not in s for s in rw if s["time"] == "night"), p.stdout + p.stderr)
            check("a WARN names the camera on stderr and SHOTS.md", "WARN shots arrival day: washed out" in p.stderr
                  and "WARN washed out" in (tmp / "out_white" / "SHOTS.md").read_text(encoding="utf-8"), p.stderr)
            check("a normal day render is not washed out", not any(s.get("washed_out") for s in rep["shots"])
                  and "WARN washed out" not in md, [s.get("ground_near_white") for s in rep["shots"]])
        else:
            print("SKIPPED washed-out check (Pillow missing)")

        # 9. a real render, when a browser and the kit pack are available
        has_browser = bool(os.environ.get("IAMAR_BROWSER") or (os.environ.get("GODOT") and os.environ.get("IAMAR_PROJECT")))
        if has_browser and os.environ.get("IAMAR_KIT_PACK"):
            real = tmp / "real"
            r = subprocess.run([sys.executable, str(SHOTS), str(DESERT), str(real), "--cameras", str(CAMS),
                                "--size", "640x360", "--frames", "10", "--timeout", "600"], capture_output=True, text=True)
            rr = json.loads((real / "shots.json").read_text(encoding="utf-8")) if (real / "shots.json").is_file() else {"shots": []}
            check("real render: 9 shots of the desert sample, every one with geometry",
                  r.returncode == 0 and len(rr["shots"]) == 9 and all(s["triangles"] > 0 and s["draws"] > 0 for s in rr["shots"]),
                  r.stdout + r.stderr)
        else:
            print("SKIPPED real render (set IAMAR_BROWSER or GODOT+IAMAR_PROJECT, and IAMAR_KIT_PACK)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    n_fail = checks.count(False)
    print("RESULT %s: %d checks, %d failed" % ("ok" if n_fail == 0 else "FAIL", len(checks), n_fail))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
