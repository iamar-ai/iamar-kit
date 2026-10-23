# Statue v4: concept picture to game statue (GPU tier, whole-statue UltraShape refine)

Swarm project `iamar-creator-knowledge`, job P5c (3240). Packaged from the city's statue workflow
(the iamar-models mesh archive (not public) `tools/mesh3d/statue_v4`, at af19688), which made the South Gate mage, the winged
sorceress and the Elven King (about 10.5k to 11.9k triangles each, `qa_statue` PASS). the maintainer 2026-10-19:
"the closest option so far". Use it for hero statues and figures whose face must hold up close; for props and
simpler shapes, `kit/gpu/sculpt.py` (one generated surface, one cage) is enough.

```
picture --sculpt.py cutout--> RGBA --sculpt.py shape (Hunyuan3D-2.1)--> coarse surface (cut the base off)
        --statue.py refine (UltraShape 1.0, GPU)--> refined surface, 3-9M faces
        --statue.py chain--> prep -> joint thinning -> split cage -> bake -> relight -> dilate -> seam blend -> QA
        --> out/<name>.gltf + .bin + _albedo.png + _normal.png, run.json (triangles, QA, feet centre, height)
```

Nothing is installed into a game or a world: copy `out/*` into your world's assets and place it by the feet
centre (below). Every step's output stays in the work folder; delete it when the statue is done.

## Commands

| # | Step | Command | Runs on | What to check |
|---|---|---|---|---|
| 1 | Cut-out | `sculpt.py cutout concept.png x_rgba.png --plinth-row N` | CPU | remove the drawn plinth rows below the boots, or the refine invents a floating disc (mage: 868); subject about 820 px on 1024. A face under about 25 px gives a blobby face: enlarge the head first |
| 2 | Coarse | `sculpt.py shape x_rgba.png x_coarse.glb --region CC`, then strip its base | GPU 17 GB | the base strip only feeds the refine; the refined mesh keeps its own soles |
| 3 | Refine | `statue.py refine x_rgba.png x_coarse.glb out/refine --us-repo DIR --ckpt FILE --region CC [--mem-cap 18G]` | GPU about 19 GB | about 10 minutes; output `out/refine/x_rgba_refined.glb`, 3-9M faces in the coarse mesh's frame |
| 4 | Look | `kit/blender/look.py` on the refined surface (front, side, top; slab views of the lowest 0.3) | CPU | decide: parts to remove (`BOXES`), the face oval, where the soles are. Locate lumps by views, never by guessed coordinates |
| 5 | Chain | `statue.py chain work/x out/refine/x_rgba_refined.glb --name x --nb 3300 --nh 2400 --nf 4800 FCX=.. FCZ=.. FRXL=.. FRXR=.. FRZ=..` | CPU (Blender, Cycles GPU if present) | `STATUE_OK`; `run.json` triangles per part and `qa: ok`. A QA FAIL stops with exit 1 |
| 5b | Face UV axis | `statue.py uv-search work/x --fdir DEG --fgx X --fgz Z [face params]` | CPU | after one chain run: tries face-only projection axes on the cage (no bake), writes `best_axis.env`; pass its `FCYLX FCYLZ FCYLR` to the next chain |
| 6 | Judge | in the world preview at playing distance and close (`kit/review/REVIEWER.md`) | | feet whole and centred, no rock or lump, face and neck one even tone, no streaks on folds, thin parts intact |

The chain's scripts (`stages/`, unchanged from the city apart from line endings, plus `feet.py`):

| Order | Script | Runs in | Does |
|---|---|---|---|
| 1 | `prep_full.py` | Blender | sole slab cut and cap, removal boxes, loose bits, face oval tagged as material `head` |
| 2 | `predec_joint.py` | Python | thins face and body welded (no rim crack) |
| 3 | `lowsplit3.py` | Python | split cage at the three budgets, one face and one neck chart, atlas |
| 4 | `bake_split_env.py` | Blender Cycles | tangent normal map and sky occlusion from the refined surface |
| 5 | `relight.py` | Python | face and neck lift, albedo from the occlusion |
| 6 | `dilate_nn.py` | Python | nearest-texel fill outside the charts and of unbaked texels |
| 7 | `seam_blend.py` | Python | colour steps at chart borders pulled together |
| 8 | `feet.py` | Python | feet centre and height for placing |
| 9 | `qa_statue.py` | Python | the automatic QA below; `qa_uv.py` is the fast face-UV score used by `uv-search` |

`statue.py check` says what this computer can run (`STEP refine`, `STEP chain`, each with its fallback), and
`statue.py chain ... --combo work/x/combo.glb` reruns everything after the slow prep with new parameters.

## Parameters (KEY=VAL after the command; all in the refined mesh's frame)

The refined mesh is normalised to about -1..1. Blender frame: x right, y back (the face looks toward -y),
z up; glb/Godot frame: x, y up, z = -Blender y. The defaults are the mage's; every new statue needs its own
face oval.

