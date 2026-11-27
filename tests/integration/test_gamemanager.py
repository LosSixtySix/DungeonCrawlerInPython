"""The game manager as a whole: starting a run, walking between floors, moving, digging, looting, fighting,
dying, saving and loading, the pause menu and the title screen.

Integration tests; the rest are in tests/acceptance/test_gamemanager.py."""
import os
import random
import tempfile
import unittest
from unittest import mock
import pygame
from cruel.core import attempts
from cruel.core import gamemanager
from cruel.entities import enemies
from cruel.inventory import items
from cruel.world import wall
from tests.support import newGame, placePlayer, openTile
from tests.helpers.gamemanager import CHEST, DOWN, DOWN_DOOR, ENEMY, FLOOR, LEFT, PILE, RIGHT, WALL, standInOpenFloor


class NewGameTests(unittest.TestCase):
    """What a brand new run looks like."""

    def setUp(self):
        random.seed(1)
        self.game = newGame()

    def test_a_new_run_starts_on_floor_zero_with_one_door_down(self):
        self.assertEqual(self.game.level, 0)
        self.assertEqual(self.game.deepest, 0)
        self.assertEqual(self.game.levelGrids, [])
        self.assertEqual(len(self.game.doorPositions), 1)
        self.assertEqual(self.game.grid[self.game.doorPositions[0]][0], DOWN_DOOR)

    def test_the_player_starts_in_the_middle_of_the_map(self):
        middleX, middleY = self.game.painter.getCenterCartesian()
        self.assertEqual(self.game.playerPositionFlat, middleX + middleY * self.game.rowLength)
        self.assertEqual(self.game.currentLocation[0], FLOOR)

    def test_a_chest_with_the_starting_pick_sits_just_left_of_the_player(self):
        chestTile = self.game.grid[self.game.playerPositionFlat - 1]
        self.assertEqual(chestTile[0], CHEST)
        self.assertIn(items.startingPick, chestTile[2])

    def test_the_grid_covers_the_whole_map(self):
        self.assertEqual(len(self.game.grid), self.game.rowLength * self.game.painter.columnLength)
        self.assertEqual(self.game.numberOfSpots, len(self.game.grid))

    def test_every_enemy_position_holds_an_enemy(self):
        for enemySpot in self.game.EnemyPositions:
            tile = self.game.grid[enemySpot]
            self.assertEqual(tile[0], ENEMY)
            self.assertIsInstance(tile[2], enemies.Enemy)

    def test_the_player_starts_at_full_health_with_no_gold(self):
        self.assertEqual(self.game.player.getCurrentHealth(), self.game.player.getMaxHealth())
        self.assertEqual(self.game.player.gold, 0)

    def test_the_escape_message_shows_when_a_run_starts(self):
        self.assertTrue(self.game.messageBools["escapeMessage"])


class DiggingAndLootTests(unittest.TestCase):
    """Breaking walls and taking what's in chests and item piles."""

    def setUp(self):
        random.seed(4)
        self.game = newGame()
        self.playerSpot = standInOpenFloor(self.game, facing=RIGHT)
        self.wallSpot = self.playerSpot + 1

    def test_hitting_a_wall_damages_it(self):
        stoneWall = wall.StoneWall()
        self.game.grid[self.wallSpot] = [WALL, 1, stoneWall]
        hpBefore = stoneWall.hp
        self.game.onInteract()
        self.assertLess(stoneWall.hp, hpBefore)
        self.assertEqual(self.game.grid[self.wallSpot][0], WALL)
        self.assertTrue(self.game.enemyMove)

    def test_hitting_a_wall_enough_breaks_it_into_floor_and_pays_out(self):
        self.game.grid[self.wallSpot] = [WALL, 1, wall.GoldWall()]
        goldBefore = self.game.player.gold
        for _ in range(200):
            if self.game.grid[self.wallSpot][0] != WALL:
                break
            self.game.onInteract()
        self.assertEqual(self.game.grid[self.wallSpot], [FLOOR, 1])
        materialsGained = sum(self.game.player.materials.values())
        self.assertTrue(self.game.player.gold > goldBefore or materialsGained > 0)

    def test_a_broken_wall_can_be_walked_into(self):
        self.game.grid[self.wallSpot] = [WALL, 1, wall.SandWall()]
        self.game.breakWall(self.wallSpot)
        self.game.movePlayer(self.wallSpot)
        self.assertEqual(self.game.playerPositionFlat, self.wallSpot)

    def test_interacting_with_a_chest_opens_items_here_and_enter_takes_the_item(self):
        self.game.grid[self.wallSpot] = [CHEST, 1, [items.startingPick]]
        self.game.roomItems = self.game.getItemsFromGrid()  # the game loop refreshes this every frame
        self.game.onInteract()
        self.assertIn("items", self.game.openWindows)
        self.assertEqual(self.game.focus, "items")
        self.game.onWindowEnter("items")
        self.assertEqual([item.name for item in self.game.player.inventory], [items.startingPick.name])
        self.assertEqual(self.game.grid[self.wallSpot][0], FLOOR)  # the emptied chest is gone
        self.assertNotIn("items", self.game.openWindows)

    def test_taking_the_starting_pick_from_the_first_chest(self):
        game = newGame()
        game.player.playerDirection = LEFT  # the starting chest is on the left
        game.setLookPosition()
        game.roomItems = game.getItemsFromGrid()
        self.assertEqual(game.roomItems, [items.startingPick])
        game.onInteract()
        game.onWindowEnter("items")
        self.assertEqual(len(game.player.inventory), 1)

    def test_an_item_pile_you_stand_on_can_be_picked_up(self):
        self.game.grid[self.wallSpot] = [PILE, 1, items.ItemPile([items.startingPick])]
        self.game.movePlayer(self.wallSpot)
        self.game.player.playerDirection = DOWN  # looking away: the pile underfoot is still used
        self.game.setLookPosition()
        self.assertEqual(self.game.itemsSpot(), self.wallSpot)
        self.game.roomItems = self.game.getItemsFromGrid()
        self.game.openWindow("items")
        self.game.onWindowEnter("items")
        self.assertEqual(len(self.game.player.inventory), 1)
        self.assertEqual(self.game.currentLocation[0], FLOOR)

    def test_a_pile_of_only_gold_goes_straight_into_your_purse(self):
        self.game.grid[self.wallSpot] = [PILE, 1, items.ItemPile([], gold=7)]
        self.game.roomItems = self.game.getItemsFromGrid()
        self.game.onInteract()
        self.assertEqual(self.game.player.gold, 7)
        self.assertNotIn("items", self.game.openWindows)


