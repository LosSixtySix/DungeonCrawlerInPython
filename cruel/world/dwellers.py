import math
import random

from cruel.world import expansion
from cruel.world import metropolis
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

Hostility. The city is calm until you do something hostile on it (hostileAct): steal from one of its chests, break
any of its walls, or hurt a Dweller. Only the Dwellers who see it happen turn hostile: within their vision, with a
clear line of sight to the spot (the one you hurt always knows). If nobody sees it, nothing happens.
  - A hostile citizen, noble or merchant runs to the nearest guard and, within TELL_REACH of it, tells it where it
    last saw you. Then it goes home and hides. If it's cornered (you're beside it and it has no free tile further
    from you to run to) it fights back instead. FORGIVE_TURNS after it last saw you, it calms down.
  - A hostile guard, one that saw it or was told, hunts you: to where you were last seen, then after you while it
    sees you. Guards never calm down.
"""

IDLE_CHANCE = 0.4           # a calm Dweller stands still this often
GO_HOME_CHANCE = 0.2        # when it picks somewhere to go, it goes home this often
WANDER_REACH = {"citizen": 10, "noble": 6, "guard": 4, "merchant": 0}
PATH_REACH = 40             # how far a path map reaches
PATH_KEEP_TURNS = 20        # a path map is worked out again after this many turns (walls may have changed)
PATH_CACHE_LIMIT = 200
TELL_REACH = 2              # a fleeing Dweller tells a guard this close to it
FORGIVE_TURNS = 300         # a hostile citizen, noble or merchant calms down after this long without seeing you
SWAP_COOLDOWN = 6           # a Dweller that swapped places with another can't swap again for this many turns
GIVE_UP_TURNS = 8           # a hunting guard that can't take a step for this many turns in a row (someone in the way)
                            # gives up on where you were seen and searches where it is


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


def nudgeAside(game, spot):
    """Moves the citizen, noble or merchant on spot onto a free tile beside it (a hunting guard needs spot). True if
    spot is free now. (If it hadn't had its turn yet, it misses this one, but stays in the game.)"""
    tile = game.grid[spot]
    if tile[0] != 5 or len(tile) < 3 or not isDweller(tile[2]) or tile[2].role == "guard":
        return False
    free = [beside for beside in game.neighbors(spot) if organizers.passable(game.grid[beside])]
    if not free:
        return False
    besideSpot, dweller = random.choice(free), tile.pop()
    organizers.moveTo(game, spot, besideSpot)
    game.grid[besideSpot].append(dweller)
    for positions in (game.EnemyPositions, getattr(game, "movedEnemies", set())):
        positions.discard(spot)
        positions.add(besideSpot)
    game.change = True
    return True


def swapPast(game, position, spot):
    """The Dweller moving from position (lifted off it for its turn) swaps places with the Dweller on spot, which
    has already had its turn (so neither moves twice). Two Dwellers in each other's way, like one in a doorway and
    one outside it, get past each other this way. A Dweller that swapped can't again for SWAP_COOLDOWN turns, so no
    pair swaps back and forth. True if they swapped (the mover then steps onto spot)."""
    tile = game.grid[spot]
    movedThisTurn = getattr(game, "movedEnemies", set())
    if tile[0] != 5 or len(tile) < 3 or not isDweller(tile[2]) or spot not in movedThisTurn:
        return False
    other = tile[2]
    if game.turnCount - getattr(other, "swappedAt", -SWAP_COOLDOWN) < SWAP_COOLDOWN:
        return False
    other.swappedAt = game.turnCount
    tile.pop()  # (spot stays an enemy tile: the mover goes there)
    game.grid[position].append(other)
    movedThisTurn.discard(spot)
    movedThisTurn.add(position)
    game.change = True
    return True


def stepToward(game, position, goal, pushPast=False):
    """One step along the path to goal, onto a free tile. Returns where it ends up (where it was if it can't move).
    pushPast (a hunting guard): a citizen, noble or merchant on the next tile of the path is nudged aside."""
    steps = pathMap(game, goal)
    here = steps.get(position, math.inf)
    if pushPast:
        ahead = [spot for spot in game.neighbors(position) if steps.get(spot, math.inf) < here]
        if ahead:
            nextSpot = min(ahead, key=lambda spot: steps[spot])
            if not organizers.passable(game.grid[nextSpot]) and nudgeAside(game, nextSpot):
                return organizers.moveTo(game, position, nextSpot)
    nearer = [spot for spot in game.neighbors(position)
              if organizers.passable(game.grid[spot]) and steps.get(spot, math.inf) < here]
    if not nearer:  # the way is blocked by another Dweller: swap past it
        ahead = [spot for spot in game.neighbors(position) if steps.get(spot, math.inf) < here]
        if ahead:
            nextSpot = min(ahead, key=lambda spot: steps[spot])
            if swapPast(game, position, nextSpot):
                return nextSpot
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


# ---------------------------------------------------------------- seeing what you do

def cityDwellers(game):
    """(position, Dweller) for every Dweller on the floor. During the enemies' turn it also finds the ones that
    have already moved (gameManager.movedEnemies), which aren't on EnemyPositions until the turn ends."""
    found = []
    for spot in set(game.EnemyPositions) | getattr(game, "movedEnemies", set()):
        tile = game.grid.get(spot)
        if tile and tile[0] == 5 and len(tile) > 2 and isDweller(tile[2]):
            found.append((spot, tile[2]))
    return found


def canSee(game, dwellerSpot, dweller, spot):
    """Can this Dweller see spot: within its vision, with nothing blocking the line between?"""
    return distance(game, dwellerSpot, spot) <= dweller.visionRange and game.lineOfSight(dwellerSpot, spot)


def hostileAct(game, spot, victim=None):
    """You did something hostile at spot on a city floor (stole, broke something, or hurt victim): every Dweller who
    can see spot turns hostile, and so does victim. Returns how many turned hostile (0: nobody saw)."""
    if game.proportion != metropolis.METROPOLIS:
        return 0
    witnesses = [dweller for dwellerSpot, dweller in cityDwellers(game)
                 if dweller is victim or canSee(game, dwellerSpot, dweller, spot)]
    if victim is not None and isDweller(victim) and victim not in witnesses:
        witnesses.append(victim)  # (the one you hurt always knows)
    for dweller in witnesses:
        turnHostile(game, dweller, game.playerPositionFlat)
    if witnesses:
        game.addPopup("Seen!", game.playerPositionFlat)
    return len(witnesses)


def turnHostile(game, dweller, sawYouAt):
    """dweller turns hostile, knowing you were at sawYouAt."""
    dweller.hostile = True
    dweller.goal = None
    dweller.toldGuard = False
    dweller.sawYouAt = sawYouAt
    dweller.lastSawYou = game.turnCount


def tellGuard(game, guardSpot, guard, sawYouAt):
    """A fleeing Dweller reached a guard and told it where you were: the guard hunts you from there."""
    if not guard.hostile:
        game.addPopup("Alarm!", guardSpot)
    turnHostile(game, guard, sawYouAt)


def noticeYou(game, position, dweller):
    """A hostile Dweller looks for you: if it sees you, it remembers where and when."""
    if game.peaceful or not canSee(game, position, dweller, game.playerPositionFlat):
        return False
    dweller.sawYouAt = game.playerPositionFlat
    dweller.lastSawYou = game.turnCount
    return True


def attitudeLabel(enemy):
    """For a Dweller's name when you look at it: "hostile" once it's turned on you. None otherwise."""
    return "hostile" if isDweller(enemy) and enemy.hostile else None


# ---------------------------------------------------------------- a turn

def takeTurn(game, position, dweller):
    """One action for the Dweller at position (already lifted off its tile). Returns where it ends up."""
    if not dweller.hostile:
        return calmTurn(game, position, dweller)
    noticeYou(game, position, dweller)
    if dweller.role == "guard":
        return guardTurn(game, position, dweller)
    if game.turnCount - dweller.lastSawYou >= FORGIVE_TURNS:  # it's calmed down
        dweller.hostile = False
        dweller.toldGuard = False
        return calmTurn(game, position, dweller)
    return fleeTurn(game, position, dweller)


def besideYou(game, position):
    return not game.peaceful and game.playerPositionFlat in game.neighbors(position)


def cornered(game, position):
    """Is a fleeing Dweller cornered: beside you, with no free tile further from you to run to?"""
    if not besideYou(game, position):
        return False
    here = distance(game, position, game.playerPositionFlat)
    return not any(organizers.passable(game.grid[spot]) and distance(game, spot, game.playerPositionFlat) > here
                   for spot in game.neighbors(position))


def nearestGuard(game, position):
    """(position, guard) of the guard nearest position, or None if the city has none left."""
    guards = [(spot, dweller) for spot, dweller in cityDwellers(game) if dweller.role == "guard"]
    return min(guards, key=lambda found: distance(game, position, found[0])) if guards else None


def stepAway(game, position):
    """One step to the free tile furthest from you (a Dweller with no guard to run to)."""
    away = [spot for spot in game.neighbors(position) if organizers.passable(game.grid[spot])]
    if not away:
        return position
    best = max(away, key=lambda spot: distance(game, spot, game.playerPositionFlat))
    if distance(game, best, game.playerPositionFlat) <= distance(game, position, game.playerPositionFlat):
        return position
    return organizers.moveTo(game, position, best)


def fleeTurn(game, position, dweller):
    """A hostile citizen, noble or merchant: cornered, it fights back; otherwise it runs to the nearest guard and
    tells it, then goes home and hides."""
    if cornered(game, position):
        game.hitPlayer(dweller, position)
        return position
    if dweller.toldGuard:
        return stepToward(game, position, dweller.home) if dweller.home not in (None, position) else position
    found = nearestGuard(game, position)
    if found is None:
        return stepAway(game, position)
    guardSpot, guard = found
    if distance(game, position, guardSpot) <= TELL_REACH:
        tellGuard(game, guardSpot, guard, dweller.sawYouAt)
        dweller.toldGuard = True
        return position
    return stepToward(game, position, guardSpot)


def guardTurn(game, position, dweller):
    """A hostile guard: hits you if you're beside it, otherwise heads for where you were last seen. Having lost you
    there, it searches the streets nearby."""
    if besideYou(game, position):
        game.hitPlayer(dweller, position)
        return position
    target = dweller.sawYouAt
    if target is None or target == position:
        dweller.sawYouAt = None
        if dweller.goal is None or dweller.goal == position:
            dweller.goal = pickGoal(game, position, dweller)
        if dweller.goal is None:
            return position
        newPosition = stepToward(game, position, dweller.goal)
        if newPosition == position:
            dweller.goal = None  # can't get there: somewhere else next turn
        return newPosition
    newPosition = stepToward(game, position, target, pushPast=True)
    if newPosition != position:
        dweller.blockedTurns = 0
        return newPosition
    dweller.blockedTurns = getattr(dweller, "blockedTurns", 0) + 1  # someone in the way: it waits for them to move
    if dweller.blockedTurns >= GIVE_UP_TURNS:
        dweller.sawYouAt = None  # it can't get there: it searches where it is
        dweller.blockedTurns = 0
    return position


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
