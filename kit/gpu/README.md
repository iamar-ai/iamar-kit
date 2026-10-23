# GPU tier (Tier 2): concept picture to game asset on your own NVIDIA GPU

Swarm project `iamar-creator-knowledge`, job P5 (2967). the maintainer 2026-10-20 (decision #33):
**local only**, no hosted forge; the GPU steps run on the user's own hardware, with exact
needs stated and a licence check.

What it does: one concept picture (drawn, painted, or generated) becomes a game asset at
real size, with a normal map carrying the sculpted detail, vertex AO and LODs, through the
same Blender build order every kit model uses (`kit/blender/README.md`).

```
picture --cutout--> RGBA --shape (GPU)--> raw surface (~400k faces) --cage--> high + cage at real size
        --game (kit/blender/asset_pipeline.py: weld, closure audit, normal bake, AO, LODs)--> <name>.glb + LODs
```

## Quick start

```bash
python kit/gpu/sculpt.py check --python ~/hy21/env/bin/python --repo ~/hy21/Hunyuan3D-2.1 --region US
python kit/gpu/sculpt.py run concept.png out/urn --height 1.2 --budget 1200 --region US \
    --python ~/hy21/env/bin/python --repo ~/hy21/Hunyuan3D-2.1 [--plinth-row 451] [--mem-cap 18G]
# -> out/urn/final/urn.glb (+ urn_lod1.glb, urn_lod2.glb), out/urn/run.json
python kit/blender/look.py ...   # or: iamar-world blender-run kit/blender/look.py -- /tmp/look out/urn/final/urn.glb --color material
```

`IAMAR_GPU_PYTHON`, `HY3D21_REPO`, `HF_HOME`, `IAMAR_REGION` and `U2NET_HOME` set the same
things once for the shell. Each step also runs alone (`sculpt.py cutout | shape | cage | game`,
`--help`), so a picture you cut out by hand or a mesh from another generator can join midway:
a mesh from anywhere enters at `cage`.

## The steps

| # | Step | Command | Runs on | What to check |
|---|---|---|---|---|
| 1 | Cut-out | `sculpt.py cutout pic.png x_rgba.png [--plinth-row N] [--fill 0.8]` (`stages/cutout.py`) | CPU (rembg isnet-general-use) | the subject whole (pale parts in front of pale backgrounds get lost); a drawn plinth or ground removed with `--plinth-row`, or the generator invents a floating disc |
| 2 | Shape | `sculpt.py shape x_rgba.png x_high.glb --region CC [--octree 380 --steps 50 --seed 0]` (`stages/shape_hy21.py`) | NVIDIA GPU, 17 GB | look at it before going on (`kit/blender/look.py`): thin parts (blades, staffs, wings) are often lost; try other seeds |
| 3 | Cage | `sculpt.py cage x_high.glb game --height M --tris N [--cut-below F] [--min-part 0.02]` (`stages/cage.py`, Blender) | CPU | crumbs dropped, base slab cut only where the picture had one (never near the feet), size in metres, centred on its footprint |
| 4 | Game | `sculpt.py game game/x_cage.glb game/x_high.glb final --budget N` (`kit/blender/asset_pipeline.py --high ... --light ao`) | CPU, Cycles GPU if present | `PIPELINE_OK`, closure audit clean, triangles per LOD in `final/pipeline.json` |
| 5 | Look and place | `kit/blender/look.py`, then put it in the world and review it in the preview (`kit/review/REVIEWER.md`) | | judge the game mesh in the world, not the raw surface |

Budgets (the kit's art bar): prop 300, building 3000, creature 6000, hero statue about 8000;
the city's statues were judged in the game at 5000 to 12000. Look at 2 or 3 budgets in the
world before choosing (city lesson: 4.8k, 12k and 24k faces looked the same in the game).

## Multiview: the far side from its own view (recipe `multiview_sculpt`)

One picture shows one side; a single-view generator guesses the rest. For heads, creatures
and figures with wings, staffs or a distinct back, the city first had MV-Adapter paint the
subject from three more sides, then shaped (and optionally painted) it from all of them. It
also runs on a smaller card: everything measured fits an 11 GB RTX 2080 Ti.

```
[concept: SDXL] -> picture --cutout | clean--> RGBA --views (MV-Adapter)--> 4 views [--recut]
   --shape --mv (Hunyuan3D-2mv)--> raw surface --cage--> high + cage [--paint (Hunyuan3D-2)] --game--> <name>.glb + LODs
```

| # | Step | Command | Runs on | What to check |
|---|---|---|---|---|
| 0 | Concept (optional) | `sculpt.py concept out/concepts --prompt "..." [--count 4 --seed 100 --low-vram]` (`stages/concept_sdxl.py`) | NVIDIA GPU, 2 GB with offload | an original picture from text only; never feed commercial art in (the city's first eagle head came from a commercial game picture and was redone) |
| 0b | Inpaint (optional) | `sculpt.py inpaint concept.png mask.png out/parts --prompt "..." [--count 4 --seed 100 --strength 0.99 --low-vram]` (`stages/inpaint_part.py`) | NVIDIA GPU, as Concept (same SDXL weights) | only the white of the mask is redrawn (black kept: the hand holding the part); feather the mask a few px; describe the part in the figure's material. The picture's sides must be multiples of 8 |
| 1 | Cut-out | `sculpt.py cutout` as above, or for a busy picture `sculpt.py clean pic.png out/x --poly "x,y;..." [--grabcut --bg "poly\|poly" --fg ...] [--cut-y ROW]` (`stages/clean_concept.py`, writes `out/x_clean.png`) | CPU | `clean`: everything outside the outline gone (arches, frames, effects), pale wings kept (`--grabcut`; pin the arch seen between wing and body with `--bg`) |
| 2 | Views | `sculpt.py views x_rgba.png out/views/x --text "what it is" [--az 0 90 180 270] [--size 768 --steps 40 --seed 7 --neg "..." --mask keep.png]` (`stages/mv_views.py`) | NVIDIA GPU, 10.8 GB free with the patch | `out/views/x_grid.png`: the views agree with the picture and each other; `--text` names the subject and material (they follow it); `--neg` names what crept in ("cloak, arches, pillars") |
| 2b | Re-cut (pale figures) | `sculpt.py recut out/views/x x_rgba.png` (`stages/mv_recut.py`) | CPU | every `x_az*_rgba.png` holds the whole figure (rembg alone lost a stone statue's wings); rembg's own cut kept as `_rgba_rembg.png` |
| 3 | Shape | `sculpt.py shape --mv out/views/x x_high.glb --region CC [--map front=000,left=090,back=180,right=270] [--octree 380 --steps 50 --max-faces 80000]` (`stages/shape_mv.py`) | NVIDIA GPU, 11 GB | look at it before going on; when a generated side or back view was wrong (wings turned into a cloak), shape from the picture alone: `--map front=000` |
| 3b | Blade (optional) | `sculpt.py blade x_high.glb x_high_blade.glb --root=x,y,z --tip=x,y,z [--width 0.07 --thick 0.02 --segments 240]` (`stages/add_blade.py`, Blender) | CPU | a thin straight part the shape lost (a sword blade) is back, from under the guard to the tip (Blender's frame: Z up, front -Y; write points with `=` so a minus sign is not an option); cage the `_blade` mesh |
| 4 | Cage | `sculpt.py cage` as above | CPU | as above |
| 4b | Paint (optional) | `sculpt.py paint game/x_cage.glb out/views/x game/x_painted.glb --region CC [--paint 000,090,270] [--base "#hex" --gain 1.12 --glow game/x_glow.png]` (`stages/paint_mv.py`) | NVIDIA GPU, 11 GB (model CPU offload) | leave the back view out of `--paint` (the weakest view); faces no view saw come out flat grey: `--base` recolours them to the subject's colour; `--glow` writes an emission mask of glowing eyes and mouths. `sculpt.py paintfix albedo.png --base "#hex"` (`stages/paint_fix.py`) does the same to any albedo PNG. Without paint, the kit's materials and bakes colour the cage |
| 5 | Game | `sculpt.py game game/x_cage.glb game/x_high.glb final --budget N` (or `x_painted.glb` as the first argument: the normal bake keeps the painted texture) | CPU | as above |

All in one: `sculpt.py run concept.png out --mv --text "what it is" --height 2.0 --budget 3000
--region CC [--recut] [--az 0,90,180,270] [--map ...] [--paint 000,090,270 [--base "#hex"]]`
(the region is checked before the cut-out; `run.json` lists every step).

City numbers to start from (iamar-models `tools/mesh3d/README.md`): dragon heads 4 views at
768 px, shape at 4000 faces, 2500 triangles per head was the lowest that kept horns, jaw,
brow and eye sockets crisp at 2 to 3 m; the six South Gate statues 4 views each, shape at
5000 faces. The concepts were 3/4 and profile views, so Hunyuan's "front" is that view: turn
the model to face the way the world needs when placing it.

## Hardware (measured)

Measured 2026-10-20 on the GPU host (RTX A5000 24 GB, 32 GB RAM, Linux, driver 550, torch 2.5.1
cu124), on the kit's test picture (a 512 px urn), `kit/tests/gpu/gpu_tier_test.py`:

| Step | GPU memory | RAM | Time | Disk |
|---|---|---|---|---|
| cutout (rembg, CPU) | none | under 2 GB | 4-9 s | rembg model 170 MB (`U2NET_HOME`, default `~/.u2net`) |
| shape, octree 380 / 50 steps (city setting) | **14.8 GB** allocated by torch, **17.0 GB** in nvidia-smi | 2.8 GB peak | 74 s sampling + 54-117 s loading | weights 7.5 GB (`HF_HOME`); environment about 10 GB |
| shape, octree 256 / 30 steps (draft) | 14.8 GB / about 16.5 GB | 1.9 GB | 36 s + load | |
| shape, octree 128 / 10 steps (smoke test) | | | 85 s with loading | |
| cage, 408k -> 1.5k faces | none | under 4 GB | 4-10 s | |
| game, 1024 px normal bake from 408k faces | Cycles GPU optional | under 4 GB | 10-40 s | |

So the shape step needs an **NVIDIA GPU with at least 17 GB** (a 20 or 24 GB card; 16 GB
cards are below the measured peak and are not offered), CUDA 12.4 drivers, **8 GB free RAM**
and **10 GB free disk** for the weights. `gpu_check.py` enforces these numbers on the GPU torch will
use (the first one in `CUDA_VISIBLE_DEVICES`, else nvidia-smi's first), including 17 GB
**free** at the time of the check; 17 to 20 GB cards pass with an "untested" note. Cached
weights count only when each folder has its `config.yaml` and a checkpoint of 100 MB or more. AMD, Intel and Apple GPUs cannot run step 2 (Hunyuan3D
needs CUDA); steps 1, 3 and 4 run on any computer with Blender 4.2+.

On a shared computer run the GPU step capped, as the city did: `--mem-cap 18G` (Linux with
systemd: a scope with `MemoryMax` and no swap; a runaway step is killed, not the desktop),
under `nice -n 19 ionice -c 3`, one generator at a time, and nothing else on the GPU.

### Multiview steps (measured in the iamar city)

Measured 2026-10-14 on the build host (RTX 2080 Ti 11 GB, Linux, torch 2.5.1 cu124, diffusers 0.31.0),
iamar-models `tools/mesh3d/README.md` "Stable dragon breeds" and "South Gate magical statues".
They were re-run by the kit's opt-in smoke test on 2026-10-22 on the GPU host (RTX A5000 24 GB, Linux, same
pins): views, shape --mv, cage and game all passed; the second table below has those figures.
The test records `peak_gpu_gib` / `peak_ram_gb` in `P_views.json` and the shape's `.json`.

| Step | GPU memory | RAM | Time | Disk |
|---|---|---|---|---|
| views, 4 at 768 px, 40 steps, **with** `patches/mvadapter_11gb.patch` | **9.7 GiB** peak (torch) | not recorded; the kit asks 12 GB free | 75-90 s | SDXL base fp16 6.7 GB, MV-Adapter 3.4 GB, fp16-fix VAE |
| views, 4 at 768 px, **without** the patch | did not fit 11 GB (MV-Adapter's README: about 14 GB) | | | |
| views, 6 at 768 px, patched | did not fit 11 GB | | | |
| shape --mv (Hunyuan3D-2mv fp16, octree 380 / 50 steps) | fits 11 GB | not recorded; the kit asks 8 GB | about 3 min, 10 with the first load | `tencent/Hunyuan3D-2mv` `hunyuan3d-dit-v2-mv` |
| paint (Hunyuan3D-2, model CPU offload, 2048 px, 3 views) | fits 11 GB | not recorded; the kit asks 16 GB (the offloaded models wait in RAM) | about 1 min | `tencent/Hunyuan3D-2` paint and delight folders |
| concept (SDXL, `--low-vram`) | about 1.5 GB | | slow (layer by layer) | SDXL base fp16 6.7 GB |

Kit smoke run (`IAMAR_GPU_SMOKE_MV=1 kit/tests/gpu/gpu_mv_test.py`, the GPU host RTX A5000, 2026-10-22,
a generated 512 px urn picture, `variant="fp16"` weights, memory patch applied):

| Step | GPU (torch peak) | RAM (peak RSS) | Time |
|---|---|---|---|
| views, 4 at 512 px, 10 steps | 11.57 GiB | 8.35 GB (17 GB before `mv_views.py` moved the UNet and VAE to the GPU straight after loading) | load 139 s, sampling 7.5 s |
| shape --mv, octree 128, 10 steps | 5.96 GB | 15.7 GB | load 91 s, sampling 15.6 s; 94,784 faces |
| cage + game (Blender), 1200 tris | none | small | 5 s + 9 s; LODs 1200 / 600 / 240 |

Two things differ from the city's numbers: the views step peaked at 11.57 GiB here against
9.7 GiB in the city (4 views at 768 px on a 2080 Ti), so an 11 GB card may not fit this
exact configuration: keep `gpu_check.py` at 10.8 GB (the city run proved it) but expect to
drop `--size` if it runs out of memory; and the shape step needs **16 GB of RAM** (15.7
measured), so `SHAPE_MV_RAM_GB` went from 8 to 16. Also: a host watchdog that kills any
process over 40% of RAM (the GPU host, 31 GB: 12.4 GB, checked every 5 minutes) killed the first
three views runs at about 5 minutes with SIGTERM (exit 143) and no message; on a small-RAM
host run the views step with the UNet already on the GPU (as now) and check `dmesg` or the
watchdog's log if a run ends with exit 143.

`gpu_check.py --stage views|shape_mv|paint|concept` (or `sculpt.py check --stage mv`, `every`)
enforces these: views need 10.8 GB total and free on the GPU torch will use with the patch
in the MV-Adapter clone (the check reads the clone and prints the `git apply` command when
it is missing on a card under 14 GB), 14 GB without it or for more than 4 views; shape --mv
and paint need 10.8 GB; concept 2 GB. AMD, Intel and Apple GPUs cannot run them (CUDA).

## Install (once; ask the user first: about 20 GB of downloads)

The exact environment the measurements came from (Linux, conda, NVIDIA driver with CUDA 12.4):

```bash
D=~/hy21
conda create -y -p $D/env python=3.10
P=$D/env/bin/pip
$P install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
$P install ninja pybind11 transformers==4.46.0 diffusers==0.30.0 accelerate==1.1.1 huggingface-hub==0.30.2 \
  safetensors==0.4.4 numpy==1.24.4 scipy==1.14.1 einops==0.8.0 opencv-python-headless==4.10.0.84 imageio \
  scikit-image==0.24.0 rembg==2.0.65 onnxruntime==1.16.3 trimesh==4.4.7 pymeshlab==2022.2.post3 pygltflib \
  omegaconf==2.3.0 pyyaml tqdm pytorch-lightning==1.9.5
git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1 $D/Hunyuan3D-2.1
git -C $D/Hunyuan3D-2.1 checkout 82920d643c0dc2f7bfd7255f45f62d386edfe60c   # the pinned commit (pins.json)
HF_HOME=$D/hf $D/env/bin/python -c "from huggingface_hub import snapshot_download as s; \
  print(s('tencent/Hunyuan3D-2.1', revision='0b94677654c57bb9a6b6845cd7b704ccf551d327', \
          allow_patterns=['hunyuan3d-dit-v2-1/*', 'hunyuan3d-vae-v2-1/*']))"
```

**Pinned versions.** `kit/gpu/pins.json` holds the exact commit of every clone and the exact Hugging Face
revision of every model the steps use. The stages download and load only those revisions, and
`sculpt.py check` reports a step not ready when a clone is at another commit or a model is only cached at
another revision (it names the `git checkout` to run). Third-party code runs on import and a model
file is unpickled on load, so an upstream repository that is re-pushed or compromised must not reach a
creator's machine unseen. To move a pin: test the new version end to end, then change pins.json and the commands
here together (gpu_tier_test.py checks they agree).

Only the shape half of Hunyuan3D-2.1 is used (`hy3dshape`); its texture half (`hy3dpaint`)
is not needed: the kit paints with its material library and bakes light instead. Then
`sculpt.py check` must print `GPU_CHECK_OK`. Uninstall: delete `$D` (the weights live in
`$D/hf`). The weights are never copied into the kit, a world or a package.

### Install multiview (once more, only if you want the multiview steps; about 25 GB)

Written from the city's install (the build host, 2026-10-14, iamar-models `tools/mesh3d/README.md`:
MV-Adapter added with pip into the existing Hunyuan3D-2 conda environment, torch 2.5.1+cu124,
diffusers 0.31.0, transformers 4.48.3 and numpy pinned by a constraints file); this fresh
from-scratch sequence was not re-run for the kit, so check `sculpt.py check --stage mv` after it:

```bash
D=~/mv                                   # any folder; MVADAPTER and HY3D2_REPO point into it
conda create -y -p $D/env python=3.10 && P=$D/env/bin/pip
printf 'torch==2.5.1\ntorchvision==0.20.1\ndiffusers==0.31.0\ntransformers==4.48.3\nnumpy==1.26.4\n' > $D/pins.txt
$P install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
$P install -c $D/pins.txt diffusers transformers accelerate safetensors huggingface-hub rembg onnxruntime \
  opencv-python-headless trimesh pymeshlab xatlas pygltflib einops omegaconf peft jaxtyping typeguard \
  matplotlib pytorch-lightning timm kornia
git clone https://github.com/huanngzh/MV-Adapter $D/MV-Adapter
git -C $D/MV-Adapter checkout 4277e0018232bac82bb2c103caf0893cedb711be      # the pinned commit (pins.json)
git -C $D/MV-Adapter apply <kit>/gpu/patches/mvadapter_11gb.patch     # needed under 14 GB
git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2 $D/Hunyuan3D-2
git -C $D/Hunyuan3D-2 checkout f8db63096c8282cb27354314d896feba5ba6ff8a        # the pinned commit (pins.json)
$P install -c $D/pins.txt -r $D/Hunyuan3D-2/requirements.txt
# paint step only: build the texture half's two extensions (needs the CUDA toolkit)
(cd $D/Hunyuan3D-2/hy3dgen/texgen/custom_rasterizer && $D/env/bin/python setup.py install)
(cd $D/Hunyuan3D-2/hy3dgen/texgen/differentiable_renderer && $D/env/bin/python setup.py install)
export IAMAR_GPU_PYTHON=$D/env/bin/python MVADAPTER=$D/MV-Adapter HY3D2_REPO=$D/Hunyuan3D-2 HF_HOME=$D/hf
python kit/gpu/sculpt.py check --stage mv --region US      # then --stage paint if you want painting
```

The weights download on first use into `HF_HOME`: SDXL base 1.0 (fp16 files only: the steps
load `variant="fp16"`; without it diffusers fetches 13 GB more), `madebyollin/sdxl-vae-fp16-fix`,
`huanngzh/mv-adapter` (`mvadapter_i2mv_sdxl.safetensors`, 3.4 GB), `tencent/Hunyuan3D-2mv`
(`hunyuan3d-dit-v2-mv`), and for paint `tencent/Hunyuan3D-2` (`hunyuan3d-paint-v2-0`,
`hunyuan3d-delight-v2-0`). The MV-Adapter step must not use diffusers'
`enable_model_cpu_offload` (accelerate copies the cross-attention kwargs and the reference
cache comes back empty: KeyError on the first step); `stages/mv_views.py` moves the text
encoders off the GPU itself instead.

## Licences and region (read before step 2)

| Tool | Licence | Limits |
|---|---|---|
| Hunyuan3D-2.1 (code and weights) | Tencent Hunyuan 3D 2.1 Community License (not open source) | **Territory excludes the EU, the UK and South Korea**: no use there, and no use, distribution **or display of its output** outside the Territory (s.5c); above 1M monthly active users a licence from Tencent is needed (s.4); output must not be used to improve any other AI model (s.5b) |
| Hunyuan3D-2 and Hunyuan3D-2mv (shape --mv, paint) | Tencent Hunyuan 3D 2.0 Community License | the same Territory clause (EU, UK, South Korea excluded), 1M MAU and no-training-other-models terms |
| MV-Adapter (views) | Apache-2.0 (code); weights `huanngzh/mv-adapter` state no separate licence | the SDXL base terms apply to what it makes |
| SDXL base 1.0 (views, concept) | CreativeML Open RAIL++-M | use restrictions (Attachment A) pass on to derivatives and must be passed on; outputs are the user's; no region limit |
| rembg | MIT; its isnet-general-use model (DIS) Apache-2.0, u2net Apache-2.0 | none |
| OpenCV (recut, clean) | Apache-2.0 | none |
| Blender | GPL-2.0-or-later (output is yours) | user installs it; never bundled |
| PyTorch, diffusers, trimesh | BSD-3 / Apache-2.0 / MIT | none |

- `sculpt.py shape`, `shape --mv`, `paint` and `run` **refuse** without the user's region (`--region CC` or
  `IAMAR_REGION`, a two-letter ISO code: `EU`, `DEU` or `Germany` are refused too) and in
  the EU, the UK or South Korea (exit 3), and print the fallback (`run --mv` before the
  cut-out, so no GPU time is spent on views that cannot be used). Ask
  the user in the design interview; never guess it.
- Because the licence also covers **displaying** the output, a world whose models came from
  Hunyuan3D shown to visitors in the EU, the UK or South Korea is outside the licence. Tell
  the user; for a world meant for visitors everywhere, prefer Tier 0 models or the catalogue
  for anything visible. (The iamar team's own use: the maintainer 2026-10-14, an internal memory record, does not
  block the swarm on this; it still binds kit users.)
- Record each generated asset's licence as `Tencent Hunyuan 3D 2.1 Community License (output)`
  (`... 2.0 Community License (output)` for shape --mv and paint) in the world's `THIRD_PARTY_NOTICES.txt` and, for a kit catalogue entry, in its licence field
  (the kit's own export, `kit/export/README.md`, withholds an asset without a recorded licence).

Sources: the licence file in the Hunyuan3D-2.1 repository (read 2026-10-20), `kit/tools/tools.json`,
`kit/inventory/licences.json`.

## When the GPU step cannot run (fallbacks)

`gpu_check.py` names the fallback for each missing piece:

| Missing | Fallback |
|---|---|
| NVIDIA GPU with 17+ GB, CUDA, the install, or a licensed region | **Tier 0**: reuse a catalogue object (`iamar-world assets search "<what>"`), or model it in Blender (`kit/blender/starter_build.py`, kit materials and trim sheet), or a mesh from any source the user has rights to, entering at `sculpt.py cage`. the maintainer 2026-10-20: no hosted forge is offered by the kit; a hosted generator on the user's own account is their choice and its terms |
| a licensed region for any Hunyuan3D step (all versions share it) | **Tier 0** only (catalogue, Blender, the kit's materials instead of Hunyuan3D paint) |
| views (MV-Adapter: 10.8 GB free with the patch, the clone) | shape from the one picture (`sculpt.py shape`, 17 GB), or draw the side and back views by hand as `P_az090_rgba.png` etc. and run `sculpt.py shape --mv` on them |
| paint (the texture half built, its weights) | skip it: the kit's material library and the normal and light bakes colour the cage, or paint the texture by hand |
| SDXL for a concept | a picture the user drew or has the rights to (never commercial art) |
| rembg | cut the subject out in any image editor (PNG with transparency); `cutout.py` keeps a picture's own alpha |
| Blender 4.2+ | install it (`kit/blender/README.md`); nothing in steps 3-4 works without it |

## GPU pipelines from the city and what the kit packages

The city made more with the same family of tools; their scripts are in `the iamar-models mesh archive (not public)`
`tools/mesh3d/` (`kit/inventory/scripts.json`, disposition "ship after wrapping"), with the full
record in that folder's `README.md`:

| Recipe | What | Needs (as run in the city) | Status in the kit |
|---|---|---|---|
| `sculpt_from_image` | one picture -> shape -> cage -> normal bake | Hunyuan3D-2 or 2.1, 17 GB | **packaged here** (`sculpt.py`, Hunyuan3D-2.1) |
| `multiview_sculpt` | a concept -> 4 generated views (MV-Adapter, SDXL) -> Hunyuan3D-2mv shape and paint; heads of the dragon breeds, the South Gate statues | 11 GB card with the `mvadapter_11gb.patch` (9.7 GB peak at 768 px, 4 views), SDXL fp16 weights 6.7 GB | **packaged here** (an internal task): `sculpt.py concept / clean / views / recut / shape --mv / paint / paintfix`, `run --mv`; from `mv_views.py`, `mv_recut.py`, `head_mv.py`, `head_tex.py`, `clean_concept.py`, `refimg.py`, `mvadapter_11gb.patch` |
| `statue_from_concept` / statue v4 | whole statue: Hunyuan3D-2.1 coarse + UltraShape 1.0 refine (3-9M faces), split face/hair/body cage, cylindrical face UV, Cycles normal + sky AO bake, relight, seam blend, automatic QA (`qa_statue.py`) | UltraShape refine about 10 min at **19 GB GPU**, RAM capped at 18 GB (the stock fp32 build is killed at 18 GB: needs the fp16 patch) | **packaged: `kit/gpu/statue` (`statue.py`, README)**; `gpu_check.py --stage refine` checks the refine step |
| head pipelines | eagle/griffin heads from one view (Hunyuan3D-2 shape + paint, mirror, whiten), dragon heads from views, head LODs | Hunyuan3D-2 27 GB of weights, 11-24 GB cards | dragon heads: the multiview steps above; `head_lods.py` (normal bake onto the painted cage, LODs by collapse on the same UVs) is what `sculpt.py game` does with `kit/blender/asset_pipeline.py`; the head's turn and length are set when placing it. Not packaged: `mirror_v2.py` / `glb_whiten.py` / `bake_v2.py` (the one-view eagle head's mirrored paint and feather whitening, city-specific fixes for a one-sided picture: use the multiview steps instead) |

## Lessons from the city (kept in the steps above)

- Decimate the **untextured** shape and bake the detail back with a normal map; textured
  decimation shattered the eagle's feather sheets at 12k faces (iamar-models `tools/mesh3d/README.md`).
- Remove the picture's plinth or ground before the generator, or it builds a floating disc.
- Never cut near the soles; a fixed cut chopped boots and left them hollow (statue v4).
- Centre on the footprint, not the bounding box: a staff sticking out moved a statue off its plinth.
- Look at the raw surface before cutting it down; thin parts (a greatsword blade) get lost and
  must be put back or the picture changed.
- A small face in the picture (about 25 px) gives a blobby face: enlarge the head in a separate pass.

## Test

`python3 kit/tests/gpu/gpu_tier_test.py` (any computer, about 10 s; Blender parts SKIPPED without
Blender): hardware check against fake GPUs (none, 8 GB, 18 GB, 24 GB, a busy 24 GB, two cards with
and without `CUDA_VISIBLE_DEVICES`), partial weight downloads, the region gate (no region, EU,
DEU, DE, GB, KR, IT, FR refused), `run` argument checks (unknown options, path names, bad numbers), cut-out geometry, and the cage and game steps on a
generated bumpy surface with a crumb and a base slab. With `IAMAR_GPU_SMOKE=1` and the install
settings it also runs `sculpt.py run` on the GPU end to end (85 s shape on the A5000, LODs
1200 / 600 / 240).

`python3 kit/tests/gpu/gpu_mv_test.py` (any computer including Windows, no GPU): the multiview
checks against fake GPUs (an 11 GB card passes the views step only with the patch, 6 views
ask 14 GB, 8 GB and busy cards refused), the patch applying to the line it targets, cached and
half-downloaded weights, the region gate on `shape --mv` and `paint` (and `run --mv` refusing
before the cut-out), argument checks, and the CPU steps on generated pictures (`paintfix`,
`recut --no-rembg`, `clean --alpha`; SKIPPED without numpy, Pillow and opencv-python). With
`IAMAR_GPU_SMOKE_MV=1`, `MVADAPTER`, `HY3D2_REPO`, `IAMAR_GPU_PYTHON`, `HF_HOME` and
`IAMAR_REGION` it also makes 4 views at 512 px / 10 steps and a Hunyuan3D-2mv shape at octree
128 / 10 steps, then the cage and game steps.
