"""
Launcher used as the entry point by CRUEL.spec (the PyInstaller build).
The game itself is the cruel/ package: cruel/core/gamemanager.py (logic) and cruel/graphics/renderer.py (drawing).
"""
from cruel.core.gamemanager import gameManager

if __name__ == "__main__":
    gameManager().RunGame()
