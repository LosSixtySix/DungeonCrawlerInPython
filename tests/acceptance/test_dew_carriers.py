"""The Queen's Dew carriers, played: a real city keeps its Queen fed with Dew from its farm, and on the farm you see
the carriers come down for it.

Acceptance tests; the rest are in tests/integration/test_dew_carriers.py."""
import unittest

from cruel.world import dwellers
from cruel.world import queen
from tests.helpers.metropolis import cityGame
from tests.helpers.mineshafts import climbDown


class DewRouteTests(unittest.TestCase):
    def test_the_queen_is_fed_dew_from_the_farm(self):
        game = cityGame()
        _, dwellerQueen = queen.courtOf(game)
        for _ in range(1200):
            game.enemyTurn()
            if dwellerQueen.dew:
                break
        self.assertGreater(dwellerQueen.dew, 0)

    def test_on_the_farm_you_see_carriers_come_down_for_dew(self):
        game = cityGame()
        climbDown(game, "farm")
        for _ in range(400):
            game.enemyTurn()
            if any(unit.work == "dew" for _, unit in dwellers.cityDwellers(game)):
                break
        self.assertTrue(any(unit.work == "dew" for _, unit in dwellers.cityDwellers(game)))


if __name__ == "__main__":
    unittest.main()
