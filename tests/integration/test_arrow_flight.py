"""Starting an arrow (gameManager.startArrow), what the renderer is handed for it (throwView) and drawing it."""
import unittest
from unittest import mock

from cruel.core import gamemanager
from cruel.graphics import sprites
from tests.helpers.gamemanager import FLOOR, RIGHT, clearAround, newGame, standInOpenFloor


class ArrowFlightTest(unittest.TestCase):
    """You stand in open floor; an archer two tiles to your left shoots at a spot three tiles to your right."""

    def setUp(self):
        game = self.game = newGame()
        self.here = standInOpenFloor(game, facing=RIGHT)
        clearAround(game, self.here)
        for step in range(1, 6):
            game.grid[self.here + step] = [FLOOR, 1]
        self.archerSpot, self.targetSpot = self.here - 2, self.here + 3

    def shoot(self, hit=True, look=None, clock=1000):
        with mock.patch("pygame.time.get_ticks", return_value=clock):
            return self.game.startArrow(self.archerSpot, self.targetSpot, hit, look)

    def arrowsShownAt(self, clock):
        with mock.patch("pygame.time.get_ticks", return_value=clock):
            return self.game.throwView()["arrows"]


class StartArrowTests(ArrowFlightTest):
    def test_it_flies_twenty_milliseconds_a_tile(self):
        arrives = self.shoot()
        flightMs = 5 * gamemanager.ARROW_MS_PER_TILE
        self.assertEqual(arrives, 1000 + flightMs, "the hit can land when it gets there")
        self.assertEqual(self.game.arrows, [{"from": self.archerSpot, "to": self.targetSpot, "start": 1000,
                                             "flightMs": flightMs, "hit": True, "look": None}])

    def test_a_floor_you_are_not_on_shows_no_arrow(self):
        self.game.simulatingAway = True
        self.shoot()
        self.assertEqual(self.game.arrows, [])


class ThrowViewTests(ArrowFlightTest):
    def test_halfway_through_its_flight_it_is_halfway_there(self):
        self.shoot(look="ember")
        [arrow] = self.arrowsShownAt(1000 + 50)
        self.assertEqual((arrow["from"], arrow["to"], arrow["look"]), (self.archerSpot, self.targetSpot, "ember"))
        frame, progress, alpha = arrow["frame"]
        self.assertEqual(frame, "flight")
        self.assertAlmostEqual(progress, 0.5)

    def test_after_its_hit_frames_it_is_gone(self):
        self.shoot(hit=True)
        self.assertEqual(self.arrowsShownAt(1000 + 100)[0]["frame"][0], "hit1")
        self.assertEqual(self.arrowsShownAt(1000 + 100 + 2 * gamemanager.ARROW_HIT_FRAME_MS), [])

    def test_with_both_ends_out_of_sight_it_is_not_drawn(self):
        self.shoot()
        self.game.grid[self.archerSpot][1] = 0
        self.game.grid[self.targetSpot][1] = 0
        self.assertEqual(self.arrowsShownAt(1000 + 50), [])


class DrawArrowTests(ArrowFlightTest):
    def drawnColors(self, spot):
        corner = self.game.painter.screenTile(spot)
        return {tuple(self.game.painter.win.get_at((corner.x + column, corner.y + row)))[:3]
                for column in range(self.game.painter.tileSize) for row in range(self.game.painter.tileSize)}

    def test_a_faction_arrow_is_drawn_with_its_cloth_fletching(self):
        self.game.painter.drawArrow({"from": self.archerSpot, "to": self.targetSpot, "look": "tidewater",
                                     "frame": ("flight", 0.0, 1.0)})
        self.assertIn(sprites.EXPANSION_LOOKS["tidewater"]["goblin"]["c"], self.drawnColors(self.archerSpot))

    def test_a_wild_arrow_is_drawn_with_red_fletching_where_it_struck(self):
        self.game.painter.drawArrow({"from": self.archerSpot, "to": self.targetSpot, "look": None,
                                     "frame": ("hit1", 1.0, 1.0)})
        self.assertIn(sprites.ARROW_COLORS["f"], self.drawnColors(self.targetSpot))

    def test_a_fading_arrow_draws_without_error(self):
        self.game.painter.drawArrow({"from": self.archerSpot, "to": self.targetSpot, "look": None,
                                     "frame": ("miss3", 1.0, 0.4)})


if __name__ == "__main__":
    unittest.main()
