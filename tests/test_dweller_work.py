"""The Dwellers at work on their city's works floors (dwellerwork.py): miners breaking seams and taking what they
get to the storehouse chests."""
import random
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.inventory import items
from cruel.inventory import resources
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import metropolis
from cruel.world import wall
from tests import support
from tests.test_expansion import blankFloor
from tests.test_mineshafts import cityGame, climbDown

FLOOR, WALL, CHEST, ENEMY = 0, 2, 3, 5


class WorkTest(unittest.TestCase):
    """An open floor with you far off in the top-left corner; walls, chests and workers placed by each test."""

    def setUp(self):
        random.seed(5)
        self.game = support.newGame()
        blankFloor(self.game)
        self.rowLength = self.game.rowLength

    def spot(self, column, row):
        return column + row * self.rowLength

    def worker(self, column, row, work="mine"):
        worker = enemies.DwellerCitizen()
        worker.work = work
        worker.home = self.spot(column, row)
        self.game.grid[self.spot(column, row)] = [ENEMY, 1, worker]
        self.game.EnemyPositions.add(self.spot(column, row))
        return worker

    def storageChest(self, column, row):
        chest = items.StorageChest()
        self.game.grid[self.spot(column, row)] = [CHEST, 1, chest]
        return chest

    def wallAt(self, column, row, kind=wall.StoneWall):
        self.game.grid[self.spot(column, row)] = [WALL, 1, kind()]
        return self.game.grid[self.spot(column, row)][2]

    def positionOf(self, unit):
        return next(spot for spot in self.game.EnemyPositions if self.game.grid[spot][2] is unit)

    def runTurns(self, count, until):
        for _ in range(count):
            self.game.enemyTurn()
            if until():
                return True
        return False


class MinerTests(WorkTest):
    def test_a_miner_breaks_the_seam_beside_it_and_pockets_the_ore(self):
        miner = self.worker(40, 30)
        self.wallAt(41, 30, wall.IronVein)
        self.storageChest(10, 60)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            self.assertTrue(self.runTurns(20, until=lambda: self.game.grid[self.spot(41, 30)][0] == FLOOR))
        self.assertIn("iron_ore", dwellerwork.carrying(miner))

    def test_it_goes_to_the_nearest_seam_it_can_reach(self):
        miner = self.worker(40, 30)
        self.wallAt(50, 30, wall.CopperVein)
        self.wallAt(46, 30, wall.IronVein)
        self.assertEqual(dwellerwork.pickSeam(self.game, self.spot(40, 30), miner), self.spot(46, 30))

    def test_gold_walls_are_seams_too(self):
        self.assertTrue(dwellerwork.isSeam([WALL, 1, wall.GoldWall()]))
        self.assertFalse(dwellerwork.isSeam([WALL, 1, wall.StoneWall()]))

    def test_with_no_seam_in_reach_it_tunnels_toward_the_nearest(self):
        miner = self.worker(40, 30)
        for row in range(0, 80):  # a wall of rock between it and the seam
            if self.spot(44, row) in self.game.grid:
                self.wallAt(44, row)
        self.wallAt(60, 30, wall.SilverVein)
        self.assertEqual(dwellerwork.pickSeam(self.game, self.spot(40, 30), miner), self.spot(44, 30))

    def test_it_never_breaks_the_citys_walls(self):
        miner = self.worker(40, 30)
        for column in range(38, 43):  # shut in a storehouse, with a seam outside it
            for row in range(28, 33):
                if max(abs(column - 40), abs(row - 30)) == 2:
                    self.wallAt(column, row, wall.ShopWall)
        self.wallAt(50, 30, wall.IronVein)
        self.assertIsNone(dwellerwork.pickSeam(self.game, self.spot(40, 30), miner))

    def test_it_never_breaks_a_wall_a_lamp_hangs_on(self):
        game = self.game
        miner = self.worker(40, 30)
        self.wallAt(40, 31, wall.IronVein)
        game.sideFloor = ("mine", 0)  # (a works floor: it has lamps)
        game.wallLamps = {game.level: {self.spot(40, 30): metropolis.WallLamp("down", 3)}}  # hung on the vein
        self.assertIsNone(dwellerwork.pickSeam(game, self.spot(40, 30), miner))

    def test_two_miners_do_not_work_the_same_seam(self):
        first, second = self.worker(40, 30), self.worker(40, 32)
        self.wallAt(41, 31, wall.IronVein)
        self.wallAt(48, 31, wall.CopperVein)
        first.target = self.spot(41, 31)
        self.assertEqual(dwellerwork.pickSeam(self.game, self.spot(40, 32), second), self.spot(48, 31))


class HaulingTests(WorkTest):
    def test_a_worker_carrying_something_takes_it_to_the_nearest_storage_chest(self):
        miner = self.worker(40, 30)
        miner.materials = {"iron_ore": 3, "gold": 1}
        chest = self.storageChest(46, 30)
        self.storageChest(80, 60)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            self.assertTrue(self.runTurns(20, until=lambda: not dwellerwork.carrying(miner)))
        self.assertEqual({stack.materialId: stack.amount for stack in chest}, {"iron_ore": 3, "gold": 1})

    def test_it_adds_to_a_stack_of_the_same_thing_up_to_the_limit(self):
        chest = items.StorageChest()
        dwellerwork.putInChest(chest, {"coal": 5})
        dwellerwork.putInChest(chest, {"coal": 4, "stone": 2})
        self.assertEqual([(stack.materialId, stack.amount) for stack in chest], [("coal", 9), ("stone", 2)])
        dwellerwork.putInChest(chest, {"coal": dwellerwork.STACK_LIMIT})
        self.assertEqual(chest[0].amount, dwellerwork.STACK_LIMIT)

    def test_killing_a_worker_gets_you_a_share_of_what_it_carried(self):
        game = self.game
        miner = self.worker(40, 30)
        miner.materials = {"iron_ore": 20}
        game.player.attributes["wisdom"] = 30  # (all of it)
        game.killEnemy(self.spot(40, 30), "player")
        self.assertGreater(game.player.materials.get("iron_ore", 0), 0)


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


if __name__ == "__main__":
    unittest.main()
