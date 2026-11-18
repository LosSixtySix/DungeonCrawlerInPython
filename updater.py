import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request

from version import VERSION

"""
Self-update over Tailscale.

Releases are served from this PC (see distribution\\README.md) at UPDATE_URL: version.json says what the
newest version is, CRUEL.zip holds the build and install.ps1 installs it.

At launch the game asks the server for version.json in the background. If it's newer than VERSION, the title
screen offers an update. Choosing it downloads install.ps1, starts it in its own window and quits the game.
The script waits for the game to close, swaps in the new build and starts it again. Saves are in %APPDATA%\\CRUEL,
not in the game folder, so they're kept.

Only the packaged game (CRUEL.exe) checks: running from source never offers an update. If the server can't be
reached (this PC is off, or the player isn't on the tailnet), the game just starts as normal.
"""

UPDATE_URL = "http://jonathanlaptop.tail6a8b0d.ts.net/cruel/"
TIMEOUT = 4  # seconds


def parseVersion(text):
    """'1.2.3' -> (1, 2, 3). Anything that isn't a version comes out as (), which is older than everything."""
    try:
        return tuple(int(part) for part in str(text).strip().split("."))
    except ValueError:
        return ()


class Updater:
    def __init__(self):
        self.latest = None  # newest version on the server, once the check finds one newer than this build
        self.changed = False  # set when the check finishes with news, so the title screen redraws
        if getattr(sys, "frozen", False):
            threading.Thread(target=self.check, daemon=True).start()

    def check(self):
        try:
            with urllib.request.urlopen(UPDATE_URL + "version.json", timeout=TIMEOUT) as response:
                latest = json.load(response).get("version", "")
        except Exception:
            return  # offline, server down, not on the tailnet: nothing to offer
        if parseVersion(latest) > parseVersion(VERSION):
            self.latest = latest
            self.changed = True

    def takeChange(self) -> bool:
        """True once after the check finds an update."""
        changed, self.changed = self.changed, False
        return changed

    def startUpdate(self):
        """Download the installer and start it. Returns an error message, or None if it's running
        (the caller then quits the game so the installer can replace it)."""
        script = os.path.join(tempfile.gettempdir(), "CRUEL-install.ps1")
        try:
            with urllib.request.urlopen(UPDATE_URL + "install.ps1", timeout=TIMEOUT) as response:
                data = response.read()
            with open(script, "wb") as file:
                file.write(data)
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-WaitPid", str(os.getpid())],
                creationflags=subprocess.CREATE_NEW_CONSOLE,  # its own window, so the player can see the progress
                close_fds=True,
                cwd=tempfile.gettempdir(),  # not the game folder: it couldn't be replaced while in use as the working directory
            )
        except Exception:
            return "Couldn't reach the update server. Try again later"
        return None
