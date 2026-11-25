"""A city keeping its farm running, played: every farmer on a real city's farm dies, and the city sends citizens down
until the farm has the farmers it needs again.

Acceptance tests; the rest are in tests/integration/test_farm_help.py."""
import unittest

from cruel.world import dwellers
from cruel.world import livingfloors
from cruel.world import queen
from tests.helpers.metropolis import cityGame


class FarmRefilledTests(unittest.TestCase):
    def test_a_farm_whose_farmers_all_die_is_staffed_again_from_the_city(self):
        game = cityGame()
        game.enemyTurn()
        farmKey = (game.level, queen.shaftsHere(game, "farm")[0])
        with livingfloors.awayFloor(game, farmKey):
            for spot, unit in list(dwellers.cityDwellers(game)):
                if unit.work == "farm":
                    game.killEnemy(spot, killer=None, unit=unit)
        citizens = {id(unit) for _, unit in dwellers.cityDwellers(game) if unit.role == "citizen" and unit.work is None}
        for _ in range(500):
            game.enemyTurn()
            record = game.workCensus[farmKey]
            if record["farmer"] >= queen.farmersWanted(record):
                break
        record = game.workCensus[farmKey]
        self.assertGreaterEqual(record["farmer"], queen.farmersWanted(record))
        self.assertGreaterEqual(record["keepers"], 1)
        self.assertGreaterEqual(record["growers"], 1)
        with livingfloors.awayFloor(game, farmKey):
            farmers = [unit for _, unit in dwellers.cityDwellers(game) if unit.work == "farm"]
        self.assertGreaterEqual(sum(1 for unit in farmers if id(unit) in citizens), queen.farmersWanted(record) - 1,
                                "they came from the city's citizens (one may have hatched from the Queen's eggs)")


if __name__ == "__main__":
    unittest.main()
