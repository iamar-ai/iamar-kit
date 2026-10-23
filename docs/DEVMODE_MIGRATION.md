# Developer mode migration: status and acceptance criteria

## Verified source snapshot

This is a source-only assessment from 2026-10-22 UTC, not a runtime or release
qualification. Recheck both repositories before changing the availability claim.

- Kit [0ac2d646d33f4fbedb77df1f8f0d4b9297ee890a](https://github.com/iamar-ai/iamar-kit/commit/0ac2d646d33f4fbedb77df1f8f0d4b9297ee890a)
  retires `kit/app`; this tree has no `kit_ui/` implementation.
- Browser [54f8568d26ccec5d2cf09f316c945ae96a109a65](the iamar browser source (not public)):
  [DEVELOPER_MODE.md](the iamar browser source (not public))
  says the setting works, but download and panels are planned.
  [DEVMODE_DESIGN.md](the iamar browser source (not public))
  places panels in the kit pack and download/mount integration in the browser.
- Browser `scripts/devmode/settings.gd`, `kit_mount.gd` and `panel_account.gd`
  provide scaffolding. Mount returns immediately for the same already-mounted
  path, without rechecking even a nonempty supplied hash. Otherwise it checks a
  nonempty supplied hash and uses `load_resource_pack(pack, false)`; this is not
  a completed download path.
  This browser tree has no `scripts/kit/kit_pin.json`.
  `scripts/kit/kit_loop.gd::ensure_tool` does not yet perform the design's pin check.
- Browser `scripts/ui/account_page.gd` already bounds HTTP replies to 1 MiB,
  uses a 15-second timeout, refuses redirects, caps each rendered list at 200 rows,
  suppresses concurrent refreshes and duplicate name-registration submissions.
  Its post-await refresh checks tree membership, not session identity; sign-out
  does not invalidate that request. Name availability requests are not sequenced.
  These are static observations, not reproduced runtime results.
- Browser `scripts/host/world_host_core.gd` already bounds work per poll and relay
  queue size and applies an upload budget. `scripts/shell/self_host.gd` binds
  asynchronous creator operations to a generation and instance.
  These native protections do not establish parity with the retired app.

## Acceptance checklist (not completed)

Use tests against the actual replacement, not the deleted Node app. Record the
kit/browser commits, test commands, results and platform for each completed item.
Historical app tests are regression requirements, not proof of native behavior.

- [ ] **Availability:** the shipped pack contains the panel entry point and the
  browser opens it. Exercise folder selection, validate, preview, sign/pack,
  registration, hosting, off/on and restart. Keep CLI use supported meanwhile.
- [ ] **Stale replies:** delay account, name, folder, validation and preview
  responses; change identity/folder, sign out, close/reopen, or start a newer
  operation. Retired results must not render, mutate current state or clear a
  newer operation's busy flag. Bound/cancel outstanding requests where supported.
- [ ] **Polling and bandwidth:** one in-flight status request per owner; bounded
  deadlines, quiet stopped/hidden states, and no duplicate polling on reopen.
  If native signals replace polling, test that no redundant network loop remains.
  Verify host upload limits and queue/response bounds under slow peers.
- [ ] **Preview and tool responsiveness:** bound output/log/image memory,
  release replaced preview resources, and keep heavy work off the UI thread.
  Test cancellation and supersession without publishing stale output.
- [ ] **Downloads:** stream with bounded memory, verify the pinned archive and
  pack before use, reuse a matching installation, coalesce identical downloads
  and serialize conflicting installs. Test interruption, corrupt bytes, disk
  failure and rollback without losing the previous good kit. Verify staging
  containment and pin checks on both UI and CLI entry points.
- [ ] **Lifecycle:** test start/stop/restart, sign-out, disconnect, shutdown and
  late callbacks against run/session identity. If HTTP heartbeats remain, bound
  and serialize them; timeout is uncertain delivery, not remote cancellation.
  If replaced by native lifecycle messages, test equivalent online/offline
  ordering and ownership. For child tools, distinguish process exit from closed
  output streams and do not let an old close release a new operation.
- [ ] **Qualification:** run relevant native tests and interrupted/repeated UI
  flows on supported platforms. Report missing CI, skipped checks and untested
  real services separately; synthetic/source checks are not end-to-end passes.

Historical comparison source:
[retired app at cc33ea0de2e54133289b36811c7880ae948efcef](https://github.com/iamar-ai/iamar-kit/tree/cc33ea0de2e54133289b36811c7880ae948efcef/kit/app),
especially `ui/index.html`, `lib/host.mjs` and `lib/browser-download.mjs`.
The checklist preserves relevant goals, not the old Node architecture.

Implementation changes to browser-owned files belong in `the iamar browser source (not public)` and
require a separately scoped review. This document neither restores the retired
app nor changes any download gate, deployment, account or payment behavior.
