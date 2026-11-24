"""Shared helpers for the tests: starting a game and moving the player around without playing."""
from cruel.core import gamemanager


def newGame(level=0):
    """A fresh run on floor 0 (or walked down to floor `level`), with the title screen and menus out of the way."""
    game = gamemanager.gameManager()
    game.newGame()
    game.scene = "playing"
    game.pausePage = None
    for _ in range(level):
        game.goToNewLevel()
    return game


def placePlayer(game, spot):
    """Put the player on `spot` the way walking there would: the tile they leave gets back what was under them,
    and the tile under them on the new spot is remembered in currentLocation."""
    game.grid[game.playerPositionFlat] = game.currentLocation
    game.playerPositionFlat = spot
    game.currentLocation = list(game.grid[spot])
    game.grid[spot] = [1, game.grid[spot][1]]


def openTile(game, avoid=()):
    """Some bare floor tile that the player isn't standing on."""
    return next(spot for spot, tile in game.grid.items()
                if tile[0] == 0 and spot != game.playerPositionFlat and spot not in avoid)
