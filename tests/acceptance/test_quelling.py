"""The Dwellers keeping Overgrowth off a real city's buildings: with them at it, far less grows near the buildings
than if they left it.

Acceptance tests; the rest are in tests/integration/test_quelling.py."""
import random
import unittest
from unittest import mock

from cruel.world import quelling
from tests.helpers.metropolis import cityGame


SEEDS = (4, 5, 6)  # three cities: how much grows near any one city's buildings swings a lot with how it was laid out


def overgrownCity(dwellersClear, seed):
    """A real city (laid out from seed) through 240 turns of Overgrowth: (wild plants, corrupted walls) near its
    buildings, averaged over the run."""
    random.seed(seed)
    game = cityGame(seed)
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
        cleared = [overgrownCity(True, seed) for seed in SEEDS]
        left = [overgrownCity(False, seed) for seed in SEEDS]
        clearedWild, clearedCorrupted = (sum(found) for found in zip(*cleared))
        leftWild, leftCorrupted = (sum(found) for found in zip(*left))
        self.assertLess(clearedWild, leftWild / 2)
        self.assertLess(clearedCorrupted, leftCorrupted / 2)


if __name__ == "__main__":
    unittest.main()