| Group | Keys | Meaning (city values) |
|---|---|---|
| Face oval | `FCX FCY FCZ FRXL FRXR FRZ FYAW` | centre (Blender x, y, z) and radii of the oval tagged as the face (mage FCX=0.059 FCZ=0.615 FRXL=0.064 FRXR=0.084 FRZ=0.086). Widen the side that leaves a sliver of skin outside; too wide stretches hair into stripes. `FYAW` turns the frame for a head in profile |
| Clean-up | `SOLE CAPH BOXES LOOSE FZCUT MAGE_CLEAN` | thin slab above the lowest point removed and capped (0.028); removal boxes `x0,x1,y0,y1,z0,z1;...`; loose bits under a share of the largest piece (0.003). `MAGE_CLEAN=1` only reproduces the mage |
| Budgets | `--nb --nh --nf`, `--nf-pre --nb-pre` | body, hat+hair, face triangles (mage 3300/2400/4800; king 3600/4400/3900); thinning targets before the cut (14000/160000) |
| Groups | `--collar --head-x0 --head-x1` | hat+hair = body above the collar height inside the x range (glb; 0.575, -0.75, 0.40) |
| Neck | `NECKX NECKY0 NECKY1 NECKR NECKZC NECKZR NECKCYL` | the neck box that gets one cylindrical chart |
| UV | `CYLX CYLZ CYLR`, `FCYLX FCYLZ FCYLR`, `FACEUV=arap`, `SELDEC=1`, `MAXCOST NDW` | cylinder axis for face and neck; a face-only axis (from `uv-search`); ARAP relax of the face chart; thin each group as a selection (hair with many strand edges) |
| Bake | `--size`, `EXT RAY` | texture size (2048); cage extrusion and ray distance as a share of the size (0.02 / 0.05) |
| Relight | `--lift`, `RX0 RX1 RY0 RY1 RZ0 RZ1 FEATHER DESAT` | the box round face and neck whose occlusion is lifted to flat stone (glb), feather, shadow desaturation |
| Seams | `--seam-r` | texels over which the colour step at chart borders fades (6) |

## Hardware and install

Measured in the city (the GPU host: RTX A5000 24 GB, 32 GB RAM, Linux, torch 2.5.1 cu124):

| Step | GPU memory | RAM | Time | Disk |
|---|---|---|---|---|
| refine (UltraShape 1.0, 50 steps, octree 1024) | **about 19 GB** | ran under a cap of **18 GB, no swap**, only with the fp16 patch (the stock fp32 CPU build is killed at 18 GB) | about 10 min | install with checkpoint about 10 GB |
| chain on a 3-9M-face surface | Cycles GPU optional | up to about 8 GB in the prep | minutes | |
| chain on the test stand-in (115k faces, 512 px) | none needed | under 2 GB | about 60 s on a laptop (Zoe) | |

`statue.py check` refuses the refine below 19 GB of GPU memory (total or free), with less than 18 GB of RAM
available, without the patched script, the checkpoint, torch with CUDA, `omegaconf`, `trimesh` or `cubvh`,
and outside the licence territory. Only a 24 GB card was measured.

