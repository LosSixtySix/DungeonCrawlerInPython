"""
Launcher used as the entry point by CRUEL.spec (the PyInstaller build).
The game itself lives in gamemanager.py (logic) and renderer.py (drawing).
"""
from gamemanager import gameManager

if __name__ == "__main__":
    gameManager().RunGame()
