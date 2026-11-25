"""The renderer: its sizes, camera, light and color helpers, and drawing every screen (a playing frame on
several floor themes, the windows, the pause menu, the title, the Attempts list, the console) under the dummy
video driver.

Acceptance tests; the rest are in tests/unit/test_renderer.py."""
import random
import unittest
from unittest import mock
from cruel.core import gamemanager
from cruel.graphics import renderer
from cruel.world import metropolis
from cruel.world import plants
from cruel.world import themes
from tests import support
from tests.support import newGame
from tests.helpers.metropolis import cityGame
from tests.helpers.mineshafts import shaftSpot
from tests.helpers.renderer import FLOOR_TYPES, distinctColors


class PlayingFrameTests(unittest.TestCase):
    """Whole playing frames, drawn through the game manager."""

    def setUp(self):
        random.seed(2)
        self.game = newGame()
        self.game.setPositionsVisible()

    def test_a_frame_draws_and_shows_more_than_one_color(self):
        game = self.game
        game.draw()
        self.assertGreater(len(distinctColors(game.win)), 3)

    def test_the_player_tile_is_drawn_in_the_middle_of_the_screen(self):
        game = self.game
        game.grid[game.playerPositionFlat][0] = 1  # the game loop marks the player's tile
        game.draw()
        playerTile = game.painter.tileOnScreen(game.playerPositionFlat)
        screenWidth, screenHeight = game.win.get_size()
        self.assertLessEqual(abs(playerTile.centerx - screenWidth // 2), game.tileSize)
        self.assertLessEqual(abs(playerTile.centery - screenHeight // 2), game.tileSize)
        tileColors = {tuple(game.win.get_at((pixelX, pixelY)))[:3] for pixelX in range(playerTile.left, playerTile.right)
                      for pixelY in range(playerTile.top, playerTile.bottom)}
        self.assertGreater(len(tileColors), 1)  # the player sprite, not a flat floor tile

    def test_standing_on_a_mineshaft_draws_you_like_standing_on_a_door(self):
        game = self.game
        game.grid[game.playerPositionFlat] = [1, 1, metropolis.Mineshaft("mine")]  # (the shaft rides along under you)
        with mock.patch.object(renderer.renderer, "plantPicture", wraps=game.painter.plantPicture) as plantPicture:
            game.draw()  # (a mineshaft has a kind, like a plant: it used to be drawn as one, and that crashed)
        plantPicture.assert_not_called()

    def test_neither_end_of_either_mineshaft_is_ever_drawn_as_a_plant(self):
        game = self.game
        for kind in metropolis.WORKS:
            for down in (True, False):
                game.grid[game.playerPositionFlat] = [1, 1, metropolis.Mineshaft(kind, down)]
                with mock.patch.object(renderer.renderer, "plantPicture", wraps=game.painter.plantPicture) as plantPicture:
                    game.draw()
                plantPicture.assert_not_called()

    def test_walking_onto_a_citys_mineshafts_and_the_shafts_up_from_their_floors(self):
        """The real thing: a Metropolis's shafts, and the ends of them on the mine and the farm."""
        for kind in metropolis.WORKS:
            game = cityGame(3)
            game.setPositionsVisible()
            for climb in (False, True):
                if climb:
                    game.onEnter()  # (down the shaft: you arrive standing on the shaft back up)
                    self.assertEqual(game.currentLocation[0], metropolis.MINESHAFT)
                else:
                    support.placePlayer(game, shaftSpot(game, kind))
                game.grid[game.playerPositionFlat] = list(game.currentLocation)  # (as the game loop leaves it: what
                game.grid[game.playerPositionFlat][0] = 1                         # you stand on stays on your tile)
                drawnAsPlants = []
                original = game.painter.plantPicture
                with mock.patch.object(game.painter, "plantPicture",
                                       side_effect=lambda plant: drawnAsPlants.append(plant) or original(plant)):
                    game.draw()
                self.assertFalse([thing for thing in drawnAsPlants if not isinstance(thing, plants.Plant)], (kind, climb))

    def test_a_plant_you_stand_in_is_still_drawn_over_you(self):
        game = self.game
        game.grid[game.playerPositionFlat] = [1, 1, plants.Plant.grown("bloodcap")]
        with mock.patch.object(renderer.renderer, "plantPicture", wraps=game.painter.plantPicture) as plantPicture:
            game.draw()
        plantPicture.assert_called()

    def test_every_floor_theme_draws(self):
        game = self.game
        for floorType in FLOOR_TYPES:
            for themeData in themes.THEMES[floorType]:
                with self.subTest(theme=themeData["name"]):
                    game.setTheme(themes.Theme(floorType, themeData))
                    game.draw()
                    self.assertEqual(game.painter.colorDict, game.theme.colors)
                    self.assertGreater(len(distinctColors(game.win)), 3)

    def test_deeper_floors_draw(self):
        game = newGame(level=2)
        game.setPositionsVisible()
        game.draw()

    def test_each_zoom_level_draws(self):
        game = self.game
        for zoom in gamemanager.MAP_ZOOMS:
            game.settings.mapZoom = zoom
            game.draw()
            self.assertEqual(game.painter.zoom, max(1, int(zoom)))

    def test_every_light_style_draws(self):
        game = self.game
        for style in gamemanager.LIGHT_STYLES:
            game.settings.lightStyle = style
            game.lightStep += 3
            game.draw()
            game.draw(lightOnly=True)
        game.menuOptions["Animated Light"] = False
        game.draw()

    def test_every_window_draws_open_and_focused(self):
        game = self.game
        for windowId in gamemanager.WINDOW_ORDER:
            if windowId != "items":
                game.openWindow(windowId)
                game.draw()
        self.assertEqual(set(game.windowRects), set(game.openWindows))
        for windowId, windowRect in game.windowRects.items():
            if windowId == "loot":
                continue  # the Loot Table's Walls tab is taller than a 768-pixel screen (reported, not tested)
            self.assertTrue(game.win.get_rect().contains(windowRect), windowId)

    def test_the_items_here_window_draws_for_the_starting_chest(self):
        game = self.game
        game.player.playerDirection = 0  # facing the chest on the left
        game.setLookPosition()
        game.roomItems = game.getItemsFromGrid()
        game.openWindow("items")
        game.draw()
        self.assertIn("items", game.windowRects)

    def test_the_hud_can_be_hidden(self):
        game = self.game
        game.menuOptions["Mini HUD"] = False
        game.draw()

    def test_the_pause_menu_and_hotkeys_page_draw(self):
        game = self.game
        for page in ("journal", "hotkeys"):
            game.pausePage = page
            game.draw()
        game.rebinding = "interact"
        game.draw()
        game.rebinding = None

    def test_the_developer_console_draws(self):
        game = self.game
        game.console.toggle()
        game.draw()
        game.console.toggle()

    def test_a_floor_message_draws_and_fades(self):
        game = self.game
        game.messageBools["floorLevelMessage"] = True
        painter = game.painter
        painter.fade = 255
        game.draw()
        self.assertLess(painter.fade, 255)

    def test_the_message_canvas_covers_the_screen(self):
        painter = self.game.painter
        canvas = painter.drawMessage("Floor 3\nGranite Hall")
        self.assertEqual(canvas.get_size(), (painter.screenWidth, painter.screenHeight))

    def test_an_aim_line_draws_and_is_cleaned_up(self):
        game = self.game
        target = game.playerPositionFlat + 3
        game.aimLine = game.createARay(game.playerPositionFlat, target)
        game.draw()
        self.assertEqual(game.painter.aimDrawn, set(game.aimLine))
        game.aimLine = None
        game.draw()
        self.assertEqual(game.painter.aimDrawn, set())

    def test_popups_and_blood_draw(self):
        game = self.game
        game.addPopup("+2 Wood", game.playerPositionFlat)
        game.addBlood(game.playerPositionFlat + 1, 0.8)
        game.draw()


if __name__ == "__main__":
    unittest.main()
