# AGENT_KIT internals

Implementation notes moved out of [`../AGENT_KIT.md`](../AGENT_KIT.md):
how the folder-panel importer works, the work bounds it reports, and the
scoped creator MCP capability reference. Agents start with `AGENT_KIT.md`;
read this only when the build needs one of these details.

## Local browser folder handoff

The **Builders' Guild → Open local folder tools** path works with editable
files on the user's computer and does not require a quest or account. Keep
local editing separate from scoped creator-service grants and hosting consent.

1. For an agent-created world, tell the user to choose **Choose world folder**
   and select its saved `manifest.json`/`scene.json` directory. Alternatively,
   **Choose parent folder**, the new folder name, world id, title and author,
   then **Create starter folder** saves and validates the existing CLI starter.
   The UI requires a fresh child folder; it never replaces an existing one.
   The starter contains `manifest.json`, `scene.json`, and empty `assets/` and
   `scripts/` folders. Use `iamar-world new` when creating it from the CLI.
2. **Copy actual folder path for my agent** gives the real local path for edits.
   The panel does not edit a scene. Make the requested changes in that folder,
   preserve existing work, and validate and preview the saved revision.
3. **Validate saved world** uses the existing world validator and reports the
   saved folder's identity and result. For TypeScript, the source-added
   **Build and validate** flow takes the selected world folder as its template:
   choose **Choose TypeScript source (.ts)** and **Choose build output parent**
   (an existing local folder outside the template), then build. It requires the
   [existing Node/TypeScript prerequisites](../AGENT_KIT.md#typescript-world-scripts), stages
   saved assets and selects fresh `output/world/` only after validation. Failed
   or canceled attempts preserve previous output. Follow the
   [desktop steps and runtime-verification limits](../../docs/TYPESCRIPT_WORLDS.md#desktop-build-and-validate-source-added).
   CLI builds also copy saved template assets into `<fresh-out>/world/`;
   select that generated world folder. Selecting source files alone does not
   compile them. Revalidate after edits; validation does not execute scripts or
   establish gameplay, signing or hosting.
4. Once approved for packaging, use the existing kit and approved signing key.
   Keep the final `.iamar` and its matching same-basename `.pieces.json`
   together. Neither folder validation nor the UI import creates a key or signs.
5. The user chooses **Import signed world (.iamar)** in the folder panel or
   **Esc → Host My World**. Both use the same verifier/installer as
   `add-to-browser`: only the verified pair is copied into `user://my_worlds`.
   Unknown signers remain unknown; signature integrity is not signer trust.
6. From the folder panel, **Open Host My World with this package** selects the
   exact imported package. Direct Host My World import selects it there too.
   The current audience choice is retained. The user reviews **Who may visit**
   and **Upload**, then explicitly chooses **Start Hosting**. An active host
   is not silently stopped or replaced. Import alone does not register or host.
7. Use the existing **Copy link** once hosting supplies an address. Scoped
   registrations already appear at the desk with **Copy address**, **Copy link**
   and **Enter / check availability**; those controls use the existing address
   and ordinary navigation. A copied address or registration is not evidence of
   a running host or a successful visitor entry.

For changed content, increment the version before repacking. Import preserves
different or incomplete installed files with the same id/version; an exact
already-installed pair is a safe retry. Failed creation/import may retain partial
files. Inspect the reported folder/recovery path, preserve useful work, and
resolve the conflict explicitly; the tools do not delete failed output. Do not
edit the source pair during import or a folder during its validation.
UI import uses the shared installer's cooperative driver; command-line import
and starter creation remain synchronous. Cancel requests retire UI publication
immediately, but the operation stays busy until its current step and resource
cleanup finish. Partial staging files are retained with a recovery path. Closing
or reopening cannot select a stale result or start a replacement import while
the original is draining. A completed package-first/list-last settlement is not
undone or relabeled canceled.

The outer importer reads at most 64 KiB per raw hash/copy step and yields after
256 KiB of those reads or a 4 ms scheduling target; a copy also writes that chunk.
These are source-level work bounds. `WorldPackage.open_async` also hashes
signed-file payloads from immutable snapshots in at most 64 KiB steps, forcing a
yield before more than 256 KiB of payload copies or 64 verification steps accrue.
It checks cancellation before each step and before returning verification.
Existing verifier list capture (up to 2 MiB), source capture/archive inflation,
signature JSON/schema/key processing, path collection/sorting, signing-text
hashing, RSA/trusted-list checks, native I/O and asset decoding remain indivisible.
The bounds do not establish maximum frame time, immediate cancellation, total
verifier memory use or measured responsiveness. Synchronous verification remains
available to existing callers.

This describes the [folder-panel source](the iamar browser source (not public)),
[shared starter](the iamar browser source (not public)) and
[shared importer](the iamar browser source (not public)). Native UI/file-dialog
behavior, real desktop Build compiler/cancellation, installed/exported platform
builds and the full creator-to-two-visitor journey remain unrun for this workflow.
Source checks are not release acceptance.

## When using a scoped creator MCP capability

The scoped creator service wraps this kit. Use only the operations and exact
world/workspace, signer, host profile and audience the owner granted. The CLI
examples below do not expand that capability or authorize obtaining keys,
changing an account, uploading content or starting an unrelated host. If a
required operation or configured dependency is unavailable, report the blocker.
Never put a creator credential or private signing key in a world, chat, address,
share link, screenshot or log.

For a requested registration/hosting workflow:

1. Make the real draft/edit, validate the current revision, run preview and review
   its images, then request signing through the exposed tools. Keep the returned
   immutable `artifactRef`. Preview images do not establish playable entry.
2. Call `iamar_world_ready` using the delegated `world`, that `artifactRef` and
   one chosen `intentId`. `activateHost` defaults to `false`: omission/false
   registers without starting a host. Use `true` only when the requested outcome
   includes hosting and the existing grant includes `host.start`. Registration
   still requires a configured authenticated host prepared for that exact artifact.
3. If the result is `preparing`, this ready workflow still needs continuation;
   an earlier registration may already exist. Keep the same world, artifact,
   intent and activation choice. Wait the returned `retryAfterMs`
   before checking again. If `iamar_world_status` is exposed, poll the same world
   and intent; otherwise repeat the same ready request after the delay. Bound
   preparation polling by the original `preparation.expiresAt` and the original
   authority's lifetime. Retain that first deadline when later results omit it or
   show a later deadline; a missing field or new transfer is not renewed authority
   or permission for unlimited retries. A completed MCP tool call describes the
   call, not the world workflow.
4. When status reports `prepared`, repeat the original ready request. A status
   read never registers or activates anything, and there is no background commit
   after the pending response. Keep the original host profile, audience, paired
   host account session and legacy MCP session for this unfinished preparation;
   a fresh session or grant cannot silently adopt its receipt. Modern stateless
   requests have no legacy session, but still require current unchanged authority.
5. `registered/offline` means the persistent address exists and the host is not
   available. If the original `activateHost` was false or omitted, report that
   registration is complete and offline even if `preparation.phase` is `verified`;
   do not turn this into a hosting request. For an original requested and authorized
   `activateHost:true`, a verified preparation marker permits repetition of that
   same ready request. An older server may omit preparation metadata after your
   own `preparing` response: before the original deadline, allow at most one
   identical ready re-evaluation, without treating the offline result as verified
   or starting an unlimited reacquisition loop. Cancellation, expiry or refusal
   can fall back to draft/offline with no terminal record; absence of a marker is
   not a new grant. For a retryable host failure, retain the same intent and
   report/recover the actual dependency before retrying. Do not silently stop,
   re-pair, change audience, obtain credentials or broaden a grant.
6. `available` confirms the exact host serving handshake. Report the returned
   address, audience and actual status; creator entry uses ordinary navigation to
   that registered identity and is a separate step. Remote visitor entry,
   reciprocal movement and direct/relay behavior still need their own evidence.

Reuse the original request after a lost response; never allocate a new intent
on every poll. Stop automatic continuation and report cancellation, expired or
revoked authority, a closed/changed legacy session, stale/conflicting intent,
version conflict, wrong package/audience/profile or another required host action.
Do not retry an unchanged permanent refusal as though it were progress. If the
user requests cancellation, the exposed preparation-cancel tool cancels only the
pending preparation in its granted scope; it preserves registration and does not
stop an already authorized host. Restart preserves the address when the hub uses
its durable JSON store; live receiver, host and room authority must be established
again. The host must remain running for visitors to enter.


## Validate's world checks

The spawn, terrain and tonemap WARNs (`AGENT_KIT.md`, after "Always look at the
screenshots") come from `scripts/kit/world_checks.gd`, called by `world_view.gd`.
`validate` builds the world bare (no environment, NPCs, creatures, sounds, portals
or triggers), reads where each stated spawn lands with the builder's own ground
query (`WorldGround.height_at`, the same search the browser's spawn drop uses) and
tests a standing visitor's capsule (0.3 m radius, knee 0.35 m to head 1.75 m)
against the colliders. The tonemap estimate is albedo x (sun facing the surface +
ambient) x exposure against the builder's linear tonemap: specular glints and
textures are not counted, so a WARN-free colour can still read bright in the
preview. Unit test: `tests/kit_world_checks/run.sh` (headless, no browser).
