"""Fighting over a space two units share (occupancy.py): enemies hit the one with the lowest HP, area damage hits
everyone there, and you choose which to hit in the Attack which? window."""
import random
import unittest
from unittest import mock

import pygame

from cruel.entities import enemies
from cruel.world import expansion
from cruel.world import occupancy
from cruel.world import organizers
from tests import support
from tests.test_gamemanager import keyDown as pressKey
from tests.test_unit_sizes import OccupancyTest


class EnemyHitTests(OccupancyTest):
    def test_the_one_with_the_lowest_hp_is_hit(self):
        strong, weak = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        strong.hp, weak.hp = 9, 2
        self.assertIs(occupancy.victimAt(self.game, self.middle, strong), weak)

    def test_a_tie_goes_either_way(self):
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        first.hp = second.hp = 5
        random.seed(1)
        hit = {id(occupancy.victimAt(self.game, self.middle, first)) for _ in range(40)}
        self.assertEqual(hit, {id(first), id(second)})

    def test_a_goblin_hitting_a_shared_space_hits_the_weaker_and_kills_only_it(self):
        game = self.game
        strong, weak = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        strong.hp, weak.hp = 9, 1
        goblin = enemies.Goblin()
        goblin.damage = 5
        with mock.patch.object(game, "enemyDodge", side_effect=lambda target, damage, position: damage):
            expansion.attack(game, self.middle - 1, goblin, strong, self.middle)
        self.assertEqual(strong.hp, 9)
        self.assertEqual(self.at(self.middle), [strong])

    def test_an_organizer_hits_the_weaker_too(self):
        game = self.game
        strong, weak = self.put(self.middle, enemies.Goblin()), self.put(self.middle, enemies.Goblin())
        strong.hp, weak.hp = 9, 3
        organizer = enemies.SquareOrganizer()
        organizer.aggro, organizer.damage = strong, 1
        with mock.patch.object(game, "enemyDodge", side_effect=lambda target, damage, position: damage):
            organizers.attack(game, self.middle - 1, organizer, self.middle)
        self.assertEqual((strong.hp, weak.hp), (9, 2))


class AreaTests(OccupancyTest):
    def blast(self, effect, power=50):
        self.game.land({"landing": self.middle, "effect": effect, "power": power})

    def test_a_bomb_hits_both_on_a_space(self):
        self.put(self.middle, enemies.DireRat())
        self.put(self.middle, enemies.DireRat())
        with mock.patch("cruel.core.gamemanager.FLOOR_BREAK_CHANCE", 0):
            self.blast("Explosive")
        self.assertEqual(self.at(self.middle), [])

    def test_fire_and_magic_hit_both_on_a_space(self):
        for effect in ("Fire", "Magic"):
            with self.subTest(effect=effect):
                first, second = self.put(self.middle, enemies.Goblin()), self.put(self.middle, enemies.Goblin())
                first.hp = second.hp = 100
                self.blast(effect, power=5)
                self.assertLess(first.hp, 100)
                self.assertLess(second.hp, 100)
                for unit in (first, second):
                    if unit in self.at(self.middle):
                        self.game.killEnemy(self.middle, killer=None, unit=unit)

    def test_a_bomb_hits_a_small_unit_under_a_giant_too(self):
        game = self.game
        giant = enemies.FireGiant()
        game.putGiant(game.grid, self.middle, giant)
        game.EnemyPositions.add(self.middle)
        rat = self.put(self.middle + 1, enemies.DireRat())
        rat.hp = 100
        with mock.patch("cruel.core.gamemanager.FLOOR_BREAK_CHANCE", 0):
            self.blast("Explosive", power=5)
        self.assertLess(rat.hp, 100)

    def test_a_second_unit_that_is_burning_burns(self):
        game = self.game
        self.put(self.middle, enemies.Goblin())
        second = self.put(self.middle, enemies.Goblin())
        second.hp, second.burnTurns = 100, 3
        game.stepBurning()
        self.assertEqual(second.burnTurns, 2)
        self.assertLess(second.hp, 100)


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
