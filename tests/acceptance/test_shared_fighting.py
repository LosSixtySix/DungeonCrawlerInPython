"""Fighting over a space two units share (occupancy.py): enemies hit the one with the lowest HP, area damage hits
everyone there, and you choose which to hit in the Attack which? window.

Acceptance tests; the rest are in tests/integration/test_shared_fighting.py."""
import unittest
from unittest import mock
import pygame
from cruel.entities import enemies
from tests import support
from tests.helpers.gamemanager import keyDown as pressKey
from tests.helpers.unit_sizes import OccupancyTest


class ChoosingTests(OccupancyTest):
    def setUp(self):
        super().setUp()
        game = self.game
        support.placePlayer(game, self.middle - 1)
        game.PlayerLookPosition = self.middle
        self.goblin, self.rat = self.put(self.middle, enemies.Goblin()), self.put(self.middle, enemies.DireRat())
        self.goblin.hp = self.rat.hp = 100
        game.enemyMove = False

    def test_attacking_a_shared_space_opens_a_window_of_their_names_and_takes_no_turn(self):
        game = self.game
        pressKey(game, pygame.K_e)
        self.assertEqual(game.focus, "attack")
        self.assertEqual(game.windowSpec("attack")["rows"], [("Goblin", ""), ("Dire Rat", "")])
        self.assertEqual(game.windowSel["attack"], 0, "the > starts on the first")
        self.assertFalse(game.enemyMove)
        self.assertEqual((self.goblin.hp, self.rat.hp), (100, 100))

    def test_w_s_and_the_arrows_move_the_marker_and_e_hits_the_one_marked(self):
        game = self.game
        for down, up in ((pygame.K_s, pygame.K_w), (pygame.K_DOWN, pygame.K_UP)):
            with self.subTest(keys=(down, up)):
                pressKey(game, pygame.K_e)
                pressKey(game, down)
                self.assertEqual(game.windowSel["attack"], 1)
                pressKey(game, up)
                self.assertEqual(game.windowSel["attack"], 0)
                pressKey(game, down)
                with mock.patch.object(game, "enemyDodge", side_effect=lambda target, damage, position: 10):
                    pressKey(game, pygame.K_e)
                self.assertNotIn("attack", game.openWindows)
                self.assertTrue(game.enemyMove)
                game.enemyMove = False
        self.assertEqual((self.goblin.hp, self.rat.hp), (100, 80), "both blows went to the rat")

    def test_escape_closes_it_without_a_blow(self):
        game = self.game
        pressKey(game, pygame.K_e)
        pressKey(game, pygame.K_ESCAPE)
        self.assertNotIn("attack", game.openWindows)
        self.assertFalse(game.enemyMove)
        self.assertEqual((self.goblin.hp, self.rat.hp), (100, 100))

    def test_killing_one_leaves_the_other_and_then_e_just_hits_it(self):
        game = self.game
        self.rat.hp = 1
        pressKey(game, pygame.K_e)
        pressKey(game, pygame.K_s)
        with mock.patch.object(game, "enemyDodge", side_effect=lambda target, damage, position: 5):
            pressKey(game, pygame.K_e)
            self.assertEqual(self.at(self.middle), [self.goblin])
            pressKey(game, pygame.K_e)
        self.assertNotIn("attack", game.openWindows, "one left: no window")
        self.assertEqual(self.goblin.hp, 95)


if __name__ == "__main__":
    unittest.main()
