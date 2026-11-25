"""Helpers for the tests of test_living_floors.py, shared by its unit, integration and acceptance tests."""



FLOOR, ENEMY = 0, 5


def unitsOn(data):
    """The units on a saved floor: {unit: spot}."""
    grid = data[0]
    return {tile[2]: spot for spot, tile in grid.items() if tile[0] == ENEMY and len(tile) > 2}
