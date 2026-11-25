"""The Dwellers keeping Overgrowth off a real city's buildings: with them at it, far less grows near the buildings
than if they left it.

Acceptance tests; the rest are in tests/integration/test_quelling.py."""
import random
import unittest
from unittest import mock

from cruel.world import quelling
from tests.helpers.metropolis import cityGame


def overgrownCity(dwellersClear):
    """A real city through 240 turns of Overgrowth: (wild plants, corrupted walls) near its buildings, averaged
    over the run."""
    random.seed(4)
    game = cityGame()
    game.floorEvents[game.level] = {"id": "overgrowth", "turnsLeft": 500, "active": True}
    wild = corrupted = samples = 0
    noClearing = mock.patch.object(quelling, "quellTurn", lambda *arguments: None)
    if dwellersClear:
        noClearing = mock.patch.object(quelling, "QUELL_REACH", quelling.QUELL_REACH)  # (nothing changed)
    with noClearing:
        for turn in range(240):
            game.enemyTurn()
            if turn % 20 == 19:
                zone = quelling.nearBuildings(game)
                wild += sum(1 for spot in zone if spot in game.grid and quelling.isWild(game.grid[spot]))
                corrupted += sum(1 for spot in zone if spot in game.grid and quelling.isCorrupted(game.grid[spot]))
                samples += 1
    return wild / samples, corrupted / samples


class OvergrownCityTests(unittest.TestCase):
    def test_the_dwellers_keep_the_plants_off_their_buildings(self):
        clearedWild, clearedCorrupted = overgrownCity(True)
        leftWild, leftCorrupted = overgrownCity(False)
        self.assertLess(clearedWild, leftWild / 2)
        self.assertLess(clearedCorrupted, leftCorrupted / 2)


if __name__ == "__main__":
    unittest.main()
