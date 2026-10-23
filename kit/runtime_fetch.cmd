@echo off
rem Fetch a runtime the kit needs when this computer has none: the pinned Node.js or the iamar
rem browser that runs the kit commands (Windows twin of kit/runtime_fetch.sh). Pins and sha256
rem sums are the win-x64 / win-arm64 lines of kit/runtime.lock.
rem   runtime_fetch.cmd node^|browser   prints the runtime's executable; fetches it once into
rem                                    kit\runtime\<name>\ (sha256-checked) when it is missing.
rem IAMAR_KIT_RUNTIME=<dir> puts runtimes elsewhere; IAMAR_KIT_NO_FETCH=1 never downloads.
rem The browser comes from the invitation-only iamar.ai: the download pass from `iamar-world
rem download-login` (IAMAR_DOWNLOAD_TOKEN or its file) or the password in IAMAR_KIT_CODE.
rem Uses only what ships with Windows 10 1803+: curl.exe, certutil, tar.exe and Windows PowerShell.
setlocal EnableExtensions DisableDelayedExpansion
set "HERE=%~dp0"
set "NAME=%~1"
rem Never echo NAME: cmd.exe would run any & | < > in it as a command, sec job kit-5.
if /i not "%NAME%"=="node" if /i not "%NAME%"=="browser" (
  echo runtime_fetch: unknown runtime ^(use node or browser^) 1>&2
  exit /b 2
)
set "BASE=%IAMAR_KIT_RUNTIME%"
if not defined BASE set "BASE=%HERE%runtime"
for %%I in ("%BASE%") do set "BASE=%%~fI"
set "DEST=%BASE%\%NAME%"
rem a 32-bit cmd on 64-bit Windows reports x86 here and the real machine in PROCESSOR_ARCHITEW6432
set "ARCH=%PROCESSOR_ARCHITEW6432%"
if not defined ARCH set "ARCH=%PROCESSOR_ARCHITECTURE%"
set "PLATFORM="
if /i "%ARCH%"=="AMD64" set "PLATFORM=win-x64"
if /i "%ARCH%"=="ARM64" set "PLATFORM=win-arm64"
if not defined PLATFORM (
  echo runtime_fetch: unsupported machine %ARCH% 1>&2
  exit /b 2
)
set "VERSION="
for /f "usebackq eol=# tokens=1-6" %%a in ("%HERE%runtime.lock") do (
  if /i "%%a"=="%NAME%" if /i "%%b"=="%PLATFORM%" if not defined VERSION (
    set "VERSION=%%c"
    set "URL=%%d"
    set "SUM=%%e"
    set "TOP=%%f"
  )
)
if not defined VERSION (
  echo runtime_fetch: no %NAME% runtime for %PLATFORM% in kit\runtime.lock 1>&2
  exit /b 3
)
if not "%URL:~0,8%"=="https://" (
  echo runtime_fetch: %NAME% url in kit\runtime.lock is not https 1>&2
  exit /b 3
)

