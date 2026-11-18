# Installs CRUEL, or updates it if it's already installed, then starts it.
#
# Players run this from PowerShell (they must be on the tailnet):
#   irm http://jonathanlaptop.tail6a8b0d.ts.net/cruel/install.ps1 | iex
# The game also runs it when you choose "Update to vX" on the title screen. It then passes -WaitPid,
# the game's process id, so the script waits for the game to close before replacing its files.
#
# The game goes in %LOCALAPPDATA%\Programs\CRUEL, with Start Menu and desktop shortcuts.
# Saves live in %APPDATA%\CRUEL and are never touched.
#
# No "exit" in here: through "irm | iex" it would close the player's PowerShell window.

param(
    [int]$WaitPid = 0,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'  # Windows PowerShell's download progress bar makes downloads very slow

$Base = 'http://jonathanlaptop.tail6a8b0d.ts.net/cruel'
$InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\CRUEL'
$Exe = Join-Path $InstallDir 'CRUEL.exe'
$VersionFile = Join-Path $InstallDir 'version.txt'

function Add-Shortcut([string]$Path) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($Path)
    $link.TargetPath = $Exe
    $link.WorkingDirectory = $InstallDir
    $link.Save()
}

function Wait-ForGameToClose {
    if ($WaitPid) {
        Write-Host 'Waiting for CRUEL to close...'
        Wait-Process -Id $WaitPid -Timeout 30 -ErrorAction SilentlyContinue
    }
    while (Get-Process CRUEL -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $Exe }) {
        Write-Host 'CRUEL is still running. Close it to continue...' -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
}

function Remove-OldInstall {
    # Windows can hold on to the game's files for a moment after it closes (antivirus scans them too), so retry
    for ($try = 1; Test-Path $InstallDir; $try++) {
        try { Remove-Item $InstallDir -Recurse -Force }
        catch {
            if ($try -ge 10) { throw }
            Start-Sleep -Seconds 1
        }
    }
}

# When the game starts this script, it starts inside the game folder. A folder that's in use as the current
# directory can't be deleted, so step out of it first (PowerShell's location and the process's own).
Set-Location $env:TEMP
[Environment]::CurrentDirectory = $env:TEMP

try {
    Write-Host 'Checking for the latest version of CRUEL...'
    $latest = [string](Invoke-RestMethod -UseBasicParsing "$Base/version.json").version
    $current = $null
    if (Test-Path $VersionFile) { $current = (Get-Content $VersionFile -Raw).Trim() }

    if ($current -and ([version]$current -ge [version]$latest)) {
        Write-Host "CRUEL v$current is up to date." -ForegroundColor Green
    } else {
        if ($current) { Write-Host "Updating CRUEL v$current -> v$latest" } else { Write-Host "Installing CRUEL v$latest" }

        $zip = Join-Path $env:TEMP "CRUEL-$latest.zip"
        $unpacked = Join-Path $env:TEMP "CRUEL-$latest"
        Write-Host 'Downloading...'
        Invoke-WebRequest -UseBasicParsing "$Base/CRUEL.zip" -OutFile $zip
        if (Test-Path $unpacked) { Remove-Item $unpacked -Recurse -Force }
        Expand-Archive $zip -DestinationPath $unpacked
        if (-not (Test-Path (Join-Path $unpacked 'CRUEL.exe'))) { throw 'The download is missing CRUEL.exe' }

        Wait-ForGameToClose
        Write-Host 'Installing...'
        Remove-OldInstall
        New-Item -ItemType Directory -Force (Split-Path $InstallDir) | Out-Null
        Move-Item $unpacked $InstallDir
        Set-Content $VersionFile $latest -Encoding ASCII
        Remove-Item $zip -Force -ErrorAction SilentlyContinue
        Write-Host "CRUEL v$latest installed." -ForegroundColor Green
    }

    Add-Shortcut (Join-Path ([Environment]::GetFolderPath('Programs')) 'CRUEL.lnk')
    Add-Shortcut (Join-Path ([Environment]::GetFolderPath('Desktop')) 'CRUEL.lnk')

    if (-not $NoLaunch) {
        Start-Process $Exe -WorkingDirectory $InstallDir
    }
} catch {
    Write-Host ''
    Write-Host "Couldn't install CRUEL: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Make sure Tailscale is running and you can open $Base/version.json in a browser."
    Read-Host 'Press Enter to close'
}
