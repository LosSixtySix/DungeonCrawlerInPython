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
from cruel.graphics import sprites
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

    def test_a_vault_never_holds_it(self):
        game = newGame()
        with mock.patch.object(gamemanager.rand, "choice", side_effect=lambda choices: choices[-1]) as choice:
            grid = {spot: [FLOOR, 0] for spot in range(game.numberOfSpots)}
            game.placeVault(grid, "workbench", set())
        offered = [call.args[0] for call in choice.call_args_list if call.args and "lantern" in call.args[0]]
        self.assertTrue(offered)
        self.assertNotIn("sealed_pattern", offered[0])


class ForgeTests(SealedPatternTest):
    def test_the_gilded_forge_can_rekindle_its_power_away(self):
        game, player = self.game, self.player
        pattern = relics.make("sealed_pattern")
        player.inventory = [pattern]
        rekindles = [recipe for recipe in recipes.relicStationRecipes("forge", player.inventory) if recipe.kind == "rekindle"]
        self.assertEqual([recipe.target for recipe in rekindles], [pattern])
        player.addMaterial("relic_dust", 2)
        player.gold = recipes.REKINDLE_GOLD
        game.finishCraft(rekindles[0])
        self.assertIn(pattern.relicPower, relics.FORGE_POWERS)
        self.assertEqual(pattern.slot, "Gloves")
        wearPattern(player)
        player.equipment["Gloves"] = pattern
        self.assertFalse(player.hasEffect("sealed_pattern"))
        self.assertEqual(player.pitchDamage(), 0)
        self.assertEqual(player.getMaxHealth(), 10 + player.attributeBonuses["constitution"], "its health cost goes with it")
        keyDown(game, pygame.K_f)
        self.assertIsNone(game.throwing, "no more Pitch Bolt")


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
        self.game.addUnsealed = True
        others = [self.here + 3 * self.game.rowLength, self.here - 3 * self.game.rowLength]
        for spot in others:
            self.putEnemy(spot, Unsealed())
        goblinSpot = self.here - 2
        goblin = self.putEnemy(goblinSpot, Goblin())
        self.killUnsealed(KILLS)
        self.assertTrue(self.game.unsealedBanished)
        self.assertEqual(self.unsealedOnFloor(), [])
        self.assertIs(self.game.grid[goblinSpot][2], goblin, "only the Unsealed die")
        self.assertFalse(self.game.addUnsealed)
        self.assertEqual(len(self.patternChests()), 1)

    def test_a_second_unsealed_sharing_a_space_dies_too(self):
        spot = self.here + 3 * self.game.rowLength
        self.putEnemy(spot, Unsealed())
        second = Unsealed()
        occupancy.sharedTiles(self.game)[spot] = second
        self.killUnsealed(KILLS)
        self.assertNotIn(second, occupancy.sharedTiles(self.game).values())
        self.assertEqual(self.unsealedOnFloor(), [])

    def test_the_chest_is_at_the_floors_center(self):
        placePlayer(self.game, self.here + 4)  # (off the center: the test map puts you right on it)
        center = self.game.floorCenter()
        rows = self.game.numberOfSpots // self.game.rowLength
        self.assertEqual((center % self.game.rowLength, center // self.game.rowLength), (self.game.rowLength // 2, rows // 2))
        self.game.grid[center] = [WALL, 0, wall.GoldWall()]
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
        self.game.proportion = "All Gold"
        self.killUnsealed(KILLS)
        self.game.addUnsealed = True  # (as if something set it again)
        self.game.grid[self.here + 3] = [WALL, 1, wall.GoldWall()]
        self.game.enemyTurn()
        self.assertEqual(self.unsealedOnFloor(), [])
        self.game.goldWallCount = 20
        self.game.addUnsealed = False
        self.game.breakWall(self.here + 3)
        self.assertFalse(self.game.addUnsealed)

    def test_the_count_starts_over_on_a_new_floor(self):
        self.killUnsealed(KILLS)
        self.game.goToNewLevel()
        self.assertEqual((self.game.unsealedKills, self.game.unsealedBanished), (0, False))

    def test_the_count_is_saved(self):
        self.killUnsealed(5)
        saveFile = os.path.join(tempfile.mkdtemp(), "sealed-save.pkl")
        gamemanager.gameManager.saveGame(self.game, saveFile)
        loaded = newGame()
        self.assertTrue(loaded.loadGame(saveFile))
        self.assertEqual((loaded.unsealedKills, loaded.unsealedBanished), (5, False))


class WearingTests(SealedPatternTest):
    def test_it_takes_max_health(self):
        before = self.player.getMaxHealth()
        wearPattern(self.player)
        self.assertEqual(self.player.getMaxHealth(), max(1, before - PATTERN_HEALTH))

    def test_max_health_stops_at_1(self):
        wearPattern(self.player)
        self.assertEqual(self.player.getMaxHealth(), 1, "a fresh character has under 16")
        self.player.equipment["Chest"] = items.equipment("Health", "Big Coat", "Chest", 30, "")
        self.assertEqual(self.player.getMaxHealth(), 10 + self.player.attributeBonuses["constitution"] + 30 - PATTERN_HEALTH)

    def test_putting_it_on_hurt_never_kills_you(self):
        self.player.damageTaken = 5
        wearPattern(self.player)
        self.assertEqual(self.player.getCurrentHealth(), 1)

    def test_each_free_hand_gives_speed_and_pitch(self):
        baseSpeed = self.player.getSpeed()
        self.assertEqual(self.player.pitchDamage(), 0)
        wearPattern(self.player)
        self.assertEqual(self.player.freeHands(), 2)
        self.assertAlmostEqual(self.player.getSpeed(), baseSpeed + 2 * relics.SEALED_PATTERN_SPEED)
        self.assertEqual(self.player.pitchDamage(), 2 * relics.SEALED_PATTERN_PITCH)
        self.player.equipment["Right Hand"] = sword()
        self.assertAlmostEqual(self.player.getSpeed(), baseSpeed + relics.SEALED_PATTERN_SPEED)
        self.assertEqual(self.player.pitchDamage(), relics.SEALED_PATTERN_PITCH)
        self.player.equipment["Left Hand"] = sword()
        self.assertAlmostEqual(self.player.getSpeed(), baseSpeed)
        self.assertEqual(self.player.pitchDamage(), 0)

    def test_a_third_hand_counts_when_free(self):
        self.player.equipment["Back"] = relics.make("vestigial_hand")
        wearPattern(self.player)
        self.assertEqual(self.player.freeHands(), 3)
        self.assertEqual(self.player.pitchDamage(), 3 * relics.SEALED_PATTERN_PITCH)


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
        for step in range(1, 7):
            self.game.grid[self.here + step] = [FLOOR, 1]

    def test_f_is_the_pitch_bolt_by_default(self):
        self.assertEqual(settings.DEFAULT_HOTKEYS["pitch_bolt"], pygame.K_f)
        self.assertEqual(settings.ACTION_LABELS["pitch_bolt"], "Pitch Bolt")

    def test_without_the_pattern_f_does_nothing(self):
        keyDown(self.game, pygame.K_f)
        self.assertIsNone(self.game.throwing)
        self.assertFalse(self.game.enemyMove)

    def test_f_aims_and_enter_fires_at_the_first_enemy_in_the_way(self):
        wearPattern(self.player)
        goblin = self.putEnemy(self.here + 2, Goblin())
        goblin.hp = 50
        behind = self.putEnemy(self.here + 3, Goblin())
        behind.hp = 50
        keyDown(self.game, pygame.K_f)
        self.assertEqual(self.game.throwing, gamemanager.PITCH_BOLT)
        self.assertEqual(self.game.throwView()["aim"]["effect"], "Pitch")
        self.assertEqual(self.game.throwView()["aim"]["area"], [self.here + 1], "one space, nothing around it")
        keyDown(self.game, pygame.K_RIGHT)
        keyDown(self.game, pygame.K_RIGHT)
        self.assertEqual(self.game.throwView()["aim"]["area"], [self.here + 2])
        inventoryBefore = list(self.player.inventory)
        keyDown(self.game, pygame.K_RETURN)
        self.assertIsNone(self.game.throwing)
        self.assertEqual(goblin.hp, 50 - relics.PITCH_BOLT_DAMAGE)
        self.assertEqual(behind.hp, 50, "no splash")
        self.assertEqual(self.player.inventory, inventoryBefore, "it uses nothing up")

    def test_f_again_fires(self):
        wearPattern(self.player)
        goblin = self.putEnemy(self.here + 1, Goblin())
        goblin.hp = 50
        keyDown(self.game, pygame.K_f)
        keyDown(self.game, pygame.K_f)
        self.assertIsNone(self.game.throwing)
        self.assertEqual(goblin.hp, 50 - relics.PITCH_BOLT_DAMAGE)

    def test_unsealed_resist_the_bolt(self):
        wearPattern(self.player)
        unsealed = self.putEnemy(self.here + 1, Unsealed())
        unsealed.hp = 50
        keyDown(self.game, pygame.K_f)
        keyDown(self.game, pygame.K_RETURN)
        self.assertEqual(unsealed.hp, 50 - round(relics.PITCH_BOLT_DAMAGE * (1 - enemies.PITCH_RESIST_UNSEALED)))

    def test_it_never_harms_walls(self):
        wearPattern(self.player)
        stone = wall.StoneWall()
        self.game.grid[self.here + 2] = [WALL, 1, stone]
        hpBefore = stone.hp
        keyDown(self.game, pygame.K_f)
        keyDown(self.game, pygame.K_RIGHT)
        keyDown(self.game, pygame.K_RIGHT)
        keyDown(self.game, pygame.K_RETURN)
        self.assertEqual(self.game.grid[self.here + 2][0], WALL)
        self.assertEqual(stone.hp, hpBefore)

    def test_a_far_bolt_flies_like_a_throw(self):
        wearPattern(self.player)
        goblin = self.putEnemy(self.here + 5, Goblin())
        goblin.hp = 50
        goblin.speed = 0  # (it stays put while the bolt flies)
        self.game.startPitchBolt()
        self.game.currentAimSpot = self.here + 5
        self.game.refreshThrowAim()
        self.game.throw()
        self.assertEqual(goblin.hp, 50, "still in the air")
        self.assertEqual(self.game.throwView()["flying"][0]["effect"], "Pitch")
        for _ in range(3):
            self.game.enemyTurn()
            if goblin.hp < 50:
                break
        self.assertEqual(goblin.hp, 50 - relics.PITCH_BOLT_DAMAGE)

    def test_esc_puts_it_away(self):
        wearPattern(self.player)
        keyDown(self.game, pygame.K_f)
        keyDown(self.game, pygame.K_ESCAPE)
        self.assertIsNone(self.game.throwing)
        self.assertFalse(self.game.enemyMove)

    def test_it_draws(self):
        wearPattern(self.player)
        self.putEnemy(self.here + 1, Goblin()).hp = 50
        self.game.messageBools = {name: False for name in self.game.messageBools}
        keyDown(self.game, pygame.K_f)
        self.game.draw()
        keyDown(self.game, pygame.K_RETURN)
        self.game.draw()
        self.assertEqual(self.game.painter.effectColor("Pitch"), self.game.painter.PITCH_SHEEN)


class BoltAnimationTests(SealedPatternTest):
    """The bolt glides along its path (gameManager.startGlide) and its hit plays once it gets there."""

    def setUp(self):
        super().setUp()
        for step in range(1, 7):
            self.game.grid[self.here + step] = [FLOOR, 1]
        wearPattern(self.player)

    def fireAt(self, spot, clock=1000):
        self.game.startPitchBolt()
        self.game.currentAimSpot = spot
        self.game.refreshThrowAim()
        with mock.patch("pygame.time.get_ticks", return_value=clock):
            self.game.throw()

    def test_a_close_bolt_glides_there_and_then_hits(self):
        self.putEnemy(self.here + 3, Goblin()).hp = 50
        self.fireAt(self.here + 3)
        glideMs = 3 * gamemanager.GLIDE_MS_PER_TILE
        self.assertEqual(self.game.glides, [{"from": self.here, "to": self.here + 3, "start": 1000, "ms": glideMs, "shot": None}])
        landing, radius, effect, start = self.game.explosions[-1]
        self.assertEqual((landing, effect, start), (self.here + 3, "Pitch", 1000 + glideMs), "the hit waits for the bolt")
        with mock.patch("pygame.time.get_ticks", return_value=1000 + glideMs // 2):
            view = self.game.throwView()
        [(fromTile, toTile, progress)] = view["glides"]
        self.assertEqual((fromTile, toTile), (self.here, self.here + 3))
        self.assertAlmostEqual(progress, 0.5, places=1)
        self.assertLess(view["explosions"][-1][3], 0, "not hit yet")

    def test_a_far_bolt_glides_out_hangs_then_glides_onto_its_target(self):
        goblin = self.putEnemy(self.here + 6, Goblin())
        goblin.hp, goblin.speed = 50, 0
        self.fireAt(self.here + 6)
        shot = self.game.inFlight[0]
        self.assertIs(self.game.glides[0]["shot"], shot)
        self.assertEqual(self.game.glides[0]["to"], self.game.shotSpot(shot))
        self.assertEqual(self.game.shotSpot(shot), self.here + 4, "halfway along its 6 tiles, for its 1 turn in the air")
        with mock.patch("pygame.time.get_ticks", return_value=5000):
            self.assertFalse(self.game.throwView()["flying"][0]["gliding"], "done gliding: it hangs there")
            self.assertTrue(self.game.animating(), "still spinning")
            for _ in range(3):
                if self.game.inFlight:
                    self.game.enemyTurn()
        self.assertEqual(self.game.glides[-1]["to"], self.here + 6)
        self.assertEqual(goblin.hp, 50 - relics.PITCH_BOLT_DAMAGE)

    def test_it_is_drawn_as_the_bolt_sprite_on_its_way(self):
        self.putEnemy(self.here + 3, Goblin()).hp = 50
        self.game.messageBools = {name: False for name in self.game.messageBools}
        self.fireAt(self.here + 3)
        halfway = 1000 + 3 * gamemanager.GLIDE_MS_PER_TILE // 2
        with mock.patch("pygame.time.get_ticks", return_value=halfway),                 mock.patch.object(self.game.painter, "drawGlidingBolt", wraps=self.game.painter.drawGlidingBolt) as drawGlidingBolt:
            self.game.draw()
        fromTile, toTile, progress, _ = drawGlidingBolt.call_args.args
        self.assertEqual((fromTile, toTile), (self.here, self.here + 3))
        self.assertAlmostEqual(progress, 0.5, places=1)

    def test_the_hit_frames_draw_over_the_target_after_it_arrives(self):
        self.putEnemy(self.here + 2, Goblin()).hp = 50
        self.game.messageBools = {name: False for name in self.game.messageBools}
        self.fireAt(self.here + 2)
        arrives = self.game.explosions[-1][3]
        for clock, expected in ((arrives - 10, []), (arrives + 10, [0]), (arrives + gamemanager.EXPLOSION_MS - 10, [2])):
            with mock.patch("pygame.time.get_ticks", return_value=clock),                     mock.patch.object(sprites, "pitchHitFrame", wraps=sprites.pitchHitFrame) as pitchHitFrame:
                self.game.draw()
            self.assertEqual([frame for frame in (sprites.pitchHitFrame(call.args[0]) for call in pitchHitFrame.call_args_list)],
                             expected, clock)

    def test_bursts_of_other_throws_are_unchanged(self):
        self.game.player.inventory = [recipes.RECIPES_BY_ID["fire_flask"].makeItem(0, 0)]
        self.game.startThrow(0)
        self.game.currentAimSpot = self.here + 2
        self.game.refreshThrowAim()
        with mock.patch("pygame.time.get_ticks", return_value=1000):
            self.game.throw()
        self.assertEqual(self.game.glides, [])
        self.assertEqual(self.game.explosions[-1][2:], ["Fire", 1000])


if __name__ == "__main__":
    unittest.main()
