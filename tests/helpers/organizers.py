"""Helpers for the tests of test_organizers.py, shared by its unit, integration and acceptance tests."""



def blankFloor(game):
    """Turns the game's floor into open Stone floor with no enemies, the player in the top-left corner."""
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


def addOrganizer(game, position, organizerClass):
    organizer = organizerClass()
    organizer.rest = 0
    game.grid[position] = [5, 0, organizer]
    game.EnemyPositions.add(position)
    return organizer


def emptyContext():
    return {"protected": {}, "claimed": set(), "targets": []}
