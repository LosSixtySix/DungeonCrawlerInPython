"""Helpers for the tests of test_metropolis.py, shared by its unit, integration and acceptance tests."""
import random
from cruel.world import dwellers
from cruel.world import metropolis
from tests import support


FLOOR, WALL, CHEST, ENEMY = 0, 2, 3, 5
ROW_LENGTH, ROW_COUNT = 102, 76


def middleSpot():
    return ROW_LENGTH // 2 + (ROW_COUNT // 2) * ROW_LENGTH


def newCity(seed=1, playerSpot=None):
    random.seed(seed)
    return metropolis.buildCity(ROW_LENGTH, ROW_COUNT, middleSpot() if playerSpot is None else playerSpot)


def cityGame(seed=4):
    """A game walked down to a new floor that is a city."""
    random.seed(seed)
    game = support.newGame()
    game.saveGame = lambda *args, **kwargs: None
    game.metropolisNext = True
    game.goToNewLevel()
    return game


def dwellersOn(game, role=None):
    """(position, Dweller) for the Dwellers on the floor (of one role, if given)."""
    found = []
    for spot in game.EnemyPositions:
        tile = game.grid[spot]
        if tile[0] == ENEMY and dwellers.isDweller(tile[2]) and (role is None or tile[2].role == role):
            found.append((spot, tile[2]))
    return found


def ringOf(city, inside):
    """The tiles round a building's inside: its walls and its door."""
    insideSet = set(inside)
    ring = set()
    for spot in inside:
        for rowOffset in (-1, 0, 1):
            for columnOffset in (-1, 0, 1):
                other = spot + columnOffset + rowOffset * city.rowLength
                if other not in insideSet:
                    ring.add(other)
    return ring


def buildingsOn(game):
    """The tiles of each building on a city floor (its walls, its sign, its inside and its door), worked out from
    the floor's rooms: every connected patch of House, Shop or Noble room is one building."""
    buildingTiles = set()
    for room in (metropolis.HOUSE, metropolis.SHOP, metropolis.NOBLE):
        buildingTiles |= game.rooms[room]
    buildings, seen = [], set()
    for start in buildingTiles:
        if start in seen:
            continue
        building, frontier = {start}, [start]
        seen.add(start)
        while frontier:
            spot = frontier.pop()
            for near in game.neighbors(spot):
                if near in buildingTiles and near not in seen:
                    seen.add(near)
                    building.add(near)
                    frontier.append(near)
        buildings.append(building)
    return buildings
