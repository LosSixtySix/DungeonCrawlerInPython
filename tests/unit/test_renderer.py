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
        self.assertEqual(self.tileSize, 10)
        self.assertEqual(self.painter.rowLength, 80)
        self.assertEqual(self.painter.columnLength, 60)
        self.assertEqual(self.painter.mapSurface.get_size(), (800, 600))
        self.assertEqual(self.painter.mapOffset, (0, 0))

    def test_leftover_pixels_are_split_evenly_around_the_map(self):
        self.painter.setTileSize(14)
        self.assertEqual(self.painter.rowLength, 800 // 14)
        self.assertEqual(self.painter.columnLength, 600 // 14)
        self.assertEqual(self.painter.mapOffset, ((800 - 57 * 14) // 2, (600 - 42 * 14) // 2))

    def test_the_center_is_half_the_map_size(self):
        self.assertEqual(self.painter.getCenterCartesian(), (40, 30))

    def test_the_camera_puts_the_player_tile_in_the_middle_of_the_screen(self):
        playerSpot = 5 + 7 * self.painter.rowLength
        self.painter.placeCamera(playerSpot, 1)
        playerTile = self.painter.tileOnScreen(playerSpot)
        self.assertEqual(playerTile.size, (10, 10))
        self.assertEqual(playerTile.center, (400, 300))

    def test_zooming_in_scales_tiles_and_keeps_the_player_centered(self):
        playerSpot = 40 + 30 * self.painter.rowLength
        view = self.painter.placeCamera(playerSpot, 2)
        self.assertEqual(self.painter.zoom, 2)
        self.assertEqual(view.get_size(), (400, 300))
        playerTile = self.painter.tileOnScreen(playerSpot)
        self.assertEqual(playerTile.size, (20, 20))
        self.assertLessEqual(abs(playerTile.centerx - 400), 10)
        self.assertLessEqual(abs(playerTile.centery - 300), 10)

    def test_a_zoom_below_one_is_treated_as_one(self):
        view = self.painter.placeCamera(0, 0)
        self.assertEqual(self.painter.zoom, 1)
        self.assertIs(view, self.window)

    def test_to_screen_applies_the_zoom(self):
        self.painter.placeCamera(0, 3)
        originX, originY = self.painter.viewOrigin
        self.assertEqual(self.painter.toScreen(4, 5), (originX + 12, originY + 15))

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
        visionRange = 10
        self.assertIsNone(self.painter.lightLevel(10, 10, 10, 10, visionRange))
        self.assertIsNone(self.painter.lightLevel(14, 10, 10, 10, visionRange))
        self.assertEqual(self.painter.lightLevel(17, 10, 10, 10, visionRange), 0)
        self.assertEqual(self.painter.lightLevel(19, 10, 10, 10, visionRange), 1)

    def test_brightness_maps_to_dither_and_darkness(self):
        self.assertEqual(self.painter.brightnessLook(1.0), (None, 0))
        self.assertEqual(self.painter.brightnessLook(0.8), (0, 0))
        self.assertEqual(self.painter.brightnessLook(0.6), (1, 0))
        level, darkness = self.painter.brightnessLook(0.0)
        self.assertEqual(level, 1)
        self.assertGreater(darkness, self.painter.brightnessLook(0.4)[1])
        self.assertEqual(darkness % 12, 0)

    def test_set_theme_switches_the_colors(self):
        theme = themes.randomTheme("All Gold")
        self.painter.setTheme(theme)
        self.assertIs(self.painter.theme, theme)
        self.assertEqual(self.painter.color("fog"), theme.colors["fog"])
        self.assertIn("chests", self.painter.sprites)
        self.assertEqual(len(self.painter.shades), len(renderer.DITHER_AMOUNTS) * 4)

    def test_a_tile_outside_every_room_is_sand(self):
        rooms = {"Stone": {1}, "Wood": {2}, "Gold": {3}}
        self.assertEqual(self.painter.roomOf(1, rooms), "Stone")
        self.assertEqual(self.painter.roomOf(3, rooms), "Gold")
        self.assertEqual(self.painter.roomOf(99, rooms), "Sand")

    def test_floor_colors_come_from_the_room(self):
        rooms = {"Wood": {5}}
        self.assertEqual(self.painter.floorColor(5, rooms, False), self.painter.colorDict["floorWood"])
        self.assertEqual(self.painter.floorColor(5, rooms, True), self.painter.colorDict["memFloorWood"])

    def test_wall_colors_come_from_the_wall_name(self):
        self.assertEqual(self.painter.wallColor("Gold Wall", False), self.painter.colorDict["wallGold"])
        self.assertEqual(self.painter.wallColor("Wood Wall", True), self.painter.colorDict["memWallWood"])
        # a wall whose first word isn't a room falls back to stone
        self.assertEqual(self.painter.wallColor("Coal Vein", False), self.painter.colorDict["wallStone"])

    def test_long_text_wraps_to_fit_a_width(self):
        sentence = "the goblin chieftain swings his rusty axe at your head " * 3
        lines = self.painter.wrapText(sentence, self.painter.windowFont, 200)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(self.painter.windowFont.size(line)[0], 200)
        self.assertEqual(" ".join(lines).split(), sentence.split())

    def test_a_short_window_is_at_least_300_pixels_wide(self):
        windowSpec = {"id": "character", "title": "Hi", "kind": "rows", "rows": [("Gold", 3)]}
        width, height = self.painter.windowSize(windowSpec)
        self.assertEqual(width, 300)
        self.assertEqual(height, renderer.renderer.WINDOW_HEAD + renderer.renderer.ROW + 14)

    def test_glint_timing_is_the_same_every_time_for_a_tile(self):
        self.assertEqual(self.painter.glintTimer(321), self.painter.glintTimer(321))
        period, _, _ = self.painter.glintTimer(321)
        self.assertTrue(renderer.GLINT_PERIOD[0] <= period <= renderer.GLINT_PERIOD[1])

    def test_the_forget_shade_and_tints_are_cached(self):
        self.assertIs(self.painter.forgetShade(0.5), self.painter.forgetShade(0.5))
        self.assertIs(self.painter.fireTint(40), self.painter.fireTint(40))
        self.assertIs(self.painter.glowTint(40), self.painter.glowTint(40))
        self.assertEqual(self.painter.forgetShade(2.0).get_alpha(), 255)


class MenuScreenTests(unittest.TestCase):
    """The title screen and the Attempts list."""

    def setUp(self):
        random.seed(3)
        self.window = pygame.display.set_mode((1024, 768))
        self.painter = renderer.renderer(self.window)
        self.painter.setTileSize(10)

    def test_the_title_draws_while_fading_in_and_when_done(self):
        options = ["New Game", "Attempts", "Settings", "Quit"]
        self.painter.drawTitle(options, 0, fade=0)
        # at the very start the title is invisible: only the empty background shows
        self.assertEqual(distinctColors(self.window, step=4), {tuple(self.painter.color("fog"))})
        self.painter.drawTitle(options, 2, message="That save could not be loaded", fade=255, heading="Settings", note="v1.0")
        self.assertGreater(len(distinctColors(self.window, step=4)), 2)

    def test_the_title_draws_in_every_theme(self):
        for floorType in FLOOR_TYPES:
            self.painter.setTheme(themes.randomTheme(floorType))
            self.painter.drawTitle(["New Game", "Quit"], 1, fade=255)

    def test_the_attempts_list_draws_empty_and_full(self):
        self.painter.drawAttempts([], 0)
        manyAttempts = [{"number": number, "deepest": 40 - number, "gold": number * 3, "date": "2026-01-01"} for number in range(1, 41)]
        self.painter.drawAttempts(manyAttempts, 0)
        self.painter.drawAttempts(manyAttempts, 10)

    def test_more_attempt_rows_fit_on_a_taller_screen(self):
        rowsHere = self.painter.attemptRowsThatFit()
        tallPainter = renderer.renderer(pygame.Surface((1024, 1200)))
        self.assertGreater(tallPainter.attemptRowsThatFit(), rowsHere)
        self.assertGreaterEqual(renderer.renderer(pygame.Surface((400, 200))).attemptRowsThatFit(), 1)

    def test_the_hud_draws_at_full_and_low_health(self):
        self.painter.drawHud(10, 10, 5, 1)
        self.painter.drawHud(2, 10, 5, 1)


if __name__ == "__main__":
    unittest.main()
