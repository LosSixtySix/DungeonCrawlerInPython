"""Helpers for the tests of test_expansion.py, shared by its unit, integration and acceptance tests."""
from cruel.world import expansion


def blankFloor(game):
    """Turns the game's floor into open, unseen Stone floor with no enemies, the player in the top-left corner."""
    for position in game.grid:
        game.grid[position] = [0, 0]
    game.rooms = {"Stone": set(game.grid), "Wood": set(), "Sand": set(), "Gold": set(), "Molten": set()}
    game.EnemyPositions = set()
    game.enemyOccupiedItemSpaces = {}
    game.playerPositionFlat = 0
    game.currentLocation = [0, 0]
    game.grid[0] = [1, 0]


def middleOf(game):
    rowCount = game.numberOfSpots // game.rowLength
    return (rowCount // 2) * game.rowLength + game.rowLength // 2


def factionGoblins(game, faction):
    return [unit for _position, unit in expansion.factionUnits(game, faction)]
