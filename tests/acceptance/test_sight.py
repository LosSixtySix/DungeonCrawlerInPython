"""Sight, played: walking with the movement keys and looking at what the map shows in view.

Acceptance tests; the rest are in tests/unit/test_sight.py, tests/integration/test_sight.py."""
import unittest

from cruel.world import wall
from tests import support
from tests.helpers.expansion import blankFloor
from tests.helpers.gamemanager import keyDown

FLOOR, WALL = 0, 2
IN_VIEW = 1


class WalkingTests(unittest.TestCase):
    def setUp(self):
        self.game = support.newGame()
        blankFloor(self.game)
        self.rowLength = self.game.rowLength
        support.placePlayer(self.game, self.spot(40, 30))
        self.game.currentLocation = [FLOOR, 1]
        self.game.player.visionRange = 12  # (far: where the old rays left holes)

    def spot(self, column, row):
        return column + row * self.rowLength

    def walk(self, action, steps):
        game = self.game
        for _ in range(steps):
            game.enemyMove = False  # (the game loop does this once the world has taken its turn)
            keyDown(game, game.settings.hotkeys[action])
        game.setPositionsVisible()  # (as the game loop does after you act)

    def inView(self):
        return {spot for spot, tile in self.game.grid.items() if tile[1] == IN_VIEW}

    def test_out_in_the_open_nothing_in_range_is_missing(self):
        game = self.game
        self.walk("move_right", 3)
        here = game.playerPositionFlat
        column, row = here % self.rowLength, here // self.rowLength
        reach = game.player.getVisionRange()
        circle = {self.spot(column + stepColumn, row + stepRow)
                  for stepColumn in range(-reach, reach + 1) for stepRow in range(-reach, reach + 1)
                  if stepColumn * stepColumn + stepRow * stepRow <= reach * reach + reach}
        self.assertEqual(circle - self.inView(), set())

    def test_nothing_shows_through_a_diagonal_wall(self):
        game = self.game
        for step in range(-14, 15):  # a wall from top left to bottom right, its tiles touching only at corners
            game.grid[self.spot(48 + step, 30 + step)] = [WALL, 0, wall.StoneWall()]
        self.walk("move_right", 3)  # (to (43, 30): below the wall)
        beyond = {spot for spot in game.grid
                  if 30 <= spot % self.rowLength <= 60 and 15 <= spot // self.rowLength <= 45
                  and spot // self.rowLength - 30 < spot % self.rowLength - 48 and game.grid[spot][0] == FLOOR}
        self.assertEqual(beyond & self.inView(), set())
        self.assertIn(self.spot(48, 30), self.inView(), "the wall itself is in view")


if __name__ == "__main__":
    unittest.main()
