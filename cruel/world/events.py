import random

"""
Floor events: something that can happen on a floor while you're on it. Each new floor (from floor 2 down)
rolls EVENT_CHANCE for an event. If it gets one, the event fires a few turns after you arrive (DELAY), with its
name shown big on screen like "The Seal is Broken", and lasts for the rest of that floor.

Every floor type can get one, the Metropolis included. When Overgrowth starts on a floor with no plants at all (a
city, say), OVERGROWTH_SEEDS wild patches spring up in random places so it has something to grow.

Each event's "plants" entry changes how plants grow while it's active (see plants.step):
  growTurns   a growth step happens this often (normally plants.GROW_TURNS)
  birth       births are this many times as likely
  death       the chance a lonely or crowded wild plant withers (normally plants.DEATH_CHANCE)
  corrupt     plants corrupt the walls around them, which then spread the plant (see plants.py)
"""

EVENT_CHANCE = 0.2     # chance a new floor gets an event
FIRST_FLOOR = 1        # no events before this floor (0 is the first floor)
DELAY = (15, 60)       # the event fires this many turns after you first arrive (random in this range)
OVERGROWTH_SEEDS = 3   # wild patches Overgrowth plants when it starts on a floor with no plants

EVENTS = {
    "overgrowth": {"name": "Overgrowth", "description": "Plants grow much faster, rarely wither and creep into the walls",
                   "plants": {"growTurns": 3, "birth": 1.5, "death": 0.05, "corrupt": True}},
    "expansion": {"name": "Expansion", "description": "A goblin war band arrives and builds a camp (expansion.py)"},
}


def roll(depth):
    """The event waiting on a new floor at this depth, or None: {"id", "turnsLeft", "active"}."""
    if depth < FIRST_FLOOR or random.random() >= EVENT_CHANCE:
        return None
    return {"id": random.choice(list(EVENTS)), "turnsLeft": random.randint(*DELAY), "active": False}


def name(eventId):
    return EVENTS[eventId]["name"]


def plantRules(eventId):
    """How plants grow under this event ({} if it doesn't change them)."""
    return EVENTS[eventId].get("plants", {}) if eventId else {}
