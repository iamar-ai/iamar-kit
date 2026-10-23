# Third-party notices

The kit's own code is MIT and its docs and original assets are CC0-1.0 (see LICENSE). This file lists
everything in this repository that comes from someone else, and every outside tool the kit calls but
does **not** contain. Source of truth: `kit/inventory/licences.json` (each row cites the upstream
licence text and the date it was read). Last verified: 2026-10-23.

## Bundled in this repository

| Group | Where | Licence | Attribution |
|---|---|---|---|
| Kenney asset kits (Fantasy Town Kit 2, Nature Kit, Castle Kit, Survival Kit), converted to catalogue meshes | `kit/catalog/assets/` | CC0 1.0 | Kenney (kenney.nl). Credit is appreciated, not required |
| Quaternius megakits (Medieval Village, Stylized Nature, Fantasy Props, Universal Base Characters, Universal Animation Library) | `kit/catalog/assets/` | CC0 1.0 | Quaternius (quaternius.com). Credit appreciated |
| Fonts Fondamento (Brian J. Bonislawsky / Astigmatic) and Noto (Google, Adobe) | only if a catalogue entry or world ships them | SIL OFL 1.1 | Ship OFL.txt with the fonts; fonts may not be sold on their own |
| Music and sound effects from OpenGameArt and Kenney (cynicmusic, RandomMind, qubodup, HaelDB) | only if a catalogue entry ships them | CC0 1.0 | as named |
| US government wolf-howl recordings (NPS, USFWS) | only if a catalogue entry ships them | US government public domain (17 USC 105) | National Park Service; USFWS |

Each catalogue entry (`kit/catalog/catalog.json`) records its own licence and attribution; the export
withholds any asset without a recorded shippable licence.

## Tools the kit calls but does not contain

None of the code or model weights below is in this repository. The user installs or downloads each
one under its own licence. Their licences apply to the user's copy, not to this kit.

| Tool | Licence | How the kit uses it |
|---|---|---|
| Blender | GPL-3.0-or-later; files Blender writes belong to their author | `kit/blender/*.py` run inside the user's Blender through its `bpy` API. The scripts are the kit's own MIT files; no Blender code is included |
| PyMeshLab | GPL-3.0 | optionally imported from the user's own Python environment. Not vendored |
| Godot Engine | MIT (Copyright Juan Linietsky, Ariel Manzur and contributors) | the user's Godot runs the worlds and tests; not included |
| xatlas (Jonathan Young, 2018-2020) | MIT | pip package, installed by the user |
| rembg (Daniel Gatis, 2020) | MIT | pip package. Its models (u2net, isnet-general-use) are Apache-2.0 and are downloaded to the user's machine; the kit uses only these two |
| MV-Adapter (huanngzh) | Apache-2.0 code; weights listed as apache-2.0 on Hugging Face | Tier 2 only. The user clones the pinned commit; `kit/gpu/patches/mvadapter_11gb.patch` is applied to that clone |
| Stable Diffusion XL base 1.0 (Stability AI) | CreativeML Open RAIL++-M | Tier 2 only. Weights downloaded by the user; the licence's use restrictions pass on to anything built on them. Output belongs to the user |
| Hunyuan3D-2, 2mv, 2.1 and UltraShape 1.0 (Tencent, PKU) | Tencent Hunyuan 3D Community Licences (not open source) | Tier 2 only. **Not licensed in the EU, UK or South Korea, including displaying output there**; a licence from Tencent is needed above 1M monthly active users; output must not be used to improve other AI models. The kit's commands refuse in those regions. Weights are never redistributed. Record generated assets as `Tencent Hunyuan 3D <version> Community License (output)` |
| Kokoro TTS, Misaki, eSpeak / phonemizer | Apache-2.0 model; GPL components | developer-side only, not bundled |
| OpenAI image API | OpenAI terms of use (hosted service) | Tier 1, on the user's own API key; the kit ships only client code |

## Not covered here

Pieces still waiting for a licence decision are not shipped: city-original meshes marked
"licence pending" in the catalogue stay withheld by the export until `original-procedural` is settled,
and the Hunyuan3D-generated head `assets/masterplan/eagle/head_gen.glb` is never shipped.
