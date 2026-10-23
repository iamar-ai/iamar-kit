# iamar kit

The iamar kit is what an AI agent needs to build a world for **iamar**, a 3D world browser.
People visit worlds, walk around, meet each other, take quests and step through portals into
other people's worlds. You tell your AI agent what world you want; it builds the world, tests
it, and gets it ready for you to publish.

Start here: **point your agent at https://iamar.ai/docs/**. Tell it what you want to make, and
it will read the kit, interview you, and work through the steps.

## What is in this repository

| Path | What it holds |
|---|---|
| `kit/AGENT_KIT.md` | The instructions an agent follows to build a world. Read it first. |
| `kit/catalog/` | The reusable asset catalogue: meshes, textures and sounds, each with its licence and attribution. |
| `kit/recipes/` | Tested techniques, with the trap each one avoids and the evidence behind it. |
| `kit/tools/`, `scripts/`, `tools/` | Scripts for building, checking, baking and packaging worlds. |
| `docs/` | Reference: the world package format, the scripting API, hardware tiers and more. |
| `tests/`, `kit/tests/` | The tests for the scripts. Run them before you trust a change. |

## Reuse first

Before you model anything, search the catalogue. Most objects a world needs already exist:

```
iamar-world assets search <words>
iamar-world assets show <name>
iamar-world assets use <id>
```

Model something new only when nothing in the catalogue fits. Check every reused object in a
close shot before you ship the world.

## Licences

- Scripts, tools and tests: MIT (the licence file ships with the public release).
- Docs, recipes, catalogue data and the project's own original assets: CC0-1.0.
- Third-party assets keep their own licence. Each catalogue entry records its licence and
  attribution, and `THIRD_PARTY_NOTICES.md` lists everything in this repository that comes from
  someone else.

Check the licence of an asset before you reuse it outside a world.

## Getting the kit

Clone this repository. Numbered release packs (and their checksums and signatures) are published
on the GitHub Releases page once the public release is made.

## Contributing

Suggestions and fixes are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Report security
problems as described in [SECURITY.md](SECURITY.md).
