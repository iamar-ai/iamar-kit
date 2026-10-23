# Private key creation prerequisite

This source proposal changes `keygen` to require private-pair native API version 1
in the matching browser. An older or incompatible browser stops before generating
a key or writing output. There is no fallback to save-then-chmod.

Use an existing private local destination directory. This version does not create
missing parent directories, fix their permissions, move keys, or select another
location automatically. Simple-name expansion still selects the configured
signing directory, but that directory must already meet the native policy.

The native backend checks the destination, ancestors and platform security before
RSA generation. Both final names must be absent. It stages files privately and
publishes the adjacent public file first, then the private file, without replacing
either destination. The two files are not one atomic commit. A failure can leave
public-only output or protected staging. A failure after private publication can
leave both final files with uncertain cleanup/durability. Errors report only
status and paths, never PEM bytes. Existing and published files are preserved;
do not blindly retry, overwrite, or delete a reported result.

Supported destinations are intentionally conservative. Linux accepts only the
reviewed local filesystem set; macOS requires supported native local filesystems
and rejects extended ACLs; Windows requires the reviewed local NTFS path and ACL
policy. Unsafe/unsupported paths fail closed. A home/profile pathname alone is
not evidence of privacy. Consult the browser native backend policy before
provisioning a destination. Provisioning and changes to existing permissions are
operator responsibilities and are not done by this command.

## Existing-key workflow

`sign` and `package` continue to accept an existing external private RSA PEM;
they do not require running `keygen`. Use a dedicated signing key the operator
owns and is authorized to use. It must already be securely provisioned outside
the world/project, package staging and shared folders, with a stable trusted path.
Pass its absolute path, never PEM text. The current loader has no passphrase or
hardware-key interface; do not silently decrypt, export or convert another key.
An adjacent `.pub` is not required for signing because public material is derived
in memory.

The selected-key packing checks are best-effort path and captured-byte checks.
They require a stable tree and do not establish race-proof reads or scan for all
other secrets. Do not run with concurrent writers. Review contents before
distribution and verify both the resulting signature and expected public key ID.
A valid unknown signature does not establish signer trust.

## Qualification status

These source changes are not qualified for native release. On 2026-10-18, isolated
read-only source assertions passed (five kit key-exclusion, two kit private-keygen,
and three browser private-pair tests). These are textual checks, not a security proof.
The unchanged POSIX source and synthetic fixture compiled without warnings with
Linux g++ 14.2 in standalone C++17 mode. The fixture rejected the available
filesystem before writing its payload; successful native creation was not tested.
The exact Godot binding/ABI, engine loading, macOS and Windows compilation, and
supported-filesystem behavior remain unverified. Nothing here authorizes generating
credentials, signing release
artifacts, changing permissions, packaging binaries, publishing or deploying.
Platform security review, native fixture tests, second-account denial tests,
failure/race/crash testing and matching browser/kit release custody remain gates.
