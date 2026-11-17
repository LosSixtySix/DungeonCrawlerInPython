import os
import shutil
import sys

"""
Where the game finds its files.

resourcePath(): read-only files that ship with the game (the font). When running from a PyInstaller
build they are inside the build's _internal folder (sys._MEIPASS); from source they sit next to this file.

savePath(): files the game writes while you play (save game, settings, attempts, menu options).
They go in %APPDATA%\\CRUEL on Windows (~/.local/share/CRUEL elsewhere), so they are kept no matter
where the game is launched from, and survive replacing the game folder with a newer build.
"""

GAME_NAME = "CRUEL"
SAVED_FILES = ["savegame.pkl", "settings.json", "attempts.json", "menuOpts.txt"]

_SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
_RESOURCE_DIR = getattr(sys, "_MEIPASS", _SOURCE_DIR)


def _saveDir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, GAME_NAME)


SAVE_DIR = _saveDir()


def resourcePath(name):
    return os.path.join(_RESOURCE_DIR, name)


def savePath(name):
    return os.path.join(SAVE_DIR, name)


def _setUpSaveDir():
    """Make the save folder. The first time, copy over any saves left next to the source files
    by older versions of the game (they used to be written to the current folder)."""
    os.makedirs(SAVE_DIR, exist_ok=True)
    for name in SAVED_FILES:
        old, new = os.path.join(_SOURCE_DIR, name), savePath(name)
        if os.path.isfile(old) and not os.path.exists(new):
            shutil.copy2(old, new)


_setUpSaveDir()
