"""Floors near you keep going while you're not on them (livingfloors.py), and floors you can never get back to are
dropped.

Acceptance tests; the rest are in tests/integration/test_living_floors.py."""
import random
import unittest
from cruel.world import livingfloors
from cruel.world import metropolis
from cruel.world import mineshafts
from tests.helpers.metropolis import cityGame
from tests.helpers.mineshafts import climbDown, shaftSpot


class CityTests(unittest.TestCase):
    def test_a_city_brings_its_mine_and_farm_along_made_even_if_you_have_never_been_down(self):
        random.seed(5)
        game = cityGame()
        game.enemyTurn()
        level = game.level
        keys = [key for key in livingfloors.floorsInReach(game) if isinstance(key, tuple)]
        self.assertEqual(sorted(keys), sorted((level, shaftSpot(game, kind)) for kind in metropolis.WORKS))
        self.assertTrue(all(key in game.floorsAside for key in keys))

    def test_going_down_finds_the_floor_that_has_been_going_on_without_you(self):
        random.seed(5)
        game = cityGame()
        game.enemyTurn()
        madeBefore = game.floorsAside[(game.level, shaftSpot(game, "farm"))]["levelGrid"][0]
        climbDown(game, "farm")
        self.assertIs(game.grid, madeBefore)

    def test_on_a_works_floor_its_city_and_the_other_works_floor_keep_going(self):
        random.seed(5)
        game = cityGame()
        level = game.level
        mineShaft = shaftSpot(game, "mine")
        climbDown(game, "farm")
        keys = livingfloors.floorsInReach(game)
        self.assertIn(level, keys, "the city")
        self.assertIn((level, mineShaft), keys, "the mine")
        self.assertNotIn(mineshafts.floorKey(game), keys, "not where you are")
        game.enemyTurn()  # (and they can take a turn without trouble)
        game.onEnter()  # back up: the city is there as it was
        self.assertEqual(game.proportion, metropolis.METROPOLIS)


if __name__ == "__main__":
    unittest.main()
