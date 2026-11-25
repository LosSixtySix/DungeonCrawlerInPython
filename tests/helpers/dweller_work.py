"""Helpers for the tests of test_dweller_work.py, shared by its unit, integration and acceptance tests."""
import random
import unittest
from cruel.entities import enemies
from cruel.inventory import items
from cruel.world import plants
from cruel.world import wall
from tests import support
from tests.helpers.expansion import blankFloor


FLOOR, WALL, CHEST, ENEMY, PLANT = 0, 2, 3, 5, 8


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



class FarmTest(WorkTest):
    """A pen with a Dew Grub in it, on the open floor; fields placed by each test."""

    def setUp(self):
        super().setUp()
        self.penInside = {self.spot(column, row) for column in range(41, 46) for row in range(31, 35)}
        for column in range(40, 47):
            for row in range(30, 36):
                if self.spot(column, row) not in self.penInside and (column, row) != (43, 30):  # (43, 30): the gate
                    self.wallAt(column, row, wall.PenFence)
        self.grub = enemies.DewGrub()
        self.grub.pen = frozenset(self.penInside)
        self.game.grid[self.spot(43, 33)] = [ENEMY, 1, self.grub]
        self.game.EnemyPositions.add(self.spot(43, 33))
        self.fields = {}

    def crop(self, column, row, kind="bloodcap", stage="harvest"):
        crop = plants.Plant(kind, planted=True)
        crop.stage, crop.timer, crop.cityCrop = stage, 0, True
        self.game.grid[self.spot(column, row)] = [PLANT, 1, crop]
        self.fields[self.spot(column, row)] = kind
        return crop

    def farmer(self, column, row):
        farmer = self.worker(column, row, work="farm")
        farmer.fields = self.fields
        return farmer


def dewMade(game):
    """All the Dew the works have made so far: in this floor's storehouse chests, in the pockets of every Dweller on
    the floors near you (and on their way up or down a shaft), and fed to the Queen (queen.py: her carriers take it
    from the farm's chests to her)."""
    from cruel.world import livingfloors
    from cruel.world import mineshafts
    from cruel.world import occupancy
    from cruel.world import dwellerwork

    def onThisFloor():
        found = sum(stack.amount for spot in dwellerwork.storageChests(game) for stack in game.grid[spot][2]
                    if stack.materialId == "dew")
        for _, unit in occupancy.allUnits(game):
            found += getattr(unit, "materials", {}).get("dew", 0) + getattr(unit, "dew", 0)
        return found

    total = onThisFloor()
    for key in livingfloors.floorsInReach(game):
        if livingfloors.floorData(game, key) is not None:
            with livingfloors.awayFloor(game, key):
                total += onThisFloor()
    total += sum(getattr(unit, "materials", {}).get("dew", 0)
                 for waiting in livingfloors.arrivals(game).values() for unit, _ in waiting)
    return total
