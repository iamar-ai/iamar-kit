#!/usr/bin/env python3
"""Source contracts and optional isolated Bash formatter checks; no runtime fetching.

Default: Python text checks/models only. --bash additionally starts /bin/bash with
an exact allowlisted formatter, an empty PATH, and synthetic environment input.
No production launcher, curl, PowerShell, network, archive tool, or runtime runs.
"""
import argparse
import re
import subprocess
import unittest
from pathlib import Path


PARSER = argparse.ArgumentParser()
PARSER.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
PARSER.add_argument("--bash", action="store_true")
ARGS, UNITTEST_ARGS = PARSER.parse_known_args()
ROOT = ARGS.source_root.resolve()
SH = (ROOT / "kit/runtime_fetch.sh").read_text(encoding="utf-8")
CMD = (ROOT / "kit/runtime_fetch.cmd").read_text(encoding="utf-8")

BASH_FORMATTER = r'''curl_user_config() {
  local escaped="$code"
  escaped="${escaped//\\/\\\\}"
  escaped="${escaped//\"/\\\"}"
  escaped="${escaped//$'\t'/\\t}"
  escaped="${escaped//$'\n'/\\n}"
  escaped="${escaped//$'\r'/\\r}"
  escaped="${escaped//$'\v'/\\v}"
  printf 'user = "kit:%s"\n' "$escaped"
}'''

# The download pass (iamar-world download-login, an internal task): format-checked, then a header on curl's stdin.
TOKEN_PS_SCRIPT = r'''$ErrorActionPreference = 'Stop'; $t = $env:IAMAR_DOWNLOAD_TOKEN; if (-not $t) { $t = Get-Content -LiteralPath $env:TFILE -TotalCount 1 }; $t = ([string]$t).Trim(); if ($t -notmatch '^iamar-dl1[.][0-9]+[.][0-9a-f]{64}$') { exit 200 }; ('header = ' + [char]34 + 'Authorization: Bearer ' + $t + [char]34) | & ($env:SystemRoot + '\System32\curl.exe') -q -fL --retry 3 --proto '=https' -K - -o $env:ARCHIVE $env:URL; exit $LASTEXITCODE'''
PS_SCRIPT = r'''$ErrorActionPreference = 'Stop'; $OutputEncoding = [System.Text.UTF8Encoding]::new($false); $c = $env:IAMAR_KIT_CODE; $c = $c.Replace('\', '\\').Replace([string][char]34, ('\' + [char]34)).Replace([string][char]9, '\t').Replace([string][char]10, '\n').Replace([string][char]13, '\r').Replace([string][char]11, '\v'); ('user = ' + [char]34 + 'kit:' + $c + [char]34) | & ($env:SystemRoot + '\System32\curl.exe') -q -fL --retry 3 --proto '=https' -K - -o $env:ARCHIVE $env:URL; exit $LASTEXITCODE'''

# These are inert public test strings, never real invitation codes.
VALUES = (
    "fixture-plain-123", " leading and trailing ", 'fixture"quote',
    "fixture\\path\\", "fixture\\n\\r\\t\\v", "fixture\ttab",
    "fixture\nnew\nlines\n", "fixture\rcarriage", "fixture\vvertical",
    'fixture"\nurl = "https://invalid.example/"\noutput = "changed',
    'fixture" & echo SHOULD_NOT_RUN | rem %PATH% !value! ^ < > ( )',
    "fixture$(echo SHOULD_NOT_RUN)`echo SHOULD_NOT_RUN`;:*?#=",
    "fixture-café-邀請-🙂", "fixture:colon:password", "fixture\x01\x1f\x7f",
)


def encode_model(code):
    """Documented curl config escaping; a model, not a PowerShell execution."""
    for old, new in (("\\", "\\\\"), ('"', '\\"'), ("\t", "\\t"),
                     ("\n", "\\n"), ("\r", "\\r"), ("\v", "\\v")):
        code = code.replace(old, new)
    return 'user = "kit:' + code + '"\n'


def decode_one_user(text):
    """Strictly accept one quoted user directive, with curl's six escapes only."""
    if not text.startswith('user = "') or not text.endswith('"\n'):
        raise ValueError("expected one quoted user setting")
    body = text[len('user = "'):-2]
    escapes = {"\\": "\\", '"': '"', "t": "\t", "n": "\n", "r": "\r", "v": "\v"}
    result = []
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\":
            index += 1
            if index >= len(body) or body[index] not in escapes:
                raise ValueError("unsupported escape")
            result.append(escapes[body[index]])
        elif char in '"\r\n':
            raise ValueError("unescaped config delimiter")
        else:
            result.append(char)
        index += 1
    return "".join(result)


