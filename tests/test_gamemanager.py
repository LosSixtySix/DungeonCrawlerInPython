"""The game manager as a whole: starting a run, walking between floors, moving, digging, looting, fighting,
dying, saving and loading, the pause menu and the title screen."""
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

FLOOR, PLAYER, WALL, CHEST, DOWN_DOOR, ENEMY, UP_DOOR, PILE = 0, 1, 2, 3, 4, 5, 6, 9
LEFT, RIGHT, UP, DOWN = 0, 1, 2, 3


def keyDown(game, key, mod=0):
    """Presses and releases a key the way pygame would deliver it."""
    game.onKeyDown(pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod))
    game.onKeyUp(pygame.event.Event(pygame.KEYUP, key=key, mod=mod))


def middleSpot(game):
    """A tile well away from the map's edges."""
    rowLength = game.rowLength
    return (game.painter.columnLength // 2) * rowLength + rowLength // 2


def clearAround(game, spot):
    """Turns the 5x5 block around spot into plain, visible floor, so nothing nearby gets in the way."""
    rowLength = game.rowLength
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            tile = spot + dx + dy * rowLength
            game.grid[tile] = [FLOOR, 1]
            game.EnemyPositions.discard(tile)


def standInOpenFloor(game, facing=LEFT):
    """Puts the player in the middle of a cleared patch of floor, facing one way, with no enemies on the floor."""
    playerSpot = middleSpot(game)
    for enemySpot in list(game.EnemyPositions):
        game.grid[enemySpot] = [FLOOR, game.grid[enemySpot][1]]
    game.EnemyPositions = set()
    placePlayer(game, playerSpot)
    clearAround(game, playerSpot)
    game.grid[playerSpot] = [PLAYER, 1]
    game.currentLocation = [FLOOR, 1]
    game.player.playerDirection = facing
    game.setLookPosition()
    return playerSpot


class NewGameTests(unittest.TestCase):
    """What a brand new run looks like."""

    def setUp(self):
        random.seed(1)
        self.game = newGame()

    def test_a_new_run_starts_on_floor_zero_with_one_door_down(self):
        game = self.game
        self.assertEqual(game.level, 0)
        self.assertEqual(game.deepest, 0)
        self.assertEqual(game.levelGrids, [])
        self.assertEqual(len(game.doorPositions), 1)
        self.assertEqual(game.grid[game.doorPositions[0]][0], DOWN_DOOR)

    def test_the_player_starts_in_the_middle_of_the_map(self):
        game = self.game
        middleX, middleY = game.painter.getCenterCartesian()
        self.assertEqual(game.playerPositionFlat, middleX + middleY * game.rowLength)
        self.assertEqual(game.currentLocation[0], FLOOR)

    def test_a_chest_with_the_starting_pick_sits_just_left_of_the_player(self):
        game = self.game
        chestTile = game.grid[game.playerPositionFlat - 1]
        self.assertEqual(chestTile[0], CHEST)
        self.assertIn(items.startingPick, chestTile[2])

    def test_the_grid_covers_the_whole_map(self):
        game = self.game
        self.assertEqual(len(game.grid), game.rowLength * game.painter.columnLength)
        self.assertEqual(game.numberOfSpots, len(game.grid))

    def test_every_enemy_position_holds_an_enemy(self):
        for enemySpot in self.game.EnemyPositions:
            tile = self.game.grid[enemySpot]
            self.assertEqual(tile[0], ENEMY)
            self.assertIsInstance(tile[2], enemies.Enemy)

    def test_the_player_starts_at_full_health_with_no_gold(self):
        player = self.game.player
        self.assertEqual(player.getCurrentHealth(), player.getMaxHealth())
        self.assertEqual(player.gold, 0)

    def test_the_escape_message_shows_when_a_run_starts(self):
        self.assertTrue(self.game.messageBools["escapeMessage"])


class FloorChangeTests(unittest.TestCase):
    """Going down to new floors, and back up and down the stairs between floors already visited."""

    def setUp(self):
        random.seed(2)
        self.game = newGame()

    def test_going_to_a_new_floor_saves_the_old_one_and_adds_a_door_up(self):
        game = self.game
        firstFloorGrid = game.grid
        game.goToNewLevel()
        self.assertEqual(game.level, 1)
        self.assertEqual(game.deepest, 1)
        self.assertEqual(len(game.levelGrids), 1)
        self.assertIs(game.levelGrids[0][0], firstFloorGrid)
        self.assertEqual(len(game.doorPositions), 2)
        upDoor = game.doorPositions[0]
        self.assertEqual(game.grid[upDoor][0], UP_DOOR)
        self.assertNotIn(upDoor, game.EnemyPositions)
        self.assertEqual(game.grid[game.doorPositions[1]][0], DOWN_DOOR)
        self.assertTrue(game.messageBools["floorLevelMessage"])

    def test_the_old_floor_is_saved_without_the_player_on_it(self):
        game = self.game
        playerSpot = game.playerPositionFlat
        game.grid[playerSpot] = [PLAYER, 1]  # what the game loop does every frame
        game.goToNewLevel()
        self.assertNotEqual(game.levelGrids[0][0][playerSpot][0], PLAYER)

    def test_change_level_goes_back_up_to_the_saved_floor_and_down_again(self):
        game = self.game
        firstFloorGrid = game.grid
        game.goToNewLevel()
        secondFloorGrid = game.grid
        game.changeLevel(0)
        self.assertEqual(game.level, 0)
        self.assertIs(game.grid, firstFloorGrid)
        self.assertEqual(game.deepest, 1)
        game.changeLevel(1)
        self.assertEqual(game.level, 1)
        self.assertIs(game.grid, secondFloorGrid)

    def test_walking_onto_the_door_down_and_pressing_enter_makes_a_new_floor(self):
        game = self.game
        downDoor = game.doorPositions[0]
        placePlayer(game, downDoor)
        keyDown(game, pygame.K_RETURN)
        self.assertEqual(game.level, 1)
        self.assertEqual(len(game.doorPositions), 2)

    def test_the_door_up_takes_you_back_and_the_door_down_returns_you(self):
        game = self.game
        placePlayer(game, game.doorPositions[0])
        game.onOpenDoor()
        self.assertEqual(game.level, 1)
        upDoor = game.doorPositions[0]
        self.assertEqual(game.playerPositionFlat, upDoor)
        game.onOpenDoor()  # standing on the door up
        self.assertEqual(game.level, 0)
        game.onOpenDoor()  # back on the door down of floor 0: the floor below already exists
        self.assertEqual(game.level, 1)
        self.assertEqual(len(game.levelGrids), 2)
        self.assertEqual(len(game.doorPositions), 2)

    def test_the_first_floor_has_no_door_up(self):
        game = self.game
        game.onOpenDoor()  # not on any door
        self.assertEqual(game.level, 0)

    def test_several_floors_down_the_doors_keep_lining_up(self):
        game = newGame(level=3)
        self.assertEqual(game.level, 3)
        self.assertEqual(game.deepest, 3)
        self.assertEqual(len(game.levelGrids), 3)
        self.assertEqual(len(game.doorPositions), 4)
        for floor in range(1, 4):
            game.changeLevel(floor)
            self.assertEqual(game.grid[game.doorPositions[floor - 1]][0], UP_DOOR)

    def test_update_doors_names_the_tile_you_stand_on(self):
        game = self.game
        placePlayer(game, game.doorPositions[0])
        game.updateDoors()
        self.assertEqual(game.currentPosition, "Door to Next Level")


class MovementTests(unittest.TestCase):
    """Walking around with movePlayer and with the movement hotkeys."""

    def setUp(self):
        random.seed(3)
        self.game = newGame()
        self.playerSpot = standInOpenFloor(self.game)

    def test_walking_onto_floor_moves_you_and_ends_your_action(self):
        game = self.game
        rightSpot = self.playerSpot + 1
        game.movePlayer(rightSpot)
        self.assertEqual(game.playerPositionFlat, rightSpot)
        self.assertTrue(game.enemyMove)
        self.assertEqual(game.grid[self.playerSpot][0], FLOOR)  # what was under you is put back

    def test_walking_into_a_wall_does_not_move_you(self):
        game = self.game
        game.grid[self.playerSpot + 1] = [WALL, 1, wall.StoneWall()]
        game.movePlayer(self.playerSpot + 1)
        self.assertEqual(game.playerPositionFlat, self.playerSpot)
        self.assertFalse(game.enemyMove)

    def test_walking_into_an_enemy_does_not_move_you(self):
        game = self.game
        game.grid[self.playerSpot + 1] = [ENEMY, 1, enemies.Goblin()]
        game.movePlayer(self.playerSpot + 1)
        self.assertEqual(game.playerPositionFlat, self.playerSpot)

    def test_walking_into_a_chest_does_not_move_you(self):
        game = self.game
        game.grid[self.playerSpot + 1] = [CHEST, 1, [items.startingPick]]
        game.movePlayer(self.playerSpot + 1)
        self.assertEqual(game.playerPositionFlat, self.playerSpot)

    def test_walking_over_an_item_pile_is_allowed(self):
        game = self.game
        game.grid[self.playerSpot + 1] = [PILE, 1, items.ItemPile([items.startingPick])]
        game.movePlayer(self.playerSpot + 1)
        self.assertEqual(game.playerPositionFlat, self.playerSpot + 1)
        self.assertEqual(game.currentLocation[0], PILE)

    def test_each_movement_hotkey_moves_and_turns_you_that_way(self):
        game = self.game
        rowLength = game.rowLength
        hotkeys = game.settings.hotkeys
        steps = [("move_right", 1, RIGHT), ("move_down", rowLength, DOWN),
                 ("move_left", -1, LEFT), ("move_up", -rowLength, UP)]
        for action, step, facing in steps:
            game.enemyMove = False  # the game loop does this once the world has taken its turn
            before = game.playerPositionFlat
            keyDown(game, hotkeys[action])
            self.assertEqual(game.playerPositionFlat, before + step, action)
            self.assertEqual(game.player.playerDirection, facing, action)

    def test_you_cannot_move_again_until_the_world_has_taken_its_turn(self):
        game = self.game
        keyDown(game, pygame.K_RIGHT)
        keyDown(game, pygame.K_RIGHT)
        self.assertEqual(game.playerPositionFlat, self.playerSpot + 1)

    def test_the_arrow_keys_move_you_too(self):
        game = self.game
        keyDown(game, pygame.K_RIGHT)
        self.assertEqual(game.playerPositionFlat, self.playerSpot + 1)

    def test_you_cannot_walk_off_the_right_edge_onto_the_next_row(self):
        game = self.game
        rowLength = game.rowLength
        edgeSpot = (game.painter.columnLength // 2) * rowLength + rowLength - 1
        placePlayer(game, edgeSpot)
        game.grid[edgeSpot + 1] = [FLOOR, 1]
        keyDown(game, game.settings.hotkeys["move_right"])
        self.assertEqual(game.playerPositionFlat, edgeSpot)
        self.assertEqual(game.player.playerDirection, RIGHT)

    def test_facing_the_map_edge_looks_at_nothing(self):
        game = self.game
        rowLength = game.rowLength
        placePlayer(game, (game.painter.columnLength // 2) * rowLength)  # the left edge
        game.player.playerDirection = LEFT
        self.assertEqual(game.setLookPosition(), -1)

    def test_holding_rotate_turns_you_without_moving(self):
        game = self.game
        game.rotate = True
        keyDown(game, pygame.K_DOWN)
        self.assertEqual(game.playerPositionFlat, self.playerSpot)
        self.assertEqual(game.player.playerDirection, DOWN)


class DiggingAndLootTests(unittest.TestCase):
    """Breaking walls and taking what's in chests and item piles."""

    def setUp(self):
        random.seed(4)
        self.game = newGame()
        self.playerSpot = standInOpenFloor(self.game, facing=RIGHT)
        self.wallSpot = self.playerSpot + 1

    def test_hitting_a_wall_damages_it(self):
        game = self.game
        stoneWall = wall.StoneWall()
        game.grid[self.wallSpot] = [WALL, 1, stoneWall]
        hpBefore = stoneWall.hp
        game.onInteract()
        self.assertLess(stoneWall.hp, hpBefore)
        self.assertEqual(game.grid[self.wallSpot][0], WALL)
        self.assertTrue(game.enemyMove)

    def test_hitting_a_wall_enough_breaks_it_into_floor_and_pays_out(self):
        game = self.game
        game.grid[self.wallSpot] = [WALL, 1, wall.GoldWall()]
        goldBefore = game.player.gold
        for _ in range(200):
            if game.grid[self.wallSpot][0] != WALL:
                break
            game.onInteract()
        self.assertEqual(game.grid[self.wallSpot], [FLOOR, 1])
        materialsGained = sum(game.player.materials.values())
        self.assertTrue(game.player.gold > goldBefore or materialsGained > 0)

    def test_a_broken_wall_can_be_walked_into(self):
        game = self.game
        game.grid[self.wallSpot] = [WALL, 1, wall.SandWall()]
        game.breakWall(self.wallSpot)
        game.movePlayer(self.wallSpot)
        self.assertEqual(game.playerPositionFlat, self.wallSpot)

    def test_interacting_with_a_chest_opens_items_here_and_enter_takes_the_item(self):
        game = self.game
        game.grid[self.wallSpot] = [CHEST, 1, [items.startingPick]]
        game.roomItems = game.getItemsFromGrid()  # the game loop refreshes this every frame
        game.onInteract()
        self.assertIn("items", game.openWindows)
        self.assertEqual(game.focus, "items")
        game.onWindowEnter("items")
        self.assertEqual([item.name for item in game.player.inventory], [items.startingPick.name])
        self.assertEqual(game.grid[self.wallSpot][0], FLOOR)  # the emptied chest is gone
        self.assertNotIn("items", game.openWindows)

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
        game = self.game
        pileSpot = self.wallSpot
        game.grid[pileSpot] = [PILE, 1, items.ItemPile([items.startingPick])]
        game.movePlayer(pileSpot)
        game.player.playerDirection = DOWN  # looking away: the pile underfoot is still used
        game.setLookPosition()
        self.assertEqual(game.itemsSpot(), pileSpot)
        game.roomItems = game.getItemsFromGrid()
        game.openWindow("items")
        game.onWindowEnter("items")
        self.assertEqual(len(game.player.inventory), 1)
        self.assertEqual(game.currentLocation[0], FLOOR)

    def test_a_pile_of_only_gold_goes_straight_into_your_purse(self):
        game = self.game
        game.grid[self.wallSpot] = [PILE, 1, items.ItemPile([], gold=7)]
        game.roomItems = game.getItemsFromGrid()
        game.onInteract()
        self.assertEqual(game.player.gold, 7)
        self.assertNotIn("items", game.openWindows)


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
        game = self.game
        goblin = self.putGoblin(self.enemySpot)
        hpBefore = goblin.hp
        with mock.patch.object(game.player, "DealDamage", return_value=2):
            game.onInteract()
        self.assertEqual(goblin.hp, hpBefore - 2)
        self.assertEqual(game.grid[self.enemySpot][0], ENEMY)
        self.assertTrue(game.enemyMove)

    def test_killing_an_enemy_clears_its_tile_and_pays_its_gold(self):
        game = self.game
        goblin = self.putGoblin(self.enemySpot)
        with mock.patch.object(game.player, "DealDamage", return_value=goblin.hp):
            game.onInteract()
        self.assertNotIn(self.enemySpot, game.EnemyPositions)
        self.assertNotEqual(game.grid[self.enemySpot][0], ENEMY)
        self.assertGreaterEqual(game.player.gold, goblin.gold)

    def test_an_enemy_beside_you_hits_you_on_its_turn(self):
        game = self.game
        goblin = self.putGoblin(self.enemySpot)
        healthBefore = game.player.getCurrentHealth()
        with mock.patch.object(game, "dodge", return_value=None):  # no lucky dodges
            game.MoveEnemies()
        self.assertEqual(game.player.getCurrentHealth(), healthBefore - goblin.damage)
        self.assertEqual(game.grid[self.enemySpot][2], goblin)  # it stays put to swing
        self.assertEqual(goblin.facing, LEFT)  # turned toward you

    def test_a_whole_enemy_turn_also_hurts_you(self):
        game = self.game
        self.putGoblin(self.enemySpot)
        healthBefore = game.player.getCurrentHealth()
        with mock.patch.object(game, "dodge", return_value=None):
            game.enemyTurn()
        self.assertLess(game.player.getCurrentHealth(), healthBefore)
        self.assertEqual(game.turnCount, 1)

    def test_a_clean_dodge_takes_no_damage(self):
        game = self.game
        self.putGoblin(self.enemySpot)
        healthBefore = game.player.getCurrentHealth()
        with mock.patch.object(game, "dodge", return_value="clean"):
            game.MoveEnemies()
        self.assertEqual(game.player.getCurrentHealth(), healthBefore)

    def test_peaceful_mode_stops_enemies_attacking(self):
        game = self.game
        self.putGoblin(self.enemySpot)
        game.peaceful = True
        healthBefore = game.player.getCurrentHealth()
        game.MoveEnemies()
        self.assertEqual(game.player.getCurrentHealth(), healthBefore)

    def test_an_enemy_two_tiles_away_walks_toward_you(self):
        game = self.game
        farSpot = self.playerSpot + 2
        goblin = self.putGoblin(farSpot)
        game.MoveEnemies()
        self.assertEqual(game.grid[self.enemySpot][0], ENEMY)
        self.assertIs(game.grid[self.enemySpot][2], goblin)
        self.assertEqual(game.grid[farSpot][0], FLOOR)
        self.assertEqual(game.EnemyPositions, {self.enemySpot})


class DeathTests(unittest.TestCase):
    """Running out of health ends the run: it's recorded and the save is deleted."""

    def setUp(self):
        random.seed(6)
        self.game = newGame()

    def test_end_attempt_records_the_run_and_goes_to_the_title(self):
        game = self.game
        game.goToNewLevel()
        game.player.gold = 12
        attemptsBefore = len(attempts.load())
        game.endAttempt()
        recorded = attempts.load()
        self.assertEqual(len(recorded), attemptsBefore + 1)
        self.assertEqual(recorded[-1]["deepest"], 1)
        self.assertEqual(recorded[-1]["gold"], 12)
        self.assertEqual(game.scene, "title")

    def test_end_attempt_deletes_the_save(self):
        game = self.game
        game.saveGame()
        self.assertTrue(os.path.exists(gamemanager.SAVE_FILE))
        game.endAttempt()
        self.assertFalse(os.path.exists(gamemanager.SAVE_FILE))

    def test_the_game_loop_ends_the_run_when_health_reaches_zero(self):
        game = self.game
        game.player.damageTaken = game.player.getMaxHealth()
        realEndAttempt = game.endAttempt

        def endThenStop():
            realEndAttempt()
            game.running = False  # leave RunGame after one frame
        with mock.patch.object(game, "endAttempt", side_effect=endThenStop) as endAttempt, \
                mock.patch.object(pygame, "quit"):  # keep pygame up for the other tests
            game.RunGame()
        endAttempt.assert_called_once()
        self.assertEqual(game.scene, "title")


class SaveAndLoadTests(unittest.TestCase):
    """A saved run comes back exactly as it was."""

    def setUp(self):
        random.seed(7)
        self.game = newGame()
        self.saveFolder = tempfile.mkdtemp(prefix="cruel-save-test-")
        self.saveFile = os.path.join(self.saveFolder, "test_save.pkl")

    def test_a_save_loads_back_into_a_fresh_game(self):
        game = self.game
        game.goToNewLevel()
        game.player.gold = 42
        game.player.damageTaken = 3
        playerSpot = game.playerPositionFlat
        doorPositions = list(game.doorPositions)
        wallSpots = {spot for spot, tile in game.grid.items() if tile[0] == WALL}
        game.saveGame(self.saveFile)

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
        self.assertEqual(loaded.theme.name, game.theme.name)

    def test_a_loaded_game_can_go_back_up_to_the_floor_above(self):
        game = self.game
        firstFloorWalls = {spot for spot, tile in game.grid.items() if tile[0] == WALL}
        game.goToNewLevel()
        game.saveGame(self.saveFile)
        loaded = newGame()
        loaded.loadGame(self.saveFile)
        loaded.changeLevel(0)
        self.assertEqual({spot for spot, tile in loaded.grid.items() if tile[0] == WALL}, firstFloorWalls)

    def test_continuing_a_save_restarts_the_session(self):
        game = self.game
        game.saveGame()  # the default save file, inside the tests' temporary save folder
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
        game = self.game
        game.saveGame(self.saveFile)
        game.rowLength += 1  # as if the screen resolution had changed
        self.assertFalse(game.loadGame(self.saveFile))


class PauseMenuTests(unittest.TestCase):
    """The Field Journal pause menu and its Hotkeys page."""

    def setUp(self):
        random.seed(8)
        self.game = newGame()
        self.menuOptionsBefore = dict(self.game.menuOptions)

    def tearDown(self):
        # Hotkeys and menu options are saved to disk: put them back for the other tests
        self.game.settings.resetHotkeys()
        self.game.menuOptions = self.menuOptionsBefore
        self.game.saveMenuOptions(gamemanager.MENU_OPTIONS_FILE)

    def selectRow(self, label):
        rowIndex = [rowLabel for _, rowLabel in gamemanager.PAUSE_ROWS].index(label)
        for _ in range(rowIndex):
            keyDown(self.game, pygame.K_DOWN)
        self.assertEqual(self.game.pauseSel, rowIndex)

    def test_escape_opens_and_closes_the_pause_menu(self):
        game = self.game
        keyDown(game, pygame.K_ESCAPE)
        self.assertEqual(game.pausePage, "journal")
        keyDown(game, pygame.K_ESCAPE)
        self.assertIsNone(game.pausePage)

    def test_escape_closes_a_focused_window_before_pausing(self):
        game = self.game
        game.openWindow("character")
        keyDown(game, pygame.K_ESCAPE)
        self.assertNotIn("character", game.openWindows)
        self.assertIsNone(game.pausePage)

    def test_movement_keys_do_not_move_you_while_paused(self):
        game = self.game
        playerSpot = game.playerPositionFlat
        keyDown(game, pygame.K_ESCAPE)
        keyDown(game, pygame.K_RIGHT)
        self.assertEqual(game.playerPositionFlat, playerSpot)

    def test_up_and_down_choose_a_row_and_stop_at_the_ends(self):
        game = self.game
        keyDown(game, pygame.K_ESCAPE)
        keyDown(game, pygame.K_UP)
        self.assertEqual(game.pauseSel, 0)
        for _ in range(len(gamemanager.PAUSE_ROWS) + 3):
            keyDown(game, pygame.K_DOWN)
        self.assertEqual(game.pauseSel, len(gamemanager.PAUSE_ROWS) - 1)

    def test_enter_flips_a_toggle(self):
        game = self.game
        keyDown(game, pygame.K_ESCAPE)
        self.selectRow("Mini HUD")
        hudBefore = game.menuOptions["Mini HUD"]
        keyDown(game, pygame.K_RETURN)
        self.assertEqual(game.menuOptions["Mini HUD"], not hudBefore)

    def test_light_style_cycles_through_the_styles(self):
        game = self.game
        styleBefore = game.settings.lightStyle
        keyDown(game, pygame.K_ESCAPE)
        self.selectRow("Light Style")
        for _ in range(len(gamemanager.LIGHT_STYLES)):
            keyDown(game, pygame.K_RETURN)
            self.assertIn(game.settings.lightStyle, gamemanager.LIGHT_STYLES)
        self.assertEqual(game.settings.lightStyle, styleBefore)  # all the way round

    def test_the_hotkeys_page_rebinds_an_action(self):
        game = self.game
        keyDown(game, pygame.K_ESCAPE)
        self.selectRow("Hotkeys")
        keyDown(game, pygame.K_RETURN)
        self.assertEqual(game.pausePage, "hotkeys")
        keyDown(game, pygame.K_RETURN)  # the first action on the page
        firstAction = gamemanager.HOTKEY_ACTIONS[0][0]
        self.assertEqual(game.rebinding, firstAction)
        keyDown(game, pygame.K_F7)
        self.assertIsNone(game.rebinding)
        self.assertEqual(game.settings.hotkeys[firstAction], pygame.K_F7)
        keyDown(game, pygame.K_ESCAPE)
        self.assertEqual(game.pausePage, "journal")

    def test_escape_cancels_a_rebind(self):
        game = self.game
        game.pausePage = "hotkeys"
        keyDown(game, pygame.K_RETURN)
        firstAction = gamemanager.HOTKEY_ACTIONS[0][0]
        keyBefore = game.settings.hotkeys[firstAction]
        keyDown(game, pygame.K_ESCAPE)
        self.assertIsNone(game.rebinding)
        self.assertEqual(game.hotkeyMessage, "Cancelled")
        self.assertEqual(game.settings.hotkeys[firstAction], keyBefore)

    def test_reset_to_defaults_puts_the_hotkeys_back(self):
        game = self.game
        firstAction = gamemanager.HOTKEY_ACTIONS[0][0]
        game.settings.rebind(firstAction, pygame.K_F7)
        game.pausePage = "hotkeys"
        game.hotkeySel = len(gamemanager.HOTKEY_ACTIONS)  # the "Reset to Defaults" row
        keyDown(game, pygame.K_RETURN)
        self.assertEqual(game.settings.hotkeys, gamemanager.Settings().hotkeys)
        self.assertNotEqual(game.settings.hotkeys[firstAction], pygame.K_F7)

    def test_quit_to_title_leaves_the_run(self):
        game = self.game
        game.menuOptions["Save on Exit"] = False
        keyDown(game, pygame.K_ESCAPE)
        self.selectRow("Quit to Title")
        keyDown(game, pygame.K_RETURN)
        self.assertEqual(game.scene, "title")

    def test_quit_to_desktop_stops_the_game(self):
        game = self.game
        game.menuOptions["Save on Exit"] = False
        keyDown(game, pygame.K_ESCAPE)
        self.selectRow("Quit to Desktop")
        keyDown(game, pygame.K_RETURN)
        self.assertFalse(game.running)

    def test_the_pause_view_describes_the_menu_for_the_renderer(self):
        game = self.game
        game.pausePage = "journal"
        pauseView = game.pauseView()
        self.assertEqual(pauseView["page"], "journal")
        self.assertEqual(len(pauseView["rows"]), len(gamemanager.PAUSE_ROWS))
        self.assertEqual(len(pauseView["hotkeys"]), len(gamemanager.HOTKEY_ACTIONS) + 1)
        game.pausePage = None
        self.assertIsNone(game.pauseView())


class TitleScreenTests(unittest.TestCase):
    """The title screen, its settings pages and the Attempts list."""

    def setUp(self):
        random.seed(9)
        self.game = gamemanager.gameManager()  # starts on the title screen
        if os.path.exists(gamemanager.SAVE_FILE):
            os.remove(gamemanager.SAVE_FILE)

    def skipFade(self):
        keyDown(self.game, pygame.K_SPACE)

    def chooseOption(self, option):
        game = self.game
        game.titleSel = game.titleOptions().index(option)
        keyDown(game, pygame.K_RETURN)

    def test_the_game_starts_on_the_title_screen(self):
        game = self.game
        self.assertEqual(game.scene, "title")
        self.assertEqual(game.titlePage, "main")
        self.assertEqual(game.titleFade, 0)

    def test_the_first_key_only_skips_the_fade_in(self):
        game = self.game
        keyDown(game, pygame.K_DOWN)
        self.assertEqual(game.titleFade, 255)
        self.assertEqual(game.titleSel, 0)

    def test_without_a_save_there_is_no_continue_button(self):
        options = self.game.titleOptions()
        self.assertNotIn("Continue", options)
        self.assertEqual(options[0], "New Game")
        self.assertEqual(options[-1], "Quit")

    def test_with_a_save_continue_comes_first(self):
        game = newGame()
        game.saveGame()
        self.assertEqual(self.game.titleOptions()[0], "Continue")
        os.remove(gamemanager.SAVE_FILE)

    def test_up_and_down_choose_an_option_and_stop_at_the_ends(self):
        game = self.game
        self.skipFade()
        keyDown(game, pygame.K_UP)
        self.assertEqual(game.titleSel, 0)
        for _ in range(10):
            keyDown(game, pygame.K_DOWN)
        self.assertEqual(game.titleSel, len(game.titleOptions()) - 1)

    def test_new_game_starts_a_run(self):
        game = self.game
        self.skipFade()
        self.chooseOption("New Game")
        self.assertEqual(game.scene, "playing")
        self.assertEqual(game.level, 0)

    def test_the_settings_pages_open_and_escape_backs_out(self):
        game = self.game
        self.skipFade()
        self.chooseOption("Settings")
        self.assertEqual(game.titlePage, "settings")
        self.chooseOption("Sound Settings")
        self.assertEqual(game.titlePage, "sound")
        keyDown(game, pygame.K_ESCAPE)
        self.assertEqual(game.titlePage, "settings")
        self.chooseOption("Display Settings")
        self.assertEqual(game.titlePage, "display")
        keyDown(game, pygame.K_ESCAPE)
        self.assertEqual(game.titlePage, "settings")
        keyDown(game, pygame.K_ESCAPE)
        self.assertEqual(game.titlePage, "main")
        self.assertEqual(game.titleOptions()[game.titleSel], "Settings")

    def test_applying_unchanged_display_settings_says_so(self):
        game = self.game
        self.skipFade()
        game.openTitlePage("display")
        game.titleSel = 2  # Apply
        keyDown(game, pygame.K_RETURN)
        self.assertEqual(game.titleMessage, "Nothing to change")

    def test_the_attempts_list_opens_and_closes(self):
        game = self.game
        self.skipFade()
        self.chooseOption("Attempts")
        self.assertEqual(game.scene, "attempts")
        game.draw()
        keyDown(game, pygame.K_ESCAPE)
        self.assertEqual(game.scene, "title")

    def test_quit_stops_the_game(self):
        game = self.game
        self.skipFade()
        self.chooseOption("Quit")
        self.assertFalse(game.running)

    def test_every_title_page_draws(self):
        game = self.game
        game.draw()  # still fading in
        game.titleFade = 255
        for page in ("main", "settings", "display", "sound"):
            game.openTitlePage(page)
            game.draw()


class DrawingTests(unittest.TestCase):
    """The game manager hands the renderer a whole frame without errors."""

    def setUp(self):
        random.seed(10)
        self.game = newGame()

    def test_a_playing_frame_draws_with_every_window_open(self):
        game = self.game
        game.setPositionsVisible()
        game.draw()
        for windowId in gamemanager.WINDOW_ORDER:
            if windowId != "items":
                game.openWindow(windowId)
        game.draw()
        self.assertEqual(set(game.windowRects), set(game.openWindows))

    def test_the_light_only_and_overlay_only_redraws_work(self):
        game = self.game
        game.setPositionsVisible()
        game.draw()
        game.draw(lightOnly=True)
        game.draw(overlayOnly=True)
        game.draw(glintOnly=True)

    def test_the_floor_message_clears_once_it_has_faded(self):
        game = self.game
        game.setPositionsVisible()
        game.messageBools["escapeMessage"] = True
        for _ in range(300):
            game.draw()
            if not game.messageBools["escapeMessage"]:
                break
        self.assertFalse(game.messageBools["escapeMessage"])


if __name__ == "__main__":
    unittest.main()
