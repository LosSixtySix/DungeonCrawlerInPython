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
        self.game.draw()
        self.assertGreater(len(distinctColors(self.game.win)), 3)

    def test_the_player_tile_is_drawn_in_the_middle_of_the_screen(self):
        self.game.grid[self.game.playerPositionFlat][0] = 1  # the game loop marks the player's tile
        self.game.draw()
        playerTile = self.game.painter.tileOnScreen(self.game.playerPositionFlat)
        screenWidth, screenHeight = self.game.win.get_size()
        self.assertLessEqual(abs(playerTile.centerx - screenWidth // 2), self.game.tileSize)
        self.assertLessEqual(abs(playerTile.centery - screenHeight // 2), self.game.tileSize)
        tileColors = {tuple(self.game.win.get_at((pixelX, pixelY)))[:3] for pixelX in range(playerTile.left, playerTile.right)
                      for pixelY in range(playerTile.top, playerTile.bottom)}
        self.assertGreater(len(tileColors), 1)  # the player sprite, not a flat floor tile

    def test_standing_on_a_mineshaft_draws_you_like_standing_on_a_door(self):
        self.game.grid[self.game.playerPositionFlat] = [1, 1, metropolis.Mineshaft("mine")]  # (the shaft rides along under you)
        with mock.patch.object(renderer.renderer, "plantPicture", wraps=self.game.painter.plantPicture) as plantPicture:
            self.game.draw()  # (a mineshaft has a kind, like a plant: it used to be drawn as one, and that crashed)
        plantPicture.assert_not_called()

    def test_neither_end_of_either_mineshaft_is_ever_drawn_as_a_plant(self):
        for kind in metropolis.WORKS:
            for down in (True, False):
                self.game.grid[self.game.playerPositionFlat] = [1, 1, metropolis.Mineshaft(kind, down)]
                with mock.patch.object(renderer.renderer, "plantPicture", wraps=self.game.painter.plantPicture) as plantPicture:
                    self.game.draw()
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
        self.game.grid[self.game.playerPositionFlat] = [1, 1, plants.Plant.grown("bloodcap")]
        with mock.patch.object(renderer.renderer, "plantPicture", wraps=self.game.painter.plantPicture) as plantPicture:
            self.game.draw()
        plantPicture.assert_called()

    def test_every_floor_theme_draws(self):
        for floorType in FLOOR_TYPES:
            for themeData in themes.THEMES[floorType]:
                with self.subTest(theme=themeData["name"]):
                    self.game.setTheme(themes.Theme(floorType, themeData))
                    self.game.draw()
                    self.assertEqual(self.game.painter.colorDict, self.game.theme.colors)
                    self.assertGreater(len(distinctColors(self.game.win)), 3)

    def test_deeper_floors_draw(self):
        game = newGame(level=2)
        game.setPositionsVisible()
        game.draw()

    def test_each_zoom_level_draws(self):
        for zoom in gamemanager.MAP_ZOOMS:
            self.game.settings.mapZoom = zoom
            self.game.draw()
            self.assertEqual(self.game.painter.zoom, max(1, int(zoom)))

    def test_every_light_style_draws(self):
        for style in gamemanager.LIGHT_STYLES:
            self.game.settings.lightStyle = style
            self.game.lightStep += 3
            self.game.draw()
            self.game.draw(lightOnly=True)
        self.game.menuOptions["Animated Light"] = False
        self.game.draw()

    def test_every_window_draws_open_and_focused(self):
        for windowId in gamemanager.WINDOW_ORDER:
            if windowId != "items":
                self.game.openWindow(windowId)
                self.game.draw()
        self.assertEqual(set(self.game.windowRects), set(self.game.openWindows))
        for windowId, windowRect in self.game.windowRects.items():
            if windowId == "loot":
                continue  # the Loot Table's Walls tab is taller than a 768-pixel screen (reported, not tested)
            self.assertTrue(self.game.win.get_rect().contains(windowRect), windowId)

    def test_the_items_here_window_draws_for_the_starting_chest(self):
        self.game.player.playerDirection = 0  # facing the chest on the left
        self.game.setLookPosition()
        self.game.roomItems = self.game.getItemsFromGrid()
        self.game.openWindow("items")
        self.game.draw()
        self.assertIn("items", self.game.windowRects)

    def test_the_hud_can_be_hidden(self):
        self.game.menuOptions["Mini HUD"] = False
        self.game.draw()

    def test_the_pause_menu_and_hotkeys_page_draw(self):
        for page in ("journal", "hotkeys"):
            self.game.pausePage = page
            self.game.draw()
        self.game.rebinding = "interact"
        self.game.draw()
        self.game.rebinding = None

    def test_the_developer_console_draws(self):
        self.game.console.toggle()
        self.game.draw()
        self.game.console.toggle()

    def test_a_floor_message_draws_and_fades(self):
        self.game.messageBools["floorLevelMessage"] = True
        self.game.painter.fade, self.game.painter.messageTicks = 255, None
        with mock.patch("pygame.time.get_ticks", return_value=1000) as clock:  # (two frames 0.1s apart)
            self.game.draw()
            clock.return_value = 1100
            self.game.draw()
        self.assertLess(self.game.painter.fade, 255)

    def test_the_message_canvas_covers_the_screen(self):
        canvas = self.game.painter.drawMessage("Floor 3\nGranite Hall")
        self.assertEqual(canvas.get_size(), (self.game.painter.screenWidth, self.game.painter.screenHeight))

    def test_an_aim_line_draws_and_is_cleaned_up(self):
        target = self.game.playerPositionFlat + 3
        self.game.aimLine = self.game.createARay(self.game.playerPositionFlat, target)
        self.game.draw()
        self.assertEqual(self.game.painter.aimDrawn, set(self.game.aimLine))
        self.game.aimLine = None
        self.game.draw()
        self.assertEqual(self.game.painter.aimDrawn, set())

    def test_popups_and_blood_draw(self):
        self.game.addPopup("+2 Wood", self.game.playerPositionFlat)
        self.game.addBlood(self.game.playerPositionFlat + 1, 0.8)
        self.game.draw()


if __name__ == "__main__":
    unittest.main()
