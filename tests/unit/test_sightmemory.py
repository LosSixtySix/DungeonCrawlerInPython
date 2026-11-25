"""Remembering sight and light between redraws (sightmemory.py): what blocks, keeping a light until a tile it
looked at changes, keeping views until anything blocking changes, and starting again on another floor.

Unit tests; the rest are in tests/integration/test_sightmemory.py."""
import types
import unittest
from unittest import mock

from cruel.world import plants
from cruel.world import sight
from cruel.world import sightmemory

FLOOR, PLAYER, WALL, ENEMY, PLANT, PILE = 0, 1, 2, 5, 8, 9
OPEN = (FLOOR, PLAYER, PILE)
ROW_LENGTH, ROW_COUNT = 30, 20


def openFloor():
    return types.SimpleNamespace(grid={spot: [FLOOR, 0] for spot in range(ROW_LENGTH * ROW_COUNT)}, rowLength=ROW_LENGTH)


def spot(column, row):
    return column + row * ROW_LENGTH


class BlockersTests(unittest.TestCase):
    def test_walls_units_and_tall_plants_block_and_the_rest_does_not(self):
        game = openFloor()
        game.grid[spot(1, 1)] = [WALL, 0]
        game.grid[spot(2, 1)] = [ENEMY, 0, object()]
        game.grid[spot(3, 1)] = [PLANT, 0, plants.Plant("emberroot")]
        game.grid[spot(4, 1)] = [PLANT, 0, plants.Plant("glowcap")]
        game.grid[spot(5, 1)] = [PILE, 0, object()]
        game.grid[spot(6, 1)] = [PLAYER, 0]
        blockers, units = sightmemory.blockersOf(game.grid, ROW_LENGTH, OPEN)
        self.assertEqual(blockers, {spot(1, 1), spot(2, 1), spot(3, 1)})
        self.assertEqual(units, {spot(2, 1)})

    def test_a_tile_missing_from_the_map_blocks(self):
        game = openFloor()
        del game.grid[spot(4, 4)]
        blockers, _ = sightmemory.blockersOf(game.grid, ROW_LENGTH, OPEN)
        self.assertIn(spot(4, 4), blockers)


class LightTests(unittest.TestCase):
    def setUp(self):
        self.game = openFloor()
        self.game.grid[spot(12, 10)] = [WALL, 0]
        self.memory = sightmemory.refresh(self.game, OPEN)
        self.lamp = spot(10, 10)

    def test_a_light_is_worked_out_once_while_nothing_changes(self):
        first = self.memory.lightFrom(self.lamp, 5)
        with mock.patch.object(sight, "fieldOfView", side_effect=AssertionError("worked out again")):
            sightmemory.refresh(self.game, OPEN)
            self.assertIs(self.memory.lightFrom(self.lamp, 5), first)

    def test_it_matches_working_it_out_afresh(self):
        lit = self.memory.lightFrom(self.lamp, 5)
        grid = self.game.grid
        self.assertEqual(lit, sight.fieldOfView(self.lamp, 5, ROW_LENGTH, ROW_COUNT, lambda place: grid[place][0] == WALL))
        self.assertNotIn(spot(14, 10), lit, "the wall shades what's behind it")

    def test_a_change_where_it_looked_works_it_out_again(self):
        self.memory.lightFrom(self.lamp, 5)
        self.game.grid[spot(12, 10)] = [FLOOR, 0]  # (the wall broken)
        sightmemory.refresh(self.game, OPEN)
        self.assertIn(spot(14, 10), self.memory.lightFrom(self.lamp, 5))

    def test_a_unit_stepping_into_it_shades_it(self):
        self.memory.lightFrom(self.lamp, 5)
        self.game.grid[spot(10, 12)] = [ENEMY, 0, object()]
        sightmemory.refresh(self.game, OPEN)
        self.assertNotIn(spot(10, 14), self.memory.lightFrom(self.lamp, 5))

    def test_a_change_out_of_its_reach_keeps_it(self):
        first = self.memory.lightFrom(self.lamp, 5)
        self.game.grid[spot(25, 2)] = [WALL, 0]
        sightmemory.refresh(self.game, OPEN)
        self.assertIs(self.memory.lightFrom(self.lamp, 5), first)

    def test_a_change_behind_a_wall_it_never_looked_past_keeps_it(self):
        game = self.game
        for row in range(5, 16):
            game.grid[spot(12, row)] = [WALL, 0]
        memory = sightmemory.refresh(game, OPEN)
        first = memory.lightFrom(self.lamp, 5)
        game.grid[spot(14, 10)] = [WALL, 0]  # (behind the wall, in reach)
        sightmemory.refresh(game, OPEN)
        self.assertIs(memory.lightFrom(self.lamp, 5), first)


class ViewTests(unittest.TestCase):
    def test_a_view_is_kept_until_anything_blocking_changes(self):
        game = openFloor()
        memory = sightmemory.refresh(game, OPEN)
        workedOut = []
        work = lambda: workedOut.append(1) or len(workedOut)
        memory.remember("view", work)
        sightmemory.refresh(game, OPEN)
        self.assertEqual(memory.remember("view", work), 1)
        game.grid[spot(25, 2)] = [WALL, 0]
        sightmemory.refresh(game, OPEN)
        self.assertEqual(memory.remember("view", work), 2)

    def test_a_unit_changing_places_with_a_wall_counts_as_a_change(self):
        game = openFloor()
        game.grid[spot(3, 3)] = [WALL, 0]
        memory = sightmemory.refresh(game, OPEN)
        memory.remember("view", lambda: "before")
        game.grid[spot(3, 3)] = [ENEMY, 0, object()]  # (still blocks, but doesn't show its whole face)
        sightmemory.refresh(game, OPEN)
        self.assertEqual(memory.remember("view", lambda: "after"), "after")

    def test_another_floor_starts_again(self):
        game = openFloor()
        memory = sightmemory.refresh(game, OPEN)
        memory.remember("view", lambda: "first floor")
        game.grid = openFloor().grid
        self.assertEqual(sightmemory.refresh(game, OPEN).remember("view", lambda: "second floor"), "second floor")


class LookedTests(unittest.TestCase):
    def test_field_of_view_says_every_tile_it_asked_about(self):
        asked = set()

        def blocks(place):
            asked.add(place)
            return place == spot(12, 10)

        looked = set()
        sight.fieldOfView(spot(10, 10), 5, ROW_LENGTH, ROW_COUNT, blocks, looked=looked)
        self.assertEqual(looked - {spot(10, 10)}, asked)


if __name__ == "__main__":
    unittest.main()
