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
        game = self.game
        game.floorEvents[game.level] = {"id": "overgrowth", "turnsLeft": 2, "active": False}
        game.stepFloorEvent()
        self.assertIsNone(game.activeEvent())
        game.stepFloorEvent()
        self.assertEqual(game.activeEvent(), "overgrowth")
        self.assertTrue(game.messageBools["eventMessage"])

    def test_an_event_on_another_floor_is_not_active_here(self):
        game = self.game
        game.floorEvents[game.level + 1] = {"id": "overgrowth", "turnsLeft": 0, "active": True}
        self.assertIsNone(game.activeEvent())

    def test_an_active_expansion_brings_in_a_goblin_war_band(self):
        game = self.game
        game.floorEvents[game.level] = {"id": "expansion", "turnsLeft": 0, "active": True}
        game.stepFloorEvent()
        event = game.floorEvents[game.level]
        self.assertTrue(event["spawned"])
        self.assertEqual(len(expansion.camp(game)["factions"]), 1)


if __name__ == "__main__":
    unittest.main()
