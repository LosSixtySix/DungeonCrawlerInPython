"""The Metropolis's own music: in a city the music comes from music/metropolis/ (Sound.setCity).

Integration tests."""
import unittest

from cruel.world import metropolis
from tests.helpers.metropolis import cityGame
from tests.support import newGame


class MetropolisMusicTests(unittest.TestCase):
    def test_a_run_that_starts_in_a_city_starts_on_the_city_music(self):
        game = cityGame()
        self.assertEqual(game.proportion, metropolis.METROPOLIS)
        game.sound.stopGameTheme()
        game.resetSession()  # (what loading a save in a city does)
        self.assertTrue(game.sound.inCity)
        self.assertIn(game.sound.gameTheme, game.sound.cityTracks)

    def test_a_run_outside_a_city_plays_the_game_music(self):
        game = newGame()
        self.assertFalse(game.sound.inCity)
        self.assertIn(game.sound.gameTheme, game.sound.gameTracks)


if __name__ == "__main__":
    unittest.main()
