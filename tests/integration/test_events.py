"""Floor events: rolling one for a new floor, the event table, and how an event counts down and fires (events.py).

Integration tests; the rest are in tests/unit/test_events.py."""
import random
import unittest
from cruel.world import expansion
from tests import support


class EventActivationTests(unittest.TestCase):
    """An event counting down on the floor you're on (gameManager.stepFloorEvent)."""

    def setUp(self):
        random.seed(4)
        self.game = support.newGame()

    def test_an_event_fires_once_its_countdown_runs_out(self):
        self.game.floorEvents[self.game.level] = {"id": "overgrowth", "turnsLeft": 2, "active": False}
        self.game.stepFloorEvent()
        self.assertIsNone(self.game.activeEvent())
        self.game.stepFloorEvent()
        self.assertEqual(self.game.activeEvent(), "overgrowth")
        self.assertTrue(self.game.messageBools["eventMessage"])

    def test_an_event_on_another_floor_is_not_active_here(self):
        self.game.floorEvents[self.game.level + 1] = {"id": "overgrowth", "turnsLeft": 0, "active": True}
        self.assertIsNone(self.game.activeEvent())

    def test_an_active_expansion_brings_in_a_goblin_war_band(self):
        self.game.floorEvents[self.game.level] = {"id": "expansion", "turnsLeft": 0, "active": True}
        self.game.stepFloorEvent()
        event = self.game.floorEvents[self.game.level]
        self.assertTrue(event["spawned"])
        self.assertEqual(len(expansion.camp(self.game)["factions"]), 1)


if __name__ == "__main__":
    unittest.main()
