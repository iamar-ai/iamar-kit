@echo off
rem iamar-world for Windows: the same commands as kit/iamar-world (bash), see
rem kit/AGENT_KIT.md. Uses the iamar browser (IAMAR_BROWSER) or a Godot 4.7
rem binary (GODOT, default godot.exe on PATH) plus this source tree (IAMAR_PROJECT).
setlocal EnableExtensions
rem Arguments are never run as cmd syntax (BatBadBut, sec job kit-5). This launcher expands
rem arguments into command lines, so an argument that holds & | < > ^ or % could run as a
rem command even when the caller quoted it. The raw arguments are read only inside a REM line
rem (echoed to a file, never executed) and the run is refused before anything else expands them.
rem Not fixable here: an unquoted & | < > that the caller's own cmd.exe splits off (a Python or
rem Node argv list with a quote and a space in one argument) runs before this file starts.
set "ARGV_FILE=%TEMP%\iamar-world-argv-%RANDOM%%RANDOM%.txt"
setlocal
set "prompt=@"
(
  echo on
  for %%a in (1) do rem #%*#
  @echo off
) >"%ARGV_FILE%"
endlocal
"%SystemRoot%\System32\findstr.exe" /r /c:"[&|<>^%%]" "%ARGV_FILE%" >nul
set "ARGV_RC=%ERRORLEVEL%"
del /q "%ARGV_FILE%" >nul 2>&1
if "%ARGV_RC%"=="1" goto argv_ok
echo iamar-world: refused: an argument holds one of ^& ^| ^< ^> ^^ %% which cmd.exe could run as a command. 1>&2
echo   Use names, titles and paths without these characters, or run kit/iamar-world from Git Bash or WSL. 1>&2
exit /b 2
:argv_ok
rem Keep literal exclamation marks in TypeScript paths, even under cmd /v:on.
if /i "%~1"=="compile-typescript" setlocal DisableDelayedExpansion
set "HERE=%~dp0"
set "CMD=%~1"
if "%CMD%"=="" set "CMD=help"
if not defined IAMAR_PROJECT for %%I in ("%HERE%..") do set "IAMAR_PROJECT=%%~fI"
rem --json (agents): one JSON object instead of text, with a fix hint on every ERROR/WARN and the
rem next command (kit\agent_output\README.md). Commands with their own JSON (doctor, lint, audit,
rem assets search, terrain, ...) take --json themselves. Human-mode runs end with a NEXT: line.
set "WANT_JSON="
if not defined IAMAR_KIT_OUTPUT_CHILD call :want_json %*
if defined WANT_JSON goto agent_json
rem download-login: a download pass for the invitation-only iamar browser (kit\download_login.cmd).
if /i "%CMD%"=="download-login" (
  call "%HERE%download_login.cmd" %2
  exit /b
)
rem TypeScript packing is independent of the browser and native command setup.
if /i "%CMD%"=="compile-typescript" goto cmd_compile_typescript
rem lint and compare-shots: style-profile checks in Python 3 (kit\lint), no browser needed.
if /i "%CMD%"=="lint" goto cmd_pylint
if /i "%CMD%"=="version" goto cmd_pylint
if /i "%CMD%"=="doctor" goto cmd_pylint
if /i "%CMD%"=="publish-local" goto cmd_pylint
if /i "%CMD%"=="compare-shots" goto cmd_pylint
rem shots: fixed-camera review sheets (kit\shots\shots.py); Python drives preview through this launcher.
if /i "%CMD%"=="shots" goto cmd_pylint
if /i "%CMD%"=="lowtier" goto cmd_pylint
rem audit: geometry audits (closure, zfight, roof, edge, door, dark-bake; kit\audit\audit.py), numpy only.
if /i "%CMD%"=="audit" goto cmd_pylint
rem style-gen: masterplan house, convex-wing roof and door arch from a style profile (kit\style\gen\gen.py).
if /i "%CMD%"=="style-gen" goto cmd_pylint
rem materials: painted material library, texel-density rule, texture budget (kit\style\materials\materials.py).
if /i "%CMD%"=="materials" goto cmd_pylint
if /i "%CMD%"=="terrain" goto cmd_pylint
rem assets search: the object catalogue (kit\catalog\catalog.py, by description), no browser needed;
rem assets search --worlds: objects in downloaded worlds (the browser's own search).
if /i "%CMD%"=="assets" if /i "%~2"=="search" if /i not "%~3"=="--worlds" if exist "%HERE%catalog\catalog.json" goto cmd_pylint
rem assets use: a catalogue object made for iamar is copied by kit\catalog\catalog.py (with its tier
rem files); built-ins and downloaded-world objects (its exit 3) go on to the browser, which references them by hash.
set "CATALOG_RC="
if /i "%CMD%"=="assets" if /i "%~2"=="use" if exist "%HERE%catalog\catalog.json" call :catalog_use %*
if defined CATALOG_RC exit /b %CATALOG_RC%
rem assets ref: reference a public catalogue object by hash instead of carrying it (kit\catalog\refs.py,
rem docs\CATALOG_PACKS.md). package/pack: refs.py first checks every catalogue reference and copy
rem (hash, licence, attribution, release); skipped when there is no Python.
if /i "%CMD%"=="assets" if /i "%~2"=="ref" if exist "%HERE%catalog\refs.py" goto cmd_pylint
if /i "%CMD%"=="assets" if /i "%~2"=="fetch" if exist "%HERE%catalog\packs.py" goto cmd_pylint
set "REFS_RC="
if /i "%CMD%"=="package" if exist "%HERE%catalog\refs.py" if exist "%~2\manifest.json" call :refs_check "%~2"
if /i "%CMD%"=="pack" if exist "%HERE%catalog\refs.py" if exist "%~2\manifest.json" call :refs_check "%~2"
if defined REFS_RC exit /b %REFS_RC%
rem The kit tools ship as iamar-kit.pck beside this launcher; the browser mounts it on demand.
if not defined IAMAR_KIT_PACK if exist "%HERE%iamar-kit.pck" set "IAMAR_KIT_PACK=%HERE%iamar-kit.pck"
rem Prefer the current export name, then the legacy browser name beside this kit.
if not defined IAMAR_BROWSER if not exist "%IAMAR_PROJECT%\project.godot" if exist "%HERE%..\iamar.exe" if not exist "%HERE%..\iamar.exe\" for %%I in ("%HERE%..\iamar.exe") do set "IAMAR_BROWSER=%%~fI"
if not defined IAMAR_BROWSER if not exist "%IAMAR_PROJECT%\project.godot" if exist "%HERE%..\Oakhaven.exe" for %%I in ("%HERE%..\Oakhaven.exe") do set "IAMAR_BROWSER=%%~fI"
rem The two homepage downloads unzipped side by side: <dir>\kit\ and <dir>\iamar\iamar.exe.
if not defined IAMAR_BROWSER if not exist "%IAMAR_PROJECT%\project.godot" if exist "%HERE%..\iamar\iamar.exe" if not exist "%HERE%..\iamar\iamar.exe\" for %%I in ("%HERE%..\iamar\iamar.exe") do set "IAMAR_BROWSER=%%~fI"
rem A kit downloaded on its own: use (or fetch once) the pinned iamar browser in kit\runtime\.
if not defined IAMAR_BROWSER if not exist "%IAMAR_PROJECT%\project.godot" if /i not "%CMD%"=="help" if /i not "%CMD%"=="where" if /i not "%CMD%"=="blender" if /i not "%CMD%"=="blender-run" for /f "usebackq delims=" %%P in (`call "%HERE%runtime_fetch.cmd" browser`) do set "IAMAR_BROWSER=%%P"
if not defined IAMAR_BROWSER if not exist "%IAMAR_PROJECT%\project.godot" if /i not "%CMD%"=="help" if /i not "%CMD%"=="where" if /i not "%CMD%"=="blender" if /i not "%CMD%"=="blender-run" (
  echo iamar-world: no iamar.exe beside this kit folder ^(looked for %HERE%..\iamar.exe and %HERE%..\iamar\iamar.exe^). 1>&2
  echo   Unzip the browser download next to the kit folder ^(kit\ and iamar\iamar.exe side by side^), 1>&2
  echo   set IAMAR_BROWSER=C:\path\to\iamar.exe ^(or, in a source checkout, GODOT and IAMAR_PROJECT^), 1>&2
  echo   or let kit\runtime_fetch.cmd browser fetch it ^(needs the network; IAMAR_KIT_NO_FETCH unset^). 1>&2
  exit /b 2
)
rem A release browser ignores -s, so it gets each tool through its kit main loop
rem (scripts/kit/kit_loop.gd): S and E wrap the tool path for the binary in use.
rem Kit jobs, including finite preview/perf snapshots, do not audition audio.
rem Dummy is a process-local option before the engine/user argument separator.
rem Set the source default before the following block expands percent variables.
if not defined IAMAR_BROWSER if not defined GODOT set "GODOT=godot.exe"
if defined IAMAR_BROWSER (set "RUN="%IAMAR_BROWSER%" --audio-driver Dummy" & set "S=-- --kit-script " & set "E=") else (
  set "RUN="%GODOT%" --audio-driver Dummy --path "%IAMAR_PROJECT%"" & set "S=-s " & set "E= --"
)
rem the kit tools resolve relative paths against PWD (cmd does not set it)
set "PWD=%CD%"
rem the first arguments by position (the loop below shifts them away)
set "A1=%~2"
set "A2=%~3"
set "A3=%~4"
shift
set "ARGS="
set "PT_HEAD="
:collect
if "%~1"=="" goto run
if /i "%CMD%"=="assets" if /i "%~1"=="--worlds" shift & goto collect
if /i "%CMD%"=="playtest" if /i "%~1"=="--headless" set "PT_HEAD=--headless" & shift & goto collect
set ARGS=%ARGS% %1
shift
goto collect
:run
if /i "%CMD%"=="new"            goto cmd_new
if /i "%CMD%"=="validate"       goto cmd_validate
if /i "%CMD%"=="impostors"      goto cmd_impostors
if /i "%CMD%"=="tiers"          goto cmd_tiers
if /i "%CMD%"=="preview"        goto cmd_preview
if /i "%CMD%"=="perf"           goto cmd_perf
if /i "%CMD%"=="playtest"       goto cmd_playtest
if /i "%CMD%"=="play"           goto cmd_play
if /i "%CMD%"=="assets"         goto cmd_assets
if /i "%CMD%"=="sign"           goto cmd_sign
if /i "%CMD%"=="verify"         goto cmd_verify
if /i "%CMD%"=="where"          goto cmd_where
if /i "%CMD%"=="techniques"     goto cmd_techniques
if /i "%CMD%"=="pack"           goto pack
if /i "%CMD%"=="package"        goto pack
if /i "%CMD%"=="serve"          goto cmd_serve
if /i "%CMD%"=="host"           goto cmd_host
if /i "%CMD%"=="add-to-browser" goto cmd_add_to_browser
if /i "%CMD%"=="keygen"         goto keygen
if /i "%CMD%"=="blender"        goto blender
if /i "%CMD%"=="blender-run"    goto blenderrun
if /i "%CMD%"=="publish"        goto publish
echo iamar-world ^<command^>   (Windows; details: kit/AGENT_KIT.md)
echo   new, where, validate, techniques, tiers, impostors, preview, perf, play, playtest, assets, keygen, sign, verify,
echo   pack, serve, add-to-browser, blender, blender-run, publish, compile-typescript, lint, compare-shots, shots, lowtier, audit,
echo   download-login [start^|wait]  (a download pass for the iamar browser; you approve it once in your web browser)
echo   compile-typescript [--from-source] world.ts template-folder fresh-output
echo     fast path: pure-Node packer, no toolchain; --from-source needs Linux x86_64
echo   sign ^<folder^> ^<key^> "^<Your Name^>" signs the folder; pack also signs it
echo   (same arguments as the bash kit/iamar-world on Linux and macOS)
goto end

rem Each engine command returns here only after its matching dispatch.
:cmd_new
%RUN% --headless %S%res://scripts/kit/world_new.gd%E%%ARGS%
goto end

:cmd_validate
%RUN% --headless %S%res://scripts/kit/world_view.gd%E% --validate%ARGS%
goto end

:cmd_impostors
%RUN% %S%res://scripts/kit/world_impostors_build.gd%E%%ARGS%
goto end

:cmd_tiers
%RUN% --headless %S%res://scripts/kit/world_tiers_build.gd%E%%ARGS%
goto end

:cmd_preview
set "RENDER_LOG=%TEMP%\iamar-world-render-%RANDOM%%RANDOM%.log"
%RUN% %S%res://scripts/kit/world_view.gd%E%%ARGS% >"%RENDER_LOG%" 2>&1
set "RENDER_RC=%ERRORLEVEL%"
call :check_render || exit /b 1
goto end

:cmd_perf
set "RENDER_LOG=%TEMP%\iamar-world-render-%RANDOM%%RANDOM%.log"
%RUN% %S%res://scripts/kit/world_view.gd%E%%ARGS% >"%RENDER_LOG%" 2>&1
set "RENDER_RC=%ERRORLEVEL%"
call :check_render || exit /b 1
goto end

:cmd_playtest
rem a private profile for the run (settings, saves, world data): never the player's own
set "PT_DIR=%TEMP%\iamar-playtest-%RANDOM%%RANDOM%"
mkdir "%PT_DIR%" >nul 2>&1
rem --headless was taken out of ARGS by :collect (never through "call", which expands every argument a second time)
setlocal
set "APPDATA=%PT_DIR%"
set "OAK_SETTINGS=%PT_DIR%\settings.cfg"
if defined IAMAR_BROWSER goto playtest_browser
%RUN% %PT_HEAD% -s res://scripts/kit/world_playtest.gd --%ARGS%
goto playtest_ran
:playtest_browser
%RUN% %PT_HEAD% -- --kit-script res://scripts/kit/world_playtest.gd%ARGS%
:playtest_ran
set "PT_RC=%ERRORLEVEL%"
endlocal & set "PT_RC=%PT_RC%"
rmdir /s /q "%PT_DIR%" >nul 2>&1
call :next_hint %PT_RC%
exit /b %PT_RC%

rem play: walk an unsigned draft in the real browser game at once, offline, reloading on save
rem (kit\play\README.md). A separate draft profile kept between runs, never the player's own.
rem The person plays it, so it has sound; --headless (tests) and --mute run silent.
:cmd_play
if not defined IAMAR_PLAY_PROFILE set "IAMAR_PLAY_PROFILE=%LOCALAPPDATA%\iamar-draft-profile"
mkdir "%IAMAR_PLAY_PROFILE%" >nul 2>&1
set "PL_HEAD="
set "PL_AUDIO="
set "PL_ARGS="
for %%a in (%ARGS%) do (if /i "%%~a"=="--headless" (set "PL_HEAD=--headless") else if /i "%%~a"=="--mute" (set "PL_AUDIO=--audio-driver Dummy") else (call set PL_ARGS=%%PL_ARGS%% %%a))
setlocal
set "APPDATA=%IAMAR_PLAY_PROFILE%"
set "OAK_SETTINGS=%IAMAR_PLAY_PROFILE%\settings.cfg"
if defined IAMAR_BROWSER ("%IAMAR_BROWSER%" %PL_AUDIO% %PL_HEAD% -- --kit-script res://scripts/kit/world_play.gd%PL_ARGS%) else ("%GODOT%" %PL_AUDIO% %PL_HEAD% --path "%IAMAR_PROJECT%" -s res://scripts/kit/world_play.gd --%PL_ARGS%)
set "PL_RC=%ERRORLEVEL%"
endlocal & set "PL_RC=%PL_RC%"
exit /b %PL_RC%

:check_render
type "%RENDER_LOG%"
if not "%RENDER_RC%"=="0" (del /q "%RENDER_LOG%" >nul 2>&1 & exit /b %RENDER_RC%)
set "VIEWS=0"
set "VISIBLE_VIEWS=0"
for /f %%N in ('%SystemRoot%\System32\findstr.exe /b /c:"VIEW " "%RENDER_LOG%" ^| "%SystemRoot%\System32\find.exe" /c /v ""') do set "VIEWS=%%N"
for /f %%N in ('%SystemRoot%\System32\findstr.exe /b /c:"VIEW " "%RENDER_LOG%" ^| "%SystemRoot%\System32\findstr.exe" /v /c:"draw=0 prims=0 objects=0" ^| "%SystemRoot%\System32\find.exe" /c /v ""') do set "VISIBLE_VIEWS=%%N"
if not "%VIEWS%"=="0" if "%VISIBLE_VIEWS%"=="0" (
  echo ERROR: preview rendered no world geometry ^(every VIEW had draw=0 prims=0 objects=0^). 1>&2
  echo   Do not accept these screenshots or performance numbers; update the browser/runtime and retry. 1>&2
  set "RENDER_RC=1"
)
del /q "%RENDER_LOG%" >nul 2>&1
exit /b %RENDER_RC%

:cmd_assets
%RUN% --headless %S%res://scripts/kit/world_assets.gd%E%%ARGS%
goto end

:cmd_sign
%RUN% --headless %S%res://scripts/kit/world_sign.gd%E% sign%ARGS%
goto end

:cmd_verify
%RUN% --headless %S%res://scripts/kit/world_sign.gd%E% verify%ARGS%
goto end

:cmd_where
set "D=%HERE%docs"
if not exist "%D%\WORLD_FORMAT.md" set "D=%IAMAR_PROJECT%\docs"
if not exist "%D%\WORLD_FORMAT.md" set "D=MISSING (expected %HERE%docs; re-download the complete browser bundle)"
set "ENGINE=%IAMAR_BROWSER%"
if not defined ENGINE set "ENGINE=%GODOT%"
if not defined ENGINE set "ENGINE=MISSING (set IAMAR_BROWSER, or GODOT with IAMAR_PROJECT)"
echo KIT %HERE%
echo DOCS %D%
echo AGENT_KIT %HERE%AGENT_KIT.md
echo BROWSER %ENGINE%
goto end

:cmd_techniques
%RUN% --headless %S%res://scripts/kit/world_techniques_check.gd%E%%ARGS%
goto end

:cmd_serve
%RUN% --headless %S%res://scripts/host/world_host.gd%E%%ARGS%
goto end

:cmd_host
%RUN% --headless %S%res://scripts/host/world_host.gd%E%%ARGS%
goto end

:cmd_pylint
set "PYTOOL=style_lint.py"
if /i "%CMD%"=="compare-shots" set "PYTOOL=compare_shots.py"
if /i "%CMD%"=="shots" set "PYTOOL=..\shots\shots.py"
if /i "%CMD%"=="lowtier" set "PYTOOL=..\shots\lowtier\lowtier.py"
if /i "%CMD%"=="assets" set "PYTOOL=..\catalog\catalog.py"
if /i "%CMD%"=="assets" if /i "%~2"=="ref" set "PYTOOL=..\catalog\refs.py"
if /i "%CMD%"=="assets" if /i "%~2"=="fetch" set "PYTOOL=..\catalog\packs.py"
if /i "%CMD%"=="audit" set "PYTOOL=..\audit\audit.py"
if /i "%CMD%"=="version" set "PYTOOL=..\version\version.py"
if /i "%CMD%"=="doctor" set "PYTOOL=..\doctor\doctor.py"
if /i "%CMD%"=="publish-local" set "PYTOOL=..\publish\publish.py"
if /i "%CMD%"=="style-gen" set "PYTOOL=..\style\gen\gen.py"
if /i "%CMD%"=="materials" set "PYTOOL=..\style\materials\materials.py"
if /i "%CMD%"=="terrain" set "PYTOOL=..\terrain\terrain.py"
set "PY="
if defined PYTHON if exist "%PYTHON%" set "PY="%PYTHON%""
if not defined PY for /f "delims=" %%P in ('%SystemRoot%\System32\where.exe $PATH:py.exe 2^>nul') do if not defined PY set "PY="%%P" -3"
if not defined PY for /f "delims=" %%P in ('%SystemRoot%\System32\where.exe $PATH:python.exe 2^>nul') do if not defined PY echo %%P | "%SystemRoot%\System32\findstr.exe" /i "WindowsApps" >nul || set "PY="%%P""
rem No Python (a stock Windows PC): doctor reports from PowerShell, assets search uses the browser's own search.
if not defined PY if /i "%CMD%"=="doctor" goto doctor_nopy
if not defined PY if /i "%CMD%"=="assets" goto cmd_assets
if not defined PY (echo iamar-world %CMD%: needs Python 3 ^(set PYTHON=C:\Python312\python.exe^); texture and screenshot checks also need numpy and Pillow 1>&2 & exit /b 2)
set "PYARGS="
shift
:pylint_args
if "%~1"=="" goto pylint_run
set PYARGS=%PYARGS% "%~1"
shift
goto pylint_args
:pylint_run
%PY% "%HERE%lint\%PYTOOL%"%PYARGS%
exit /b %ERRORLEVEL%

:doctor_nopy
set "DJ="
if /i "%~2"=="--json" set "DJ=-Json"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%HERE%doctor\doctor_nopy.ps1" %DJ%
exit /b %ERRORLEVEL%

:catalog_use
set "CATALOG_RC="
set "CPY="
for /f "delims=" %%P in ('%SystemRoot%\System32\where.exe $PATH:python.exe 2^>nul') do if not defined CPY set "CPY=%%P"
if not defined CPY set "CPY=python.exe"
if defined PYTHON set "CPY=%PYTHON%"
"%CPY%" "%HERE%catalog\catalog.py" %2 %3 %4 %5 %6 %7 %8 %9
set "CRC=%ERRORLEVEL%"
rem 3: not a kit file (the browser takes it); 9009: no Python (the browser's own use still works)
if "%CRC%"=="3" goto :eof
if "%CRC%"=="9009" goto :eof
set "CATALOG_RC=%CRC%"
goto :eof

:refs_check
set "REFS_RC="
set "CPY="
for /f "delims=" %%P in ('%SystemRoot%\System32\where.exe $PATH:python.exe 2^>nul') do if not defined CPY set "CPY=%%P"
if not defined CPY set "CPY=python.exe"
if defined PYTHON set "CPY=%PYTHON%"
"%CPY%" "%HERE%catalog\refs.py" check "%~1"
set "RRC=%ERRORLEVEL%"
rem 9009: no Python (the browser packs as before)
if "%RRC%"=="9009" goto :eof
if not "%RRC%"=="0" set "REFS_RC=1"
goto :eof

:cmd_add_to_browser
%RUN% --headless %S%res://scripts/host/world_host_add.gd%E%%ARGS%
goto end

:keygen
set "K=%A1%"
if not defined K (echo keygen ^<name or path^> & exit /b 1)
rem A name holding \ or / or .key is a path; a bare name goes to %APPDATA%\iamar\signing.
rem String tests only: K is never expanded into a command line (sec job kit-5).
set "KP="
if not "%K:\=%"=="%K%" set "KP=1"
if not "%K:/=%"=="%K%" set "KP=1"
if not "%K:.key=%"=="%K%" set "KP=1"
if not defined KP set "K=%APPDATA%\iamar\signing\%K%.key"
%RUN% --headless %S%res://scripts/kit/world_sign.gd%E% keygen "%K%"
goto end

:findblender
set "B="
if defined BLENDER if exist "%BLENDER%" set "B=%BLENDER%"
if not defined B for /f "delims=" %%P in ('%SystemRoot%\System32\where.exe $PATH:blender 2^>nul') do if not defined B set "B=%%P"
if not defined B for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do if exist "%%D\blender.exe" set "B=%%D\blender.exe"
exit /b 0

:blender
call :findblender
if not defined B (echo NO BLENDER: install Blender 4.x from https://www.blender.org/download/ or set BLENDER & exit /b 1)
echo BLENDER %B%
set "BLENDER_EXE=%B%"
set "BV="
for /f "usebackq delims=" %%V in (`%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -Command "$o=[IO.Path]::GetTempFileName(); $p=Start-Process -FilePath $env:BLENDER_EXE -ArgumentList '--version' -RedirectStandardOutput $o -NoNewWindow -PassThru; if(-not $p.WaitForExit(10000)){$p.Kill(); Remove-Item $o -Force; exit 124}; Get-Content $o -TotalCount 1; Remove-Item $o -Force"`) do if not defined BV set "BV=%%V"
if not defined BV (echo BLENDER ERROR: version probe did not finish successfully within 10s & exit /b 1)
echo %BV%
goto end

:blenderrun
call :findblender
if not defined B (echo NO BLENDER: run iamar-world blender & exit /b 1)
"%B%" -b --factory-startup --python%ARGS%
goto end

:pack
rem as on Linux: rebuild the lower hardware tiers first (docs/WORLD_TIERS.md), then report the recipes
call :buildtiers "%A1%" || exit /b 1
%RUN% --headless %S%res://scripts/kit/world_sign.gd%E% pack%ARGS% || exit /b 1
rem (after signing: the folder only opens signed)
call :techniques "%A1%"
goto end

:buildtiers
if defined IAMAR_NO_TIERS exit /b 0
if not exist "%~1\manifest.json" exit /b 0
"%SystemRoot%\System32\findstr.exe" /c:"\"tiers\"" "%~1\manifest.json" >nul || exit /b 0
echo TIERS building the lower tiers of %~1 (set IAMAR_NO_TIERS=1 to skip)
%RUN% --headless %S%res://scripts/kit/world_tiers_build.gd%E% "%~1" || (echo TIERS failed: fix the tier above ^(or its budgets^) before packing & exit /b 1)
exit /b 0

:techniques
if defined IAMAR_NO_TECHNIQUES exit /b 0
%RUN% --headless %S%res://scripts/kit/world_techniques_check.gd%E% "%~1" | "%SystemRoot%\System32\findstr.exe" /b /c:"TECHNIQUE" /c:"ADVICE" /c:"OFF" /c:"ERROR"
exit /b 0

:publish
rem publish <folder> <signing key> "<Your Name>" (needs IAMAR_BUILDER_KEY; curl ships with Windows 10+)
if "%A3%"=="" (echo publish ^<folder^> ^<signing key^> ^<your name^> & exit /b 1)
call :buildtiers "%A1%" || exit /b 1
if not defined IAMAR_BUILDER_KEY (echo set IAMAR_BUILDER_KEY to the builder key from the game ^(it starts with iamk_^) & exit /b 1)
if not defined IAMAR_HUB set "IAMAR_HUB=https://hub.vessences.com"
set "T=%TEMP%\iamar-publish-%RANDOM%%RANDOM%"
mkdir "%T%"
%RUN% --headless %S%res://scripts/kit/world_sign.gd%E% pack "%A1%" "%T%\package.iamar" "%A2%" "%A3%"
set "P="
for %%F in ("%T%\*.pieces.json") do set "P=%%F"
if not exist "%T%\package.iamar" (echo publish: packing failed ^(see above^) & rd /s /q "%T%" & exit /b 1)
if not defined P (echo publish: packing failed ^(see above^) & rd /s /q "%T%" & exit /b 1)
set "H=%IAMAR_HUB%"
if /i "%H:~0,6%"=="wss://" set "H=https://%H:~6%"
if /i "%H:~0,5%"=="ws://" set "H=http://%H:~5%"
if "%H:~-1%"=="/" set "H=%H:~0,-1%"
if /i "%H:~-7%"=="/signal" set "H=%H:~0,-7%"
set "OKH="
if /i "%H:~0,8%"=="https://" set "OKH=1"
for %%L in (localhost 127.0.0.1) do (
  if /i "%H%"=="http://%%L" set "OKH=1"
  if /i "%H:~0,17%"=="http://%%L:" set "OKH=1"
)
if not defined OKH (echo publish: refusing to send the builder key to the hub ^(https required^) & rd /s /q "%T%" & exit /b 1)
rem Key in a private config file (not on the command line); -q ignores the user's curlrc.
>"%T%\curl.cfg" echo header = "Authorization: Bearer %IAMAR_BUILDER_KEY%"
"%SystemRoot%\System32\curl.exe" -q -sS -K "%T%\curl.cfg" --max-redirs 0 -F "pieces=@%P%" -F "package=@%T%\package.iamar" "%H%/api/builder/worlds"
echo.
rd /s /q "%T%"
goto end

rem --json: is it asked for, on a command whose text output kit\agent_output\agent_output.py reads?
:want_json
for %%C in (new validate preview perf techniques tiers impostors assets package pack sign verify keygen add-to-browser playtest where) do if /i "%~1"=="%%C" set "WANT_JSON=%%C"
if not defined WANT_JSON exit /b 0
if /i "%~1"=="assets" if /i "%~2"=="search" if /i not "%~3"=="--worlds" goto want_json_no
:want_json_scan
shift
if "%~1"=="" goto want_json_no
if /i "%~1"=="--json" exit /b 0
goto want_json_scan
:want_json_no
set "WANT_JSON="
exit /b 0

:agent_py
set "APY="
if defined PYTHON if exist "%PYTHON%" set "APY="%PYTHON%""
if not defined APY for /f "delims=" %%P in ('%SystemRoot%\System32\where.exe $PATH:py.exe 2^>nul') do if not defined APY set "APY="%%P" -3"
if not defined APY for /f "delims=" %%P in ('%SystemRoot%\System32\where.exe $PATH:python.exe 2^>nul') do if not defined APY echo %%P | "%SystemRoot%\System32\findstr.exe" /i "WindowsApps" >nul || set "APY="%%P""
exit /b 0

:agent_json
call :agent_py
if not defined APY goto agent_json_nopy
%APY% "%HERE%agent_output\agent_output.py" run %WANT_JSON% -- "%~f0" %*
exit /b %ERRORLEVEL%
:agent_json_nopy
echo {"schema": "iamar-kit-output/1", "command": "%WANT_JSON%", "exit_code": 2, "ok": false, "errors": [{"message": "--json needs Python 3", "fix": "Install Python 3 or set PYTHON to python.exe; iamar-world doctor checks it"}]}
exit /b 2

rem The NEXT: line that ends a human-mode run (%1: the exit code; IAMAR_KIT_NO_NEXT=1 turns it off).
:next_hint
if defined IAMAR_KIT_OUTPUT_CHILD exit /b 0
call :agent_py
rem activity log: one line in <world>\.iamar\activity.jsonl (IAMAR_KIT_NO_ACTIVITY=1 turns it off)
if defined APY %APY% "%HERE%agent_output\agent_output.py" activity %CMD% %1%ARGS% 2>nul
if defined IAMAR_KIT_NO_NEXT exit /b 0
if defined APY %APY% "%HERE%agent_output\agent_output.py" next %CMD% %1%ARGS% 2>nul
exit /b 0

:cmd_compile_typescript
rem This branch runs before the native dispatcher shifts the original arguments.
rem Fast path: pure Node, with no browser, C toolchain or downloads.
set "A1=%~2"
set "A2=%~3"
set "A3=%~4"
set "EXTRA=%~5"
if /i "%A1%"=="--from-source" (
  echo compile-typescript --from-source needs the Linux x86_64 source builder; use kit/iamar-world on Linux. 1>&2
  exit /b 2
)
if defined EXTRA goto compile_usage
rem Expand the raw fifth argument only after its dequoted value is empty.
rem This also rejects an explicitly empty extra argument without re-parsing a path.
if not "%5"=="" goto compile_usage
if "%A1%"=="" goto compile_usage
if "%A2%"=="" goto compile_usage
if "%A3%"=="" goto compile_usage
if not exist "%A1%" goto compile_source_missing
if exist "%A1%\" goto compile_source_missing
if not exist "%A2%\manifest.json" goto compile_template_missing
if exist "%A2%\manifest.json\" goto compile_template_missing

rem Select one complete dependency set. An existing kit packer never borrows
rem a missing SDK or prebuilt guest from IAMAR_PROJECT.
set "TSW=%HERE%ts-world"
set "SDK=%TSW%\iamar-world.d.ts"
if exist "%TSW%\pack.mjs" goto compile_dependencies_selected
set "TSW=%IAMAR_PROJECT%\tools\typescript-world"
set "SDK=%IAMAR_PROJECT%\api\typescript\iamar-world.d.ts"
:compile_dependencies_selected
set "PREBUILT=%TSW%\prebuilt\iamar_ts_guest.wasm"
for %%F in ("%TSW%\pack.mjs" "%PREBUILT%" "%SDK%") do (
  if not exist "%%~F" goto compile_dependencies_missing
  if exist "%%~F\" goto compile_dependencies_missing
)

rem Resolve the compiler before any Node invocation; an explicit choice wins.
set "TSC=%IAMAR_TS_COMPILER%"
if not defined TSC if exist "%TSW%\node_modules\typescript\lib\typescript.js" set "TSC=%TSW%\node_modules\typescript\lib\typescript.js"
if not defined TSC if exist "%TSW%\typescript.js" set "TSC=%TSW%\typescript.js"
if not defined TSC goto compile_compiler_missing
if not exist "%TSC%" goto compile_compiler_missing
if exist "%TSC%\" goto compile_compiler_missing
set "NODE=%IAMAR_TS_NODE%"
if not defined NODE for /f "delims=" %%P in ('%SystemRoot%\System32\where.exe $PATH:node 2^>nul') do if not defined NODE set "NODE=%%P"
rem No Node 20+ on PATH: the kit's own pinned Node (fetched once, kit\runtime_fetch.cmd).
if defined NODE if not defined IAMAR_TS_NODE call :node20 || set "NODE="
if not defined NODE for /f "usebackq delims=" %%P in (`call "%HERE%runtime_fetch.cmd" node`) do set "NODE=%%P"
if not defined NODE goto compile_node_missing
if not exist "%NODE%" goto compile_node_missing
if exist "%NODE%\" goto compile_node_missing
rem Do not let a caller-defined ERRORLEVEL shadow the packer process status.
set "ERRORLEVEL="
"%NODE%" "%TSW%\pack.mjs" --source "%A1%" --sdk "%SDK%" --typescript "%TSC%" --prebuilt "%PREBUILT%" --template "%A2%" --out "%A3%"
exit /b %ERRORLEVEL%

:compile_usage
echo usage: iamar-world compile-typescript world.ts template-folder fresh-output 1>&2
exit /b 2
:compile_source_missing
echo compile-typescript: source must name an existing file 1>&2
exit /b 2
:compile_template_missing
echo compile-typescript: template folder needs a manifest.json file 1>&2
exit /b 2
:compile_dependencies_missing
echo compile-typescript: selected dependency set is incomplete ^(packer, prebuilt guest and SDK files required^) 1>&2
echo   Use a complete kit/ts-world bundle or a complete source checkout. 1>&2
exit /b 2
:compile_compiler_missing
echo compile-typescript: the official TypeScript 5.9.3 compiler file is required. 1>&2
echo   Install it beside the selected packer or set IAMAR_TS_COMPILER to its approved typescript.js file. 1>&2
exit /b 2
:node20
set "NODE_V="
for /f "usebackq delims=" %%V in (`call "%NODE%" -p "Number(process.versions.node.split('.')[0]) >= 20"`) do set "NODE_V=%%V"
if "%NODE_V%"=="true" exit /b 0
exit /b 1
:compile_node_missing
echo compile-typescript: Node.js 20 or newer is required on PATH or as IAMAR_TS_NODE 1>&2
exit /b 2
:end
set "END_RC=%ERRORLEVEL%"
call :next_hint %END_RC%
endlocal & exit /b %END_RC%
