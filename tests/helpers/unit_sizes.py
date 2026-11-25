"""Helpers for the tests of test_unit_sizes.py, shared by its unit, integration and acceptance tests."""
import random
import unittest
from cruel.world import occupancy
from tests import support
from tests.helpers.expansion import blankFloor, middleOf


FLOOR, ENEMY, PLANT, PILE = 0, 5, 8, 9


class OccupancyTest(unittest.TestCase):
    """An open floor, you in the top-left corner."""

    def setUp(self):
        random.seed(4)
        self.game = support.newGame()
        blankFloor(self.game)
        self.middle = middleOf(self.game)

    def put(self, spot, unit):
        """unit on spot: the first unit there, or the second if there is one."""
        if occupancy.primaryAt(self.game, spot) is None:
            self.game.grid[spot] = [ENEMY, 1, unit]
            self.game.EnemyPositions.add(spot)
        else:
            occupancy.sharedTiles(self.game)[spot] = unit
        return unit

    def at(self, spot):
        return occupancy.unitsAt(self.game, spot)
