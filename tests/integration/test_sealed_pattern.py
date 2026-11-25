"""The Sealed Pattern (relics.py) and Pitch damage. Kill relics.SEALED_PATTERN_KILLS Unsealed on one floor and every other
Unsealed dies, no more come, and a relic chest holding the Sealed Pattern appears at the floor's center
(gameManager.countUnsealedKill, banishUnsealed). Worn, the Pattern costs max health (never below 1); each free hand
gives speed and Pitch damage on every hit; and the Pitch Bolt hotkey (F) fires a bolt of Pitch like a throw that hits
one space and never walls (startPitchBolt, land, pitchEnemy).

Integration tests."""
import os
import tempfile
import unittest
from unittest import mock

import pygame

from cruel.core import gamemanager, settings
from cruel.entities import enemies, playerClass
from cruel.entities.enemies import Goblin, Unsealed
from cruel.inventory import items, recipes, relics
from cruel.world import occupancy, peddler, wall
from tests.support import placePlayer
from tests.helpers.gamemanager import CHEST, ENEMY, FLOOR, RIGHT, WALL, keyDown, newGame, standInOpenFloor

KILLS = relics.SEALED_PATTERN_KILLS
PATTERN_HEALTH = relics.SEALED_PATTERN_HEALTH


def wearPattern(player):
    player.equipment["Gloves"] = relics.make("sealed_pattern")
    player.syncSlots()


def sword():
    return items.equipment("Damage", "Sword", "Hands", 3, "")


class SealedPatternTest(unittest.TestCase):
    def setUp(self):
        game = self.game = newGame()
        self.here = standInOpenFloor(game, facing=RIGHT)
        self.player = game.player

    def putEnemy(self, spot, enemy):
        self.game.grid[spot] = [ENEMY, 1, enemy]
        self.game.EnemyPositions.add(spot)
        return enemy

    def unsealedOnFloor(self):
        return [spot for spot in self.game.EnemyPositions
                if len(self.game.grid[spot]) > 2 and getattr(self.game.grid[spot][2], "name", None) == "Unsealed"]

    def patternChests(self):
        return [spot for spot, tile in self.game.grid.items() if tile[0] == CHEST and len(tile) > 2
                and any(getattr(item, "relicId", None) == "sealed_pattern" for item in tile[2])]


class RelicTests(unittest.TestCase):
    def test_it_is_a_gloves_relic_with_its_own_power(self):
        pattern = relics.make("sealed_pattern")
        self.assertEqual((pattern.name, pattern.slot), ("Sealed Pattern", "Gloves"))
        self.assertEqual(pattern.relicPower, "sealed_pattern")
        self.assertIn("Pitch Bolt", pattern.description)

    def test_it_only_comes_from_the_unsealed(self):
        self.assertNotIn("sealed_pattern", [relicId for relicId, _, _ in relics.CHEST_RELICS])
        self.assertIn("sealed_pattern", peddler.NEVER_SOLD_RELICS)
        self.assertIn("sealed_pattern", relics.BOUND_POWERS, "the Gilded Forge can't rekindle it away")

    def test_a_vault_never_holds_it(self):
        game = newGame()
        with mock.patch.object(gamemanager.rand, "choice", side_effect=lambda choices: choices[-1]) as choice:
            grid = {spot: [FLOOR, 0] for spot in range(game.numberOfSpots)}
            game.placeVault(grid, "workbench", set())
        offered = [call.args[0] for call in choice.call_args_list if call.args and "lantern" in call.args[0]]
        self.assertTrue(offered)
        self.assertNotIn("sealed_pattern", offered[0])


