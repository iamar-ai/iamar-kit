# kit/ci: inventory / recipe / catalogue gate (an internal task)

`python3 kit/ci/check_entries.py` fails when something is added without its entry:

| Added | Needs |
|---|---|
| script (`.py .gd .sh .mjs .cmd .js .ts`) | a row in `kit/inventory/scripts.json` or `kit/inventory/scripts_added.json` (path, purpose, disposition); a `ship` row needs its file name in a test or `.md` |
| glTF/GLB under `kit/catalog/assets/` | an entry in `kit/catalog/catalog.json` (`python3 kit/catalog/catalog.py build`) |
| recipe in `techniques.json` | id, source (evidence), check (kit=automatic recipes exempt), layer, tier, and a line in `TECHNIQUES.md` (`python3 kit/recipes/make_recipes.py`) |

`--suggest` prints stub rows for uncovered scripts (edit purpose/disposition, then append to `scripts_added.json`).
Runs locally and costs no Actions minutes: `sh kit/ci/install_hook.sh` installs it as the pre-push hook.
The hook also runs the public-export scan on HEAD (`tools/export_public.py`, about 6 s) and refuses the push on `EXPORT_FAILED`: a host name or e-mail in an evidence doc, a secret, or a new image/mesh with no licence record (add a glob to `asset_licences` in `kit/export/rules.json`). `KIT_PREPUSH_EXPORT=0` skips the scan for one push. Test: `python3 kit/tests/ci/pre_push_export_test.py`.
A workflow can call the same command; none is added because private-repo minutes are limited.
Test: `python3 kit/tests/ci/check_entries_test.py` (seeded misses must fail).
