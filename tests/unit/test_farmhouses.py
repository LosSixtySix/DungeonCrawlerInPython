"""The Dwellers' farmhouses on a city's farm floor (farmhouses.py): round, two doors, four boat-shaped plots that
never spread by themselves, a chest in the middle; the farmers build more as the herd grows.

Unit tests; the rest are in tests/integration/test_farmhouses.py."""
import unittest
from unittest import mock
from cruel.inventory import items
from cruel.inventory import loot
from cruel.world import dwellerbuilding
from cruel.world import dwellerfarming
from cruel.world import dwellers
from cruel.world import farmhouses
from cruel.world import plants
from cruel.world import wall
from tests.helpers.dweller_growth import PenTest
from tests.helpers.farmhouses import FLOOR


class ShapeTests(unittest.TestCase):
    def setUp(self):
        self.inside, self.walls, self.beds = farmhouses.offsets()

    def test_it_is_round_its_corners_are_not_part_of_it(self):
        for corner in ((farmhouses.HALF, farmhouses.HALF), (-farmhouses.HALF, farmhouses.HALF),
                       (farmhouses.HALF, -farmhouses.HALF), (-farmhouses.HALF, -farmhouses.HALF)):
            self.assertNotIn(corner, self.walls | self.inside)
        self.assertIn((farmhouses.HALF, 0), self.walls)
        self.assertIn((0, -farmhouses.HALF), self.walls)

    def test_four_triangular_plots_round_the_middle_and_paths_to_it(self):
        self.assertEqual(len(self.beds), 4 * len(farmhouses.BOAT))
        self.assertTrue(set(self.beds) <= self.inside)
        self.assertNotIn((0, 0), self.beds, "the chest")
        self.assertFalse([bed for bed in self.beds if 0 in bed], "the cross of paths stays clear")

    def test_a_full_plot_never_sprouts_more_by_the_game_of_life(self):
        beds = set(self.beds)
        counts = {}
        for column, row in beds:
            for stepColumn in (-1, 0, 1):
                for stepRow in (-1, 0, 1):
                    if stepColumn or stepRow:
                        near = (column + stepColumn, row + stepRow)
                        counts[near] = counts.get(near, 0) + 1
        self.assertEqual([tile for tile, count in counts.items() if count == 3 and tile not in beds], [])

    def test_its_two_doors_face_the_shaft_and_away(self):
        rowLength = 100
        site = farmhouses.shape(rowLength, 50, 50, (20, 50))  # the shaft to the left
        self.assertEqual(site["door"], 50 - farmhouses.HALF + 50 * rowLength)
        self.assertEqual(site["backDoor"], 50 + farmhouses.HALF + 50 * rowLength)
        self.assertNotIn(site["door"], site["walls"])
        self.assertEqual(site["chest"], 50 + 50 * rowLength)


class PlantedBonusTests(unittest.TestCase):
    def test_a_dweller_crop_is_planted_and_gives_the_planted_bonus(self):
        grid = {0: [FLOOR, 1]}
        game = mock.Mock(grid=grid)
        dwellerfarming.sow(game, 0, "bloodcap")
        crop = grid[0][2]
        self.assertTrue(crop.planted)
        crop.stage, crop.timer = "harvest", 0
        least = min(low for _, _, (low, _) in loot.CROP_LOOT[loot.plantSource(crop, "harvest")])
        wildLeast = min(low for _, _, (low, _) in loot.PLANT_LOOT[loot.plantSource(crop, "harvest")])
        self.assertEqual(least, wildLeast + loot.PLANTED_BONUS)
        farmer = mock.Mock(materials={})
        dwellerfarming.pickCrop(game, 0, farmer)
        self.assertGreaterEqual(farmer.materials.get("bloodcap", 0), least)


class NewFarmhouseTests(PenTest):
    def test_short_of_field_the_growers_build_a_farmhouse_and_its_plots_join_the_fields(self):
        self.pen(40, 30)
        fields, built = {self.spot(10, 10): "bloodcap"}, []
        growers = [self.farmer(column, 45) for column in (45, 47, 49)]
        for grower in growers:
            grower.farmRole, grower.fields, grower.farmhouses = "grower", fields, built
        plan = dwellerbuilding.farmhousePlan(self.game, self.spot(45, 45), growers[0])
        self.assertEqual(plan["crop"], "bloodcap", "a crop they have seeds of")
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            self.assertTrue(self.runTurns(600, until=lambda: built))
        farmhouse = built[0]
        for spot in farmhouse["walls"]:
            self.assertIsInstance(self.game.grid[spot][2], wall.FarmhouseWall)
        self.assertIsInstance(self.game.grid[farmhouse["chest"]][2], items.StorageChest)
        self.assertTrue(set(farmhouse["beds"]) <= set(fields))
        self.assertEqual(plants.floorOf(farmhouse["beds"][0], self.game.rooms), farmhouses.floorFor("bloodcap"))


if __name__ == "__main__":
    unittest.main()