class CombatTests(unittest.TestCase):
    """You hitting enemies, and enemies hitting you on their turn."""

    def setUp(self):
        random.seed(5)
        self.game = newGame()
        self.playerSpot = standInOpenFloor(self.game, facing=RIGHT)
        self.enemySpot = self.playerSpot + 1

    def putGoblin(self, spot):
        goblin = enemies.Goblin()
        self.game.grid[spot] = [ENEMY, 1, goblin]
        self.game.EnemyPositions.add(spot)
        return goblin

    def test_attacking_an_enemy_takes_away_its_health(self):
        goblin = self.putGoblin(self.enemySpot)
        hpBefore = goblin.hp
        with mock.patch.object(self.game.player, "DealDamage", return_value=2):
            self.game.onInteract()
        self.assertEqual(goblin.hp, hpBefore - 2)
        self.assertEqual(self.game.grid[self.enemySpot][0], ENEMY)
        self.assertTrue(self.game.enemyMove)

    def test_killing_an_enemy_clears_its_tile_and_pays_its_gold(self):
        goblin = self.putGoblin(self.enemySpot)
        with mock.patch.object(self.game.player, "DealDamage", return_value=goblin.hp):
            self.game.onInteract()
        self.assertNotIn(self.enemySpot, self.game.EnemyPositions)
        self.assertNotEqual(self.game.grid[self.enemySpot][0], ENEMY)
        self.assertGreaterEqual(self.game.player.gold, goblin.gold)

    def test_an_enemy_beside_you_hits_you_on_its_turn(self):
        goblin = self.putGoblin(self.enemySpot)
        healthBefore = self.game.player.getCurrentHealth()
        with mock.patch.object(self.game, "dodge", return_value=None):  # no lucky dodges
            self.game.MoveEnemies()
        self.assertEqual(self.game.player.getCurrentHealth(), healthBefore - goblin.damage)
        self.assertEqual(self.game.grid[self.enemySpot][2], goblin)  # it stays put to swing
        self.assertEqual(goblin.facing, LEFT)  # turned toward you

    def test_a_whole_enemy_turn_also_hurts_you(self):
        self.putGoblin(self.enemySpot)
        healthBefore = self.game.player.getCurrentHealth()
        with mock.patch.object(self.game, "dodge", return_value=None):
            self.game.enemyTurn()
        self.assertLess(self.game.player.getCurrentHealth(), healthBefore)
        self.assertEqual(self.game.turnCount, 1)

    def test_a_clean_dodge_takes_no_damage(self):
        self.putGoblin(self.enemySpot)
        healthBefore = self.game.player.getCurrentHealth()
        with mock.patch.object(self.game, "dodge", return_value="clean"):
            self.game.MoveEnemies()
        self.assertEqual(self.game.player.getCurrentHealth(), healthBefore)

    def test_peaceful_mode_stops_enemies_attacking(self):
        self.putGoblin(self.enemySpot)
        self.game.peaceful = True
        healthBefore = self.game.player.getCurrentHealth()
        self.game.MoveEnemies()
        self.assertEqual(self.game.player.getCurrentHealth(), healthBefore)

    def test_an_enemy_two_tiles_away_walks_toward_you(self):
        farSpot = self.playerSpot + 2
        goblin = self.putGoblin(farSpot)
        self.game.MoveEnemies()
        self.assertEqual(self.game.grid[self.enemySpot][0], ENEMY)
        self.assertIs(self.game.grid[self.enemySpot][2], goblin)
        self.assertEqual(self.game.grid[farSpot][0], FLOOR)
        self.assertEqual(self.game.EnemyPositions, {self.enemySpot})


