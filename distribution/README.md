# Sharing CRUEL over Tailscale

Players install and update the game from this PC over the tailnet. Only players in the tailnet's `group:players`
(and you) can reach it.

## One-time setup (this PC)

Releases are served as the Tailscale Service `svc:cruel`, at `http://cruel.tail6a8b0d.ts.net/`. In the admin
console, the service is defined on the Services page (port `tcp:80`), and this PC carries the tag
`tag:cruel-host`. Only tagged devices can host a service.

Then, from an **admin** PowerShell (Tailscale only lets admins serve a folder):

```powershell
tailscale serve --service=svc:cruel --http=80 C:\Users\Jonathan\Desktop\PersonalCode\release
```

`release\` is gitignored and filled by `release.ps1`. The setting survives reboots. To check it, run
`tailscale serve status`. To undo it, run `tailscale serve clear svc:cruel`.

Versions 0.1.8 and older look for updates at the old address,
`http://jonathanlaptop.tail6a8b0d.ts.net/cruel/`. Keep that one served too until every player has updated:
`tailscale serve --bg --http=80 --set-path /cruel C:\Users\Jonathan\Desktop\PersonalCode\release`.

It uses plain HTTP, which is fine here: tailnet traffic is already encrypted by WireGuard.

## Giving someone access

1. Admin console -> Users -> Invite users. They install Tailscale and accept the invite.
2. Add their login email to `group:players` in the access policy (admin console -> Access controls).
   A grant lets that group reach `svc:cruel` on port 80 and nothing else, so they can't reach your devices.
3. Have them run the install command below.

Players from before the service existed got access through a machine share of `jonathanlaptop`. The
`autogroup:shared` grant still lets them reach the old `/cruel` address on port 80, so they can update from 0.1.8.
Once they've all updated, remove that grant and the old serve.

## Publishing a release

```powershell
.\distribution\release.ps1                 # 0.1.0 -> 0.1.1
.\distribution\release.ps1 -Version 0.2.0  # pick the number yourself
```

It bumps `cruel\core\version.py`, builds with PyInstaller, then puts `CRUEL.zip`, `install.ps1` and `version.json` in
`release\`. Commit `cruel\core\version.py` afterwards.

## What players do

First install, in PowerShell:

```powershell
irm http://cruel.tail6a8b0d.ts.net/install.ps1 | iex
```

This installs to `%LOCALAPPDATA%\Programs\CRUEL`, adds Start Menu and desktop shortcuts and starts the game.

After that, the game checks for updates on launch. When there's a newer version, the title screen shows
**Update to vX**. Choosing it closes the game, installs the update and reopens the game. Running the
command above again also updates. Saves are in `%APPDATA%\CRUEL`, so updates never touch them.

This PC has to be on and connected to Tailscale for anyone to download. If it isn't, the game just
starts without offering an update.
