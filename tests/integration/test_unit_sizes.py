"""Unit sizes (occupancy.py): small units share a space two at a time, or with a part of a Fire Giant; medium ones
take a whole space.

Integration tests; the rest are in tests/unit/test_unit_sizes.py, tests/acceptance/test_unit_sizes.py."""
import unittest
from unittest import mock
from cruel.entities import enemies
from cruel.world import dwellers
from cruel.world import expansion
from cruel.world import occupancy
from cruel.world import plants
from cruel.world import wall
from tests import support
from tests.helpers.unit_sizes import FLOOR, OccupancyTest, PLANT


class SharingRuleTests(OccupancyTest):
    def test_a_small_unit_can_join_one_small_unit_on_its_side(self):
        self.put(self.middle, enemies.DireRat())
        self.assertTrue(occupancy.canJoin(self.game, self.middle, enemies.Goblin()))
        self.assertFalse(occupancy.canJoin(self.game, self.middle, enemies.GoblinChief()), "a medium unit can't")

    def test_no_third_and_never_onto_a_medium_unit(self):
        self.put(self.middle, enemies.DireRat())
        self.put(self.middle, enemies.DireRat())
        self.assertFalse(occupancy.canJoin(self.game, self.middle, enemies.DireRat()))
        self.put(self.middle + 1, enemies.DireMole())
        self.assertFalse(occupancy.canJoin(self.game, self.middle + 1, enemies.DireRat()))

    def test_only_units_on_the_same_side_share(self):
        self.put(self.middle, enemies.DwellerCitizen())
        self.assertTrue(occupancy.canJoin(self.game, self.middle, enemies.DwellerGuard()))
        self.assertFalse(occupancy.canJoin(self.game, self.middle, enemies.Goblin()), "a goblin and a Dweller fight")
        goblin = self.put(self.middle + 1, enemies.Goblin())
        goblin.faction = 1
        other = enemies.Goblin()
        other.faction = 2
        self.assertFalse(occupancy.canJoin(self.game, self.middle + 1, other), "goblins of two factions")
        other.faction = 1
        self.assertTrue(occupancy.canJoin(self.game, self.middle + 1, other))

    def test_a_small_unit_can_join_a_part_of_a_giant(self):
        giant = enemies.FireGiant()
        self.game.putGiant(self.game.grid, self.middle, giant)
        self.assertTrue(occupancy.canJoin(self.game, self.middle + 1, enemies.DireRat()))


