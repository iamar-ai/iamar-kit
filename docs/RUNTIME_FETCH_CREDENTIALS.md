# Invitation codes in runtime launchers

## Download pass for agents (device code)

An agent cannot type the download password into the iamar.ai form, and its
person should not have to paste the password into an agent chat. Instead:

1. The agent runs `iamar-world download-login start`. It prints one line that
   begins `HUMAN STEP:` with a link (`https://iamar.ai/download/agent?code=...`)
   and a code such as `BCDF-GH23`. The agent shows both to its person.
2. **The person** opens the link in their own web browser, checks that it shows
   the same code, enters the download password if the page asks for it, and
   presses Allow. This is the only human step. The code works for ten minutes,
   once.
3. The agent runs `iamar-world download-login wait`. It gets a download pass
   and saves it in `~/.config/iamar/download_token` (Windows:
   `%APPDATA%\iamar\download_token`; `IAMAR_DOWNLOAD_TOKEN_FILE` moves it).
   The pass is never printed.
4. `kit/runtime_fetch.sh browser` (or any kit command that needs the browser)
   now downloads the iamar browser, sending the pass as
   `Authorization: Bearer <pass>`.

Both launchers are thin: `kit/download_login.sh` (Linux, macOS) and
`kit/download_login.cmd` (Windows PowerShell inside cmd) do the work.
`iamar-world download-login` with no argument does all three steps in one
command, for a person running it themselves. The pass lasts 30 days and stops
working when the download password changes; then run `download-login` again.
`IAMAR_DOWNLOAD_TOKEN=<pass>` in the environment is used before the file.

The pass opens only the gated downloads on iamar.ai (`/download/city/...` and
`/download/<os>`); it is not the password and cannot unlock anything else. The
launchers check its format (`iamar-dl1.<expiry>.<64 hex>`) before use and send
it to curl only through stdin (`-K -`), like the invitation code below. The
developer kit itself is public (decision 59) and needs neither.

Server side: `site/iamar_site_server.py` in https://iamar.ai
(`/download/agent/start`, `/download/agent`, `/download/agent/approve`,
`/download/agent/poll`). Until that server version is deployed, `download-login`
reports that iamar.ai does not offer agent downloads, and `IAMAR_KIT_CODE`
below still works.

    python3 -I tests/download_token/test_download_login.py -v

runs the bash (and on Windows the cmd) launcher end to end against a local fake
of those routes; `IAMAR_SITE_SERVER=<path to iamar_site_server.py>` runs it
against the real server code instead.

## Invitation code (IAMAR_KIT_CODE)

`IAMAR_KIT_CODE` is the download gate's opaque password, used as the HTTP
Basic password with user `kit`. It is needed only for an uncached runtime
whose pinned URL begins with `https://iamar.ai/`. The gate hashes the supplied
UTF-8 password verbatim; it does not specify a restricted invitation-code
alphabet. Do not trim codes or reject punctuation, spaces, or Unicode merely
to simplify quoting.

The Bash launcher escapes backslashes, double quotes, tab, newline, carriage
return, and vertical tab in curl's quoted configuration syntax. The resulting
single `user` setting goes to curl through stdin. Shell tracing is disabled
before the code is read.

The Windows launcher never expands the code into cmd syntax. A fixed Windows
PowerShell command reads the environment directly, performs the same escaping,
and sends UTF-8 configuration to curl's stdin. The code is not a command-line
argument or a temporary file. PowerShell runs without profiles or interaction;
it does not bypass execution policy. A PowerShell failure or curl failure
leads to the existing download-failure path. Windows PowerShell is included
in the supported Windows 10 1803+ baseline; environments that disable it must
provide a runtime through an already-supported local/runtime path.

Both curl invocations use `-q` first, so a per-user curlrc cannot introduce
tracing, additional destinations, or changes to credential forwarding. This
also means runtime fetches no longer use other curlrc customization. Curl's
normal environment settings, including supported proxy/CA settings, still
apply. No credential is added to the URL or argv. Avoid storing real invitation
codes in shell history, committed files, or diagnostic output yourself.

## Focused checks

From the repository root:

    python3 -I tests/runtime_fetch_security/test_inert.py -v

This runs Python source contracts and a strict curl-config parser/model only.
For the optional isolated Bash formatter checks:

    python3 -I tests/runtime_fetch_security/test_inert.py --bash -v

The optional checks extract only an exact allowlisted formatter body. They run
it using `/bin/bash --noprofile --norc`, an empty PATH, a clean environment,
synthetic codes, captured output, and a five-second subprocess timeout. They
do not source or run the runtime launcher. No curl, PowerShell, Windows cmd,
network request, extraction, browser/runtime execution, account operation,
deployment, or real credential is used. Test strings are public synthetic data.

Windows assertions and the escaping model are source/model evidence, not a
native Windows or PowerShell result. Native Windows command parsing, encoding,
and error propagation still need platform qualification. These focused checks
are not a release or end-to-end download qualification.

## Boundaries unchanged

The lock file, installed kit, selected executables on PATH, runtime directory,
and operating-system environment remain trusted local inputs. The checksum,
cache marker, staging, extraction, and replacement code is unchanged. This
change does not validate untrusted archives or malicious runtime.lock entries,
rehash cached programs, solve cross-process races, or qualify rollback and
native filesystem behavior. It also does not make other cmd-expanded paths
safe to obtain from an untrusted party. The app's Node-based download path is
separate from these launchers.

Sources:

- [Download gate password handling](https://iamar.ai)
- [curl config syntax](https://curl.se/docs/manpage.html#-K)
- [curl default-config disabling](https://curl.se/docs/manpage.html#-q)
- [PowerShell environment access](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_environment_variables?view=powershell-5.1)