class SourceContracts(unittest.TestCase):
    def test_bash_formatter_is_the_reviewed_builtin_only_body(self):
        self.assertIn(BASH_FORMATTER + "\n", SH)

    def test_bash_disables_tracing_before_reading_code(self):
        read = SH.index('code="${IAMAR_KIT_CODE:-}"')
        self.assertLess(SH.index("\nset +x\n"), read)
        self.assertNotRegex(SH[read:], r"set\s+[^\n]*-x")

    def test_bash_credentials_use_stdin_and_curl_defaults_are_disabled(self):
        self.assertIn("curl_user_config | curl -q -fL", SH)
        self.assertNotIn("printf 'user = \"kit:%s\"\\n' \"$code\"", SH)
        for match in re.finditer(r"\bcurl\s+(-[^\n]+)", SH):
            self.assertTrue(match.group(1).startswith("-q "))
        self.assertNotRegex(SH, r"curl[^\n]*(?:\$code|\$escaped|IAMAR_KIT_CODE)")

    def test_windows_never_expands_invitation_code_in_cmd(self):
        self.assertNotRegex(CMD, r"(?i)%IAMAR_KIT_CODE%|!IAMAR_KIT_CODE!")
        self.assertIn("if not defined IAMAR_KIT_CODE (", CMD)
        self.assertIn("DisableDelayedExpansion", CMD)

    def test_windows_fixed_powershell_program_reads_env_and_propagates_curl_exit(self):
        scripts = re.findall(r'powershell\.exe" -NoLogo -NoProfile -NonInteractive -Command "([^"\n]+)" 1>&2', CMD)
        self.assertEqual(scripts, [TOKEN_PS_SCRIPT, PS_SCRIPT])
        for script in scripts:
            self.assertNotIn("%", script)
            self.assertNotIn("!", script)
            self.assertIn("if errorlevel 1 (", CMD[CMD.index(script):])

    def test_download_pass_is_format_checked_and_only_sent_on_stdin(self):
        self.assertNotRegex(CMD, r"(?i)%IAMAR_DOWNLOAD_TOKEN%|!IAMAR_DOWNLOAD_TOKEN!")
        self.assertIn("-notmatch '^iamar-dl1[.][0-9]+[.][0-9a-f]{64}$') { exit 200 }", TOKEN_PS_SCRIPT)
        self.assertLess(TOKEN_PS_SCRIPT.index("exit 200"), TOKEN_PS_SCRIPT.index("curl.exe') -q -fL"))
        check = SH.index(r'"$token" =~ ^iamar-dl1\.[0-9]+\.[0-9a-f]{64}$')
        self.assertLess(SH.index("\nset +x\n"), SH.index('token="${IAMAR_DOWNLOAD_TOKEN:-}"'))
        self.assertLess(check, SH.index(r"""printf 'header = "Authorization: Bearer %s"\n' "$token" | curl -q -fL"""))
        self.assertNotRegex(SH, r"curl[^\n]*\$token")

    def test_no_credential_files_or_argument_auth_options_are_added(self):
        for source in (SH, CMD):
            self.assertNotRegex(source, r"(?:--user|--header|--data|-u)\s+")
            self.assertNotIn("--location-trusted", source)
            self.assertIn("-K -", source)
        self.assertIn("curl.exe\" -q -fL", CMD)

    def test_origin_guards_are_exact_and_similar_domains_are_not_gated(self):
        self.assertIn('case "$url" in https://iamar.ai/*)', SH)
        self.assertIn('if /i "%URL:~0,17%"=="https://iamar.ai/" (', CMD)
        prefix = "https://iamar.ai/"
        self.assertEqual(len(prefix), 17)
        for value in ("https://iamar.ai.evil.example/x", "https://iamar.ai@evil.example/x", "http://iamar.ai/x"):
            self.assertFalse(value.startswith(prefix))

    def test_missing_code_and_no_fetch_remain_fail_closed(self):
        self.assertIn('[[ -n "$token" || -n "$code" ]] || { echo "runtime_fetch:', SH)
        self.assertIn('IAMAR_KIT_NO_FETCH:-0', SH)
        self.assertIn('set "RC=3" & goto fail', CMD)
        self.assertLess(SH.index('IAMAR_KIT_NO_FETCH:-0'), SH.index('curl_user_config()'))
        self.assertLess(CMD.index('if "%IAMAR_KIT_NO_FETCH%"=="1"'), CMD.index('powershell.exe'))

    def test_checksum_precedes_extraction_and_install(self):
        self.assertLess(SH.index('[[ "$got" == "$sum" ]]'), SH.index('tar -xzf'))
        self.assertLess(SH.index('[[ "$got" == "$sum" ]]'), SH.index('mv -- "$src" "$dest"'))
        self.assertLess(CMD.index('if /i not "%GOT%"=="%SUM%"'), CMD.index('tar.exe" -xf'))
        self.assertLess(CMD.index('if /i not "%GOT%"=="%SUM%"'), CMD.index('move "%SRC%" "%DEST%"'))


