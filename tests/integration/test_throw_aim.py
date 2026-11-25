"""Aiming a throw past an enemy (gameManager.onThrowKey, throwView, renderer.drawAimCursor). The throw still lands on
the first enemy in its way, but the tile you're aiming at is drawn too, so every key visibly moves the aim. (Before,
only the landing spot was drawn: aimed at an enemy, the next few keys seemed to do nothing.)

Integration tests."""
import unittest
from unittest import mock

import pygame

from cruel.entities.enemies import Goblin
from cruel.inventory import recipes
from tests.helpers.gamemanager import FLOOR, ENEMY, RIGHT, keyDown, newGame, standInOpenFloor

ENEMY_DISTANCE = 2


class AimPastAnEnemyTest(unittest.TestCase):
    def setUp(self):
        game = self.game = newGame()
        self.here = standInOpenFloor(game, facing=RIGHT)
        for step in range(1, 7):
            game.grid[self.here + step] = [FLOOR, 1]
        self.enemySpot = self.here + ENEMY_DISTANCE
        game.grid[self.enemySpot] = [ENEMY, 1, Goblin()]
        game.EnemyPositions.add(self.enemySpot)
        game.player.inventory = [recipes.RECIPES_BY_ID["fire_flask"].makeItem(0, 0)]
        game.startThrow(0)
        game.currentAimSpot = self.enemySpot  # (aimed right at the enemy)
        game.refreshThrowAim()

    def aim(self):
        return self.game.throwView()["aim"]


class AimTests(AimPastAnEnemyTest):
    def test_each_key_moves_the_aim_you_see_even_past_the_enemy(self):
        self.assertEqual(self.aim()["target"], self.enemySpot)
        for step in range(1, 4):
            keyDown(self.game, pygame.K_RIGHT)
            self.assertEqual(self.aim()["target"], self.enemySpot + step)

    def test_the_throw_still_lands_on_the_first_enemy_in_the_way(self):
        keyDown(self.game, pygame.K_RIGHT)
        keyDown(self.game, pygame.K_RIGHT)
        self.assertEqual(self.aim()["landing"], self.enemySpot)

    def test_one_key_back_brings_the_aim_back(self):
        keyDown(self.game, pygame.K_RIGHT)
        keyDown(self.game, pygame.K_LEFT)
        self.assertEqual(self.aim()["target"], self.enemySpot)


class DrawingTests(AimPastAnEnemyTest):
    def cursorsDrawn(self):
        """The tiles drawAimCursor was asked to draw on, for one frame."""
        painter = self.game.painter
        with mock.patch.object(painter, "drawAimCursor", wraps=painter.drawAimCursor) as drawAimCursor:
            self.game.draw()
        return [call.args[0] for call in drawAimCursor.call_args_list]

    def test_the_aimed_tile_is_drawn_when_it_is_past_the_landing(self):
        keyDown(self.game, pygame.K_RIGHT)
        self.assertEqual(self.cursorsDrawn(), [self.enemySpot + 1])

    def test_no_cursor_when_the_throw_lands_where_you_aim(self):
        self.assertEqual(self.cursorsDrawn(), [])

    def test_the_cursor_shows_in_the_frame_as_corner_brackets_in_the_potion_color(self):
        game = self.game
        game.messageBools = {name: False for name in game.messageBools}  # (the new game's message covers the screen)
        keyDown(game, pygame.K_RIGHT)
        game.draw()
        painter = game.painter
        tile = painter.screenTile(self.enemySpot + 1)
        fire = tuple(painter.effectColor("Fire"))[:3]
        for corner in (tile.topleft, (tile.right - 1, tile.top), (tile.left, tile.bottom - 1), (tile.right - 1, tile.bottom - 1)):
            self.assertEqual(tuple(painter.win.get_at(corner))[:3], fire, corner)
        self.assertNotEqual(tuple(painter.win.get_at(tile.center))[:3], fire, "the middle stays clear")


if __name__ == "__main__":
    unittest.main()
