# Host My World: a player's self-hosting guide

You packed a world and now you want other people to visit it. This guide
covers the Esc-menu **Host My World** feature: turning it on, choosing who
may come in, how visitors reach you without you touching your router, the
world's shareable link, and how to stop or troubleshoot. No commands and no
config files are needed for the normal path.

If your world needs scripted behaviour, author it in **TypeScript** and follow
[WORLD_FORMAT.md section 10](WORLD_FORMAT.md#10-scripts) before packaging.
`kit/iamar-world compile-typescript` defaults to the pure-Node packer with a
prebuilt guest; only the optional `--from-source` route requires the Linux x86_64
source toolchain. Provide Node.js 20 or newer, and check the actual kit's
`kit/ts-world/TYPESCRIPT.md` for bundled or separately supplied TypeScript 5.9.3.
See [TYPESCRIPT_WORLDS.md](TYPESCRIPT_WORLDS.md) for wrapper paths and prerequisites.
The output package is `<fresh-out>/world/`; include its referenced assets, validate
and preview that folder, then sign and pack it. Hosting uses the finished signed
package, not `world.ts` or the compiler's build-output root. Compilation alone
does not qualify native hosting, a downloaded kit or visitor entry.

## Local folder tools: from your agent's files to a signed world

Creation has no quest prerequisite; the lessons are optional. At the
**Builders' Guild** desk, choose **Open local folder tools**. Local folder
work needs no account. Signing in, granting scoped agent access and hosting
remain separate choices.

1. If your agent already made the world, use **Choose world folder** and select
   the folder containing `manifest.json` and `scene.json`.
2. To make a starter instead, use **Choose parent folder**, fill in **New folder
   name**, **World id**, **World title** and **Author**, then choose **Create
   starter folder**. Use a new child folder name; the panel refuses an existing
   destination. This saves the same starter as `iamar-world new`, including
   `manifest.json`, `scene.json` and empty `assets/` and `scripts/` folders,
   then validates the saved files.
3. Use **Copy actual folder path for my agent** to give your agent the local
   path. The agent edits those files with the existing kit; the panel is not a
   scene editor. Opening the desk or copying a plan does not create a world.
4. Choose **Validate saved world** after edits. For TypeScript, have the agent
   compile first and choose the generated `<fresh-out>/world/` folder, with
   every referenced asset present. A **Validated folder (saved snapshot)**
   result covers the files checked then; revalidate after changes. Validation
   does not run scripts, preview gameplay, sign, or start hosting.
5. Have the agent validate and preview the final revision, then use the existing
   kit to sign and pack it with your approved signing key. The panel does not
   install compiler tools, create keys or perform these steps. Keep the resulting
   `.iamar` beside its matching, same-basename `.pieces.json`.
6. Choose **Import signed world (.iamar)** and select that package. Import
   verifies the signed pair and copies only those two files into the browser's
   worlds folder. A valid signature does not make an unknown signer trusted.
   On success, choose **Open Host My World with this package**. The imported
   package is selected, your current audience choice is retained, and hosting
   has not started. Review the audience and upload limit before **Start Hosting**.

You can also import directly in **Esc → Host My World**. An active host is not
replaced automatically: stop it deliberately before switching packages.
**Cancel pending file action** cancels a picker or pending validation and requests
cancellation of a cooperative UI import. Wait for the current step and file
cleanup to finish; closing or reopening the panel does not release an import
still finishing. Partial import files are retained, with a recovery path. Once
the package and final discovery list have been installed, cancellation cannot
undo them. Import never starts hosting automatically.

The UI importer yields between bounded raw hash/copy steps and uses the existing
validators. Its asynchronous package validator also hashes signed-file payloads
from immutable snapshots in at most 64 KiB steps, forcing a yield before more
than 256 KiB of payload copies or 64 verification steps accumulate. It checks
cancellation before each step and before returning a result. Source capture and
archive inflation, signature JSON/schema/key processing, path collection/sorting,
signing-text hashing, RSA/trusted-list checks, native I/O and asset decoding remain
indivisible. These source/model bounds do not guarantee or measure immediate
cancellation, total memory use or maximum frame delay.
Starter creation and command-line import remain synchronous. Failed creation
may leave partial files for inspection; choose a fresh destination for a new
attempt.

These instructions describe the [folder-panel source](../scripts/ui/local_creator_files_panel.gd)
and [shared importer](../scripts/host/local_world_install.gd). Native file-dialog
and cancellation checks, installed/exported Windows/macOS/Linux builds, and the
full creator-to-remote-visitor journey remain unrun for this workflow. A saved
folder or successful import is not evidence that another user can enter.

## Turning hosting on

1. Open the game menu with **Esc** and choose **Host My World** (it sits just
   above "Quit Game").
2. In the panel, pick your world with the **World** button. It lists your
   packed, signed worlds from your `my_worlds` folder. If yours is not listed,
   choose **Import signed world (.iamar)** and select the finished package;
   its matching `.pieces.json` must be beside it. Successful import refreshes
   the list and selects that exact installed package without starting a host
   or changing your audience choice. The command-line alternative remains
   `iamar-world add-to-browser <file.iamar>` after packing with the kit.
   Only that package file and its matching signed piece list are ever served.
3. Choose **who may visit** (see below) and the **upload** limit (see below).
4. Press **Start Hosting**. The status line walks through connecting to the
   hub, registering, and finally shows "Hosting ..." with the visitor count
   and how much data has been sent.

Your computer serves the world while Oakhaven is open. Visitors reach it
through the hub; you do not open router ports, set up port forwarding, or run
a second program. You can close the panel (Back, or Esc) and hosting keeps
running — the menu entry changes to **Host My World - Hosting** so you can
see at a glance that you are live. The panel also shows **Here now:** with
the names of your current visitors and the last few lines of the host log.

You must be logged in to iamar first: your account owns the world's address
on the hub.

## Access options: who may visit

The **Who may visit** button cycles through:

- **Everyone (listed)** — `public`. Anyone can find the world through the
  hub's lookup (looking someone up works without logging in, but it sees
  public worlds only) and join with your link.
