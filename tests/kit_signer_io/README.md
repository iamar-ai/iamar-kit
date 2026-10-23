# Signer I/O failure regression

Run from the repository root:

    PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_signer_io/test_model.py
    PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_signer_input/test_model.py
    PYTHONDONTWRITEBYTECODE=1 python3 tests/kit_signer_text/test_model.py

These are finite Python standard-library models and source-text checks. They
do not run GDScript, generate or read keys, perform cryptography, write world
packages, launch a compiler/native process, start hosts, or use a network. The
I/O model holds all pretend files in memory and supplies each failure explicitly;
it is not a FileAccess implementation or evidence of native filesystem behavior.

## Corrected control flow

`world_sign.gd::_sign` first refuses detected manifest/signature symlinks, then
admits a bounded `WorldSource` folder snapshot and
reads the manifest from it. Failed source admission, missing/empty manifest, or
invalid root signer input returns nonzero before either output is opened for
writing. It releases the first snapshot before replacing the manifest. Just
before the manifest write, `_folder_writable` creates and removes a probe file in
the folder: a folder where entries cannot be created or removed (Unix mode 555
with the files still writable) refuses there, with manifest.json and
signature.json untouched, instead of failing at the signature unlink after the
manifest already names the new signer (an internal task). Each
output open is checked before dereference; each `store_string` result and the
reported store/flush errors are checked after closing the handle.

The manifest is then recaptured by `WorldSource`, and its exact UTF-8 bytes must
match the requested write before signature construction. The old signature stays
in place through these checks: `WorldSignature.hash_files` already excludes it.
The replacement is checked against the existing signature-size limit before
the old signature is removed. Removal failure returns nonzero. Keeping this late,
checked unlink avoids introducing WRITE-through-hardlink truncation of the old
signature's shared inode. After successful removal, an output-open failure can
leave the signature missing. The replacement is read back after close with reads bounded to the serialized
byte count, equal pre/post read lengths, an error check and exact byte equality.
The existing `_verify` must succeed before `SIGNED` is printed and zero returned.

Godot's documented `store_string` returns a boolean. The Unix and Windows
FileAccess implementations in [Godot 4.5](https://github.com/godotengine/godot/tree/4.5-stable)
call `fflush` without refreshing `last_error`, so a post-flush `get_error` alone
cannot establish that the requested bytes were written. Readback catches an
observable missing/partial/changed output even when the reported error stays OK.
It does not prove fsync durability, survival of a power failure, atomic publication,
or protection from concurrent writers changing pathnames or contents.

## Remaining mutation and behavior limits

These remain in-place writes with no rollback. Once its WRITE open succeeds,
the manifest can be truncated, partial or changed on failure. Its changed signer
claim can invalidate the old signature even while that signature's bytes remain.
Once signature removal succeeds, the old signature is lost even if the next open
fails; a subsequent write can leave partial bytes. A signature size/removal/open
failure leaves the already rewritten manifest; final verification failure may
leave both new outputs.
No previous-output preservation is promised after writing starts.

Preflight is structural/byte admission, not schema or signature verification.
It includes an existing signature file under ordinary source size/read limits.
An unreadable signature or one exceeding those source limits now refuses before
mutation instead of being deleted. A readable stale/invalid old signature can
still be replaced because its cryptographic validity is not a preflight condition.
Symlink checks are repeated before the manifest write and signature replacement,
but they are not atomic no-follow operations. Manifest hardlink behavior is
unchanged. The manifest and signature are recaptured separately; source races, real key
handling, permissions, atomic multi-file publication and broader rollback remain
outside this correction. No `WorldSource`, `WorldSignature`, format or keygen
implementation is changed.

## Evidence covered

Twelve test groups cover folder/link/input/preflight/probe refusal, the probe's create-then-remove order, both null opens, false stores,
reported store/flush failures, silent flush with truncated readback, equal-length
wrong bytes, failed manifest recapture, signature size/removal refusal, loss of
the old signature after removal followed by open failure, read-open/error/
length failures, the shared-inode unlink/create model, verification failure,
and success with or without an old
signature. Source assertions bind the ordering, guards and bounded read to
production text. The existing signer-input matrix is unchanged. The lexical
suite changes only its final verification assertion to follow the new success
ordering; all lexical cases remain intact.

Passing establishes source/model evidence only. GDScript parsing/execution,
real signing, actual I/O failures and native Linux/macOS/Windows validation are
separate, unrun acceptance gates.
