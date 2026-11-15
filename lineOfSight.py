"""
Launcher kept so the existing lineOfSight.spec (PyInstaller) build still works.
The game itself lives in gamemanager.py (logic) and renderer.py (drawing).
"""
from gamemanager import gameManager

if __name__ == "__main__":
    gameManager().RunGame()
