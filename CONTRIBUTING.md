# Contributing to the iamar kit

Thank you for helping agents build better worlds. This repository holds reusable scripts,
catalogue assets and the documentation an agent reads. Contributions are welcome in the forms below.

## Proposing a script

A script is ready to share when it has:

1. a command an agent can run, with a `--help` that says what it does;
2. a test under `tests/` or `kit/tests/` that passes on Ubuntu with Python 3;
3. a doc entry in `kit/AGENT_KIT.md` or the matching `docs/` page;
4. no personal names, host names, private addresses or secrets.

## Proposing an asset

An asset needs a catalogue entry in `kit/catalog/catalog.json` that records:

- its **licence** (CC0-1.0 or another licence the kit already accepts);
- its **attribution**, if the licence asks for it;
- its **provenance**: where it came from, and whether any generative model made it. Models
  with unclear licences are not accepted.

Run the catalogue check before you open a pull request.

## How changes reach this repository

This repository is a curated export. Pull requests are reviewed, then the change is ported into the
maintainers' source repository and exported again. So the public history consists of export
commits, and a merged change may appear here under a new commit id. Credit stays in the commit
message.

## Pull requests

- Keep one change per pull request.
- Say what changed and how you checked it.
- Do not include generated files, large binaries or downloaded packs. Assets belong in the
  catalogue, and large packs are published as release assets.

## Licence of your contribution

By contributing, you agree that your scripts and tests are released under the MIT licence and your
docs, recipes and assets under CC0-1.0, the same as the rest of the kit.
