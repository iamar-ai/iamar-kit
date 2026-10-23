# CLI Node override: inert boundary regression

Run from the source root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/typescript-world/node_override_inert.py .
```

The Linux/macOS `kit/iamar-world compile-typescript` wrapper treats a present
`IAMAR_TS_NODE` as authoritative, including an empty value. An empty, missing
or non-executable selection fails the existing availability check. Only an unset
override discovers `node` on PATH. Valid paths with spaces remain intact.
This aligns empty-override behavior with desktop Build/Validate; it does not
change the source-toolchain route, compiler discovery, or Windows wrapper.

Seven tests extract the actual shell selection and availability fragment and
run it with mocked PATH discovery and inert temporary files. The selected files
are never executed. The fragment ends before the Node version probe or packer
invocation. No Node, compiler, Godot, signing, world execution or network runs.
The same tests fail once against the previous wrapper: an explicit empty value
silently selected the PATH executable. These tests establish shell selection
behavior only, not real compilation, packaging or platform acceptance.
