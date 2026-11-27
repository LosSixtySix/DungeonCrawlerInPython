"""Helpers for the tests of test_gamemanager.py, shared by its unit, integration and acceptance tests."""
import pygame
from tests.support import newGame, placePlayer, openTile


FLOOR, PLAYER, WALL, CHEST, DOWN_DOOR, ENEMY, UP_DOOR, PILE = 0, 1, 2, 3, 4, 5, 6, 9
LEFT, RIGHT, UP, DOWN = 0, 1, 2, 3


def keyDown(game, key, modifierKeys=0):
    """Presses and releases a key the way pygame would deliver it."""
    game.onKeyDown(pygame.event.Event(pygame.KEYDOWN, key=key, mod=modifierKeys))
    game.onKeyUp(pygame.event.Event(pygame.KEYUP, key=key, mod=modifierKeys))


def middleSpot(game):
    """A tile well away from the map's edges."""
    return (game.painter.columnLength // 2) * game.rowLength + game.rowLength // 2


def clearAround(game, spot):
    """Turns the 5x5 block around spot into plain, visible floor, so nothing nearby gets in the way."""
    for rowOffset in range(-2, 3):
        for columnOffset in range(-2, 3):
            tile = spot + columnOffset + rowOffset * game.rowLength
            game.grid[tile] = [FLOOR, 1]
            game.EnemyPositions.discard(tile)


def standInOpenFloor(game, facing=LEFT):
    """Puts the player in the middle of a cleared patch of floor, facing one way, with no enemies on the floor."""
    playerSpot = middleSpot(game)
    for enemySpot in list(game.EnemyPositions):
        game.grid[enemySpot] = [FLOOR, game.grid[enemySpot][1]]
    game.EnemyPositions = set()
    placePlayer(game, playerSpot)
    clearAround(game, playerSpot)
    game.grid[playerSpot] = [PLAYER, 1]
    game.currentLocation = [FLOOR, 1]
    game.player.playerDirection = facing
    game.setLookPosition()
    return playerSpot
