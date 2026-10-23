# Sign-in response ordering

Device sign-in responses can arrive after a newer attempt or sign-out. The hub
client now discards superseded polls before installing a token. The core checks
both request generation and pending-attempt identity before saving a session,
changing the username, or clearing pending state. Polls pause while a replacement
start is unresolved, so the old code cannot borrow the new request generation.
A rejected replacement can preserve the old valid attempt, but only a fresh poll
after it settles may authenticate that attempt. Sign-out cancels pending work
before awaiting host shutdown; duplicate sign-outs share one operation.

The UI separately guards its start requests and polling timers. An old response
cannot open an obsolete link, stop a newer timer, hide a newer code, or refresh
the account after sign-out. Only one poll is in flight per UI attempt, preventing
a duplicate response from overtaking the current approval. A current terminal
response invalidates queued callbacks. The existing URL-safety checks remain in place.

Existing method arguments and successful results are unchanged. Cancelled polls
return `{ status: "none" }`; cancelled starts reject with `signin_cancelled`.
A new start during sign-out rejects with `signout_pending` so the user can retry
after logout finishes. A host-stop error still attempts logout and clears local
auth state, while reporting the host error to its caller.

## Synthetic qualification

All 47 candidate cases passed on Linux/Node 24.19.0, both before and after
rebasing onto the published per-attempt output-directory changes. The unchanged
baseline passed 6 of 35 new lifecycle cases and failed 29 contract assertions;
these are regression cases, not a count of independent vulnerabilities. All
source hashes were unchanged before and after the reviewed runs.

The regressions in `auth_lifecycle.test.mjs` use deferred fake hub responses and
in-memory session/host spies. `auth_ui_lifecycle.test.mjs` evaluates only the
actual sign-in UI section in a VM with inert timers, DOM, navigation, and request
doubles. They cover 23 core/hub cases and 12 UI cases. Existing sign-in URL tests
provide 12 additional compatibility cases. These files do not open a real
account, run a runtime, create credentials, or write a real session.

Cancelling a response does not abort an issued network request or revoke a token
that the remote service may already have issued. These regressions do not
qualify remote revocation, stalled network requests, native browser behavior,
or unrelated account-refresh and registration races.