call :exe
set "CUR="
if exist "%DEST%\.runtime" set /p CUR=<"%DEST%\.runtime"
if "%CUR%"=="%VERSION% %SUM%" if exist "%EXE%" goto done
if "%IAMAR_KIT_NO_FETCH%"=="1" (
  echo runtime_fetch: %NAME% is missing and IAMAR_KIT_NO_FETCH=1 1>&2
  exit /b 3
)
if not exist "%BASE%\" mkdir "%BASE%" || exit /b 3
set "TMPD=%BASE%\.fetch.%RANDOM%%RANDOM%"
mkdir "%TMPD%" || exit /b 3
for %%U in ("%URL%") do set "ARCHIVE=%TMPD%\%%~nxU"
echo iamar kit: fetching %NAME% %VERSION% for %PLATFORM% (once) from %URL% 1>&2
rem iamar.ai downloads sit behind the invitation gate. First choice: the download pass that
rem `iamar-world download-login` saved (a Bearer header; PowerShell checks its format and reads it
rem from the environment, never from cmd syntax). Else the code is the HTTP Basic password.
set "TFILE=%IAMAR_DOWNLOAD_TOKEN_FILE%"
if not defined TFILE set "TFILE=%APPDATA%\iamar\download_token"
set "HAVE_PASS="
if defined IAMAR_DOWNLOAD_TOKEN set "HAVE_PASS=1"
if exist "%TFILE%" set "HAVE_PASS=1"
if /i "%URL:~0,17%"=="https://iamar.ai/" if defined HAVE_PASS (
  "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference = 'Stop'; $t = $env:IAMAR_DOWNLOAD_TOKEN; if (-not $t) { $t = Get-Content -LiteralPath $env:TFILE -TotalCount 1 }; $t = ([string]$t).Trim(); if ($t -notmatch '^iamar-dl1[.][0-9]+[.][0-9a-f]{64}$') { exit 200 }; ('header = ' + [char]34 + 'Authorization: Bearer ' + $t + [char]34) | & ($env:SystemRoot + '\System32\curl.exe') -q -fL --retry 3 --proto '=https' -K - -o $env:ARCHIVE $env:URL; exit $LASTEXITCODE" 1>&2
  if errorlevel 200 (
    echo runtime_fetch: the saved download pass is malformed: run iamar-world download-login again 1>&2
    set "RC=3" & goto fail
  )
  if errorlevel 1 (
    echo runtime_fetch: iamar.ai refused the download pass ^(it lasts 30 days and ends when the download password changes^): run iamar-world download-login again 1>&2
    set "RC=3" & goto fail
  )
  goto fetched
)
if /i "%URL:~0,17%"=="https://iamar.ai/" (
  if not defined IAMAR_KIT_CODE (
    echo runtime_fetch: %NAME% comes from iamar.ai, which is invitation-only. 1>&2
    echo   HUMAN STEP: run iamar-world download-login and approve it in your web browser ^(your agent can run it and show you the link^), 1>&2
    echo   or set IAMAR_KIT_CODE=your-download-password; then run again 1>&2
    set "RC=3" & goto fail
  )
  rem Never expand the code in cmd syntax. PowerShell reads it directly from the environment,
  rem escapes curl's quoted config syntax, and sends UTF-8 only through curl's stdin.
  rem -q must be first so a user curlrc cannot add tracing or change credential handling.
  "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference = 'Stop'; $OutputEncoding = [System.Text.UTF8Encoding]::new($false); $c = $env:IAMAR_KIT_CODE; $c = $c.Replace('\', '\\').Replace([string][char]34, ('\' + [char]34)).Replace([string][char]9, '\t').Replace([string][char]10, '\n').Replace([string][char]13, '\r').Replace([string][char]11, '\v'); ('user = ' + [char]34 + 'kit:' + $c + [char]34) | & ($env:SystemRoot + '\System32\curl.exe') -q -fL --retry 3 --proto '=https' -K - -o $env:ARCHIVE $env:URL; exit $LASTEXITCODE" 1>&2
) else (
  "%SystemRoot%\System32\curl.exe" -q -fL --retry 3 --proto =https -o "%ARCHIVE%" "%URL%" 1>&2
)
if errorlevel 1 (
  echo runtime_fetch: download of %NAME% failed 1>&2
  set "RC=3" & goto fail
)
:fetched
rem certutil prints a header line, the hash (spaced on older Windows), then a status line
set "GOT="
for /f "skip=1 delims=" %%H in ('%SystemRoot%\System32\certutil.exe -hashfile "%ARCHIVE%" SHA256') do if not defined GOT set "GOT=%%H"
if defined GOT set "GOT=%GOT: =%"
if /i not "%GOT%"=="%SUM%" (
  echo runtime_fetch: %NAME% download sha256 %GOT% does not match kit\runtime.lock ^(%SUM%^); not installed 1>&2
  set "RC=4" & goto fail
)
mkdir "%TMPD%\x"
"%SystemRoot%\System32\tar.exe" -xf "%ARCHIVE%" -C "%TMPD%\x" 1>&2
if errorlevel 1 (
  echo runtime_fetch: could not unpack %ARCHIVE% 1>&2
  set "RC=4" & goto fail
)
rem top "." keeps the whole archive
set "SRC=%TMPD%\x"
if not "%TOP%"=="." set "SRC=%TMPD%\x\%TOP%"
if not exist "%SRC%\" (
  echo runtime_fetch: the %NAME% archive has no %TOP%\ folder 1>&2
  set "RC=4" & goto fail
)
>"%SRC%\.runtime" echo %VERSION% %SUM%
if exist "%DEST%.old\" rd /s /q "%DEST%.old"
if exist "%DEST%\" move "%DEST%" "%DEST%.old" >nul || (set "RC=4" & goto fail)
move "%SRC%" "%DEST%" >nul || (set "RC=4" & goto fail)
if exist "%DEST%.old\" rd /s /q "%DEST%.old"
rd /s /q "%TMPD%"
call :exe
if not exist "%EXE%" (
  echo runtime_fetch: %NAME% unpacked but %EXE% is missing 1>&2
  exit /b 4
)
echo iamar kit: %NAME% %VERSION% ready in %DEST% 1>&2
:done
for %%E in ("%EXE%") do echo %%~E
exit /b 0

:fail
if exist "%TMPD%\" rd /s /q "%TMPD%"
exit /b %RC%

rem The runtime's executable inside DEST (the browser export may be named iamar or Oakhaven).
:exe
if /i "%NAME%"=="node" (set "EXE=%DEST%\node.exe" & exit /b 0)
set "EXE=%DEST%\Oakhaven.exe"
if exist "%DEST%\iamar.exe" set "EXE=%DEST%\iamar.exe"
exit /b 0
