"""The EventDispatcher that routes pygame events to the handlers that subscribed to them."""
import unittest
from types import SimpleNamespace

import pygame

import tests  # noqa: F401
from cruel.core.EventDispatcher import EventDispatcher


def makeEvent(eventType, **details):
    return SimpleNamespace(type=eventType, **details)


class EventDispatcherTests(unittest.TestCase):
    """Subscribing handlers and dispatching events to them."""

    def test_a_subscribed_handler_receives_its_event(self):
        dispatcher, received = EventDispatcher(), []
        dispatcher.subscribe("hit", received.append)
        hitEvent = makeEvent("hit", amount=3)
        dispatcher.dispatch(hitEvent)
        self.assertEqual(received, [hitEvent])

    def test_a_handler_ignores_other_event_types(self):
        dispatcher, received = EventDispatcher(), []
        dispatcher.subscribe("hit", received.append)
        dispatcher.dispatch(makeEvent("heal"))
        self.assertEqual(received, [])

    def test_an_event_nobody_subscribed_to_is_harmless(self):
        EventDispatcher().dispatch(makeEvent("nothing"))

    def test_handlers_run_in_the_order_they_subscribed(self):
        dispatcher, callOrder = EventDispatcher(), []
        dispatcher.subscribe("turn", lambda event: callOrder.append("first"))
        dispatcher.subscribe("turn", lambda event: callOrder.append("second"))
        dispatcher.dispatch(makeEvent("turn"))
        dispatcher.dispatch(makeEvent("turn"))
        self.assertEqual(callOrder, ["first", "second", "first", "second"])

    def test_real_pygame_key_events_route_by_type(self):
        dispatcher, keysPressed = EventDispatcher(), []
        dispatcher.subscribe(pygame.KEYDOWN, keysPressed.append)
        dispatcher.dispatch(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
        dispatcher.dispatch(pygame.event.Event(pygame.KEYUP, key=pygame.K_a))
        self.assertEqual([event.key for event in keysPressed], [pygame.K_a])


if __name__ == "__main__":
    unittest.main()
