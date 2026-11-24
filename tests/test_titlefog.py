"""The fog that rolls across the title screen: its noise, its shape with height, and drawing it."""
import unittest

import pygame

from cruel.graphics import titlefog


class FogShapeTests(unittest.TestCase):
    """How thick the fog can be at each height, and the noise it's made from."""

    def test_there_is_no_fog_above_the_fog_line(self):
        self.assertEqual(titlefog._shape(0.0), 0.0)
        self.assertEqual(titlefog._shape(titlefog.FOG_TOP), 0.0)

    def test_the_fog_gets_thicker_toward_the_floor(self):
        heights = [0.2, 0.4, 0.6, 0.8, 1.0]
        thickness = [titlefog._shape(height) for height in heights]
        self.assertEqual(thickness, sorted(thickness))
        self.assertGreater(thickness[-1], thickness[0])

    def test_smoothing_keeps_the_ends_and_the_middle(self):
        self.assertEqual(titlefog._smooth(0), 0)
        self.assertEqual(titlefog._smooth(1), 1)
        self.assertEqual(titlefog._smooth(0.5), 0.5)

    def test_noise_is_the_same_for_the_same_seed(self):
        firstNoise, secondNoise = titlefog._Noise(5), titlefog._Noise(5)
        self.assertEqual(firstNoise.at(3.3, 7.1, 8), secondNoise.at(3.3, 7.1, 8))

    def test_noise_repeats_across_every_period(self):
        noise = titlefog._Noise(1337)
        for position in (0.0, 1.25, 3.5, 6.9):
            self.assertAlmostEqual(noise.at(position, 2.5, 8), noise.at(position + 8, 2.5, 8))

    def test_noise_stays_between_zero_and_one(self):
        noise = titlefog._Noise(2)
        for step in range(200):
            value = noise.at(step * 0.37, step * 0.11, 5)
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 1)


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
        screen = self.screen
        screen.fill((0, 0, 0))
        self.fog.draw(screen, (255, 255, 255))
        self.assertEqual(tuple(screen.get_at((320, 5)))[:3], (0, 0, 0))
        bottomRow = {tuple(screen.get_at((pixelX, 470)))[:3] for pixelX in range(0, 640, 8)}
        self.assertNotEqual(bottomRow, {(0, 0, 0)})  # the fog shows near the floor

    def test_fog_at_zero_alpha_is_invisible(self):
        screen = self.screen
        screen.fill((0, 0, 0))
        self.fog.draw(screen, (255, 255, 255), alpha=0)
        bottomRow = {tuple(screen.get_at((pixelX, 470)))[:3] for pixelX in range(0, 640, 8)}
        self.assertEqual(bottomRow, {(0, 0, 0)})


if __name__ == "__main__":
    unittest.main()
