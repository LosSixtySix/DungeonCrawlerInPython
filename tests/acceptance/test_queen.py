"""The Dweller Queen, played: walking up to her in a real city, seeing her drawn, and fighting her.

Acceptance tests; the rest are in tests/unit/test_queen.py, tests/integration/test_queen.py."""
import unittest
from unittest import mock

from cruel.graphics import renderer
from cruel.world import queen
from tests import support
from tests.helpers.metropolis import cityGame

FLOOR = 0
FACINGS = {-1: 0, 1: 1}  # a step left or right: the player's direction (0 left, 1 right)


class QueenInHerChamberTests(unittest.TestCase):
    def setUp(self):
        self.game = cityGame()
        self.anchor, self.queen = queen.courtOf(self.game)
        game = self.game
        body = set(game.footprint(self.anchor, 2))
        beside = [spot for tile in body for spot in game.neighbors(tile)
                  if spot not in body and game.grid[spot][0] == FLOOR and spot // game.rowLength in {tile // game.rowLength for tile in body}]
        self.besideHer = beside[0]
        self.towardHer = 1 if any(self.besideHer + 1 == tile for tile in body) else -1
        support.placePlayer(game, self.besideHer)
        game.player.playerDirection = FACINGS[self.towardHer]
        game.setLookPosition()
        for spot in game.grid:
            game.grid[spot][1] = 1

    def test_she_is_drawn_from_her_own_picture_over_her_four_tiles(self):
        game = self.game
        with mock.patch.object(renderer.renderer, "giantQuarter", wraps=game.painter.giantQuarter) as giantQuarter:
            game.change = True
            game.draw()
        drawnFor = {call.args[0] for call in giantQuarter.call_args_list if call.args[1] is self.queen}
        self.assertTrue(drawnFor and drawnFor <= set(game.footprint(self.anchor, 2)))

    def test_you_hit_her_she_turns_on_you_and_hits_back(self):
        game = self.game
        self.assertEqual(game.lookingAt().split(" (")[0], "Dweller Queen")
        game.player.DealDamage = lambda: 5
        game.enemyDodge = lambda target, damage, position: damage
        game.player.evasion = lambda: 0
        game.onInteract()
        self.assertTrue(self.queen.hostile)
        self.assertEqual(self.queen.hp, self.queen.maxHp - 5)
        game.player.damageTaken = 0
        game.enemyTurn()
        self.assertGreater(game.player.damageTaken, 0, "she hits back")
        self.assertEqual(queen.courtOf(game), (self.anchor, self.queen), "without moving")


if __name__ == "__main__":
    unittest.main()
