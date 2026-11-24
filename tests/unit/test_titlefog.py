"""The fog that rolls across the title screen: its noise, its shape with height, and drawing it.

Unit tests; the rest are in tests/acceptance/test_titlefog.py."""
import unittest
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


if __name__ == "__main__":
    unittest.main()
