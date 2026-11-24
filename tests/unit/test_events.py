"""Floor events: rolling one for a new floor, the event table, and how an event counts down and fires (events.py).

Unit tests; the rest are in tests/integration/test_events.py."""
import random
import unittest
from unittest import mock
from cruel.world import events


class EventTableTests(unittest.TestCase):
    """The EVENTS table and its lookups."""

    def test_every_event_has_a_name_and_description(self):
        for eventId, eventDetails in events.EVENTS.items():
            self.assertTrue(eventDetails["name"])
            self.assertTrue(eventDetails["description"])
            self.assertEqual(events.name(eventId), eventDetails["name"])

    def test_overgrowth_speeds_up_plants_and_lets_them_corrupt_walls(self):
        rules = events.plantRules("overgrowth")
        self.assertEqual(rules["growTurns"], 3)
        self.assertGreater(rules["birth"], 1)
        self.assertTrue(rules["corrupt"])

    def test_events_without_plant_rules_and_no_event_change_nothing(self):
        self.assertEqual(events.plantRules("expansion"), {})
        self.assertEqual(events.plantRules(None), {})


class EventRollTests(unittest.TestCase):
    """Whether a new floor gets an event, and what it looks like."""

    def test_the_first_floor_never_gets_an_event(self):
        with mock.patch("random.random", return_value=0.0):
            self.assertIsNone(events.roll(0))

    def test_a_lucky_roll_gives_a_waiting_event(self):
        random.seed(2)
        with mock.patch("random.random", return_value=0.0):
            event = events.roll(4)
        self.assertIn(event["id"], events.EVENTS)
        self.assertFalse(event["active"])
        low, high = events.DELAY
        self.assertTrue(low <= event["turnsLeft"] <= high)

    def test_an_unlucky_roll_gives_no_event(self):
        with mock.patch("random.random", return_value=events.EVENT_CHANCE):
            self.assertIsNone(events.roll(4))

    def test_about_one_floor_in_five_gets_an_event(self):
        random.seed(3)
        eventCount = sum(events.roll(3) is not None for _ in range(4000))
        self.assertAlmostEqual(eventCount / 4000, events.EVENT_CHANCE, delta=0.03)


if __name__ == "__main__":
    unittest.main()
