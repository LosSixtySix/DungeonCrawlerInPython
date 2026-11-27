"""Sight in the game (gameManager.rayCircleVision, lightAround and seenFromAfar, all by sight.fieldOfView): what
blocks it, smoke, tremor sense, light, and seeing lit tiles from afar.

Integration tests; the rest are in tests/unit/test_sight.py, tests/acceptance/test_sight.py."""
import unittest

from cruel.entities import enemies
from cruel.world import plants
from tests import support
from tests.helpers.expansion import blankFloor

FLOOR, PLAYER, WALL, ENEMY, PLANT = 0, 1, 2, 5, 8


class SightTest(unittest.TestCase):
    def setUp(self):
        self.game = support.newGame()
        blankFloor(self.game)
        self.rowLength = self.game.rowLength
        self.here = self.spot(30, 20)
        support.placePlayer(self.game, self.here)
        self.game.currentLocation = [FLOOR, 1]
        self.game.smoke = {}

    def spot(self, column, row):
        return column + row * self.rowLength

    def wall(self, column, row):
        self.game.grid[self.spot(column, row)] = [WALL, 0]

    def mine(self, reach=8):
        return self.game.rayCircleVision(self.here, reach, PLAYER)


class WhatBlocksTests(SightTest):
    def test_walls_are_seen_and_hide_what_is_behind(self):
        self.wall(33, 20)
        seen = self.mine()
        self.assertIn(self.spot(33, 20), seen)
        self.assertNotIn(self.spot(35, 20), seen)

    def test_an_enemy_hides_what_is_behind_it_from_you_but_not_from_another_enemy(self):
        self.game.grid[self.spot(33, 20)] = [ENEMY, 1, enemies.Goblin()]
        self.assertIn(self.spot(33, 20), self.mine())
        self.assertNotIn(self.spot(35, 20), self.mine())
        self.assertIn(self.spot(35, 20), self.game.rayCircleVision(self.spot(31, 20), 8, ENEMY), "enemies see past each other")

    def test_a_tall_plant_blocks_sight_a_short_one_does_not(self):
        self.game.grid[self.spot(33, 20)] = [PLANT, 1, plants.Plant("emberroot")]
        self.assertNotIn(self.spot(35, 20), self.mine())
        self.game.grid[self.spot(33, 20)] = [PLANT, 1, plants.Plant("glowcap")]
        self.assertIn(self.spot(35, 20), self.mine())

    def test_smoke_is_seen_into_but_not_through_and_from_inside_it_you_see_beside_you(self):
        self.game.smoke = {self.spot(33, 20): 5}
        seen = self.mine()
        self.assertIn(self.spot(33, 20), seen)
        self.assertNotIn(self.spot(35, 20), seen)
        self.game.smoke = {spot: 5 for spot in self.game.grid}
        self.assertEqual(self.mine(), {self.here} | set(self.game.eightAround(self.here)))

    def test_tremor_sense_feels_through_walls_and_smoke(self):
        for row in range(10, 30):
            self.wall(32, row)
        self.game.smoke = {self.spot(31, 20): 5}
        felt = self.game.rayCircleVision(self.here, 6, ENEMY, tremorSense=True)
        self.assertIn(self.spot(35, 20), felt)

    def test_an_enemy_you_see_sees_you(self):
        for column, row in ((32, 18), (33, 22), (28, 21), (34, 19), (31, 24)):
            self.wall(column, row)
        for spot in self.mine(9):
            if self.game.grid[spot][0] == FLOOR:
                self.assertIn(self.here, self.game.rayCircleVision(spot, 9, ENEMY), f"{spot} can't see back")


class LightTests(SightTest):
    def test_a_fire_lights_the_open_ground_round_it_and_the_wall_faces_but_not_behind_them(self):
        for row in range(10, 30):
            self.wall(35, row)
        lit = self.game.lightAround(self.spot(33, 20), 4)
        self.assertIn(self.spot(31, 20), lit)
        self.assertIn(self.spot(35, 20), lit, "the wall face")
        self.assertNotIn(self.spot(36, 20), lit)

    def test_lit_tiles_far_off_are_seen_if_nothing_is_in_the_way(self):
        far, hidden = self.spot(50, 20), self.spot(30, 40)
        for column in range(25, 36):
            self.wall(column, 35)
        visible = self.game.seenFromAfar({far, hidden}, self.mine(3))
        self.assertEqual(visible, {far})

    def test_from_inside_smoke_no_light_out_there_is_seen(self):
        self.game.smoke = {self.here: 5}
        self.assertEqual(self.game.seenFromAfar({self.spot(50, 20)}, set()), set())


if __name__ == "__main__":
    unittest.main()
