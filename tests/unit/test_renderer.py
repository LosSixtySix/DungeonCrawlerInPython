"""The renderer: its sizes, camera, light and color helpers, and drawing every screen (a playing frame on
several floor themes, the windows, the pause menu, the title, the Attempts list, the console) under the dummy
video driver.

Unit tests; the rest are in tests/acceptance/test_renderer.py."""
import random
import unittest
import pygame
from cruel.graphics import renderer
from cruel.world import themes
from tests.helpers.renderer import FLOOR_TYPES, distinctColors


class RendererHelperTests(unittest.TestCase):
    """Sizes, the camera, the light and the theme colors, without drawing a frame."""

    @classmethod
    def setUpClass(cls):
        cls.window = pygame.display.set_mode((800, 600))

    def setUp(self):
        random.seed(1)
        self.painter = renderer.renderer(self.window)
        self.tileSize = self.painter.setTileSize(10)

    def test_the_map_fills_the_screen_in_whole_tiles(self):
        painter = self.painter
        self.assertEqual(self.tileSize, 10)
        self.assertEqual(painter.rowLength, 80)
        self.assertEqual(painter.columnLength, 60)
        self.assertEqual(painter.mapSurface.get_size(), (800, 600))
        self.assertEqual(painter.mapOffset, (0, 0))

    def test_leftover_pixels_are_split_evenly_around_the_map(self):
        painter = self.painter
        painter.setTileSize(14)
        self.assertEqual(painter.rowLength, 800 // 14)
        self.assertEqual(painter.columnLength, 600 // 14)
        self.assertEqual(painter.mapOffset, ((800 - 57 * 14) // 2, (600 - 42 * 14) // 2))

    def test_the_center_is_half_the_map_size(self):
        self.assertEqual(self.painter.getCenterCartesian(), (40, 30))

    def test_the_camera_puts_the_player_tile_in_the_middle_of_the_screen(self):
        painter = self.painter
        playerSpot = 5 + 7 * painter.rowLength
        painter.placeCamera(playerSpot, 1)
        playerTile = painter.tileOnScreen(playerSpot)
        self.assertEqual(playerTile.size, (10, 10))
        self.assertEqual(playerTile.center, (400, 300))

    def test_zooming_in_scales_tiles_and_keeps_the_player_centered(self):
        painter = self.painter
        playerSpot = 40 + 30 * painter.rowLength
        view = painter.placeCamera(playerSpot, 2)
        self.assertEqual(painter.zoom, 2)
        self.assertEqual(view.get_size(), (400, 300))
        playerTile = painter.tileOnScreen(playerSpot)
        self.assertEqual(playerTile.size, (20, 20))
        self.assertLessEqual(abs(playerTile.centerx - 400), 10)
        self.assertLessEqual(abs(playerTile.centery - 300), 10)

    def test_a_zoom_below_one_is_treated_as_one(self):
        painter = self.painter
        view = painter.placeCamera(0, 0)
        self.assertEqual(painter.zoom, 1)
        self.assertIs(view, self.window)

    def test_to_screen_applies_the_zoom(self):
        painter = self.painter
        painter.placeCamera(0, 3)
        originX, originY = painter.viewOrigin
        self.assertEqual(painter.toScreen(4, 5), (originX + 12, originY + 15))

    def test_wiggle_stays_between_zero_and_one_and_is_repeatable(self):
        for moment in (0, 0.25, 1.5, 17.9, 1234.5):
            value = renderer.renderer.wiggle(3, moment)
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 1)
            self.assertEqual(value, renderer.renderer.wiggle(3, moment))

    def test_a_still_light_has_no_offset_and_full_reach(self):
        self.assertEqual(self.painter.lightShape(12.3, None), (0.0, 0.0, 1.0))

    def test_a_swaying_light_drifts_less_than_half_a_tile(self):
        for moment in range(50):
            offsetX, offsetY, reach = self.painter.lightShape(moment / 7, "sway")
            self.assertLessEqual(abs(offsetX), renderer.SWAY_AMOUNT / 2)
            self.assertLessEqual(abs(offsetY), renderer.SWAY_AMOUNT / 2)
            self.assertEqual(reach, 1.0)

    def test_a_flickering_light_changes_its_reach_but_stays_put(self):
        for moment in range(50):
            offsetX, offsetY, reach = self.painter.lightShape(moment / 7, "flicker")
            self.assertEqual((offsetX, offsetY), (0.0, 0.0))
            self.assertLessEqual(abs(reach - 1), renderer.FLICKER_AMOUNT / 2)

    def test_the_light_is_full_near_you_and_dithered_further_out(self):
        lightLevel = self.painter.lightLevel
        visionRange = 10
        self.assertIsNone(lightLevel(10, 10, 10, 10, visionRange))
        self.assertIsNone(lightLevel(14, 10, 10, 10, visionRange))
        self.assertEqual(lightLevel(17, 10, 10, 10, visionRange), 0)
        self.assertEqual(lightLevel(19, 10, 10, 10, visionRange), 1)

    def test_brightness_maps_to_dither_and_darkness(self):
        brightnessLook = self.painter.brightnessLook
        self.assertEqual(brightnessLook(1.0), (None, 0))
        self.assertEqual(brightnessLook(0.8), (0, 0))
        self.assertEqual(brightnessLook(0.6), (1, 0))
        level, darkness = brightnessLook(0.0)
        self.assertEqual(level, 1)
        self.assertGreater(darkness, brightnessLook(0.4)[1])
        self.assertEqual(darkness % 12, 0)

    def test_set_theme_switches_the_colors(self):
        painter = self.painter
        theme = themes.randomTheme("All Gold")
        painter.setTheme(theme)
        self.assertIs(painter.theme, theme)
        self.assertEqual(painter.color("fog"), theme.colors["fog"])
        self.assertIn("chests", painter.sprites)
        self.assertEqual(len(painter.shades), len(renderer.DITHER_AMOUNTS) * 4)

    def test_a_tile_outside_every_room_is_sand(self):
        rooms = {"Stone": {1}, "Wood": {2}, "Gold": {3}}
        self.assertEqual(self.painter.roomOf(1, rooms), "Stone")
        self.assertEqual(self.painter.roomOf(3, rooms), "Gold")
        self.assertEqual(self.painter.roomOf(99, rooms), "Sand")

    def test_floor_colors_come_from_the_room(self):
        painter = self.painter
        rooms = {"Wood": {5}}
        self.assertEqual(painter.floorColor(5, rooms, False), painter.colorDict["floorWood"])
        self.assertEqual(painter.floorColor(5, rooms, True), painter.colorDict["memFloorWood"])

    def test_wall_colors_come_from_the_wall_name(self):
        painter = self.painter
        self.assertEqual(painter.wallColor("Gold Wall", False), painter.colorDict["wallGold"])
        self.assertEqual(painter.wallColor("Wood Wall", True), painter.colorDict["memWallWood"])
        # a wall whose first word isn't a room falls back to stone
        self.assertEqual(painter.wallColor("Coal Vein", False), painter.colorDict["wallStone"])

    def test_long_text_wraps_to_fit_a_width(self):
        painter = self.painter
        sentence = "the goblin chieftain swings his rusty axe at your head " * 3
        lines = painter.wrapText(sentence, painter.windowFont, 200)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(painter.windowFont.size(line)[0], 200)
        self.assertEqual(" ".join(lines).split(), sentence.split())

    def test_a_short_window_is_at_least_300_pixels_wide(self):
        windowSpec = {"id": "character", "title": "Hi", "kind": "rows", "rows": [("Gold", 3)]}
        width, height = self.painter.windowSize(windowSpec)
        self.assertEqual(width, 300)
        self.assertEqual(height, renderer.renderer.WINDOW_HEAD + renderer.renderer.ROW + 14)

    def test_glint_timing_is_the_same_every_time_for_a_tile(self):
        painter = self.painter
        self.assertEqual(painter.glintTimer(321), painter.glintTimer(321))
        period, _, _ = painter.glintTimer(321)
        self.assertTrue(renderer.GLINT_PERIOD[0] <= period <= renderer.GLINT_PERIOD[1])

    def test_the_forget_shade_and_tints_are_cached(self):
        painter = self.painter
        self.assertIs(painter.forgetShade(0.5), painter.forgetShade(0.5))
        self.assertIs(painter.fireTint(40), painter.fireTint(40))
        self.assertIs(painter.glowTint(40), painter.glowTint(40))
        self.assertEqual(painter.forgetShade(2.0).get_alpha(), 255)


class MenuScreenTests(unittest.TestCase):
    """The title screen and the Attempts list."""

    def setUp(self):
        random.seed(3)
        self.window = pygame.display.set_mode((1024, 768))
        self.painter = renderer.renderer(self.window)
        self.painter.setTileSize(10)

    def test_the_title_draws_while_fading_in_and_when_done(self):
        painter = self.painter
        options = ["New Game", "Attempts", "Settings", "Quit"]
        painter.drawTitle(options, 0, fade=0)
        # at the very start the title is invisible: only the empty background shows
        self.assertEqual(distinctColors(self.window, step=4), {tuple(painter.color("fog"))})
        painter.drawTitle(options, 2, message="That save could not be loaded", fade=255, heading="Settings", note="v1.0")
        self.assertGreater(len(distinctColors(self.window, step=4)), 2)

    def test_the_title_draws_in_every_theme(self):
        painter = self.painter
        for floorType in FLOOR_TYPES:
            painter.setTheme(themes.randomTheme(floorType))
            painter.drawTitle(["New Game", "Quit"], 1, fade=255)

    def test_the_attempts_list_draws_empty_and_full(self):
        painter = self.painter
        painter.drawAttempts([], 0)
        manyAttempts = [{"number": number, "deepest": 40 - number, "gold": number * 3, "date": "2026-01-01"} for number in range(1, 41)]
        painter.drawAttempts(manyAttempts, 0)
        painter.drawAttempts(manyAttempts, 10)

    def test_more_attempt_rows_fit_on_a_taller_screen(self):
        rowsHere = self.painter.attemptRowsThatFit()
        tallPainter = renderer.renderer(pygame.Surface((1024, 1200)))
        self.assertGreater(tallPainter.attemptRowsThatFit(), rowsHere)
        self.assertGreaterEqual(renderer.renderer(pygame.Surface((400, 200))).attemptRowsThatFit(), 1)

    def test_the_hud_draws_at_full_and_low_health(self):
        painter = self.painter
        painter.drawHud(10, 10, 5, 1)
        painter.drawHud(2, 10, 5, 1)


if __name__ == "__main__":
    unittest.main()