- **My buddies** — `buddies`. Only people on your iamar buddy list are
  admitted; the hub applies the access check, so a visitor needs a signed-in
  iamar session.
- **Only me** — `private`. No one else may join. Useful for testing: only
  your own account can enter.

There is also a **guild** audience for hosted worlds, written
`guild:<name>` optionally followed by a minimum member level 1-4, e.g.
`guild:casinosalsa:2`. It restricts entry to members of the named guild at or
above that level. It is not on the panel's cycle button; it comes from the
saved `[selfhost] access` setting (or a creator pairing that prepared it).

## Upload cap: how much bandwidth your world may use

The **Upload** button cycles through four caps, in kilobytes per second:

- **no limit** (0)
- **256 KB/s**
- **1024 KB/s**
- **4096 KB/s**

This is a ceiling on how fast your computer serves world data to visitors. It
protects your connection while you play or do other things. There is no per-
visitor cap to configure separately.

Related, but separate: the hub only accepts a world package up to **512 MiB**
and pieces at most 64 KiB; bigger packages will not register (see
`docs/SELFHOST_DOCTOR.md` for preflight checks).

## Keeping a world online when the browser is closed

Hosting from the Esc menu ends when the browser closes. To keep a world up all the time, run it on an
always-on computer with `iamar-world serve`, which uses the same signed package and the same hub relay
(no port forwarding). Use it when the visitors are not only you and friends who ask first.

1. Pack and sign the world as usual, and copy the `.iamar` and its `.pieces.json` onto the always-on
   computer. Install the kit and the iamar browser there (see "The kit needs the iamar browser").
2. Store the hub password in a file only you can read, never in a command line or a unit file:
   `install -m 600 /dev/null ~/.config/iamar/host.pw`, then write the password into it.
3. Test it in a terminal first:

       iamar-world serve --package=$HOME/worlds/my_world-0.1.0.iamar \
         --hub=wss://hub.vessences.com --user=<account> \
         --password-file=$HOME/.config/iamar/host.pw --access=public --port=0

   `--port=0` serves through the hub relay only. Check the printed address, then visit it from a
   different computer on a different network.
