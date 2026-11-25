"""The game manager as a whole: starting a run, walking between floors, moving, digging, looting, fighting,
dying, saving and loading, the pause menu and the title screen.

Acceptance tests; the rest are in tests/integration/test_gamemanager.py."""
import os
import random
import unittest
from unittest import mock
import pygame
from cruel.core import gamemanager
from cruel.entities import enemies
from cruel.inventory import items
from cruel.world import wall
from tests.support import newGame, placePlayer, openTile
from tests.helpers.gamemanager import CHEST, DOWN, DOWN_DOOR, ENEMY, FLOOR, LEFT, PILE, PLAYER, RIGHT, UP, UP_DOOR, WALL, keyDown, standInOpenFloor


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
        game.painter.messageTicks = None
        with mock.patch("pygame.time.get_ticks", return_value=0) as clock:  # (frames 1/60 s apart)
            for frame in range(300):
                clock.return_value = frame * 1000 // 60
                game.draw()
                if not game.messageBools["escapeMessage"]:
                    break
        self.assertFalse(game.messageBools["escapeMessage"])


if __name__ == "__main__":
    unittest.main()
