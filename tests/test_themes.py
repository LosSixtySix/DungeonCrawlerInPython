"""Color themes: which palettes each floor type can get, and how a Theme turns them into drawing colors (themes.py)."""
import random
import unittest

from cruel.world import themes
from cruel.world import wall

BASE_FLOOR_TYPES = ["Mostly Stone", "Mostly Sand", "Mostly Wood", "All Gold", "Mixed", "Scorched Depths"]
THEME_KEYS = ["name", "fog", "panel", "font", "boxLine", "select", "player", "marker", "enemy", "chest",
              "doorNext", "doorPrev", "aim", "floor", "wall"]


class ThemeTableTests(unittest.TestCase):
    """The THEMES table itself."""

    def test_every_floor_type_and_ore_floor_has_at_least_one_theme(self):
        for floorType in BASE_FLOOR_TYPES + list(wall.ORE_FLOORS):
            self.assertTrue(themes.THEMES.get(floorType), floorType)

    def test_every_theme_has_every_color_it_needs(self):
        for floorType, options in themes.THEMES.items():
            for themeData in options:
                with self.subTest(floorType=floorType, theme=themeData.get("name")):
                    self.assertTrue(set(THEME_KEYS) <= set(themeData))
                    for room in ("Stone", "Wood", "Sand", "Gold"):
                        self.assertIn(room, themeData["floor"])
                        self.assertIn(room, themeData["wall"])

    def test_every_theme_builds_valid_rgb_colors(self):
        for floorType, options in themes.THEMES.items():
            for themeData in options:
                theme = themes.Theme(floorType, themeData)
                for colorName, color in theme.colors.items():
                    self.assertEqual(len(color), 3, colorName)
                    self.assertTrue(all(0 <= channel <= 255 for channel in color), (theme.name, colorName))


class ThemeLookupTests(unittest.TestCase):
    """Picking a theme for a new floor."""

    def test_a_random_theme_comes_from_its_floor_types_list(self):
        random.seed(1)
        for floorType in themes.THEMES:
            theme = themes.randomTheme(floorType)
            self.assertEqual(theme.floorType, floorType)
            self.assertIn(theme.name, [data["name"] for data in themes.THEMES[floorType]])

    def test_an_unknown_floor_type_falls_back_to_the_mixed_themes(self):
        theme = themes.randomTheme("Nowhere In Particular")
        self.assertIn(theme.name, [data["name"] for data in themes.THEMES["Mixed"]])


class ThemeColorTests(unittest.TestCase):
    """The color math behind remembered (out of sight) tiles."""

    def test_hex_colors_become_rgb_lists(self):
        self.assertEqual(themes.hexToRGB("#ff8000"), [255, 128, 0])

    def test_mix_moves_one_color_toward_another(self):
        black, white = [0, 0, 0], [255, 255, 255]
        self.assertEqual(themes.mix(black, white, 0), black)
        self.assertEqual(themes.mix(black, white, 1), white)
        self.assertEqual(themes.mix(black, [100, 200, 50], 0.5), [50, 100, 25])

    def test_desaturating_a_gray_leaves_it_alone_and_pulls_a_color_toward_gray(self):
        self.assertEqual(themes.desaturate([120, 120, 120], 1), [120, 120, 120])
        red = themes.desaturate([255, 0, 0], 1)
        self.assertEqual(red[0], red[1])
        self.assertEqual(red[1], red[2])

    def test_remembered_tiles_are_closer_to_the_fog_than_seen_ones(self):
        theme = themes.Theme("Mostly Stone", themes.THEMES["Mostly Stone"][0])
        fog = theme.colors["fog"]
        seenWall, rememberedWall = theme.colors["wallStone"], theme.colors["memWallStone"]
        distance = lambda color: sum(abs(channel - fogChannel) for channel, fogChannel in zip(color, fog))
        self.assertLess(distance(rememberedWall), distance(seenWall))

    def test_themes_without_lava_get_the_default_molten_colors(self):
        theme = themes.Theme("Mostly Stone", themes.THEMES["Mostly Stone"][0])
        self.assertEqual(theme.colors["floorMolten"], themes.hexToRGB(themes.MOLTEN_DEFAULT["floor"]))
        self.assertEqual(theme.colors["wallMolten"], themes.hexToRGB(themes.MOLTEN_DEFAULT["wall"]))

    def test_muted_text_sits_between_the_font_and_panel_colors(self):
        theme = themes.Theme("Mixed", themes.THEMES["Mixed"][0])
        font, panel, muted = theme.colors["font"], theme.colors["panel"], theme.colors["muted"]
        for fontChannel, panelChannel, mutedChannel in zip(font, panel, muted):
            self.assertTrue(min(fontChannel, panelChannel) <= mutedChannel <= max(fontChannel, panelChannel))


if __name__ == "__main__":
    unittest.main()
