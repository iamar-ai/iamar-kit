# iamar-world doctor for a PC without Python 3 (called by kit\iamar-world.cmd when no python.exe/py.exe is found).
# Same checks, ids and exit rule as doctor.py: exit 1 only when a REQUIRED item is MISSING.
#   doctor_nopy.ps1 [-Json]
param([switch]$Json)
$ErrorActionPreference = 'SilentlyContinue'
$kit = Split-Path -Parent $PSScriptRoot
$checks = New-Object System.Collections.ArrayList

function First-File($paths) { foreach ($p in $paths) { if ($p -and (Test-Path -LiteralPath $p -PathType Leaf)) { return $p } } return '' }
function Add-Check($id, $level, $ok, $detail, $fix, $needed) {
    $status = if ($ok) { 'OK' } elseif ($level -eq 'required') { 'MISSING' } else { 'OPTIONAL' }
    [void]$checks.Add([ordered]@{ id = $id; level = $level; status = $status; detail = $detail; fix = $(if ($ok) { '' } else { $fix }); needed_for = $needed })
}

$local = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME 'AppData\Local' }
$pack = First-File @($env:IAMAR_KIT_PACK, (Join-Path $kit 'iamar-kit.pck'), (Join-Path $local 'iamar\kit\iamar-kit.pck'), (Join-Path $HOME '.iamar\kit\iamar-kit.pck'))
Add-Check 'kit_pack' 'required' ([bool]$pack) $(if ($pack) { $pack } else { 'iamar-kit.pck not found' }) 'turn on Developer mode in the iamar browser (Esc menu), or download the kit from https://downloads.vessences.com/kit and put iamar-kit.pck beside kit\ (or set IAMAR_KIT_PACK)' 'validate, preview, package, every browser-run command'

$cands = @($env:IAMAR_BROWSER)
foreach ($n in 'iamar.exe', 'Oakhaven.exe') { $cands += (Join-Path $kit "..\$n"); $cands += (Join-Path $kit "..\iamar\$n") }
$cands += @(Get-ChildItem -Path (Join-Path $kit 'runtime') -Filter 'iamar.exe' -Recurse -File | ForEach-Object { $_.FullName })
$browser = First-File $cands
if ($browser) { $browser = [System.IO.Path]::GetFullPath($browser) }
Add-Check 'browser' 'required' ([bool]$browser) $(if ($browser) { $browser } else { 'no iamar browser beside kit\' }) 'put kit\ beside the downloaded iamar browser, set IAMAR_BROWSER=C:\path\to\iamar.exe, or run kit\runtime_fetch.cmd browser' 'validate, preview, perf, package, playtest'

$py = $null
foreach ($c in 'py.exe', 'python.exe') { $g = Get-Command $c -CommandType Application; if ($g -and $g.Source -notmatch 'WindowsApps') { $py = $g.Source; break } }
Add-Check 'python' 'required' $false 'Python 3 not found (this report ran without it)' 'winget install Python.Python.3.12  (or https://www.python.org), then open a new terminal' 'lint, audit, shots, assets search, terrain, version'

$nbin = if ($env:IAMAR_TS_NODE) { $env:IAMAR_TS_NODE } else { $g = Get-Command node.exe -CommandType Application; if ($g) { $g.Source } else { '' } }
$nv = ''
if ($nbin) { $nv = (& $nbin --version 2>$null | Select-Object -First 1); }
$nok = $false
if ($nv -match '^v(\d+)\.') { $nok = [int]$Matches[1] -ge 20 }
Add-Check 'node' 'optional' $nok $(if ($nv) { "Node $nv" } else { 'Node not found' }) 'winget install OpenJS.NodeJS.LTS (Node 20 or newer), or let the kit fetch its own: kit\runtime_fetch.cmd node' 'compile-typescript (TypeScript world scripts)'

$bl = if ($env:BLENDER) { $env:BLENDER } else { First-File @(Get-ChildItem 'C:\Program Files\Blender Foundation' -Directory | ForEach-Object { Join-Path $_.FullName 'blender.exe' }) }
$blok = $false; $bv = ''
if ($bl) { $bv = (& $bl --version 2>$null | Select-Object -First 1); if ($bv -match 'Blender (\d+)\.(\d+)') { $blok = ([int]$Matches[1] -gt 4) -or ([int]$Matches[1] -eq 4 -and [int]$Matches[2] -ge 2) } }
Add-Check 'blender' 'optional' $blok $(if ($bv) { "$bv" } else { 'Blender not found' }) 'install Blender 4.2 or newer (https://www.blender.org) or set BLENDER=C:\path\to\blender.exe' 'blender, blender-run, own meshes'

Add-Check 'display' 'optional' $true 'a display is available' '' 'preview, perf, shots'

$sign = Join-Path $(if ($env:APPDATA) { $env:APPDATA } else { $HOME }) 'iamar\signing'
Add-Check 'signing_key' 'optional' ((Test-Path -LiteralPath $sign -PathType Container) -and (@(Get-ChildItem -LiteralPath $sign).Count -gt 0)) $(if (Test-Path -LiteralPath $sign) { $sign } else { 'no signing key yet' }) 'iamar-world keygen <your-name> (the key stays on this computer; never commit it)' 'package, signed worlds'

$login = $false
if ($env:APPDATA) { foreach ($f in (Get-ChildItem -Path $env:APPDATA -Filter 'settings.cfg' -Recurse -File -Depth 4 | Select-Object -First 20)) { if (Select-String -LiteralPath $f.FullName -Pattern '^token\s*=\s*"[^"]+"' -Quiet) { $login = $true; break } } }
Add-Check 'hub_login' 'optional' $login $(if ($login) { 'signed in to the hub' } else { 'no sign-in token found' }) 'open the iamar browser, sign in with your iamar account (Esc menu > Account), then Start Hosting' 'register and host a world'

$ok = -not ($checks | Where-Object { $_.status -eq 'MISSING' })
if ($Json) {
    [ordered]@{ checks = @($checks); ok = [bool]$ok } | ConvertTo-Json -Depth 4
} else {
    foreach ($c in $checks) {
        Write-Output ('{0,-8} {1}: {2}' -f $c.status, $c.id, $c.detail)
        if ($c.fix) { Write-Output "         fix: $($c.fix)"; Write-Output "         needed for: $($c.needed_for)" }
    }
    Write-Output ('DOCTOR ' + $(if ($ok) { 'OK' } else { 'FAILED: fix the MISSING items above' }))
    Write-Output ('NEXT: ' + $(if ($ok) { 'iamar-world new <folder>' } else { 'fix the first MISSING item, then run iamar-world doctor again' }))
}
if ($ok) { exit 0 } else { exit 1 }
