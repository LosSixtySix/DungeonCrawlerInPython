"""Waiting a turn (the Wait hotkey, Space by default: gameManager.waitTurn): you do nothing and the world takes its
turn, as if you'd stepped.

Integration tests."""
import unittest

import pygame

from cruel.core import settings
from tests.helpers.gamemanager import clearAround, keyDown, middleSpot, newGame, placePlayer


class WaitTest(unittest.TestCase):
    def setUp(self):
        self.game = newGame()
        self.here = middleSpot(self.game)
        clearAround(self.game, self.here)
        placePlayer(self.game, self.here)

    def endFrame(self):
        """What the game's loop does with your action at the end of the frame (gameManager.RunGame)."""
        if self.game.enemyMove:
            self.game.spendActions(1)
            self.game.enemyMove = False


class WaitTests(WaitTest):
    def test_space_is_wait_by_default_and_it_is_in_the_hotkeys_menu(self):
        self.assertEqual(settings.DEFAULT_HOTKEYS["wait"], pygame.K_SPACE)
        self.assertEqual(settings.ACTION_LABELS["wait"], "Wait a Turn")

    def test_space_spends_your_action_and_you_stay_put(self):
        self.game.player.startRound()
        actionsAllowed = self.game.player.actionsAllowed
        turn = self.game.turnCount
        for _ in range(actionsAllowed):
            keyDown(self.game, pygame.K_SPACE)
            self.endFrame()
        self.assertEqual(self.game.turnCount, turn + 1, "the world took its turn")
        self.assertEqual(self.game.playerPositionFlat, self.here)

    def test_it_waits_with_a_window_open_too(self):
        keyDown(self.game, settings.DEFAULT_HOTKEYS["inventory"])
        self.assertEqual(self.game.focus, "inventory")
        keyDown(self.game, pygame.K_SPACE)
        self.assertTrue(self.game.enemyMove)

    def test_holding_it_keeps_waiting(self):
        self.assertTrue(self.game.isRepeatable(pygame.K_SPACE))
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0)
        self.game.onKeyDown(event)
        self.endFrame()
        self.game.onKeyDown(event)  # (held: the key repeating)
        self.assertTrue(self.game.enemyMove)

    def test_rebound_wait_follows_its_new_key(self):
        self.game.settings.rebind("wait", pygame.K_z)
        try:
            keyDown(self.game, pygame.K_SPACE)
            self.assertFalse(self.game.enemyMove)
            keyDown(self.game, pygame.K_z)
            self.assertTrue(self.game.enemyMove)
        finally:
            self.game.settings.resetHotkeys()

    def test_a_move_key_you_had_put_on_space_keeps_moving_you(self):
        self.game.settings.hotkeys["move_right"] = pygame.K_SPACE  # (bound before Wait was added)
        try:
            keyDown(self.game, pygame.K_SPACE)
            self.assertEqual(self.game.playerPositionFlat, self.here + 1)
        finally:
            self.game.settings.resetHotkeys()


if __name__ == "__main__":
    unittest.main()
