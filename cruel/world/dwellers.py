import math
import random

from cruel.world import expansion
from cruel.world import organizers

"""
The Metropolis's Dwellers at work (metropolis.py builds the city, enemies.Dweller and its four roles are the units).

  Citizen   walks the streets near where it is, and goes home now and then.
  Noble     walks near its mansion (and the plaza), and goes home now and then.
  Guard     patrols within PATROL_REACH of its post.
  Merchant  minds its shop: it stands at its counter.

They walk with path maps (expansion.walkingDistances), so they go round walls and through doors instead of bumping
into them. A path map is kept for a while per destination (PATH_KEEP_TURNS), since Dwellers keep going to the same
places (their homes, posts and counters).
"""

IDLE_CHANCE = 0.4           # a calm Dweller stands still this often
GO_HOME_CHANCE = 0.2        # when it picks somewhere to go, it goes home this often
WANDER_REACH = {"citizen": 10, "noble": 6, "guard": 4, "merchant": 0}
PATH_REACH = 40             # how far a path map reaches
PATH_KEEP_TURNS = 20        # a path map is worked out again after this many turns (walls may have changed)
PATH_CACHE_LIMIT = 200


def isDweller(enemy):
    return getattr(enemy, "dweller", False)


def distance(game, spot, other):
    rowLength = game.rowLength
    return math.hypot(spot % rowLength - other % rowLength, spot // rowLength - other // rowLength)


# ---------------------------------------------------------------- walking

def pathMap(game, goal):
    """{tile: steps to goal}, kept for PATH_KEEP_TURNS on this floor."""
    cache = game.__dict__.setdefault("dwellerPaths", {})
    key = (game.level, game.turnCount // PATH_KEEP_TURNS, goal)
    if key not in cache:
        if len(cache) > PATH_CACHE_LIMIT:
            cache.clear()
        cache[key] = expansion.walkingDistances(game, goal, PATH_REACH)
    return cache[key]


def stepToward(game, position, goal):
    """One step along the path to goal, onto a free tile. Returns where it ends up (where it was if it can't move)."""
    steps = pathMap(game, goal)
    here = steps.get(position, math.inf)
    nearer = [spot for spot in game.neighbors(position)
              if organizers.passable(game.grid[spot]) and steps.get(spot, math.inf) < here]
    if not nearer and position not in steps:  # too far for the path map: just head that way
        nearer = [spot for spot in game.neighbors(position)
                  if organizers.passable(game.grid[spot]) and distance(game, spot, goal) < distance(game, position, goal)]
    if not nearer:
        return position
    best = min(nearer, key=lambda spot: steps.get(spot, distance(game, spot, goal)))
    return organizers.moveTo(game, position, best)


def pickGoal(game, position, dweller):
    """Somewhere for a calm Dweller to walk to: home now and then, otherwise a free tile near it (a guard: near
    its post)."""
    if dweller.home is not None and dweller.role != "guard" and random.random() < GO_HOME_CHANCE:
        return dweller.home
    reach = WANDER_REACH[dweller.role]
    anchor = dweller.home if dweller.role == "guard" and dweller.home is not None else position
    rowLength = game.rowLength
    choices = []
    for rowOffset in range(-reach, reach + 1):
        for columnOffset in range(-reach, reach + 1):
            column = anchor % rowLength + columnOffset
            spot = anchor + columnOffset + rowOffset * rowLength
            if 0 <= column < rowLength and spot in game.grid and spot != position and organizers.passable(game.grid[spot]):
                choices.append(spot)
    return random.choice(choices) if choices else None


# ---------------------------------------------------------------- a turn

def takeTurn(game, position, dweller):
    """One action for the Dweller at position (already lifted off its tile). Returns where it ends up."""
    return calmTurn(game, position, dweller)


def calmTurn(game, position, dweller):
    """Going about its day: merchants stay put; the others stand about or walk somewhere."""
    if dweller.role == "merchant" or random.random() < IDLE_CHANCE:
        return position
    if dweller.goal is None or dweller.goal == position:
        dweller.goal = pickGoal(game, position, dweller)
    if dweller.goal is None:
        return position
    newPosition = stepToward(game, position, dweller.goal)
    if newPosition == position:
        dweller.goal = None  # blocked: somewhere else next time
    return newPosition