class WindowsBinaryQualificationTests(unittest.TestCase):
    def test_launchers_never_run_unqualified_system_binaries(self):
        for name in ("runtime_fetch.cmd", "iamar-world.cmd", "download_login.cmd"):
            src = (ROOT / "kit" / name).read_text(encoding="utf-8")
            for n, line in enumerate(src.splitlines(), 1):
                if line.lstrip().lower().startswith("rem"):
                    continue
                self.assertNotRegex(line, r"(?i)(?:^|[\s(`'|&])(?:curl|certutil|tar|powershell|where|findstr)\.exe\s", f"{name}:{n}")
                self.assertNotRegex(line, r"(?i)(?:^|[`'|(])\s*(?:where|certutil|findstr)\s", f"{name}:{n}")

    def test_for_f_commands_never_start_with_a_quote(self):
        # for /f runs its command through cmd /c, which strips the first and last quote of a
        # command that starts with one and holds more: ('"%SystemRoot%\..." "%X%"') then fails
        # with "The system cannot find the path specified" (a4adfa9 broke the sha256 check,
        # the preview no-geometry guard and the Blender probe this way).
        for name in ("runtime_fetch.cmd", "iamar-world.cmd", "download_login.cmd"):
            src = (ROOT / "kit" / name).read_text(encoding="utf-8")
            for n, line in enumerate(src.splitlines(), 1):
                self.assertNotRegex(line, r"(?i)\bfor /f\b.*\bin \(\s*['`]\s*\"", f"{name}:{n}")


class ConfigModelTests(unittest.TestCase):
    def test_opaque_passwords_round_trip_without_new_directives(self):
        for index, value in enumerate(VALUES):
            with self.subTest(case=index):
                encoded = encode_model(value)
                self.assertEqual(encoded.count("\n"), 1)
                self.assertEqual(decode_one_user(encoded), "kit:" + value)

    def test_the_previous_raw_interpolation_is_not_safe(self):
        for value in ('fixture"quote', 'fixture"\nurl = "https://invalid.example/'):
            with self.assertRaises(ValueError):
                decode_one_user('user = "kit:' + value + '"\n')
        # A literal backslash sequence was also silently changed by curl before.
        value = "fixture\\ntext"
        self.assertNotEqual(decode_one_user('user = "kit:' + value + '"\n'), "kit:" + value)


@unittest.skipUnless(ARGS.bash, "optional Bash formatter execution requires --bash")
class BashFormatterTests(unittest.TestCase):
    def run_formatter(self, value, trace=False):
        # Reject changed source before spawning anything. Do not source the launcher.
        self.assertIn(BASH_FORMATTER + "\n", SH)
        program = 'set +x\ncode="${IAMAR_KIT_CODE:-}"\n' + BASH_FORMATTER + '\ncurl_user_config\n'
        args = ["/bin/bash", "--noprofile", "--norc"] + (["-x"] if trace else []) + ["-c", program]
        proc = subprocess.run(args, input=b"", capture_output=True, timeout=5, check=False,
                              env={"PATH": "", "LC_ALL": "C.UTF-8", "IAMAR_KIT_CODE": value})
        self.assertEqual(proc.returncode, 0, "isolated formatter failed")
        self.assertNotIn(value.encode("utf-8"), proc.stderr)
        self.assertNotIn(value, "\n".join(args))
        return proc.stdout.decode("utf-8"), proc.stderr

    def test_exact_bash_formatter_round_trips_all_synthetic_inputs(self):
        for index, value in enumerate(VALUES):
            with self.subTest(case=index):
                output, error = self.run_formatter(value)
                self.assertEqual(output, encode_model(value))
                self.assertEqual(decode_one_user(output), "kit:" + value)
                self.assertEqual(error, b"")

    def test_xtrace_does_not_print_the_synthetic_password(self):
        output, error = self.run_formatter('fixture-secret-"\\\n%-must-stay-private', trace=True)
        self.assertEqual(error, b"+ set +x\n")
        self.assertEqual(output.count("\n"), 1)


if __name__ == "__main__":
    unittest.main(argv=[__file__, *UNITTEST_ARGS])
