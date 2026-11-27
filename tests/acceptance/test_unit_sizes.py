"""Unit sizes (occupancy.py): small units share a space two at a time, or with a part of a Fire Giant; medium ones
take a whole space.

Acceptance tests; the rest are in tests/unit/test_unit_sizes.py, tests/integration/test_unit_sizes.py."""
import unittest
from unittest import mock
from cruel.entities import enemies
from cruel.graphics import renderer
from cruel.world import occupancy
from tests import support
from tests.helpers.unit_sizes import OccupancyTest


class EverythingElseTests(OccupancyTest):
    def test_killing_the_first_leaves_the_second(self):
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        self.game.killEnemy(self.middle, killer=None)
        self.assertEqual(self.at(self.middle), [second])

    def test_killing_the_second_leaves_the_first(self):
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        self.game.killEnemy(self.middle, killer=None, unit=second)
        self.assertEqual(self.at(self.middle), [first])

    def test_both_fall_when_the_floor_gives_way(self):
        self.put(self.middle, enemies.DireRat())
        self.put(self.middle, enemies.DireRat())
        self.game.collapseFloor(self.middle, 0)
        self.assertEqual(self.at(self.middle), [])
        self.assertEqual(len(self.game.fallen[self.game.level + 1]), 2)

    def test_looking_at_a_shared_space_names_both(self):
        self.put(self.middle, enemies.Goblin())
        self.put(self.middle, enemies.DireRat())
        self.game.PlayerLookPosition = self.middle
        self.assertEqual(self.game.lookingAt(), "Goblin and Dire Rat")

    def test_every_unit_is_found_second_ones_too(self):
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        self.assertCountEqual([unit for _, unit in occupancy.allUnits(self.game)], [first, second])

    def test_a_floor_keeps_its_second_units_when_you_leave_and_come_back(self):
        self.put(self.middle, enemies.DireRat())
        second = self.put(self.middle, enemies.DireRat())
        self.game.saveLevel()
        self.game.grid = {}  # (another floor)
        self.game.LoadLevel(self.game.level)
        self.assertIs(occupancy.sharedTiles(self.game).get(self.middle), second)

    def test_two_on_a_space_are_drawn_smaller_side_by_side(self):
        self.put(self.middle, enemies.DireRat())
        self.put(self.middle, enemies.Goblin())
        support.placePlayer(self.game, self.middle + 2)
        self.game.revealMap = True
        self.game.setPositionsVisible()
        with mock.patch.object(renderer.renderer, "drawUnit", autospec=True, side_effect=renderer.renderer.drawUnit) as drawUnit:
            self.game.draw()
        small = [call for call in drawUnit.call_args_list if call.kwargs.get("small")]
        self.assertEqual(len(small), 2)


if __name__ == "__main__":
    unittest.main()
