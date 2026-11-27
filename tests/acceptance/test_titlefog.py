"""The fog that rolls across the title screen: its noise, its shape with height, and drawing it.

Acceptance tests; the rest are in tests/unit/test_titlefog.py."""
import unittest
import pygame
from cruel.graphics import titlefog


class FogDrawingTests(unittest.TestCase):
    """Building the fog layers once and drawing them over the title screen."""

    @classmethod
    def setUpClass(cls):
        cls.screen = pygame.display.set_mode((640, 480))
        cls.fog = titlefog.TitleFog()
        cls.fog.build()  # the slow part, done once for the whole class

    def test_one_layer_is_built_for_each_layer_setting(self):
        self.assertEqual(len(self.fog.base), len(titlefog.LAYERS))
        for layer in self.fog.base:
            self.assertEqual(layer.get_size(), (titlefog.LOW_W, titlefog.LOW_H))

    def test_layers_are_scaled_to_two_screens_wide(self):
        layers = self.fog.layersFor((200, 180, 160), (640, 480))
        for layer in layers:
            self.assertEqual(layer.get_size(), (640 * titlefog.SCREENS_PER_REPEAT, 480))

    def test_the_same_color_and_size_reuse_the_tinted_layers(self):
        firstLayers = self.fog.layersFor((10, 20, 30), (640, 480))
        self.assertIs(self.fog.layersFor((10, 20, 30, 255), (640, 480)), firstLayers)
        self.assertIsNot(self.fog.layersFor((99, 20, 30), (640, 480)), firstLayers)

    def test_drawing_the_fog_leaves_the_top_of_the_screen_alone(self):
        self.screen.fill((0, 0, 0))
        self.fog.draw(self.screen, (255, 255, 255))
        self.assertEqual(tuple(self.screen.get_at((320, 5)))[:3], (0, 0, 0))
        bottomRow = {tuple(self.screen.get_at((pixelX, 470)))[:3] for pixelX in range(0, 640, 8)}
        self.assertNotEqual(bottomRow, {(0, 0, 0)})  # the fog shows near the floor

    def test_fog_at_zero_alpha_is_invisible(self):
        self.screen.fill((0, 0, 0))
        self.fog.draw(self.screen, (255, 255, 255), alpha=0)
        bottomRow = {tuple(self.screen.get_at((pixelX, 470)))[:3] for pixelX in range(0, 640, 8)}
        self.assertEqual(bottomRow, {(0, 0, 0)})


if __name__ == "__main__":
    unittest.main()
