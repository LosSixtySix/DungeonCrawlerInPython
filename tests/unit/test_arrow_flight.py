"""A Goblin Archer's arrow over time (gamemanager.arrowFrame): it flies, then sinks in and quivers on a hit, or
clatters, skids and fades on a miss."""
import unittest

from cruel.core import gamemanager
from cruel.core.gamemanager import ARROW_FADE_MS, ARROW_HIT_FRAME_MS, ARROW_MISS_FRAME_MS, arrowFrame

FLIGHT_MS = 100


def arrow(hit):
    return {"from": 0, "to": 5, "start": 0, "flightMs": FLIGHT_MS, "hit": hit, "look": None}


class FlightTests(unittest.TestCase):
    def test_it_leaves_the_bow_at_the_start(self):
        self.assertEqual(arrowFrame(arrow(True), 0), ("flight", 0.0, 1.0))

    def test_it_is_partway_along_halfway_through_its_flight(self):
        frame, progress, alpha = arrowFrame(arrow(True), FLIGHT_MS / 2)
        self.assertEqual((frame, alpha), ("flight", 1.0))
        self.assertAlmostEqual(progress, 0.5)

    def test_nothing_shows_before_it_is_shot(self):
        self.assertIsNone(arrowFrame(arrow(True), -1))


class HitTests(unittest.TestCase):
    def test_it_sinks_in_then_quivers_where_it_struck(self):
        self.assertEqual(arrowFrame(arrow(True), FLIGHT_MS), ("hit1", 1.0, 1.0))
        self.assertEqual(arrowFrame(arrow(True), FLIGHT_MS + ARROW_HIT_FRAME_MS), ("hit2", 1.0, 1.0))

    def test_then_it_is_gone(self):
        self.assertIsNone(arrowFrame(arrow(True), FLIGHT_MS + 2 * ARROW_HIT_FRAME_MS))


class MissTests(unittest.TestCase):
    def test_it_clatters_skids_and_lies_there(self):
        for frame in range(3):
            with self.subTest(frame=frame):
                self.assertEqual(arrowFrame(arrow(False), FLIGHT_MS + frame * ARROW_MISS_FRAME_MS), (f"miss{frame + 1}", 1.0, 1.0))

    def test_then_it_fades_out(self):
        lying = FLIGHT_MS + 3 * ARROW_MISS_FRAME_MS
        frame, _, alpha = arrowFrame(arrow(False), lying + ARROW_FADE_MS / 2)
        self.assertEqual(frame, "miss3")
        self.assertAlmostEqual(alpha, 0.5)
        self.assertIsNone(arrowFrame(arrow(False), lying + ARROW_FADE_MS))

    def test_the_sheet_timings_are_used(self):
        self.assertEqual((gamemanager.ARROW_MS_PER_TILE, ARROW_HIT_FRAME_MS, ARROW_MISS_FRAME_MS, ARROW_FADE_MS), (20, 90, 110, 450))


if __name__ == "__main__":
    unittest.main()
