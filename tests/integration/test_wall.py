"""Walls: the wall types, how hits wear them down, ore veins, and the rare ore floors (wall.py).

Integration tests; the rest are in tests/unit/test_wall.py."""
import random
import unittest
from unittest import mock
from cruel.world import wall
from tests import support


class OreFloorTests(unittest.TestCase):
    """The rare ore floors (ORE_FLOORS) and how a floor's type and veins are picked from them."""

    def test_every_ore_floor_spec_is_complete(self):
        for floorName, oreFloor in wall.ORE_FLOORS.items():
            with self.subTest(floorName):
                self.assertGreaterEqual(oreFloor["first"], 1)
                self.assertGreater(oreFloor["weight"], 0)
                self.assertTrue(set(oreFloor["rooms"]) <= {"Stone", "Wood", "Sand", "Gold"})
                self.assertTrue(all(issubclass(veinClass, wall.OreVein) for veinClass in oreFloor["ores"]))
                self.assertIsInstance(oreFloor["coal"], bool)

    def test_an_ore_floor_never_appears_before_any_of_its_ores_can(self):
        for floorName, oreFloor in wall.ORE_FLOORS.items():
            earliestOre = min(wall.VEIN_FIRST_FLOOR[veinClass] for veinClass in oreFloor["ores"])
            self.assertGreaterEqual(oreFloor["first"], earliestOre, floorName)

    def test_metal_lodes_have_coal_and_gem_grottos_do_not(self):
        self.assertTrue(wall.ORE_FLOORS["Iron Lode"]["coal"])
        self.assertFalse(wall.ORE_FLOORS["Ruby Grotto"]["coal"])

    def test_density_ranges_are_sane_and_a_motherlode_is_denser(self):
        low, high = wall.ORE_FLOOR_DENSITY
        motherLow, motherHigh = wall.MOTHERLODE_DENSITY
        self.assertTrue(0 < low < high <= motherLow < motherHigh <= 1)

    def test_on_floor_one_only_the_copper_lode_is_unlocked(self):
        game = support.newGame()
        with mock.patch("random.random", return_value=0.0):
            floorName, motherlode = game.pickOreFloor(1)
        self.assertEqual(floorName, "Copper Lode")
        self.assertTrue(motherlode)  # random 0.0 is under MOTHERLODE_CHANCE too

    def test_a_failed_ore_floor_roll_gives_a_normal_floor(self):
        game = support.newGame()
        with mock.patch("random.random", return_value=0.99):
            self.assertEqual(game.pickOreFloor(5), (None, False))

    def test_ore_floor_weights_decide_how_often_each_one_is_picked(self):
        game = support.newGame()
        random.seed(11)
        picks = {}
        for _ in range(3000):
            floorName, _motherlode = game.randomOreFloor()
            picks[floorName] = picks.get(floorName, 0) + 1
        # Copper Lode (weight 3) comes up roughly three times as often as a weight-1 grotto
        self.assertGreater(picks["Copper Lode"], 2 * picks["Jade Grotto"])
        self.assertLess(picks["Copper Lode"], 4 * picks["Jade Grotto"])

    def test_a_copper_lode_fills_its_walls_with_copper_and_a_third_coal(self):
        random.seed(12)
        game = support.newGame()
        grid = game.grid
        wallCount = sum(1 for tile in grid.values() if tile[0] == 2)
        game.placeOreFloorVeins(grid, "Copper Lode", 5, False)
        veins = [tile[2] for tile in grid.values() if tile[0] == 2 and isinstance(tile[2], wall.OreVein)]
        veinTypes = {type(vein) for vein in veins}
        self.assertTrue(veinTypes <= {wall.CopperVein, wall.CoalVein})
        low, high = wall.ORE_FLOOR_DENSITY
        self.assertLessEqual(len(veins), high * wallCount)
        self.assertGreater(len(veins), low * wallCount * 0.5)
        coalShare = sum(isinstance(vein, wall.CoalVein) for vein in veins) / len(veins)
        self.assertAlmostEqual(coalShare, wall.COAL_SHARE, delta=0.1)


if __name__ == "__main__":
    unittest.main()
