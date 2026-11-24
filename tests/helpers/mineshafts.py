"""Helpers for the tests of test_mineshafts.py, shared by its unit, integration and acceptance tests."""
from cruel.world import dwellers
from cruel.world import metropolis
from tests import support


FLOOR, WALL, CHEST, ENEMY, PLANT = 0, 2, 3, 5, 8


def shaftSpot(game, kind):
    return next(spot for spot, tile in game.grid.items() if tile[0] == metropolis.MINESHAFT and tile[2].kind == kind)


def climbDown(game, kind):
    """Walks onto the city's shaft of this kind and presses Enter."""
    support.placePlayer(game, shaftSpot(game, kind))
    game.onEnter()


def dwellersHere(game):
    return [game.grid[spot][2] for spot in game.EnemyPositions
            if game.grid[spot][0] == ENEMY and dwellers.isDweller(game.grid[spot][2])]