class MovingTests(OccupancyTest):
    def test_a_rat_steps_onto_a_space_with_a_rat_and_both_stay(self):
        standing = self.put(self.middle, enemies.DireRat())
        mover = self.put(self.middle - 1, enemies.DireRat())
        support.placePlayer(self.game, self.middle + 3)  # (it sees you, straight ahead)
        occupancy.lift(self.game, self.middle - 1, mover)
        position, _ = self.game.enemyAct(self.middle - 1, mover, {}, expansion.beginTurn(self.game))
        occupancy.settle(self.game, position, mover)
        self.assertEqual(position, self.middle)
        self.assertEqual(self.at(self.middle), [standing, mover])
        self.assertEqual(self.game.grid[self.middle - 1][0], FLOOR)

    def test_when_the_first_leaves_the_second_takes_its_place(self):
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        occupancy.lift(self.game, self.middle, first)
        occupancy.leave(self.game, self.middle)
        self.assertIs(occupancy.primaryAt(self.game, self.middle), second)
        self.assertNotIn(self.middle, occupancy.sharedTiles(self.game))
        self.assertIn(self.middle, self.game.EnemyPositions)

    def test_when_the_second_leaves_the_first_stays(self):
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        occupancy.lift(self.game, self.middle, second)
        occupancy.leave(self.game, self.middle)
        self.assertEqual(self.at(self.middle), [first])

    def test_both_units_on_a_space_take_their_turns(self):
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        acted = []
        with mock.patch.object(self.game, "enemyAct", side_effect=lambda position, unit, *rest: (acted.append(unit), (position, unit))[1]):
            self.game.MoveEnemies()
        self.assertIn(first, acted)
        self.assertIn(second, acted)
        self.assertEqual(self.at(self.middle), [first, second])

    def test_dwellers_share_a_doorway_to_get_past_each_other(self):
        column = (self.middle + 1) % self.game.rowLength
        for row in range(len(self.game.grid) // self.game.rowLength):  # a wall down the floor with a one-tile doorway in it
            spot = column + row * self.game.rowLength
            if spot != self.middle + 1:
                self.game.grid[spot] = [2, 1, wall.StoneWall()]
        inDoorway = self.put(self.middle + 1, enemies.DwellerCitizen())
        mover = enemies.DwellerCitizen()
        self.put(self.middle, mover)
        occupancy.lift(self.game, self.middle, mover)
        position = dwellers.stepToward(self.game, self.middle, self.middle + 2, unit=mover)
        occupancy.settle(self.game, position, mover)
        self.assertEqual(position, self.middle + 1)
        self.assertEqual(self.at(self.middle + 1), [inDoorway, mover])

    def test_a_goblin_steps_onto_a_space_with_a_goblin(self):
        standing = self.put(self.middle, enemies.Goblin())
        mover = self.put(self.middle - 1, enemies.Goblin())
        occupancy.lift(self.game, self.middle - 1, mover)
        position = expansion.step(self.game, self.middle - 1, mover, self.middle + 3, set())
        occupancy.settle(self.game, position, mover)
        self.assertEqual(self.at(self.middle), [standing, mover])

    def test_a_giant_steps_over_a_small_unit_which_stays_under_it(self):
        giant = enemies.FireGiant()
        self.game.putGiant(self.game.grid, self.middle, giant)
        self.game.EnemyPositions.add(self.middle)
        rat = self.put(self.middle + 2, enemies.DireRat())
        self.assertTrue(self.game.canFit(self.middle + 1, giant.size, own=set(self.game.footprint(self.middle, giant.size)), giant=giant))
        self.game.liftGiant(self.game.grid, giant)
        self.game.putGiant(self.game.grid, self.middle + 1, giant)
        self.assertEqual(self.at(self.middle + 2), [giant, rat])
        self.game.liftGiant(self.game.grid, giant)  # it moves off again: the rat has the space
        self.game.putGiant(self.game.grid, self.middle + 2 * self.game.rowLength, giant)
        self.assertEqual(self.at(self.middle + 2), [rat])
        self.assertIn(self.middle + 2, self.game.EnemyPositions)


class KeepingTilesWholeTests(OccupancyTest):
    def test_leaving_never_spoils_a_tile_no_unit_was_lifted_off(self):
        plant = plants.Plant.grown("glowcap")
        self.game.grid[self.middle] = [PLANT, 1, plant]  # (the first unit there went by some other way: the plant is back)
        second = enemies.Goblin()
        occupancy.sharedTiles(self.game)[self.middle] = second
        occupancy.leave(self.game, self.middle)
        self.assertIs(occupancy.primaryAt(self.game, self.middle), second, "the second takes the space")
        self.assertIs(self.game.enemyOccupiedItemSpaces[self.middle][2], plant, "the plant stays under it")
        occupancy.lift(self.game, self.middle, second)
        occupancy.leave(self.game, self.middle)
        self.assertEqual(self.game.grid[self.middle][0], PLANT)
        self.assertIs(self.game.grid[self.middle][2], plant)

    def test_a_second_unit_on_a_space_never_swaps(self):
        first, second = self.put(self.middle, enemies.Goblin()), self.put(self.middle, enemies.Goblin())
        other = self.put(self.middle + 1, enemies.Goblin())
        for goblin in (first, second, other):
            goblin.faction = 1
        self.game.movedEnemies = {self.middle + 1}
        occupancy.lift(self.game, self.middle, second)
        self.assertIsNone(expansion.swapWith(self.game, expansion.beginTurn(self.game), self.middle, second, [self.middle + 1]))
        self.assertEqual(self.at(self.middle + 1), [other])


if __name__ == "__main__":
    unittest.main()
