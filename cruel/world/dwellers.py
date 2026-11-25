import math
import random

from cruel.world import dwellerwork
from cruel.world import expansion
from cruel.world import metropolis
from cruel.world import occupancy
from cruel.world import organizers

"""
The Metropolis's Dwellers at work (metropolis.py builds the city, enemies.Dweller and its four roles are the units).

  Citizen   walks the streets near where it is, and goes home now and then.
  Noble     walks near its mansion (and the plaza), and goes home now and then.
  Guard     patrols within PATROL_REACH of its post.
  Merchant  minds its shop: it stands at its counter.
  Worker    a citizen on one of the city's works floors (mineshafts.py): it works (dwellerwork.py).
  Grub      a Dew Grub, the city's livestock: it stays in its pen (unless a farmer leads it to another) and
            never fights (dwellerwork.py, dewgrubs.py).
  Queen     the Dweller Queen, and her court: Royal Guards (guards with a leash: they never go more than leash tiles
            from their post beside her) and Royal Pupae (queen.py).

They walk with path maps (expansion.walkingDistances), so they go round walls and through doors instead of bumping
into them. A path map is kept for a while per destination (PATH_KEEP_TURNS), since Dwellers keep going to the same
places (their homes, posts and counters).

Hostility. The city is calm until you do something hostile on it (hostileAct): steal from one of its chests, break
any of its buildings' walls (the rock round them is anyone's), or hurt a Dweller. Its works floors (mineshafts.py)
are the same. Only the Dwellers who see it happen turn hostile: within their vision, with a
clear line of sight to the spot (the one you hurt always knows). If nobody sees it, nothing happens.
  - A hostile citizen, noble or merchant runs to the nearest guard and, within TELL_REACH of it, tells it where it
    last saw you. Then it goes home and hides. If it's cornered (you're beside it and it has no free tile further
    from you to run to) it fights back instead. FORGIVE_TURNS after it last saw you, it calms down.
  - A hostile guard, one that saw it or was told, hunts you: to where you were last seen, then after you while it
    sees you. Guards never calm down.

Enemies of the city. Every Dweller is always hostile to every monster that isn't a Dweller or the Gray Peddler
(isCityEnemy): goblins of any faction (neutral ones too) or none, and anything else. Only guards hunt and kill
them: a guard goes after any enemy it can see, or one it has been told about. A citizen, noble or merchant that sees
an enemy runs to the nearest guard and, within TELL_REACH, tells it where the enemy is (then goes back to its day);
with no guard left, it runs away from the enemy. Only when it's cornered by one (the enemy beside it, no free tile
further away) does it fight back. None of this turns the city against you.
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

def pathMap(game, goal, throughPlants=False):
    """{tile: steps to goal}, kept for PATH_KEEP_TURNS on this floor. throughPlants (a farmer): through any plant."""
    cache = game.__dict__.setdefault("dwellerPaths", {})
    key = (game.level, getattr(game, "sideFloor", None), game.turnCount // PATH_KEEP_TURNS, goal, throughPlants)
    if key not in cache:
        if len(cache) > PATH_CACHE_LIMIT:
            cache.clear()
        cache[key] = expansion.walkingDistances(game, goal, PATH_REACH, plantsOpen=throughPlants)
    return cache[key]


def canStep(game, spot, throughPlants=False, unit=None):
    """Can a Dweller (unit) step onto spot? Passable (with throughPlants any plant but Organizer's Demise), or a
    space it can share with the one there (occupancy.canJoin: Dwellers are small)."""
    tile = game.grid[spot]
    if expansion.canEnter(tile, throughPlants) if throughPlants else organizers.passable(tile):
        return True
    return unit is not None and occupancy.canJoin(game, spot, unit)


def canBeMoved(unit):
    """Can another Dweller move this one out of its way (nudgeAside, swapPast)? Not the Queen or anything else
    bigger than a space, and not a Royal Pupa (it can't move)."""
    return getattr(unit, "size", 1) == 1 and getattr(unit, "role", None) not in ("queen", "pupa")


def nudgeAside(game, spot):
    """Moves the citizen, noble or merchant on spot onto a free tile beside it (a hunting guard needs spot). True if
    spot is free now. (If it hadn't had its turn yet, it misses this one, but stays in the game.)"""
    tile = game.grid[spot]
    if tile[0] != 5 or len(tile) < 3 or not isDweller(tile[2]) or tile[2].role == "guard" or not canBeMoved(tile[2]):
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


def swapPast(game, position, spot, force=False):
    """The Dweller moving from position (lifted off it for its turn) swaps places with the Dweller on spot, which
    has already had its turn (so neither moves twice). Two Dwellers in each other's way, like one in a doorway and
    one outside it, get past each other this way. A Dweller that swapped can't again for SWAP_COOLDOWN turns, so no
    pair swaps back and forth, unless force (the mover has been stuck a while: a worker in a queue at a door,
    dwellerwork.walkTo). True if they swapped (the mover then steps onto spot)."""
    tile = game.grid[spot]
    movedThisTurn = getattr(game, "movedEnemies", set())
    if tile[0] != 5 or len(tile) < 3 or not isDweller(tile[2]) or spot not in movedThisTurn or not canBeMoved(tile[2]):
        return False
    if occupancy.stillOccupied(game, position) or spot in occupancy.sharedTiles(game):
        return False  # (only two units each alone on their space swap)
    other = tile[2]
    if other.role == "grub" and position not in other.pen and position not in (other.headedTo or ()):
        return False  # (livestock is only swapped into its pen, or the one a farmer is moving it to)
    if not force and game.turnCount - getattr(other, "swappedAt", -SWAP_COOLDOWN) < SWAP_COOLDOWN:
        return False
    other.swappedAt = game.turnCount
    tile.pop()  # (spot stays an enemy tile: the mover goes there)
    game.grid[position].append(other)
    movedThisTurn.discard(spot)
    movedThisTurn.add(position)
    game.change = True
    return True


def stepToward(game, position, goal, pushPast=False, forceSwap=False, throughPlants=False, unit=None):
    """One step along the path to goal, onto a free tile (or one unit, the Dweller moving, can share). Returns where
    it ends up (where it was if it can't move). pushPast (a hunting guard): a citizen, noble or merchant on the next
    tile of the path is nudged aside. forceSwap: a Dweller in the way swaps past even if it swapped lately
    (swapPast). throughPlants (a farmer, like a goblin farmer): it walks through any plant."""
    steps = pathMap(game, goal, throughPlants)
    here = steps.get(position, math.inf)
    if pushPast:
        ahead = [spot for spot in game.neighbors(position) if steps.get(spot, math.inf) < here]
        if ahead:
            nextSpot = min(ahead, key=lambda spot: steps[spot])
            if not organizers.passable(game.grid[nextSpot]) and nudgeAside(game, nextSpot):
                return organizers.moveTo(game, position, nextSpot)
    nearer = [spot for spot in game.neighbors(position)
              if canStep(game, spot, throughPlants, unit) and steps.get(spot, math.inf) < here]
    if not nearer:  # the way is blocked by another Dweller: swap past it
        ahead = [spot for spot in game.neighbors(position) if steps.get(spot, math.inf) < here]
        if ahead:
            nextSpot = min(ahead, key=lambda spot: steps[spot])
            if swapPast(game, position, nextSpot, force=forceSwap):
                return nextSpot
    if not nearer and position not in steps:  # too far for the path map: just head that way
        nearer = [spot for spot in game.neighbors(position)
                  if canStep(game, spot, throughPlants, unit) and distance(game, spot, goal) < distance(game, position, goal)]
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
    """(position, Dweller) for every Dweller on the floor, two on a space included (occupancy.allUnits: during the
    enemies' turn it also finds the ones that have already moved)."""
    return [(spot, unit) for spot, unit in occupancy.allUnits(game) if isDweller(unit)]


def canSee(game, dwellerSpot, dweller, spot):
    """Can this Dweller see spot: within its vision, with nothing blocking the line between?"""
    return distance(game, dwellerSpot, spot) <= dweller.visionRange and game.lineOfSight(dwellerSpot, spot)


def onDwellerFloor(game):
    """Is this a floor the Dwellers keep: a city, or one of its works floors (mineshafts.py)?"""
    return game.proportion == metropolis.METROPOLIS or getattr(game, "sideFloor", None) is not None


def hostileAct(game, spot, victim=None):
    """You did something hostile at spot on a Dweller floor (stole, broke one of its buildings, or hurt victim):
    every Dweller who can see spot turns hostile, and so does victim. Returns how many turned hostile (0: nobody
    saw)."""
    if not onDwellerFloor(game):
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
    """A hostile Dweller looks for you: if it sees you, it remembers where and when (a Royal Guard: only while you're
    within its leash; outside it, it forgets where you went)."""
    if game.peaceful or not canSee(game, position, dweller, game.playerPositionFlat):
        return False
    if not withinLeash(game, dweller, game.playerPositionFlat):
        dweller.sawYouAt = None
        return False
    dweller.sawYouAt = game.playerPositionFlat
    dweller.lastSawYou = game.turnCount
    return True


def attitudeLabel(enemy):
    """For a Dweller's name when you look at it: "hostile" once it's turned on you; a Dew Grub: "livestock", and
    whether its Dew is ready. None otherwise."""
    if isDweller(enemy) and enemy.role == "grub":
        if not getattr(enemy, "grown", True):
            return "livestock, young"
        return "livestock, Dew ready" if enemy.dewReady else "livestock"
    return "hostile" if isDweller(enemy) and enemy.hostile else None


# ---------------------------------------------------------------- a turn

def isCityEnemy(enemy):
    """Is this a monster the Dwellers are always hostile to: anything but a Dweller or the Gray Peddler (every
    goblin included, a neutral faction's too)?"""
    return enemy is not None and not isDweller(enemy) and not getattr(enemy, "merchant", False)


def isGoblin(enemy):
    """Any goblin: a faction's (neutral or not) or a wild one, builders and farmers included."""
    return getattr(enemy, "name", "").startswith("Goblin")


def enemyBeside(game, position):
    """(position, enemy) of an enemy of the city right beside position, or None."""
    for spot in game.neighbors(position):
        tile = game.grid[spot]
        if tile[0] == 5 and len(tile) > 2 and isCityEnemy(tile[2]):
            return spot, tile[2]
    return None


def withinLeash(game, dweller, spot):
    """Is spot somewhere this Dweller will go? A Royal Guard won't go more than its leash from its post."""
    leash = getattr(dweller, "leash", None)
    return leash is None or dweller.home is None or distance(game, dweller.home, spot) <= leash


def enemyInSight(game, position, dweller):
    """(position, enemy) of the nearest enemy of the city this Dweller can see (and will go after: withinLeash), or
    None."""
    seen = []
    for spot in set(game.EnemyPositions) | getattr(game, "movedEnemies", set()):
        tile = game.grid.get(spot)
        if tile and tile[0] == 5 and len(tile) > 2 and isCityEnemy(tile[2]) and canSee(game, position, dweller, spot) \
                and withinLeash(game, dweller, spot):
            seen.append((distance(game, position, spot), spot, tile[2]))
    if not seen:
        return None
    _, spot, enemy = min(seen, key=lambda found: found[0])
    return spot, enemy


def guardAgainstEnemies(game, position, guard):
    """A guard against the city's enemies: it hits one beside it, heads for one it can see, or goes to where it was
    told one is. (A guard hunting you deals with you first.) Returns where it ends up, or None if there's nothing
    for it to do."""
    huntingYou = guard.hostile and (guard.sawYouAt is not None or besideYou(game, position))
    if huntingYou:
        return None
    beside = enemyBeside(game, position)
    if beside is not None:
        enemySpot, enemy = beside
        expansion.attack(game, position, guard, enemy, enemySpot)  # (it fights back)
        return position
    seen = enemyInSight(game, position, guard)
    if seen is not None:
        guard.enemyAt = None  # it's found it
        return stepToward(game, position, seen[0], pushPast=True, unit=guard)
    toldOf = getattr(guard, "enemyAt", None)
    if toldOf is not None and not withinLeash(game, guard, toldOf):
        toldOf = guard.enemyAt = None  # (too far from the Queen for a Royal Guard)
    if toldOf is not None:
        if distance(game, position, toldOf) <= 1:
            guard.enemyAt = None  # nothing there now
            return position
        return stepToward(game, position, toldOf, pushPast=True, unit=guard)
    return None


def raiseTheAlarm(game, position, dweller):
    """A citizen, noble or merchant against the city's enemies: cornered by one, it fights back; seeing one, it
    runs to the nearest guard to tell it where (or, with no guard left, away from the enemy). Returns where it ends
    up, or None if it has no enemy to deal with."""
    beside = enemyBeside(game, position)
    if beside is not None and corneredBy(game, position, beside[0]):
        expansion.attack(game, position, dweller, beside[1], beside[0])
        return position
    seen = enemyInSight(game, position, dweller)
    if seen is not None:
        dweller.enemyAt = seen[0]  # what it will tell a guard
    enemyAt = getattr(dweller, "enemyAt", None)
    if enemyAt is None:
        return None
    found = nearestGuard(game, position)
    if found is None:
        return stepAwayFrom(game, position, enemyAt)
    guardSpot, guard = found
    if distance(game, position, guardSpot) <= TELL_REACH:
        if getattr(guard, "enemyAt", None) is None:
            game.addPopup("!", guardSpot)
        guard.enemyAt = enemyAt
        dweller.enemyAt = None  # told: back to its day
        return position
    return stepToward(game, position, guardSpot, unit=dweller)


def dealWithEnemies(game, position, dweller):
    """Guards fight the city's enemies; everyone else raises the alarm. None if there's nothing to deal with."""
    if dweller.role == "guard":
        return guardAgainstEnemies(game, position, dweller)
    return raiseTheAlarm(game, position, dweller)


def takeTurn(game, position, dweller):
    """One action for the Dweller at position (already lifted off its tile). Returns where it ends up."""
    if dweller.role == "grub":  # livestock: it just shuffles about its pen (dwellerwork.py)
        return dwellerwork.grubTurn(game, position, dweller)
    if dweller.role == "pupa":  # turning royal: it waits (queen.py)
        return position
    dealtWith = dealWithEnemies(game, position, dweller)
    if dealtWith is not None:
        return dealtWith
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


def corneredBy(game, position, threatSpot):
    """Is a Dweller at position cornered by whatever is on threatSpot: right beside it, with no free tile further
    from it to run to?"""
    if threatSpot not in game.neighbors(position):
        return False
    here = distance(game, position, threatSpot)
    return not any(organizers.passable(game.grid[spot]) and distance(game, spot, threatSpot) > here
                   for spot in game.neighbors(position))


def cornered(game, position):
    """Is a fleeing Dweller cornered by you?"""
    return besideYou(game, position) and corneredBy(game, position, game.playerPositionFlat)


def nearestGuard(game, position):
    """(position, guard) of the guard nearest position, or None if the city has none left."""
    guards = [(spot, dweller) for spot, dweller in cityDwellers(game) if dweller.role == "guard"]
    return min(guards, key=lambda found: distance(game, position, found[0])) if guards else None


def stepAwayFrom(game, position, threatSpot):
    """One step to the free tile furthest from threatSpot (a Dweller with no guard to run to)."""
    away = [spot for spot in game.neighbors(position) if organizers.passable(game.grid[spot])]
    if not away:
        return position
    best = max(away, key=lambda spot: distance(game, spot, threatSpot))
    if distance(game, best, threatSpot) <= distance(game, position, threatSpot):
        return position
    return organizers.moveTo(game, position, best)


def stepAway(game, position):
    """One step to the free tile furthest from you."""
    return stepAwayFrom(game, position, game.playerPositionFlat)


def fleeTurn(game, position, dweller):
    """A hostile citizen, noble or merchant: cornered, it fights back; otherwise it runs to the nearest guard and
    tells it, then goes home and hides."""
    if cornered(game, position):
        game.hitPlayer(dweller, position)
        return position
    if dweller.toldGuard:
        return stepToward(game, position, dweller.home, unit=dweller) if dweller.home not in (None, position) else position
    found = nearestGuard(game, position)
    if found is None:
        return stepAway(game, position)
    guardSpot, guard = found
    if distance(game, position, guardSpot) <= TELL_REACH:
        tellGuard(game, guardSpot, guard, dweller.sawYouAt)
        dweller.toldGuard = True
        return position
    return stepToward(game, position, guardSpot, unit=dweller)


def guardTurn(game, position, dweller):
    """A hostile guard: hits you if you're beside it, otherwise heads for where you were last seen. Having lost you
    there, it searches the streets nearby (a Royal Guard: near its post)."""
    if besideYou(game, position):
        game.hitPlayer(dweller, position)
        return position
    if dweller.sawYouAt is not None and not withinLeash(game, dweller, dweller.sawYouAt):
        dweller.sawYouAt = None
    target = dweller.sawYouAt
    if target is None or target == position:
        dweller.sawYouAt = None
        if dweller.goal is None or dweller.goal == position:
            dweller.goal = pickGoal(game, position, dweller)
        if dweller.goal is None:
            return position
        newPosition = stepToward(game, position, dweller.goal, unit=dweller)
        if newPosition == position:
            dweller.goal = None  # can't get there: somewhere else next turn
        return newPosition
    newPosition = stepToward(game, position, target, pushPast=True, unit=dweller)
    if newPosition != position:
        dweller.blockedTurns = 0
        return newPosition
    dweller.blockedTurns = getattr(dweller, "blockedTurns", 0) + 1  # someone in the way: it waits for them to move
    if dweller.blockedTurns >= GIVE_UP_TURNS:
        dweller.sawYouAt = None  # it can't get there: it searches where it is
        dweller.blockedTurns = 0
    return position


def calmTurn(game, position, dweller):
    """Going about its day: workers work (dwellerwork.py); merchants stay put; the others stand about or walk
    somewhere."""
    if dwellerwork.isWorker(dweller):
        worked = dwellerwork.workTurn(game, position, dweller)
        if worked is not None:
            return worked
    if dweller.role == "merchant" or random.random() < IDLE_CHANCE:
        return position
    if dweller.goal is None or dweller.goal == position:
        dweller.goal = pickGoal(game, position, dweller)
    if dweller.goal is None:
        return position
    newPosition = stepToward(game, position, dweller.goal, unit=dweller)
    if newPosition == position:
        dweller.goal = None  # blocked: somewhere else next time
    return newPosition