class DeathTests(unittest.TestCase):
    """Running out of health ends the run: it's recorded and the save is deleted."""

    def setUp(self):
        random.seed(6)
        self.game = newGame()

    def test_end_attempt_records_the_run_and_goes_to_the_title(self):
        self.game.goToNewLevel()
        self.game.player.gold = 12
        attemptsBefore = len(attempts.load())
        self.game.endAttempt()
        recorded = attempts.load()
        self.assertEqual(len(recorded), attemptsBefore + 1)
        self.assertEqual(recorded[-1]["deepest"], 1)
        self.assertEqual(recorded[-1]["gold"], 12)
        self.assertEqual(self.game.scene, "title")

    def test_end_attempt_deletes_the_save(self):
        self.game.saveGame()
        self.assertTrue(os.path.exists(gamemanager.SAVE_FILE))
        self.game.endAttempt()
        self.assertFalse(os.path.exists(gamemanager.SAVE_FILE))

    def test_the_game_loop_ends_the_run_when_health_reaches_zero(self):
        self.game.player.damageTaken = self.game.player.getMaxHealth()
        realEndAttempt = self.game.endAttempt

        def endThenStop():
            realEndAttempt()
            self.game.running = False  # leave RunGame after one frame
        with mock.patch.object(self.game, "endAttempt", side_effect=endThenStop) as endAttempt, \
                mock.patch.object(pygame, "quit"):  # keep pygame up for the other tests
            self.game.RunGame()
        endAttempt.assert_called_once()
        self.assertEqual(self.game.scene, "title")


class SaveAndLoadTests(unittest.TestCase):
    """A saved run comes back exactly as it was."""

    def setUp(self):
        random.seed(7)
        self.game = newGame()
        self.saveFolder = tempfile.mkdtemp(prefix="cruel-save-test-")
        self.saveFile = os.path.join(self.saveFolder, "test_save.pkl")

    def test_a_save_loads_back_into_a_fresh_game(self):
        self.game.goToNewLevel()
        self.game.player.gold = 42
        self.game.player.damageTaken = 3
        playerSpot = self.game.playerPositionFlat
        doorPositions = list(self.game.doorPositions)
        wallSpots = {spot for spot, tile in self.game.grid.items() if tile[0] == WALL}
        self.game.saveGame(self.saveFile)

        loaded = newGame()
        self.assertTrue(loaded.loadGame(self.saveFile))
        self.assertEqual(loaded.level, 1)
        self.assertEqual(loaded.deepest, 1)
        self.assertEqual(loaded.playerPositionFlat, playerSpot)
        self.assertEqual(loaded.doorPositions, doorPositions)
        self.assertEqual(loaded.player.gold, 42)
        self.assertEqual(loaded.player.damageTaken, 3)
        self.assertEqual(len(loaded.levelGrids), 2)
        self.assertEqual({spot for spot, tile in loaded.grid.items() if tile[0] == WALL}, wallSpots)
        self.assertEqual(loaded.theme.name, self.game.theme.name)

    def test_a_loaded_game_can_go_back_up_to_the_floor_above(self):
        firstFloorWalls = {spot for spot, tile in self.game.grid.items() if tile[0] == WALL}
        self.game.goToNewLevel()
        self.game.saveGame(self.saveFile)
        loaded = newGame()
        loaded.loadGame(self.saveFile)
        loaded.changeLevel(0)
        self.assertEqual({spot for spot, tile in loaded.grid.items() if tile[0] == WALL}, firstFloorWalls)

    def test_continuing_a_save_restarts_the_session(self):
        self.game.saveGame()  # the default save file, inside the tests' temporary save folder
        loaded = newGame()
        loaded.scene = "title"
        self.assertTrue(loaded.continueGame())
        self.assertEqual(loaded.scene, "playing")
        self.assertTrue(loaded.messageBools["floorLevelMessage"])
        os.remove(gamemanager.SAVE_FILE)

    def test_a_missing_save_does_not_load(self):
        self.assertFalse(self.game.loadGame(os.path.join(self.saveFolder, "missing.pkl")))

    def test_a_corrupt_save_does_not_load(self):
        with open(self.saveFile, "wb") as saveFile:
            saveFile.write(b"this is not a pickle")
        self.assertFalse(self.game.loadGame(self.saveFile))

    def test_a_save_from_another_map_size_does_not_load(self):
        self.game.saveGame(self.saveFile)
        self.game.rowLength += 1  # as if the screen resolution had changed
        self.assertFalse(self.game.loadGame(self.saveFile))


if __name__ == "__main__":
    unittest.main()
