# Builds CRUEL and publishes it to the release folder that Tailscale serves, so players get the update.
#
#   .\distribution\release.ps1                  bump the patch number (0.1.0 -> 0.1.1)
#   .\distribution\release.ps1 -Version 0.2.0   set the version yourself
#
# Afterwards commit version.py, so the source matches what was released.

param([string]$Version)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path $PSScriptRoot
$Release = Join-Path $Repo 'release'  # served by: tailscale serve --bg --http=80 --set-path /cruel <this folder>
$VersionPy = Join-Path $Repo 'version.py'

# Work out the new version
$source = Get-Content $VersionPy -Raw
if ($source -notmatch 'VERSION = "(\d+)\.(\d+)\.(\d+)"') { throw "Couldn't find VERSION in version.py" }
if (-not $Version) { $Version = "$($Matches[1]).$($Matches[2]).$([int]$Matches[3] + 1)" }
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Version must look like 1.2.3, not '$Version'" }
$source = $source -replace 'VERSION = "[^"]*"', "VERSION = `"$Version`""
[IO.File]::WriteAllText($VersionPy, $source)
Write-Host "Releasing CRUEL v$Version"

# Build
Push-Location $Repo
try {
    python -m PyInstaller --noconfirm CRUEL.spec
    if ($LASTEXITCODE) { throw 'PyInstaller failed' }
} finally { Pop-Location }

# Publish. version.json goes last, so nobody is told about a version whose zip isn't there yet.
New-Item -ItemType Directory -Force $Release | Out-Null
$zipTemp = Join-Path $Release 'CRUEL.zip.tmp'
if (Test-Path $zipTemp) { Remove-Item $zipTemp -Force }
tar --format=zip -c -f $zipTemp -C (Join-Path $Repo 'dist\CRUEL') .
if ($LASTEXITCODE) { throw 'Zipping the build failed' }
Move-Item $zipTemp (Join-Path $Release 'CRUEL.zip') -Force
Copy-Item (Join-Path $PSScriptRoot 'install.ps1') $Release -Force
[IO.File]::WriteAllText((Join-Path $Release 'version.json'), "{`"version`": `"$Version`"}")

Write-Host "Published CRUEL v$Version to $Release" -ForegroundColor Green
Write-Host 'Players get it the next time they open the game (or run the install command).'
Write-Host 'Remember to commit version.py.'
