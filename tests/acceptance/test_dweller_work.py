"""The Dwellers at work on their city's works floors (dwellerwork.py): miners breaking seams, farmers tending crops
and Dew Grubs, and everything they get taken to the storehouse chests.

Acceptance tests; the rest are in tests/unit/test_dweller_work.py, tests/integration/test_dweller_work.py."""
import random
import unittest
from unittest import mock
from cruel.inventory import resources
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import expansion
from cruel.world import mineshafts
from tests.helpers.metropolis import cityGame
from tests.helpers.mineshafts import climbDown
from tests.helpers.dweller_work import PLANT


class MineFloorTests(unittest.TestCase):
    def test_a_mine_fills_its_storage_chests_with_ore(self):
        random.seed(3)
        game = cityGame()
        climbDown(game, "mine")
        for _ in range(150):
            game.enemyTurn()
        stored = [stack for spot in dwellerwork.storageChests(game) for stack in game.grid[spot][2]]
        self.assertTrue(any(isinstance(stack, resources.MaterialStack) and stack.materialId != "stone" for stack in stored))

    def test_taking_from_a_storage_chest_is_stealing(self):
        game = cityGame()
        climbDown(game, "mine")
        chestSpot = dwellerwork.storageChests(game)[0]
        game.PlayerLookPosition = chestSpot
        with mock.patch.object(dwellers, "hostileAct") as hostileAct:
            game.tookFromChest()
        hostileAct.assert_called_once_with(game, chestSpot)

    def test_a_worker_that_sees_trouble_stops_working_to_deal_with_it(self):
        game = cityGame()
        climbDown(game, "mine")
        spot, worker = next((spot, game.grid[spot][2]) for spot in game.EnemyPositions if dwellerwork.isWorker(game.grid[spot][2]))
        dwellers.turnHostile(game, worker, game.playerPositionFlat)
        with mock.patch.object(dwellerwork, "workTurn") as workTurn:
            game.grid[spot].pop()
            dwellers.takeTurn(game, spot, worker)
        workTurn.assert_not_called()


class FarmFloorTests(unittest.TestCase):
    def setUp(self):
        random.seed(3)
        self.game = cityGame()
        climbDown(self.game, "farm")

    def test_pens_of_grubs_and_fields_of_crops(self):
        grubs = dwellerwork.grubsHere(self.game)
        self.assertGreaterEqual(len(grubs), mineshafts.PENS[0] * mineshafts.GRUBS_PER_PEN[0])
        crops = [tile[2] for tile in self.game.grid.values() if tile[0] == PLANT and getattr(tile[2], "cityCrop", False)]
        self.assertGreater(len(crops), 5)
        farmers = [self.game.grid[spot][2] for spot in self.game.EnemyPositions
                   if getattr(self.game.grid[spot][2], "work", None) == "farm"]
        self.assertTrue(farmers)
        self.assertTrue(all(farmer.fields is farmers[0].fields for farmer in farmers), "one set of fields for the farm")

    def test_every_pen_can_be_walked_into_from_the_shaft(self):
        reach = expansion.walkingDistances(self.game, self.game.playerPositionFlat, 200)
        for spot, grub in dwellerwork.grubsHere(self.game):
            self.assertTrue(any(tile in reach for tile in grub.pen))

    def test_a_farm_makes_dew(self):
        for _ in range(500):
            self.game.enemyTurn()
        dew = sum(stack.amount for spot in dwellerwork.storageChests(self.game) for stack in self.game.grid[spot][2]
                  if stack.materialId == "dew")
        self.assertGreater(dew, 0)


if __name__ == "__main__":
    unittest.main()
