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
        game = self.game
        standing = self.put(self.middle, enemies.DireRat())
        mover = self.put(self.middle - 1, enemies.DireRat())
        support.placePlayer(game, self.middle + 3)  # (it sees you, straight ahead)
        occupancy.lift(game, self.middle - 1, mover)
        position, _ = game.enemyAct(self.middle - 1, mover, {}, expansion.beginTurn(game))
        occupancy.settle(game, position, mover)
        self.assertEqual(position, self.middle)
        self.assertEqual(self.at(self.middle), [standing, mover])
        self.assertEqual(game.grid[self.middle - 1][0], FLOOR)

    def test_when_the_first_leaves_the_second_takes_its_place(self):
        game = self.game
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        occupancy.lift(game, self.middle, first)
        occupancy.leave(game, self.middle)
        self.assertIs(occupancy.primaryAt(game, self.middle), second)
        self.assertNotIn(self.middle, occupancy.sharedTiles(game))
        self.assertIn(self.middle, game.EnemyPositions)

    def test_when_the_second_leaves_the_first_stays(self):
        game = self.game
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        occupancy.lift(game, self.middle, second)
        occupancy.leave(game, self.middle)
        self.assertEqual(self.at(self.middle), [first])

    def test_both_units_on_a_space_take_their_turns(self):
        game = self.game
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        acted = []
        with mock.patch.object(game, "enemyAct", side_effect=lambda position, unit, *rest: (acted.append(unit), (position, unit))[1]):
            game.MoveEnemies()
        self.assertIn(first, acted)
        self.assertIn(second, acted)
        self.assertEqual(self.at(self.middle), [first, second])

    def test_dwellers_share_a_doorway_to_get_past_each_other(self):
        game = self.game
        column = (self.middle + 1) % game.rowLength
        for row in range(len(game.grid) // game.rowLength):  # a wall down the floor with a one-tile doorway in it
            spot = column + row * game.rowLength
            if spot != self.middle + 1:
                game.grid[spot] = [2, 1, wall.StoneWall()]
        inDoorway = self.put(self.middle + 1, enemies.DwellerCitizen())
        mover = enemies.DwellerCitizen()
        self.put(self.middle, mover)
        occupancy.lift(game, self.middle, mover)
        position = dwellers.stepToward(game, self.middle, self.middle + 2, unit=mover)
        occupancy.settle(game, position, mover)
        self.assertEqual(position, self.middle + 1)
        self.assertEqual(self.at(self.middle + 1), [inDoorway, mover])

    def test_a_goblin_steps_onto_a_space_with_a_goblin(self):
        game = self.game
        standing = self.put(self.middle, enemies.Goblin())
        mover = self.put(self.middle - 1, enemies.Goblin())
        occupancy.lift(game, self.middle - 1, mover)
        position = expansion.step(game, self.middle - 1, mover, self.middle + 3, set())
        occupancy.settle(game, position, mover)
        self.assertEqual(self.at(self.middle), [standing, mover])

    def test_a_giant_steps_over_a_small_unit_which_stays_under_it(self):
        game = self.game
        giant = enemies.FireGiant()
        game.putGiant(game.grid, self.middle, giant)
        game.EnemyPositions.add(self.middle)
        rat = self.put(self.middle + 2, enemies.DireRat())
        self.assertTrue(game.canFit(self.middle + 1, giant.size, own=set(game.footprint(self.middle, giant.size)), giant=giant))
        game.liftGiant(game.grid, giant)
        game.putGiant(game.grid, self.middle + 1, giant)
        self.assertEqual(self.at(self.middle + 2), [giant, rat])
        game.liftGiant(game.grid, giant)  # it moves off again: the rat has the space
        game.putGiant(game.grid, self.middle + 2 * game.rowLength, giant)
        self.assertEqual(self.at(self.middle + 2), [rat])
        self.assertIn(self.middle + 2, game.EnemyPositions)


class KeepingTilesWholeTests(OccupancyTest):
    def test_leaving_never_spoils_a_tile_no_unit_was_lifted_off(self):
        game = self.game
        plant = plants.Plant.grown("glowcap")
        game.grid[self.middle] = [PLANT, 1, plant]  # (the first unit there went by some other way: the plant is back)
        second = enemies.Goblin()
        occupancy.sharedTiles(game)[self.middle] = second
        occupancy.leave(game, self.middle)
        self.assertIs(occupancy.primaryAt(game, self.middle), second, "the second takes the space")
        self.assertIs(game.enemyOccupiedItemSpaces[self.middle][2], plant, "the plant stays under it")
        occupancy.lift(game, self.middle, second)
        occupancy.leave(game, self.middle)
        self.assertEqual(game.grid[self.middle][0], PLANT)
        self.assertIs(game.grid[self.middle][2], plant)

    def test_a_second_unit_on_a_space_never_swaps(self):
        game = self.game
        first, second = self.put(self.middle, enemies.Goblin()), self.put(self.middle, enemies.Goblin())
        other = self.put(self.middle + 1, enemies.Goblin())
        for goblin in (first, second, other):
            goblin.faction = 1
        game.movedEnemies = {self.middle + 1}
        occupancy.lift(game, self.middle, second)
        self.assertIsNone(expansion.swapWith(game, expansion.beginTurn(game), self.middle, second, [self.middle + 1]))
        self.assertEqual(self.at(self.middle + 1), [other])


if __name__ == "__main__":
    unittest.main()
