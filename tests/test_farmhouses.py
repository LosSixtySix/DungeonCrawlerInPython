"""The Dwellers' farmhouses on a city's farm floor (farmhouses.py): round, two doors, four boat-shaped plots that
never spread by themselves, a chest in the middle; the farmers build more as the herd grows."""
import random
import unittest
from unittest import mock

from cruel.inventory import items
from cruel.inventory import loot
from cruel.world import dwellerbuilding
from cruel.world import dwellerfarming
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import farmhouses
from cruel.world import mineshafts
from cruel.world import plants
from cruel.world import wall
from tests import support
from tests.test_dweller_growth import PenTest

FLOOR, WALL, CHEST, PLANT = 0, 2, 3, 8


class ShapeTests(unittest.TestCase):
    def setUp(self):
        self.inside, self.walls, self.beds = farmhouses.offsets()

    def test_it_is_round_its_corners_are_not_part_of_it(self):
        half = farmhouses.HALF
        for corner in ((half, half), (-half, half), (half, -half), (-half, -half)):
            self.assertNotIn(corner, self.walls | self.inside)
        self.assertIn((half, 0), self.walls)
        self.assertIn((0, -half), self.walls)

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


class FarmFloorTests(unittest.TestCase):
    def setUp(self):
        random.seed(6)
        self.game = support.newGame()
        grid, self.rowLength = self.game.grid, self.game.rowLength
        self.shaft = (len(grid) // self.rowLength // 2) * self.rowLength + self.rowLength // 2
        self.works = mineshafts.layOutWorks(grid, self.rowLength, self.shaft, "farm", self.game.rooms)

    def test_farmhouses_with_a_chest_planted_plots_and_their_crops_floor(self):
        game = self.game
        self.assertEqual(len(self.works.farmhouses), mineshafts.FARMHOUSES)
        for farmhouse in self.works.farmhouses:
            crop = farmhouse["crop"]
            for spot in farmhouse["walls"]:
                self.assertIsInstance(game.grid[spot][2], wall.FarmhouseWall)
            self.assertIsInstance(game.grid[farmhouse["chest"]][2], items.StorageChest)
            for bed in farmhouse["beds"]:
                tile = game.grid[bed]
                self.assertEqual(tile[0], PLANT)
                self.assertTrue(tile[2].planted and tile[2].cityCrop)
                self.assertEqual(self.works.fields[bed], crop)
            for spot in farmhouse["inside"]:
                self.assertEqual(plants.floorOf(spot, game.rooms), farmhouses.floorFor(crop))

    def test_both_doors_open_onto_ground_you_can_walk_to_from_the_shaft(self):
        grid = self.game.grid
        for farmhouse in self.works.farmhouses:
            shut = {spot: ([FLOOR, 0] if tile[0] in (5, PLANT) else tile) for spot, tile in grid.items()}
            for spot in farmhouse["box"]:
                shut[spot] = [WALL, 0]
            reached = mineshafts.walkable(shut, self.rowLength, self.shaft) | {self.shaft}
            for door in (farmhouse["door"], farmhouse["backDoor"]):
                self.assertEqual(grid[door][0], FLOOR)
                outside = [near for near in self.game.neighbors(door) if near not in farmhouse["box"]]
                self.assertTrue(any(near in reached for near in outside))

    def test_the_farmers_know_their_farmhouses_and_nothing_wild_grows_in_them(self):
        game = self.game
        for spot, dweller in self.works.dwellers.items():
            game.grid[spot] = [5, 0, dweller]
            game.EnemyPositions.add(spot)
        farmer = next(dweller for dweller in self.works.dwellers.values() if getattr(dweller, "work", None) == "farm")
        self.assertIs(farmer.farmhouses, self.works.farmhouses)
        tiles = dwellerfarming.fieldTiles(game)
        for farmhouse in self.works.farmhouses:
            self.assertTrue(set(farmhouse["inside"]) <= tiles)


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
        game = self.game
        self.pen(40, 30)
        fields, built = {self.spot(10, 10): "bloodcap"}, []
        growers = [self.farmer(column, 45) for column in (45, 47, 49)]
        for grower in growers:
            grower.farmRole, grower.fields, grower.farmhouses = "grower", fields, built
        plan = dwellerbuilding.farmhousePlan(game, self.spot(45, 45), growers[0])
        self.assertEqual(plan["crop"], "bloodcap", "a crop they have seeds of")
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            self.assertTrue(self.runTurns(600, until=lambda: built))
        farmhouse = built[0]
        for spot in farmhouse["walls"]:
            self.assertIsInstance(game.grid[spot][2], wall.FarmhouseWall)
        self.assertIsInstance(game.grid[farmhouse["chest"]][2], items.StorageChest)
        self.assertTrue(set(farmhouse["beds"]) <= set(fields))
        self.assertEqual(plants.floorOf(farmhouse["beds"][0], game.rooms), farmhouses.floorFor("bloodcap"))


if __name__ == "__main__":
    unittest.main()
