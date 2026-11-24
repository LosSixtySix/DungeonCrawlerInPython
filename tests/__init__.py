"""
CRUEL's tests. Run them all from the repo root with:

    python -m unittest discover tests

or one file with:   python -m unittest tests.test_plants

This file runs before any test module: it points pygame at dummy video/audio drivers (no window, no sound)
and points the save folder at a temporary one, so tests never touch your real saves in %APPDATA%/CRUEL.
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
SAVE_DIR = tempfile.mkdtemp(prefix="cruel-tests-")
os.environ["APPDATA"] = SAVE_DIR  # read by cruel.core.paths when it's first imported

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from cruel.core import paths  # noqa: E402

assert paths.SAVE_DIR.startswith(SAVE_DIR), "tests must never write to the real save folder"
