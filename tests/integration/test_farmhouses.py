"""The Dwellers' farmhouses on a city's farm floor (farmhouses.py): round, two doors, four boat-shaped plots that
never spread by themselves, a chest in the middle; the farmers build more as the herd grows.

Integration tests; the rest are in tests/unit/test_farmhouses.py."""
import random
import unittest
from cruel.inventory import items
from cruel.world import dwellerfarming
from cruel.world import farmhouses
from cruel.world import mineshafts
from cruel.world import plants
from cruel.world import wall
from tests import support
from tests.helpers.farmhouses import FLOOR, PLANT, WALL


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


if __name__ == "__main__":
    unittest.main()
