# Sharing CRUEL over Tailscale

Players install and update the game from this PC over the tailnet. Only devices on the tailnet, or ones
this machine is shared with, can reach it.

## One-time setup (this PC)

From an **admin** PowerShell (Tailscale only lets admins serve a folder):

```powershell
tailscale serve --bg --http=80 --set-path /cruel C:\Users\Jonathan\Desktop\PersonalCode\release
```

`release\` is gitignored and filled by `release.ps1`. The setting survives reboots. To check it, run
`tailscale serve status`. To undo it, run `tailscale serve --http=80 --set-path /cruel off`.

It uses plain HTTP, which is fine here: tailnet traffic is already encrypted by WireGuard.

## Giving someone access

Admin console -> Machines -> `jonathanlaptop` -> Share. They install Tailscale and accept the invite.
They can only reach this machine, not the rest of your tailnet.

## Publishing a release

```powershell
.\distribution\release.ps1                 # 0.1.0 -> 0.1.1
.\distribution\release.ps1 -Version 0.2.0  # pick the number yourself
```

It bumps `version.py`, builds with PyInstaller, then puts `CRUEL.zip`, `install.ps1` and `version.json` in
`release\`. Commit `version.py` afterwards.

## What players do

First install, in PowerShell:

```powershell
irm http://jonathanlaptop.tail6a8b0d.ts.net/cruel/install.ps1 | iex
```

This installs to `%LOCALAPPDATA%\Programs\CRUEL`, adds Start Menu and desktop shortcuts and starts the game.

After that, the game checks for updates on launch. When there's a newer version, the title screen shows
**Update to vX**. Choosing it closes the game, installs the update and reopens the game. Running the
command above again also updates. Saves are in `%APPDATA%\CRUEL`, so updates never touch them.

This PC has to be on and connected to Tailscale for anyone to download. If it isn't, the game just
starts without offering an update.