4. On Linux, keep it running with a systemd user service (`~/.config/systemd/user/iamar-world.service`):

       [Unit]
       Description=iamar world host
       After=network-online.target
       Wants=network-online.target

       [Service]
       ExecStart=%h/iamar-kit/iamar-world serve --package=%h/worlds/my_world-0.1.0.iamar \
         --hub=wss://hub.vessences.com --user=<account> \
         --password-file=%h/.config/iamar/host.pw --access=public --port=0
       Restart=always
       RestartSec=15

       [Install]
       WantedBy=default.target

   Then `systemctl --user daemon-reload && systemctl --user enable --now iamar-world`, and
   `loginctl enable-linger $USER` so it keeps running when you log out. Read its log with
   `journalctl --user -u iamar-world -f`. On Windows, run the same command from Task Scheduler
   ("at startup", restart on failure).
5. To publish a new version, bump `version` in the manifest, pack and sign again, copy the new pair, change
   `--package` and restart the service. Stop it with `systemctl --user stop iamar-world`.

Status of this recipe: it uses only the options `AGENT_KIT.md` documents for `serve`. It has not been
run as a service on a real always-on computer yet, and the full journey from an always-on host to a
visitor on another network is still to be proven (see the unrun list above).

## Hub relay: why no port forwarding is needed

Hosting keeps **one authenticated WebSocket** open to the hub and registers
your world with `relay: true`, without publishing any public address or port.
When a visitor wants a world piece, the hub asks your browser over that same
connection (`relay-get`) and your browser answers with the bytes; the hub
forwards them on. The hub does not trust what your browser sends: it accepts
the piece list only if it is validly signed for the registered world, and
every returned piece must match the exact length and SHA-256 hash the list
declares, so a visitor can always verify what they receive. Player signaling
and live room traffic continue to use the normal room protocol or direct
WebRTC; the relay transports only the immutable signed world package.

Because everything rides over your existing outbound connection, a computer
behind a home router can host with all inbound ports closed. The relay is
rate-limited per world (default 60 HTTP requests/s per visitor address,
4 MiB/s forwarded per world, at most 16 requests in flight) so one busy world
does not starve the hub; if the relay is unavailable for your run, the panel
warns you ("this hub cannot relay: visitors cannot reach you").

Advanced option: the `[selfhost] port` setting (default `0`, relay only).
Give it a forwarded port if you *also* want visitors to be able to connect to
you directly, but the normal path needs nothing.

## The public alias link and the Copy button

Once hosting is running, the panel shows a **Copy link** button with your
world's free public link, which looks like

    iamar://<13 characters>

The 13-character alias is issued by the hub when the world registers. Press
the button once and the link goes to your clipboard ("Copied iamar://…").
Share it anywhere — chat, a web page, an email. Your world is also addressable
as `iamar://<your-name>/<world>`; the alias is the short form that never
changes across restarts as long as the world's name does.

The menu entry also shows your hosting state: **Host My World - Hosting**
when live, **Host My World - Resuming** while it reconnects, and
**Host My World - Needs Attention** when something failed.

## Auto-resume at startup

