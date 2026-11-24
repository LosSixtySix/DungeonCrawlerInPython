"""Walls: the wall types, how hits wear them down, ore veins, and the rare ore floors (wall.py).

Unit tests; the rest are in tests/integration/test_wall.py."""
import random
import unittest
from cruel.world import wall
from tests.helpers.wall import TILE_SIZE


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
        for pixelX, pixelY in sandWall.brokenPoints:
            self.assertTrue(1 <= pixelX <= TILE_SIZE - 2 and 1 <= pixelY <= TILE_SIZE - 2)

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
        self.assertTrue(all(2 <= pixelX <= 4 and 7 <= pixelY <= 8 for pixelX, pixelY in points))


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


if __name__ == "__main__":
    unittest.main()
