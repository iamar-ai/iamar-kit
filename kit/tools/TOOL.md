# Kit tools: command, hardware, licence, region limits, fallback

Machine-readable source: `tools.json` (check: `python kit/tools/check_tools.py`, prints `TOOLS_OK`).
Licences were read from upstream licence text on 2026-10-19. Model weights are never copied into the kit.

| Tool | Tier | Hardware | Licence | Region / use limits | Fallback |
|---|---|---|---|---|---|
| Blender 4.2-4.5 | 0 | any CPU, 4 GB | GPL-2.0+ (output free) | none | base tier |
| Godot 4.7 | 0 | any | MIT | none | headless asserts only |
| trimesh | 0 | any | MIT | none | Blender bmesh |
| xatlas | 0 | CPU | MIT | none | Blender Smart UV |
| pymeshlab | 0 | CPU | GPL-3.0 (do not bundle) | none | Blender Decimate |
| rembg | 1 | CPU/GPU | MIT code; per-model licences | check each model | manual mask |
| SDXL | 2 | NVIDIA 12+ GB | CreativeML Open RAIL++-M | use restrictions carry to derivatives | hosted image API |
| MV-Adapter | 2 | NVIDIA 16+ GB | Apache-2.0 code; base SDXL terms apply | none stated | single view + manual |
| Hunyuan3D-2 | 2 | NVIDIA 16+ GB | Tencent Hunyuan 3D 2.0 Community | **not licensed in EU, UK, South Korea**; >1M MAU needs Tencent licence; outputs must not train other AI models | hosted generator, or Tier 0 |
| Hunyuan3D-2.1 (`kit/gpu/sculpt.py`) | 2 | NVIDIA **17+ GB** (measured 17.0 GB on an A5000), 8 GB RAM, 10 GB disk | Tencent Hunyuan 3D 2.1 Community | **not licensed in EU, UK, South Korea, also for displaying output there**; >1M MAU needs Tencent licence; outputs must not train other AI models | Tier 0 (catalogue, Blender), any mesh into `sculpt.py cage` |
| UltraShape 1.0 | 2 | NVIDIA, large VRAM | **Tencent Hunyuan 3D 2.1 Community** (repo LICENSE) | same EU/UK/KR exclusion and 1M MAU cap; public machine-generated content must be labelled | coarse mesh + Blender cleanup |
| OpenAI image edit (gpt-image-1.5) | 1 | any; network; user's own API key (paid per image) | OpenAI Terms of Use (hosted service) | OpenAI supported countries only | `concept.py paint --provider manual` + `concept.py import` |

## Traps

- The image API key is the user's own: `kit/concept/concept.py` reads it only from the environment (OPENAI_API_KEY), never from a file or the command line, and redacts it from API error text. Never commit one or put it in a concept set (the set check fails on `api_key`).
- UltraShape's Hugging Face card says `apache-2.0`; the repository LICENSE is the Tencent community licence. Treat it as the Tencent one.
- The interview must ask the user's region before offering any Hunyuan3D/UltraShape step; in EU, UK or South Korea route to Tier 0 or a hosted generator.
- GPL tools (Blender, pymeshlab) are user-installed, never bundled; their output models are not covered by the GPL.
- Unknown licence = not shippable. Re-verify the table before any publish (job P6, `kit/inventory/licences.json`).

## Our own workflow scripts: where each one lives in the kit

`ship_scripts.json` has one entry per script in `kit/inventory/scripts.json` marked ship or ship after
wrapping that lives outside this repository (the iamar browser source (not public), the iamar-models mesh archive (not public)): 120 scripts. Each says
where a user finds it:

| Status | Meaning | Carries |
|---|---|---|
| `in-kit` | copied into the kit | kit files, command, test, doc |
| `covered` | a kit tool does the same job (a port or a successor) | kit files, command, test, doc, reason |
| `bundled` | `tools/kit_bundle.sh` copies it into the kit download (TypeScript packer) | destination, command, test, doc |
| `browser` | stays in the iamar browser, which every user has (builder desk, kit dispatcher, the TypeScript guest build) | reason, doc |
| `internal` | not for users: superseded, a one-off run, swarm tooling | reason |
| `pending` | a follow-up job brings it in (PUB8b 4187 Mission Hall, PUB8c 4188 `add_blade` / `inpaint_part`) | job, reason |

`python kit/tools/check_tools.py` fails when a ship row has no entry, an entry names a kit file, test or doc
that does not exist, a bundled script is not copied by `kit_bundle.sh`, or an entry is still pending
(`--allow-pending` lists them without failing). Test: `python kit/tests/ship_scripts_test.py`. A new ship
script in the inventory needs its entry here before the check passes again.

## Texture painters (`kit/tools/painters/`)

Seeded, procedural painters from the city, each taking its output path as the first argument (a file for the first four, a directory for the rest; `--preview` where the source had it). Needs numpy, Pillow and scipy. Test: `python3 kit/tests/painters_test.py` (runs each twice, checks non-flat PNGs and identical bytes).

| Painter | Writes |
|---|---|
| `forest_road_paint.py` | tileable forest road track texture |
| `forest_tree_paint.py` | painted leaf cards and bark for trees |
| `road_lantern_paint.py` | road lantern textures |
| `mp_fields_paint.py` | countryside fields atlas |
| `mp_flora_paint.py`, `mp_herb_paint.py` | flower, grass and herb card atlases (herb imports flora) |
| `mp_waterfall_paint.py` | waterfall fall/flow/foam textures |
| `masterplan_garden_paint.py` | garden plants, hedge and mulch with normal maps |
| `strand_paint.py` | hair-card atlas, hair fill and beard fill (`beard` argument: beard only) |

City-only painters (`forest_paint.py`, `portrait_paint.py`, `masterplan_griffin_paint.py`) stay in the city repo, listed `internal` in `ship_scripts.json`.