If you quit Oakhaven while hosting was on, it remembers: the `[selfhost] on`
setting stays true, and the next time the browser starts it resumes hosting
the same world with the same access and upload settings, with no extra
clicks. If the saved world file is missing or something else prevents the
resume, the menu shows **Host My World - Needs Attention** and the panel
explains what happened ("The saved world is missing. Open Host My World and
choose it again.").

Stopping hosting (below) clears the flag, so the next launch does not resume.

## What visitors see

A visitor opens your link or looks up your public world on the hub. The hub
applies the existence, access, and "is it running" checks — for non-public
worlds the visitor must be signed in to iamar — and then the visitor's
browser downloads the world's verified pieces through the hub relay and joins
the room. To the visitor it is an ordinary world visit; every piece is
verified against the signed list your world was packed with, so visitors are
protected whether the world runs on the hub or on your computer.

As the host, you see them arrive in the panel's **Here now:** line and in the
status ("Hosting … - N visitors, M MB sent").

## Stopping hosting

1. Open Esc and choose **Host My World** (it shows **- Hosting** while live).
2. Press **Stop Hosting**.

The world unregisters from the hub and current visitors are disconnected.
Hosting also stops automatically when the browser closes, and the auto-resume
flag is cleared so the next start comes up not hosting.

## Troubleshooting

- **The world list is empty.** The panel only lists packed, signed
  `<id>-<version>.iamar` packages (with their signed
  `<id>-<version>.pieces.json` beside them) in your `my_worlds` folder or a
  configured `[selfhost] dirs` entry. Pack with `iamar-world pack`, then use
  **Import signed world (.iamar)** or `iamar-world add-to-browser`.
- **Import failed.** Keep the `.iamar` and its matching signed `.pieces.json`
  together and unchanged during import. Unsigned, missing or mismatched files
  are refused. A different or incomplete installed package with the same world
  id/version is preserved; use a new version for changed content. An exact
  already-installed pair can be imported again safely.
- **Import reports retained partial files.** Inspect the reported recovery path
  and the worlds folder. A failed import leaves files in place, including a
  possible package whose piece list could not be settled. Preserve anything
  useful and explicitly move conflicting/retained files aside before retrying;
  the panel does not clear them for you or report them as a successful import.
- **"log in to iamar first".** Your account owns the world's address, so
  hosting needs a signed-in session. Log in, then start hosting.
- **"only worlds in your worlds folder can be hosted".** The world file must
  sit under `user://my_worlds` (or a configured directory); pick it from the
  panel list rather than typing a path.
- **The panel warns "(this hub cannot relay: visitors cannot reach you)".**
  Your host run registered but the hub cannot relay for it. Hosting on this
  path is relay-based; check your hub URL in settings and try again, or run
  `tools/selfhost_doctor.py` to diagnose the configuration.
- **Resume failed after a restart.** The saved world may have moved or been
  renamed. Open **Host My World**, pick it again, and press Start Hosting.
- **Suspect a setup problem.** Run the read-only preflight — it never starts
  a host, contacts no one, and shows no secrets:

      python3 tools/selfhost_doctor.py --world <path to your world.iamar>

  See `docs/SELFHOST_DOCTOR.md` for the full checklist (package signatures,
  the 512 MiB browser limit, settings, ports, and what each check means).
- **End-to-end self test (needs Godot, Node, and a display).** Developers can
  spin up a local hub, pack a small world, auto-resume hosting, and have a
  second instance visit through the relay in one command:

      tools/selfhost_test.sh

  It reports `PASS`/`FAIL` counts and where the logs live.

## The kit needs the iamar browser

The kit's tools run inside the iamar browser (`iamar --headless -- --kit <command>`), so a computer needs
one. The kit looks for it beside the kit folder, then in `IAMAR_BROWSER`, then in `kit/runtime/browser`
(where it puts the one it downloads). If there is none, or the one it finds is too old to have the kit
commands (an older browser starts the game and never answers), `iamar-world` stops with a plain message instead of
hanging. The download comes from iamar.ai, behind the invitation gate: set `IAMAR_KIT_CODE=<code>` before running `iamar-world` or `runtime_fetch`. On Linux it is one
AppImage file (no FUSE needed), on Windows a folder, on macOS an `iamar.app`.

## Hosting with Developer mode in the browser

The standalone Node kit desktop app is retired. Its replacement Developer mode
panels are **not yet an available end-to-end workflow** at the
[verified source snapshot](DEVMODE_MIGRATION.md#verified-source-snapshot).
The browser has an on/off setting and mount/account scaffolding, but no automatic
kit download or complete creator panels. Use the existing `iamar-world` commands
and **Host My World** workflow described above in the meantime.

The planned panels cover choosing a folder, validating and previewing, signing
and packing, registering, and hosting. The design reuses the browser account
token in its settings; it does not use the retired Node app's `session.json`.
Do not assume the old app's separate host process, 30-second heartbeat loop or
shutdown behavior describes the browser implementation.
See [DEVMODE_MIGRATION.md](DEVMODE_MIGRATION.md) for source evidence and the
safeguards to verify before claiming feature parity.

## .3d names

Besides the free alias, an account can hold names in iamar's own namespace, such as `mycafe.3d`. A
name resolves through the hub to one of your worlds; it is not a web domain and needs no DNS. For now
registering a name needs an invitation code (iamar.ai, My account, Register a name); payment is not
connected yet. Each account has an allowance of names and aliases (3 names and 32 aliases unless the
operator sets another), reserved words and brand names are refused, and a released name is never
issued again. Names can be pointed at another of your worlds, handed to another account, or released.