Install (Linux; ask the user first, about 10 GB): clone `PKU-YuanGroup/UltraShape-1.0` into `D/repo` and `git -C D/repo checkout 5e8dcef05df101ab00ab6cd5fdd0ed0c74fbca66`
(the pin in `kit/gpu/pins.json`; `statue.py check` refuses another commit); make a venv with `--system-site-packages` on top of the Hunyuan3D-2.1 environment
(`kit/gpu/README.md`); `pip install -r requirements.txt` without flash_attn, deepspeed, sageattention, diso,
ipywidgets, pythreejs, wandb and tensorboard; `pip install git+https://github.com/ashawkey/cubvh@de1badf89b54975d407c42a02a47d41fa149e486 --no-build-isolation`
(set `TORCH_CUDA_ARCH_LIST` to your card, 8.6 for Ampere); a prebuilt flash_attn wheel matching torch
(city: `flash_attn-2.7.4.post1+cu12torch2.5cxx11abiFALSE-cp310`); weights:
`huggingface_hub.snapshot_download("infinith/UltraShape", revision="5aeb21a7185d39f042d02b2695802f125a6f5159", local_dir="D/checkpoints")`
(`check` compares the checkpoint's size with the pin and `refine` its sha256, because the patched script unpickles it; the patch loads it
with `weights_only=True`, which refuses code objects in the file). Then
`statue.py patch --us-repo D/repo` writes `scripts/infer_fp16.py` into YOUR clone (the kit ships no
UltraShape code; the patched file carries the licence's modification notice). The chain needs Blender 4.2+ and
`numpy scipy pillow trimesh pymeshlab xatlas` in `--python` / `IAMAR_STATUE_PYTHON`. Settings:
`ULTRASHAPE_REPO`, `ULTRASHAPE_CKPT` (default `D/checkpoints/ultrashape_v1.pt`), `IAMAR_REGION`, `BLENDER`.

## Licences (read before step 3)

| Tool | Licence | Limits |
|---|---|---|
| UltraShape 1.0 (code and weights, built on Hunyuan3D 2.1) | Tencent Hunyuan 3D 2.1 Community License (its repository's LICENSE, read 2026-10-20 at 5e8dcef) | as Hunyuan3D-2.1: **no use, distribution or display of the output in the EU, the UK or South Korea** (s.5c); over 1M monthly users needs a Tencent licence (s.4); output must not train other AI models (s.5b); modified files carry a notice (s.3b, done by `patch`); distributions carry the licence and a Notice file (s.3a/3d); products made with it are encouraged to be labelled as such (s.3c) |
| Hunyuan3D-2.1 (the coarse step) | the same licence | see `kit/gpu/README.md` |
| Blender, pymeshlab, xatlas, trimesh | GPL-2.0+ / GPL-3.0 / MIT / MIT | tools only, never bundled; output is yours |

`statue.py refine` refuses without a region and in the EU, the UK or South Korea (exit 3). Record each statue's
licence as `Tencent Hunyuan 3D 2.1 Community License (output)` in the world's `THIRD_PARTY_NOTICES.txt` and the
catalogue entry; label a world that shows it ("made with Tencent Hunyuan 3D"). Weights are never copied into
the kit, a world or a package.

## Fallbacks

| Missing | Fallback |
|---|---|
| a 19 GB+ NVIDIA GPU, the install, or a licensed region | run `chain` on the coarse Hunyuan3D-2.1 surface (softer detail, same face and neck handling); or `sculpt.py cage`/`game`; or Tier 0: a catalogue statue (`iamar-world assets search statue`) or a Blender model |
| the chain's Python modules or Blender | install them; the chain runs on CPU on any computer |

## Placing the statue

`run.json` `placement`: `feet_center` (x, z of the soles: the median of the lowest 6% of the vertices) and
`height` (model units). Scale = wanted height in metres / `height`; offset by `-feet_center` so the soles sit on
the plinth centre. Never centre by the bounding box: a staff or a cloak moves it off the plinth. The city's own
placement (`mp_statues.gd` `fit_height`, `feet_center`, stone shader `relief` about 0.4) is the same idea.

## QA (`stages/qa_statue.py`, run by the chain)

Face texture seams with a colour jump (over 0.10 long fails), face UV crushed (over 6% of the face area under a
quarter of the median texel density) or folded (over 15%), a second shell within 1.2 cm behind the face skin
(over 4% of samples), black texels inside charts (over 0.2%), more than 8 floating pieces, cracks (open edges)
round the face longer than 0.02, and fewer than 200 triangles inside the face oval (a wrong oval would make the
check vacuous). `--qa-force` keeps going after a FAIL; do not ship such a statue.

## Lessons from the city (do not repeat)

- Face budgets of 4.8k, 12k and 24k looked the same in the game: the game shows what the high surface holds.
- Brown streaks on folds = the stone shader's relief tint at 1.0 (use about 0.4). Dark bleed at chart borders =
  a hatched background fill: `dilate_nn.py` fills with the nearest real texel, also the unbaked black ones inside.
- xatlas cuts a face into 100+ charts whatever its options: the face and the neck each get one cylindrical chart
  (`use_input_mesh_uvs`); a protruding nose is crushed by an axis far behind the face: give the face its own axis
  (`uv-search`); an axis nearer the face folded 31% of the UV. `FACEUV=arap` relaxes brow and nose underside.
- Never cut near the soles: a fixed cut chopped the boots and left them hollow; use the thin `SOLE` slab and cap.
- A face rim crack (dark jagged line) came from thinning face and body apart: `predec_joint.py` thins them
  welded. Dead ends: quality-weighted collapse, a selected-only face pass, a rim band with both edges locked,
  locking every open edge, one unlocked joint pass from twice the budget.
- Each chart bakes on its own, so charts meet with a colour step: `seam_blend.py` (sorceress 0.459 -> 0.054).
- With every group border locked the king's hair could not go under 3.9k: `SELDEC=1`.
- Remaining flaws seen on city statues: closed-slit eyes (a sharper face needs a separate head-crop refine baked
  onto the face), a crack where face and hair charts meet at the temples, small bright triangles under the chin.
- Judged in the real city at FOV 12 (2026-10-20, mp-RV), the sorceress v5 and king v6 faces still showed
  cracks: always judge close-ups in the world, not only the QA.

## Test

`python3 kit/tests/gpu_statue/statue_test.py` (any computer; the chain part needs Blender 4.2+ and the Python
modules, about 60 s): refine check against fake GPUs, licence gate, the fp16 patch (applied once with its
notice, refused on a changed script; checked byte-identical to the city's `infer_fp16.py` on UltraShape
5e8dcef), no host paths, and the chain end to end on a generated stand-in statue (puddle cut, face tagged, split
cage at budget, bake, QA PASS) plus a wrong face oval that must fail the QA. `IAMAR_STATUE_SMOKE=1` with the
install runs a real refine.
