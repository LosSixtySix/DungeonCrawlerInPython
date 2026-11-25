"""A city's works (mineshafts.py): its mine and its farm, the mineshafts down to them, and the works floors below,
which sit beside the city's floor while you're on them.

Integration tests; the rest are in tests/acceptance/test_mineshafts.py."""
import random
import unittest
from cruel.world import metropolis
from cruel.world import mineshafts
from cruel.world import wall
from tests import support
from tests.helpers.metropolis import cityGame, newCity
from tests.helpers.mineshafts import shaftSpot

WALL = 2


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


class ClearanceTests(unittest.TestCase):
    """Room round every building on a works floor, so nothing blocks its doors."""

    def buildingBoxes(self, works):
        boxes = [storehouse["walls"] | storehouse["inside"] | {storehouse["door"], storehouse["backDoor"]}
                 for storehouse in works.storehouses]
        boxes += [pen["fence"] | set(pen["inside"]) for pen in works.pens]
        boxes += [farmhouse["box"] for farmhouse in works.farmhouses]
        return boxes

    def test_no_rock_and_no_other_building_within_two_tiles_of_any_building(self):
        for seed in range(6):
            random.seed(seed)
            game = support.newGame()
            grid, rowLength = game.grid, game.rowLength
            shaft = (len(grid) // rowLength // 2) * rowLength + rowLength // 2
            works = mineshafts.layOutWorks(grid, rowLength, shaft, "farm", game.rooms)
            boxes = self.buildingBoxes(works)
            self.assertTrue(works.pens and works.farmhouses, f"seed {seed}")
            for box in boxes:
                columns, rows = [spot % rowLength for spot in box], [spot // rowLength for spot in box]
                around = {column + row * rowLength
                          for row in range(min(rows) - mineshafts.CLEARANCE, max(rows) + mineshafts.CLEARANCE + 1)
                          for column in range(min(columns) - mineshafts.CLEARANCE, max(columns) + mineshafts.CLEARANCE + 1)} - box
                for spot in around:
                    tile = grid.get(spot)
                    if tile is None or not mineshafts.inBounds(rowLength, len(grid) // rowLength, spot % rowLength, spot // rowLength):
                        continue
                    self.assertFalse(tile[0] == WALL and not isinstance(tile[2], wall.CityBuildingWall),
                                     f"seed {seed}: rock beside a building")
                for other in boxes:
                    if other is not box and not (other & box):
                        self.assertFalse(around & other, f"seed {seed}: two buildings closer than two tiles")


if __name__ == "__main__":
    unittest.main()
