"""The Dwellers keeping Overgrowth off their buildings (quelling.py), and builders picking wild plants off their
sites (dwellerbuilding.py).

Integration tests; the rest are in tests/acceptance/test_quelling.py."""
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.world import dwellerbuilding
from cruel.world import dwellers
from cruel.world import plants
from cruel.world import quelling
from cruel.world import wall
from tests.helpers.dweller_growth import PenTest
from tests.integration.test_city_hostility import CityTest

FLOOR, WALL, PLANT = 0, 2, 8


class QuellingTest(CityTest):
    """An open city floor in Overgrowth with a house wall along row 20 (columns 25 to 35)."""

    def setUp(self):
        super().setUp()
        self.game.floorEvents[self.game.level] = {"id": "overgrowth", "turnsLeft": 500, "active": True}
        for column in range(25, 36):
            self.addWall(column, 20)

    def plant(self, column, row, planted=False):
        plant = plants.Plant.grown("glowcap")
        plant.planted = planted
        self.game.grid[self.spot(column, row)] = [PLANT, 1, plant]
        return plant

    def runQuiet(self, count, until=None):
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0), mock.patch.object(self.game, "stepPlants", lambda: None):
            return self.runTurns(count, until)  # (no new plants: just the Dwellers' work)


class ClearingTests(QuellingTest):
    def test_a_dweller_pulls_up_a_wild_plant_near_a_building(self):
        self.plant(30, 22)
        self.addDweller(enemies.DwellerCitizen, 30, 27)
        self.assertTrue(self.runQuiet(20, until=lambda: self.game.grid[self.spot(30, 22)][0] != PLANT))
        self.assertEqual(self.game.grid[self.spot(30, 22)][0], FLOOR)

    def test_crops_are_left_alone(self):
        self.plant(30, 22, planted=True)
        self.addDweller(enemies.DwellerCitizen, 30, 27)
        self.runQuiet(20)
        self.assertEqual(self.game.grid[self.spot(30, 22)][0], PLANT)

    def test_it_scrapes_the_vines_off_a_building_wall_and_leaves_the_wall(self):
        houseWall = self.game.grid[self.spot(30, 20)][2]
        houseWall.corruptedBy = "glowcap"
        self.addDweller(enemies.DwellerCitizen, 30, 25)
        self.assertTrue(self.runQuiet(20, until=lambda: houseWall.corruptedBy is None))
        self.assertIs(self.game.grid[self.spot(30, 20)][2], houseWall)

    def test_it_breaks_a_corrupted_rock_wall_near_a_building(self):
        rock = wall.StoneWall()
        rock.corruptedBy = "glowcap"
        self.game.grid[self.spot(28, 22)] = [WALL, 1, rock]
        self.addDweller(enemies.DwellerCitizen, 28, 26)
        self.assertTrue(self.runQuiet(80, until=lambda: self.game.grid[self.spot(28, 22)][0] == FLOOR))

    def test_plants_far_from_any_building_are_left(self):
        self.plant(30, 40)
        self.addDweller(enemies.DwellerCitizen, 30, 42)
        self.runQuiet(20)
        self.assertEqual(self.game.grid[self.spot(30, 40)][0], PLANT)

    def test_without_overgrowth_nobody_clears(self):
        self.game.floorEvents.pop(self.game.level)
        self.plant(30, 22)
        self.addDweller(enemies.DwellerCitizen, 30, 27)
        self.runQuiet(20)
        self.assertEqual(self.game.grid[self.spot(30, 22)][0], PLANT)

    def test_two_dwellers_go_for_different_plants(self):
        game = self.game
        self.plant(29, 22)
        self.plant(31, 22)
        first = self.addDweller(enemies.DwellerCitizen, 30, 26)
        second = self.addDweller(enemies.DwellerCitizen, 30, 27)
        quelling.quellTurn(game, self.spot(30, 26), first)
        quelling.quellTurn(game, self.spot(30, 27), second)
        self.assertNotEqual(first.quellTarget, second.quellTarget)


class WhoTests(unittest.TestCase):
    def test_who_comes_out_to_clear(self):
        keeper, grower, carrier, eggCarrier, hatchling = (enemies.DwellerCitizen() for _ in range(5))
        keeper.work, keeper.farmRole = "farm", "keeper"
        grower.work, grower.farmRole = "farm", "grower"
        carrier.work = "dew"
        eggCarrier.heldEgg = enemies.DwellerEgg()
        hatchling.joining = "mine"
        clears = {unit: quelling.quells(unit) for unit in (enemies.DwellerCitizen(), enemies.DwellerNoble(), enemies.DwellerGuard(),
                                                          grower, keeper, enemies.DwellerMerchant(), carrier, eggCarrier, hatchling)}
        self.assertEqual(list(clears.values()), [True, True, True, True, False, False, False, False, False])


class BuildersPickingTests(PenTest):
    def test_a_site_with_wild_plants_on_it_is_fine_and_they_are_cleared_with_it(self):
        game = self.game
        wild = self.spot(51, 40)
        game.grid[wild] = [PLANT, 1, plants.Plant.grown("glowcap")]
        site = {"box": {wild, self.spot(52, 40)}}
        self.assertEqual(dwellerbuilding.siteRock(game, site, set()), {wild}, "not turned down: it's to be cleared")
        plan = {"kind": "pen", "box": site["box"], "walls": set(), "inside": frozenset(site["box"]), "door": self.spot(52, 40),
                "outside": self.spot(53, 40), "chests": []}
        self.assertEqual(dwellerbuilding.pieces(game, plan), [("dig", wild)])

    def test_picking_a_wild_plant_is_one_swing_and_the_builder_keeps_what_it_gives(self):
        game = self.game
        farmer = self.farmer(50, 40)
        game.grid[self.spot(51, 40)] = [PLANT, 1, plants.Plant.grown("glowcap")]
        plan = {"kind": "pen", "box": {self.spot(51, 40)}, "walls": set(), "inside": frozenset({self.spot(51, 40)}),
                "door": self.spot(51, 40), "outside": self.spot(50, 40), "chests": []}
        dwellerbuilding.build(game, self.spot(50, 40), farmer, plan)
        self.assertEqual(game.grid[self.spot(51, 40)][0], FLOOR)

    def test_a_crop_still_keeps_a_site_off(self):
        game = self.game
        crop = plants.Plant.grown("glowcap")
        crop.planted = True
        game.grid[self.spot(51, 40)] = [PLANT, 1, crop]
        site = {"box": {self.spot(51, 40)}}
        self.assertIsNone(dwellerbuilding.siteRock(game, site, set()))

    def test_the_rock_round_a_site_is_dug_out_too(self):
        game = self.game
        rock = self.wallAt(60, 40, wall.StoneWall)
        plan = {"kind": "pen", "box": {self.spot(57, 40)}, "walls": set(), "inside": frozenset({self.spot(57, 40)}),
                "door": self.spot(57, 40), "outside": self.spot(56, 40), "chests": [],
                "margin": {self.spot(58, 40), self.spot(59, 40), self.spot(60, 40)}}
        self.assertIn(("dig", self.spot(60, 40)), dwellerbuilding.pieces(game, plan))


if __name__ == "__main__":
    unittest.main()
