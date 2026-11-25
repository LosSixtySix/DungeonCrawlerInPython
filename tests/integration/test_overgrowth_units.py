"""Overgrowth hurting every unit, not just you (gameManager.stepPlants, overgrowUnits): a plant that sprouts under a
unit hurts it and grows on under it; planted plants never hurt anyone.

Integration tests; the rest are in tests/acceptance/test_overgrowth.py."""
import unittest
from unittest import mock

from cruel.core import gamemanager
from cruel.entities import enemies
from cruel.world import events
from cruel.world import livingfloors
from cruel.world import occupancy
from cruel.world import plants
from tests import support
from tests.helpers.expansion import blankFloor

FLOOR, ENEMY, PLANT = 0, 5, 8


class UnitTest(unittest.TestCase):
    def setUp(self):
        self.game = support.newGame(level=1)
        blankFloor(self.game)
        self.game.floorEvents[self.game.level] = {"id": "overgrowth", "turnsLeft": 0, "active": True}
        self.rowLength = self.game.rowLength

    def spot(self, column, row):
        return column + row * self.rowLength

    def place(self, unit, column, row):
        spot = self.spot(column, row)
        self.game.grid[spot] = [ENEMY, 1, unit]
        self.game.EnemyPositions.add(spot)
        unit.speed = 0  # (it stays put)
        return spot

    def sproutOn(self, spots, kind="hearthmoss", planted=False):
        """Run this floor's growth step, sprouting kind on spots. Returns the tile types the step saw there."""
        grid = self.game.grid
        seen = {}

        def sprout(stepGrid, *arguments, **keywords):
            if stepGrid is not grid:
                return False
            for spot in spots:
                seen[spot] = stepGrid[spot][0]
                plant = plants.Plant.grown(kind)
                plant.planted = planted
                stepGrid[spot] = [PLANT, stepGrid[spot][1], plant]
            return True

        with mock.patch.object(plants, "step", sprout):
            self.game.stepPlants()
        return seen

    def onGrowthTurn(self):
        growTurns = events.plantRules(self.game.activeEvent()).get("growTurns", plants.GROW_TURNS)
        self.game.turnCount = -self.game.growthOffset(growTurns) % growTurns


class SproutingTests(UnitTest):
    def test_the_step_sees_bare_floor_under_a_unit_and_the_sprout_hurts_it_and_grows_under_it(self):
        goblin = enemies.Goblin()
        spot = self.place(goblin, 30, 20)
        before = goblin.hp
        self.onGrowthTurn()
        self.assertEqual(self.sproutOn([spot]), {spot: FLOOR})
        self.assertEqual(goblin.hp, before - gamemanager.OVERGROWTH_DAMAGE)
        self.assertIs(self.game.grid[spot][2], goblin, "it stays where it is")
        self.assertEqual(self.game.enemyOccupiedItemSpaces[spot][0], PLANT, "the plant is under it")

    def test_one_killed_by_it_leaves_the_plant_there(self):
        goblin = enemies.Goblin()
        goblin.hp, goblin.gold = 1, 0  # (nothing to drop: what it drops would lie there instead)
        spot = self.place(goblin, 30, 20)
        self.onGrowthTurn()
        self.sproutOn([spot])
        self.assertEqual(self.game.grid[spot][0], PLANT)
        self.assertNotIn(spot, self.game.EnemyPositions)
        game = self.game
        besideIt = [p for p in game.neighbors(spot) if game.bodyAt(p) is not None]
        self.assertEqual([game.bodyAt(p).unitName for p in besideIt], ["Goblin"], "its body is pushed aside")

    def test_two_sharing_a_space_are_both_hurt(self):
        first, second = enemies.DwellerCitizen(), enemies.DwellerCitizen()
        spot = self.place(first, 30, 20)
        occupancy.sharedTiles(self.game)[spot] = second
        self.onGrowthTurn()
        self.sproutOn([spot])
        self.assertEqual((first.hp, second.hp), (first.maxHp - 2, second.maxHp - 2))

    def test_a_giant_is_hurt_once_and_nothing_grows_on_its_body(self):
        game = self.game
        giant = enemies.FireGiant()
        anchor = self.spot(30, 20)
        game.putGiant(game.grid, anchor, giant)
        game.EnemyPositions.add(anchor)
        giant.speed = 0
        body = game.footprint(anchor, 2)
        self.onGrowthTurn()
        self.sproutOn(body)
        self.assertEqual(giant.hp, giant.maxHp - gamemanager.OVERGROWTH_DAMAGE)
        self.assertFalse(set(body) & set(game.enemyOccupiedItemSpaces))
        self.assertTrue(all(game.grid[tile][2] is giant for tile in body))

    def test_a_planted_plant_hurts_no_unit_and_not_you(self):
        game = self.game
        goblin = enemies.Goblin()
        spot = self.place(goblin, 30, 20)
        self.onGrowthTurn()
        self.sproutOn([spot], planted=True)
        self.assertEqual(goblin.hp, goblin.maxHp)
        planted = plants.Plant.grown("hearthmoss")
        planted.planted = True
        game.player.damageTaken = 0
        game.overgrowPlayer([PLANT, 1, planted])
        self.assertEqual(game.player.damageTaken, 0)

    def test_without_overgrowth_nothing_grows_under_units(self):
        self.game.floorEvents.pop(self.game.level)
        spot = self.place(enemies.Goblin(), 30, 20)
        self.onGrowthTurn()
        self.assertEqual(self.sproutOn([spot]), {spot: ENEMY}, "the step sees the unit, not floor under it")


class AwayTests(unittest.TestCase):
    def test_units_on_a_floor_you_are_not_on_are_hurt_too(self):
        game = support.newGame(level=3)
        game.changeLevel(2)
        data = game.levelGrids[1]
        game.floorEvents[1] = {"id": "overgrowth", "turnsLeft": 0, "active": True}
        grid = data[0]
        spot = next(spot for spot, tile in grid.items() if tile[0] == FLOOR)
        goblin = enemies.Goblin()
        goblin.speed = 0
        grid[spot] = [ENEMY, 0, goblin]
        data[3].add(spot)
        real = plants.step

        def sprout(stepGrid, *arguments, **keywords):
            if stepGrid is not grid:
                return real(stepGrid, *arguments, **keywords)
            stepGrid[spot] = [PLANT, stepGrid[spot][1], plants.Plant.grown("hearthmoss")]
            return True

        with livingfloors.awayFloor(game, 1):
            growTurns = events.plantRules(game.activeEvent()).get("growTurns", plants.GROW_TURNS)
            turn = -game.growthOffset(growTurns) % growTurns
        game.turnCount = turn
        with mock.patch.object(plants, "step", sprout):
            livingfloors.simulate(game)
        self.assertEqual(goblin.hp, goblin.maxHp - gamemanager.OVERGROWTH_DAMAGE)


if __name__ == "__main__":
    unittest.main()