class TriggerTests(SealedPatternTest):
    def killUnsealed(self, times):
        """You kill an Unsealed beside you, times over."""
        for _ in range(times):
            spot = self.here + 1
            self.putEnemy(spot, Unsealed())
            self.game.killEnemy(spot, killer="player")

    def test_199_kills_do_nothing(self):
        self.killUnsealed(KILLS - 1)
        self.assertEqual(self.game.unsealedKills, KILLS - 1)
        self.assertFalse(self.game.unsealedBanished)
        self.assertEqual(self.patternChests(), [])

    def test_the_200th_kill_kills_every_unsealed_and_brings_the_chest(self):
        game = self.game
        game.addUnsealed = True
        others = [self.here + 3 * game.rowLength, self.here - 3 * game.rowLength]
        for spot in others:
            self.putEnemy(spot, Unsealed())
        goblinSpot = self.here - 2
        goblin = self.putEnemy(goblinSpot, Goblin())
        self.killUnsealed(KILLS)
        self.assertTrue(game.unsealedBanished)
        self.assertEqual(self.unsealedOnFloor(), [])
        self.assertIs(game.grid[goblinSpot][2], goblin, "only the Unsealed die")
        self.assertFalse(game.addUnsealed)
        self.assertEqual(len(self.patternChests()), 1)

    def test_a_second_unsealed_sharing_a_space_dies_too(self):
        game = self.game
        spot = self.here + 3 * game.rowLength
        self.putEnemy(spot, Unsealed())
        second = Unsealed()
        occupancy.sharedTiles(game)[spot] = second
        self.killUnsealed(KILLS)
        self.assertNotIn(second, occupancy.sharedTiles(game).values())
        self.assertEqual(self.unsealedOnFloor(), [])

    def test_the_chest_is_at_the_floors_center(self):
        game = self.game
        placePlayer(game, self.here + 4)  # (off the center: the test map puts you right on it)
        center = game.floorCenter()
        rows = game.numberOfSpots // game.rowLength
        self.assertEqual((center % game.rowLength, center // game.rowLength), (game.rowLength // 2, rows // 2))
        game.grid[center] = [WALL, 0, wall.GoldWall()]
        self.killUnsealed(KILLS)
        self.assertEqual(self.patternChests(), [center])

    def test_the_chest_never_lands_on_you(self):
        with mock.patch.object(self.game, "floorCenter", return_value=self.here):
            self.killUnsealed(KILLS)
        chests = self.patternChests()
        self.assertEqual(len(chests), 1)
        self.assertNotEqual(chests[0], self.here)

    def test_kills_by_others_dont_count(self):
        spot = self.here + 1
        self.putEnemy(spot, Unsealed())
        self.game.killEnemy(spot, killer=None)
        self.assertEqual(self.game.unsealedKills, 0)

    def test_other_enemies_dont_count(self):
        spot = self.here + 1
        self.putEnemy(spot, Goblin())
        self.game.killEnemy(spot, killer="player")
        self.assertEqual(self.game.unsealedKills, 0)

    def test_no_more_unsealed_come_and_gold_walls_dont_wake_them(self):
        game = self.game
        game.proportion = "All Gold"
        self.killUnsealed(KILLS)
        game.addUnsealed = True  # (as if something set it again)
        game.grid[self.here + 3] = [WALL, 1, wall.GoldWall()]
        game.enemyTurn()
        self.assertEqual(self.unsealedOnFloor(), [])
        game.goldWallCount = 20
        game.addUnsealed = False
        game.breakWall(self.here + 3)
        self.assertFalse(game.addUnsealed)

    def test_the_count_starts_over_on_a_new_floor(self):
        game = self.game
        self.killUnsealed(KILLS)
        game.goToNewLevel()
        self.assertEqual((game.unsealedKills, game.unsealedBanished), (0, False))

    def test_the_count_is_saved(self):
        game = self.game
        self.killUnsealed(5)
        saveFile = os.path.join(tempfile.mkdtemp(), "sealed-save.pkl")
        gamemanager.gameManager.saveGame(game, saveFile)
        loaded = newGame()
        self.assertTrue(loaded.loadGame(saveFile))
        self.assertEqual((loaded.unsealedKills, loaded.unsealedBanished), (5, False))


class WearingTests(SealedPatternTest):
    def test_it_takes_max_health(self):
        before = self.player.getMaxHealth()
        wearPattern(self.player)
        self.assertEqual(self.player.getMaxHealth(), max(1, before - PATTERN_HEALTH))

    def test_max_health_stops_at_1(self):
        player = self.player
        wearPattern(player)
        self.assertEqual(player.getMaxHealth(), 1, "a fresh character has under 16")
        player.equipment["Chest"] = items.equipment("Health", "Big Coat", "Chest", 30, "")
        self.assertEqual(player.getMaxHealth(), 10 + player.attributeBonuses["constitution"] + 30 - PATTERN_HEALTH)

    def test_putting_it_on_hurt_never_kills_you(self):
        player = self.player
        player.damageTaken = 5
        wearPattern(player)
        self.assertEqual(player.getCurrentHealth(), 1)

    def test_each_free_hand_gives_speed_and_pitch(self):
        player = self.player
        baseSpeed = player.getSpeed()
        self.assertEqual(player.pitchDamage(), 0)
        wearPattern(player)
        self.assertEqual(player.freeHands(), 2)
        self.assertAlmostEqual(player.getSpeed(), baseSpeed + 2 * relics.SEALED_PATTERN_SPEED)
        self.assertEqual(player.pitchDamage(), 2 * relics.SEALED_PATTERN_PITCH)
        player.equipment["Right Hand"] = sword()
        self.assertAlmostEqual(player.getSpeed(), baseSpeed + relics.SEALED_PATTERN_SPEED)
        self.assertEqual(player.pitchDamage(), relics.SEALED_PATTERN_PITCH)
        player.equipment["Left Hand"] = sword()
        self.assertAlmostEqual(player.getSpeed(), baseSpeed)
        self.assertEqual(player.pitchDamage(), 0)

    def test_a_third_hand_counts_when_free(self):
        player = self.player
        player.equipment["Back"] = relics.make("vestigial_hand")
        wearPattern(player)
        self.assertEqual(player.freeHands(), 3)
        self.assertEqual(player.pitchDamage(), 3 * relics.SEALED_PATTERN_PITCH)


class PitchHitTests(SealedPatternTest):
    def swingAt(self, enemy):
        spot = self.here + 1
        self.putEnemy(spot, enemy)
        with mock.patch.object(self.game, "dodge", return_value=None), \
                mock.patch.object(self.player, "DealDamage", return_value=0):
            self.game.attackUnit(spot, enemy)
        return spot

    def test_hits_add_pitch_for_each_free_hand(self):
        wearPattern(self.player)
        goblin = Goblin()
        goblin.hp = goblin.maxHp = 50
        self.swingAt(goblin)
        self.assertEqual(goblin.hp, 50 - 2 * relics.SEALED_PATTERN_PITCH)

    def test_unsealed_resist_pitch(self):
        wearPattern(self.player)
        unsealed = Unsealed()
        unsealed.hp = 50
        self.swingAt(unsealed)
        pitch = 2 * relics.SEALED_PATTERN_PITCH
        self.assertEqual(unsealed.hp, 50 - round(pitch * (1 - enemies.PITCH_RESIST_UNSEALED)))
        self.assertLess(50 - unsealed.hp, pitch)

    def test_no_pattern_no_pitch(self):
        goblin = Goblin()
        goblin.hp = 50
        self.swingAt(goblin)
        self.assertEqual(goblin.hp, 50)

    def test_a_clean_dodge_dodges_the_pitch_too(self):
        wearPattern(self.player)
        goblin = Goblin()
        goblin.hp = 50
        self.putEnemy(self.here + 1, goblin)
        with mock.patch.object(self.game, "dodge", return_value="clean"):
            self.game.attackUnit(self.here + 1, goblin)
        self.assertEqual(goblin.hp, 50)

    def test_a_graze_halves_the_pitch_too(self):
        wearPattern(self.player)
        goblin = Goblin()
        goblin.hp = 50
        self.putEnemy(self.here + 1, goblin)
        with mock.patch.object(self.game, "dodge", return_value="partial"),                 mock.patch.object(self.player, "DealDamage", return_value=4):
            self.game.attackUnit(self.here + 1, goblin)
        pitch = 2 * relics.SEALED_PATTERN_PITCH
        self.assertEqual(50 - goblin.hp, -(-(4 + pitch) // 2))
        self.assertEqual(gamemanager.gameManager.pitchShare(4 + pitch, pitch, -(-(4 + pitch) // 2)), pitch // 2)

    def test_pitch_can_kill(self):
        wearPattern(self.player)
        goblin = Goblin()
        spot = self.swingAt(goblin)
        self.assertNotIn(spot, self.game.EnemyPositions)


class PitchBoltTests(SealedPatternTest):
    def setUp(self):
        super().setUp()
        game = self.game
        for step in range(1, 7):
            game.grid[self.here + step] = [FLOOR, 1]

    def test_f_is_the_pitch_bolt_by_default(self):
        self.assertEqual(settings.DEFAULT_HOTKEYS["pitch_bolt"], pygame.K_f)
        self.assertEqual(settings.ACTION_LABELS["pitch_bolt"], "Pitch Bolt")

    def test_without_the_pattern_f_does_nothing(self):
        keyDown(self.game, pygame.K_f)
        self.assertIsNone(self.game.throwing)
        self.assertFalse(self.game.enemyMove)

    def test_f_aims_and_enter_fires_at_the_first_enemy_in_the_way(self):
        game = self.game
        wearPattern(self.player)
        goblin = self.putEnemy(self.here + 2, Goblin())
        goblin.hp = 50
        behind = self.putEnemy(self.here + 3, Goblin())
        behind.hp = 50
        keyDown(game, pygame.K_f)
        self.assertEqual(game.throwing, gamemanager.PITCH_BOLT)
        self.assertEqual(game.throwView()["aim"]["effect"], "Pitch")
        self.assertEqual(game.throwView()["aim"]["area"], [self.here + 1], "one space, nothing around it")
        keyDown(game, pygame.K_RIGHT)
        keyDown(game, pygame.K_RIGHT)
        self.assertEqual(game.throwView()["aim"]["area"], [self.here + 2])
        inventoryBefore = list(self.player.inventory)
        keyDown(game, pygame.K_RETURN)
        self.assertIsNone(game.throwing)
        self.assertEqual(goblin.hp, 50 - relics.PITCH_BOLT_DAMAGE)
        self.assertEqual(behind.hp, 50, "no splash")
        self.assertEqual(self.player.inventory, inventoryBefore, "it uses nothing up")

    def test_f_again_fires(self):
        game = self.game
        wearPattern(self.player)
        goblin = self.putEnemy(self.here + 1, Goblin())
        goblin.hp = 50
        keyDown(game, pygame.K_f)
        keyDown(game, pygame.K_f)
        self.assertIsNone(game.throwing)
        self.assertEqual(goblin.hp, 50 - relics.PITCH_BOLT_DAMAGE)

    def test_unsealed_resist_the_bolt(self):
        game = self.game
        wearPattern(self.player)
        unsealed = self.putEnemy(self.here + 1, Unsealed())
        unsealed.hp = 50
        keyDown(game, pygame.K_f)
        keyDown(game, pygame.K_RETURN)
        self.assertEqual(unsealed.hp, 50 - round(relics.PITCH_BOLT_DAMAGE * (1 - enemies.PITCH_RESIST_UNSEALED)))

    def test_it_never_harms_walls(self):
        game = self.game
        wearPattern(self.player)
        stone = wall.StoneWall()
        game.grid[self.here + 2] = [WALL, 1, stone]
        hpBefore = stone.hp
        keyDown(game, pygame.K_f)
        keyDown(game, pygame.K_RIGHT)
        keyDown(game, pygame.K_RIGHT)
        keyDown(game, pygame.K_RETURN)
        self.assertEqual(game.grid[self.here + 2][0], WALL)
        self.assertEqual(stone.hp, hpBefore)

    def test_a_far_bolt_flies_like_a_throw(self):
        game = self.game
        wearPattern(self.player)
        goblin = self.putEnemy(self.here + 5, Goblin())
        goblin.hp = 50
        goblin.speed = 0  # (it stays put while the bolt flies)
        game.startPitchBolt()
        game.currentAimSpot = self.here + 5
        game.refreshThrowAim()
        game.throw()
        self.assertEqual(goblin.hp, 50, "still in the air")
        self.assertEqual(game.throwView()["flying"][0]["effect"], "Pitch")
        for _ in range(3):
            game.enemyTurn()
            if goblin.hp < 50:
                break
        self.assertEqual(goblin.hp, 50 - relics.PITCH_BOLT_DAMAGE)

    def test_esc_puts_it_away(self):
        game = self.game
        wearPattern(self.player)
        keyDown(game, pygame.K_f)
        keyDown(game, pygame.K_ESCAPE)
        self.assertIsNone(game.throwing)
        self.assertFalse(game.enemyMove)

    def test_it_draws(self):
        game = self.game
        wearPattern(self.player)
        self.putEnemy(self.here + 1, Goblin()).hp = 50
        game.messageBools = {name: False for name in game.messageBools}
        keyDown(game, pygame.K_f)
        game.draw()
        keyDown(game, pygame.K_RETURN)
        game.draw()
        self.assertEqual(game.painter.effectColor("Pitch"), game.painter.PITCH_SHEEN)


if __name__ == "__main__":
    unittest.main()
