"""Walls: the wall types, how hits wear them down, ore veins, and the rare ore floors (wall.py)."""
import random
import unittest
from unittest import mock

from cruel.world import wall
from tests import support

TILE_SIZE = 10


class WallTypeTests(unittest.TestCase):
    """The plain wall types and how much punishment each one takes."""

    def test_each_wall_type_has_its_own_hp_and_hardness(self):
        expected = {wall.StoneWall: ("Stone Wall", 40, 5, False),
                    wall.WoodWall: ("Wood Wall", 15, 15, True),
                    wall.SandWall: ("Sand Wall", 10, 10, True),
                    wall.GoldWall: ("Gold Wall", 7, 2, False),
                    wall.MoltenWall: ("Molten Wall", 30, 5, False)}
        for wallClass, (name, hp, hardness, soft) in expected.items():
            newWall = wallClass()
            self.assertEqual((newWall.name, newWall.hp, newWall.hardness, newWall.soft), (name, hp, hardness, soft))
            self.assertEqual(newWall.brokenPoints, set())

    def test_a_hit_does_no_more_damage_than_the_walls_hardness(self):
        stoneWall = wall.StoneWall()
        stoneWall.takeDamage(100, TILE_SIZE)
        self.assertEqual(stoneWall.hp, 40 - 5)

    def test_a_weak_hit_does_its_full_damage(self):
        woodWall = wall.WoodWall()
        woodWall.takeDamage(4, TILE_SIZE)
        self.assertEqual(woodWall.hp, 11)

    def test_hits_chip_points_off_the_inside_of_the_tile(self):
        random.seed(3)
        sandWall = wall.SandWall()
        sandWall.takeDamage(5, TILE_SIZE)
        self.assertTrue(sandWall.brokenPoints)
        for x, y in sandWall.brokenPoints:
            self.assertTrue(1 <= x <= TILE_SIZE - 2 and 1 <= y <= TILE_SIZE - 2)

    def test_a_wall_worn_down_to_zero_hp_shatters_completely_on_the_next_hit(self):
        random.seed(4)
        wornWall = wall.StoneWall()
        wornWall.hp = 0
        wornWall.takeDamage(5, TILE_SIZE)  # no division by zero
        self.assertLess(wornWall.hp, 0)
        self.assertGreater(len(wornWall.brokenPoints), 30)

    def test_random_points_stay_inside_the_ranges_given(self):
        random.seed(5)
        points = wall.getRandomPoints((2, 5), (7, 9), 50)
        self.assertTrue(all(2 <= x <= 4 and 7 <= y <= 8 for x, y in points))


class OreVeinTests(unittest.TestCase):
    """Ore veins and where they are allowed to spawn."""

    def test_every_vein_is_a_hard_wall_that_gives_its_ore(self):
        expectedOre = {wall.CoalVein: "coal", wall.CopperVein: "copper_ore", wall.IronVein: "iron_ore",
                       wall.SilverVein: "silver_ore", wall.JadeVein: "rough_jade", wall.PeridotVein: "rough_peridot",
                       wall.RoseQuartzVein: "rough_rose_quartz", wall.RubyVein: "rough_ruby",
                       wall.AmethystVein: "rough_amethyst"}
        for veinClass, ore in expectedOre.items():
            vein = veinClass()
            self.assertIsInstance(vein, wall.OreVein)
            self.assertEqual(vein.ore, ore)
            self.assertFalse(vein.soft)
            self.assertEqual(len(vein.oreColor), 3)

    def test_the_five_gems_share_the_gem_vein_base(self):
        for gemClass in (wall.JadeVein, wall.PeridotVein, wall.RoseQuartzVein, wall.RubyVein, wall.AmethystVein):
            self.assertTrue(issubclass(gemClass, wall.GemVein))
        self.assertFalse(issubclass(wall.IronVein, wall.GemVein))

    def test_deeper_metals_are_harder_to_mine(self):
        hardnesses = [veinClass().hardness for veinClass in
                      (wall.CoalVein, wall.CopperVein, wall.IronVein, wall.SilverVein)]
        self.assertEqual(hardnesses, sorted(hardnesses))

    def test_first_floor_table_matches_the_vein_spawn_list(self):
        self.assertEqual(wall.VEIN_FIRST_FLOOR[wall.CoalVein], 0)
        self.assertEqual(wall.VEIN_FIRST_FLOOR[wall.IronVein], 2)
        self.assertEqual(wall.VEIN_FIRST_FLOOR[wall.AmethystVein], 5)
        self.assertEqual(len(wall.VEIN_FIRST_FLOOR), len(wall.VEIN_SPAWNS))


class OreFloorTests(unittest.TestCase):
    """The rare ore floors (ORE_FLOORS) and how a floor's type and veins are picked from them."""

    def test_every_ore_floor_spec_is_complete(self):
        for floorName, spec in wall.ORE_FLOORS.items():
            with self.subTest(floorName):
                self.assertGreaterEqual(spec["first"], 1)
                self.assertGreater(spec["weight"], 0)
                self.assertTrue(set(spec["rooms"]) <= {"Stone", "Wood", "Sand", "Gold"})
                self.assertTrue(all(issubclass(veinClass, wall.OreVein) for veinClass in spec["ores"]))
                self.assertIsInstance(spec["coal"], bool)

    def test_an_ore_floor_never_appears_before_any_of_its_ores_can(self):
        for floorName, spec in wall.ORE_FLOORS.items():
            earliestOre = min(wall.VEIN_FIRST_FLOOR[veinClass] for veinClass in spec["ores"])
            self.assertGreaterEqual(spec["first"], earliestOre, floorName)

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
