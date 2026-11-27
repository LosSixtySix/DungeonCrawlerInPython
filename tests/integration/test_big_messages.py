"""The big messages over the screen (a new floor, an event starting, the Seal broken, Escape): each fades away
over its own time in real time, however fast the frames come (renderer.fadeMessage); an event's name shows as
long as a floor's and only darkens the view behind it, where the others start from black.

Integration tests."""
import random
import unittest
from unittest import mock

from cruel.core import gamemanager
from tests.support import newGame


class FrameClock:
    """pygame.time.get_ticks for the renderer, moving on stepMs a frame."""

    def __init__(self, stepMs):
        self.now, self.stepMs = 1000, stepMs

    def __call__(self):
        return self.now

    def tick(self):
        self.now += self.stepMs


def secondsOnScreen(game, key, stepMs):
    """How long (in game time) the message key stays up, frames coming every stepMs."""
    clock = FrameClock(stepMs)
    game.messageBools = {name: name == key for name in game.messageBools}
    game.painter.fade, game.painter.messageTicks = 255, None  # (a message from before this one is forgotten)
    with mock.patch("pygame.time.get_ticks", clock):
        started = clock.now
        while game.messageBools[key]:
            game.draw(overlayOnly=True)
            clock.tick()
            assert clock.now - started < 20000, "the message never went"
    return (clock.now - started) / 1000


class MessageTest(unittest.TestCase):
    def setUp(self):
        random.seed(3)
        self.game = newGame()
        self.game.setPositionsVisible()
        self.game.draw()


class TimingTests(MessageTest):
    def test_an_event_shows_as_long_as_a_floor(self):
        self.assertEqual(gamemanager.MESSAGE_SECONDS["eventMessage"], gamemanager.MESSAGE_SECONDS["floorLevelMessage"])
        floor = secondsOnScreen(self.game, "floorLevelMessage", 16)
        event = secondsOnScreen(self.game, "eventMessage", 16)
        self.assertAlmostEqual(event, floor, delta=0.05)
        self.assertAlmostEqual(floor, gamemanager.MESSAGE_SECONDS["floorLevelMessage"], delta=0.05)

    def test_slow_frames_do_not_make_it_last_longer_or_shorter(self):
        quick = secondsOnScreen(self.game, "eventMessage", 16)
        slow = secondsOnScreen(self.game, "eventMessage", 45)
        self.assertAlmostEqual(slow, quick, delta=0.06)

    def test_a_stalled_frame_does_not_eat_the_message(self):
        clock = FrameClock(16)
        self.game.messageBools["floorLevelMessage"] = True
        self.game.painter.fade, self.game.painter.messageTicks = 255, None
        with mock.patch("pygame.time.get_ticks", clock):
            self.game.draw(overlayOnly=True)
            clock.now += 3000  # (a new floor being made)
            self.game.draw(overlayOnly=True)
        self.assertTrue(self.game.messageBools["floorLevelMessage"], "still up")
        self.assertGreater(self.game.painter.fade, 200)


class ShadeTests(MessageTest):
    def shadeBehind(self, key):
        """How dark (alpha 0 to 255) the screen behind the message is on its first frame."""
        self.game.messageBools = {name: name == key for name in self.game.messageBools}
        self.game.painter.fade = 255
        self.game.draw()
        return self.game.painter.messageCanvas.get_at((0, 0)).a

    def test_an_event_only_darkens_the_view(self):
        shade = self.shadeBehind("eventMessage")
        self.assertEqual(shade, gamemanager.MESSAGE_SHADES["eventMessage"])
        self.assertLess(shade, 255)

    def test_a_floor_message_starts_from_black(self):
        self.assertEqual(self.shadeBehind("floorLevelMessage"), 255)

    def test_the_darkness_lightens_as_it_fades(self):
        self.shadeBehind("eventMessage")
        self.game.painter.fade = 100
        self.game.draw()
        self.assertEqual(self.game.painter.messageCanvas.get_at((0, 0)).a, 100 * gamemanager.MESSAGE_SHADES["eventMessage"] // 255)


if __name__ == "__main__":
    unittest.main()
