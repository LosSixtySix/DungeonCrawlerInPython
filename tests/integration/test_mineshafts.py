"""A city's works (mineshafts.py): its mine and its farm, the mineshafts down to them, and the works floors below,
which sit beside the city's floor while you're on them.

Integration tests; the rest are in tests/acceptance/test_mineshafts.py."""
import unittest
from cruel.world import metropolis
from tests import support
from tests.helpers.metropolis import cityGame, newCity
from tests.helpers.mineshafts import shaftSpot


class CityWorksTests(unittest.TestCase):
    """The mine and the farm in the city."""

    def test_every_city_has_a_mine_and_a_farm(self):
        for seed in range(10):
            city = newCity(seed)
            self.assertEqual(set(city.works), set(metropolis.WORKS))

    def test_each_has_a_mineshaft_in_its_middle_and_a_sign_by_its_door(self):
        city = newCity(3)
        for kind, building in city.works.items():
            self.assertIn(building.shaft, building.inside)
            shaft = city.grid[building.shaft]
            self.assertEqual(shaft[0], metropolis.MINESHAFT)
            self.assertEqual(shaft[2].kind, kind)
            self.assertTrue(shaft[2].down)
            self.assertEqual(city.grid[building.sign][0], metropolis.SHOP_SIGN)
            self.assertEqual(metropolis.signName(city.grid[building.sign][2]), metropolis.WORKS[kind])

    def test_looking_at_a_shaft_or_standing_on_one_says_where_it_goes(self):
        game = cityGame()
        spot = shaftSpot(game, "mine")
        game.PlayerLookPosition = spot
        self.assertEqual(game.lookingAt(), "Mineshaft down to the Dweller Mine")
        support.placePlayer(game, spot)
        game.updateDoors()
        self.assertEqual(game.currentPosition, "Mineshaft down to the Dweller Mine")


if __name__ == "__main__":
    unittest.main()
